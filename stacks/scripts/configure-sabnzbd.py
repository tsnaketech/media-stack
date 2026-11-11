#!/lsiopy/bin/python3
"""Apply SABnzbd settings at container startup using its bundled ConfigObj."""
import os
from pathlib import Path
import secrets
import subprocess
import sys

from configobj import ConfigObj


def configure():
    if os.environ.get("SABNZBD_SETUP_ENABLED", "true").lower() != "true":
        return
    username = os.environ.get("SABNZBD_USERNAME", "admin")
    password = os.environ.get("SABNZBD_PASSWORD", "")
    if not username or len(password) < 12:
        raise ValueError("Set SABNZBD_USERNAME and SABNZBD_PASSWORD (at least 12 characters)")
    path = Path("/config/sabnzbd.ini")
    cfg = ConfigObj(str(path), encoding="utf-8")
    cfg.setdefault("misc", {})
    misc = cfg["misc"]
    misc.update({"host": "0.0.0.0", "port": "8080", "username": username,
                 "password": password, "inet_exposure": "0", "auto_browser": "0",
                 "host_whitelist": [x.strip() for x in os.environ.get("SABNZBD_ALLOWED_HOSTS", "sabnzbd,localhost").split(",") if x.strip()],
                 "download_dir": "/downloads/usenet/incomplete",
                 "complete_dir": "/downloads/usenet/complete",
                 "download_free": os.environ.get("SABNZBD_MIN_FREE_SPACE", "2G")})
    if not misc.get("api_key"):
        misc["api_key"] = secrets.token_hex(16)
    if not misc.get("nzb_key"):
        misc["nzb_key"] = secrets.token_hex(16)
    # Keep the queue idle until a provider and indexer have been configured.
    cfg.setdefault("categories", {})
    categories = cfg["categories"]
    for name in ("movies", "tv", "music", "books") + tuple(x.strip() for x in os.environ.get("SABNZBD_EXTRA_CATEGORIES", "").split(",") if x.strip()):
        categories.setdefault(name, {"name": name, "dir": name, "pp": "3", "priority": "0"})
    host = os.environ.get("SABNZBD_SERVER_HOST", "").strip()
    if host:
        port = int(os.environ.get("SABNZBD_SERVER_PORT", "563"))
        connections = int(os.environ.get("SABNZBD_SERVER_CONNECTIONS", "8"))
        if not 1 <= port <= 65535 or connections < 1:
            raise ValueError("Invalid Usenet server port or connection count")
        cfg.setdefault("servers", {})
        cfg["servers"]["env-provider"] = {
            "name": "env-provider", "host": host, "port": str(port),
            "username": os.environ.get("SABNZBD_SERVER_USERNAME", ""),
            "password": os.environ.get("SABNZBD_SERVER_PASSWORD", ""),
            "ssl": "1" if os.environ.get("SABNZBD_SERVER_SSL", "true").lower() == "true" else "0",
            "ssl_verify": "3", "connections": str(connections), "enable": "1"}
    # Shared Proxmox directories use ACLs; create and test them as the app user
    # instead of attempting chown from an unprivileged LXC root.
    subprocess.run([sys.executable, "-c", """
from pathlib import Path
import tempfile
for directory in ('/downloads/usenet/incomplete', '/downloads/usenet/complete'):
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=path):
        pass
"""], check=True, user=int(os.environ.get("PUID", "1000")),
                   group=int(os.environ.get("PGID", "1000")), extra_groups=[])
    cfg.write()
    os.chmod(path, 0o600)
    os.chown(path, int(os.environ.get("PUID", "1000")), int(os.environ.get("PGID", "1000")))
    print("SABnzbd: authentication, folders and categories configured; provider " + ("configured" if host else "not supplied"))


if __name__ == "__main__":
    configure()
