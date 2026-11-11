#!/usr/bin/env bash
# Start the VPN first and reconnect clients if their network namespace changed.
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
docker network inspect media-shared >/dev/null 2>&1 || docker network create media-shared >/dev/null
vpn=(python3 "$repo_root/scripts/stack-compose.py" vpn)
download=(python3 "$repo_root/scripts/stack-compose.py" download)
"${vpn[@]}" config --quiet
"${download[@]}" config --quiet
"${vpn[@]}" up -d --wait --wait-timeout 120
vpn_namespace=$(docker exec gluetun readlink /proc/self/ns/net)
for client in qbittorrent metube jdownloader; do
  client_namespace=$(docker exec "$client" readlink /proc/self/ns/net 2>/dev/null || true)
  if [[ "$vpn_namespace" != "$client_namespace" ]]; then
    "${download[@]}" up -d --no-deps --force-recreate "$client"
  else
    "${download[@]}" up -d --no-deps "$client"
  fi
done
python3 "$repo_root/scripts/configure-qbittorrent-vpn.py"
