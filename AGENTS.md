# Repository Guidelines

## Project Structure & Module Organization

The repository root is `/opt/media-stack`.

- `stacks/{vpn,indexer,download,shared,music,movie,tv,audiobook,book}/` contains nine populated Compose stacks, environment examples and service guides.
- `stacks/scripts/` contains configuration and lifecycle automation. `stacks/tests/` contains Python unit tests. CI workflows live in `.github/workflows/` and run from `stacks/`.
- `homepage/`, `dozzle/`, `traefik/` and `arcane/` contain infrastructure stacks. `--with-infra` includes them in management commands.
- `stacks/docs/`, `docs/` and `CONTRIBUTING.md` document deployment and maintenance.
- Runtime data lives in stack `data/` directories. Libraries mount under `/media`, downloads under `/downloads`. Deployment extensions, backups and reports may live outside the checkout.

## Build, Test, and Development Commands

Run from the repository root with Docker Engine, Compose 2.30+, Python 3, Bash and jq installed.

```sh
./stacks/scripts/stacks.sh validate --with-infra
./stacks/scripts/stacks.sh status --with-infra
python3 stacks/scripts/initialize.py check
STACK_EXTENSIONS_DIR= python3 -m unittest discover -s stacks/tests -v
python3 stacks/scripts/check-services.py --with-infra --proxy-domain arr.local
```

These validate Compose models, inspect containers, check deployment prerequisites, run unit tests and check HTTP routes. `initialize.py prepare` prepares environment files and directories. `initialize.py up` starts and configures the media stacks.

Jellyfin uses `lscr.io/linuxserver/jellyfin:latest`. Its `/custom-cont-init.d` hook reapplies pinned Abyss assets and Spotlight at startup, including `abyss-je.css`. Keep LinuxServer's root/s6 initialization and pass `PUID`/`PGID`; do not add Docker `init`, force `user`, or drop all capabilities. Theme sources live in `stacks/shared/jellyfin-abyss/`.

## Coding Style & Naming Conventions

Follow `.editorconfig`. Use two-space YAML indentation, four-space Python indentation, LF endings and executable shell scripts. Keep Compose filenames as `docker-compose.yml`, service keys lowercase and environment variables uppercase.

Every Compose declares `x-common-keys: &common-keys`; every service inherits it. Document new settings with English comments in grouped `.env.example` sections. Prefer Python standard-library automation on the host and shell for containers without Python.

## Testing Guidelines

Tests use `unittest`. Validate changed Compose files and run relevant automation tests. `python3 stacks/scripts/test-initialization.py --docker` checks the native core with isolated data and ports. Inspect affected containers, logs and routes after deployment. After recreating Gluetun, run `stacks/scripts/vpn-up.sh` to reconnect its three clients.

`python3 stacks/scripts/install-vpn-boot.py` installs the systemd VPN reconciliation service. It runs after Docker starts, checks storage and tunnel readiness, and retries failures. See `stacks/docs/boot.md`; avoid rebooting the host for routine validation.

## Commit & Pull Request Guidelines

Use concise imperative subjects, such as `music: configure album folders`. Describe affected stacks, behavior changes, validation and migration steps. Link relevant issues and include screenshots for interface changes.

## Private Configuration

Keep secrets and host addresses in ignored local files. Public templates cover `.env.example`, `homepage/config.example/`, `traefik/config/dynamic.example/` and `README.local.md.example`. Check `.gitignore` before staging changes. Follow the permissions guide when changing shared storage ACLs.

Use `stacks/scripts/stack-compose.py STACK ...` for lifecycle operations. It applies external Compose overlays and environment files declared through `STACK_EXTENSIONS_DIR` in the root local `.env`. Keep deployment-specific integrations outside the checkout; see `docs/extensions.md`.
