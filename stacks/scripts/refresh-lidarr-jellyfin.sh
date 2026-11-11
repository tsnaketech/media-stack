#!/bin/sh
# Refresh only Jellyfin's music library after a Lidarr event.
set -eu

config=/config/jellyfin-connect.json
url=$(jq -er '.url | select(length > 0)' "$config")
token=$(jq -er '.api_key | select(length > 0)' "$config")
library=$(jq -er '.library_path | select(length > 0)' "$config")

jellyfin() {
    printf 'Authorization: MediaBrowser Token="%s"\n' "$token" |
        curl --fail --silent --show-error --max-time 15 --header @- "$@"
}

folders=$(jellyfin "$url/Library/VirtualFolders")
item_id=$(printf '%s' "$folders" | jq -er --arg path "$library" '
    [ .[] | select((.Locations // []) | index($path)) | .ItemId ]
    | select(length == 1) | .[0] | select(test("^[0-9a-fA-F-]+$"))
')

if [ "${lidarr_eventtype:-}" = Test ]; then
    echo "Jellyfin music library is reachable."
    exit 0
fi

status=$(jellyfin --request POST --output /dev/null --write-out '%{http_code}' \
    "$url/Items/$item_id/Refresh?Recursive=true&MetadataRefreshMode=Default&ImageRefreshMode=Default&ReplaceAllMetadata=false&ReplaceAllImages=false")
if [ "$status" != 204 ]; then
    echo "Unexpected Jellyfin refresh status: $status" >&2
    exit 1
fi
echo "Jellyfin music library refresh accepted (HTTP 204)."
