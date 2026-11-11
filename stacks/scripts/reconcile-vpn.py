#!/usr/bin/env python3
"""Check VPN storage prerequisites before running the shared startup helper."""
import importlib
import os
from pathlib import Path
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CLIENTS = ("qbittorrent", "metube", "jdownloader")


def validate_storage(models):
    for services, names in models:
        for name in names:
            for volume in services[name].get("volumes", []):
                if volume.get("type") != "bind":
                    continue
                source = Path(volume["source"])
                for base in (Path("/media"), Path("/downloads")):
                    if source == base or base in source.parents:
                        if not os.path.ismount(base):
                            raise RuntimeError(f"Required storage mount unavailable: {base}")
                if not source.exists():
                    raise RuntimeError(f"Required bind source unavailable: {source}")


def main():
    common = importlib.import_module("configure-profilarr")
    try:
        if not stat.S_ISCHR(Path("/dev/net/tun").stat().st_mode):
            raise RuntimeError("/dev/net/tun must be a character device")
        vpn = common.compose(ROOT, "vpn")["services"]
        download = common.compose(ROOT, "download")["services"]
        validate_storage(((vpn, ("gluetun",)), (download, CLIENTS)))
        subprocess.run(["bash", str(ROOT / "scripts/vpn-up.sh")], check=True)
    except (common.SetupError, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"VPN startup reconciliation failed: {exc}") from None


if __name__ == "__main__":
    main()
