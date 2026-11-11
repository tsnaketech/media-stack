#!/usr/bin/env python3
"""Apply Seerr settings from shared/.env while preserving accounts and setup state."""
import copy
import datetime
import fcntl
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.parse

common = importlib.import_module("configure-profilarr")
SetupError = common.SetupError

# Only whitelisted fields leave the container. Credentials enter through stdin,
# never command arguments, logs, or returned API response bodies.
PROBE_JS = r"""
(async () => {
  let raw = ''; for await (const chunk of process.stdin) raw += chunk;
  const p = JSON.parse(raw);
  async function get(path) {
    const r = await fetch(p.url.replace(/\/$/, '') + path, {
      headers: p.key ? (p.kind === 'media' ? { Authorization: 'MediaBrowser Token=' + JSON.stringify(p.key) + ', Client="Homelab setup", Device="Server", DeviceId="homelab-seerr", Version="1.0"' } : { 'X-Api-Key': p.key }) : {},
      signal: AbortSignal.timeout(15000)
    });
    if (!r.ok) throw new Error('remote status');
    return r.json();
  }
  let result;
  if (p.kind === 'arr') {
    const profiles = await get('/api/v3/qualityprofile');
    const roots = await get('/api/v3/rootfolder');
    result = {profiles: profiles.map(x => ({id:x.id, name:x.name})),
              roots: roots.map(x => ({id:x.id, path:x.path}))};
  } else if (p.kind === 'media') {
    const info = await get('/System/Info');
    const folders = await get('/Library/VirtualFolders');
    result = {name:info.ServerName, id:info.Id, libraries:folders
      .filter(x => ['movies', 'tvshows'].includes(x.CollectionType))
      .map(x => ({id:String(x.ItemId), name:x.Name, type:x.CollectionType === 'movies' ? 'movie' : 'show'}))};
  } else {
    const s = await get('/api/v1/settings/public');
    result = Object.fromEntries(['initialized','applicationTitle','applicationUrl','locale',
      'discoverRegion','streamingRegion','localLogin','mediaServerLogin'].map(k => [k,s[k]]));
  }
  process.stdout.write(JSON.stringify(result));
})().catch(() => { process.stderr.write('Seerr configuration probe failed.\n'); process.exit(1); });
"""


def boolean(env, name, default=False):
    value = str(env.get(name, str(default))).lower()
    if value not in ("true", "false"):
        raise SetupError(f"{name} must be true or false.")
    return value == "true"


def split_url(value, name):
    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        raise SetupError(f"{name}: invalid URL or port.") from None
    if (parsed.scheme not in ("http", "https") or not parsed.hostname or
            parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise SetupError(f"{name}: use an HTTP(S) URL without embedded credentials, query or fragment.")
    return {"hostname": parsed.hostname, "port": port, "useSsl": parsed.scheme == "https",
            "baseUrl": parsed.path.rstrip("/")}


def probe(root, payload):
    try:
        result = subprocess.run(
            common.extensions.compose_command(root, "shared", ["exec", "-T", "seerr", "node", "-e", PROBE_JS]),
            input=json.dumps(payload), text=True, capture_output=True, timeout=50, check=True,
        )
        return json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        raise SetupError("Connection test from Seerr failed; check server reachability and credentials.") from None


def build_server(app, env, metadata, key):
    prefix = "SEERR_" + app.upper() + "_"
    url = split_url(env[prefix + "URL"], prefix + "URL")
    matches = [p for p in metadata["profiles"] if p["name"] == env[prefix + "PROFILE"]]
    roots = [r for r in metadata["roots"] if r["path"] == env[prefix + "ROOT_FOLDER"]]
    if len(matches) != 1 or len(roots) != 1:
        raise SetupError(f"{app}: configured quality profile or root folder was not found uniquely.")
    result = dict(url, name=env[prefix + "NAME"], apiKey=key,
                  activeProfileId=matches[0]["id"], activeProfileName=matches[0]["name"],
                  activeDirectory=roots[0]["path"], is4k=False,
                  isDefault=boolean(env, prefix + "DEFAULT", True),
                  syncEnabled=boolean(env, prefix + "SYNC_ENABLED", True),
                  preventSearch=boolean(env, prefix + "PREVENT_SEARCH", False))
    if not result["name"].strip():
        raise SetupError(f"{prefix}NAME must not be empty.")
    if app == "radarr":
        value = env.get(prefix + "MINIMUM_AVAILABILITY", "released")
        if value not in ("announced", "inCinemas", "released"):
            raise SetupError("SEERR_RADARR_MINIMUM_AVAILABILITY must be announced, inCinemas or released.")
        result["minimumAvailability"] = value
    else:
        series_type = env.get(prefix + "SERIES_TYPE", "standard")
        if series_type not in ("standard", "daily", "anime"):
            raise SetupError("SEERR_SONARR_SERIES_TYPE must be standard, daily or anime.")
        result.update(seriesType=series_type, animeSeriesType="anime",
                      enableSeasonFolders=boolean(env, prefix + "SEASON_FOLDERS", True),
                      monitorNewItems="all", activeAnimeProfileId=matches[0]["id"],
                      activeAnimeProfileName=matches[0]["name"], activeAnimeDirectory=roots[0]["path"])
    return result


def merge_server(rows, desired):
    rows = copy.deepcopy(rows)
    def target(row):
        return (row.get("hostname"), row.get("port"), bool(row.get("useSsl")), row.get("baseUrl", "").rstrip("/"))
    matches = [r for r in rows if target(r) == target(desired) and not r.get("is4k")]
    if not matches:
        matches = [r for r in rows if r.get("name") == desired["name"] and not r.get("is4k")]
    if len(matches) > 1:
        raise SetupError("Multiple matching Seerr servers; resolve duplicates before applying settings.")
    if matches:
        row = matches[0]
    else:
        row = {"id": max((r["id"] for r in rows), default=-1) + 1,
               "tags": [], "animeTags": [], "tagRequests": False, "overrideRule": []}
        rows.append(row)
    row.update(desired)
    if desired["isDefault"]:
        for other in rows:
            if other is not row and not other.get("is4k"):
                other["isDefault"] = False
    return rows


def merge_settings(current, env, servers, media=None):
    result = copy.deepcopy(current)
    main = result.setdefault("main", {})
    for var, field in (("APPLICATION_TITLE", "applicationTitle"), ("APPLICATION_URL", "applicationUrl"),
                       ("LOCALE", "locale"), ("DISCOVER_REGION", "discoverRegion"), ("STREAMING_REGION", "streamingRegion")):
        main[field] = env["SEERR_" + var]
    main["localLogin"] = boolean(env, "SEERR_LOCAL_LOGIN", True)
    main["mediaServerLogin"] = boolean(env, "SEERR_MEDIA_SERVER_LOGIN", True)
    if not main["localLogin"] and not main["mediaServerLogin"]:
        raise SetupError("At least one Seerr login method must remain enabled.")
    if main["applicationUrl"]:
        split_url(main["applicationUrl"], "SEERR_APPLICATION_URL")
    for app, desired in servers.items():
        result[app] = merge_server(result.get(app, []), desired)
    if media:
        config, server = media
        typ = env["SEERR_MEDIA_SERVER_TYPE"].lower()
        if typ not in ("jellyfin", "emby"):
            raise SetupError("Media-server provisioning supports jellyfin or emby; configure Plex through its wizard.")
        main["mediaServerType"] = 2 if typ == "jellyfin" else 3
        old = result.get("jellyfin", {})
        same = (old.get("ip"), old.get("port"), bool(old.get("useSsl")), old.get("urlBase", "").rstrip("/")) == (
            config["hostname"], config["port"], config["useSsl"], config["baseUrl"])
        previous = {str(lib["id"]): lib for lib in old.get("libraries", [])} if same else {}
        selected = {x.strip() for x in env.get("SEERR_MEDIA_SERVER_LIBRARY_IDS", "").split(",") if x.strip()}
        available = {lib["id"] for lib in server["libraries"]}
        if not selected.issubset(available):
            raise SetupError("SEERR_MEDIA_SERVER_LIBRARY_IDS contains an unknown movie/TV library ID.")
        libraries = [dict(previous.get(lib["id"], {}), **lib,
                          enabled=lib["id"] in selected if selected else bool(previous.get(lib["id"], {}).get("enabled")))
                     for lib in server["libraries"]]
        result["jellyfin"] = dict(old, name=server["name"], ip=config["hostname"], port=config["port"],
                                  useSsl=config["useSsl"], urlBase=config["baseUrl"], apiKey=env["SEERR_MEDIA_SERVER_API_KEY"],
                                  serverId=server["id"], libraries=libraries,
                                  externalHostname=env.get("SEERR_MEDIA_SERVER_EXTERNAL_URL", ""))
    return result


def read_settings(path):
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        raise SetupError("Seerr settings.json is unavailable or invalid; start Seerr once first.") from None
    if not isinstance(data, dict) or not isinstance(data.get("main"), dict) or "public" not in data:
        raise SetupError("Unrecognized Seerr settings schema; nothing modified.")
    return data


def write_settings(path, data, owner):
    fd, temporary = tempfile.mkstemp(prefix=".seerr-env-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        os.fchown(fd, owner.st_uid, owner.st_gid)
        with os.fdopen(fd, "w") as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run_compose(root, *args):
    try:
        subprocess.run(common.extensions.compose_command(root, "shared", args),
                       check=True, capture_output=True, timeout=90)
    except (OSError, subprocess.SubprocessError):
        raise SetupError("Seerr Compose operation failed; inspect its container status.") from None


def complete_setup(root, service, env):
    if not boolean(env, "SEERR_BOOTSTRAP_WITH_JELLYFIN", False):
        return
    helpers = importlib.import_module("configure-jellyfin")
    http = importlib.import_module("configure-download-clients")
    volume = next(v for v in service["volumes"] if v.get("target") == "/app/config")
    settings = read_settings(Path(volume["source"]) / "settings.json")
    if settings["public"].get("initialized"):
        return
    if settings["main"].get("mediaServerType") != 2 or not any(
            library.get("enabled") for library in settings.get("jellyfin", {}).get("libraries", [])):
        raise SetupError("Configure Jellyfin libraries before completing Seerr setup.")
    api = http.API(helpers.local_url(service, 5055), {"X-Api-Key": settings["main"]["apiKey"]})
    try:
        user = api.call("api/v1/auth/me")
        if user.get("id") != 1:
            raise SetupError("Seerr first-administrator authentication is required.")
        api.call("api/v1/settings/initialize", "POST", {})
        if not api.call("api/v1/settings/public").get("initialized"):
            raise SetupError("Seerr initialization was not confirmed.")
    except http.SetupError:
        raise SetupError("Authenticate the Jellyfin administrator with configure-jellyfin.py before finishing Seerr setup.") from None
    print("Seerr: setup completed through the native administrator API.")


def main():
    root = Path(__file__).resolve().parent.parent
    service = common.compose(root, "shared")["services"]["seerr"]
    env = service["environment"]
    if not boolean(env, "SEERR_SETUP_ENABLED"):
        print("Seerr: environment configuration disabled.")
        return
    config = next((v for v in service["volumes"] if v.get("type") == "bind" and v.get("target") == "/app/config"), None)
    if not config:
        raise SetupError("Seerr needs its /app/config bind mount for environment provisioning.")
    path = Path(config["source"]) / "settings.json"
    # Keep credentials-bearing snapshots out of all log output and source files.
    with open(Path(config["source"]) / ".configure-seerr.lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SetupError("Another Seerr configuration script is running.") from None
        run_compose(root, "up", "-d", "seerr")
        for attempt in range(30):
            try:
                read_settings(path)
                probe(root, {"kind": "public", "url": "http://127.0.0.1:5055"})
                break
            except SetupError:
                if attempt == 29:
                    raise
                time.sleep(2)
        servers = {}
        for app, stack, port in (("radarr", "movie", 7878), ("sonarr", "tv", 8989)):
            if not boolean(env, "SEERR_CONFIGURE_" + app.upper(), True):
                continue
            prefix = "SEERR_" + app.upper() + "_"
            url = env[prefix + "URL"]
            parsed = split_url(url, prefix + "URL")
            override = env.get(prefix + "API_KEY")
            if not override and parsed != {"hostname": app, "port": port, "useSsl": False, "baseUrl": ""}:
                raise SetupError(f"{app}: specify an API key explicitly for a non-local destination.")
            key = common.api_key(root, stack, app, override)
            metadata = probe(root, {"kind": "arr", "url": url, "key": key})
            servers[app] = build_server(app, env, metadata, key)
        media = None
        media_url = env.get("SEERR_MEDIA_SERVER_URL", "")
        if media_url:
            config = split_url(media_url, "SEERR_MEDIA_SERVER_URL")
            if not env.get("SEERR_MEDIA_SERVER_API_KEY"):
                raise SetupError("SEERR_MEDIA_SERVER_API_KEY is required with its server URL.")
            if env.get("SEERR_MEDIA_SERVER_TYPE", "").lower() not in ("jellyfin", "emby"):
                raise SetupError("Set SEERR_MEDIA_SERVER_TYPE to jellyfin or emby.")
            media = (config, probe(root, {"kind": "media", "url": media_url, "key": env["SEERR_MEDIA_SERVER_API_KEY"]}))
        current = read_settings(path)
        desired = merge_settings(current, env, servers, media)
        if current == desired:
            complete_setup(root, service, env)
            print("Seerr: settings already match .env; server connections verified.")
            return
        run_compose(root, "stop", "seerr")
        original = None
        owner = None
        applied = False
        try:
            original = read_settings(path)
            desired = merge_settings(original, env, servers, media)
            owner = path.stat()
            backups = path.parent / "backups"
            backups.mkdir(exist_ok=True, mode=0o700)
            stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = backups / f"env-settings-{stamp}.json"
            fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as out:
                json.dump(original, out)
            write_settings(path, desired, owner)
            applied = True
            run_compose(root, "up", "-d", "seerr")
            for attempt in range(30):
                try:
                    public = probe(root, {"kind": "public", "url": "http://127.0.0.1:5055"})
                    break
                except SetupError:
                    if attempt == 29:
                        raise
                    time.sleep(2)
            for field in ("applicationTitle", "applicationUrl", "locale", "discoverRegion", "streamingRegion", "localLogin", "mediaServerLogin"):
                if public.get(field) != desired["main"][field]:
                    raise SetupError("Seerr did not load the expected environment settings.")
            if public.get("initialized") != original["public"].get("initialized"):
                raise SetupError("Seerr setup state unexpectedly changed.")
            saved = read_settings(path)
            for app, expected in servers.items():
                matches = [row for row in saved[app] if row.get("name") == expected["name"]]
                if len(matches) != 1 or any(matches[0].get(k) != v for k, v in expected.items()):
                    raise SetupError(f"{app}: persisted Seerr settings do not match .env.")
            print("Seerr: .env settings applied, connections tested and running configuration verified.")
            print("Private settings backup created under shared/data/seerr/backups/.")
        except Exception:
            try:
                if applied:
                    run_compose(root, "stop", "seerr")
                    write_settings(path, original, owner)
            finally:
                run_compose(root, "up", "-d", "seerr")
            raise
        complete_setup(root, service, env)


if __name__ == "__main__":
    try:
        main()
    except (SetupError, OSError):
        # Never print exception text from filesystem/process/library failures which
        # could include a settings document or credentials.
        message = sys.exc_info()[1]
        print(str(message) if isinstance(message, SetupError) else "Seerr: filesystem operation failed.", file=sys.stderr)
        sys.exit(1)
