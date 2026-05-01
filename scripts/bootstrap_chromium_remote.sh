#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/bootstrap_chromium_remote.sh HOST [--build]

Prepares a remote Ubuntu worker for the Chromium AgentFlow campaign.

Environment:
  AGENTFLOW_SSH_KEY          SSH key path (default: ~/.ssh/ops-cli-us-east-1.pem)
  CHROMIUM_SSH_USER          SSH user (default: ubuntu)
  CHROMIUM_CAMPAIGN_ROOT     Remote campaign root (default: /home/ubuntu/campaigns/chromium-agentflow)
  CHROMIUM_ROOT              Remote Chromium checkout root (default: /home/ubuntu/campaigns/chromium)
  CHROMIUM_MODEL             Codex/OpenRouter model (default: moonshotai/kimi-k2.5)
EOF
}

HOST=""
DO_BUILD=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --build)
      DO_BUILD=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [[ -n "$HOST" ]]; then
        echo "only one HOST is supported per invocation" >&2
        exit 2
      fi
      HOST="$1"
      shift
      ;;
  esac
done

if [[ -z "$HOST" ]]; then
  usage >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
KEY="${AGENTFLOW_SSH_KEY:-$HOME/.ssh/ops-cli-us-east-1.pem}"
USER="${CHROMIUM_SSH_USER:-ubuntu}"
REMOTE_ROOT="${CHROMIUM_CAMPAIGN_ROOT:-/home/ubuntu/campaigns/chromium-agentflow}"
CHROMIUM_ROOT="${CHROMIUM_ROOT:-/home/ubuntu/campaigns/chromium}"
MODEL="${CHROMIUM_MODEL:-moonshotai/kimi-k2.5}"
DEST="${USER}@${HOST}"
SSH=(ssh -i "$KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$DEST")

"${SSH[@]}" "mkdir -p $(printf '%q' "$REMOTE_ROOT")/agent_template"

if command -v rsync >/dev/null 2>&1; then
  rsync -az -e "ssh -i $KEY -o BatchMode=yes -o StrictHostKeyChecking=accept-new" \
    "$REPO_ROOT/campaigns/chromium/agent_template/" \
    "$DEST:$REMOTE_ROOT/agent_template/"
else
  tar -C "$REPO_ROOT/campaigns/chromium/agent_template" -cf - . | \
    "${SSH[@]}" "cd $(printf '%q' "$REMOTE_ROOT")/agent_template && tar xf -"
fi

"${SSH[@]}" \
  "REMOTE_ROOT=$(printf '%q' "$REMOTE_ROOT") CHROMIUM_ROOT=$(printf '%q' "$CHROMIUM_ROOT") MODEL=$(printf '%q' "$MODEL") DO_BUILD=$DO_BUILD bash -s" <<'REMOTE'
set -euo pipefail

export PATH="$HOME/.npm-global/bin:$HOME/depot_tools:$PATH"

mkdir -p "$HOME/.npm-global" "$HOME/bin" "$HOME/.codex" "$REMOTE_ROOT"/{agents,docs,crashes,locks}
npm config set prefix "$HOME/.npm-global" >/dev/null

if ! command -v codex >/dev/null 2>&1; then
  npm install -g @openai/codex
fi

cat > "$HOME/.codex/config.toml" <<EOF
model = "$MODEL"
model_provider = "openrouter"
approval_policy = "never"
sandbox_mode = "danger-full-access"
model_reasoning_effort = "high"

[model_providers.openrouter]
name = "openrouter"
base_url = "https://openrouter.ai/api/v1"
env_key = "OPENROUTER_API_KEY"
wire_api = "responses"

[profiles.agentflow]
model = "$MODEL"
model_provider = "openrouter"
approval_policy = "never"
sandbox_mode = "danger-full-access"
model_reasoning_effort = "high"
EOF

cat > "$HOME/bin/codex-openrouter" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ -f "$HOME/.openrouter_env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.openrouter_env"
fi
export PATH="$HOME/.npm-global/bin:$PATH"
exec codex "$@"
EOF
chmod +x "$HOME/bin/codex-openrouter"

python3 -m pip install --user --break-system-packages playwright >/dev/null
python3 -m playwright install-deps chromium >/dev/null || true

if [[ ! -d "$HOME/depot_tools/.git" ]]; then
  git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git "$HOME/depot_tools"
fi

if [[ "$DO_BUILD" == "1" ]]; then
  mkdir -p "$CHROMIUM_ROOT"
  if [[ ! -d "$CHROMIUM_ROOT/src/.git" ]]; then
    cd "$CHROMIUM_ROOT"
    fetch --nohooks chromium
  fi

  cd "$CHROMIUM_ROOT/src"
  sudo ./build/install-build-deps.sh --no-prompt
  gclient sync --nohooks
  gclient runhooks
  gn gen out/asan --args='is_debug=false is_asan=true is_lsan=false is_ubsan_security=true symbol_level=1 blink_symbol_level=1 v8_symbol_level=1 use_remoteexec=false treat_warnings_as_errors=false'
  autoninja -C out/asan chrome
fi

echo "BOOTSTRAP_OK host=$(hostname) build=$DO_BUILD"
REMOTE
