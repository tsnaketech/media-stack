"""Ensure TMDB provisioning never resets unrelated settings or logs tokens."""
import importlib
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
setup = importlib.import_module("configure-profilarr")


def settings():
    return {
        "logSettings": {"retention_days": 17, "min_level": "WARN", "enabled": True,
                        "file_logging": False, "console_logging": True},
        "backupSettings": {"schedule": "0 4 * * *", "retention_days": 23, "enabled": True},
        "generalSettings": {"date_format": "dmy", "landing_page": "arr",
                            "apply_default_delay_profiles": False, "fail_on_referenced_delete": True,
                            "sync_prompt_enabled": False},
        "aiSettings": {"enabled": True, "api_url": "http://local-ai/v1", "model": "existing-model"},
        "tmdbSettings": {"hasApiKey": True},
    }


class TMDBSettingsTests(unittest.TestCase):
    def test_blank_token_preserves_existing_token_without_requests(self):
        client = Mock()
        setup.configure_tmdb(client, "  ")
        client.page.assert_not_called()
        client.call.assert_not_called()

    def test_existing_general_settings_are_preserved(self):
        payload = setup.tmdb_settings_payload(settings(), "private-token")
        self.assertEqual(payload["log_retention_days"], 17)
        self.assertEqual(payload["log_min_level"], "WARN")
        self.assertEqual(payload["backup_schedule"], "0 4 * * *")
        self.assertEqual(payload["backup_retention_days"], 23)
        self.assertEqual(payload["date_format"], "dmy")
        self.assertEqual(payload["landing_page"], "arr")
        self.assertEqual(payload["ai_model"], "existing-model")
        self.assertNotIn("ai_api_key", payload)
        self.assertEqual(payload["backup_enabled"], "on")
        self.assertEqual(payload["fail_on_referenced_delete"], "on")
        self.assertNotIn("log_file_logging", payload)
        self.assertNotIn("arr_apply_default_delay_profiles", payload)
        self.assertNotIn("sync_prompt_enabled", payload)

    def test_rejected_token_does_not_save_settings(self):
        client = Mock()
        client.page.return_value = settings()
        client.call.return_value = {"success": False}
        with self.assertRaises(setup.SetupError):
            setup.configure_tmdb(client, "private-token")
        self.assertEqual(client.call.call_count, 1)
        self.assertEqual(client.call.call_args.args[0], "/tmdb/validate")

    def test_missing_schema_does_not_save_or_validate(self):
        client = Mock()
        client.page.return_value = {}
        with self.assertRaises(setup.SetupError):
            setup.configure_tmdb(client, "private-token")
        client.call.assert_not_called()

    def test_save_is_validated_and_secret_is_not_printed(self):
        client = Mock()
        client.page.side_effect = [settings(), {"tmdbSettings": {"hasApiKey": True}}]
        client.call.side_effect = [{"success": True}, {"type": "success"}, {"success": True}]
        with patch("builtins.print") as output:
            setup.configure_tmdb(client, "Bearer private-token")
        self.assertEqual(client.call.call_args_list[0].args[1], {"apiKey": "private-token"})
        self.assertEqual(client.call.call_args_list[1].args[0], "/settings/general?/save")
        self.assertEqual(client.call.call_args_list[2].args, ("/tmdb/validate", {}))
        self.assertNotIn("private-token", str(output.call_args_list))


if __name__ == "__main__":
    unittest.main()
