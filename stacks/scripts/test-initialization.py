#!/usr/bin/env python3
"""Test a data-free checkout; optional native core smoke test in an isolated Docker project."""
import argparse
import importlib
import json
import os
import re
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

os.environ["STACK_EXTENSIONS_DIR"] = ""

bootstrap = importlib.import_module("initialize")
common = importlib.import_module("configure-profilarr")
http = importlib.import_module("configure-download-clients")
jellyfin = importlib.import_module("configure-jellyfin")
connect = importlib.import_module("configure-arr-connect")
prowlarr = importlib.import_module("configure-prowlarr-apps")


class CleanupFailure(common.SetupError):
    """Retain the fixture if Docker cannot remove its disposable project."""


def clone_fixture(source, destination):
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(
        "data", ".env", "*credentials*.json", "__pycache__", ".git", ".venv", "logs"))
    # The fixture contains public source/templates only, never production data or credentials.
    assert not list(destination.glob("*/.env"))
    assert not list(destination.glob("*/data"))
    media, downloads = destination.parent / "media", destination.parent / "downloads"
    for path in [media, downloads] + [media / n for n in ("movies", "tv", "music", "books", "audiobooks")]:
        path.mkdir(mode=0o755, exist_ok=True)
        if os.geteuid() == 0:
            os.chown(path, 1000, 1000)
    return media, downloads


def snapshot(root):
    files = list(root.glob("*/.env")) + [root / "download/.qbittorrent-credentials.json",
                                        root / "download/data/qbittorrent/qBittorrent/qBittorrent.conf"]
    return {str(p.relative_to(root)): p.read_bytes() for p in files}


def wait_http(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(90):
        try:
            with opener.open(url, timeout=3):
                return
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):
                return
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(1)
    raise common.SetupError("Isolated test service did not become ready")


def smoke(root, configs, pull=False):
    identifier = "init-test-" + secrets.token_hex(6)
    chosen = {"qbittorrent": "download", "prowlarr": "indexer", "radarr": "movie", "jellyfin": "shared"}
    services = {}
    for name, stack in chosen.items():
        svc = json.loads(json.dumps(configs[stack]["services"][name]))
        image = svc["image"]
        if subprocess.run(["docker", "image", "inspect", image], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
            if not pull:
                raise common.SetupError("A smoke-test image is missing; rerun with --pull or pull the images first")
            if svc.get("build"):
                bootstrap.run(["docker", "compose", "-f", str(root / stack / "docker-compose.yml"),
                               "build", "--pull", name])
            else:
                bootstrap.run(["docker", "pull", image])
        svc.update(container_name=identifier + "-" + name, restart="no")
        svc.pop("build", None)
        svc.pop("network_mode", None)
        svc.pop("depends_on", None)
        svc["networks"] = {"isolation": {"aliases": [name]}}
        # Only bind HTTP on loopback using ephemeral ports; never reuse production ports.
        svc["ports"] = [{"target": 8080 if name == "qbittorrent" else 9696 if name == "prowlarr" else 7878 if name == "radarr" else 8096,
                         "published": "0", "host_ip": "127.0.0.1", "protocol": "tcp"}]
        services[name] = svc
    model = {"name": identifier, "services": services,
             "networks": {"isolation": {"name": identifier, "internal": False}}}
    aggregate = root.parent / "smoke-compose.json"
    aggregate.write_text(json.dumps(model))
    aggregate.chmod(0o600)
    command = ["docker", "compose", "-p", identifier, "-f", str(aggregate)]
    try:
        bootstrap.run(command + ["up", "-d"])
        for name, svc in services.items():
            row = json.loads(subprocess.check_output(["docker", "inspect", svc["container_name"]]))[0]
            assert row["Config"]["Labels"]["com.docker.compose.project"] == identifier
            assert set(row["NetworkSettings"]["Networks"]) == {identifier}
            mapping = svc["ports"][0]
            mapping["published"] = row["NetworkSettings"]["Ports"][str(mapping["target"]) + "/tcp"][0]["HostPort"]
        # Write test-only resolved models so existing scripts discover ephemeral ports and binds.
        for name, stack in chosen.items():
            configs[stack]["services"][name] = services[name]
        configs["vpn"]["services"]["gluetun"]["ports"][0]["published"] = services["qbittorrent"]["ports"][0]["published"]
        configs["shared"]["services"]["seerr"]["environment"]["SEERR_BOOTSTRAP_WITH_JELLYFIN"] = "false"
        for stack, config in configs.items():
            config.setdefault("networks", {})["isolation"] = {"name": identifier, "external": True}
            p = root / stack / "docker-compose.yml"
            p.write_text(json.dumps(config))
            p.chmod(0o600)
        for svc in services.values():
            wait_http("http://127.0.0.1:" + svc["ports"][0]["published"] + "/")
        qbit_url = "http://127.0.0.1:" + services["qbittorrent"]["ports"][0]["published"]
        qbit = http.API(qbit_url + "/api/v2", http.qbit_headers(qbit_url))
        bootstrap.complete_qbittorrent(root)
        credentials = http.credentials_from_file_or_env(root / "download/.qbittorrent-credentials.json")
        qbit.call("auth/login", "POST", credentials, form=True)
        assert isinstance(qbit.call("app/preferences"), dict), "Initial qBittorrent password was not accepted"
        # Exercise the actual CLI twice: categories and arr clients must not duplicate.
        for _ in range(2):
            bootstrap.run([sys.executable, str(root / "scripts/configure-download-clients.py"), "--apps", "radarr"])
        categories = qbit.call("torrents/categories")
        assert categories["movies"]["savePath"] == "/downloads/movies"
        assert categories["other"]["savePath"] == "/downloads/other"
        assert qbit.call("torrents/info") == [], "Smoke test must never start a download"
        radarr = http.app_api(root, "radarr", "127.0.0.1")
        assert len(radarr.call("downloadclient")) == 1
        assert any(r["path"] == "/movies" for r in radarr.call("rootfolder")), "Native root-folder hook did not initialize"
        psvc = services["prowlarr"]
        papi = http.API(jellyfin.local_url(psvc, 9696), {"X-Api-Key": common.api_key(root, "indexer", "prowlarr", None)})
        env = {f"PROWLARR_APP_{app}_ENABLED": "false" for app in ("LIDARR", "SONARR")}
        prowlarr.configure(papi, root, env)
        prowlarr.configure(papi, root, env)
        assert len(papi.call("api/v1/applications")) == 1
        assert papi.call("api/v1/applications")[0]["syncLevel"] == "fullSync"
        # Native Jellyfin first-run wizard, libraries and generated integration key.
        bootstrap.run([sys.executable, str(root / "scripts/configure-jellyfin.py")])
        env = common.compose(root, "shared")["services"]["jellyfin"]["environment"]
        key = connect.ensure_key(root, services["jellyfin"], env)
        jellyfin_api = http.API(jellyfin.local_url(services["jellyfin"], 8096),
                               {"Authorization": f'MediaBrowser Token="{key}"'})
        repositories = jellyfin_api.call("Repositories")
        for _, _, url in jellyfin.PLUGIN_REPOSITORIES:
            assert sum(row["Url"] == url for row in repositories) == 1
        destination = connect.parse_url("http://jellyfin:8096")
        connect.configure([("radarr", radarr)], destination, key, {})
        connect.configure([("radarr", radarr)], destination, key, {})
        assert len(radarr.call("notification")) == 1
        print("Native clean-data smoke: qBittorrent credentials/categories, Radarr hooks/client, Prowlarr fullSync and Jellyfin Connect passed; repeat runs created no duplicates.")
    finally:
        # Cleanup is scoped to a random project, its temporary binds and dedicated network.
        result = subprocess.run(command + ["down", "--volumes", "--remove-orphans"], capture_output=True, text=True)
        if result.returncode:
            # A container/network removal race should not leave test resources behind.
            query = subprocess.run(["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=" + identifier], capture_output=True, text=True)
            ids = query.stdout.split()
            removed = subprocess.run(["docker", "rm", "-f", "-v", *ids], capture_output=True) if ids else None
            network = subprocess.run(["docker", "network", "inspect", identifier], capture_output=True)
            clean_network = subprocess.run(["docker", "network", "rm", identifier], capture_output=True) if network.returncode == 0 else None
            if query.returncode or (removed and removed.returncode) or (clean_network and clean_network.returncode):
                raise CleanupFailure("Smoke-test cleanup failed for " + identifier + "; temporary fixture retained for inspection")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", action="store_true", help="Run isolated native qBittorrent/Prowlarr/Radarr/Jellyfin smoke test")
    parser.add_argument("--pull", action="store_true", help="Allow pulling missing smoke-test images")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    # Exported settings must not inject production secrets into a clean fixture.
    variable_names = {"QBITTORRENT_USERNAME", "QBITTORRENT_PASSWORD", "SHELFMARK_API_KEY",
                      "COMPOSE_ENV_FILES", "COMPOSE_FILE", "COMPOSE_PROJECT_NAME"}
    for path in source.glob("*/.env.example"):
        variable_names.update(re.findall(r"^([A-Z][A-Z0-9_]*)=", path.read_text(), re.M))
    for path in source.glob("*/docker-compose.yml"):
        variable_names.update(re.findall(r"\$\{([A-Z][A-Z0-9_]*)", path.read_text()))
    for name in variable_names:
        os.environ.pop(name, None)
    base = Path(tempfile.mkdtemp(prefix="homelab-init-test-"))
    cleanup = True
    original_directory = Path.cwd()
    try:
        os.chdir(base)
        base.chmod(0o755)
        root = base / "stacks"
        media, downloads = clone_fixture(source, root)
        configs = bootstrap.prepare(root, media, downloads)
        before = snapshot(root)
        bootstrap.prepare(root, media, downloads)
        assert snapshot(root) == before, "Preparing twice changed accounts or configuration"
        for p in root.glob("*/.env"):
            assert p.stat().st_mode & 0o777 == 0o600
        assert not configs["vpn"]["services"]["gluetun"]["environment"].get("WIREGUARD_PRIVATE_KEY"), "Production VPN key leaked into fixture"
        print("Fresh checkout preparation passed: no production data/secrets, valid Compose models, private generated accounts, idempotent rerun.")
        if args.docker:
            smoke(root, configs, args.pull)
    except CleanupFailure:
        cleanup = False
        base.chmod(0o700)
        print("Retained test directory:", base, file=sys.stderr)
        raise
    finally:
        os.chdir(original_directory)
        if cleanup:
            shutil.rmtree(base)
    print("Test resources cleaned. Scope excludes a real VPN/provider, indexer searches, Profilarr policy sync and interactive app wizards; see docs/initialization.md.")


if __name__ == "__main__":
    try:
        main()
    except (common.SetupError, http.SetupError, OSError, ValueError, AssertionError) as error:
        message = str(error) if isinstance(error, (common.SetupError, http.SetupError, AssertionError)) else "Initialization smoke test failed; inspect the isolated test diagnostics."
        print(message, file=sys.stderr)
        sys.exit(1)
