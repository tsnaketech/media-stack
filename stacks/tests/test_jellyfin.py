"""Protect Jellyfin libraries and secret-bearing dotenv updates."""
import importlib
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
jellyfin = importlib.import_module("configure-jellyfin")


class JellyfinSetupTests(unittest.TestCase):
    def test_theme_import_update_preserves_custom_rules_inside_old_managed_block(self):
        custom = ':root { --abyss-accent: 100, 160, 255; --abyss-radius: 8px; }'
        source = '/* ABYSS THEME START */\n@import url("/web/ui/abyss.css");\n' + custom + '\n/* ABYSS THEME END */'
        result = jellyfin.abyss_css(source)
        self.assertEqual(result.count('@import url("/web/ui/abyss.css");'), 1)
        self.assertEqual(result.count('@import url("/web/ui/abyss-je.css");'), 1)
        self.assertIn(custom, result.split('/* ABYSS THEME END */', 1)[1])
        self.assertEqual(jellyfin.abyss_css(result), result)

    def test_theme_update_keeps_other_stylesheets(self):
        source = '@import url("https://example.org/font.css");\nbody { color: white; }'
        result = jellyfin.abyss_css(source)
        self.assertIn(source, result)
        self.assertEqual(jellyfin.abyss_css(result), result)

    def test_repository_setup_preserves_other_sources_and_deduplicates(self):
        api = Mock()
        official = {"Name": "Stable", "Url": "https://repo.jellyfin.org/manifest.json", "Enabled": True}
        custom = {"Name": "Personal", "Url": "https://example.org/manifest.json", "Enabled": False}
        existing = [official, custom]
        expected = existing + [{"Name": name, "Url": url, "Enabled": True}
                               for _, name, url in jellyfin.PLUGIN_REPOSITORIES]
        api.call.side_effect = [existing, None, expected, expected]
        jellyfin.ensure_plugin_repositories(api, {})
        jellyfin.ensure_plugin_repositories(api, {})
        writes = [call for call in api.call.call_args_list if len(call.args) > 1]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0].args, ("Repositories", "POST", expected))
        self.assertEqual(existing, [official, custom])

    def test_existing_repository_name_and_disabled_status_are_preserved(self):
        api = Mock()
        key, _, url = jellyfin.PLUGIN_REPOSITORIES[0]
        api.call.return_value = [{"Name": "Chosen name", "Url": url + "/", "Enabled": False}]
        env = {variable: "" for variable, _, _ in jellyfin.PLUGIN_REPOSITORIES}
        env[key] = url
        jellyfin.ensure_plugin_repositories(api, env)
        api.call.assert_called_once_with("Repositories")

    def test_repository_input_is_validated_before_api_writes(self):
        api = Mock()
        with self.assertRaises(jellyfin.common.SetupError):
            jellyfin.ensure_plugin_repositories(api, {"JELLYFIN_ENHANCED_REPOSITORY": "ftp://example.org/manifest"})
        api.call.assert_not_called()

    def test_disabled_or_empty_repository_setup_does_not_call_api(self):
        for env in ({"JELLYFIN_PLUGIN_REPOSITORIES_ENABLED": "false"},
                    {variable: "" for variable, _, _ in jellyfin.PLUGIN_REPOSITORIES}):
            api = Mock()
            jellyfin.ensure_plugin_repositories(api, env)
            api.call.assert_not_called()

    def test_existing_library_is_not_duplicated(self):
        api = Mock()
        api.call.return_value = [{"Name": "Films", "Locations": ["/media/movies"],
                                  "CollectionType": "movies", "ItemId": "library-id"}]
        self.assertEqual(jellyfin.ensure_library(api, "Films", "movies", "/media/movies"), "library-id")
        api.call.assert_called_once_with("Library/VirtualFolders")

    def test_existing_library_with_different_path_is_not_replaced(self):
        api = Mock()
        api.call.return_value = [{"Name": "Films", "Locations": ["/other"],
                                  "CollectionType": "movies", "ItemId": "library-id"}]
        with self.assertRaises(jellyfin.common.SetupError):
            jellyfin.ensure_library(api, "Films", "movies", "/media/movies")
        api.call.assert_called_once()

    def test_restricted_creation_preserves_existing_access_without_granting_new_library(self):
        api = Mock()
        api.call.side_effect = [
            [{"Name": "Films", "ItemId": "movies-id"}],
            [{"Id": "admin", "Policy": {"IsAdministrator": True, "EnableAllFolders": True}},
             {"Id": "viewer", "Policy": {"IsAdministrator": False, "EnableAllFolders": True,
                                           "EnableMediaPlayback": True}},
             {"Id": "restricted", "Policy": {"EnableAllFolders": False, "EnabledFolders": []}}],
            None]
        with patch.object(jellyfin, "ensure_library", return_value="restricted-id") as ensure:
            self.assertEqual(jellyfin.ensure_restricted_library(api, "Private", "movies", "/media/restricted"), "restricted-id")
        ensure.assert_called_once_with(api, "Private", "movies", "/media/restricted")
        policies = [c for c in api.call.call_args_list if c.args[0].endswith("/Policy")]
        self.assertEqual(len(policies), 1)
        self.assertEqual(policies[0].args[0], "Users/viewer/Policy")
        self.assertFalse(policies[0].args[2]["EnableAllFolders"])
        self.assertEqual(policies[0].args[2]["EnabledFolders"], ["movies-id"])
        self.assertTrue(policies[0].args[2]["EnableMediaPlayback"])

    def test_existing_restricted_library_does_not_overwrite_manual_access(self):
        api = Mock()
        api.call.return_value = [{"Name": "Private", "ItemId": "restricted-id"}]
        with patch.object(jellyfin, "ensure_library", return_value="restricted-id"):
            jellyfin.ensure_restricted_library(api, "Private", "movies", "/media/restricted")
        api.call.assert_called_once_with("Library/VirtualFolders")

    def test_generated_env_preserves_other_secrets_and_csv_quotes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            prefix = '# Keep this comment\nOTHER_PASSWORD=\'existing-secret\'\nPROFILARR_PROFILES=\'"1080p Français","2160p Français"\'\n'
            path.write_text(prefix + "JELLYFIN_API_KEY=''\n")
            jellyfin.update_env(path, {"JELLYFIN_API_KEY": "private-token", "SEERR_MEDIA_SERVER_URL": "http://jellyfin:8096"})
            self.assertTrue(path.read_text().startswith(prefix))
            self.assertEqual(path.read_text().count("JELLYFIN_API_KEY="), 1)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            previous = path.stat().st_mtime_ns
            jellyfin.update_env(path, {"JELLYFIN_API_KEY": "private-token", "SEERR_MEDIA_SERVER_URL": "http://jellyfin:8096"})
            self.assertEqual(previous, path.stat().st_mtime_ns)
            self.assertFalse(list(Path(directory).glob(".env.jellyfin-*")))

    def test_invalid_generated_value_does_not_change_env(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("SECRET='preserve'\n")
            with self.assertRaises(jellyfin.common.SetupError):
                jellyfin.update_env(path, {"JELLYFIN_API_KEY": "invalid\nINJECTED=true"})
            self.assertEqual(path.read_text(), "SECRET='preserve'\n")


if __name__ == "__main__":
    unittest.main()
