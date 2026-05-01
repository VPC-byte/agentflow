#!/usr/bin/env python3
"""AgentFlow fanout for the Chromium Kimi crash campaign."""

from __future__ import annotations

from collections import defaultdict
import os
from pathlib import Path
import shlex

from agentflow import Graph, codex, fanout, shell


REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = REPO_ROOT / "prompts" / "chromium-agentflow-kimi-chaofan-inspired.md"

REMOTE_ROOT = os.environ.get("CHROMIUM_CAMPAIGN_ROOT", "/home/ubuntu/campaigns/chromium-agentflow")
CHROMIUM_SOURCE = os.environ.get("CHROMIUM_SOURCE", "/home/ubuntu/campaigns/chromium/src")
CHROMIUM_PATH = os.environ.get("CHROMIUM_PATH", f"{CHROMIUM_SOURCE}/out/asan/chrome")
SSH_USER = os.environ.get("CHROMIUM_SSH_USER", "ubuntu")
SSH_KEY = os.environ.get("AGENTFLOW_SSH_KEY", str(Path.home() / ".ssh" / "ops-cli-us-east-1.pem"))
MODEL = os.environ.get("CHROMIUM_MODEL", "moonshotai/kimi-k2.5")
TRUE_CRASHES = os.environ.get("TARGET_TRUE_CRASHES", "1")
SHARD_TIMEOUT_SECONDS = int(os.environ.get("CHROMIUM_SHARD_TIMEOUT_SECONDS", "21600"))
DEFAULT_SHARD_COUNT = 24


COMPONENT_BUCKETS = [
    "Blink LayoutNG fragmentation, inline layout, paint invalidation, and display-list lifetime paths",
    "Blink CSS parser/style resolver/custom property/value lifetime paths outside blink/modules/ai",
    "Blink DOM lifecycle, custom elements, mutation observers, ranges, and garbage-collected wrapper edges",
    "Blink editing, selection, input method, clipboard, spellcheck, and range mutation paths",
    "Blink SVG, filters, masks, image resources, and paint property tree interactions",
    "Canvas, WebGL/WebGPU bindings, image bitmap, video frame, and GPU resource lifetime paths",
    "Media Source Extensions, WebCodecs, audio/video demuxing bindings, and cross-thread media callbacks",
    "ServiceWorker, CacheStorage, IndexedDB, FileSystem Access, and storage object lifetime paths",
    "Mojo/IPC exposed from renderer APIs, deserialization, associated interfaces, and bad message edges",
    "V8 integration from browser-exposed JS APIs: ArrayBuffer backing stores, Wasm JS API, and Blink bindings",
    "Accessibility tree serialization, layout object references, AX cache invalidation, and event routing",
    "Navigation, BFCache, prerender, portals/fenced frames, and document lifecycle transition paths",
    "WebAudio, WebMIDI, AudioWorklet, and cross-thread audio graph lifetime paths",
    "WebRTC, peer connection, media capture, encoded transform, and RTP/RTCP parser edges",
    "Font loading, HarfBuzz/shaping integration, text rendering, and fallback font cache lifetime paths",
    "Image decoders and animation paths for WebP, AVIF, JPEG XL, PNG, GIF, and SVG-as-image",
    "CSS animations, scroll timelines, view transitions, compositing, and style/layout invalidation races",
    "Extension renderer bindings, user-script worlds, messaging, and browser-exposed extension APIs",
]


def _csv(name: str, default: str) -> list[str]:
    raw = os.environ.get(name, default)
    return [part.strip() for part in raw.split(",") if part.strip()]


def _worker_hosts() -> list[str]:
    hosts = _csv("CHROMIUM_WORKER_HOSTS", "44.223.72.154,3.238.79.147")
    if not hosts:
        raise RuntimeError("CHROMIUM_WORKER_HOSTS must contain at least one host")
    return hosts


def _selected_components() -> list[str]:
    requested = int(os.environ.get("CHROMIUM_SHARD_COUNT", str(DEFAULT_SHARD_COUNT)))
    if requested < 1:
        raise RuntimeError("CHROMIUM_SHARD_COUNT must be at least 1")
    selected = []
    for index in range(requested):
        target = COMPONENT_BUCKETS[index % len(COMPONENT_BUCKETS)]
        pass_number = index // len(COMPONENT_BUCKETS) + 1
        if pass_number > 1:
            target = (
                f"{target} (pass {pass_number}: choose a different subcomponent, file path, "
                "and trigger style from earlier docs/global_lessons findings)"
            )
        selected.append(target)
    return selected


def _render_prompt() -> str:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    replacements = {
        "${TARGET}": "{{ item.target }}",
        "${TARGET_TRUE_CRASHES}": TRUE_CRASHES,
        "${CHROMIUM_SOURCE}": CHROMIUM_SOURCE,
        "${AGENT_UTILS}": "utils.py",
        "${AGENT_TEMPLATE}": "poc.py",
        "${INPUT_HTML}": "input.html",
        "${INPUT_PY}": "repro.py",
        "${AGENT_DIR}": "{{ item.workspace }}",
        "${AGENT_ID}": "{{ item.shard_id }}",
        "${CHROMIUM_PATH}": CHROMIUM_PATH,
    }
    for needle, value in replacements.items():
        text = text.replace(needle, value)
    return text


def _shards() -> list[dict[str, str]]:
    hosts = _worker_hosts()
    shards = []
    for index, target in enumerate(_selected_components()):
        shard_id = f"{index:03d}"
        workspace = f"{REMOTE_ROOT}/agents/agent_{shard_id}"
        shards.append(
            {
                "host": hosts[index % len(hosts)],
                "target": target,
                "shard_id": shard_id,
                "workspace": workspace,
            }
        )
    return shards


def _ssh_target(host: str, remote_workdir: str) -> dict[str, str | int]:
    return {
        "kind": "ssh",
        "host": host,
        "username": SSH_USER,
        "identity_file": SSH_KEY,
        "remote_workdir": remote_workdir,
    }


def _task_host_suffix(index: int) -> str:
    return f"{index:02d}"


def _init_script(assigned_shards: list[dict[str, str]]) -> str:
    lines = [
        "set -euo pipefail",
        f"ROOT={shlex.quote(REMOTE_ROOT)}",
        "mkdir -p \"$ROOT/docs\" \"$ROOT/crashes\" \"$ROOT/locks\" \"$ROOT/agents\"",
        "if [ ! -s \"$ROOT/crashes/README.md\" ]; then",
        "  cat > \"$ROOT/crashes/README.md\" <<'EOF'",
        "# Crash Registry",
        "| Timestamp | Shard | Evidence | Artifact |",
        "|---|---|---|---|",
        "EOF",
        "fi",
        "if [ ! -s \"$ROOT/docs/global_lessons.md\" ]; then",
        "  cat > \"$ROOT/docs/global_lessons.md\" <<'EOF'",
        "# Shared Lessons",
        "Use this file only for reusable campaign-wide notes.",
        "EOF",
        "fi",
    ]
    for shard in assigned_shards:
        workspace = shlex.quote(shard["workspace"])
        lines.extend(
            [
                f"mkdir -p {workspace}",
                f"cp -f \"$ROOT/agent_template/utils.py\" {workspace}/utils.py",
                f"cp -f \"$ROOT/agent_template/poc.py\" {workspace}/poc.py",
                f"ln -sfn \"$ROOT/docs\" {workspace}/docs",
                f"ln -sfn \"$ROOT/crashes\" {workspace}/crashes",
                f"ln -sfn \"$ROOT/locks\" {workspace}/locks",
            ]
        )
    lines.append("echo INIT_OK")
    return "\n".join(lines)


def _host_summary_script(host: str) -> str:
    return "\n".join(
        [
            "set -euo pipefail",
            f"cd {shlex.quote(REMOTE_ROOT)}",
            f"echo '# Chromium Host Summary: {host}'",
            "echo",
            "echo '## Crash Registry'",
            "cat crashes/README.md",
            "echo",
            "echo '## Agent Outputs'",
            "find agents -maxdepth 2 -type f \\( -name 'repro.py' -o -name 'input.html' -o -name 'chrome_stderr.log' \\) | sort",
        ]
    )


def _combined_summary_script(summary_node_ids: list[str]) -> str:
    lines = [
        "set -euo pipefail",
        "mkdir -p runs/chromium-kimi-agentflow",
        "cat > runs/chromium-kimi-agentflow/combined_summary.md <<'SUMMARY_EOF'",
        "# Chromium Campaign Combined Summary",
        "",
        f"Workers: {', '.join(_worker_hosts())}",
        "",
    ]
    for node_id in summary_node_ids:
        lines.extend(
            [
                f"## {node_id}",
                "",
                f"{{{{ nodes.{node_id}.output }}}}",
                "",
            ]
        )
    lines.extend(
        [
            "SUMMARY_EOF",
            "cat runs/chromium-kimi-agentflow/combined_summary.md",
        ]
    )
    return "\n".join(lines)


def build_graph() -> Graph:
    shards = _shards()
    by_host: dict[str, list[dict[str, str]]] = defaultdict(list)
    for shard in shards:
        by_host[shard["host"]].append(shard)

    concurrency = int(os.environ.get("CHROMIUM_CONCURRENCY", str(min(4, len(shards)))))
    working_dir = REPO_ROOT / "runs" / "chromium-kimi-agentflow"
    working_dir.mkdir(parents=True, exist_ok=True)

    with Graph(
        "chromium-kimi-agentflow",
        description="Chromium ASAN crash campaign using the original Chromium prompt and Kimi through OpenRouter.",
        working_dir=str(working_dir),
        concurrency=concurrency,
        fail_fast=False,
        node_defaults={"capture": "trace"},
    ) as dag:
        init_nodes = []
        host_summary_nodes = []
        for index, (host, assigned) in enumerate(sorted(by_host.items())):
            suffix = _task_host_suffix(index)
            init_nodes.append(
                shell(
                    task_id=f"init_{suffix}",
                    script=_init_script(assigned),
                    target=_ssh_target(host, "/home/ubuntu"),
                    timeout_seconds=120,
                    success_criteria=[{"kind": "output_contains", "value": "INIT_OK"}],
                )
            )
            host_summary_nodes.append(
                shell(
                    task_id=f"summary_{suffix}",
                    script=_host_summary_script(host),
                    target=_ssh_target(host, REMOTE_ROOT),
                    timeout_seconds=300,
                )
            )

        fuzzer = fanout(
            codex(
                task_id="chromium",
                tools="read_write",
                executable="/home/ubuntu/bin/codex-openrouter",
                target={
                    "kind": "ssh",
                    "host": "{{ item.host }}",
                    "username": SSH_USER,
                    "identity_file": SSH_KEY,
                    "remote_workdir": "{{ item.workspace }}",
                },
                timeout_seconds=SHARD_TIMEOUT_SECONDS,
                retries=0,
                env={
                    "AGENTFLOW_CODEX_SANDBOX_MODE": "danger-full-access",
                    "CHROMIUM_PATH": CHROMIUM_PATH,
                },
                extra_args=[
                    "--profile",
                    "agentflow",
                    "--model",
                    MODEL,
                    "-c",
                    'model_reasoning_effort="high"',
                    "--add-dir",
                    CHROMIUM_SOURCE,
                    "--add-dir",
                    REMOTE_ROOT,
                ],
                prompt=_render_prompt(),
            ),
            shards,
        )

        summary = shell(
            task_id="summary",
            script=_combined_summary_script([node.id for node in host_summary_nodes]),
            timeout_seconds=300,
        )

        init_nodes >> fuzzer
        fuzzer >> host_summary_nodes
        host_summary_nodes >> summary

    return dag


if __name__ == "__main__":
    print(build_graph().to_json())
