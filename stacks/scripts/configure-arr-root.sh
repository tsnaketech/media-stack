#!/usr/bin/env bash
# Compose post_start hook: register a media root without moving existing items.
set -euo pipefail
umask 077

[[ -n "${ARR_ROOT_FOLDER:-}" ]] || exit 0
if [[ "$ARR_ROOT_FOLDER" != /* || "$ARR_ROOT_FOLDER" == / ]]; then
  echo 'Media root must be an absolute directory other than /.' >&2
  exit 1
fi
: "${ARR_ROOT_API_URL:?ARR_ROOT_API_URL is required}"
workdir=$(mktemp -d /tmp/arr-root.XXXXXXXX)
trap 'rm -rf -- "$workdir"' EXIT
ready=false
for attempt in {1..60}; do
  api_key=$(sed -n 's|.*<ApiKey>\([^<]*\)</ApiKey>.*|\1|p' /config/config.xml 2>/dev/null | head -n 1) || api_key=''
  if [[ -n "$api_key" ]] && curl --fail --silent --connect-timeout 2 --max-time 5 \
    --header "X-Api-Key: $api_key" "$ARR_ROOT_API_URL" \
    --output "$workdir/roots.json" 2>/dev/null; then
    ready=true
    break
  fi
  sleep 2
done
if [[ "$ready" != true ]]; then
  echo 'Media root: API unavailable; no changes made.' >&2
  exit 1
fi
if jq --exit-status 'any(.[]; .path == env.ARR_ROOT_FOLDER)' "$workdir/roots.json" >/dev/null; then
  echo 'Media root already registered; existing settings preserved.'
  exit 0
fi
if [[ ! -d "$ARR_ROOT_FOLDER" ]]; then
  echo 'Media root directory is missing; check the volume mount.' >&2
  exit 1
fi
jq -n '{path: env.ARR_ROOT_FOLDER}' > "$workdir/new-root.json"
# Lidarr requires a name and valid default quality/metadata profiles.
if [[ "${ARR_ROOT_KIND:-}" == lidarr ]]; then
  api_base=${ARR_ROOT_API_URL%/rootfolder}
  for profile in qualityprofile metadataprofile; do
    curl --fail --silent --connect-timeout 2 --max-time 10 \
      --header "X-Api-Key: $api_key" "$api_base/$profile" > "$workdir/$profile.json"
  done
  quality_id=$(jq -er '.[0].id' "$workdir/qualityprofile.json")
  metadata_id=$(jq -er '.[0].id' "$workdir/metadataprofile.json")
  jq --argjson quality "$quality_id" --argjson metadata "$metadata_id" \
    '. + {name: "Music", defaultQualityProfileId: $quality,
          defaultMetadataProfileId: $metadata, defaultMonitorOption: "none",
          defaultNewItemMonitorOption: "none", defaultTags: []}' \
    "$workdir/new-root.json" > "$workdir/lidarr-root.json"
  mv "$workdir/lidarr-root.json" "$workdir/new-root.json"
fi
if ! curl --fail --silent --connect-timeout 2 --max-time 30 \
  --request POST --header "X-Api-Key: $api_key" --header 'Content-Type: application/json' \
  --data-binary "@$workdir/new-root.json" "$ARR_ROOT_API_URL" \
  --output "$workdir/result.json"; then
  echo 'Media root rejected by the API; check directory permissions and profiles.' >&2
  exit 1
fi
curl --fail --silent --connect-timeout 2 --max-time 10 \
  --header "X-Api-Key: $api_key" "$ARR_ROOT_API_URL" > "$workdir/verified.json"
jq --exit-status 'any(.[]; .path == env.ARR_ROOT_FOLDER)' "$workdir/verified.json" >/dev/null
printf 'Media root registered and verified: %s\n' "$ARR_ROOT_FOLDER"
