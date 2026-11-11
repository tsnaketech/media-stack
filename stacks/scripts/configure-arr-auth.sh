#!/usr/bin/env bash
# Compose post_start hook: apply optional credentials without logging secrets.
set -euo pipefail
umask 077

if [[ -z "${ARR_AUTH_PASSWORD:-}" ]]; then
  echo 'Authentification : mot de passe vide, compte existant conservé.'
  exit 0
fi
if [[ -z "${ARR_AUTH_USERNAME:-}" ]]; then
  echo 'Authentification : ARR_AUTH_USERNAME est requis avec ARR_AUTH_PASSWORD.' >&2
  exit 1
fi
: "${ARR_AUTH_API_URL:?ARR_AUTH_API_URL manquant}"

workdir=$(mktemp -d /tmp/arr-auth.XXXXXXXX)
trap 'rm -rf -- "$workdir"' EXIT
ready=false
for attempt in {1..60}; do
  api_key=$(sed -n 's|.*<ApiKey>\([^<]*\)</ApiKey>.*|\1|p' /config/config.xml 2>/dev/null | head -n 1) || api_key=''
  if [[ -n "$api_key" ]] && curl --fail --silent --connect-timeout 2 --max-time 5 \
    --header "X-Api-Key: $api_key" "$ARR_AUTH_API_URL" \
    --output "$workdir/current.json" 2>/dev/null; then
    ready=true
    break
  fi
  sleep 2
done
if [[ "$ready" != true ]]; then
  echo 'Authentification : API indisponible, identifiants non modifiés.' >&2
  exit 1
fi

jq '.username = env.ARR_AUTH_USERNAME | .password = env.ARR_AUTH_PASSWORD |
    if has("passwordConfirmation") then .passwordConfirmation = env.ARR_AUTH_PASSWORD else . end' \
  "$workdir/current.json" > "$workdir/update.json"

if ! curl --fail --silent --connect-timeout 2 --max-time 15 \
  --request PUT --header "X-Api-Key: $api_key" --header 'Content-Type: application/json' \
  --data-binary "@$workdir/update.json" "$ARR_AUTH_API_URL" \
  --output "$workdir/result.json"; then
  echo 'Authentification : API a refusé la modification ; vérifier les réglages.' >&2
  exit 1
fi
curl --fail --silent --connect-timeout 2 --max-time 10 \
  --header "X-Api-Key: $api_key" "$ARR_AUTH_API_URL" > "$workdir/verified.json"
jq --exit-status '.username == env.ARR_AUTH_USERNAME' "$workdir/verified.json" >/dev/null
printf 'Authentification : identifiants du .env appliqués et utilisateur vérifié.\n'
