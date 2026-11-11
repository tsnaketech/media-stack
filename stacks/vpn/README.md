# VPN: Gluetun

**English** | [Français](README.fr.md)

This dedicated stack uses [passteque/gluetun](https://github.com/passteque/gluetun)
and the `qmcgaw/gluetun:latest` image. The GitHub repository choice does not change
the Docker image name. It uses the external `media-shared` network,
`data:/gluetun`, the `NET_ADMIN` capability, and `/dev/net/tun`.
The image supplies its own health check. Gluetun publishes qBittorrent port 8080,
MeTube port 8081, and JDownloader port 5800. Its control server stays on the
container loopback interface.

## Provider configuration

The template supports **Proton VPN Plus / WireGuard**. Set your provider-issued
credentials in the local `.env`, verify TUN access, and select servers compatible
with your subscription and P2P requirements. `SERVER_COUNTRIES` is optional;
when set, use the English country names expected by Gluetun.

qBittorrent, MeTube, and JDownloader require this stack. `scripts/stacks.sh`
includes the VPN by default; `--with-vpn` remains accepted for compatibility.

## Files and settings

To reconcile VPN clients automatically after Docker starts, run
`sudo python3 stacks/scripts/install-vpn-boot.py` from the project root.
See [startup automation](../docs/boot.md) for behavior, logs and maintenance.

- `docker-compose.yml`: service and Docker network.
- `.env.example`: versionable template with English comments.
- `.env`: local provider, protocol, and secrets; protect with mode `600`.
- `data/`: Gluetun state and optional VPN configuration files, ignored by Git.

From `/opt/media-stack/stacks`:

```sh
test -f vpn/.env || cp vpn/.env.example vpn/.env
chmod 600 vpn/.env
./scripts/stacks.sh validate --with-vpn
```

The template uses `VPN_SERVICE_PROVIDER=protonvpn` and `VPN_TYPE=wireguard`.
See the [Proton VPN guide](protonvpn.md) to obtain a key and activate the tunnel.
The `custom` and OpenVPN options below support other explicitly configured setups.

### WireGuard

Set `WIREGUARD_PRIVATE_KEY` and `WIREGUARD_ADDRESSES` from your provider.
For a custom endpoint, also supply `WIREGUARD_PUBLIC_KEY`,
`WIREGUARD_ENDPOINT_IP`, and `WIREGUARD_ENDPOINT_PORT`. A preshared key is optional.
Use provider-issued settings rather than generating an arbitrary replacement key.

You can also place a configuration at `data/wireguard/wg0.conf`; its fields take
precedence over corresponding environment variables. This file contains secrets
and must remain in storage ignored by Git.

### OpenVPN

Choose `VPN_TYPE=openvpn`, then supply `OPENVPN_USER` and `OPENVPN_PASSWORD`
if required by the provider. For `custom`, place the configuration in
`data/custom.ovpn` and set:

```dotenv
VPN_SERVICE_PROVIDER=custom
VPN_TYPE=openvpn
OPENVPN_CUSTOM_CONFIG=/gluetun/custom.ovpn
```

Referenced certificate files must also be accessible under `/gluetun`.
For a built-in provider, leave `OPENVPN_CUSTOM_CONFIG` empty.

## LXC prerequisites

The [Proxmox/TUN procedure](../docs/proxmox-tun.md) covers module loading,
backing up `${CT_ID}.conf`, the two configuration entries, restarting the LXC,
and checking the device.

On Proxmox, pass `/dev/net/tun` into the LXC hosting Docker, then restart that LXC
when a service interruption is acceptable. The device must be available before
creating the Docker container:

```sh
test -c /dev/net/tun && ls -l /dev/net/tun
```

Compose passes only this device with `NET_ADMIN`; Docker privileged mode is not
required. Proxmox configuration and the LXC restart are host administration steps.

## Activation and verification

Once the provider, secrets, and TUN are configured:

```sh
./scripts/vpn-up.sh
python3 scripts/stack-compose.py vpn ps
python3 scripts/stack-compose.py vpn logs --since=5m --tail=80
```

Confirm a healthy status, then verify the exit address and DNS resolution from
inside the container before routing applications through it.
To start all stacks:

```sh
./scripts/stacks.sh up --with-vpn
./scripts/stacks.sh status --with-vpn
```

## Checking the VPN from qBittorrent

Run these commands inside the Docker-hosting LXC. They check qBittorrent's network;
a test on the LXC itself does not verify its tunnel. MeTube and JDownloader share
that tunnel. SABnzbd and other services are not automatically protected by Gluetun.

### Health and network attachment

```sh
docker inspect gluetun --format '{{.State.Health.Status}}'
docker exec gluetun readlink /proc/self/ns/net
docker exec qbittorrent readlink /proc/self/ns/net
```

Gluetun should be `healthy`. Both `net:[...]` identifiers must match, confirming
that the containers share a network namespace. Health alone does not establish
that qBittorrent uses this network. If identifiers differ, run `./scripts/vpn-up.sh`
from `stacks/`, then repeat the checks.

### Public address and route

```sh
docker exec qbittorrent curl -fsS --max-time 15 https://ipinfo.io/json
docker exec qbittorrent ip route get 1.1.1.1
```

The public address should belong to the VPN exit. If `SERVER_COUNTRIES` is set,
check that the reported country matches your selected location. The address can change on
reconnection; do not pin it. Geolocation is indicative, and an IPinfo outage
alone does not establish a VPN failure. The route should include `dev tun0`.

Also check **qBittorrent → Options → Advanced → Network interface** for `tun0`.
The configuration helper binds torrent connections to this interface.

### Blocking direct Internet access

After confirming the VPN request works:

```sh
docker exec qbittorrent curl -fsS \
  --interface eth0 --connect-timeout 3 --max-time 5 \
  https://1.1.1.1/cdn-cgi/trace
```

This forces Docker's `eth0` interface outside the tunnel. It should fail,
typically with a timeout (`curl: (28)`). A successful response requires checking
the firewall before resuming downloads. A different error may have another cause
and does not by itself prove that direct access is blocked.

This test leaves the VPN running. It checks the direct path at test time rather
than simulating tunnel failure. LAN exceptions in `FIREWALL_OUTBOUND_SUBNETS`
remain allowed.

### DNS and troubleshooting

```sh
docker exec qbittorrent cat /etc/resolv.conf
python3 scripts/stack-compose.py vpn logs --since=5m --tail=80
docker exec gluetun iptables -S OUTPUT
```

This installation expects `nameserver 127.0.0.1`, Gluetun's resolver.
That checks local DNS configuration, not external DNS leakage. The firewall
should show `-P OUTPUT DROP` with allowances for the tunnel, its endpoint,
and intended local networks. Review network addresses in logs before sharing them.

## Connecting applications

VPN protection applies to applications sharing Gluetun's network namespace.
Across Compose projects, use `network_mode: "container:gluetun"`. Publish the
application's ports on Gluetun, start it after Gluetun, and prepare addresses
used by other applications. qBittorrent, MeTube, and JDownloader use the VPN;
other applications keep their normal networks. The `qbittorrent` Docker alias
belongs to Gluetun, so `http://qbittorrent:8080` remains usable.

Gluetun's firewall blocks traffic outside the tunnel.
`FIREWALL_INPUT_PORTS=8080,8081,5800` allows the three web interfaces.
Set only the intended LAN CIDR in `FIREWALL_OUTBOUND_SUBNETS` for local replies;
this exception also permits connections to that LAN outside the VPN.
HTTP and Shadowsocks proxies are disabled in this template.

Documentation: [Gluetun](https://github.com/passteque/gluetun),
[provider settings](https://github.com/qdm12/gluetun-wiki/tree/main/setup/providers),
[connecting a container](https://github.com/qdm12/gluetun-wiki/blob/main/setup/connect-a-container-to-gluetun.md).

## Restarting without losing the connection

From `stacks/`:

```sh
./scripts/vpn-up.sh
# Or start the whole homelab, with VPN first:
./scripts/stacks.sh up
```

The script creates the external network if missing, waits for Gluetun to become
healthy, then recreates qBittorrent, MeTube, and JDownloader if their namespaces
differ. Run it after every Gluetun recreation: restarting qBittorrent alone does
not attach it to a new VPN container. Avoid stopping Gluetun during a download.

`configure-qbittorrent-vpn.py` uses existing local credentials to bind torrents to
`tun0` and disable UPnP and random ports. This binding and the Gluetun firewall
block torrent traffic if the tunnel disappears. Peer ports 6881 are no longer
published on the host. Proton port forwarding remains disabled; outgoing
connections work without it.

`QBITTORRENT_WEB_BIND_IP` and `QBITTORRENT_WEB_PORT` in `vpn/.env` control web
publication. Configuration scripts resolve the published port from the effective
Compose model; the internal port remains 8080. The external network survives
`compose down`; keep it while other stacks use it. Operational backups remain
outside Git.

### First installation without qBittorrent credentials

After configuring TUN and `vpn/.env`, start once:

```sh
docker network inspect media-shared >/dev/null 2>&1 || docker network create media-shared
python3 scripts/stack-compose.py vpn up -d --wait --wait-timeout 120
python3 scripts/stack-compose.py download up -d --no-deps qbittorrent
```

Choose a permanent password in the web interface, then save credentials with
`python3 scripts/configure-download-clients.py --init-credentials`.
Finish with `./scripts/vpn-up.sh` to apply and verify the `tun0` binding.

## MeTube through Gluetun

MeTube shares qBittorrent's tunnel. `METUBE_WEB_BIND_IP` and `METUBE_PORT` in
`vpn/.env` control publication of internal port 8081. The firewall allows web
access on 8081; the network alias is `metube`. `scripts/vpn-up.sh` reconnects all
three download clients after VPN recreation. See the
[MeTube verification procedure](../download/docs/metube.md#raccordement-vpn).
