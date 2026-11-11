#!/bin/sh
# Configure the native download destination before JDownloader starts.
set -eu
settings=/config/cfg/org.jdownloader.settings.GeneralSettings.json
mkdir -p /config/cfg
temporary=$(mktemp "${settings}.XXXXXX")
trap 'rm -f "$temporary"' EXIT HUP INT TERM
if [ -f "$settings" ]; then
  jq --arg path "${JDOWNLOADER_DOWNLOAD_PATH:-/output}" '.defaultdownloadfolder = $path' "$settings" > "$temporary"
else
  jq -n --arg path "${JDOWNLOADER_DOWNLOAD_PATH:-/output}" '{defaultdownloadfolder: $path}' > "$temporary"
fi
chmod 600 "$temporary"
chown "${USER_ID:-1000}:${GROUP_ID:-1000}" "$temporary"
mv "$temporary" "$settings"

# Preserve custom rules and configure only the two built-in folder rules.
subfolders=${JDOWNLOADER_SUBFOLDERS:-false}
case "$subfolders" in
  true|false) ;;
  *) echo 'JDOWNLOADER_SUBFOLDERS must be true or false.' >&2; exit 1 ;;
esac
settings=/config/cfg/org.jdownloader.controlling.packagizer.PackagizerSettings.rulelist.json
temporary=$(mktemp "${settings}.XXXXXX")
if [ -f "$settings" ]; then
  input=$settings
else
  input=/dev/null
fi
jq -s --argjson enabled "$subfolders" '
  (.[0] // []) |
  reduce ["SubFolderByPackageRule", "SubFolderByPluginRule"][] as $id
    (. ; if any(.[]; .id == $id)
         then map(if .id == $id then .enabled = $enabled else . end)
         else . + [{id: $id, enabled: $enabled, staticRule: true}] end)
' "$input" > "$temporary"
chmod 600 "$temporary"
chown "${USER_ID:-1000}:${GROUP_ID:-1000}" "$temporary"
mv "$temporary" "$settings"
