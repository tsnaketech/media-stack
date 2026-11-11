"""Prevent duplicate registrations and writes after failed connection tests."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location(
    "profilarr_setup", Path(__file__).resolve().parents[1] / "scripts/configure-profilarr.py"
)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class ProfilarrSetupTests(unittest.TestCase):
    def test_matching_url_preserves_existing_connection(self):
        row = {"id": 7, "type": "radarr", "name": "My films", "url": "http://radarr:7878/"}
        client = Mock()
        client.instances.return_value = [row]
        client.call.return_value = {"success": True}
        setup.configure(client, "radarr", "http://radarr:7878", "secret")
        self.assertEqual([call.args[0] for call in client.call.call_args_list], ["/arr/validate"])

    def test_failed_probe_never_creates_instance(self):
        client = Mock()
        client.instances.return_value = []
        client.call.return_value = {"success": False, "error": "private diagnostic"}
        with self.assertRaises(setup.SetupError) as error:
            setup.configure(client, "sonarr", "http://sonarr:8989", "secret")
        self.assertNotIn("private diagnostic", str(error.exception))
        self.assertEqual(client.call.call_count, 1)

    def test_same_name_cannot_redirect_secret_to_different_destination(self):
        rows = [{"id": 1, "name": "Radarr", "type": "radarr", "url": "http://other:7878"}]
        with self.assertRaises(setup.SetupError):
            setup.find_instance(rows, "radarr", "http://radarr:7878")

    def test_duplicate_targets_require_manual_resolution(self):
        row = {"id": 1, "name": "Films", "type": "radarr", "url": "http://radarr:7878"}
        with self.assertRaises(setup.SetupError):
            setup.find_instance([row, dict(row, id=2)], "radarr", row["url"])


if __name__ == "__main__":
    unittest.main()
