#!/usr/bin/env python3
"""Register arr applications in Prowlarr and synchronize their indexers."""
import copy
import importlib
from pathlib import Path
import sys
import time
import urllib.parse

common = importlib.import_module("configure-profilarr")
http = importlib.import_module("configure-download-clients")
urls = importlib.import_module("configure-flaresolverr")
APPS = (("lidarr", "music", 8686), ("radarr", "movie", 7878),
        ("sonarr", "tv", 8989))
APPS += tuple((name, spec[0], spec[1]) for name, spec in common.extensions.settings().get("applications", {}).items())
LEVELS = {"disabled", "addOnly", "fullSync"}


def valid_url(value, label):
    value = value.rstrip("/")
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise common.SetupError(f"{label} must be an HTTP(S) URL without credentials or query.")
    return value


def field(row, name):
    return next((f.get("value") for f in row.get("fields", []) if f["name"] == name), None)


def find_application(rows, implementation, url):
    matches = [row for row in rows if row.get("implementation") == implementation
               and str(field(row, "baseUrl")).rstrip("/") == url]
    if len(matches) > 1:
        raise common.SetupError(f"Multiple {implementation} applications match; resolve duplicates manually.")
    if matches:
        return matches[0]
    if any(row.get("name") == implementation for row in rows):
        raise common.SetupError(f"{implementation} already exists at another destination; no changes made.")
    return None


def application_payload(schema, existing, url, prowlarr_url, key, level):
    if level not in LEVELS:
        raise common.SetupError("Sync level must be disabled, addOnly or fullSync.")
    result = copy.deepcopy(existing or schema)
    if not existing:
        result.pop("id", None)
        result["name"] = schema["implementation"]
        result["tags"] = []
    result["syncLevel"] = level
    fields = {f["name"]: f for f in result.get("fields", [])}
    if not {"baseUrl", "prowlarrUrl", "apiKey"}.issubset(fields):
        raise common.SetupError("Unsupported Prowlarr application schema.")
    for name, value in (("baseUrl", url), ("prowlarrUrl", prowlarr_url), ("apiKey", key)):
        fields[name]["value"] = value
    return result


def configure(api, root, env):
    prowlarr_url = valid_url(env.get("PROWLARR_APPS_PROWLARR_URL", "http://prowlarr:9696"),
                             "PROWLARR_APPS_PROWLARR_URL")
    rows = api.call("api/v1/applications")
    schemas = api.call("api/v1/applications/schema")
    plans = []
    for app, stack, port in APPS:
        prefix = "PROWLARR_APP_" + app.upper()
        if str(env.get(prefix + "_ENABLED", "true")).lower() != "true":
            continue
        default_url = f"http://{app}:{port}"
        url = valid_url(env.get(prefix + "_URL", default_url), prefix + "_URL")
        override = env.get(prefix + "_API_KEY", "")
        if url != default_url and not override:
            raise common.SetupError(f"Set {prefix}_API_KEY for a custom destination.")
        implementation = app.capitalize()
        existing = find_application(rows, implementation, url)
        schema = next((r for r in schemas if r.get("implementation") == implementation), None)
        if not schema:
            raise common.SetupError(f"Prowlarr does not provide a {implementation} schema.")
        level = env.get(prefix + "_SYNC_LEVEL") or env.get("PROWLARR_APPS_SYNC_LEVEL", "fullSync")
        payload = application_payload(schema, existing, url, prowlarr_url,
                                      common.api_key(root, stack, app, override), level)
        plans.append((implementation, existing, payload))
    # Test every destination before changing any saved application.
    for _, _, payload in plans:
        api.call("api/v1/applications/test", "POST", payload)
    for name, existing, payload in plans:
        if not existing:
            saved = api.call("api/v1/applications", "POST", payload)
        elif existing != payload:
            saved = api.call(f"api/v1/applications/{existing['id']}", "PUT", payload)
        else:
            saved = existing
        verified = api.call(f"api/v1/applications/{saved['id']}")
        if (verified.get("syncLevel") != payload["syncLevel"]
                or field(verified, "baseUrl") != field(payload, "baseUrl")
                or field(verified, "prowlarrUrl") != prowlarr_url):
            raise common.SetupError(f"{name}: application settings were not persisted.")
        print(f"Prowlarr: {name} registered and tested; sync level {payload['syncLevel']}.")
    if not plans:
        print("Prowlarr: no applications selected; existing entries preserved.")
        return
    command = api.call("api/v1/command", "POST", {"name": "ApplicationIndexerSync", "forceSync": True})
    for _ in range(120):
        status = api.call(f"api/v1/command/{command['id']}")
        if status.get("status") == "completed":
            print("Prowlarr: indexer synchronization command completed.")
            return
        if status.get("status") in ("failed", "aborted", "cancelled", "orphaned"):
            raise common.SetupError("Prowlarr indexer synchronization failed; inspect application events.")
        time.sleep(1)
    raise common.SetupError("Prowlarr synchronization is still running; inspect System / Tasks before retrying.")


def main():
    root = Path(__file__).resolve().parents[1]
    service = common.compose(root, "indexer")["services"]["prowlarr"]
    env = service["environment"]
    if str(env.get("PROWLARR_APPS_SETUP_ENABLED", "true")).lower() != "true":
        print("Prowlarr: automatic application configuration disabled.")
        return
    api = http.API(urls.local_url(service, 9696),
                   {"X-Api-Key": common.api_key(root, "indexer", "prowlarr", None)})
    for attempt in range(30):
        try:
            api.call("api/v1/system/status")
            break
        except http.SetupError:
            if attempt == 29:
                raise
            time.sleep(2)
    configure(api, root, env)


if __name__ == "__main__":
    try:
        main()
    except (common.SetupError, http.SetupError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
