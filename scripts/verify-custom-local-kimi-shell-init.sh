#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

AGENTFLOW_KIMI_PIPELINE_MODE="shell-init" bash "$script_dir/verify-custom-local-kimi-pipeline.sh"
