#!/usr/bin/env bash
# Bring the whole stock-news setup up with one command, then check it end to end.
#
#   scripts/up.sh          (or: make up)
#
# - first run: make setup (venv, dependencies, browser, .env), then stops so .env can be filled in
# - Docker and the Postgres container (data kept between runs), tables created or upgraded
# - the production services under systemd: OmniRoute, the API (:8080), the local dashboard (:3000)
# - the hourly pipeline and daily backup timers (a run missed while the laptop was off or asleep
#   starts straight away)
# - installs everything first (tests, build, snapshot: make deploy) if it was never deployed
# - keeps the services running without a login session, so they come back after a reboot
# - the Tailscale Funnel the hosted dashboard reaches the API through
# - finally `make doctor`: every part, including the hosted site, checked from outside
#
# Safe to run any time: whatever is already up is left alone. scripts/stop.sh (make down) undoes it.
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."

API_PORT=8080
DASH_PORT=3000
TIMERS=(stocknews-pipeline.timer stocknews-backup.timer)
SERVICES=(stocknews-omniroute stocknews-api stocknews-dashboard)

step() { printf '→ %s\n' "$*"; }
warn() { printf '! %s\n' "$*"; }
die()  { printf '✗ %s\n' "$*"; exit 1; }
wait_for() {  # wait_for <seconds> <command...>
  local secs=$1; shift
  for _ in $(seq "$secs"); do "$@" >/dev/null 2>&1 && return 0; sleep 1; done
  return 1
}
env_value() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"'"'"; }

# 0. First run on this machine: Python environment, dependencies, browser, .env ----------------------
if [ ! -x venv/bin/python ]; then
  step "First run: setting up (Python environment, dependencies, browser)"
  make --no-print-directory setup || die "make setup failed; see above."
fi
[ -f .env ] || cp .env.example .env
if cmp -s .env .env.example; then
  die "Fill in .env first (template copied; see README → Configuration), then run make up again."
fi

rm -f .run/stopped   # make down's "stay stopped" marker: up means up

# 1. Docker and Postgres ---------------------------------------------------------------------------
if ! docker info >/dev/null 2>&1; then
  step "Starting Docker (asks for your password)"
  sudo systemctl start docker || die "Docker could not be started."
  wait_for 30 docker info || die "Docker didn't come up."
fi
step "Postgres"
docker compose -f docker/docker-compose.yml up -d postgres >/dev/null 2>&1 || die "Docker could not start Postgres."
wait_for 60 docker exec stocknews-postgres pg_isready -U postgres -d stocknews || die "Postgres didn't become ready."
venv/bin/python -m pipeline.db.local >/dev/null 2>&1 || die "Couldn't create the tables: venv/bin/python -m pipeline.db.local"

# 2. Install on first use --------------------------------------------------------------------------
if ! systemctl --user cat stocknews-api.service >/dev/null 2>&1 || [ ! -f "$HOME/.local/share/stock-news-pipeline/release/RELEASE" ]; then
  step "Not installed yet: running make deploy (tests, build, snapshot, systemd units)"
  make --no-print-directory deploy || die "make deploy failed; see above."
fi

# 3. Services and timers ---------------------------------------------------------------------------
step "OmniRoute, API, dashboard, hourly pipeline and daily backup"
systemctl --user enable --now "${SERVICES[@]}" "${TIMERS[@]}" >/dev/null 2>&1 \
  || die "systemd could not start the services: systemctl --user status 'stocknews-*'"
for svc in "${SERVICES[@]}"; do   # anything that had crashed gets another go
  systemctl --user is-active --quiet "$svc" || systemctl --user restart "$svc"
done

# Without "linger", user services stop at logout and don't start after a reboot until you log in.
if [ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)" != yes ]; then
  if loginctl enable-linger "$USER" 2>/dev/null; then
    step "Services now start at boot, without waiting for a login"
  else
    warn "Couldn't turn on start-at-boot (loginctl enable-linger $USER); services start when you log in."
  fi
fi

# 4. Tailscale Funnel (the hosted dashboard's way in) ----------------------------------------------
if command -v tailscale >/dev/null 2>&1; then
  if ! tailscale status >/dev/null 2>&1; then
    step "Connecting Tailscale"
    tailscale up >/dev/null 2>&1 || sudo tailscale up || warn "Tailscale isn't connected: the hosted dashboard can't reach this laptop."
  fi
  if ! tailscale funnel status 2>/dev/null | grep -q "127.0.0.1:$API_PORT"; then
    step "Opening the Tailscale Funnel to the API (:$API_PORT)"
    tailscale funnel --bg "$API_PORT" >/dev/null 2>&1 || warn "Couldn't open the Funnel: tailscale funnel --bg $API_PORT"
  fi
else
  warn "Tailscale isn't installed: only this laptop can use the dashboard."
fi

# 5. Wait until it answers -------------------------------------------------------------------------
step "Waiting for the API, dashboard and OmniRoute"
wait_for 45 curl -sf "http://127.0.0.1:$API_PORT/health" || warn "The API isn't answering yet: journalctl --user -u stocknews-api -e"
wait_for 20 curl -sf -o /dev/null "http://127.0.0.1:$DASH_PORT/" || warn "The dashboard isn't answering yet: journalctl --user -u stocknews-dashboard -e"
omniroute=$(env_value OMNIROUTE_API_URL); omniroute=${omniroute:-http://localhost:8000/v1}
# Any HTTP answer will do (it wants a key): OmniRoute takes several seconds longer to start than the API.
wait_for 90 curl -s -o /dev/null "${omniroute%/}/models" || warn "OmniRoute isn't answering yet: journalctl --user -u stocknews-omniroute -e"
public_api=$(env_value PUBLIC_API_URL)
[ -n "$public_api" ] && { wait_for 30 curl -sf "${public_api%/}/health" || true; }  # the Funnel takes a moment after a restart

# 6. Check everything ------------------------------------------------------------------------------
echo
venv/bin/python -m pipeline.ops.doctor
status=$?
site=$(env_value PUBLIC_SITE_URL)
next=$(systemctl --user show stocknews-pipeline.timer -p NextElapseUSecRealtime --value 2>/dev/null)
echo
if [ "$status" -eq 0 ]; then
  echo "✓ Everything is up. ${site:+Dashboard $site · }local http://localhost:$DASH_PORT · next pipeline run: ${next:-?}"
else
  echo "! Up, but make doctor found problems (above)."
fi
if systemctl --user is-active --quiet stocknews-pipeline.service; then
  echo "  A pipeline run is in progress now (catching up): make logs"
fi
exit "$status"
