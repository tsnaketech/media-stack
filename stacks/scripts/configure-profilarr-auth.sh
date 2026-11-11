#!/usr/bin/env bash
# Apply local credentials through Profilarr's own authenticated form actions.
set -euo pipefail
umask 077
if [[ -z ${PROFILARR_PASSWORD:-} ]]; then
  echo 'Profilarr: empty password; existing account preserved.'
  exit 0
fi
PROFILARR_USERNAME=${PROFILARR_USERNAME:-}
if [[ ${#PROFILARR_USERNAME} -lt 3 || ${#PROFILARR_PASSWORD} -lt 8 ]]; then
  echo 'Profilarr: username needs 3 characters and password needs 8 characters.' >&2
  exit 1
fi
if [[ ${AUTH:-on} != on ]]; then
  echo 'Profilarr: credential configuration requires AUTH=on.' >&2
  exit 1
fi
origin=${ORIGIN:?ORIGIN is required}
host=${origin#*://}
host=${host%%/*}
base=http://127.0.0.1:6868
workdir=$(mktemp -d /tmp/profilarr-auth.XXXXXXXX)
trap 'rm -rf -- "$workdir"' EXIT
printf '%s' "$PROFILARR_USERNAME" > "$workdir/username"
printf '%s' "$PROFILARR_PASSWORD" > "$workdir/password"
printf '%s' "${PROFILARR_CURRENT_PASSWORD:-}" > "$workdir/current"
request() {
  curl --silent --show-error --connect-timeout 2 --max-time 15 \
    --header "Host: $host" --header "Origin: $origin" --header 'Accept: text/html' \
    --cookie "$workdir/cookies" --cookie-jar "$workdir/cookies" \
    --output "$workdir/response" --write-out '%{http_code}' "$@"
}
ready=false
for ((attempt=0; attempt<60; attempt++)); do
  status=$(request "$base/auth/setup") || status=000
  if [[ $status == 200 || $status == 303 ]]; then ready=true; break; fi
  sleep 2
done
if [[ $ready != true ]]; then echo 'Profilarr: service unavailable.' >&2; exit 1; fi
login() {
  local status
  rm -f "$workdir/cookies"
  status=$(request --data-urlencode "username@$workdir/username" \
    --data-urlencode "password@$1" "$base/auth/login")
  [[ $status == 303 ]] || return 1
  [[ $(request "$base/settings/security") == 200 ]]
}
if [[ $status == 200 ]]; then
  status=$(request --data-urlencode "username@$workdir/username" \
    --data-urlencode "password@$workdir/password" \
    --data-urlencode "confirmPassword@$workdir/password" "$base/auth/setup")
  if [[ $status != 303 ]]; then
    echo 'Profilarr: account creation refused; account unchanged.' >&2; exit 1
  fi
elif ! login "$workdir/password"; then
  if [[ ! -s $workdir/current ]] || ! login "$workdir/current"; then
    echo 'Profilarr: login refused. Keep the existing username and supply PROFILARR_CURRENT_PASSWORD for password rotation.' >&2
    exit 1
  fi
  status=$(request --data-urlencode "currentPassword@$workdir/current" \
    --data-urlencode "newPassword@$workdir/password" \
    --data-urlencode "confirmPassword@$workdir/password" \
    "$base/settings/security?/changePassword")
  if [[ $status != 200 ]]; then echo 'Profilarr: password change refused.' >&2; exit 1; fi
fi
if ! login "$workdir/password"; then
  echo 'Profilarr: credential verification failed.' >&2; exit 1
fi
echo 'Profilarr: local credentials applied and login verified.'
