# Dozzle

**English** | [Français](README.fr.md)

Docker log viewer in `/opt/media-stack/dozzle`. Direct and Traefik URLs are listed
in the [local directory](../README.local.md). The default host port is `9999`.
Settings live in `.env`, based on `.env.example`; persistent preferences live in
`data/`, outside Git.

## Docker access

The `docker-proxy` service filters Docker socket access using LinuxServer
socket-proxy. Read access to containers, logs, events, and system information is
enabled; `POST=0` blocks mutations. Dozzle actions and its terminal are disabled.
The proxy publishes no ports and uses the internal `infra-observability` network,
shared with Homepage for container status. Dozzle also joins `proxy-network` for
its interface. It does not require the VPN.

Authentication is not configured; the interface is intended for the LAN. Logs may
contain sensitive data. Blocking Docker writes does not hide secrets already
exposed in application logs or metadata.

## Management

From `/opt/media-stack`, after Traefik creates `proxy-network`:

```sh
python3 stacks/scripts/stack-compose.py dozzle config --quiet
python3 stacks/scripts/stack-compose.py dozzle up -d
python3 stacks/scripts/stack-compose.py dozzle ps
python3 stacks/scripts/stack-compose.py dozzle logs --tail=60
```

Keep the Dozzle network while Homepage uses it. To stop only the interface:
`python3 stacks/scripts/stack-compose.py dozzle stop dozzle`.
The management and HTTP check scripts include Dozzle with `--with-infra`.
Infrastructure starts in this order: Traefik, Arcane, Dozzle, Homepage.
Back up `.env` and `data/`.

Sources: [Dozzle](https://dozzle.dev/guide/getting-started),
[proxy connection](https://dozzle.dev/guide/remote-hosts),
[LinuxServer socket-proxy](https://docs.linuxserver.io/images/docker-socket-proxy/).
