from __future__ import annotations

import asyncio
import json

import typer
import uvicorn

from agentflow.app import create_app
from agentflow.loader import load_pipeline_from_path
from agentflow.orchestrator import Orchestrator
from agentflow.store import RunStore

app = typer.Typer(add_completion=False)


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    uvicorn.run(create_app(), host=host, port=port)


@app.command()
def run(path: str) -> None:
    store = RunStore()
    orchestrator = Orchestrator(store=store)
    pipeline = load_pipeline_from_path(path)

    async def _run() -> None:
        run_record = await orchestrator.submit(pipeline)
        completed = await orchestrator.wait(run_record.id, timeout=None)
        typer.echo(json.dumps(completed.model_dump(mode="json"), indent=2))
        raise typer.Exit(code=0 if completed.status.value == "completed" else 1)

    asyncio.run(_run())


if __name__ == "__main__":
    app()
