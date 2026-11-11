#!/usr/bin/env bash
# Reapply the pinned local theme on every LinuxServer container start.
set -euo pipefail
web_dir=/usr/share/jellyfin/web
assets=/opt/abyss-assets
ui_dir="$web_dir/ui"
index="$web_dir/index.html"
loader='<script src="ui/spotlight-loader.js" data-abyss-spotlight></script>'

[[ -f "$index" ]] || { echo 'Abyss: Jellyfin web directory is unavailable.' >&2; exit 1; }
for file in abyss.css abyss-je.css spotlight.html spotlight.css spotlight-loader.js LICENSE; do
  [[ -s "$assets/$file" ]] || { echo "Abyss: missing local asset $file." >&2; exit 1; }
done
mkdir -p "$ui_dir" /usr/share/doc/abyss-jellyfin
for file in abyss.css abyss-je.css spotlight.html spotlight.css spotlight-loader.js; do
  if ! cmp -s "$assets/$file" "$ui_dir/$file"; then
    install -m 0644 "$assets/$file" "$ui_dir/$file"
  fi
done
install -m 0644 "$assets/LICENSE" /usr/share/doc/abyss-jellyfin/LICENSE
html=$(<"$index")
html=${html//"$loader"/}
[[ "$html" == *'</body>'* ]] || { echo 'Abyss: index has no closing body tag.' >&2; exit 1; }
html=${html/<\/body>/${loader}<\/body>}
temporary=$(mktemp "$web_dir/.abyss-index.XXXXXX")
trap 'rm -f "$temporary"' EXIT
printf '%s\n' "$html" > "$temporary"
chmod --reference="$index" "$temporary"
chown --reference="$index" "$temporary"
mv -f "$temporary" "$index"
echo 'Abyss: local theme, Enhanced CSS and Spotlight installed.'
