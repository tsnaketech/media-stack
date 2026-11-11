#!/usr/bin/env python3
"""Prepare, check and initialize a checkout without replacing existing application data."""
import argparse
import base64
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import shutil
import subprocess
import sys
import time

common = importlib.import_module("configure-profilarr")
dotenv = importlib.import_module("configure-jellyfin")
STAGES = ("vpn", "indexer", "download", "shared", "music", "movie", "tv", "audiobook", "book")
CONFIGURATORS = ("configure-qbittorrent-vpn.py", "configure-download-clients.py", "configure-bazarr.py",
                 "configure-qui.py", "configure-flaresolverr.py", "configure-prowlarr-apps.py",
                 "configure-jellyfin.py", "configure-arr-connect.py", "configure-profilarr.py",
                 "configure-french-profiles.py", "configure-seerr.py")
SECRET_FIELDS = {
    "indexer": {"ARR_AUTH_PASSWORD": "prowlarr"},
    "download": {"QUI_PASSWORD": "qui", "QUI_SESSION_SECRET": "qui", "JOAL_UI_SECRET_TOKEN": "joal",
                 "SABNZBD_PASSWORD": "sabnzbd", "JDOWNLOADER_PASSWORD": "jdownloader"},
    "shared": {"JELLYFIN_ADMIN_PASSWORD": "jellyfin", "PROFILARR_PASSWORD": "profilarr", "BAZARR_PASSWORD": "bazarr"},
    **{s: {"ARR_AUTH_PASSWORD": a} for s, a in (("music", "lidarr"), ("movie", "radarr"), ("tv", "sonarr"))},
}
STAGES += tuple(common.extensions.settings().get("stacks", {}))
SECRET_FIELDS.update(common.extensions.settings().get("secret_fields", {}))



def run(command, **kwargs):
    try:
        return subprocess.run(command, check=True, **kwargs)
    except subprocess.CalledProcessError:
        raise common.SetupError("Command failed: " + str(command[0]) + " (inspect the preceding diagnostic)") from None


def raw_values(path):
    """Read single-line values for generated settings; Compose resolves runtime values."""
    values = {}
    for line in path.read_text().splitlines():
        match = re.match(r"^([A-Z][A-Z0-9_]*)=(.*)$", line)
        if match:
            value = match[2].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[match[1]] = value
    return values


def has_data(path):
    return path.exists() and any(p.is_file() for p in path.rglob("*"))


def private_json(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as out:
        json.dump(data, out)


def seed_qbittorrent(root, service):
    config_mount = next(v for v in service["volumes"] if v.get("target") == "/config")
    config = Path(config_mount["source"]) / "qBittorrent/qBittorrent.conf"
    credentials = root / "download/.qbittorrent-credentials.json"
    if config.exists():
        if not credentials.exists():
            raise common.SetupError("Existing qBittorrent config has no credential file; run configure-download-clients.py --init-credentials. Nothing reset.")
        return
    if credentials.exists():
        helper = importlib.import_module("configure-download-clients")
        account = helper.credentials_from_file_or_env(credentials)
    else:
        env = raw_values(root / "download/.env")
        env.update({k: v for k, v in service.get("environment", {}).items() if k.startswith("QBITTORRENT_INIT_")})
        account = {"username": env.get("QBITTORRENT_INIT_USERNAME") or "admin",
                   "password": env.get("QBITTORRENT_INIT_PASSWORD") or secrets.token_hex(24)}
        if len(account["password"]) < 12 or not re.fullmatch(r"[A-Za-z0-9_.@-]{1,64}", account["username"]):
            raise common.SetupError("Invalid qBittorrent initial account (password needs 12 characters).")
        dotenv.update_env(root / "download/.env", {"QBITTORRENT_INIT_USERNAME": account["username"],
                                                    "QBITTORRENT_INIT_PASSWORD": account["password"]})
        private_json(credentials, account)
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha512", account["password"].encode(), salt, 100000)
    encoded = base64.b64encode(salt).decode() + ":" + base64.b64encode(derived).decode()
    config.parent.mkdir(parents=True, exist_ok=True)
    # Legacy layout is migrated by qBittorrent 5.1/5.2 on first start.
    text = ('[LegalNotice]\nAccepted=true\n\n[BitTorrent]\nSession\\DefaultSavePath=/downloads/\n'
            'Session\\DisableAutoTMMByDefault=false\nSession\\UseCategoryPathsInManualMode=true\n'
            'Session\\Interface=tun0\n\n[Preferences]\nWebUI\\LocalHostAuth=true\n'
            f'WebUI\\Username={account["username"]}\nWebUI\\Password_PBKDF2="@ByteArray({encoded})"\n')
    fd = os.open(config, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as out:
        out.write(text)
    uid = int(service.get("environment", {}).get("PUID", 1000))
    gid = int(service.get("environment", {}).get("PGID", 1000))
    if os.geteuid() == 0:
        os.chown(config.parent, uid, gid)
        os.chown(config, uid, gid)
    marker = config.parent / ".initial-account-pending"
    marker.touch(mode=0o600, exist_ok=False)
    print("qBittorrent: initial account seeded offline; existing accounts are never reset.")



def complete_qbittorrent(root):
    """Verify only a newly seeded account; never change an existing account."""
    service = common.compose(root, "download")["services"]["qbittorrent"]
    base = Path(next(v["source"] for v in service["volumes"] if v.get("target") == "/config"))
    marker = base / "qBittorrent/.initial-account-pending"
    if not marker.exists():
        return
    helper = importlib.import_module("configure-download-clients")
    account = helper.credentials_from_file_or_env(root / "download/.qbittorrent-credentials.json")
    vpn = common.compose(root, "vpn")["services"]["gluetun"]
    endpoint = dotenv.local_url(vpn, 8080)
    api = helper.API(endpoint + "/api/v2", helper.qbit_headers(endpoint))
    for attempt in range(30):
        try:
            api.call("auth/login", "POST", account, form=True)
            preferences = api.call("app/preferences")
            break
        except helper.SetupError:
            if attempt == 29:
                raise
            time.sleep(2)
    if preferences.get("web_ui_username") != account["username"] or preferences.get("bypass_local_auth") is not False:
        raise common.SetupError("qBittorrent initial account or localhost authentication was not verified")
    marker.unlink()
    print("qBittorrent: initial account authenticated; localhost authentication required.")


def storage_values(stack, library, downloads):
    values = {}
    if downloads and stack in ("download", "music", "movie", "tv", "book"):
        values["SHARED_DOWNLOADS_DIR"] = str(downloads)
    if library:
        sub = {"music": "music", "movie": "movies", "tv": "tv", "book": "books", "audiobook": "audiobooks"}
        if stack in sub:
            values["MUSIC_DIR" if stack == "music" else "LIBRARY_DIR"] = str(library / sub[stack])
        if stack == "shared":
            for name in ("movies", "tv", "music"):
                values[f"JELLYFIN_{name.upper()}_DIR"] = str(library / name)
            for name in ("movies", "tv"):
                values[f"BAZARR_{name.upper()}_DIR"] = str(library / name)
    extra = common.extensions.settings().get("storage", {}).get(stack, {})
    if library and extra.get("library_subdir"):
        values[extra["variable"]] = str(library / extra["library_subdir"])
    if downloads and extra.get("downloads"):
        values["SHARED_DOWNLOADS_DIR"] = str(downloads)
    if downloads and stack == "download":
        values["METUBE_VIDEO_DIR"] = str(downloads / "youtube/videos")
    return values


def prepare(root, library=None, downloads=None):
    if not shutil.which("docker"):
        raise common.SetupError("Docker CLI and Compose 2.30+ are required to prepare the resolved bind paths.")
    for stack in STAGES:
        path = common.extensions.stack_directory(root, stack) / ".env"
        if not path.exists():
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as out:
                out.write((common.extensions.stack_directory(root, stack) / ".env.example").read_text())
        updates = storage_values(stack, library, downloads)
        values = raw_values(path)
        for key, app in SECRET_FIELDS.get(stack, {}).items():
            if not values.get(key) and not has_data(common.extensions.stack_directory(root, stack) / "data" / app):
                updates[key] = secrets.token_hex(24)
        if stack == "download" and values.get("JOAL_UI_PATH", "changeThisPathBeforeUse") == "changeThisPathBeforeUse" and not has_data(root / stack / "data/joal"):
            updates["JOAL_UI_PATH"] = secrets.token_hex(8)
        if updates:
            dotenv.update_env(path, updates)
        path.chmod(0o600)
    configs = {stack: common.compose(root, stack) for stack in STAGES}
    for config in configs.values():
        for svc in config["services"].values():
            user = svc.get("user", "").split(":")
            uid = int(user[0]) if user and user[0].isdigit() else int(svc.get("environment", {}).get("PUID", 1000))
            gid = int(user[1]) if len(user) > 1 and user[1].isdigit() else int(svc.get("environment", {}).get("PGID", 1000))
            for volume in svc.get("volumes", []):
                if volume.get("type") != "bind":
                    continue
                path = Path(volume["source"])
                # Only create repository data directories. Never chmod/chown media trees.
                bases = [root] + ([common.extensions.directory(root)] if common.extensions.directory(root) else [])
                if any(path.is_relative_to(base) and "data" in path.relative_to(base).parts for base in bases) and not path.exists():
                    path.mkdir(parents=True, exist_ok=True)
                    if os.geteuid() == 0:
                        os.chown(path, uid, gid)
    # Download subdirectories are created as the application user, preserving host ACLs.
    qbit = configs["download"]["services"]["qbittorrent"]
    target = next(Path(v["source"]) for v in qbit["volumes"] if v["target"] == "/downloads")
    if target.is_dir():
        uid, gid = (int(qbit["environment"][key]) for key in ("PUID", "PGID"))
        code = "from pathlib import Path; import sys; root=Path(sys.argv[1]); [ (root/p).mkdir(parents=True, exist_ok=True) for p in ('movies','tv','music','books/ingest','other','prowlarr','usenet/incomplete','usenet/complete','youtube/audio','youtube/videos','youtube/.tmp','direct')]"
        options = {"user": uid, "group": gid, "extra_groups": []} if os.geteuid() == 0 else {}
        code += "; [(root/p).mkdir(parents=True, exist_ok=True) for p in " + repr(common.extensions.settings(root).get("download_directories", [])) + "]"
        run([sys.executable, "-c", code, str(target)], **options)
    seed_qbittorrent(root, qbit)
    print("Prepared environment files and local data directories; no containers started, no secrets displayed.")
    return configs


def writable_as(path, uid, gid, write):
    code = "import os,sys,tempfile; p=sys.argv[1]; assert os.access(p, os.R_OK|os.X_OK); f=tempfile.TemporaryFile(dir=p) if sys.argv[2]=='write' else None"
    options = {"user": uid, "group": gid, "extra_groups": []} if os.geteuid() == 0 else {}
    result = subprocess.run([sys.executable, "-c", code, str(path), "write" if write else "read"],
                            capture_output=True, **options)
    return result.returncode == 0


def preflight(root, configs, check_vpn=True):
    problems = []
    info = subprocess.run(["docker", "info"], capture_output=True)
    if info.returncode:
        raise common.SetupError("Docker Engine is unavailable; check the service, Docker context and socket permissions.")
    version = subprocess.check_output(["docker", "compose", "version", "--short"], text=True).strip().lstrip("v")
    match = re.match(r"(\d+)\.(\d+)", version)
    if not match or tuple(map(int, match.groups())) < (2, 30):
        problems.append("Docker Compose 2.30+ is required")
    checked = set()
    download_sources = set()
    reserved_ports = set()
    for stack, config in configs.items():
        for name, svc in config["services"].items():
            env = svc.get("environment", {})
            user = svc.get("user", "").split(":")
            uid = int(user[0]) if user and user[0].isdigit() else int(env.get("PUID", 1000))
            gid = int(user[1]) if len(user) > 1 and user[1].isdigit() else int(env.get("PGID", 1000))
            for v in svc.get("volumes", []):
                if v.get("type") != "bind":
                    continue
                p = Path(v["source"])
                if not p.exists():
                    problems.append(f"{stack}/{name}: missing bind source {p}")
                    continue
                if p.is_dir() and not p.is_relative_to(root):
                    key = (str(p), uid, gid, v.get("read_only", False))
                    if key not in checked and not writable_as(p, uid, gid, not v.get("read_only", False)):
                        problems.append(f"{stack}/{name}: storage inaccessible to {uid}:{gid}: {p}")
                    checked.add(key)
                    for base in (Path("/media"), Path("/downloads")):
                        if (p == base or p.is_relative_to(base)) and not os.path.ismount(base):
                            problems.append(f"Expected storage mount is absent: {base}; configure a custom storage path for local directories")
            if name in (*common.extensions.settings(root).get("applications", {}), "qbittorrent", "sabnzbd", "lidarr", "radarr", "sonarr", "shelfmark"):
                download_sources.update(v["source"] for v in svc.get("volumes", []) if v.get("target") == "/downloads")
            # Fixed names must not belong to a different checkout.
            result = subprocess.run(["docker", "inspect", svc.get("container_name", name)], capture_output=True, text=True)
            row = None
            if result.returncode == 0:
                row = json.loads(result.stdout)[0]
                files = row["Config"].get("Labels", {}).get("com.docker.compose.project.config_files", "")
                expected = {str(common.extensions.stack_directory(root, stack) / "docker-compose.yml")}
                export = common.extensions.management_directory(root, stack)
                if export is not None:
                    expected.add(str(export / "docker-compose.yml"))
                if files and not expected.intersection(files.split(",")):
                    problems.append(f"Container name already belongs to another checkout: {name}")
            for mapping in svc.get("ports", []):
                protocol = mapping.get("protocol", "tcp")
                port = int(mapping["published"])
                bind = mapping.get("host_ip") or "0.0.0.0"
                slot = (bind, port, protocol)
                if slot in reserved_ports:
                    problems.append(f"Duplicate published port: {bind}:{port}/{protocol}")
                reserved_ports.add(slot)
                owned = False
                if row and row["State"].get("Running"):
                    actual = row["NetworkSettings"].get("Ports", {}).get(f"{mapping['target']}/{protocol}") or []
                    owned = any(int(m["HostPort"]) == port and m["HostIp"] == bind for m in actual)
                if owned or port == 0:
                    continue
                family = socket.AF_INET6 if ":" in bind else socket.AF_INET
                kind = socket.SOCK_DGRAM if protocol == "udp" else socket.SOCK_STREAM
                try:
                    with socket.socket(family, kind) as listener:
                        listener.bind((bind, port))
                except OSError:
                    problems.append(f"Published port is unavailable: {bind}:{port}/{protocol}")
    if len(download_sources) > 1:
        problems.append("SHARED_DOWNLOADS_DIR differs between clients and arr applications")
    helper = importlib.import_module("configure-download-clients")
    try:
        helper.credentials_from_file_or_env(root / "download/.qbittorrent-credentials.json")
    except helper.SetupError:
        problems.append("qBittorrent credentials are absent or invalid; prepare a fresh account or supply the existing credentials")
    if check_vpn:
        env = configs["vpn"]["services"]["gluetun"]["environment"]
        if not Path("/dev/net/tun").is_char_device():
            problems.append("Missing character device /dev/net/tun; prepare TUN on the Docker host/LXC")
        wgfile = root / "vpn/data/wireguard/wg0.conf"
        if env.get("VPN_TYPE") == "wireguard" and not env.get("WIREGUARD_PRIVATE_KEY") and not wgfile.exists():
            problems.append("Set WIREGUARD_PRIVATE_KEY in vpn/.env or provide data/wireguard/wg0.conf")
        if env.get("VPN_TYPE") == "openvpn" and env.get("VPN_SERVICE_PROVIDER") != "custom" and not env.get("OPENVPN_USER"):
            problems.append("Set the provider OpenVPN credentials in vpn/.env")
    if problems:
        raise common.SetupError("Preflight failed:\n- " + "\n- ".join(dict.fromkeys(problems)))
    print("Preflight passed: Compose, bind paths, application storage permissions, container ownership, published ports and VPN prerequisites.")


def start(root, configs, infra=False):
    run(["bash", str(root / "scripts/vpn-up.sh")], cwd=root)
    run([sys.executable, str(root / "scripts/prepare-joal.py")], cwd=root)
    for stack in STAGES:
        run(common.extensions.compose_command(root, stack, ["up", "-d"]), cwd=root)
    # Wait for every arr API before provisioning cross-service integrations.
    helper = importlib.import_module("configure-download-clients")
    for name in helper.APPS:
        for attempt in range(60):
            try:
                helper.app_api(root, name, "127.0.0.1").call("system/status")
                break
            except helper.SetupError:
                if attempt == 59:
                    raise common.SetupError(f"{name}: API did not become ready")
                time.sleep(2)
    failed = []
    for script in CONFIGURATORS:
        result = subprocess.run([sys.executable, str(root / "scripts" / script)], cwd=root)
        if result.returncode:
            failed.append(script)
    if infra:
        parent = Path(os.environ.get("INFRA_ROOT", str(root.parent)))
        for stack in ("traefik", "arcane", "dozzle", "homepage"):
            common.extensions.prepare_runtime_mounts(root, parent / stack)
            run(common.extensions.compose_command(root, parent / stack, ["up", "-d"]))
    print("Manual/external steps: indexers, Usenet provider, subtitle providers, Calibre database, first Audiobookshelf/Navidrome users, DNS/TLS. See docs/initialization.md.")
    if failed:
        raise common.SetupError("Services started, but configuration is incomplete: " + ", ".join(failed) + ". Successful steps were preserved; correct the diagnostics and rerun.")
    run([sys.executable, str(root / "scripts/check-services.py")], cwd=root)
    print("Initialization completed; external accounts and catalog selections still require configuration.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "check", "up"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--library-root", type=Path, help="Explicit host media base; update all relevant .env paths")
    parser.add_argument("--downloads-root", type=Path, help="Explicit host download base; update all relevant .env paths")
    parser.add_argument("--with-infra", action="store_true")
    args = parser.parse_args()
    for p in (args.library_root, args.downloads_root):
        if p is not None and (not p.is_absolute() or p == Path("/")):
            parser.error("Storage roots must be absolute directories other than /")
    root = args.root.resolve()
    if args.action == "check":
        configs = {stack: common.compose(root, stack) for stack in STAGES}
    else:
        configs = prepare(root, args.library_root, args.downloads_root)
    if args.action in ("check", "up"):
        preflight(root, configs)
    if args.action == "up":
        start(root, configs, args.with_infra)


if __name__ == "__main__":
    try:
        main()
    except (common.SetupError, dotenv.http.SetupError, OSError, ValueError) as error:
        message = str(error) if isinstance(error, (common.SetupError, dotenv.http.SetupError)) else "Initialization could not access a required file or setting; check paths, ownership and templates."
        print(message, file=sys.stderr)
        sys.exit(1)
