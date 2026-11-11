#!/usr/bin/env python3
"""Initialize local Jellyfin and export its Seerr connection into shared/.env."""
import importlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import urllib.parse

common = importlib.import_module("configure-profilarr")
http = importlib.import_module("configure-download-clients")
PLUGIN_REPOSITORIES = (
    ("JELLYFIN_ENHANCED_REPOSITORY", "Jellyfin-Enhanced",
     "https://raw.githubusercontent.com/n00bcodr/jellyfin-plugins/main/manifest.json"),
)
PLUGIN_REPOSITORIES += tuple(tuple(row) for row in common.extensions.settings().get("plugin_repositories", []))


def update_env(path, values):
    """Write generated connection values without exposing secrets in arguments."""
    original = path.read_text()
    updated = original
    for key, value in values.items():
        if any(c in value for c in ("\n", "\r", "'")):
            raise common.SetupError("Unexpected characters in a generated connection setting.")
        line = key + "='" + value + "'"
        pattern = re.compile(r"^" + re.escape(key) + r"=.*$", re.M)
        updated = pattern.sub(lambda _: line, updated) if pattern.search(updated) else updated + "\n" + line + "\n"
    if updated == original:
        return
    owner = path.stat()
    fd, temporary = tempfile.mkstemp(prefix=".env.jellyfin-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        os.fchown(fd, owner.st_uid, owner.st_gid)
        with os.fdopen(fd, "w") as out:
            out.write(updated)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def local_url(service, target):
    mapping = next(p for p in service["ports"] if int(p["target"]) == target and p.get("protocol", "tcp") == "tcp")
    host = mapping.get("host_ip") or "127.0.0.1"
    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"
    if ":" in host:
        host = "[" + host + "]"
    return f"http://{host}:{mapping['published']}"


def ensure_plugin_repositories(api, env):
    if str(env.get("JELLYFIN_PLUGIN_REPOSITORIES_ENABLED", "true")).lower() != "true":
        print("Jellyfin: plugin repository setup disabled.")
        return
    requested = []
    for variable, name, default in PLUGIN_REPOSITORIES:
        url = env.get(variable, default).strip()
        if not url:
            continue
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            raise common.SetupError(f"{variable} must contain an HTTP(S) manifest URL without credentials.")
        requested.append({"Name": name, "Url": url, "Enabled": True})
    if not requested:
        return
    existing = api.call("Repositories")
    merged = list(existing)
    known = {row["Url"].rstrip("/") for row in existing}
    for row in requested:
        if row["Url"].rstrip("/") not in known:
            merged.append(row)
            known.add(row["Url"].rstrip("/"))
    if merged != existing:
        api.call("Repositories", "POST", merged)
        saved = {row["Url"].rstrip("/") for row in api.call("Repositories")}
        if not all(row["Url"].rstrip("/") in saved for row in requested):
            raise common.SetupError("Jellyfin did not persist the configured plugin repositories.")
    print(f"Jellyfin: {len(requested)} configured plugin repositories verified.")


def ensure_library(api, name, collection_type, path):
    libraries = api.call("Library/VirtualFolders")
    matches = [lib for lib in libraries if lib["Name"] == name]
    if len(matches) > 1:
        raise common.SetupError("Duplicate Jellyfin library names; resolve manually.")
    if matches:
        if path not in matches[0].get("Locations", []) or matches[0].get("CollectionType") != collection_type:
            raise common.SetupError("An existing Jellyfin library has a different path/type; no replacement attempted.")
        return str(matches[0]["ItemId"])
    query = urllib.parse.urlencode({"name": name, "collectionType": collection_type, "refreshLibrary": "false"})
    api.call("Library/VirtualFolders?" + query, "POST", {"LibraryOptions": {
        "PathInfos": [{"Path": path}], "PreferredMetadataLanguage": "fr", "MetadataCountryCode": "FR",
        "EnableRealtimeMonitor": True, "SaveLocalMetadata": False,
    }})
    match = next((lib for lib in api.call("Library/VirtualFolders") if lib["Name"] == name), None)
    if not match:
        raise common.SetupError("Jellyfin library creation was not persisted.")
    return str(match["ItemId"])



def ensure_restricted_library(api, name, collection_type, path):
    libraries = api.call("Library/VirtualFolders")
    if not any(lib["Name"] == name for lib in libraries):
        # Freeze existing all-library grants before adding a sensitive library.
        # Existing explicit grants and administrator access remain unchanged.
        existing_ids = [str(lib["ItemId"]) for lib in libraries]
        for user in api.call("Users"):
            policy = user.get("Policy", {})
            if policy.get("IsAdministrator") or not policy.get("EnableAllFolders"):
                continue
            policy = dict(policy, EnableAllFolders=False, EnabledFolders=existing_ids)
            api.call(f"Users/{user['Id']}/Policy", "POST", policy)
    return ensure_library(api, name, collection_type, path)


def bootstrap_seerr(service, jellyfin_env):
    if str(service["environment"].get("SEERR_BOOTSTRAP_WITH_JELLYFIN", "false")).lower() != "true":
        return
    api = http.API(local_url(service, 5055))
    public = api.call("api/v1/settings/public")
    if public.get("initialized"):
        return
    # Follow the same supported media-server login flow as the setup wizard.
    root_volume = next(v for v in service["volumes"] if v.get("target") == "/app/config")
    settings = json.loads((Path(root_volume["source"]) / "settings.json").read_text())
    payload = {"username": jellyfin_env["JELLYFIN_ADMIN_USERNAME"],
               "password": jellyfin_env["JELLYFIN_ADMIN_PASSWORD"], "serverType": 2}
    if not settings.get("jellyfin", {}).get("ip"):
        payload.update(hostname="jellyfin", port=8096, useSsl=False, urlBase="")
    user = api.call("api/v1/auth/jellyfin", "POST", payload)
    if user.get("id") != 1:
        raise common.SetupError("Seerr bootstrap did not authenticate its first administrator.")
    print("Seerr: Jellyfin administrator authenticated through the native login flow.")


def abyss_css(css):
    """Refresh managed imports while preserving custom rules, even inside old markers."""
    start, end = "/* ABYSS THEME START */", "/* ABYSS THEME END */"
    remaining = (css or "").replace(start, "").replace(end, "")
    imports = r'@import\s+url\(\s*([\"\x27]?)(?:/web/ui/(?:abyss|abyss-je)\.css|https://cdn\.jsdelivr\.net/gh/AumGupta/abyss-jellyfin@[^\s\"\x27()]+/(?:abyss\.css|styles/abyss-je\.css))\1\s*\)\s*;'
    remaining = re.sub(imports, "", remaining).strip()
    block = start + '\n@import url("/web/ui/abyss.css");\n@import url("/web/ui/abyss-je.css");\n' + end
    return block + ("\n\n" + remaining if remaining else "")


def ensure_abyss(api, user_id, config_path):
    branding = api.call("Branding/Configuration")
    query = urllib.parse.urlencode({"userId": user_id, "client": "emby"})
    path = "DisplayPreferences/usersettings?" + query
    preferences = api.call(path)
    backup = config_path / "abyss-before.json"
    if not backup.exists():
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump({"branding": branding, "displayPreferences": preferences, "userId": user_id}, stream)
    updated_css = abyss_css(branding.get("CustomCss"))
    if branding.get("CustomCss") != updated_css:
        api.call("System/Configuration/Branding", "POST", dict(branding, CustomCss=updated_css))
    expected = {
        "appTheme": "dark", "dashboardTheme": "dark",
        "homesection0": "resume", "homesection1": "nextup",
        "homesection2": "smalllibrarytiles", "homesection3": "latestmedia",
    }
    custom = preferences.setdefault("CustomPrefs", {})
    if any(custom.get(key) != value for key, value in expected.items()):
        custom.update(expected)
        api.call(path, "POST", preferences)
    print("Jellyfin: Abyss branding and administrator display preferences configured.")


def main():
    root = Path(__file__).resolve().parent.parent
    configuration = common.compose(root, "shared")
    service = configuration["services"]["jellyfin"]
    env = service["environment"]
    if str(env.get("JELLYFIN_SETUP_ENABLED", "false")).lower() != "true":
        print("Jellyfin: environment setup disabled.")
        return
    username, password = env.get("JELLYFIN_ADMIN_USERNAME", ""), env.get("JELLYFIN_ADMIN_PASSWORD", "")
    if not username or len(password) < 12:
        raise common.SetupError("Set JELLYFIN_ADMIN_USERNAME and an administrator password of at least 12 characters.")
    api = http.API(local_url(service, 8096), {"Authorization":
        'MediaBrowser Client="Homelab setup", Device="Server", DeviceId="homelab-setup", Version="1.0"'})
    for attempt in range(60):
        try:
            public = api.call("System/Info/Public")
            break
        except http.SetupError:
            if attempt == 59:
                raise
            time.sleep(2)
    fresh = not public.get("StartupWizardCompleted")
    if fresh:
        api.call("Startup/User")
        api.call("Startup/Configuration", "POST", {"ServerName": env.get("JELLYFIN_SERVER_NAME", "Homelab"),
                 "UICulture": "fr", "MetadataCountryCode": "FR", "PreferredMetadataLanguage": "fr"})
        try:
            api.call("Startup/User", "POST", {"Name": username, "Password": password})
        except http.SetupError as error:
            # A partial previous run may already have set the password; never reset it.
            if "HTTP 403 " not in str(error):
                raise
    session = api.call("Users/AuthenticateByName", "POST", {"Username": username, "Pw": password})
    if not session.get("User", {}).get("Policy", {}).get("IsAdministrator"):
        raise common.SetupError("Jellyfin credentials must belong to an administrator.")
    api.headers["Authorization"] += ', Token="' + session["AccessToken"] + '"'
    api.headers["X-Emby-Token"] = session["AccessToken"]
    config = next(v for v in service["volumes"] if v.get("target") == "/config")
    ensure_abyss(api, session["User"]["Id"], Path(config["source"]))
    if fresh:
        api.call("Startup/RemoteAccess", "POST", {"EnableRemoteAccess": True, "EnableAutomaticPortMapping": False})
        api.call("Startup/Complete", "POST")
    ensure_plugin_repositories(api, env)
    keys = api.call("Auth/Keys").get("Items", [])
    key = next((k["AccessToken"] for k in keys if k.get("AppName") == "Homelab Seerr" and k.get("IsActive", True)), None)
    if not key:
        api.call("Auth/Keys?app=Homelab%20Seerr", "POST")
        key = next((k["AccessToken"] for k in api.call("Auth/Keys")["Items"] if k.get("AppName") == "Homelab Seerr"), None)
    if not key:
        raise common.SetupError("Jellyfin did not return its Seerr integration key.")
    libraries = {}
    for name_key, collection, path in (("MOVIES", "movies", "/media/movies"),
                                        ("TV", "tvshows", "/media/tv"),
                                        ("MUSIC", "music", "/media/music")):
        libraries[name_key] = ensure_library(api, env[f"JELLYFIN_{name_key}_NAME"], collection, path)
    extra_created = False
    for library in common.extensions.settings(root).get("jellyfin_libraries", []):
        if str(env.get(library["enabled"], "false")).lower() != "true":
            continue
        name = env.get(library["name_variable"], library["name"])
        if not name or name in [env[f"JELLYFIN_{kind}_NAME"] for kind in ("MOVIES", "TV", "MUSIC")]:
            raise common.SetupError("An additional library needs a unique, non-empty name.")
        extra_created |= not any(lib["Name"] == name for lib in api.call("Library/VirtualFolders"))
        ensure = ensure_restricted_library if library.get("restricted") else ensure_library
        libraries[library["key"]] = ensure(api, name, library["type"], library["path"])
    update_env(root / "shared/.env", {
        "JELLYFIN_API_KEY": key,
        "SEERR_MEDIA_SERVER_TYPE": "jellyfin",
        "SEERR_MEDIA_SERVER_URL": "http://jellyfin:8096",
        "SEERR_MEDIA_SERVER_API_KEY": key,
        "SEERR_MEDIA_SERVER_EXTERNAL_URL": env.get("JELLYFIN_PublishedServerUrl", ""),
        "SEERR_MEDIA_SERVER_LIBRARY_IDS": ",".join([libraries["MOVIES"], libraries["TV"]]),
    })
    bootstrap_seerr(configuration["services"]["seerr"], env)
    config = next(v for v in service["volumes"] if v.get("target") == "/config")
    marker = Path(config["source"]).parent / ".initial-library-scan"
    if fresh or extra_created or not marker.exists() or marker.read_text() != public["Id"]:
        api.call("Library/Refresh", "POST")
        marker.write_text(public["Id"])
        marker.chmod(0o600)
    print(f"Jellyfin: administrator and {len(libraries)} libraries verified; Seerr connection saved in shared/.env.")


if __name__ == "__main__":
    try:
        main()
    except (common.SetupError, http.SetupError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
