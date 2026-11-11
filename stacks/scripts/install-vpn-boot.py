#!/usr/bin/env python3
"""Install and enable the repository's post-Docker VPN reconciliation unit."""
import os
from pathlib import Path
import subprocess
import tempfile

MARKER = "# Managed by media-stack."
ROOT = Path(__file__).resolve().parents[2]


def unit_quote(path, command=False):
    value = str(path)
    if any(char in value for char in "\n\r\x00"):
        raise ValueError("Invalid systemd path")
    value = value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    if command:
        value = value.replace("$", "$$")
    return '"' + value + '"'


def render_unit(root):
    template = (root / "stacks/systemd/media-stack-vpn.service").read_text()
    return template.replace("@WORKING_ROOT@", str(root).replace("%", "%%")).replace("@PROJECT_ROOT@", unit_quote(root)).replace(
        "@RECONCILE_SCRIPT@", unit_quote(root / "stacks/scripts/reconcile-vpn.py", command=True))


def main():
    if os.geteuid() != 0:
        raise SystemExit("Run this installer as root (sudo python3 stacks/scripts/install-vpn-boot.py).")
    target = Path("/etc/systemd/system/media-stack-vpn.service")
    if target.exists() and not target.read_text().startswith(MARKER):
        raise SystemExit("Refusing to replace an unmanaged media-stack-vpn.service.")
    rendered = render_unit(ROOT)
    with tempfile.TemporaryDirectory(prefix="media-stack-systemd-") as temporary:
        candidate = Path(temporary) / target.name
        candidate.write_text(rendered)
        subprocess.run(["systemd-analyze", "verify", str(candidate)], check=True)
    temporary_target = target.with_suffix(".service.tmp")
    try:
        temporary_target.write_text(rendered)
        temporary_target.chmod(0o644)
        temporary_target.replace(target)
    finally:
        temporary_target.unlink(missing_ok=True)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "media-stack-vpn.service"], check=True)
    # Restart also applies updated scripts when reinstalling an existing unit.
    subprocess.run(["systemctl", "restart", "media-stack-vpn.service"], check=True)
    print("VPN boot reconciliation installed, enabled and verified.")


if __name__ == "__main__":
    main()
