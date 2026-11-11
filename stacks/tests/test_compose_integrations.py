"""Ensure configuration helpers operate on the effective deployment model."""
import importlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
seerr = importlib.import_module('configure-seerr')
bazarr = importlib.import_module('configure-bazarr')
vpn = importlib.import_module('configure-qbittorrent-vpn')
common = importlib.import_module('configure-profilarr')
http = importlib.import_module('configure-download-clients')
initialize = importlib.import_module('initialize')


class ComposeIntegrationTests(unittest.TestCase):
    def test_seerr_lifecycle_uses_the_effective_compose_command(self):
        root = Path('/checkout/stacks')
        command = ['docker', 'compose', '-f', '/external/merged.yml', 'up', '-d', 'seerr']
        with patch.object(common.extensions, 'compose_command', return_value=command) as resolve, \
             patch.object(seerr.subprocess, 'run') as run:
            seerr.run_compose(root, 'up', '-d', 'seerr')
        resolve.assert_called_once_with(root, 'shared', ('up', '-d', 'seerr'))
        self.assertEqual(run.call_args.args[0], command)

    def test_seerr_probe_and_bazarr_key_use_extension_aware_exec(self):
        root = Path('/checkout/stacks')
        command = ['docker', 'compose', '-f', '/external/merged.yml', 'exec']
        with patch.object(common.extensions, 'compose_command', return_value=command) as resolve, \
             patch.object(seerr.subprocess, 'run', return_value=subprocess.CompletedProcess(command, 0, '{}')) as run:
            self.assertEqual(seerr.probe(root, {'kind': 'public', 'url': 'http://example'}), {})
            self.assertEqual(run.call_args.args[0], command)
            self.assertEqual(resolve.call_args.args[2][:3], ['exec', '-T', 'seerr'])
        with patch.object(common.extensions, 'compose_command', return_value=command) as resolve, \
             patch.object(bazarr.subprocess, 'run', return_value=subprocess.CompletedProcess(command, 0, 'test-key\n')) as run:
            self.assertEqual(bazarr.api_key(root), 'test-key')
            self.assertEqual(run.call_args.args[0], command)
            self.assertEqual(resolve.call_args.args[2][:3], ['exec', '-T', 'bazarr'])

    def test_vpn_helper_uses_a_remapped_published_port(self):
        config = {'services': {'gluetun': {'ports': [
            {'target': 8080, 'published': '18080', 'host_ip': '0.0.0.0'}]}}}
        desired = {'current_network_interface': 'tun0', 'current_interface_address': '',
                   'upnp': False, 'random_port': False}
        api = Mock()
        api.call.side_effect = [None, desired, desired]
        with patch.object(common, 'compose', return_value=config) as compose, \
             patch.object(http, 'API', return_value=api) as factory, \
             patch.object(http, 'credentials_from_file_or_env', return_value={}), \
             patch.object(initialize, 'complete_qbittorrent'):
            vpn.main()
        self.assertEqual(compose.call_args.args[1], 'vpn')
        self.assertEqual(factory.call_args.args[0], 'http://127.0.0.1:18080')
