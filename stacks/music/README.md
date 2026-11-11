# Music: Lidarr and Navidrome

**English** | [Français](README.fr.md)

Run these commands on the Docker host from `/opt/media-stack/stacks/music`.
Docker Engine and the Docker Compose plugin are required.

## Preparation

Preserve an existing `.env`. If missing, copy `.env.example` to `.env`.
Set `PUID` and `PGID` to the music user's IDs (`id -u` and `id -g`).
Default host paths are `/media/music` for the library and `/downloads` for shared
downloads; override them with `MUSIC_DIR` and `SHARED_DOWNLOADS_DIR`.
Music downloads appear at `/downloads/music` inside the container.

With default settings, prepare the directories:

```sh
sudo mkdir -p data/lidarr data/navidrome /media/music /downloads/music
# Replace 1000:1000 with the selected PUID:PGID values.
sudo chown 1000:1000 data/lidarr data/navidrome /media/music /downloads/music
```

Adjust paths if you changed the variables. For an existing library, also check
file and subdirectory permissions: Lidarr needs write access; Navidrome needs
read access. These commands do not recursively change existing file ownership.

## Startup and checks

Use the common launcher so optional deployment overrides are applied:

```sh
python3 ../scripts/stack-compose.py music config --quiet
python3 ../scripts/stack-compose.py music pull
python3 ../scripts/stack-compose.py music up -d
python3 ../scripts/stack-compose.py music ps
python3 ../scripts/stack-compose.py music logs --tail=100 lidarr navidrome
```

Open Lidarr at `http://SERVER_IP:8686` and Navidrome at `http://SERVER_IP:4533`.
Configure Lidarr authentication and create the first Navidrome administrator.

Add `/music` as Lidarr's root folder. Navidrome reads the same library read-only.
Automatic downloads also require an indexer and download client in Lidarr;
neither is part of this music stack. The client must share the downloads folder
using a path consistent with `/downloads` in Lidarr.

The interfaces work directly on their ports without Traefik or Arcane.
Run `../scripts/vpn-up.sh` first to prepare `media-shared`. Verify actual startup
on the Docker host.

## Related services

See [indexer](../indexer/README.md) for Prowlarr and
[download](../download/README.md) for qBittorrent. Downloads use
`SHARED_DOWNLOADS_DIR=/downloads` by default, exposed as `/downloads`.
The music category saves to `/downloads/music`. The old `DOWNLOADS_DIR` variable
is no longer used.

Container root paths are configurable in `.env`; see the
[media roots guide](../docs/media-roots.md).
Download-client connections on this host are already configured; see
[clients and categories](../docs/download-clients.md).

## Organizing tracks into album directories

Under **Settings → Media Management → Track Naming**, enable **Rename Tracks**.
The text before the first `/` in the naming format defines the album directory.
The configured format starts with `{Album Title} ({Release Year})/`.
For example, *Lunatic* tracks are stored in `/music/Booba/Lunatic (2010)/` in Lidarr.

The command below enables renaming for future imports and applies the existing
naming format to an album's current tracks through Lidarr. It moves and renames
library files. Run from `/opt/media-stack/stacks/music` with Compose and Python 3.
Replace Lidarr IDs `2` (Booba) and `10` (Lunatic) to process a different album.

```sh
python3 - 2 10 <<'PY'
import importlib
import sys
from pathlib import Path

artist_id, album_id = map(int, sys.argv[1:])
root = Path.cwd().parent
sys.path.insert(0, str(root / "scripts"))
clients = importlib.import_module("configure-download-clients")
lidarr = clients.app_api(root, "lidarr", "127.0.0.1")

album = lidarr.call(f"album/{album_id}")
if album["artistId"] != artist_id:
    raise SystemExit("This album does not belong to the specified artist.")

naming = lidarr.call("config/naming")
if not naming["renameTracks"]:
    naming["renameTracks"] = True
    lidarr.call(f"config/naming/{naming['id']}", "PUT", naming)

renames = lidarr.call(f"rename?artistId={artist_id}")
tracks = [entry for entry in renames if entry["albumId"] == album_id]
if not tracks:
    raise SystemExit("No tracks in this album need renaming.")

for entry in tracks:
    print(f"{entry['existingPath']} → {entry['newPath']}")

command = lidarr.call("command", "POST", {
    "name": "RenameFiles",
    "artistId": artist_id,
    "files": [entry["trackFileId"] for entry in tracks],
})
print(f"Lidarr task {command['id']} started for {len(tracks)} tracks.")
PY
```

Check completion under **System → Tasks**, then inspect the album directory.
The command reads the local API key through the repository helper.

[Lidarr naming documentation](https://github.com/Servarr/Wiki/blob/master/lidarr/settings.md)
