#!/usr/bin/env bash
# Compose post_start hook: apply extra-file import settings through the API.
set -euo pipefail
umask 077

case "${ARR_IMPORT_EXTRA_FILES:-false}" in
  true|false) import_extra_files=${ARR_IMPORT_EXTRA_FILES:-false} ;;
  *) echo 'ARR_IMPORT_EXTRA_FILES must be true or false.' >&2; exit 1 ;;
esac
extensions=$(jq -nr --arg value "${ARR_EXTRA_FILE_EXTENSIONS:-srt}" \
  '$value | split(",") | map(gsub("^\\s+|\\s+$"; "") | ltrimstr(".") | ascii_downcase) |
   map(select(length > 0)) | join(",")')
if [[ -n "$extensions" && ! "$extensions" =~ ^[a-z0-9]+(,[a-z0-9]+)*$ ]]; then
  echo 'Extra file extensions must be comma-separated suffixes, without paths.' >&2
  exit 1
fi
: "${ARR_MEDIA_API_URL:?ARR_MEDIA_API_URL is required}"
config_file=${ARR_CONFIG_FILE:-/config/config.xml}
workdir=$(mktemp -d /tmp/arr-media.XXXXXXXX)
trap 'rm -rf -- "$workdir"' EXIT
ready=false
for attempt in {1..60}; do
  api_key=$(sed -n 's|.*<ApiKey>\([^<]*\)</ApiKey>.*|\1|p' "$config_file" 2>/dev/null | head -n 1) || api_key=''
  if [[ -n "$api_key" ]] && curl --fail --silent --connect-timeout 2 --max-time 5 \
    --header "X-Api-Key: $api_key" "$ARR_MEDIA_API_URL" \
    --output "$workdir/current.json" 2>/dev/null; then
    ready=true
    break
  fi
  sleep 2
done
if [[ "$ready" != true ]]; then
  echo 'Media settings: API unavailable; no changes made.' >&2
  exit 1
fi
if jq --exit-status --argjson enabled "$import_extra_files" --arg extensions "$extensions" \
  '.importExtraFiles == $enabled and .extraFileExtensions == $extensions' \
  "$workdir/current.json" >/dev/null; then
  echo 'Extra-file import settings already configured.'
  exit 0
fi
jq --argjson enabled "$import_extra_files" --arg extensions "$extensions" \
  '.importExtraFiles = $enabled | .extraFileExtensions = $extensions' \
  "$workdir/current.json" > "$workdir/update.json"
if ! curl --fail --silent --connect-timeout 2 --max-time 15 \
  --request PUT --header "X-Api-Key: $api_key" --header 'Content-Type: application/json' \
  --data-binary "@$workdir/update.json" "$ARR_MEDIA_API_URL" \
  --output "$workdir/result.json"; then
  echo 'Extra-file import settings rejected by the API.' >&2
  exit 1
fi
curl --fail --silent --connect-timeout 2 --max-time 10 \
  --header "X-Api-Key: $api_key" "$ARR_MEDIA_API_URL" > "$workdir/verified.json"
jq --exit-status --argjson enabled "$import_extra_files" --arg extensions "$extensions" \
  '.importExtraFiles == $enabled and .extraFileExtensions == $extensions' \
  "$workdir/verified.json" >/dev/null
printf 'Extra-file import settings applied and verified.\n'
