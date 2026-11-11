# Shared services

**English** | [Français](README.fr.md)

This stack contains **Jellyfin**, **Seerr**, **Profilarr** with its parser, and
**Bazarr**. Prowlarr and FlareSolverr live in [indexer](../indexer/README.md);
qBittorrent, SABnzbd, qui, and JOAL live in [download](../download/README.md).

## Configuration and startup

Settings are grouped in `.env.example`. Preserve the existing local `.env` and
protect its secrets with `chmod 600 shared/.env`. Each service stores its state
in `shared/data/<service>`.

From `stacks/`:

```sh
./scripts/stacks.sh up
# Or manage the shared services once media-shared exists:
python3 scripts/stack-compose.py shared config --quiet
python3 scripts/stack-compose.py shared up -d
python3 scripts/stack-compose.py shared ps
python3 scripts/stack-compose.py shared logs --since=5m --tail=60
```

The external `media-shared` network connects the stacks. The private
`profilarr-internal` network connects Profilarr to its parser without publishing
the parser. `scripts/vpn-up.sh` prepares the external network before global startup.

## Guides and automation

- [Jellyfin](docs/jellyfin.md): libraries and media playback, port `8096`.
- [Seerr](docs/seerr.md): requests and Jellyfin/Radarr/Sonarr connections, port `5055`.
- [Profilarr](docs/profilarr.md): Radarr/Sonarr profiles and formats, port `6868`.
- [Bazarr](docs/bazarr.md): subtitles and Radarr/Sonarr connections, port `6767`.
- [Arr connections to Jellyfin](docs/arr-connect.md): library refreshes.

The corresponding scripts live in `../scripts` and use the `JELLYFIN_*`,
`SEERR_*`, `PROFILARR_*`, and `BAZARR_*` variables supplied by Compose.
Jellyfin mounts libraries read-only; Bazarr writes subtitles to the libraries.

Keep `.env`, databases, logs, and application state out of Git. URLs containing
the host's actual address belong in `/opt/media-stack/README.local.md`.
