#!/usr/bin/env python3
"""Bind torrent traffic to Gluetun's tunnel, preserving existing client settings."""
import importlib
import json
from pathlib import Path
import subprocess
import time


def main():
    helper = importlib.import_module("configure-download-clients")
    root = Path(__file__).resolve().parents[1]
    # Resolve the published port from Compose without printing environment secrets.
    common = importlib.import_module("configure-profilarr")
    config = common.compose(root, "vpn")
    mapping = next(p for p in config["services"]["gluetun"]["ports"]
                   if int(p["target"]) == 8080)
    host = mapping.get("host_ip", "0.0.0.0")
    host = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host
    host = f"[{host}]" if ":" in host else host
    endpoint = f"http://{host}:{mapping['published']}"
    api = helper.API(endpoint, helper.qbit_headers(endpoint))
    importlib.import_module("initialize").complete_qbittorrent(root)
    credentials = helper.credentials_from_file_or_env(root / "download/.qbittorrent-credentials.json")
    for attempt in range(30):
        try:
            api.call("api/v2/auth/login", "POST", credentials, form=True)
            preferences = api.call("api/v2/app/preferences")
            break
        except helper.SetupError:
            if attempt == 29:
                raise
            time.sleep(2)
    desired = {"current_network_interface": "tun0", "current_interface_address": "",
               "upnp": False, "random_port": False}
    if any(preferences.get(key) != value for key, value in desired.items()):
        api.call("api/v2/app/setPreferences", "POST", {"json": json.dumps(desired)}, form=True)
    preferences = api.call("api/v2/app/preferences")
    if any(preferences.get(key) != value for key, value in desired.items()):
        raise helper.SetupError("qBittorrent VPN preferences were not saved")
    print("qBittorrent: torrent interface tun0, UPnP and random port disabled")


if __name__ == "__main__":
    try:
        main()
    except (importlib.import_module("configure-download-clients").SetupError,
            importlib.import_module("configure-profilarr").SetupError,
            subprocess.CalledProcessError) as exc:
        raise SystemExit(f"VPN configuration failed: {exc}")
