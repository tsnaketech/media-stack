#!/usr/bin/env python3
"""Register and test a tagged FlareSolverr proxy in Prowlarr."""
import copy
import csv
import importlib
from pathlib import Path
import re
import sys
import time
import urllib.parse

common = importlib.import_module("configure-profilarr")
http = importlib.import_module("configure-download-clients")


def field_value(row, name):
    return next((f.get("value") for f in row.get("fields", []) if f["name"] == name), None)


def find_proxy(rows, url):
    matches = [row for row in rows if row.get("implementation") == "FlareSolverr" and (
        str(field_value(row, "host")).rstrip("/") == url.rstrip("/") or row.get("name") == "FlareSolverr")]
    if len(matches) > 1:
        raise common.SetupError("Multiple matching FlareSolverr proxies; resolve duplicates manually.")
    if not matches and any(row.get("name") == "FlareSolverr" for row in rows):
        raise common.SetupError("The FlareSolverr name is already used by another proxy type.")
    return matches[0] if matches else None


def selected_indexers(rows, value):
    if not value.strip():
        return []
    try:
        names = next(csv.reader([value], skipinitialspace=True, strict=True))
    except csv.Error:
        raise common.SetupError("FLARESOLVERR_INDEXERS must contain CSV indexer names.") from None
    if any(not n.strip() for n in names) or len(set(names)) != len(names):
        raise common.SetupError("FlareSolverr indexer names must be unique and non-empty.")
    selected = []
    for name in names:
        matches = [row for row in rows if row.get("name") == name.strip()]
        if len(matches) != 1:
            raise common.SetupError("An indexer named in FLARESOLVERR_INDEXERS was not found uniquely.")
        selected.append(matches[0])
    return selected


def proxy_payload(schema, existing, url, timeout, tag_id):
    result = copy.deepcopy(existing or schema)
    result["name"] = result.get("name") or "FlareSolverr"
    result["tags"] = [tag_id]
    fields = {field["name"]: field for field in result["fields"]}
    if not {"host", "requestTimeout"}.issubset(fields):
        raise common.SetupError("Unsupported Prowlarr FlareSolverr schema.")
    fields["host"]["value"] = url
    fields["requestTimeout"]["value"] = timeout
    return result


def local_url(service, port):
    mapping = next(p for p in service["ports"] if int(p["target"]) == port)
    host = mapping.get("host_ip") or "127.0.0.1"
    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"
    if ":" in host:
        host = "[" + host + "]"
    return f"http://{host}:{mapping['published']}"


def main():
    root = Path(__file__).resolve().parent.parent
    configuration = common.compose(root, "indexer")
    prowlarr = configuration["services"]["prowlarr"]
    env = prowlarr["environment"]
    if str(env.get("FLARESOLVERR_SETUP_ENABLED", "false")).lower() != "true":
        print("FlareSolverr: automatic Prowlarr configuration disabled.")
        return
    url = env["FLARESOLVERR_URL"]
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise common.SetupError("FLARESOLVERR_URL must be a complete HTTP(S) URL without embedded credentials.")
    try:
        timeout = int(env.get("FLARESOLVERR_REQUEST_TIMEOUT", "60"))
    except ValueError:
        raise common.SetupError("FLARESOLVERR_REQUEST_TIMEOUT must be an integer.") from None
    if not 1 <= timeout <= 180:
        raise common.SetupError("FLARESOLVERR_REQUEST_TIMEOUT must be between 1 and 180 seconds.")
    label = env.get("FLARESOLVERR_TAG", "flaresolverr")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", label):
        raise common.SetupError("FLARESOLVERR_TAG must use lowercase letters, digits and hyphens.")
    ready = http.API(local_url(configuration["services"]["flaresolverr"], 8191), timeout=5)
    for attempt in range(60):
        try:
            status = ready.call("")
            if not isinstance(status, dict) or not status.get("version"):
                raise common.SetupError("FlareSolverr readiness response was unexpected.")
            break
        except http.SetupError:
            if attempt == 59:
                raise
            time.sleep(2)
    key = common.api_key(root, "indexer", "prowlarr", None)
    api = http.API(local_url(prowlarr, 9696), {"X-Api-Key": key}, timeout=timeout + 20)
    existing = find_proxy(api.call("api/v1/indexerproxy"), url)
    targets = selected_indexers(api.call("api/v1/indexer"), env.get("FLARESOLVERR_INDEXERS", ""))
    schema = next((row for row in api.call("api/v1/indexerproxy/schema") if row.get("implementation") == "FlareSolverr"), None)
    if not schema:
        raise common.SetupError("Prowlarr does not provide the FlareSolverr proxy schema.")
    tags = api.call("api/v1/tag")
    tag = next((row for row in tags if row["label"] == label), None)
    if not tag:
        tag = api.call("api/v1/tag", "POST", {"label": label})
    payload = proxy_payload(schema, existing, url, timeout, tag["id"])
    api.call("api/v1/indexerproxy/test", "POST", payload)
    if existing:
        if payload != existing:
            saved = api.call(f"api/v1/indexerproxy/{existing['id']}", "PUT", payload)
        else:
            saved = existing
    else:
        saved = api.call("api/v1/indexerproxy", "POST", payload)
    verified = next((row for row in api.call("api/v1/indexerproxy") if row["id"] == saved["id"]), None)
    if not verified or field_value(verified, "host") != url or verified["tags"] != [tag["id"]]:
        raise common.SetupError("FlareSolverr proxy settings were not persisted correctly.")
    updated = 0
    for row in targets:
        if tag["id"] not in row.get("tags", []):
            payload = copy.deepcopy(row)
            payload["tags"] = row.get("tags", []) + [tag["id"]]
            api.call(f"api/v1/indexer/{row['id']}", "PUT", payload)
            updated += 1
    print(f"FlareSolverr: proxy registered and connection tested by Prowlarr; {updated} indexers tagged.")
    if not targets:
        print(f"Apply the '{label}' tag to the indexers that need this proxy, or set FLARESOLVERR_INDEXERS.")


if __name__ == "__main__":
    try:
        main()
    except (common.SetupError, http.SetupError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
