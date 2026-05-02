#!/usr/bin/env bash
set -euo pipefail

cd /data/service/agentflow

PRIMARY="${CHROMIUM_PRIMARY_HOST:-44.223.72.154}"
SECONDARY="${CHROMIUM_SECONDARY_HOST:-3.238.79.147}"
SSH_USER="${CHROMIUM_SSH_USER:-ubuntu}"
SSH_KEY="${AGENTFLOW_SSH_KEY:-$HOME/.ssh/ops-cli-us-east-1.pem}"
REMOTE_CHROMIUM="${CHROMIUM_ROOT:-/home/ubuntu/campaigns/chromium}"
REMOTE_CAMPAIGN="${CHROMIUM_CAMPAIGN_ROOT:-/home/ubuntu/campaigns/chromium-agentflow}"
CHROME_BIN="$REMOTE_CHROMIUM/src/out/asan/chrome"
POLL_SECONDS="${CHROMIUM_WATCH_POLL_SECONDS:-300}"
AGENTFLOW_BIN="${AGENTFLOW_BIN:-/home/ubuntu/.local/bin/agentflow}"
RUN_LOG="${CHROMIUM_AGENTFLOW_RUN_LOG:-runs/chromium-transition/two_worker_agentflow_run.log}"
HEALTH_LOG="${CHROMIUM_AUDIT_HEALTH_LOG:-runs/chromium-transition/two_worker_health.log}"
PID_FILE="${CHROMIUM_WATCH_PID_FILE:-runs/chromium-transition/two_worker_watch.pid}"
STARTUP_TIMEOUT_SECONDS="${CHROMIUM_AUDIT_STARTUP_TIMEOUT_SECONDS:-1200}"
STARTUP_POLL_SECONDS="${CHROMIUM_AUDIT_STARTUP_POLL_SECONDS:-30}"
HEALTH_INTERVAL_SECONDS="${CHROMIUM_AUDIT_HEALTH_INTERVAL_SECONDS:-300}"
UNHEALTHY_LIMIT="${CHROMIUM_AUDIT_UNHEALTHY_LIMIT:-3}"
MAX_RESTARTS="${CHROMIUM_AUDIT_MAX_RESTARTS:-3}"
PROGRESS_STALE_SECONDS="${CHROMIUM_PROGRESS_STALE_SECONDS:-900}"
CAMPAIGN_ROUND_SLEEP_SECONDS="${CHROMIUM_CAMPAIGN_ROUND_SLEEP_SECONDS:-60}"
MAX_CAMPAIGN_ROUNDS="${CHROMIUM_MAX_CAMPAIGN_ROUNDS:-0}"
CODEX_AUDIT_PATTERN='[c]odex exec .*--model moonshotai/kimi-k2.5'

mkdir -p runs/chromium-transition
if [[ -s "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${old_pid:-}" && "$old_pid" != "$$" ]] && kill -0 "$old_pid" 2>/dev/null; then
    echo "[$(date -Is)] another two-worker watcher is already running pid=$old_pid"
    exit 0
  fi
fi
echo "$$" > "$PID_FILE"
trap 'rm -f "$PID_FILE"' EXIT

ssh_remote() {
  local host="$1"
  shift
  ssh -i "$SSH_KEY" \
    -o BatchMode=yes \
    -o ConnectTimeout=20 \
    -o ServerAliveInterval=15 \
    -o ServerAliveCountMax=2 \
    -o StrictHostKeyChecking=accept-new \
    "$SSH_USER@$host" "$@"
}

timestamp() {
  date -Is
}

log_health() {
  echo "[$(timestamp)] $*" | tee -a "$HEALTH_LOG"
}

remote_preflight() {
  local host="$1"
  log_health "preflight host=$host"
  ssh_remote "$host" "set -euo pipefail
test -x $(printf '%q' "$CHROME_BIN")
test -x /home/ubuntu/bin/codex-openrouter
test -s /home/ubuntu/.openrouter_env
test -d $(printf '%q' "$REMOTE_CAMPAIGN")
free -h | sed -n '1,2p'
df -h /
echo PREFLIGHT_OK"
}

remote_audit_active() {
  local host="$1"
  ssh_remote "$host" "pgrep -af $(printf '%q' "$CODEX_AUDIT_PATTERN") >/dev/null"
}

remote_audit_snapshot() {
  local host="$1"
  ssh_remote "$host" "set -euo pipefail
echo 'host='\"\$(hostname)\"
pgrep -af $(printf '%q' "$CODEX_AUDIT_PATTERN") || true
find $(printf '%q' "$REMOTE_CAMPAIGN")/agents -maxdepth 2 -type f \( -name input.html -o -name repro.py -o -name chrome_stderr.log \) -printf '%TY-%Tm-%TdT%TH:%TM %p\n' 2>/dev/null | sort | tail -12 || true"
}

remote_stop_auditors() {
  local host="$1"
  log_health "stopping stale remote auditors before new campaign host=$host"
  ssh_remote "$host" "pkill -TERM -f $(printf '%q' "$CODEX_AUDIT_PATTERN") || true
sleep 5
pkill -KILL -f $(printf '%q' "$CODEX_AUDIT_PATTERN") || true" || true
}

remote_sanitize_crash_registry() {
  local host="$1"
  log_health "sanitizing crash registry host=$host"
  ssh_remote "$host" "REMOTE_CAMPAIGN=$(printf '%q' "$REMOTE_CAMPAIGN") python3 - <<'PY'
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

root = Path(os.environ['REMOTE_CAMPAIGN'])
readme = root / 'crashes' / 'README.md'
if not readme.exists():
    raise SystemExit(0)

original = readme.read_text(encoding='utf-8', errors='replace')
kept = []
removed = []
for line in original.splitlines():
    if not line.startswith('|') or line.startswith('|---') or line.startswith('| Timestamp '):
        kept.append(line)
        continue

    columns = [part.strip() for part in line.strip().strip('|').split('|')]
    if len(columns) < 4:
        kept.append(line)
        continue
    evidence = columns[2]
    artifact = columns[3]
    if evidence.startswith('No crashes found') or not artifact.startswith('crashes/'):
        removed.append(line)
        continue
    artifact_path = Path(artifact)
    if not artifact_path.is_absolute():
        artifact_path = root / artifact_path
    if not artifact_path.exists():
        removed.append(line)
        continue
    kept.append(line)

if not removed:
    raise SystemExit(0)

timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup = root / f'crashes/README.md.bak.{timestamp}'
backup.write_text(original, encoding='utf-8')
readme.write_text('\n'.join(kept).rstrip() + '\n', encoding='utf-8')
for line in removed:
    print(f'non-crash registry row or missing crash artifact: {line}')
print(f'crash registry backup: {backup}')
PY" >> "$HEALTH_LOG" 2>&1 || true
}

run_progress_snapshot() {
  python3 - "$PROGRESS_STALE_SECONDS" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

stale_seconds = int(sys.argv[1])
runs_dir = Path(".agentflow/runs")
terminal = {"completed", "failed", "cancelled", "skipped"}

run_paths = sorted(
    runs_dir.glob("*/run.json"),
    key=lambda path: path.stat().st_mtime,
    reverse=True,
)
payload = None
run_dir = None
for path in run_paths:
    candidate = json.loads(path.read_text(encoding="utf-8"))
    if candidate.get("status") == "running":
        payload = candidate
        run_dir = path.parent
        break

if payload is None or run_dir is None:
    print("run_id=none run_status=none progress_ok=0 active_nodes=0 pending_nodes=0 unfinished_primary=0 unfinished_secondary=0 recent_trace_age=999999")
    raise SystemExit(0)

nodes = payload.get("nodes") or {}
inferred_statuses = {
    node_id: node.get("status")
    for node_id, node in nodes.items()
    if node_id.startswith("chromium_")
}
latest_trace = None

events_path = run_dir / "events.jsonl"
if events_path.exists():
    with events_path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_type = event.get("type")
            node_id = event.get("node_id") or ""
            if not node_id.startswith("chromium_"):
                continue

            if event_type == "node_started":
                inferred_statuses[node_id] = "running"
            elif event_type == "node_completed":
                inferred_statuses[node_id] = "completed"
            elif event_type == "node_failed":
                inferred_statuses[node_id] = "failed"
            elif event_type == "node_cancelled":
                inferred_statuses[node_id] = "cancelled"
            elif event_type == "node_trace":
                if inferred_statuses.get(node_id) in {None, "pending"}:
                    inferred_statuses[node_id] = "running"
            else:
                continue

            if event_type != "node_trace":
                continue
            timestamp = event.get("timestamp")
            if not timestamp:
                continue
            try:
                parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            else:
                parsed = parsed.astimezone(timezone.utc)
            latest_trace = parsed if latest_trace is None else max(latest_trace, parsed)

active_nodes = 0
pending_nodes = 0
unfinished_primary = 0
unfinished_secondary = 0
for node_id, status in inferred_statuses.items():
    if status == "running":
        active_nodes += 1
    if status == "pending":
        pending_nodes += 1
    if status not in terminal:
        try:
            index = int(node_id.rsplit("_", 1)[1])
        except (IndexError, ValueError):
            index = 0
        if index % 2 == 0:
            unfinished_primary += 1
        else:
            unfinished_secondary += 1

if latest_trace is None:
    recent_trace_age = 999999
else:
    recent_trace_age = int((datetime.now(timezone.utc) - latest_trace).total_seconds())

progress_ok = int((active_nodes + pending_nodes) > 0 or recent_trace_age <= stale_seconds)
print(
    f"run_id={payload.get('id')} run_status={payload.get('status')} progress_ok={progress_ok} "
    f"active_nodes={active_nodes} pending_nodes={pending_nodes} "
    f"unfinished_primary={unfinished_primary} unfinished_secondary={unfinished_secondary} "
    f"recent_trace_age={recent_trace_age}"
)
PY
}

wait_process() {
  local pid="$1"
  local rc=0
  set +e
  wait "$pid"
  rc=$?
  set -e
  return "$rc"
}

stop_campaign_process() {
  local pid="$1"
  if kill -0 "$pid" 2>/dev/null; then
    log_health "stopping local agentflow pid=$pid"
    kill "$pid" 2>/dev/null || true
    sleep 20
  fi
  if kill -0 "$pid" 2>/dev/null; then
    log_health "force stopping local agentflow pid=$pid"
    kill -9 "$pid" 2>/dev/null || true
  fi
  wait_process "$pid" || true
}

start_campaign_once() {
  log_health "starting two-worker AgentFlow campaign log=$RUN_LOG" >&2
  remote_stop_auditors "$PRIMARY" >&2
  remote_stop_auditors "$SECONDARY" >&2
  remote_sanitize_crash_registry "$PRIMARY" >&2
  remote_sanitize_crash_registry "$SECONDARY" >&2
  export CHROMIUM_WORKER_HOSTS="$PRIMARY,$SECONDARY"
  export CHROMIUM_SHARD_COUNT="${CHROMIUM_SHARD_COUNT:-24}"
  export CHROMIUM_CONCURRENCY="${CHROMIUM_CONCURRENCY:-4}"
  export AGENTFLOW_SSH_KEY="$SSH_KEY"
  mkdir -p runs/chromium-kimi-agentflow "$(dirname "$RUN_LOG")"
  "$AGENTFLOW_BIN" run examples/chromium_kimi_campaign.py >> "$RUN_LOG" 2>&1 &
  echo "$!"
}

wait_for_both_auditors() {
  local pid="$1"
  local deadline=$((SECONDS + STARTUP_TIMEOUT_SECONDS))
  while (( SECONDS < deadline )); do
    local primary_active=0
    local secondary_active=0
    remote_audit_active "$PRIMARY" && primary_active=1 || true
    remote_audit_active "$SECONDARY" && secondary_active=1 || true
    log_health "startup health pid=$pid primary_active=$primary_active secondary_active=$secondary_active"
    if [[ "$primary_active" -eq 1 && "$secondary_active" -eq 1 ]]; then
      log_health "both workers have active Codex audit processes"
      remote_audit_snapshot "$PRIMARY" >> "$HEALTH_LOG" 2>&1 || true
      remote_audit_snapshot "$SECONDARY" >> "$HEALTH_LOG" 2>&1 || true
      return 0
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      local rc=0
      wait_process "$pid" || rc=$?
      log_health "campaign exited before both workers became active rc=$rc"
      return 125
    fi
    sleep "$STARTUP_POLL_SECONDS"
  done
  log_health "startup timeout waiting for both workers"
  remote_audit_snapshot "$PRIMARY" >> "$HEALTH_LOG" 2>&1 || true
  remote_audit_snapshot "$SECONDARY" >> "$HEALTH_LOG" 2>&1 || true
  return 124
}

monitor_campaign() {
  local pid="$1"
  local unhealthy=0
  while kill -0 "$pid" 2>/dev/null; do
    sleep "$HEALTH_INTERVAL_SECONDS"
    local primary_active=0
    local secondary_active=0
    remote_audit_active "$PRIMARY" && primary_active=1 || true
    remote_audit_active "$SECONDARY" && secondary_active=1 || true
    local snapshot
    snapshot="$(run_progress_snapshot || true)"
    log_health "runtime health pid=$pid primary_active=$primary_active secondary_active=$secondary_active $snapshot"
    if [[ "$primary_active" -eq 1 && "$secondary_active" -eq 1 ]]; then
      unhealthy=0
      continue
    fi
    active_total=$((primary_active + secondary_active))
    if [[ "$active_total" -ge 1 && "$snapshot" == *"progress_ok=1"* ]]; then
      if [[ "$primary_active" -eq 0 && "$snapshot" != *"unfinished_primary=0"* ]]; then
        :
      elif [[ "$secondary_active" -eq 0 && "$snapshot" != *"unfinished_secondary=0"* ]]; then
        :
      else
        log_health "runtime health degraded but progressing pid=$pid active_total=$active_total $snapshot"
        unhealthy=0
        continue
      fi
    fi
    unhealthy=$((unhealthy + 1))
    remote_audit_snapshot "$PRIMARY" >> "$HEALTH_LOG" 2>&1 || true
    remote_audit_snapshot "$SECONDARY" >> "$HEALTH_LOG" 2>&1 || true
    if (( unhealthy >= UNHEALTHY_LIMIT )); then
      log_health "campaign unhealthy for $unhealthy consecutive checks"
      stop_campaign_process "$pid"
      return 1
    fi
  done
  wait_process "$pid"
}

supervise_campaign() {
  remote_preflight "$PRIMARY"
  remote_preflight "$SECONDARY"

  local attempt=1
  while (( attempt <= MAX_RESTARTS )); do
    log_health "campaign attempt=$attempt max=$MAX_RESTARTS"
    local pid
    pid="$(start_campaign_once)"
    local startup_rc=0
    wait_for_both_auditors "$pid" || startup_rc=$?
    if [[ "$startup_rc" -ne 0 ]]; then
      log_health "campaign startup failed rc=$startup_rc"
      stop_campaign_process "$pid"
    else
      local run_rc=0
      monitor_campaign "$pid" || run_rc=$?
      log_health "campaign exited rc=$run_rc"
      if [[ "$run_rc" -eq 0 ]]; then
        return 0
      fi
    fi

    attempt=$((attempt + 1))
    if (( attempt <= MAX_RESTARTS )); then
      log_health "restarting campaign after 60s"
      sleep 60
    fi
  done

  log_health "campaign failed after $MAX_RESTARTS attempts"
  return 1
}

echo "[$(timestamp)] watcher started primary=$PRIMARY secondary=$SECONDARY"

while true; do
  chrome_status=0
  ssh_remote "$PRIMARY" "test -x $(printf '%q' "$CHROME_BIN")" || chrome_status=$?
  if [[ "$chrome_status" -eq 0 ]]; then
    echo "[$(timestamp)] primary chrome ready"
    break
  fi
  if [[ "$chrome_status" -eq 255 ]]; then
    echo "[$(timestamp)] primary ssh unavailable while checking chrome; retrying"
    sleep "$POLL_SECONDS"
    continue
  fi

  build_status=0
  ssh_remote "$PRIMARY" "pgrep -af '[c]hromium_build.sh|[f]etch --nohooks chromium|[g]client sync --nohooks|[a]utoninja -C out/asan chrome' >/dev/null" || build_status=$?
  if [[ "$build_status" -eq 0 ]]; then
    echo "[$(timestamp)] primary still building"
    ssh_remote "$PRIMARY" "python3 - <<'PY'
from pathlib import Path
text = Path('/home/ubuntu/chromium_build.log').read_text(errors='replace')[-20000:]
parts = [part.strip() for part in text.replace('\r', '\n').splitlines() if part.strip()]
for line in parts[-8:]:
    print(line[:240])
PY" || echo "[$(timestamp)] primary build log unavailable; retrying"
    sleep "$POLL_SECONDS"
    continue
  fi
  if [[ "$build_status" -eq 255 ]]; then
    echo "[$(timestamp)] primary ssh unavailable while checking build process; retrying"
    sleep "$POLL_SECONDS"
    continue
  fi

  echo "[$(timestamp)] primary chrome not ready and no build process is running" >&2
  ssh_remote "$PRIMARY" "tail -80 /home/ubuntu/chromium_build.log || true" >&2
  exit 1
done

if ssh_remote "$SECONDARY" "test -x $(printf '%q' "$CHROME_BIN")"; then
  echo "[$(timestamp)] secondary chrome already ready"
else
  echo "[$(timestamp)] syncing chromium tree from primary to secondary"
  ssh_remote "$PRIMARY" "command -v rsync >/dev/null || (sudo apt-get update && sudo apt-get install -y rsync)"
  ssh_remote "$SECONDARY" "command -v rsync >/dev/null || (sudo apt-get update && sudo apt-get install -y rsync); mkdir -p $(printf '%q' "$REMOTE_CHROMIUM") $(printf '%q' "$REMOTE_CAMPAIGN")"
  SECONDARY_PRIVATE_IP="$(ssh_remote "$SECONDARY" "hostname -I | cut -d' ' -f1")"
  SYNC_PUBKEY="$(ssh_remote "$PRIMARY" "set -e; mkdir -p ~/.ssh; if [ ! -f ~/.ssh/chromium_sync_ed25519 ]; then ssh-keygen -t ed25519 -N '' -f ~/.ssh/chromium_sync_ed25519 >/dev/null; fi; cat ~/.ssh/chromium_sync_ed25519.pub")"
  ssh_remote "$SECONDARY" "set -e; mkdir -p ~/.ssh; touch ~/.ssh/authorized_keys; grep -qxF $(printf '%q' "$SYNC_PUBKEY") ~/.ssh/authorized_keys || echo $(printf '%q' "$SYNC_PUBKEY") >> ~/.ssh/authorized_keys; chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys"
  ssh_remote "$PRIMARY" "set -e; rsync -az --delete -e 'ssh -i ~/.ssh/chromium_sync_ed25519 -o StrictHostKeyChecking=accept-new' $(printf '%q' "$REMOTE_CHROMIUM")/ $SSH_USER@$SECONDARY_PRIVATE_IP:$(printf '%q' "$REMOTE_CHROMIUM")/"
  echo "[$(timestamp)] chromium tree sync complete"
fi

if ! ssh_remote "$SECONDARY" "test -x $(printf '%q' "$CHROME_BIN")"; then
  echo "[$(timestamp)] secondary chrome still missing after sync" >&2
  exit 1
fi

round=1
while true; do
  if (( MAX_CAMPAIGN_ROUNDS > 0 && round > MAX_CAMPAIGN_ROUNDS )); then
    log_health "campaign round limit reached max=$MAX_CAMPAIGN_ROUNDS"
    exit 0
  fi

  log_health "campaign round=$round starting"
  round_rc=0
  supervise_campaign || round_rc=$?
  log_health "campaign round=$round exited rc=$round_rc"
  round=$((round + 1))
  log_health "sleeping ${CAMPAIGN_ROUND_SLEEP_SECONDS}s before next campaign round"
  sleep "$CAMPAIGN_ROUND_SLEEP_SECONDS"
done
