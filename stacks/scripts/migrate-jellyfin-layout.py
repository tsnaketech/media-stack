#!/usr/bin/env python3
"""Convert an offline official-image config tree to LinuxServer's directory layout."""
import argparse
import os
from pathlib import Path
import sqlite3
import sys
import uuid


def migrate_root_paths(database):
    old, new = '/config/root', '/config/data/root'
    with sqlite3.connect(database) as connection:
        connection.execute(
            'UPDATE BaseItems SET Path=? || substr(Path,?) WHERE Path=? OR Path LIKE ?',
            (new, len(old) + 1, old, old + '/%'))
        paths = connection.execute('SELECT changes()').fetchone()[0]
        connection.execute('UPDATE BaseItems SET Data=replace(Data,?,?) WHERE instr(Data,?)>0',
                           (old, new, old))
        serialized = connection.execute('SELECT changes()').fetchone()[0]
        if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('Database integrity verification failed.')
    return bool(paths or serialized)


def migrate(root):
    root = Path(root).resolve()
    if (root / 'system.xml').is_file() and (root / 'data/data/jellyfin.db').is_file():
        return migrate_root_paths(root / 'data/data/jellyfin.db')
    old_config = root / 'config'
    old_database = root / 'data/jellyfin.db'
    if not (old_config / 'system.xml').is_file() or not old_database.is_file():
        raise ValueError('Expected an official-image Jellyfin tree; no files changed.')
    configs = list(old_config.iterdir())
    for item in configs:
        if (root / item.name).exists():
            raise ValueError('Config destination already exists; no files changed.')
    if any((root / name).is_symlink() for name in ('data', 'metadata', 'plugins', 'root')):
        raise ValueError('Source directories must not be symlinks; no files changed.')
    for name in ('metadata', 'plugins', 'root'):
        if not (root / name).is_dir():
            raise ValueError('Expected a complete Jellyfin tree; no files changed.')
    owner = root.stat()
    stage = root.parent / ('.jellyfin-data-' + uuid.uuid4().hex)
    (root / 'data').rename(stage)
    (root / 'data').mkdir(mode=0o755)
    if os.geteuid() == 0:
        os.chown(root / 'data', owner.st_uid, owner.st_gid)
    for item in list(root.iterdir()):
        if item.name in ('config', 'data', 'log', 'cache', 'abyss-before.json'):
            continue
        item.rename(root / 'data' / item.name)
    stage.rename(root / 'data/data')
    for item in configs:
        item.rename(root / item.name)
    old_config.rmdir()
    # Existing database rows reference these absolute paths. Keep them usable.
    for name in ('metadata', 'plugins', 'root'):
        (root / name).symlink_to('data/' + name, target_is_directory=True)
        if os.geteuid() == 0:
            os.lchown(root / name, owner.st_uid, owner.st_gid)
    # Root lookups use the new canonical data path; keep the existing item IDs.
    migrate_root_paths(root / 'data/data/jellyfin.db')
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config_directory', type=Path)
    parser.add_argument('--offline', action='store_true', required=True,
                        help='Confirm Jellyfin is stopped and a verified backup exists')
    args = parser.parse_args()
    if migrate(args.config_directory):
        print('Jellyfin layout migrated; legacy metadata, plugin and library paths preserved.')
    else:
        print('Jellyfin already uses the LinuxServer layout; nothing changed.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, sqlite3.Error) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
