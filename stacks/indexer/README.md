# Indexers

**English** | [Français](README.fr.md)

This stack contains **Prowlarr** and its **FlareSolverr** proxy. They share the
external `media-shared` network with arr applications. Docker addresses are
`prowlarr:9696` and `flaresolverr:8191`. By default, the FlareSolverr API is published
only on the host loopback interface.

## Configuration and startup

Copy `.env.example` to `.env` only when needed, then protect it with
`chmod 600 indexer/.env`. `ARR_AUTH_*` and `ARR_ALLOWED_HOSTS` configure Prowlarr.
`PROWLARR_APPS_*` and `PROWLARR_APP_<APP>_*` control application registration;
`FLARESOLVERR_*` configures the proxy and its tags.

From `stacks/`:

```sh
./scripts/stacks.sh up
# Or manage this stack after creating the external media-shared network:
python3 scripts/stack-compose.py indexer config --quiet
python3 scripts/stack-compose.py indexer up -d
python3 scripts/stack-compose.py indexer ps
python3 scripts/stack-compose.py indexer logs --since=5m --tail=60
```

After the relevant services start:

```sh
python3 scripts/configure-flaresolverr.py
python3 scripts/configure-prowlarr-apps.py
```

See [Prowlarr applications](prowlarr-apps.md) and [FlareSolverr](docs/flaresolverr.md).
The default synchronization level is `fullSync`. Add indexers to Prowlarr with
the appropriate access credentials.

## State and access

Configuration persists in `indexer/data/prowlarr` and `indexer/data/flaresolverr`.
The scripts read Prowlarr's API key from `config.xml`. Do not edit its SQLite
database while it is running. Git excludes application state and the local
`.env`; back them up separately. Host URLs are in `/opt/media-stack/README.local.md`.
