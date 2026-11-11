#!/usr/bin/env python3
"""Initialize JOAL's release configuration without adding or replacing torrents."""
import importlib
import os
from pathlib import Path
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.request

common = importlib.import_module("configure-profilarr")


def release_path(name):
    parts = Path(name).parts
    if "clients" in parts:
        result = Path(*parts[parts.index("clients"):])
    elif parts and parts[-1] == "config.json":
        result = Path("config.json")
    else:
        return None
    if result.is_absolute() or ".." in result.parts:
        raise common.SetupError("Invalid path in the JOAL release archive.")
    return result


def main():
    root = Path(__file__).resolve().parent.parent
    service = common.compose(root, "download")["services"]["joal"]
    volume = next(v for v in service["volumes"] if v.get("target") == "/data")
    target = Path(volume["source"])
    target.mkdir(parents=True, exist_ok=True)
    uid, gid = map(int, service.get("user", "1000:1000").split(":"))
    for directory in (target, target / "clients", target / "torrents"):
        if not directory.exists():
            directory.mkdir()
        os.chown(directory, uid, gid)
    if (target / "config.json").exists() and any((target / "clients").glob("*.client")):
        print("JOAL: existing configuration preserved.")
        return
    version = service["image"].rsplit(":", 1)[1]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise common.SetupError("Use an explicit JOAL release version when preparing its configuration.")
    url = f"https://github.com/anthonyraymond/joal/releases/download/{version}/joal.tar.gz"
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / "joal.tar.gz"
        with urllib.request.urlopen(url, timeout=30) as response, archive.open("wb") as out:
            shutil.copyfileobj(response, out)
        with tarfile.open(archive) as release:
            for member in release:
                if not member.isfile():
                    continue
                relative = release_path(member.name)
                if relative is None:
                    continue
                path = target / relative
                if not path.resolve().is_relative_to(target.resolve()):
                    raise common.SetupError("JOAL release destination escapes its data directory.")
                if path.exists():
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                with release.extractfile(member) as src, path.open("xb") as out:
                    shutil.copyfileobj(src, out)
                os.chown(path, uid, gid)
    if not (target / "config.json").exists() or not any((target / "clients").glob("*.client")):
        raise common.SetupError("JOAL release configuration is incomplete.")
    print("JOAL: release configuration initialized; no torrents imported.")


if __name__ == "__main__":
    try:
        main()
    except (common.SetupError, OSError, tarfile.TarError) as error:
        print(str(error) if isinstance(error, common.SetupError) else "JOAL release initialization failed.", file=sys.stderr)
        sys.exit(1)
