"""Verify client setup logic with fake APIs; no containers or secrets required."""
import copy
import importlib.util
import io
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error

SCRIPT = Path(os.environ.get(
    "DOWNLOAD_CLIENT_SCRIPT", Path(__file__).resolve().parents[1] / "scripts/configure-download-clients.py"
))
spec = importlib.util.spec_from_file_location("download_setup", SCRIPT)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
CREDENTIALS = {"username": "test-user", "password": "test-password-not-for-output"}


class FakeArr:
    def __init__(self, name, existing=None, reject=False):
        self.name, self.reject = name, reject
        self.clients = copy.deepcopy(existing or [])
        self.calls = []

    def call(self, path, method="GET", payload=None):
        self.calls.append((path, method, copy.deepcopy(payload)))
        if path == "downloadclient/schema":
            names = ["host", "port", "useSsl", "urlBase", "username", "password", "apiKey",
                     setup.APPS[self.name][3], "contentLayout"]
            return [{"implementation": "QBittorrent", "configContract": "QBittorrentSettings",
                     "fields": [{"name": name, "value": "original" if name == "contentLayout" else ""}
                                for name in names]}]
        if path == "downloadclient/test":
            if self.reject:
                raise setup.SetupError("Connection test refused.")
            return None
        if path == "downloadclient" and method == "POST":
            client = copy.deepcopy(payload)
            client["id"] = 1
            self.clients.append(client)
            return client
        if path.startswith("downloadclient/") and method == "PUT":
            self.clients = [copy.deepcopy(payload)]
            return payload
        if path == "downloadclient":
            return copy.deepcopy(self.clients)
        raise AssertionError(path)


class FakeShelfmark:
    def __init__(self, client=""):
        self.values = {"PROWLARR_TORRENT_CLIENT": client, "PROWLARR_URL": "http://existing-prowlarr"}
        self.calls = []

    def call(self, path, method="GET", payload=None):
        self.calls.append((path, method, copy.deepcopy(payload)))
        if method == "GET":
            return {"fields": [{"key": k, "value": v} for k, v in self.values.items()]}
        if method == "PUT":
            self.values.update(payload)
        return {"success": True}


class DownloadClientTests(unittest.TestCase):
    def test_new_clients_use_each_application_category_and_keep_schema_defaults(self):
        for name in setup.APPS:
            with self.subTest(app=name):
                api = FakeArr(name)
                status = setup.configure_arr(api, name, CREDENTIALS, "http://qbittorrent:8080")
                fields = {f["name"]: f["value"] for f in api.clients[0]["fields"]}
                self.assertEqual(fields[setup.APPS[name][3]], setup.APPS[name][4])
                self.assertEqual(fields["host"], "qbittorrent")
                self.assertEqual(fields["port"], 8080)
                self.assertEqual(fields["contentLayout"], "original")
                self.assertNotIn(CREDENTIALS["password"], status)
                if name != "prowlarr":
                    self.assertFalse(api.clients[0]["removeCompletedDownloads"])
                setup.configure_arr(api, name, CREDENTIALS, "http://qbittorrent:8080")
                self.assertEqual(len(api.clients), 1)

    def test_existing_client_is_preserved_without_update_flag(self):
        api = FakeArr("sonarr", [{"id": 4, "implementation": "QBittorrent", "enable": False,
                                 "priority": 9, "fields": [{"name": "host", "value": "custom"}]}])
        before = copy.deepcopy(api.clients)
        setup.configure_arr(api, "sonarr", CREDENTIALS, "http://qbittorrent:8080")
        self.assertEqual(api.clients, before)
        self.assertFalse(any(method == "PUT" for _, method, _ in api.calls))

    def test_update_existing_replaces_connection_only(self):
        api = FakeArr("radarr")
        setup.configure_arr(api, "radarr", CREDENTIALS, "http://old-client:8080")
        api.clients[0].update(priority=7, tags=[12])
        setup.configure_arr(api, "radarr", CREDENTIALS, "https://qbittorrent:9443/base", True)
        fields = {f["name"]: f["value"] for f in api.clients[0]["fields"]}
        self.assertEqual(fields["port"], 9443)
        self.assertTrue(fields["useSsl"])
        self.assertEqual(fields["urlBase"], "/base")
        self.assertEqual(api.clients[0]["priority"], 7)
        self.assertEqual(api.clients[0]["tags"], [12])
        self.assertEqual(len(api.clients), 1)

    def test_failed_test_does_not_create_client(self):
        api = FakeArr("lidarr", reject=True)
        with self.assertRaises(setup.SetupError):
            setup.configure_arr(api, "lidarr", CREDENTIALS, "http://qbittorrent:8080")
        self.assertEqual(api.clients, [])

    def test_shelfmark_existing_client_is_not_overwritten(self):
        api = FakeShelfmark("qbittorrent")
        before = copy.deepcopy(api.values)
        setup.configure_shelfmark(api, CREDENTIALS, "http://qbittorrent:8080", "/downloads/books", "test-key")
        self.assertEqual(api.values, before)
        self.assertFalse(any(method == "PUT" for _, method, _ in api.calls))

    def test_shelfmark_new_client_is_saved_and_tested(self):
        api = FakeShelfmark()
        setup.configure_shelfmark(api, CREDENTIALS, "http://qbittorrent:8080", "/downloads/books", "test-key")
        self.assertEqual(api.values["QBITTORRENT_CATEGORY"], "books")
        self.assertEqual(api.values["QBITTORRENT_DOWNLOAD_DIR"], "/downloads/books")
        self.assertEqual(api.calls[-2][0], "prowlarr_clients/action/test_qbittorrent")

    def test_http_errors_do_not_expose_response_or_password(self):
        api = setup.API("http://test.invalid")
        error = urllib.error.HTTPError("http://test.invalid", 401, "Unauthorized", {},
                                       io.BytesIO(CREDENTIALS["password"].encode()))
        with patch.object(api.opener, "open", side_effect=error):
            with self.assertRaises(setup.SetupError) as caught:
                api.call("auth/login", "POST", CREDENTIALS)
        self.assertNotIn(CREDENTIALS["password"], str(caught.exception))

    def test_partial_environment_credentials_are_rejected(self):
        with patch.dict(os.environ, {"QBITTORRENT_USERNAME": "test"}, clear=True):
            with self.assertRaises(setup.SetupError):
                setup.credentials_from_file_or_env(Path("missing"))


if __name__ == "__main__":
    unittest.main()
