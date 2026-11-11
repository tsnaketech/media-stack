"""Verify optional external stacks never leak into an independent checkout."""
import json
import os
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import stack_extensions as extensions


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'project'
        self.root = self.project / 'stacks'
        self.root.mkdir(parents=True)
        self.private = Path(self.temp.name) / 'deployment'
        self.private.mkdir()
        self.manifest = {
            'stacks': {'sample': 'stacks/sample'},
            'compose_overrides': {'shared': ['overrides/shared.yml']},
            'env_files': {'shared': ['settings.env']},
        }
        (self.private / 'extensions.json').write_text(json.dumps(self.manifest))

    def test_clean_checkout_has_no_extensions(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(extensions.settings(self.root), {})
            self.assertEqual(extensions.stack_directory(self.root, 'shared'), self.root / 'shared')

    def test_explicit_empty_setting_disables_local_deployment(self):
        (self.project / '.env').write_text(f'STACK_EXTENSIONS_DIR={self.private}\n')
        with patch.dict(os.environ, {'STACK_EXTENSIONS_DIR': ''}):
            self.assertEqual(extensions.settings(self.root), {})

    def test_root_env_loads_stack_and_layers_env_before_overrides(self):
        (self.project / '.env').write_text(f'STACK_EXTENSIONS_DIR={self.private}\n')
        base = self.root / 'shared'
        base.mkdir()
        (base / '.env').touch()
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(extensions.stack_directory(self.root, 'sample'), self.private / 'stacks/sample')
            command = extensions.compose_command(self.root, 'shared', ['up', '-d'])
        self.assertEqual(command, ['docker', 'compose', '--project-directory', str(base),
                                  '--env-file', str(self.project / '.env'),
                                  '--env-file', str(base / '.env'), '--env-file', str(self.private / 'settings.env'),
                                  '-f', str(base / 'docker-compose.yml'), '-f', str(self.private / 'overrides/shared.yml'),
                                  'up', '-d'])

    def test_bad_extension_directory_fails_instead_of_ignoring_it(self):
        (self.private / 'incomplete').mkdir()
        for value in ('relative/path', str(self.private / 'incomplete')):
            with self.subTest(value=value), patch.dict(os.environ, {'STACK_EXTENSIONS_DIR': value}):
                with self.assertRaises(ValueError):
                    extensions.settings(self.root)

    def test_infrastructure_resolves_from_project_root(self):
        folder = self.project / 'dashboard'
        folder.mkdir()
        (folder / 'docker-compose.yml').touch()
        with patch.dict(os.environ, {'STACK_EXTENSIONS_DIR': ''}):
            self.assertEqual(extensions.stack_directory(self.root, 'dashboard'), folder)

    def test_common_management_export_stays_with_checkout_and_preserves_secrets(self):
        self.manifest['management_exports'] = ['shared']
        (self.private / 'extensions.json').write_text(json.dumps(self.manifest))
        model = {'name': 'sample', 'services': {'player': {'environment': {'TOKEN': 'private-token'}}}}
        with patch.dict(os.environ, {'STACK_EXTENSIONS_DIR': str(self.private)}):
            target = extensions.store_management_model(self.root, 'shared', model)
            self.assertEqual(json.loads(target.read_text()), model)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertEqual(target, self.project / "runtime/arcane/shared/docker-compose.yml")
            self.assertIsNone(extensions.store_management_model(self.root, 'other', model))

    def test_external_stack_export_stays_outside_checkout(self):
        self.manifest['management_exports'] = ['sample']
        (self.private / 'extensions.json').write_text(json.dumps(self.manifest))
        with patch.dict(os.environ, {'STACK_EXTENSIONS_DIR': str(self.private)}):
            target = extensions.store_management_model(self.root, 'sample', {'services': {}})
        self.assertEqual(target, self.private / 'runtime/arcane/sample/docker-compose.yml')
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_missing_optional_directory_uses_common_configuration(self):
        with patch.dict(os.environ, {'STACK_EXTENSIONS_DIR': str(self.private / 'absent')}):
            self.assertEqual(extensions.settings(self.root), {})
            command = extensions.compose_command(self.root, 'shared', ['config', '--quiet'])
            self.assertEqual(command.count('-f'), 1)
            self.assertIn(str(self.root / 'shared/docker-compose.yml'), command)

    def test_list_without_extensions_produces_no_blank_stack(self):
        launcher = Path(extensions.__file__).with_name('stack-compose.py')
        result = subprocess.run([sys.executable, str(launcher), '--list'],
                                env=dict(os.environ, STACK_EXTENSIONS_DIR=''),
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, '')

    def test_shell_management_rejects_invalid_extension_setting_before_docker(self):
        launcher = Path(extensions.__file__).with_name('stacks.sh')
        result = subprocess.run(['bash', str(launcher), 'validate'],
                                env=dict(os.environ, STACK_EXTENSIONS_DIR='relative/path'),
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('must be absolute', result.stderr)

    def test_new_runtime_mount_is_prepared_without_changing_existing_paths(self):
        target = self.project / 'runtime/dashboard'
        existing = self.project / 'runtime/existing'
        existing.mkdir(parents=True)
        existing.chmod(0o755)
        model = {'services': {'dashboard': {'user': '1234:1235', 'volumes': [
            {'type': 'bind', 'source': str(target), 'target': '/app/config'},
            {'type': 'bind', 'source': str(existing), 'target': '/other'}]}}}
        with patch.dict(os.environ, {'STACK_EXTENSIONS_DIR': ''}), \
             patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, json.dumps(model))), \
             patch.object(extensions.os, 'geteuid', return_value=0), \
             patch.object(extensions.os, 'chown') as chown:
            extensions.prepare_runtime_mounts(self.root, 'dashboard')
        self.assertTrue(target.is_dir())
        chown.assert_called_once_with(target, 1234, 1235)
        self.assertEqual(existing.stat().st_mode & 0o777, 0o755)

    def test_common_exports_can_be_refreshed_when_extensions_are_absent(self):
        folder = self.root / 'shared'
        folder.mkdir()
        (folder / 'docker-compose.yml').touch()
        with patch.dict(os.environ, {'STACK_EXTENSIONS_DIR': str(self.private / 'absent')}):
            target = extensions.store_management_model(self.root, 'shared', {'services': {}})
        self.assertEqual(target, self.project / 'runtime/arcane/shared/docker-compose.yml')
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
