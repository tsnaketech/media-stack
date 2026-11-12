# Media Stack

**English** | [Français](README.fr.md)

Docker Compose configuration for a media homelab: discovery, downloads, playback,
and administration. Examples use `/opt/media-stack` as the checkout path; adapt it to your deployment.

## Layout

```text
media-stack/
├── stacks/      # Nine media stacks, scripts, and tests
├── homepage/      # Dashboard
├── dozzle/        # Docker logs and read-only proxy
├── traefik/       # Reverse proxy
├── arcane/        # Container management
├── docs/          # Project layout and migration
├── .github/       # Continuous integration
└── README.md
```

Each stack documents its settings in `.env.example`. Copy these templates to local
`.env` files, then adjust paths, accounts, and secrets.

## Installation and management

Prepare the media stacks from the project root:

```sh
python3 stacks/scripts/initialize.py prepare
python3 stacks/scripts/initialize.py check
python3 stacks/scripts/initialize.py up
```

Prepare the infrastructure configuration and networks before including them in
management commands. The layout guide covers the Traefik and Homepage templates.

```sh
./stacks/scripts/stacks.sh validate --with-infra
./stacks/scripts/stacks.sh status --with-infra
python3 stacks/scripts/check-services.py --with-infra --proxy-domain arr.local
```

Libraries use `/media`; downloads use `/downloads`. Proxmox mounts, ACLs, and `.env`
values must match the deployment environment.

## Local access

Use `README.local.md.example` to create a local `README.local.md` containing your
host URLs. This directory of links can also live outside the checkout in a local
operations folder. Application state, `.env` files, active routes, reports, and
backups are excluded from Git.

## Documentation

Detailed deployment guides currently remain in French.

- [Automatic startup and VPN reconciliation](stacks/docs/boot.md)
- [Video duplicate detection and CSV/HTML reports](stacks/docs/video-duplicates.md)

- [Service installation, permissions, and configuration](stacks/README.md)
- [Project layout and migration](docs/project-layout.md)
- [Git preparation and local files](stacks/docs/github.md)
- [Initialization in another environment](stacks/docs/initialization.md)
- [External deployment extensions](docs/extensions.md)
- [Contributing](CONTRIBUTING.md)
- [Homepage](homepage/README.md)
- [Dozzle](dozzle/README.md)
