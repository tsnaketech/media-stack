# Homepage

**English** | [Français](README.fr.md)

Homelab dashboard in `/opt/media-stack/homepage`. Host URLs are listed in the
[local directory](../README.local.md), which Git ignores. The default port is `3002`.

## Common configuration

Copy `config.example/*.yaml` into `config/`, then adjust URLs and DNS names.
Source files stay in the common repository:

- `.env`: UID/GID, image, port, and `HOMEPAGE_ALLOWED_HOSTS`.
- `config/services.yaml`: common services and Docker status.
- `config/settings.yaml`: language, theme, and layout.
- `config/docker.yaml`: connection to Dozzle's Docker proxy.
- `config/widgets.yaml` and `config/bookmarks.yaml`: widgets and bookmarks.

Git ignores `config/`, which is mounted read-only. The launcher prepares
`../runtime/homepage/`, owned by the container user, for generated files and logs.
The renderer uses Node and the YAML parser already bundled with the image.

## Optional additions

An override can mount an external directory read-only at `/app/config-extra`.
Its `services.yaml` contains only additional entries, under existing group names
or new groups. Without this directory, Homepage uses only the common services.

At startup, the script merges both lists into `runtime/homepage/services.yaml`.
It then watches the source directories and propagates changes automatically.
Duplicate service names within a group are rejected; an invalid update preserves
the last valid output. Do not edit the generated YAML directly. Other common
configuration files are available through links in the runtime directory.

## Management

Dozzle must first create its network and Docker proxy. From the project root:

```sh
python3 stacks/scripts/stack-compose.py dozzle up -d
python3 stacks/scripts/stack-compose.py homepage config --quiet
python3 stacks/scripts/stack-compose.py homepage up -d
python3 stacks/scripts/stack-compose.py homepage logs --tail=60
```

Changes to `.env` or mounts require container recreation. Back up `.env`, `config/`,
and external additions; the runtime is regenerable. Add permitted hostnames to
`HOMEPAGE_ALLOWED_HOSTS`. The interface is intended for the LAN and does not
configure authentication.
