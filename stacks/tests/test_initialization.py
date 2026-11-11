"""Ensure first-run account generation never resets an existing deployment."""
import base64
import configparser
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
init = importlib.import_module("initialize")


class InitializationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "download").mkdir()
        (self.root / "download/.env").write_text("QBITTORRENT_INIT_USERNAME=admin\nQBITTORRENT_INIT_PASSWORD=''\n")
        self.config_dir = self.root / "download/data/qbittorrent"
        self.config_dir.mkdir(parents=True)
        self.service = {"environment": {"PUID": str(os.geteuid()), "PGID": str(os.getegid())},
                        "volumes": [{"source": str(self.config_dir), "target": "/config"}]}

    def test_first_run_password_hash_matches_private_credentials(self):
        init.seed_qbittorrent(self.root, self.service)
        credentials = self.root / "download/.qbittorrent-credentials.json"
        account = json.loads(credentials.read_text())
        self.assertGreaterEqual(len(account["password"]), 12)
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str
        config = self.config_dir / "qBittorrent/qBittorrent.conf"
        parser.read(config)
        stored = parser["Preferences"]["WebUI\\Password_PBKDF2"].strip('"')
        salt, digest = stored[len("@ByteArray("):-1].split(":")
        self.assertEqual(hashlib.pbkdf2_hmac("sha512", account["password"].encode(), base64.b64decode(salt), 100000),
                         base64.b64decode(digest))
        self.assertNotIn(account["password"], config.read_text())
        self.assertEqual(credentials.stat().st_mode & 0o777, 0o600)
        before = (credentials.read_bytes(), config.read_bytes())
        init.seed_qbittorrent(self.root, self.service)
        self.assertEqual(before, (credentials.read_bytes(), config.read_bytes()))

    def test_existing_config_without_credentials_is_never_reset(self):
        path = self.config_dir / "qBittorrent/qBittorrent.conf"
        path.parent.mkdir()
        path.write_text("existing configuration")
        with self.assertRaises(init.common.SetupError):
            init.seed_qbittorrent(self.root, self.service)
        self.assertEqual(path.read_text(), "existing configuration")
        self.assertFalse((self.root / "download/.qbittorrent-credentials.json").exists())

    def test_invalid_initial_password_does_not_create_account(self):
        (self.root / "download/.env").write_text("QBITTORRENT_INIT_PASSWORD=short\n")
        with self.assertRaises(init.common.SetupError):
            init.seed_qbittorrent(self.root, self.service)
        self.assertFalse((self.root / "download/.qbittorrent-credentials.json").exists())

    def test_explicit_storage_updates_do_not_change_container_paths(self):
        values = init.storage_values("shared", Path("/srv/media"), Path("/srv/downloads"))
        self.assertEqual(values["JELLYFIN_MOVIES_DIR"], "/srv/media/movies")
        self.assertNotIn("ARR_ROOT_FOLDER", values)
        values = init.storage_values("download", Path("/srv/media"), Path("/srv/downloads"))
        self.assertEqual(values["METUBE_VIDEO_DIR"], "/srv/downloads/youtube/videos")
        self.assertEqual(values["SHARED_DOWNLOADS_DIR"], "/srv/downloads")

    def test_private_file_creation_cannot_overwrite_existing_credentials(self):
        path = self.root / "private.json"
        path.write_text("preserve")
        with self.assertRaises(FileExistsError):
            init.private_json(path, {"password": "new"})
        self.assertEqual(path.read_text(), "preserve")

    def test_profile_database_disabled_by_user_is_not_reactivated(self):
        client = Mock()
        client.call.return_value = [{"id": 1, "name": "Dictionarry", "enabled": 0}]
        init.common.ensure_database(client, {"PROFILARR_FRENCH_PROFILES_ENABLED": "true"})
        client.call.assert_called_once_with("/api/v1/databases")
        client.page.assert_not_called()

    def test_preflight_reports_missing_vpn_before_starting_any_container(self):
        configs = {"vpn": {"services": {"gluetun": {
            "environment": {"VPN_TYPE": "wireguard", "WIREGUARD_PRIVATE_KEY": ""}}}}}
        with patch.object(init, "run"), patch.object(init.subprocess, "check_output", return_value="5.7.0"), \
             patch.object(init.subprocess, "run", side_effect=lambda args, **kwargs: Mock(returncode=0 if args[1] == "info" else 1, stdout="")) as execute, \
             patch.object(Path, "is_char_device", return_value=False):
            with self.assertRaises(init.common.SetupError) as error:
                init.preflight(self.root, configs)
        self.assertIn("WIREGUARD_PRIVATE_KEY", str(error.exception))
        self.assertIn("/dev/net/tun", str(error.exception))
        self.assertFalse(any("up" in call.args[0] for call in execute.call_args_list))

    def test_prepare_does_not_generate_password_for_an_existing_arr_account(self):
        for stack in init.STAGES:
            folder = self.root / stack
            folder.mkdir(exist_ok=True)
            (folder / ".env.example").write_text("ARR_AUTH_PASSWORD=''\n")
        movie = self.root / "movie"
        (movie / ".env").write_text("ARR_AUTH_USERNAME=existing\nARR_AUTH_PASSWORD=''\n")
        data = movie / "data/radarr"
        data.mkdir(parents=True)
        (data / "config.xml").write_text("preserved application data")
        target = self.root / "downloads"
        target.mkdir()
        self.service["volumes"].append({"target": "/downloads", "source": str(target)})
        configs = {s: {"services": {}} for s in init.STAGES}
        configs["download"]["services"]["qbittorrent"] = self.service
        with patch.object(init.shutil, "which", return_value="/test/docker"), \
             patch.object(init.common, "compose", side_effect=lambda root, stack: configs[stack]):
            init.prepare(self.root)
        self.assertEqual(init.raw_values(movie / ".env")["ARR_AUTH_PASSWORD"], "")
        self.assertEqual((data / "config.xml").read_text(), "preserved application data")

    def test_qbit_headers_support_remapped_ports_without_disabling_validation(self):
        helper = importlib.import_module("configure-download-clients")
        self.assertEqual(helper.qbit_headers("http://127.0.0.1:32000"),
                         {"Host": "127.0.0.1", "Referer": "http://127.0.0.1"})
        self.assertEqual(helper.qbit_headers("http://[::1]:32000")["Host"], "[::1]")

    def test_profile_page_error_becomes_safe_diagnostic(self):
        client = init.common.Client("http://unused", "http://unused")
        with patch.object(client, "call", return_value={"nodes": [{"type": "error", "error": {"message": "private context"}}]}):
            with self.assertRaises(init.common.SetupError) as error:
                client.page("/custom-formats/1")
        self.assertNotIn("private context", str(error.exception))


if __name__ == "__main__":
    unittest.main()
