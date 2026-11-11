"""Protect existing qui accounts and qBittorrent connections during setup."""
import importlib
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
qui = importlib.import_module("configure-qui")
joal = importlib.import_module("prepare-joal")


class QuiSetupTests(unittest.TestCase):
    def setUp(self):
        self.env = {"QUI_USERNAME": "admin", "QUI_PASSWORD": "example-long-password",
                    "QUI_QBITTORRENT_URL": "http://qbittorrent:8080", "QUI_INSTANCE_NAME": "qBittorrent"}
        self.credentials = {"username": "qbit-user", "password": "private-qbit-password"}

    def test_existing_account_and_instance_are_not_recreated(self):
        api = Mock()
        api.call.side_effect = [{"setupRequired": False}, {}, {"username": "admin"},
                                [{"id": 7, "host": "http://qbittorrent:8080/", "name": "Existing"}],
                                {"connected": True}]
        qui.configure(api, self.env, self.credentials)
        paths = [call.args[0] for call in api.call.call_args_list]
        self.assertNotIn("api/auth/setup", paths)
        self.assertEqual(paths[-1], "api/instances/7/test")
        self.assertEqual(sum(path == "api/instances" for path in paths), 1)

    def test_new_instance_has_no_local_filesystem_access(self):
        api = Mock()
        api.call.side_effect = [{"setupRequired": True}, {}, {}, {"username": "admin"}, [],
                                {"id": 1}, {"connected": True}]
        qui.configure(api, self.env, self.credentials)
        payload = next(call.args[2] for call in api.call.call_args_list if call.args[:2] == ("api/instances", "POST"))
        self.assertFalse(payload["hasLocalFilesystemAccess"])
        self.assertEqual(payload["host"], self.env["QUI_QBITTORRENT_URL"])

    def test_name_collision_does_not_repoint_existing_client(self):
        with self.assertRaises(qui.common.SetupError):
            qui.find_instance([{"id": 1, "name": "qBittorrent", "host": "http://other:8080"}],
                              "http://qbittorrent:8080", "qBittorrent")

    def test_unknown_existing_password_cannot_reset_account(self):
        api = Mock()
        api.call.side_effect = [{"setupRequired": False}, qui.http.SetupError("HTTP 401")]
        with self.assertRaises(qui.http.SetupError):
            qui.configure(api, self.env, self.credentials)
        self.assertEqual([c.args[0] for c in api.call.call_args_list], ["api/auth/check-setup", "api/auth/login"])

    def test_arr_existing_integration_is_preserved_without_reading_key(self):
        api = Mock()
        api.call.side_effect = [[{"id": 3, "type": "sonarr", "name": "Custom", "base_url": "http://sonarr:8989/"}],
                                {"success": True}]
        with patch.object(qui.common, "api_key") as key:
            qui.configure_arr(api, Path("/unused"), {"QUI_RADARR_ENABLED": "false"})
        key.assert_not_called()
        self.assertEqual([c.args[0] for c in api.call.call_args_list],
                         ["api/arr/instances", "api/arr/instances/3/test"])

    def test_arr_failed_preflight_does_not_create_integration(self):
        api = Mock()
        api.call.side_effect = [[], {"success": False}]
        with patch.object(qui.common, "api_key", return_value="private-key"):
            with self.assertRaises(qui.common.SetupError):
                qui.configure_arr(api, Path("/unused"), {"QUI_RADARR_ENABLED": "false"})
        self.assertFalse(any(c.args[:2] == ("api/arr/instances", "POST")
                             for c in api.call.call_args_list))

    def test_arr_custom_destination_needs_explicit_key(self):
        api = Mock()
        api.call.return_value = []
        with patch.object(qui.common, "api_key") as key:
            with self.assertRaises(qui.common.SetupError):
                qui.configure_arr(api, Path("/unused"), {"QUI_RADARR_ENABLED": "false",
                                  "QUI_SONARR_URL": "http://other:8989"})
        key.assert_not_called()

    def test_joal_archive_cannot_escape_client_directory(self):
        with self.assertRaises(joal.common.SetupError):
            joal.release_path("clients/../../outside")

    def test_joal_release_does_not_import_torrents_or_binaries(self):
        self.assertIsNone(joal.release_path("joal/torrents/example.torrent"))
        self.assertIsNone(joal.release_path("joal/joal.jar"))
        self.assertEqual(joal.release_path("joal/clients/example.client"), Path("clients/example.client"))


if __name__ == "__main__":
    unittest.main()
