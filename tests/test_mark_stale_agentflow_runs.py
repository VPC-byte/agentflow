from __future__ import annotations

import json
import subprocess
from pathlib import Path


SCRIPT = Path("scripts/mark_stale_agentflow_runs.py")


def test_mark_stale_agentflow_run_fails_running_nodes(tmp_path: Path) -> None:
    run_id = "stale-run"
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "id": run_id,
                "status": "running",
                "pipeline": {"name": "stale", "working_dir": ".", "nodes": []},
                "optimization_parent_run_id": None,
                "optimization_round": None,
                "optimization_session": None,
                "created_at": "2026-05-01T00:00:00+00:00",
                "started_at": "2026-05-01T00:00:00+00:00",
                "finished_at": None,
                "nodes": {
                    "active": {
                        "node_id": "active",
                        "status": "running",
                        "started_at": "2026-05-01T00:00:01+00:00",
                        "finished_at": None,
                        "exit_code": None,
                        "final_response": None,
                        "output": None,
                        "stdout_lines": [],
                        "stderr_lines": [],
                        "trace_events": [],
                        "success": None,
                        "success_details": [],
                        "current_attempt": 1,
                        "attempts": [
                            {
                                "number": 1,
                                "status": "running",
                                "started_at": "2026-05-01T00:00:01+00:00",
                                "finished_at": None,
                                "exit_code": None,
                                "final_response": None,
                                "output": None,
                                "success": None,
                                "success_details": [],
                            }
                        ],
                        "tick_count": 0,
                        "last_tick_started_at": None,
                        "next_scheduled_at": None,
                        "diff": None,
                    },
                    "done": {
                        "node_id": "done",
                        "status": "completed",
                        "started_at": "2026-05-01T00:00:01+00:00",
                        "finished_at": "2026-05-01T00:00:02+00:00",
                        "exit_code": 0,
                        "final_response": "ok",
                        "output": "ok",
                        "stdout_lines": ["ok"],
                        "stderr_lines": [],
                        "trace_events": [],
                        "success": True,
                        "success_details": [],
                        "current_attempt": 1,
                        "attempts": [],
                        "tick_count": 0,
                        "last_tick_started_at": None,
                        "next_scheduled_at": None,
                        "diff": None,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--runs-dir",
            str(tmp_path),
            "--run-id",
            run_id,
            "--reason",
            "control process exited",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert f"{run_id}: marked failed" in result.stdout
    payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["finished_at"]
    assert payload["nodes"]["active"]["status"] == "failed"
    assert payload["nodes"]["active"]["finished_at"]
    assert payload["nodes"]["active"]["attempts"][0]["status"] == "failed"
    assert payload["nodes"]["done"]["status"] == "completed"

    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert events[-1]["type"] == "run_completed"
    assert events[-1]["data"]["status"] == "failed"
