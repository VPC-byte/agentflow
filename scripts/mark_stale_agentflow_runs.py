#!/usr/bin/env python3
"""Mark AgentFlow runs stale when their controller process is gone."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled"}
TERMINAL_NODE_STATUSES = {"completed", "failed", "cancelled", "skipped"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_event(run_dir: Path, run_id: str, event_type: str, *, node_id: str | None = None, data: dict[str, Any] | None = None) -> None:
    event = {
        "timestamp": _now(),
        "run_id": run_id,
        "type": event_type,
        "node_id": node_id,
        "data": data or {},
    }
    with (run_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False))
        handle.write("\n")


def mark_run(run_dir: Path, *, status: str, reason: str) -> str:
    run_path = run_dir / "run.json"
    payload = _load_json(run_path)
    run_id = payload["id"]
    if payload.get("status") in TERMINAL_RUN_STATUSES:
        return f"{run_id}: already terminal ({payload.get('status')})"

    finished_at = _now()
    node_status = "cancelled" if status == "cancelled" else "failed"
    changed_nodes: list[str] = []

    for node_id, node in (payload.get("nodes") or {}).items():
        if node.get("status") in TERMINAL_NODE_STATUSES:
            continue
        changed_nodes.append(node_id)
        node["status"] = node_status
        node["finished_at"] = finished_at
        node["success"] = False
        details = node.setdefault("success_details", [])
        if reason not in details:
            details.append(reason)
        stderr_lines = node.setdefault("stderr_lines", [])
        stderr_lines.append(reason)
        for attempt in node.get("attempts") or []:
            if attempt.get("status") not in TERMINAL_NODE_STATUSES:
                attempt["status"] = node_status
                attempt["finished_at"] = finished_at
                attempt["success"] = False
                attempt_details = attempt.setdefault("success_details", [])
                if reason not in attempt_details:
                    attempt_details.append(reason)

    payload["status"] = status
    payload["finished_at"] = finished_at
    _write_json(run_path, payload)

    for node_id in changed_nodes:
        _append_event(
            run_dir,
            run_id,
            "node_cancelled" if status == "cancelled" else "node_failed",
            node_id=node_id,
            data={"stale": True, "reason": reason},
        )
    _append_event(run_dir, run_id, "run_completed", data={"status": status, "stale": True, "reason": reason})
    return f"{run_id}: marked {status}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", default=".agentflow/runs")
    parser.add_argument("--run-id", action="append", required=True)
    parser.add_argument("--status", choices=["failed", "cancelled"], default="failed")
    parser.add_argument("--reason", default="stale AgentFlow controller process exited")
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir)
    for run_id in args.run_id:
        print(mark_run(runs_dir / run_id, status=args.status, reason=args.reason))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
