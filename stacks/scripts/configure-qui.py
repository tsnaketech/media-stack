#!/usr/bin/env python3
"""Configure qui, its qBittorrent instance, and Sonarr/Radarr integrations."""
import argparse
import importlib
from pathlib import Path
import sys
import time
import urllib.parse

common = importlib.import_module("configure-profilarr")
http = importlib.import_module("configure-download-clients")
urls = importlib.import_module("configure-jellyfin")


def find_instance(rows, host, name):
    matches = [row for row in rows if row["host"].rstrip("/") == host.rstrip("/")]
    if len(matches) > 1:
        raise common.SetupError("Multiple qui instances use this qBittorrent URL; resolve manually.")
    if matches:
        return matches[0]
    if any(row["name"] == name for row in rows):
        raise common.SetupError("The qui instance name is already used with a different destination.")
    return None


def configure(api, env, credentials, update=False):
    username, password = env.get("QUI_USERNAME", ""), env.get("QUI_PASSWORD", "")
    if not username or len(password) < 12:
        raise common.SetupError("Set QUI_USERNAME and a QUI_PASSWORD of at least 12 characters.")
    host, name = env["QUI_QBITTORRENT_URL"], env["QUI_INSTANCE_NAME"]
    parsed = urllib.parse.urlsplit(host)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise common.SetupError("QUI_QBITTORRENT_URL must be an HTTP(S) URL without embedded credentials.")
    status = api.call("api/auth/check-setup")
    if status.get("setupRequired"):
        api.call("api/auth/setup", "POST", {"username": username, "password": password})
    # Always verify the configured credentials; do not reset an existing user.
    api.call("api/auth/login", "POST", {"username": username, "password": password})
    me = api.call("api/auth/me")
    if me.get("username") != username:
        raise common.SetupError("qui did not authenticate the configured username.")
    existing = find_instance(api.call("api/instances"), host, name)
    payload = {"name": name, "host": host, "username": credentials["username"],
               "password": credentials["password"], "hasLocalFilesystemAccess": False}
    if not existing:
        instance = api.call("api/instances", "POST", payload)
    elif update:
        # Preserve filesystem, automation and instance-specific settings.
        payload.pop("hasLocalFilesystemAccess")
        instance = api.call(f"api/instances/{existing['id']}", "PUT", payload)
    else:
        instance = existing
    if api.call(f"api/instances/{instance['id']}/test", "POST", {}).get("connected") is not True:
        raise common.SetupError("qui cannot connect to qBittorrent; check its saved credentials.")
    print("qui: administrator verified and qBittorrent connection tested; no torrents changed.")



def configure_arr(api, root, env, update=False):
    for app, stack, port in (("sonarr", "tv", 8989), ("radarr", "movie", 7878)):
        prefix = "QUI_" + app.upper()
        if str(env.get(prefix + "_ENABLED", "true")).lower() != "true":
            continue
        host = env.get(prefix + "_URL", f"http://{app}:{port}").rstrip("/")
        parsed = urllib.parse.urlsplit(host)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise common.SetupError(f"{prefix}_URL must be an HTTP(S) URL without credentials or query.")
        rows = api.call("api/arr/instances")
        matches = [row for row in rows if row["type"] == app
                   and row["base_url"].rstrip("/") == host]
        if len(matches) > 1:
            raise common.SetupError(f"qui: multiple {app} integrations match; resolve manually.")
        existing = matches[0] if matches else None
        name = app.capitalize()
        if not existing and any(row["name"] == name for row in rows):
            raise common.SetupError(f"qui: {name} already points elsewhere; resolve manually.")
        if not existing or update:
            override = env.get(prefix + "_API_KEY", "")
            if host != f"http://{app}:{port}" and not override:
                raise common.SetupError(f"Set {prefix}_API_KEY for a custom destination.")
            payload = {"type": app, "name": name, "base_url": host,
                       "api_key": common.api_key(root, stack, app, override),
                       "enabled": True, "priority": 0, "timeout_seconds": 15}
            if api.call("api/arr/test", "POST", payload).get("success") is not True:
                raise common.SetupError(f"qui: {name} connection test failed; integration unchanged.")
            if existing:
                # Preserve priorities, timeouts, names and the enabled state.
                payload = {key: payload[key] for key in ("base_url", "api_key")}
                instance = api.call(f"api/arr/instances/{existing['id']}", "PUT", payload)
            else:
                instance = api.call("api/arr/instances", "POST", payload)
        else:
            instance = existing
        if api.call(f"api/arr/instances/{instance['id']}/test", "POST", {}).get("success") is not True:
            raise common.SetupError(f"qui: saved {name} integration failed its connection test.")
        print(f"qui: {name} integration {'configured' if not existing or update else 'preserved'}; connection test passed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-existing", action="store_true", help="Update managed connection credentials after rotation")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    service = common.compose(root, "download")["services"]["qui"]
    env = service["environment"]
    if str(env.get("QUI_SETUP_ENABLED", "false")).lower() != "true":
        print("qui: automatic configuration disabled.")
        return
    username, password = env.get("QUI_QBITTORRENT_USERNAME"), env.get("QUI_QBITTORRENT_PASSWORD")
    if username or password:
        if not username or not password:
            raise common.SetupError("Set both QUI_QBITTORRENT_USERNAME and QUI_QBITTORRENT_PASSWORD.")
        credentials = {"username": username, "password": password}
    else:
        if env["QUI_QBITTORRENT_URL"].rstrip("/") != "http://qbittorrent:8080":
            raise common.SetupError("Supply explicit qBittorrent credentials for a different destination.")
        credentials = http.credentials_from_file_or_env(root / "download/.qbittorrent-credentials.json")
    api = http.API(urls.local_url(service, 7476), {"X-Requested-With": "XMLHttpRequest"})
    for attempt in range(30):
        try:
            api.call("api/auth/check-setup")
            break
        except http.SetupError:
            if attempt == 29:
                raise
            time.sleep(2)
    configure(api, env, credentials, args.update_existing)
    configure_arr(api, root, env, args.update_existing)


if __name__ == "__main__":
    try:
        main()
    except (common.SetupError, http.SetupError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
