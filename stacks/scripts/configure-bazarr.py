#!/usr/bin/env python3
"""Configure Bazarr's connections, French subtitle profile and form login."""
import copy
import importlib
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.parse

common = importlib.import_module("configure-profilarr")
http = importlib.import_module("configure-download-clients")
urls = importlib.import_module("configure-jellyfin")


def profile_settings(profiles, languages, name):
    result = copy.deepcopy(profiles)
    matches = [profile for profile in result if profile["name"] == name]
    if len(matches) > 1:
        raise common.SetupError("Bazarr has multiple matching language profiles; resolve manually.")
    if matches:
        profile = matches[0]
        if {item["language"] for item in profile["items"]} != {"fr"}:
            raise common.SetupError("The existing Bazarr language-profile name targets different languages.")
    else:
        profile = {"profileId": max((int(p["profileId"]) for p in result), default=0) + 1,
                   "name": name, "cutoff": 1, "mustContain": [], "mustNotContain": [],
                   "originalFormat": False, "tag": None,
                   "items": [{"id": 1, "language": "fr", "hi": "False", "forced": "False",
                              "audio_exclude": "False", "audio_only_include": "False"}]}
        result.append(profile)
    enabled = sorted({lang["code2"] for lang in languages if lang.get("enabled")} | {"fr"})
    return profile["profileId"], {"languages-enabled": enabled, "languages-profiles": json.dumps(result)}


def connection_fields(app, url, key):
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        raise common.SetupError(f"Invalid Bazarr {app} URL.") from None
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise common.SetupError(f"Bazarr {app} URL must not contain credentials or query parameters.")
    return {f"settings-{app}-ip": parsed.hostname, f"settings-{app}-port": port,
            f"settings-{app}-ssl": str(parsed.scheme == "https").lower(),
            f"settings-{app}-base_url": parsed.path or "/", f"settings-{app}-apikey": key,
            f"settings-general-use_{app}": "true"}


def api_key(root):
    # Use Bazarr's bundled YAML parser; no dependency installation on the host.
    code = ("import sys;sys.path[:0]=['/app/bazarr/bin/libs','/app/bazarr/libs'];"
            "import yaml;print(yaml.safe_load(open('/config/config/config.yaml'))['auth']['apikey'])")
    try:
        result = subprocess.run(common.extensions.compose_command(root, "shared",
                                ["exec", "-T", "bazarr", "python3", "-c", code]),
                                check=True, text=True, capture_output=True, timeout=15)
        key = result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        raise common.SetupError("Bazarr API key unavailable; wait for startup or check its config volume.") from None
    if not key:
        raise common.SetupError("Bazarr API key is empty.")
    return key


def main():
    root = Path(__file__).resolve().parent.parent
    service = common.compose(root, "shared")["services"]["bazarr"]
    env = service["environment"]
    if str(env.get("BAZARR_SETUP_ENABLED", "false")).lower() != "true":
        print("Bazarr: automatic configuration disabled.")
        return
    for attempt in range(30):
        try:
            key = api_key(root)
            api = http.API(urls.local_url(service, 6767), {"X-API-KEY": key})
            settings = api.call("api/system/settings")
            break
        except (common.SetupError, http.SetupError):
            if attempt == 29:
                raise
            time.sleep(2)
    profile_id, payload = profile_settings(api.call("api/system/languages/profiles"),
                                          api.call("api/system/languages"), env["BAZARR_LANGUAGE_PROFILE"])
    payload.update({"settings-general-movie_default_enabled": "true", "settings-general-serie_default_enabled": "true",
                    "settings-general-movie_default_profile": profile_id, "settings-general-serie_default_profile": profile_id})
    for app, stack, port in (("radarr", "movie", 7878), ("sonarr", "tv", 8989)):
        url = env[f"BAZARR_{app.upper()}_URL"]
        override = env.get(f"BAZARR_{app.upper()}_API_KEY")
        if not override and url.rstrip("/") != f"http://{app}:{port}":
            raise common.SetupError(f"Set an explicit Bazarr {app} API key for a different destination.")
        payload.update(connection_fields(app, url, common.api_key(root, stack, app, override)))
    password = env.get("BAZARR_PASSWORD", "")
    if password:
        if not env.get("BAZARR_USERNAME") or len(password) < 12:
            raise common.SetupError("Set BAZARR_USERNAME and a BAZARR_PASSWORD of at least 12 characters.")
        payload.update({"settings-auth-type": "form", "settings-auth-username": env["BAZARR_USERNAME"],
                        "settings-auth-password": password})
    api.call("api/system/settings", "POST", payload, form=True)
    verified = api.call("api/system/settings")
    for app in ("radarr", "sonarr"):
        if not verified["general"][f"use_{app}"] or verified[app]["apikey"] != payload[f"settings-{app}-apikey"]:
            raise common.SetupError(f"Bazarr {app} settings were not persisted.")
    profile_ids = {p["profileId"] for p in api.call("api/system/languages/profiles")}
    if profile_id not in profile_ids or any(
            str(verified["general"][kind + "_default_profile"]) != str(profile_id) or
            not verified["general"][kind + "_default_enabled"] for kind in ("movie", "serie")):
        raise common.SetupError("Bazarr French language defaults were not confirmed.")
    if password:
        login = http.API(urls.local_url(service, 6767))
        login.call("api/system/account", "POST", {"action": "login", "username": env["BAZARR_USERNAME"], "password": password}, form=True)
    status = api.call("api/system/status")["data"]
    for app in ("radarr", "sonarr"):
        if not status.get(app + "_version") or str(status[app + "_version"]).lower() in ("unknown", "none"):
            raise common.SetupError(f"Bazarr cannot identify the {app} version; check its connection.")
    auth_status = "login verified" if password else "existing authentication preserved"
    print(f"Bazarr: Radarr/Sonarr connections and French subtitle defaults configured; {auth_status}.")
    if not verified["general"].get("enabled_providers"):
        print("No subtitle provider enabled; select providers and credentials in Settings > Providers.")


if __name__ == "__main__":
    try:
        main()
    except (common.SetupError, http.SetupError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
