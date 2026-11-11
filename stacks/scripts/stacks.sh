#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"
stacks=(vpn indexer download shared music movie tv audiobook book)
extra_output=$(python3 scripts/stack-compose.py --list)
extra_stacks=()
if [[ -n "$extra_output" ]]; then
  mapfile -t extra_stacks <<< "$extra_output"
fi
stacks+=("${extra_stacks[@]}")
action=${1:-status}
if [[ $# -gt 0 ]]; then shift; fi
with_infra=false
with_vpn=false
usage() {
  echo "Usage: $0 {validate|up|status|logs} [--with-infra] [--with-vpn]" >&2
}
while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-infra) with_infra=true ;;
    --with-vpn) with_vpn=true ;;
    *) usage; exit 2 ;;
  esac
  shift
done
if [[ "$with_vpn" == true ]]; then
  : # Compatibility flag: VPN is now a required dependency.
fi
if [[ "$with_infra" == true ]]; then
  infra_root=${INFRA_ROOT:-$(dirname "$repo_root")}
  stacks+=("$infra_root/traefik" "$infra_root/arcane" "$infra_root/dozzle" "$infra_root/homepage")
fi
validate() {
  for stack in "${stacks[@]}"; do
    python3 "$repo_root/scripts/stack-compose.py" "$stack" config --quiet
    echo "$stack: configuration valide"
  done
}
case "$action" in
  validate) validate ;;
  up)
    init_args=(up)
    if [[ "$with_infra" == true ]]; then init_args+=(--with-infra); fi
    python3 scripts/initialize.py "${init_args[@]}"
    ;;
  status)
    for stack in "${stacks[@]}"; do
      echo "$stack"
      python3 "$repo_root/scripts/stack-compose.py" "$stack" ps -a
    done
    ;;
  logs)
    for stack in "${stacks[@]}"; do
      python3 "$repo_root/scripts/stack-compose.py" "$stack" logs --since=5m --tail=30
    done
    ;;
  *) usage; exit 2 ;;
esac
