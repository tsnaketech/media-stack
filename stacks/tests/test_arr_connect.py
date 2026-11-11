"""Protect native Jellyfin connections and their path mappings."""
import copy
import importlib
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
connect = importlib.import_module("configure-arr-connect")


def schema():
    return {"implementation": "MediaBrowser", "name": "", "tags": [],
            "onGrab": False, "supportsOnGrab": True,
            "onDownload": False, "supportsOnDownload": True,
            "onRename": False, "supportsOnRename": True,
            "onHealthIssue": False, "supportsOnHealthIssue": True,
            "fields": [{"name": name, "value": None} for name in
                       ("host", "port", "useSsl", "urlBase", "apiKey", "notify", "updateLibrary", "mapFrom", "mapTo")]}


class ArrConnectTests(unittest.TestCase):
    def test_refresh_events_and_paths_without_unsupported_notifications(self):
        row = schema()
        result = connect.payload_for("radarr", row, None, connect.parse_url("http://jellyfin:8096"), "private-key", {})
        self.assertTrue(result["onDownload"])
        self.assertTrue(result["onRename"])
        self.assertFalse(result["onGrab"])
        self.assertFalse(result["onHealthIssue"])
        self.assertFalse(connect.field(result, "notify"))
        self.assertTrue(connect.field(result, "updateLibrary"))
        self.assertEqual(connect.field(result, "mapFrom"), "/movies")
        self.assertEqual(connect.field(result, "mapTo"), "/media/movies")
        self.assertEqual(row, schema())

    def test_existing_name_tags_and_identity_are_preserved(self):
        existing = dict(schema(), id=9, name="My media server", tags=[4])
        before = copy.deepcopy(existing)
        result = connect.payload_for("sonarr", schema(), existing,
                                     connect.parse_url("https://jellyfin:8920/base"), "private-key", {})
        self.assertEqual(result["id"], 9)
        self.assertEqual(result["name"], "My media server")
        self.assertEqual(result["tags"], [4])
        self.assertEqual(existing, before)
        self.assertTrue(connect.field(result, "useSsl"))
        self.assertEqual(connect.field(result, "urlBase"), "/base")

    def test_duplicate_connections_are_rejected(self):
        destination = connect.parse_url("http://jellyfin:8096")
        row = connect.payload_for("radarr", schema(), None, destination, "key", {})
        with self.assertRaises(connect.common.SetupError):
            connect.find_connection([row, row], destination)

    def test_name_collision_does_not_repoint_an_existing_connection(self):
        row = connect.payload_for("radarr", schema(), None, connect.parse_url("http://old:8096"), "key", {})
        with self.assertRaises(connect.common.SetupError):
            connect.find_connection([row], connect.parse_url("http://jellyfin:8096"))

    def test_embedded_credentials_and_invalid_ports_are_rejected(self):
        for url in ("http://user:secret@server", "http://server:invalid", "ftp://server", "http://server/?token=secret"):
            with self.subTest(url=url), self.assertRaises(connect.common.SetupError):
                connect.parse_url(url)

    def test_failed_preflight_does_not_write_connection(self):
        api = Mock()
        api.call.side_effect = [[schema()], [], connect.http.SetupError("Test failed")]
        with self.assertRaises(connect.http.SetupError):
            connect.configure([("radarr", api)], connect.parse_url("http://jellyfin:8096"), "key", {})
        self.assertEqual([c.args[0] for c in api.call.call_args_list],
                         ["notification/schema", "notification", "notification/test"])


if __name__ == "__main__":
    unittest.main()
