import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


boot = load("reconcile-vpn")
installer = load("install-vpn-boot")


class BootTests(unittest.TestCase):
    def test_missing_mount_blocks_existing_directory(self):
        models = (({"client": {"volumes": [{"type": "bind", "source": "/downloads/music"}]}}, ("client",)),)
        with patch.object(boot.os.path, "ismount", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "mount unavailable"):
                boot.validate_storage(models)

    def test_custom_storage_must_exist(self):
        with tempfile.TemporaryDirectory() as temporary:
            volume = {"type": "bind", "source": temporary}
            models = (({"client": {"volumes": [volume]}}, ("client",)),)
            boot.validate_storage(models)
            volume["source"] += "/missing"
            with self.assertRaisesRegex(RuntimeError, "bind source unavailable"):
                boot.validate_storage(models)

    def test_rendered_unit(self):
        unit = installer.render_unit(SCRIPTS.parents[1])
        for expected in ("PartOf=docker.service", "After=docker.service network-online.target",
                         "Restart=on-failure", "WantedBy=docker.service", "Type=oneshot"):
            self.assertIn(expected, unit)
        self.assertNotIn("@PROJECT_ROOT@", unit)
        self.assertIn(f"WorkingDirectory={SCRIPTS.parents[1]}\n", unit)
        self.assertEqual(installer.unit_quote('/a b/%c/$d'), '"/a b/%%c/$d"')
        self.assertEqual(installer.unit_quote('/a/$d', command=True), '"/a/$$d"')
        with self.assertRaises(ValueError):
            installer.unit_quote('/a\nb')

    def run_helper(self, mismatch=False, broken=False, unhealthy=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / "stacks/scripts"
            scripts.mkdir(parents=True)
            helper = scripts / "vpn-up.sh"
            helper.write_text((SCRIPTS / "vpn-up.sh").read_text())
            fake = root / "bin"
            fake.mkdir()
            stub = '''#!PYTHON
import os, pathlib, sys
root = pathlib.Path(os.environ["FAKE_ROOT"])
args = sys.argv[1:]
with (root / "calls").open("a") as log:
    log.write(pathlib.Path(sys.argv[0]).name + " " + " ".join(args) + "\\n")
if pathlib.Path(sys.argv[0]).name == "docker":
    if args[0] == "inspect":
        print("unhealthy" if os.environ["UNHEALTHY"] == "1" else "healthy")
    elif args[0] == "exec":
        mismatch = args[1] == "qbittorrent" and os.environ["MISMATCH"] == "1" and not (root / "fixed").exists()
        print("net:[2]" if mismatch else "net:[1]")
elif "--force-recreate" in args and os.environ["BROKEN"] != "1":
    (root / "fixed").touch()
'''.replace("PYTHON", sys.executable)
            for name in ("docker", "python3"):
                file = fake / name
                file.write_text(stub)
                file.chmod(0o755)
            env = dict(os.environ, PATH=f"{fake}:{os.environ['PATH']}", FAKE_ROOT=str(root),
                       MISMATCH=str(int(mismatch)), BROKEN=str(int(broken)), UNHEALTHY=str(int(unhealthy)))
            result = subprocess.run(["bash", str(helper)], env=env, text=True, capture_output=True)
            return result, (root / "calls").read_text()

    def test_healthy_clients_not_recreated(self):
        result, calls = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("--force-recreate", calls)

    def test_only_mismatched_client_recreated(self):
        result, calls = self.run_helper(mismatch=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        recreated = [line for line in calls.splitlines() if "--force-recreate" in line]
        self.assertEqual(len(recreated), 1)
        self.assertTrue(recreated[0].endswith("qbittorrent"))

    def test_failed_reconnection_is_reported(self):
        result, _ = self.run_helper(mismatch=True, broken=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("namespace verification failed", result.stderr)

    def test_unhealthy_vpn_is_reported(self):
        result, _ = self.run_helper(unhealthy=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no longer healthy", result.stderr)
