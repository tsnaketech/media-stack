# Books: Calibre-Web and Shelfmark Lite

**English** | [Français](README.fr.md)

Replace `SERVER_IP` below with your host address.

- Calibre-Web: http://SERVER_IP:8083, serving `/books` from `/media/books`.
- Shelfmark Lite: http://SERVER_IP:8084 or http://shelfmark.arr.local after adding
  a DNS record pointing to `SERVER_IP`.

## Shelfmark volumes

| LXC host | Container | Purpose |
|---|---|---|
| `./data/shelfmark` | `/config` | Persistent configuration, database, and cache |
| `/downloads/books/ingest` | `/books` | Destination for retrieved ebooks |
| `/downloads` | `/downloads` | Same path as qBittorrent for retrieving files |

Override `/downloads` with `SHARED_DOWNLOADS_DIR`; use the same value in the
`download` stack. Directories must be accessible to Shelfmark's UID/GID, which
defaults to `1000:1000`, and to Docker Engine. Shelfmark does not mount the existing
`/media/books` library. Retrieved files stay in a separate intake folder until import.

## Management

From `/opt/media-stack/stacks`:

```sh
./scripts/vpn-up.sh
python3 scripts/stack-compose.py indexer up -d
python3 scripts/stack-compose.py book config --quiet
python3 scripts/stack-compose.py book up -d shelfmark
python3 scripts/stack-compose.py book ps
python3 scripts/stack-compose.py book logs --since=5m --tail=80 shelfmark
curl -fsS http://127.0.0.1:8084/api/health
```

`scripts/vpn-up.sh` creates the external `media-shared` network. Calibre-Web keeps
its existing network. Shelfmark's health check also verifies that its download
coordinator is running.

## First use

1. Open Shelfmark and configure authentication in its settings.
2. Configure the desired sources. For Prowlarr, use `http://prowlarr:9696` and its
   API key. Add ebook indexers in Prowlarr before expecting search results.
3. Configure qBittorrent with `http://qbittorrent:8080` and its credentials.
   Use a dedicated category such as `books`, saving to `/downloads/books`.
   Both services see this path identically.
4. Choose formats, languages, and metadata providers. Some sources require a
   personal account or API key.
5. Test connections in the interface before the first download.

Lite retains the web interface, search, and client integrations. It removes the
internal browser used by some direct-download sources; those sources may need a
compatible external resolver. No resolver or source is added automatically.

## Importing into Calibre-Web

Shelfmark retrieves files but does not manage a Calibre library or monitor authors'
new releases. Import ebooks from the intake folder into a valid Calibre library,
or upload them through Calibre-Web if configured. Copying an EPUB into
`/media/books` does not update `metadata.db`. This stack does not automatically
modify the existing library.

Documentation: [Shelfmark](https://github.com/calibrain/shelfmark),
[official Lite Compose](https://github.com/calibrain/shelfmark/blob/main/compose/docker-compose.lite.yml).

Container root paths are configurable through `.env`; see the
[media roots guide](../docs/media-roots.md). Download-client connections on this
host are already configured; see [clients and categories](../docs/download-clients.md).
