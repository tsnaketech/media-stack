"""Protect library IDs and metadata when changing the Jellyfin container layout."""
import importlib
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
layout = importlib.import_module('migrate-jellyfin-layout')


class JellyfinLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'config'
        for directory in ['config', 'data', 'metadata', 'plugins/configurations', 'root/default', 'log']:
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        (self.root / 'config/system.xml').write_text('<config/>')
        (self.root / 'metadata/art.jpg').write_bytes(b'original-art')
        (self.root / 'plugins/configurations/settings.xml').write_text('<plugin/>')
        self.db = self.root / 'data/jellyfin.db'
        with sqlite3.connect(self.db) as c:
            c.execute('CREATE TABLE BaseItems (Id TEXT PRIMARY KEY, Path TEXT, Data TEXT)')
            c.executemany('INSERT INTO BaseItems VALUES (?,?,?)', [
                ('library-id', '/config/root/default/Films', '{"Path":"/config/root/default/Films"}'),
                ('media-id', '/media/movies/file.mkv', '{"IsLocked":true}')])

    def test_migration_preserves_ids_media_paths_and_old_image_and_plugin_paths(self):
        self.assertTrue(layout.migrate(self.root))
        self.assertEqual((self.root / 'metadata/art.jpg').read_bytes(), b'original-art')
        self.assertEqual((self.root / 'plugins/configurations/settings.xml').read_text(), '<plugin/>')
        self.assertTrue((self.root / 'system.xml').is_file())
        with sqlite3.connect(self.root / 'data/data/jellyfin.db') as c:
            rows = c.execute('SELECT * FROM BaseItems ORDER BY Id').fetchall()
        self.assertEqual(rows, [
            ('library-id', '/config/data/root/default/Films', '{"Path":"/config/data/root/default/Films"}'),
            ('media-id', '/media/movies/file.mkv', '{"IsLocked":true}')])
        self.assertFalse(layout.migrate(self.root))

    def test_conflicting_configuration_is_rejected_before_any_moves(self):
        (self.root / 'system.xml').write_text('existing')
        with self.assertRaises(ValueError):
            layout.migrate(self.root)
        self.assertTrue(self.db.exists())
        self.assertTrue((self.root / 'metadata').is_dir())
        self.assertEqual((self.root / 'system.xml').read_text(), 'existing')
