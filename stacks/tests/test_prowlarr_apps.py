"""Protect Prowlarr application identity and custom settings during provisioning."""
import copy
import importlib
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
setup = importlib.import_module("configure-prowlarr-apps")


def application():
    return {"id": 7, "name": "My Sonarr", "implementation": "Sonarr", "tags": [12],
            "syncLevel": "addOnly", "fields": [
                {"name": "baseUrl", "value": "http://sonarr:8989"},
                {"name": "prowlarrUrl", "value": "http://prowlarr:9696"},
                {"name": "apiKey", "value": "old-private-key"},
                {"name": "syncCategories", "value": [5000, 5040]},
                {"name": "animeSyncCategories", "value": [5070]}]}


class ProwlarrApplicationsTests(unittest.TestCase):
    def test_updates_preserve_identity_tags_and_custom_categories(self):
        row = application()
        before = copy.deepcopy(row)
        payload = setup.application_payload({}, row, "http://sonarr:8989", "http://prowlarr:9696",
                                            "new-private-key", "fullSync")
        self.assertEqual(row, before)
        self.assertEqual(payload["id"], 7)
        self.assertEqual(payload["tags"], [12])
        self.assertEqual(payload["name"], "My Sonarr")
        self.assertEqual(setup.field(payload, "syncCategories"), [5000, 5040])
        self.assertEqual(setup.field(payload, "animeSyncCategories"), [5070])
        self.assertEqual(setup.field(payload, "apiKey"), "new-private-key")
        self.assertEqual(payload["syncLevel"], "fullSync")

    def test_duplicate_destinations_are_rejected(self):
        with self.assertRaises(setup.common.SetupError):
            setup.find_application([application(), application()], "Sonarr", "http://sonarr:8989")

    def test_name_collision_cannot_repoint_a_saved_application(self):
        row = application()
        row["name"] = "Sonarr"
        with self.assertRaises(setup.common.SetupError):
            setup.find_application([row], "Sonarr", "http://another:8989")

    def test_custom_destination_cannot_receive_local_key_implicitly(self):
        api = Mock()
        api.call.side_effect = [[], []]
        with patch.object(setup.common, "api_key") as key:
            with self.assertRaises(setup.common.SetupError):
                setup.configure(api, Path("/unused"), {"PROWLARR_APP_LIDARR_URL": "http://other:8686"})
        key.assert_not_called()

    def test_failed_connection_test_does_not_modify_any_application(self):
        api = Mock()
        row = application()
        api.call.side_effect = [[row], [row], setup.http.SetupError("Connection test failed")]
        env = {f"PROWLARR_APP_{app}_ENABLED": "false" for app in ("LIDARR", "RADARR")}
        with patch.object(setup.common, "api_key", return_value="private-key"):
            with self.assertRaises(setup.http.SetupError):
                setup.configure(api, Path("/unused"), env)
        self.assertFalse(any(call.args[1:2] == ("PUT",) for call in api.call.call_args_list))
        self.assertFalse(any(call.args[:2] == ("api/v1/applications", "POST")
                             for call in api.call.call_args_list))

    def test_rerun_preserves_existing_entry_without_writes(self):
        api = Mock()
        row = application()
        api.call.side_effect = [[row], [row], None, row, {"id": 99}, {"status": "completed"}]
        env = {f"PROWLARR_APP_{app}_ENABLED": "false" for app in ("LIDARR", "RADARR")}
        env["PROWLARR_APPS_SYNC_LEVEL"] = "addOnly"
        with patch.object(setup.common, "api_key", return_value="old-private-key"):
            setup.configure(api, Path("/unused"), env)
        self.assertFalse(any(call.args[1:2] == ("PUT",) for call in api.call.call_args_list))
        self.assertFalse(any(call.args[:2] == ("api/v1/applications", "POST")
                             for call in api.call.call_args_list))

    def test_invalid_sync_level_is_rejected(self):
        with self.assertRaises(setup.common.SetupError):
            setup.application_payload({}, application(), "http://sonarr:8989", "http://prowlarr:9696", "key", "full")


if __name__ == "__main__":
    unittest.main()
