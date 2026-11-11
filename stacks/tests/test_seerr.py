"""Protect existing Seerr accounts/settings and prevent ambiguous configuration."""
import copy
import importlib
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
seerr = importlib.import_module("configure-seerr")


class SeerrSettingsTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "SEERR_APPLICATION_TITLE": "Seerr", "SEERR_APPLICATION_URL": "http://seerr.example.test",
            "SEERR_LOCALE": "fr", "SEERR_DISCOVER_REGION": "FR", "SEERR_STREAMING_REGION": "FR",
            "SEERR_LOCAL_LOGIN": "true", "SEERR_MEDIA_SERVER_LOGIN": "true",
        }
        self.original = {"main": {"apiKey": "private-key", "defaultPermissions": 32},
                         "public": {"initialized": False}, "sessionSecret": "session-secret",
                         "notifications": {"custom": "unchanged"}, "radarr": [], "sonarr": []}
        self.target = {"name": "Radarr", "hostname": "radarr", "port": 7878,
                       "useSsl": False, "baseUrl": "", "is4k": False, "isDefault": True,
                       "activeProfileId": 7, "activeProfileName": "1080p Français"}

    def test_merge_preserves_secrets_permissions_and_setup_state(self):
        source = copy.deepcopy(self.original)
        result = seerr.merge_settings(source, self.env, {"radarr": self.target})
        self.assertEqual(result["main"]["apiKey"], "private-key")
        self.assertEqual(result["sessionSecret"], "session-secret")
        self.assertEqual(result["main"]["defaultPermissions"], 32)
        self.assertEqual(result["public"], {"initialized": False})
        self.assertEqual(result["notifications"], source["notifications"])
        self.assertEqual(source, self.original)

    def test_repeat_merge_does_not_duplicate_servers(self):
        once = seerr.merge_server([], self.target)
        twice = seerr.merge_server(once, self.target)
        self.assertEqual(once, twice)
        self.assertEqual(len(twice), 1)

    def test_custom_fields_and_4k_defaults_survive(self):
        rows = [dict(self.target, id=8, tags=[3], externalUrl="https://films.example.test"),
                dict(self.target, id=9, name="4K", port=7879, is4k=True)]
        merged = seerr.merge_server(rows, dict(self.target, activeProfileId=10))
        self.assertEqual(merged[0]["id"], 8)
        self.assertEqual(merged[0]["tags"], [3])
        self.assertEqual(merged[0]["externalUrl"], "https://films.example.test")
        self.assertTrue(merged[1]["isDefault"])
        self.assertEqual(merged[0]["activeProfileId"], 10)

    def test_ambiguous_servers_are_rejected(self):
        rows = [dict(self.target, id=0), dict(self.target, id=1)]
        with self.assertRaises(seerr.SetupError):
            seerr.merge_server(rows, self.target)

    def test_missing_profile_cannot_be_replaced_with_arbitrary_default(self):
        env = dict(self.env, SEERR_RADARR_URL="http://radarr:7878", SEERR_RADARR_PROFILE="1080p Français",
                   SEERR_RADARR_ROOT_FOLDER="/movies")
        metadata = {"profiles": [{"id": 1, "name": "Any"}], "roots": [{"id": 1, "path": "/movies"}]}
        with self.assertRaises(seerr.SetupError):
            seerr.build_server("radarr", env, metadata, "private-key")

    def test_disabling_both_login_methods_is_rejected(self):
        env = dict(self.env, SEERR_LOCAL_LOGIN="false", SEERR_MEDIA_SERVER_LOGIN="false")
        with self.assertRaises(seerr.SetupError):
            seerr.merge_settings(self.original, env, {})

    def test_credentials_in_url_are_rejected_without_echoing_them(self):
        with self.assertRaises(seerr.SetupError) as error:
            seerr.split_url("https://admin:private-password@example.test", "TEST_URL")
        self.assertNotIn("private-password", str(error.exception))

    def test_media_library_selection_and_setup_are_preserved(self):
        original = copy.deepcopy(self.original)
        original["jellyfin"] = {"ip": "jellyfin", "port": 8096, "useSsl": False, "urlBase": "",
                                "libraries": [{"id": "one", "enabled": True}, {"id": "two", "enabled": False}]}
        env = dict(self.env, SEERR_MEDIA_SERVER_TYPE="jellyfin", SEERR_MEDIA_SERVER_API_KEY="media-secret",
                   SEERR_MEDIA_SERVER_LIBRARY_IDS="")
        media = ({"hostname": "jellyfin", "port": 8096, "useSsl": False, "baseUrl": ""},
                 {"name": "Jellyfin", "id": "server-id", "libraries": [
                     {"id": "one", "name": "Films", "type": "movie"},
                     {"id": "two", "name": "TV", "type": "show"}]})
        result = seerr.merge_settings(original, env, {}, media)
        self.assertEqual([x["enabled"] for x in result["jellyfin"]["libraries"]], [True, False])
        self.assertFalse(result["public"]["initialized"])
        self.assertEqual(result["main"]["mediaServerType"], 2)

    def test_failed_runtime_verification_restores_previous_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            data = root / "shared/data/seerr"
            data.mkdir(parents=True)
            path = data / "settings.json"
            path.write_text(json.dumps(self.original))
            env = dict(self.env, SEERR_SETUP_ENABLED="true", SEERR_CONFIGURE_RADARR="false",
                       SEERR_CONFIGURE_SONARR="false", SEERR_MEDIA_SERVER_URL="")
            resolved = {"services": {"seerr": {"environment": env, "volumes": [
                {"type": "bind", "target": "/app/config", "source": str(data)}]}}}
            readiness = {"initialized": False}
            wrong_runtime = dict(readiness, applicationTitle="unexpected-title")
            with patch.object(seerr, "__file__", str(root / "scripts/configure-seerr.py")), \
                 patch.object(seerr.common, "compose", return_value=resolved), \
                 patch.object(seerr, "run_compose") as compose, \
                 patch.object(seerr, "probe", side_effect=[readiness, wrong_runtime]):
                with self.assertRaises(seerr.SetupError):
                    seerr.main()
            self.assertEqual(json.loads(path.read_text()), self.original)
            self.assertEqual(compose.call_args.args[1:], ("up", "-d", "seerr"))
            self.assertEqual(len(list((data / "backups").glob("env-settings-*.json"))), 1)

    def test_atomic_file_is_private_and_keeps_ownership(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(json.dumps(self.original))
            owner = path.stat()
            seerr.write_settings(path, self.original, owner)
            self.assertEqual(json.loads(path.read_text()), self.original)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual((path.stat().st_uid, path.stat().st_gid), (owner.st_uid, owner.st_gid))
            self.assertFalse(list(Path(directory).glob(".seerr-env-*")))


if __name__ == "__main__":
    unittest.main()
