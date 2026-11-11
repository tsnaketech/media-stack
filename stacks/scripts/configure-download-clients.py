#!/usr/bin/env python3
"""Configure qBittorrent clients and categories without starting downloads."""
import argparse
import stack_extensions as extensions
import importlib
import copy
import getpass
import http.cookiejar
import json
import os
from pathlib import Path
import posixpath
import sys
import urllib.error
import urllib.parse
import urllib.request

# name: (stack, published port, API version, category field, category)
APPS = {
    "prowlarr": ("indexer", 9696, "v1", "category", "prowlarr"),
    "lidarr": ("music", 8686, "v1", "musicCategory", "music"),
    "radarr": ("movie", 7878, "v3", "movieCategory", "movies"),
    "sonarr": ("tv", 8989, "v3", "tvCategory", "tv"),
}


class SetupError(Exception):
    """Safe diagnostic which never includes response bodies or credentials."""

APPS.update({name: tuple(spec) for name, spec in extensions.settings().get("applications", {}).items()})


class API:
    def __init__(self, base_url, headers=None, timeout=30):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        )

    def call(self, path, method="GET", payload=None, form=False):
        headers = dict(self.headers)
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
            data = (urllib.parse.urlencode(payload, doseq=True) if form else json.dumps(payload)).encode()
        request = urllib.request.Request(self.base_url + "/" + path, data=data, method=method, headers=headers)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as error:
            raise SetupError(f"HTTP {error.code} on {path}; check access and credentials.") from None
        except (urllib.error.URLError, OSError):
            raise SetupError(f"Cannot reach {path}; check the running service and network.") from None
        if not body:
            return None
        try:
            return json.loads(body)
        except (ValueError, UnicodeError):
            return body.decode(errors="replace").strip()



def qbit_headers(url):
    """Keep qBittorrent Host/Origin validation with a remapped published port."""
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname
    if ":" in host:
        host = "[" + host + "]"
    return {"Host": host, "Referer": f"{parsed.scheme}://{host}"}


def credentials_from_file_or_env(path):
    username, password = os.environ.get("QBITTORRENT_USERNAME"), os.environ.get("QBITTORRENT_PASSWORD")
    if username is not None or password is not None:
        values = {"username": username, "password": password}
    else:
        try:
            values = json.loads(path.read_text())
        except (OSError, ValueError):
            raise SetupError("Credentials file missing or invalid; use --init-credentials or supply both QBITTORRENT_* variables.") from None
    if not isinstance(values, dict) or not all(isinstance(values.get(k), str) and values[k] for k in ("username", "password")):
        raise SetupError("Both qBittorrent username and password must be non-empty strings.")
    return {key: values[key] for key in ("username", "password")}


def initialize_credentials(path):
    if path.exists():
        raise SetupError("Credentials file already exists; edit it locally instead of overwriting it.")
    username = input("Current qBittorrent username [admin]: ").strip() or "admin"
    password = getpass.getpass("Current qBittorrent password: ")
    if not password or password != getpass.getpass("Confirm password: "):
        raise SetupError("Passwords are empty or do not match; nothing saved.")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump({"username": username, "password": password}, handle)
    print("Existing credentials saved locally with mode 600; qBittorrent was not modified.")


def app_api(root, name, host):
    stack, port, version, _, _ = APPS[name]
    common = importlib.import_module("configure-profilarr")
    try:
        service = common.compose(root, stack)["services"][name]
        key = common.api_key(root, stack, name, None)
        published = next(p["published"] for p in service["ports"] if int(p["target"]) == port)
    except common.SetupError as error:
        raise SetupError(str(error)) from None
    except (KeyError, StopIteration):
        raise SetupError(f"{name}: published API port is unavailable in Compose.") from None
    return API(f"http://{host}:{published}/api/{version}", {"X-Api-Key": key})


def configure_arr(api, name, credentials, client_url, update_existing=False):
    existing = [c for c in api.call("downloadclient") if c.get("implementation") == "QBittorrent"]
    if len(existing) > 1:
        raise SetupError("Multiple qBittorrent clients exist; select the intended one in the interface.")
    if existing and not update_existing:
        api.call("downloadclient/test", "POST", existing[0])
        return "existing client preserved; connection test passed"
    if existing:
        payload = copy.deepcopy(existing[0])
    else:
        schema = next((s for s in api.call("downloadclient/schema") if s.get("implementation") == "QBittorrent"), None)
        if not schema:
            raise SetupError("qBittorrent schema unavailable in this application.")
        payload = {key: copy.deepcopy(schema[key]) for key in ("implementation", "configContract", "fields")}
        payload.update(name="qBittorrent", enable=True, priority=1, tags=[])
        if name != "prowlarr":
            payload.update(removeCompletedDownloads=False, removeFailedDownloads=False)
    target = urllib.parse.urlsplit(client_url)
    category_field, category = APPS[name][3:]
    values = dict(host=target.hostname, port=target.port or (443 if target.scheme == "https" else 80),
                  useSsl=target.scheme == "https", urlBase=target.path.rstrip("/"),
                  username=credentials["username"], password=credentials["password"], apiKey="")
    values[category_field] = category
    for field in payload["fields"]:
        if field["name"] in values:
            field["value"] = values[field["name"]]
    api.call("downloadclient/test", "POST", payload)
    if existing:
        api.call(f"downloadclient/{payload['id']}", "PUT", payload)
    else:
        api.call("downloadclient", "POST", payload)
    saved = [c for c in api.call("downloadclient") if c.get("implementation") == "QBittorrent"]
    if len(saved) != 1:
        raise SetupError("Saved qBittorrent client could not be verified.")
    fields = {f["name"]: f.get("value") for f in saved[0]["fields"]}
    if any(fields.get(k) != values[k] for k in ("host", "port", category_field)):
        raise SetupError("Saved client target or category does not match the requested settings.")
    api.call("downloadclient/test", "POST", saved[0])
    return f"client {'updated' if existing else 'created'}; category {category}; saved connection test passed"


def shelfmark_values(tab):
    if not isinstance(tab, dict) or not isinstance(tab.get("fields"), list):
        raise SetupError("Shelfmark settings unavailable; check authentication and SHELFMARK_API_KEY.")
    return {field["key"]: field.get("value") for field in tab["fields"]}


def checked(result):
    if not isinstance(result, dict) or not result.get("success"):
        raise SetupError("Shelfmark refused the settings or connection test; check its interface.")


def configure_shelfmark(api, credentials, client_url, books_path, prowlarr_key, update_existing=False):
    current = shelfmark_values(api.call("prowlarr_clients"))
    if current.get("PROWLARR_TORRENT_CLIENT") and not update_existing:
        if current["PROWLARR_TORRENT_CLIENT"] != "qbittorrent":
            raise SetupError("A different torrent client is selected; use --update-existing to replace it.")
        checked(api.call("prowlarr_clients/action/test_qbittorrent", "POST", {}))
        status = "existing client preserved; connection test passed"
    else:
        settings = dict(PROWLARR_TORRENT_CLIENT="qbittorrent", QBITTORRENT_URL=client_url,
                        QBITTORRENT_USERNAME=credentials["username"], QBITTORRENT_PASSWORD=credentials["password"],
                        QBITTORRENT_API_KEY="",
                        QBITTORRENT_CATEGORY="books", QBITTORRENT_DOWNLOAD_DIR=books_path)
        checked(api.call("prowlarr_clients/action/test_qbittorrent", "POST", settings))
        checked(api.call("prowlarr_clients", "PUT", settings))
        checked(api.call("prowlarr_clients/action/test_qbittorrent", "POST", {}))
        status = "client saved; category books; connection test passed"
    prowlarr = shelfmark_values(api.call("prowlarr_config"))
    if update_existing or not prowlarr.get("PROWLARR_URL"):
        checked(api.call("prowlarr_config", "PUT", dict(PROWLARR_ENABLED=True,
                    PROWLARR_URL="http://prowlarr:9696", PROWLARR_API_KEY=prowlarr_key)))
        status += "; Prowlarr link saved"
    return status


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="Repository root")
    parser.add_argument("--credentials", type=Path, help="Private JSON file (default: download/.qbittorrent-credentials.json)")
    parser.add_argument("--init-credentials", action="store_true", help="Save current credentials interactively and exit")
    parser.add_argument("--apps", nargs="+", choices=[*APPS, "shelfmark"], default=[*APPS, "shelfmark"])
    parser.add_argument("--api-host", default="127.0.0.1", help="Host exposing the application ports")
    parser.add_argument("--client-url", default="http://qbittorrent:8080", help="qBittorrent URL seen by the containers")
    parser.add_argument("--update-existing", action="store_true", help="Explicitly update existing client credentials and category")
    args = parser.parse_args(argv)
    args.root = args.root.resolve()
    args.credentials = args.credentials or args.root / "download/.qbittorrent-credentials.json"
    target = urllib.parse.urlsplit(args.client_url)
    if target.scheme not in ("http", "https") or not target.hostname or target.username or target.password or target.query or target.fragment:
        parser.error("--client-url must be an HTTP(S) URL without credentials, query or fragment")
    return args


def run(args):
    if args.init_credentials:
        initialize_credentials(args.credentials)
        return 0
    credentials = credentials_from_file_or_env(args.credentials)
    host = f"[{args.api_host}]" if ":" in args.api_host else args.api_host
    common = importlib.import_module("configure-profilarr")
    vpn = common.compose(args.root, "vpn")["services"]["gluetun"]
    qbit_port = next(p["published"] for p in vpn["ports"] if int(p["target"]) == 8080)
    qbit_url = f"http://{host}:{qbit_port}"
    qbit = API(qbit_url + "/api/v2", qbit_headers(qbit_url))
    qbit.call("auth/login", "POST", credentials, form=True)
    preferences = qbit.call("app/preferences")
    if not isinstance(preferences, dict):
        raise SetupError("qBittorrent authentication did not return valid preferences.")
    categories = qbit.call("torrents/categories")
    requested_categories = ["books" if name == "shelfmark" else APPS[name][4] for name in args.apps]
    for category in dict.fromkeys(requested_categories + ["other"]):
        if category not in categories:
            qbit.call("torrents/createCategory", "POST", {"category": category, "savePath": "/downloads/" + category}, form=True)
            categories[category] = {"savePath": "/downloads/" + category}
            print(f"Category {category}: created")
        else:
            print(f"Category {category}: preserved")
    failures = []
    for name in dict.fromkeys(args.apps):
        try:
            if name == "shelfmark":
                path = categories["books"].get("savePath") or ""
                books_path = posixpath.normpath(posixpath.join(preferences["save_path"], path))
                if not books_path.startswith("/downloads/"):
                    raise SetupError("Books category is outside /downloads; verify the shared mount before configuring Shelfmark.")
                prowlarr_api = app_api(args.root, "prowlarr", host)
                headers = {"X-API-Key": os.environ["SHELFMARK_API_KEY"]} if os.environ.get("SHELFMARK_API_KEY") else {}
                status = configure_shelfmark(API(f"http://{host}:8084/api/settings", headers), credentials,
                                             args.client_url, books_path, prowlarr_api.headers["X-Api-Key"], args.update_existing)
            else:
                status = configure_arr(app_api(args.root, name, host), name, credentials, args.client_url, args.update_existing)
            print(f"{name}: {status}")
        except (SetupError, KeyError, ValueError) as error:
            message = str(error) if isinstance(error, SetupError) else "Unexpected API response; check the application's settings."
            print(f"{name}: ERROR: {message}", file=sys.stderr)
            failures.append(name)
    if failures:
        print("Failed applications: " + ", ".join(failures), file=sys.stderr)
    return int(bool(failures))


def main(argv=None):
    try:
        return run(parse_args(argv))
    except (SetupError, OSError, ValueError, EOFError, importlib.import_module("configure-profilarr").SetupError) as error:
        message = str(error) if isinstance(error, SetupError) else "Cannot read settings or credentials; check local files and input."
        print("ERROR: " + message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
