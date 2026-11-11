#!/bin/sh
set -eu
node /app/merge-services.cjs
node /app/merge-services.cjs --watch &
exec docker-entrypoint.sh "$@"
