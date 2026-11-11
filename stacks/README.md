# Media services

**English** | [Français](README.fr.md)

Docker Compose stacks for homelab discovery, downloads, and playback. Each domain
has its own stack, settings templates, and local application state. This directory
belongs to the `/opt/media-stack` repository; media and downloads are configurable
external volumes. Run the commands below from `/opt/media-stack/stacks`.

## Layout

```text
.
├── vpn/              # Gluetun for qBittorrent, MeTube, and JDownloader
├── indexer/          # Prowlarr and FlareSolverr
├── download/         # qBittorrent, SABnzbd, qui, JOAL, MeTube, and JDownloader
├── shared/           # Jellyfin, Seerr, Profilarr, and Bazarr
├── music/            # Lidarr and Navidrome
├── movie/            # Radarr
├── tv/               # Sonarr
├── audiobook/        # Audiobookshelf
├── book/             # Calibre-Web and Shelfmark Lite
├── scripts/          # Lifecycle, HTTP checks, and configuration helpers
└── docs/             # Deployment, permissions, authentication, and Git preparation
```

CI workflows live in `.github/workflows/` at the repository root.
Each stack's `docker-compose.yml` and `.env.example` can be versioned. `.env` and
`data/` stay local and are ignored by Git. The [VPN stack](vpn/README.md) is required
for qBittorrent and included by default. Use `./scripts/stacks.sh up` so the VPN
is healthy before its clients start. Arcane and Traefik are optional infrastructure;
interfaces also work directly through their published ports.

## Installing in a new environment

The [clean initialization guide](docs/initialization.md) covers prerequisites,
mounts, secrets, external accounts, and manual steps.

```sh
python3 scripts/initialize.py prepare
# Fill VPN settings and verify storage paths in the generated .env files.
python3 scripts/initialize.py check
python3 scripts/initialize.py up
```

Initialization preserves existing data and accounts. Its isolated test uses fresh
data and separate ports:

```sh
python3 scripts/test-initialization.py
sudo python3 scripts/test-initialization.py --docker --pull
```

The guide explains exclusions such as a real VPN, providers, and interactive
setup wizards. Failed steps are reported without hiding other errors.

## Startup

Requirements: Docker Engine, Docker Compose **2.30+**, Bash, Python 3, and jq.
Python runs HTTP checks and application configuration. Preserve existing `.env`
files when preparing settings:

```sh
for stack in vpn indexer download shared music movie tv audiobook book; do
  test -f "$stack/.env" || cp "$stack/.env.example" "$stack/.env"
  chmod 600 "$stack/.env"
done
./scripts/stacks.sh validate
```

Fill the WireGuard key in `vpn/.env` and prepare TUN using the
[VPN guide](vpn/README.md). The VPN helper uses
`download/.qbittorrent-credentials.json`; see [download clients](docs/download-clients.md).

Adjust paths and UID/GID values in `.env`:

| Variable | Purpose |
|---|---|
| `DNS_PRIMARY`, `DNS_SECONDARY` | Container DNS, defaulting to `1.1.1.1` and `1.0.0.1` |
| `PUID`, `PGID` | Application user, defaulting to `1000:1000` |
| `SHARED_DOWNLOADS_DIR` | Same host directory across participating stacks |
| `LIBRARY_DIR` | Stack library, such as `/media/tv` |
| `MUSIC_DIR` | Host music library for Lidarr and Navidrome |
| `ARR_IMPORT_EXTRA_FILES`, `ARR_EXTRA_FILE_EXTENSIONS` | Enable extra-file import and choose extensions |
| `ARR_ROOT_FOLDER` | Container media root, registered automatically in the arr application |
| `NAVIDROME_ROOT_FOLDER`, `CALIBRE_ROOT_FOLDER`, `AUDIOBOOKSHELF_ROOT_FOLDER`, `SHELFMARK_ROOT_FOLDER` | Other applications' container roots; see the media guide |
| `ARR_AUTH_METHOD`, `ARR_AUTH_REQUIRED` | Arr login method and authentication requirement |
| `ARR_ALLOWED_HOSTS` | Allowed HTTP hostnames, separated by semicolons |
| `ARR_TRUSTED_PROXIES` | Trusted proxies forwarding client addresses |
| `ARR_AUTH_USERNAME`, `ARR_AUTH_PASSWORD` | Credentials applied by the hook; an empty password preserves the account |

Prepare directories and permissions before startup; see
[deployment](docs/deployment.md) and [permissions](docs/permissions.md).
For a fresh installation, create accounts and libraries or supply arr credentials
through `.env`. Download sources and indexers are not supplied automatically.

```sh
./scripts/stacks.sh up       # Start stacks and configure their integrations
./scripts/stacks.sh status
./scripts/stacks.sh logs
python3 scripts/check-services.py
# Configure and test download clients after supplying qBittorrent credentials.
python3 scripts/configure-download-clients.py
```

Default web ports: Prowlarr `9696`, qBittorrent `8080`, SABnzbd `8085`, MeTube `8081`,
[JDownloader](download/docs/jdownloader.md) `5800`, Lidarr `8686`, Navidrome `4533`,
Radarr `7878`, Sonarr `8989`, Audiobookshelf `13378`, Calibre-Web `8083`,
Shelfmark `8084`, Seerr `5055`, Profilarr `6868`, Jellyfin `8096`, Bazarr `6767`,
qui `7476`, and JOAL `8088` (its interface path is configured in `.env`).

## Optional infrastructure

Traefik, Arcane, Dozzle, and Homepage are in the repository root, one level above
`stacks/`. Include them explicitly:

```sh
./scripts/stacks.sh status --with-infra
./scripts/stacks.sh validate --with-vpn
# INFRA_ROOT contains traefik/, arcane/, dozzle/, and homepage/.
INFRA_ROOT=/opt/media-stack ./scripts/stacks.sh validate --with-infra
python3 scripts/check-services.py --with-infra --proxy-domain arr.local
```

Without `--proxy-domain`, HTTP checks do not require a reverse proxy. `--host`
selects another address. Manage Traefik routes and local DNS through the
infrastructure configuration.

## Documentation and contributions

- [Deployment and operation](docs/deployment.md)
- [Profilarr profiles and formats](shared/docs/profilarr.md)
- [Seerr requests](shared/docs/seerr.md)
- [Jellyfin media server](shared/docs/jellyfin.md)
- [FlareSolverr proxy](indexer/docs/flaresolverr.md)
- [Qui interface](download/docs/qui.md)
- [JOAL service](download/docs/joal.md)
- [Bazarr subtitles](shared/docs/bazarr.md)
- [Passing TUN to a Proxmox LXC](docs/proxmox-tun.md)
- [qBittorrent clients and categories](docs/download-clients.md)
- [Importing extra files](docs/media-management.md)
- [Media roots and volumes in .env](docs/media-roots.md)
- [Proxmox / LXC / Docker permissions](docs/permissions.md)
- [Authentication and credentials in .env](docs/authentication.md)
- [GitHub preparation and publication](docs/github.md)
- [Contributing](../CONTRIBUTING.md)

Databases, media, passwords, API keys, and generated configuration are not part of
the repository. Keep separate backups of local state.

[SABnzbd](download/sabnzbd.md) provides Usenet downloads in `download/`.
Configure a provider and NZB indexer before using it.
[Prowlarr applications](indexer/prowlarr-apps.md) are configured by
`python3 scripts/configure-prowlarr-apps.py`, with `fullSync` by default and
`PROWLARR_APPS_*` / `PROWLARR_APP_<APP>_*` variables in `indexer/.env`.

Downloads use the Proxmox `/downloads` mount. The
[download storage guide](docs/downloads-storage.md) covers ACLs, migration, and
pre-start checks. [MeTube](download/docs/metube.md) provides a yt-dlp web interface
in `download/`: videos go to `METUBE_VIDEO_DIR` (default `/downloads/youtube/videos`),
while audio and temporary files stay under `SHARED_DOWNLOADS_DIR/youtube`.
