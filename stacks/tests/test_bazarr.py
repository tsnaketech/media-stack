"""Preserve other Bazarr language profiles and encode multi-value form settings."""
import copy
import importlib
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock
import urllib.parse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
bazarr = importlib.import_module("configure-bazarr")


class BazarrSetupTests(unittest.TestCase):
    def test_existing_languages_and_profiles_are_preserved(self):
        original = [{"profileId": 3, "name": "English", "items": [{"language": "en"}]}]
        before = copy.deepcopy(original)
        profile_id, payload = bazarr.profile_settings(original, [{"code2": "en", "enabled": True}], "Français")
        self.assertEqual(profile_id, 4)
        self.assertEqual(payload["languages-enabled"], ["en", "fr"])
        import json
        self.assertEqual(json.loads(payload["languages-profiles"])[0], before[0])
        self.assertEqual(original, before)

    def test_existing_french_profile_is_not_duplicated(self):
        original = [{"profileId": 7, "name": "Français", "items": [{"language": "fr"}]}]
        profile_id, payload = bazarr.profile_settings(original, [], "Français")
        self.assertEqual(profile_id, 7)
        import json
        self.assertEqual(len(json.loads(payload["languages-profiles"])), 1)

    def test_conflicting_profile_name_is_rejected(self):
        original = [{"profileId": 7, "name": "Français", "items": [{"language": "en"}]}]
        with self.assertRaises(bazarr.common.SetupError):
            bazarr.profile_settings(original, [], "Français")

    def test_connection_url_cannot_embed_credentials(self):
        with self.assertRaises(bazarr.common.SetupError) as error:
            bazarr.connection_fields("radarr", "http://admin:private-password@example.test", "key")
        self.assertNotIn("private-password", str(error.exception))

    def test_form_lists_are_sent_as_repeated_parameters(self):
        api = bazarr.http.API("http://example.test")
        api.opener = MagicMock()
        api.opener.open.return_value.__enter__.return_value.read.return_value = b""
        api.call("settings", "POST", {"languages-enabled": ["en", "fr"], "settings-auth-username": "admin"}, form=True)
        request = api.opener.open.call_args.args[0]
        payload = urllib.parse.parse_qs(request.data.decode())
        self.assertEqual(payload["languages-enabled"], ["en", "fr"])
        self.assertEqual(payload["settings-auth-username"], ["admin"])


if __name__ == "__main__":
    unittest.main()
