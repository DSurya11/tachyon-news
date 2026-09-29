#!/usr/bin/env bash
# Kept for old habits: everything now starts with scripts/up.sh (make up).
exec "$(dirname "$(readlink -f "$0")")/up.sh" "$@"
