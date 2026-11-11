#!/usr/bin/env bash
# Start the VPN first and reconnect clients if their network namespace changed.
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p "$repo_root/../runtime/locks"
exec 9>"$repo_root/../runtime/locks/vpn.lock"
flock -w 180 9 || { echo "Another VPN reconciliation is still running." >&2; exit 1; }
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
[[ $(docker inspect --format '{{.State.Health.Status}}' gluetun) == healthy ]] || {
  echo "Gluetun is no longer healthy." >&2; exit 1;
}
vpn_namespace=$(docker exec gluetun readlink /proc/self/ns/net)
for client in qbittorrent metube jdownloader; do
  [[ $(docker exec "$client" readlink /proc/self/ns/net) == "$vpn_namespace" ]] || {
    echo "$client: VPN namespace verification failed." >&2; exit 1;
  }
done
echo "VPN ready: all three clients share Gluetun's network namespace."
