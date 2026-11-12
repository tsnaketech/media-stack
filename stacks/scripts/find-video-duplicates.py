#!/usr/bin/env python3
"""Read-only video duplicate detection with cached fingerprints and CSV/HTML reports."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import hashlib
import html
import itertools
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import statistics
import subprocess
import sys
import time

EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".m4v", ".webm", ".wmv", ".ts", ".m2ts"}
VERSION = 1
FIELDS = ["group", "classification", "similar_frames_percent", "mean_hash_distance",
          "path_a", "path_b", "size_a", "size_b", "duration_a", "duration_b",
          "resolution_a", "resolution_b", "codec_a", "codec_b", "decision"]


@contextmanager
def reader(uid):
    """Temporarily use an application UID for host bind mounts, then restore root."""
    previous = os.geteuid()
    try:
        if uid is not None and uid != previous:
            os.seteuid(uid)
        yield
    finally:
        if os.geteuid() != previous:
            os.seteuid(previous)


def identity(path, uid):
    with reader(uid):
        s = path.stat()
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns]


def inventory(roots, uid):
    videos, aliases, errors, seen = [], [], [], {}
    with reader(uid):
        for root in roots:
            try:
                available = root.is_dir()
            except OSError:
                available = False
            if not available:
                errors.append((str(root), "inventory", "Directory missing or inaccessible"))
                continue
            def failed(error):
                errors.append((str(error.filename), "inventory", str(error)))
            for parent, directories, files in os.walk(root, followlinks=False, onerror=failed):
                directories.sort()
                for name in sorted(files):
                    path = Path(parent) / name
                    if path.suffix.lower() not in EXTENSIONS or path.is_symlink():
                        continue
                    try:
                        stamp = identity(path, uid)
                    except OSError as error:
                        errors.append((str(path), "inventory", str(error)))
                        continue
                    key = tuple(stamp[:2])
                    if key in seen:
                        if str(path) != seen[key]:
                            aliases.append((seen[key], str(path)))
                        continue
                    seen[key] = str(path)
                    videos.append({"path": str(path), "stamp": stamp, "size": stamp[2]})
    return videos, aliases, errors


def sha256(path, uid):
    digest = hashlib.sha256()
    with reader(uid), Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def frame_hash(pixels):
    """64-bit dHash; discard dark or nearly uniform frames."""
    if len(pixels) != 72 or max(pixels) - min(pixels) < 20 or statistics.mean(pixels) < 8:
        return None
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    if bits.bit_count() < 5 or bits.bit_count() > 59:
        return None
    return bits


def visual_match(a, b):
    duration_a, duration_b = a.get("duration", 0), b.get("duration", 0)
    if min(duration_a, duration_b) <= 0 or abs(duration_a - duration_b) > max(2, min(duration_a, duration_b) * .02):
        return None
    distances = [(x ^ y).bit_count() for x, y in zip(a.get("hashes", []), b.get("hashes", []))
                 if x is not None and y is not None]
    if len(distances) < max(6, len(a.get("hashes", [])) // 2):
        return None
    fraction = sum(d <= 10 for d in distances) / len(distances)
    mean = statistics.mean(distances)
    if fraction < .6 or mean > 14:
        return None
    return ("probable_visual" if fraction >= .8 and mean <= 8 else "possible_visual",
            round(100 * fraction, 1), round(mean, 2))


class Scanner:
    def __init__(self, args):
        self.args = args

    def run(self, tool, arguments, timeout):
        if self.args.container:
            command = ["docker", "exec", "-u", self.args.container_user, self.args.container,
                       "nice", "-n", "10", "ionice", "-c", "3", self.args.ffmpeg_dir + "/" + tool]
        else:
            command = [tool]
        result = subprocess.run(command + arguments, capture_output=True, timeout=timeout,
                                user=None if self.args.container else self.args.read_uid)
        if result.returncode:
            # Keep output short; diagnostics remain in local reports.
            raise RuntimeError(f"{tool}: " + result.stderr.decode(errors="replace")[-600:].strip())
        return result.stdout

    def probe(self, path):
        data = json.loads(self.run("ffprobe", ["-v", "error", "-show_streams", "-show_format",
                                               "-of", "json", path], 30))
        stream = next(s for s in data["streams"] if s.get("codec_type") == "video"
                      and not s.get("disposition", {}).get("attached_pic"))
        return {"duration": float(data.get("format", {}).get("duration") or stream.get("duration") or 0),
                "resolution": f"{stream.get('width', 0)}x{stream.get('height', 0)}",
                "codec": stream.get("codec_name", ""), "stream": stream["index"]}

    def fingerprints(self, path, metadata):
        duration = metadata["duration"]
        if duration <= 0:
            raise RuntimeError("Cannot fingerprint video with unknown duration")
        hashes = []
        for index in range(self.args.frames):
            position = duration * (.05 + .9 * index / (self.args.frames - 1))
            pixels = self.run("ffmpeg", ["-nostdin", "-v", "error", "-threads", "1", "-ss", str(position),
                "-i", path, "-map", f"0:{metadata['stream']}", "-frames:v", "1", "-an", "-sn",
                "-vf", "scale=9:8,format=gray", "-threads", "1", "-f", "rawvideo", "pipe:1"], 45)
            hashes.append(frame_hash(pixels))
        return hashes


def spreadsheet_safe(value):
    value = str(value)
    return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r", "\n")) else value


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as out:
        writer = csv.writer(out, delimiter=";")
        writer.writerow(fields)
        for row in rows:
            writer.writerow([spreadsheet_safe(value) for value in row])
    path.chmod(0o600)


def report(folder, pairs, aliases, errors, total, cache_hits, exact_only):
    fields = FIELDS
    rows = [[pair.get(field, "") for field in fields] for pair in pairs]
    write_csv(folder / "duplicates.csv", fields, rows)
    write_csv(folder / "hardlinks.csv", ["path_a", "path_b"], aliases)
    write_csv(folder / "errors.csv", ["path", "stage", "error"], errors)
    labels = {"exact": "Identiques (SHA-256)", "probable_visual": "Forte ressemblance",
              "possible_visual": "À vérifier"}
    esc = lambda text: html.escape(str(text), quote=True)
    lines = []
    for pair in pairs:
        lines.append("<tr>" + "".join(f"<td>{esc(v)}</td>" for v in [pair['group'], labels[pair['classification']],
            pair['path_a'], pair['path_b'], f"{pair['size_a'] / 1048576:.1f} / {pair['size_b'] / 1048576:.1f} Mo",
            f"{pair['resolution_a']} / {pair['resolution_b']}",
            f"{pair['duration_a']} / {pair['duration_b']} s", pair.get('similar_frames_percent', '')]) + "</tr>")
    warning = "<strong>Analyse incomplète : consulter errors.csv.</strong>" if errors else "Aucune erreur de lecture signalée."
    content = f'''<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><title>Doublons vidéo</title>
<style>body{{font:16px system-ui;margin:2rem;background:#111827;color:#e5e7eb}}
input{{padding:.6rem;width:min(90%,40rem)}}table{{border-collapse:collapse;width:100%;margin-top:1rem}}
td,th{{padding:.6rem;border:1px solid #4b5563;text-align:left;overflow-wrap:anywhere}}a{{color:#93c5fd}}
td:nth-child(3),td:nth-child(4){{min-width:15rem}}.scroll{{overflow:auto}}</style>
<h1>Doublons vidéo</h1><p>{total} fichiers distincts · {len(pairs)} paires candidates ·
{len(aliases)} liens physiques · {cache_hits} entrées en cache · {len(errors)} erreurs.</p>
<p>{warning} Analyse visuelle : {'désactivée' if exact_only else 'activée'}.</p>
<p>Seul SHA-256 confirme une copie exacte. Les ressemblances visuelles sont des pistes à vérifier,
pas des probabilités. Les vidéos coupées ou recadrées peuvent échapper à la détection.
Aucun fichier n’a été modifié ou supprimé.</p>
<p><a href="duplicates.csv">Paires CSV</a> · <a href="hardlinks.csv">Liens physiques CSV</a> ·
<a href="errors.csv">Erreurs CSV</a></p><label>Filtrer <input id="filter" type="search"></label>
<div class="scroll"><table><thead><tr><th>Groupe</th><th>Résultat</th><th>Vidéo A</th><th>Vidéo B</th>
<th>Tailles</th><th>Résolutions</th><th>Durées</th><th>Images proches (%)</th></tr></thead>
<tbody>{''.join(lines)}</tbody></table></div>
<script>document.getElementById('filter').addEventListener('input',function(){{
for(const row of document.querySelectorAll('tbody tr'))row.hidden=!row.textContent.toLowerCase().includes(this.value.toLowerCase());
}});</script></html>'''
    (folder / "index.html").write_text(content, encoding="utf-8")
    (folder / "index.html").chmod(0o600)


def analyze_item(task):
    """Process isolation keeps temporary UID changes separate between workers."""
    args, item, needs_hash, value = task
    path = item["path"]
    scanner = Scanner(args)
    try:
        if needs_hash and not value.get("sha256"):
            value["sha256"] = sha256(path, args.read_uid)
        if not args.exact_only:
            if not value.get("metadata"):
                value["metadata"] = scanner.probe(path)
            if "hashes" not in value:
                value["hashes"] = scanner.fingerprints(path, value["metadata"])
        if identity(Path(path), args.read_uid) != item["stamp"]:
            raise RuntimeError("File changed during scan; rerun when the download is complete")
        item.update(value.get("metadata", {}))
        item.update({key: value[key] for key in ("sha256", "hashes") if key in value})
        return item, value, None
    except (OSError, RuntimeError, ValueError, KeyError, StopIteration, subprocess.SubprocessError) as error:
        # A failure must not become a visual match or hide an otherwise valid exact hash.
        try:
            if value.get("sha256") and identity(Path(path), args.read_uid) == item["stamp"]:
                item["sha256"] = value["sha256"]
        except OSError:
            pass
        return item, None, (path, "fingerprint", str(error))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path, help="Parent directory for dated reports")
    parser.add_argument("--cache", type=Path, help="SQLite cache (default: OUTPUT/fingerprints.sqlite)")
    parser.add_argument("--container", help="Use an existing container with the same absolute media paths")
    parser.add_argument("--container-user", default="1000:1000")
    parser.add_argument("--ffmpeg-dir", default="/usr/lib/jellyfin-ffmpeg")
    parser.add_argument("--read-uid", type=int, help="Host UID for inventory and hashing (root required to switch)")
    parser.add_argument("--frames", type=int, default=12, choices=range(8, 25), metavar="8..24")
    parser.add_argument("--exact-only", action="store_true")
    parser.add_argument("--workers", type=int, default=1, choices=range(1, 5), metavar="1..4",
                        help="Concurrent video processes; default 1")
    args = parser.parse_args(argv)
    if args.read_uid is not None and os.geteuid() not in (0, args.read_uid):
        parser.error("--read-uid requires root or the same UID")
    os.umask(0o077)
    args.output.mkdir(parents=True, exist_ok=True)
    folder = args.output / ("duplicates-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ"))
    folder.mkdir(mode=0o700)
    cache_path = args.cache or args.output / "fingerprints.sqlite"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(cache_path)
    db.execute("CREATE TABLE IF NOT EXISTS fingerprints (path TEXT PRIMARY KEY, stamp TEXT, value TEXT)")
    cache_path.chmod(0o600)
    roots = [Path(os.path.abspath(p)) for p in args.roots]
    videos, aliases, errors = inventory(roots, args.read_uid)
    size_counts = {}
    for item in videos:
        size_counts[item["size"]] = size_counts.get(item["size"], 0) + 1
    cache_hits, tasks = 0, []
    started = time.monotonic()
    for item in videos:
        path = item["path"]
        stamp = json.dumps([VERSION, args.frames, item["stamp"]])
        cached = db.execute("SELECT value FROM fingerprints WHERE path=? AND stamp=?", (path, stamp)).fetchone()
        value = json.loads(cached[0]) if cached else {}
        cache_hits += bool(cached)
        tasks.append((args, item, size_counts[item["size"]] > 1, value))
    executor = None
    if args.workers == 1:
        results = map(analyze_item, tasks)
    else:
        executor = ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context("spawn"))
        futures = [executor.submit(analyze_item, task) for task in tasks]
        results = (future.result() for future in as_completed(futures))
    completed = []
    try:
        for index, (item, value, error) in enumerate(results, 1):
            completed.append(item)
            if error:
                errors.append(error)
            else:
                stamp = json.dumps([VERSION, args.frames, item["stamp"]])
                db.execute("INSERT OR REPLACE INTO fingerprints VALUES (?, ?, ?)", (item["path"], stamp, json.dumps(value)))
                db.commit()
            if index % 5 == 0 or index == len(videos):
                print(f"Analyzed {index}/{len(videos)} videos; {len(errors)} errors; {int(time.monotonic()-started)}s elapsed", flush=True)
    finally:
        if executor:
            executor.shutdown(wait=True, cancel_futures=True)
    videos = sorted(completed, key=lambda item: item["path"])
    pairs = []
    for a, b in itertools.combinations(videos, 2):
        match = None
        if a.get("sha256") and a["sha256"] == b.get("sha256"):
            match = ("exact", "", "")
        elif not args.exact_only:
            match = visual_match(a, b)
        if match:
            classification, percentage, distance = match
            pair = {"classification": classification, "similar_frames_percent": percentage,
                    "mean_hash_distance": distance, "decision": ""}
            for suffix, video in (("a", a), ("b", b)):
                for key in ("path", "size", "duration", "resolution", "codec"):
                    pair[f"{key}_{suffix}"] = video.get(key, "")
            pairs.append(pair)
    # Connected components give related candidate pairs the same review group.
    parents = {}
    def group(path):
        parents.setdefault(path, path)
        if parents[path] != path:
            parents[path] = group(parents[path])
        return parents[path]
    for pair in pairs:
        parents[group(pair['path_a'])] = group(pair['path_b'])
    groups = {}
    priority = {"exact": 0, "probable_visual": 1, "possible_visual": 2}
    pairs.sort(key=lambda p: (priority[p['classification']], p['path_a'], p['path_b']))
    for pair in pairs:
        representative = group(pair['path_a'])
        groups.setdefault(representative, len(groups) + 1)
        pair['group'] = groups[representative]
    report(folder, pairs, aliases, errors, len(videos), cache_hits, args.exact_only)
    db.close()
    print(f"Report: {folder / 'index.html'}", flush=True)
    print(f"Results: {len(pairs)} candidate pairs, {len(aliases)} hardlinks, {len(errors)} errors", flush=True)
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
