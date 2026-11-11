# TV: Sonarr

**English** | [Français](README.fr.md)

Replace `SERVER_IP` below with your host address.

Interface: http://SERVER_IP:8989 or http://sonarr.arr.local after adding a DNS record
pointing to `SERVER_IP`. The stack uses the external `media-shared` network,
prepared by `scripts/vpn-up.sh`.

## Volumes and permissions

| LXC host | Sonarr | Purpose |
|---|---|---|
| `./data/sonarr` | `/config` | Local configuration and database |
| `/media/tv` | `/tv` | Final TV library |
| `/downloads` | `/downloads` | Downloads shared with qBittorrent |

Override paths with `LIBRARY_DIR` and `SHARED_DOWNLOADS_DIR`. Keep the download
host path identical to the `download` stack. The default UID/GID is `1000:1000`.
The existing `/media/series` directory is not used: this stack mounts `/media/tv`
at `/tv`. Keep the libraries separate.

For Proxmox ACLs, see the [permissions guide](../docs/permissions.md).
The TV library needs the same ACLs for host UID `101000` as the movie library.
Set inheritance on existing directories as well.

## Commands in the LXC

```sh
cd /opt/media-stack/stacks
./scripts/vpn-up.sh
python3 scripts/stack-compose.py indexer up -d
python3 scripts/stack-compose.py tv config --quiet
python3 scripts/stack-compose.py tv up -d
python3 scripts/stack-compose.py tv ps
python3 scripts/stack-compose.py tv logs --since=5m --tail=80
```

`scripts/stacks.sh` includes this stack, and `scripts/check-services.py` checks
Sonarr's interface.

## Application configuration

- Create administrator credentials on first access.
- The `/tv` root folder is already registered on this host. Select quality profiles
  before adding series.
- In qBittorrent, create the `tv` category with save path `/downloads/tv`.
- Under Settings → Download Clients, add qBittorrent using host `qbittorrent`,
  port `8080`, your credentials, and category `tv`. Test before saving.
- Sonarr is already registered in Prowlarr on this host. Check Settings → Apps:
  Sonarr URL `http://sonarr:8989`, Prowlarr URL `http://prowlarr:9696`, and Sonarr's
  API key from Settings → General. Keep an existing entry rather than duplicating it.
- Add indexers offering TV categories in Prowlarr. Indexers and series searches
  are not configured automatically.

Image documentation: https://docs.linuxserver.io/images/docker-sonarr/

Container root paths are configurable through `.env`; see the
[media roots guide](../docs/media-roots.md). Download-client connections on this
host are already configured; see [clients and categories](../docs/download-clients.md).
