# Downloads

**English** | [Français](README.fr.md)

This stack contains **qBittorrent**, **SABnzbd**, **qui**, **JOAL**, **MeTube**, and
**JDownloader 2**. Gluetun lives in `../vpn`; qBittorrent, MeTube, and JDownloader
share its network namespace. Other services join the external `media-shared` network.

## Configuration

Settings are grouped by tool in `.env.example`. Keep local values, accounts, and
secrets in `.env`, with permissions `600`. `SHARED_DOWNLOADS_DIR=/downloads`
identifies the Proxmox mount shared by download clients and arr applications.
Verify that it is mounted before startup.

Default ports are qBittorrent `8080`, MeTube `8081`, and JDownloader `5800`
(published by Gluetun), SABnzbd `8085`, qui `7476`, and JOAL `8088`.
Host-specific URLs are in `/opt/media-stack/README.local.md`.
Docker service names remain unchanged.

## Startup and checks

Before the first installation, prepare the MeTube directories described in its
[storage guide](docs/metube.md#stockage), then run from `stacks/`:

```sh
./scripts/vpn-up.sh
python3 scripts/prepare-joal.py
python3 scripts/stack-compose.py download up -d
python3 scripts/stack-compose.py download ps
python3 scripts/stack-compose.py download logs --since=5m --tail=60
```

`./scripts/stacks.sh up` also starts the other stacks. After startup:

```sh
python3 scripts/configure-qui.py
python3 scripts/configure-download-clients.py
```

These scripts and VPN configuration use the local `.qbittorrent-credentials.json`.
Existing accounts and torrents are preserved. Service state lives in
`download/data/<service>` and is excluded from Git. Back up configuration and
secrets separately.

See the [JDownloader](docs/jdownloader.md), [MeTube](docs/metube.md),
[SABnzbd](sabnzbd.md), [qui](docs/qui.md), [JOAL](docs/joal.md),
[VPN](../vpn/README.md), and [shared storage](../docs/downloads-storage.md) guides.
SABnzbd requires a Usenet provider and NZB indexer. Its traffic does not
automatically pass through qBittorrent's VPN.
