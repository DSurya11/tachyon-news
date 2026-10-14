#!/usr/bin/env bash
# Stop the stock-news pipeline completely, and keep it stopped until scripts/up.sh (make up).
#
#   scripts/stop.sh        (or: make down / make stop)
#
# - ends a pipeline run in progress cleanly (the next run picks up where it left off)
# - stops the hourly pipeline and daily backup timers
# - stops OmniRoute, the API and the dashboard (systemd services and `make dev-up` ones)
# - stops the Postgres container (data is kept)
# - turns off start-at-login, so nothing comes back after a reboot until make up
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."

TIMERS=(stocknews-pipeline.timer stocknews-backup.timer)
SERVICES=(stocknews-pipeline.service stocknews-backup.service stocknews-api stocknews-dashboard stocknews-omniroute)

step() { printf '→ %s\n' "$*"; }

# "Stopped" wins over anything already in flight: a make deploy that finishes after this installs
# the new code but starts nothing while this marker exists (make up removes it).
mkdir -p .run && touch .run/stopped

if systemctl --user cat stocknews-api.service >/dev/null 2>&1; then
  if [ "$(systemctl --user show -p ActiveState --value stocknews-pipeline.service)" = activating ]; then
    step "Ending the pipeline run in progress"
  fi
  step "Stopping timers and services, and turning off start-at-login"
  systemctl --user disable --now "${TIMERS[@]}" >/dev/null 2>&1
  systemctl --user stop "${SERVICES[@]}" >/dev/null 2>&1
  systemctl --user disable stocknews-api stocknews-dashboard stocknews-omniroute >/dev/null 2>&1
fi

# Development services started with `make dev-up` (tracked by pid files).
for svc in frontend backend omniroute; do
  pidfile=".run/$svc.pid"
  if [ -f "$pidfile" ]; then
    kill "$(cat "$pidfile")" 2>/dev/null && step "Stopped $svc (make dev-up)"
    rm -f "$pidfile"
  fi
done

if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx stocknews-postgres; then
  step "Stopping Postgres (data is kept)"
  docker compose -f docker/docker-compose.yml stop postgres >/dev/null 2>&1
fi

# A pipeline started by hand in a terminal holds the run lock; it is not killed from here.
if [ -e logs/.pipeline.lock ] && ! flock -n logs/.pipeline.lock true 2>/dev/null; then
  echo "! A pipeline run started by hand is still going; stop it with Ctrl-C in its terminal."
fi

# Services can take a few seconds to let go of their ports.
listening() {
  local busy=()
  for port in 8080 3000 8000 20128 5432; do
    ss -ltn "sport = :$port" 2>/dev/null | grep -q LISTEN && busy+=("$port")
  done
  echo "${busy[*]}"
}
busy=$(listening)
for _ in $(seq 15); do [ -z "$busy" ] && break; sleep 1; busy=$(listening); done
if [ -n "$busy" ]; then
  echo "! Still listening on port(s): $busy — see what holds them: ss -ltnp | grep -E ':(${busy// /|})\b'"
  exit 1
fi
echo "✓ Stock-news is fully stopped and stays off after a reboot. Start it again with: make up"
