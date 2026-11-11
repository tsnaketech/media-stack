"""Exercise media settings against a local fake curl, never a running arr API."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(os.environ.get(
    "ARR_MEDIA_SCRIPT", Path(__file__).resolve().parents[1] / "scripts/configure-arr-media.sh"
))
FAKE_CURL = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
def option(name, default=None):
    return args[args.index(name) + 1] if name in args else default
state = Path(os.environ["MOCK_STATE"])
if option("--request") == "PUT":
    if os.environ.get("MOCK_REJECT") == "1":
        raise SystemExit(22)
    payload = Path(option("--data-binary")[1:]).read_text()
    state.write_text(payload)
    Path(os.environ["MOCK_WRITES"]).write_text("PUT")
body = state.read_text()
out = option("--output")
if out:
    Path(out).write_text(body)
else:
    print(body)
'''


@unittest.skipUnless(shutil.which("jq"), "jq is required")
class MediaSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "curl").write_text(FAKE_CURL)
        (self.root / "curl").chmod(0o755)
        self.state = self.root / "state.json"
        self.initial = {
            "id": 1, "importExtraFiles": False, "extraFileExtensions": "srt",
            "recycleBin": "/trash", "copyUsingReflinks": True,
        }
        self.state.write_text(json.dumps(self.initial))
        (self.root / "config.xml").write_text("<Config><ApiKey>test-key</ApiKey></Config>")
        self.env = dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ["PATH"],
                        ARR_CONFIG_FILE=str(self.root / "config.xml"),
                        ARR_MEDIA_API_URL="http://test.invalid/config/mediamanagement",
                        MOCK_STATE=str(self.state), MOCK_WRITES=str(self.root / "writes"))

    def run_hook(self, **settings):
        return subprocess.run(["bash", str(SCRIPT)], env=dict(self.env, **settings),
                              capture_output=True, text=True, timeout=10)

    def test_enable_and_normalize_extensions_preserves_other_settings(self):
        result = self.run_hook(ARR_IMPORT_EXTRA_FILES="true", ARR_EXTRA_FILE_EXTENSIONS=".SRT, nfo ")
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = dict(self.initial, importExtraFiles=True, extraFileExtensions="srt,nfo")
        self.assertEqual(json.loads(self.state.read_text()), expected)

    def test_existing_values_do_not_trigger_a_write(self):
        result = self.run_hook(ARR_IMPORT_EXTRA_FILES="false", ARR_EXTRA_FILE_EXTENSIONS="srt")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "writes").exists())

    def test_invalid_boolean_is_rejected(self):
        result = self.run_hook(ARR_IMPORT_EXTRA_FILES="maybe")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(self.state.read_text()), self.initial)

    def test_paths_are_not_valid_extensions(self):
        result = self.run_hook(ARR_IMPORT_EXTRA_FILES="true", ARR_EXTRA_FILE_EXTENSIONS="../nfo")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(self.state.read_text()), self.initial)

    def test_api_rejection_leaves_settings_unchanged(self):
        self.env["MOCK_REJECT"] = "1"
        result = self.run_hook(ARR_IMPORT_EXTRA_FILES="true", ARR_EXTRA_FILE_EXTENSIONS="srt,nfo")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(self.state.read_text()), self.initial)


if __name__ == "__main__":
    unittest.main()
