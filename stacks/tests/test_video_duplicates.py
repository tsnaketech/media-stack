import csv
import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/find-video-duplicates.py"
spec = importlib.util.spec_from_file_location("video_duplicates", SCRIPT)
duplicates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(duplicates)


class DuplicateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.media = self.root / "media"
        self.media.mkdir()
        self.output = self.root / "reports"

    def run_scan(self, *extra):
        with redirect_stdout(io.StringIO()):
            result = duplicates.main([str(self.media), "--output", str(self.output), *extra])
        report = sorted(self.output.glob("duplicates-*"))[-1]
        with (report / "duplicates.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter=";"))
        return result, report, rows

    def test_exact_matches_ignore_names_and_separate_hardlinks(self):
        (self.media / "one.mp4").write_bytes(b"identical")
        (self.media / "renamed.mkv").write_bytes(b"identical")
        (self.media / "different.mp4").write_bytes(b"different")
        os.link(self.media / "one.mp4", self.media / "hardlink.mp4")
        result, folder, rows = self.run_scan("--exact-only")
        self.assertEqual(result, 0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["classification"], "exact")
        with (folder / "hardlinks.csv").open(encoding="utf-8-sig") as stream:
            self.assertEqual(len(list(csv.reader(stream, delimiter=";"))), 2)

    def test_visual_similarity_requires_multiple_nonblank_frames_and_close_duration(self):
        first = {"duration": 600, "hashes": [0xAAAAAAAAAAAAAAAA] * 12}
        similar = {"duration": 601, "hashes": [0xAAAAAAAAAAAAAAAB] * 12}
        self.assertEqual(duplicates.visual_match(first, similar)[0], "probable_visual")
        self.assertIsNone(duplicates.visual_match(first, {**similar, "duration": 900}))
        self.assertIsNone(duplicates.visual_match(first, {**similar, "hashes": [None] * 12}))
        self.assertIsNone(duplicates.visual_match(first, {**similar, "hashes": [0x5555555555555555] * 12}))
        self.assertIsNone(duplicates.visual_match(first, {**similar, "hashes": [None] * 9 + similar["hashes"][:3]}))

    def test_dark_uniform_frames_are_rejected(self):
        self.assertIsNone(duplicates.frame_hash(bytes([0] * 72)))
        self.assertIsNone(duplicates.frame_hash(bytes([128] * 72)))
        self.assertIsNotNone(duplicates.frame_hash(bytes([20, 180, 20, 180, 20, 180, 20, 180, 20] * 8)))

    def test_cache_reused_then_invalidated_after_file_change(self):
        video = self.media / "video.mp4"
        video.write_bytes(b"first")
        with patch.object(duplicates.Scanner, "probe", return_value={"duration": 100}), patch.object(
                duplicates.Scanner, "fingerprints", return_value=[0xAAAAAAAAAAAAAAAA] * 12) as fingerprint:
            self.assertEqual(self.run_scan()[0], 0)
            self.assertEqual(fingerprint.call_count, 1)
            self.assertEqual(self.run_scan()[0], 0)
            self.assertEqual(fingerprint.call_count, 1)
            video.write_bytes(b"changed and longer")
            self.assertEqual(self.run_scan()[0], 0)
            self.assertEqual(fingerprint.call_count, 2)

    def test_reports_escape_html_and_csv_formulas(self):
        malicious = '<script>alert("test")</script>'
        pair = dict.fromkeys(duplicates.FIELDS, "")
        pair.update(group=1, classification="exact", path_a=malicious, path_b="=1+1", size_a=1, size_b=1)
        duplicates.report(self.root, [pair], [], [], 2, 0, True)
        content = (self.root / "index.html").read_text()
        self.assertNotIn(malicious, content)
        self.assertIn("&lt;script&gt;", content)
        self.assertIn("'=1+1", (self.root / "duplicates.csv").read_text(encoding="utf-8-sig"))

    def test_failure_produces_incomplete_report_and_no_visual_candidate(self):
        (self.media / "broken.mp4").write_bytes(b"video")
        with patch.object(duplicates.Scanner, "probe", side_effect=RuntimeError("Cannot decode")):
            result, folder, rows = self.run_scan()
        self.assertEqual(result, 2)
        self.assertFalse(rows)
        self.assertIn("Analyse incomplète", (folder / "index.html").read_text())
        self.assertIn("Cannot decode", (folder / "errors.csv").read_text())

    def test_missing_directory_produces_inventory_error(self):
        videos, aliases, errors = duplicates.inventory([self.root / "missing"], None)
        self.assertFalse(videos)
        self.assertFalse(aliases)
        self.assertEqual(len(errors), 1)

    def test_media_files_are_unchanged(self):
        paths = [self.media / "one.mp4", self.media / "two.mp4"]
        for path in paths:
            path.write_bytes(b"same content")
        before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths]
        self.run_scan("--exact-only")
        self.assertEqual(before, [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths])

    def test_parallel_workers_report_exact_matches(self):
        for name in ("one.mp4", "two.mkv"):
            (self.media / name).write_bytes(b"same content")
        result = subprocess.run([sys.executable, str(SCRIPT), str(self.media), "--output", str(self.output),
                                 "--exact-only", "--workers", "2"], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = next(self.output.glob("duplicates-*"))
        with (folder / "duplicates.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter=";"))
        self.assertEqual([r["classification"] for r in rows], ["exact"])

    def test_host_decoder_uses_selected_reader_uid(self):
        scanner = duplicates.Scanner(SimpleNamespace(container=None, read_uid=os.geteuid()))
        with patch.object(duplicates.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=b"ok")) as run:
            self.assertEqual(scanner.run("ffprobe", ["-version"], 30), b"ok")
        self.assertEqual(run.call_args.kwargs["user"], os.geteuid())
