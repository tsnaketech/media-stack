#!/usr/bin/env python3
"""Register and test Radarr/Sonarr in Profilarr without selecting sync profiles."""
import argparse
import stack_extensions as extensions
import http.cookiejar
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


class SetupError(Exception):
    """Credential-safe diagnostic."""


class Unavailable(SetupError):
    """Transient connection failure, safe to retry."""


def compose(root, stack):
    try:
        result = subprocess.run(
            extensions.compose_command(root, stack, ["config", "--format", "json"]),
            check=True, capture_output=True, text=True,
        )
        model = json.loads(result.stdout)
        extensions.store_management_model(root, stack, model)
        return model
    except (OSError, subprocess.CalledProcessError, ValueError):
        raise SetupError(f"Cannot resolve {stack} Compose configuration.") from None


def api_key(root, stack, app, override):
    if override:
        return override
    service = compose(root, stack)["services"][app]
    for volume in service.get("volumes", []):
        if volume.get("type") == "bind" and volume.get("target") == "/config":
            try:
                key = ET.parse(Path(volume["source"]) / "config.xml").findtext("ApiKey")
            except (OSError, ET.ParseError):
                break
            if key:
                return key
    raise SetupError(f"{app}: API key unavailable; start the application or provide its override.")


class Client:
    def __init__(self, base, origin):
        self.base = base.rstrip("/")
        parsed = urllib.parse.urlsplit(origin)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or "," in origin:
            raise SetupError("PROFILARR_ORIGIN must contain a single complete URL.")
        self.headers = {"Origin": origin, "Host": parsed.netloc}
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(self.cookies)
        )

    def call(self, path, payload=None, form=False):
        headers = dict(self.headers)
        headers["Accept"] = "application/json"
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
            data = (urllib.parse.urlencode(payload) if form else json.dumps(payload)).encode()
        request = urllib.request.Request(self.base + path, data=data, headers=headers)
        try:
            with self.opener.open(request, timeout=30) as response:
                result = json.loads(response.read())
        except urllib.error.HTTPError as error:
            raise SetupError(f"Profilarr returned HTTP {error.code} for {path}.") from None
        except OSError:
            raise Unavailable(f"Profilarr unavailable for {path}.") from None
        except ValueError:
            raise SetupError(f"Profilarr returned an unexpected response for {path}.") from None
        if isinstance(result, dict) and result.get("type") in ("failure", "error"):
            raise SetupError(f"Profilarr rejected the action on {path}.")
        return result

    def page(self, path):
        """Read SvelteKit page data without scraping HTML or writing its database."""
        document = self.call(path.rstrip("/") + "/__data.json")
        if any(node and node.get("type") == "error" for node in document.get("nodes", [])):
            raise SetupError("Profilarr page unavailable: check that its database is enabled and synchronized (database cache), then retry.")
        merged = {}
        for node in document.get("nodes", []):
            if node and node.get("type") == "data":
                merged.update(decode_page_data(node["data"]))
        return merged

    def login(self, username, password):
        result = self.call("/auth/login", {"username": username, "password": password}, form=True)
        if not isinstance(result, dict) or result.get("type") != "redirect" or result.get("location") != "/":
            raise SetupError("Profilarr login failed; apply the credentials hook first.")
        self.instances()  # An authenticated endpoint must return a JSON list.

    def instances(self):
        result = self.call("/api/v1/arr")
        if not isinstance(result, list):
            raise SetupError("Profilarr did not return an authenticated instance list.")
        return result


def decode_page_data(values):
    """Decode the plain objects, arrays and references used by these page loads."""
    memo = {}

    def resolve(index):
        if index < 0:
            return None
        if index in memo:
            return memo[index]
        value = values[index]
        if isinstance(value, dict):
            memo[index] = {}
            memo[index].update({key: resolve(ref) for key, ref in value.items()})
        elif isinstance(value, list):
            memo[index] = [resolve(ref) if isinstance(ref, int) else ref for ref in value]
        else:
            memo[index] = value
        return memo[index]

    return resolve(0)


def normalize(url):
    return url.rstrip("/")


def find_instance(instances, app, url):
    targets = [item for item in instances if item.get("type") == app and normalize(item.get("url", "")) == normalize(url)]
    if len(targets) > 1:
        raise SetupError(f"{app}: multiple matching connections; resolve them manually.")
    if targets:
        return targets[0]
    if any(item.get("name", "").lower() == app for item in instances):
        raise SetupError(f"{app}: name already used for a different destination; no changes made.")
    return None


def configure(client, app, url, key, update=False):
    instance = find_instance(client.instances(), app, url)
    payload = {"type": app, "url": url, "apiKey": key}
    if instance:
        payload["instanceId"] = instance["id"]
    result = client.call("/arr/validate", payload)
    if not isinstance(result, dict) or result.get("success") is not True:
        raise SetupError(f"{app}: connection test from Profilarr failed.")
    fields = {"name": app.capitalize(), "type": app, "url": url, "api_key": key, "tags": "[]"}
    if instance and update:
        fields.update({
            "name": instance["name"], "external_url": instance.get("external_url") or "",
            "tags": json.dumps(instance.get("tags") or []),
            "library_refresh_interval": instance.get("library_refresh_interval") or 0,
        })
        client.call(f"/arr/{instance['id']}/settings?/update", fields, form=True)
    elif not instance:
        result = client.call("/arr/new", fields, form=True)
        if not isinstance(result, dict) or result.get("type") != "redirect":
            raise SetupError(f"{app}: instance creation not confirmed.")
    if not find_instance(client.instances(), app, url):
        raise SetupError(f"{app}: connection not persisted.")
    print(f"{app}: connection {'updated' if instance and update else 'preserved' if instance else 'created'}; API test succeeded.")


def tmdb_settings_payload(settings, token):
    """Preserve every field submitted by Profilarr's general-settings form."""
    try:
        log, backup = settings["logSettings"], settings["backupSettings"]
        general, ai = settings["generalSettings"], settings["aiSettings"]
        payload = {
            "tmdb_api_key": token,
            "log_retention_days": log["retention_days"], "log_min_level": log["min_level"],
            "backup_schedule": backup["schedule"], "backup_retention_days": backup["retention_days"],
            "date_format": general["date_format"], "landing_page": general["landing_page"] or "",
            "ai_api_url": ai["api_url"], "ai_model": ai["model"],
        }
        toggles = {
            "log_enabled": log["enabled"], "log_file_logging": log["file_logging"],
            "log_console_logging": log["console_logging"], "backup_enabled": backup["enabled"],
            "ai_enabled": ai["enabled"],
            "arr_apply_default_delay_profiles": general["apply_default_delay_profiles"],
            "fail_on_referenced_delete": general["fail_on_referenced_delete"],
            "sync_prompt_enabled": general["sync_prompt_enabled"],
        }
    except KeyError:
        raise SetupError("Unsupported Profilarr settings schema; TMDB token not changed.") from None
    payload.update({key: "on" for key, enabled in toggles.items() if enabled})
    return payload


def configure_tmdb(client, token):
    token = (token or "").strip()
    if not token:
        return
    # Profilarr expects the raw API Read Access Token, not the literal Bearer prefix.
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    settings = client.page("/settings/general")
    payload = tmdb_settings_payload(settings, token)
    if client.call("/tmdb/validate", {"apiKey": token}).get("success") is not True:
        raise SetupError("TMDB rejected the supplied token; existing settings preserved.")
    result = client.call("/settings/general?/save", payload, form=True)
    if result.get("type") != "success":
        raise SetupError("Profilarr did not confirm the TMDB settings update.")
    if not client.page("/settings/general").get("tmdbSettings", {}).get("hasApiKey"):
        raise SetupError("Profilarr did not persist the TMDB token.")
    if client.call("/tmdb/validate", {}).get("success") is not True:
        raise SetupError("The TMDB token saved by Profilarr failed validation.")
    print("Profilarr: TMDB token applied and validated; token not displayed.")



def ensure_database(client, env):
    if str(env.get("PROFILARR_FRENCH_PROFILES_ENABLED", "false")).lower() != "true":
        return
    if str(env.get("PROFILARR_DATABASE_SETUP_ENABLED", "true")).lower() != "true":
        return
    name = env.get("PROFILARR_DATABASE_NAME", "Dictionarry")
    rows = client.call("/api/v1/databases")
    matches = [row for row in rows if row.get("name") == name]
    if len(matches) > 1:
        raise SetupError("Duplicate Profilarr database names; resolve manually.")
    if matches:
        database = matches[0]
        if database.get("enabled") == 0:
            print("Profilarr: existing database is disabled; preserved. Enable/synchronize it or disable French policy provisioning.")
            return
    else:
        database = client.call("/api/v1/databases", {
            "name": name,
            "repository_url": env.get("PROFILARR_DATABASE_URL", "https://github.com/Dictionarry-Hub/database"),
            "local_ops_enabled": True})
    if not isinstance(database, dict) or not database.get("id"):
        raise SetupError("Profilarr database registration was not confirmed.")
    path = "/custom-formats/" + str(database["id"])
    try:
        if "customFormats" in client.page(path):
            return
    except SetupError:
        pass
    client.call(f"/api/v1/databases/{database['id']}/sync", {})
    for _ in range(120):
        try:
            if "customFormats" in client.page(path):
                print("Profilarr: policy database registered and synchronized.")
                return
        except SetupError:
            pass
        time.sleep(1)
    raise SetupError("Profilarr database cache is unavailable; inspect its synchronization task, repository access and enabled state.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-existing", action="store_true", help="Refresh saved API keys while preserving other instance settings")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    service = compose(root, "shared")["services"]["profilarr"]
    env = service["environment"]
    if str(env.get("PROFILARR_SETUP_ENABLED", "false")).lower() != "true":
        print("Profilarr: automatic connections disabled.")
        return
    if env.get("AUTH") != "on" or not env.get("PROFILARR_PASSWORD"):
        raise SetupError("Set PROFILARR_AUTH=on and PROFILARR_USERNAME/PASSWORD in shared/.env first.")
    # Host runtime only; no Python installation is needed in the containers.
    ports = [p for p in service["ports"] if int(p["target"]) == 6868]
    if len(ports) != 1:
        raise SetupError("Expected one published Profilarr HTTP port.")
    bind = ports[0].get("host_ip", "0.0.0.0")
    host = "127.0.0.1" if bind in ("", "0.0.0.0") else bind
    if ":" in host:
        host = "[::1]" if host == "::" else f"[{host}]"
    client = Client(f"http://{host}:{ports[0]['published']}", env["ORIGIN"])
    for attempt in range(30):
        try:
            client.login(env.get("PROFILARR_USERNAME", "admin"), env["PROFILARR_PASSWORD"])
            break
        except Unavailable:
            if attempt == 29:
                raise
            time.sleep(2)
    configure_tmdb(client, env.get("PROFILARR_TMDB_API_TOKEN", ""))
    # Resolve both keys before creating either connection.
    targets = [
        (app, env[f"PROFILARR_{app.upper()}_URL"], api_key(root, stack, app, env.get(f"PROFILARR_{app.upper()}_API_KEY")))
        for app, stack in (("radarr", "movie"), ("sonarr", "tv"))
    ]
    for app, url, key in targets:
        configure(client, app, url, key, args.update_existing)
    ensure_database(client, env)


if __name__ == "__main__":
    try:
        main()
    except SetupError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
