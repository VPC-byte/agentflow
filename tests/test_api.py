from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from agentflow.app import create_app
from agentflow.orchestrator import Orchestrator
from agentflow.store import RunStore
from tests.test_orchestrator import make_orchestrator


def test_api_starts_and_returns_run_details(tmp_path):
    orchestrator = make_orchestrator(tmp_path)
    app = create_app(store=orchestrator.store, orchestrator=orchestrator)
    client = TestClient(app)

    payload = {
        "pipeline": {
            "name": "api-run",
            "working_dir": str(tmp_path),
            "nodes": [
                {"id": "alpha", "agent": "codex", "prompt": "api success"},
            ],
        }
    }
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 200
    run_id = response.json()["id"]
    asyncio.run(orchestrator.wait(run_id, timeout=5))
    run_response = client.get(f"/api/runs/{run_id}")
    assert run_response.status_code == 200
    body = run_response.json()
    assert body["status"] == "completed"
    assert body["nodes"]["alpha"]["output"] == "api success"
