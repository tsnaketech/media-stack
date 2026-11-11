#!/usr/bin/env python3
"""Configure Jellyfin library refreshes in the media arr applications."""
import copy
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import urllib.parse

common = importlib.import_module("configure-profilarr")
http = importlib.import_module("configure-download-clients")
jellyfin = importlib.import_module("configure-jellyfin")
APPS = (("lidarr", "music"), ("radarr", "movie"), ("sonarr", "tv"))
ROOTS = {"radarr": ("/movies", "/media/movies"), "sonarr": ("/tv", "/media/tv")}
APPS += tuple((name, spec[0]) for name, spec in common.extensions.settings().get("applications", {}).items())
ROOTS.update(common.extensions.settings().get("connect_roots", {}))
EVENTS = {"onDownload", "onReleaseImport", "onUpgrade", "onRename", "onMovieDelete",
          "onMovieFileDelete", "onSeriesDelete", "onEpisodeFileDelete", "onArtistDelete", "onAlbumDelete"}
LIDARR_SCRIPT = "/opt/refresh-lidarr-jellyfin.sh"


def field(row, name):
    return next((f.get("value") for f in row.get("fields", []) if f["name"] == name), None)


def parse_url(value):
    try:
        url = urllib.parse.urlsplit(value)
        if (url.scheme not in ("http", "https") or not url.hostname or url.username or url.password
                or url.query or url.fragment):
            raise ValueError()
        port = url.port or (443 if url.scheme == "https" else 80)
    except ValueError:
        raise common.SetupError("JELLYFIN_CONNECT_URL must be a valid HTTP(S) URL without credentials or query.") from None
    return {"host": url.hostname, "port": port, "useSsl": url.scheme == "https",
            "urlBase": url.path.rstrip("/")}


def find_connection(rows, destination):
    matches = [r for r in rows if r.get("implementation") == "MediaBrowser"
               and field(r, "host") == destination["host"]
               and int(field(r, "port") or 8096) == destination["port"]
               and bool(field(r, "useSsl")) == destination["useSsl"]
               and (field(r, "urlBase") or "").rstrip("/") == destination["urlBase"]]
    if len(matches) > 1:
        raise common.SetupError("Multiple Connect entries match Jellyfin; resolve duplicates manually.")
    if matches:
        return matches[0]
    if any(r.get("name") == "Jellyfin" for r in rows):
        raise common.SetupError("The Jellyfin Connect name is already used at another destination.")
    return None


def set_events(result, schema):
    for name in list(result):
        if name.startswith("on") and isinstance(result[name], bool):
            supported = schema.get("supports" + name[0].upper() + name[1:], False)
            result[name] = name in EVENTS and bool(supported)


def payload_for(app, schema, existing, destination, key, env):
    result = copy.deepcopy(existing or schema)
    if not existing:
        result.pop("id", None)
        result.update(name="Jellyfin", tags=[])
    set_events(result, schema)
    values = dict(destination, apiKey=key, notify=False, updateLibrary=True)
    if app in ROOTS:
        prefix = "JELLYFIN_CONNECT_" + app.upper()
        values["mapFrom"] = env.get(prefix + "_MAP_FROM", ROOTS[app][0])
        values["mapTo"] = env.get(prefix + "_MAP_TO", ROOTS[app][1])
    fields = {f["name"]: f for f in result.get("fields", [])}
    if not set(values).issubset(fields):
        raise common.SetupError(f"{app}: unsupported Jellyfin Connect schema.")
    for name, value in values.items():
        fields[name]["value"] = value
    return result


def lidarr_connection(schema, rows, destination):
    scripts = [row for row in rows if row.get("implementation") == "CustomScript"
               and field(row, "path") == LIDARR_SCRIPT]
    legacy = find_connection([row for row in rows if row not in scripts], destination)
    if len(scripts) + bool(legacy) > 1:
        raise common.SetupError("Lidarr: multiple Jellyfin Connect entries found.")
    existing = scripts[0] if scripts else legacy
    result = copy.deepcopy(scripts[0] if scripts else schema)
    if existing:
        result.update(id=existing["id"], name=existing["name"], tags=existing.get("tags", []))
    else:
        result.pop("id", None)
        result.update(name="Jellyfin", tags=[])
    set_events(result, schema)
    for item in result["fields"]:
        if item["name"] == "path":
            item["value"] = LIDARR_SCRIPT
        elif item["name"] == "arguments":
            item["value"] = ""
    return existing, result


def write_lidarr_config(root, env, key):
    service = common.compose(root, "music")["services"]["lidarr"]
    volume = next(v for v in service["volumes"] if v["target"] == "/config")
    path = Path(volume["source"]) / "jellyfin-connect.json"
    settings = {
        "url": env.get("JELLYFIN_CONNECT_URL", "http://jellyfin:8096").rstrip("/"),
        "api_key": key,
        "library_path": env.get("JELLYFIN_CONNECT_LIDARR_MAP_TO", "/media/music"),
    }
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(settings, stream)
            stream.close()
            if os.geteuid() == 0:
                owner = service["environment"]
                os.chown(temporary, int(owner.get("PUID", 1000)), int(owner.get("PGID", 1000)))
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def ensure_key(root, service, env):
    if env.get("JELLYFIN_CONNECT_API_KEY"):
        return env["JELLYFIN_CONNECT_API_KEY"]
    if env.get("JELLYFIN_CONNECT_URL", "http://jellyfin:8096").rstrip("/") != "http://jellyfin:8096":
        raise common.SetupError("Supply JELLYFIN_CONNECT_API_KEY for a custom destination.")
    api = http.API(jellyfin.local_url(service, 8096), {"Authorization":
        'MediaBrowser Client="Homelab Connect", Device="Server", DeviceId="homelab-connect", Version="1.0"'})
    session = api.call("Users/AuthenticateByName", "POST", {
        "Username": env.get("JELLYFIN_ADMIN_USERNAME", ""), "Pw": env.get("JELLYFIN_ADMIN_PASSWORD", "")})
    if not session.get("User", {}).get("Policy", {}).get("IsAdministrator"):
        raise common.SetupError("An administrator is required to create the Jellyfin Connect API key.")
    api.headers["Authorization"] += ', Token="' + session["AccessToken"] + '"'
    name = "Homelab Arr Connect"
    keys = api.call("Auth/Keys").get("Items", [])
    key = next((k["AccessToken"] for k in keys if k.get("AppName") == name and k.get("IsActive", True)), None)
    if not key:
        api.call("Auth/Keys?app=" + urllib.parse.quote(name), "POST")
        key = next((k["AccessToken"] for k in api.call("Auth/Keys").get("Items", []) if k.get("AppName") == name), None)
    if not key:
        raise common.SetupError("Jellyfin did not persist the Connect key.")
    jellyfin.update_env(root / "shared/.env", {"JELLYFIN_CONNECT_API_KEY": key})
    return key


def configure(targets, destination, key, env):
    plans = []
    for app, api in targets:
        implementation = "CustomScript" if app == "lidarr" else "MediaBrowser"
        schema = next((r for r in api.call("notification/schema") if r.get("implementation") == implementation), None)
        if not schema:
            raise common.SetupError(f"{app}: required Jellyfin notification type is unavailable.")
        rows = api.call("notification")
        if app == "lidarr":
            existing, payload = lidarr_connection(schema, rows, destination)
        else:
            existing = find_connection(rows, destination)
            payload = payload_for(app, schema, existing, destination, key, env)
        plans.append((app, api, existing, payload))
    for _, api, _, payload in plans:
        api.call("notification/test", "POST", payload)
    for app, api, existing, payload in plans:
        if existing:
            saved = api.call(f"notification/{existing['id']}", "PUT", payload) if payload != existing else existing
        else:
            saved = api.call("notification", "POST", payload)
        verified = api.call(f"notification/{saved['id']}")
        if verified.get("implementation") != payload["implementation"]:
            raise common.SetupError(f"{app}: Jellyfin notification type was not persisted.")
        fields = ("path", "arguments") if app == "lidarr" else (
            "host", "port", "useSsl", "urlBase", "notify", "updateLibrary", "mapFrom", "mapTo")
        for name in fields:
            if field(verified, name) != field(payload, name):
                raise common.SetupError(f"{app}: Jellyfin Connect settings were not persisted.")
        if any(verified.get(name) != value for name, value in payload.items()
               if name.startswith("on") and isinstance(value, bool)):
            raise common.SetupError(f"{app}: Jellyfin notification events were not persisted.")
        print(f"{app}: Jellyfin Connect configured; connection test passed; library updates enabled.")


def main():
    root = Path(__file__).resolve().parents[1]
    service = common.compose(root, "shared")["services"]["jellyfin"]
    env = service["environment"]
    if str(env.get("JELLYFIN_CONNECT_ENABLED", "true")).lower() != "true":
        print("Jellyfin Connect: automatic configuration disabled.")
        return
    destination = parse_url(env.get("JELLYFIN_CONNECT_URL", "http://jellyfin:8096"))
    targets = []
    for app, stack in APPS:
        if str(env.get("JELLYFIN_CONNECT_" + app.upper() + "_ENABLED", "true")).lower() != "true":
            continue
        svc = common.compose(root, stack)["services"][app]
        _, port, version, _, _ = http.APPS[app]
        targets.append((app, http.API(jellyfin.local_url(svc, port) + "/api/" + version,
                         {"X-Api-Key": common.api_key(root, stack, app, None)})))
    if not targets:
        print("Jellyfin Connect: no applications selected; existing entries preserved.")
        return
    key = ensure_key(root, service, env)
    if any(app == "lidarr" for app, _ in targets):
        write_lidarr_config(root, env, key)
    configure(targets, destination, key, env)


if __name__ == "__main__":
    try:
        main()
    except (common.SetupError, http.SetupError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
