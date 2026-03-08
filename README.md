# AgentFlow

AgentFlow is a Python orchestrator for `codex`, `claude`, and `kimi` agents that supports:

- Airflow-like DAG definitions in Python and YAML
- Parallel node execution with dependency-aware scheduling
- Per-node model, provider, tools mode, MCP selection, and skills selection
- Local, container, and AWS Lambda execution targets
- Final-response or full-trace outputs per node
- Success criteria such as output contains text, file exists, file contains text, and file non-empty
- A FastAPI frontend that visualizes DAG runs and parsed JSONL traces in real time

## Why this shape

This project was built from scratch in this repo, and the integrations were informed by:

- OpenAI Codex CLI docs and source: `reference/codex`
- Claude Code Telegram integration patterns: `reference/claude-code-telegram`
- Moonshot's Kimi CLI wire protocol and web UI: `reference/kimi-cli`

Those references drove the parser tolerances and the frontend event model.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .[dev]
```

## Run the web app

```bash
agentflow serve --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

## Run a pipeline from YAML

```bash
agentflow run examples/pipeline.yaml
```

## Airflow-like Python DAG

```python
from agentflow import DAG, claude, codex, kimi

with DAG("demo", working_dir=".", concurrency=3) as dag:
    plan = codex(task_id="plan", prompt="Inspect the repo and plan the work.")
    implement = claude(
        task_id="implement",
        prompt="Implement the plan:\n\n{{ nodes.plan.output }}",
        tools="read_write",
    )
    review = kimi(
        task_id="review",
        prompt="Review the plan:\n\n{{ nodes.plan.output }}",
        capture="trace",
    )
    merge = codex(
        task_id="merge",
        prompt="Merge the implementation and review outputs.",
    )

    plan >> [implement, review]
    [implement, review] >> merge

spec = dag.to_spec()
```

## Pipeline schema

Each node supports:

- `agent`: `codex`, `claude`, or `kimi`
- `model`: any model string understood by the backend
- `provider`: a string or a structured provider config with `base_url`, `api_key_env`, headers, and env
- `tools`: `read_only` or `read_write`
- `mcps`: a list of MCP server definitions
- `skills`: a list of local skill file paths or names
- `target`: `local`, `container`, or `aws_lambda`
- `capture`: `final` or `trace`
- `success_criteria`: output/file checks evaluated after execution

## Execution targets

### Local

Runs the agent command directly on the host.

### Container

Wraps the command in `docker run`, mounts the working directory, runtime directory, and the AgentFlow app, then streams stdout/stderr back into the run trace.

### AWS Lambda

Invokes `agentflow.remote.lambda_handler.handler`. The payload contains the prepared command, env, and runtime files. This is suitable for remote execution where the Lambda package includes AgentFlow and the agent executable.

## Agent notes

### Codex

- Uses `codex exec --json`
- Maps tools mode to Codex sandboxing
- Writes `CODEX_HOME/config.toml` per node for provider and MCP selection

### Claude

- Uses `claude -p ... --output-format stream-json --verbose`
- Passes `--allowedTools` according to the read-only vs read-write policy
- Writes a per-node MCP JSON config and passes it with `--mcp-config`

### Kimi

- Uses `python3 -m agentflow.remote.kimi_bridge`
- Emits a Kimi-style JSON-RPC event stream
- Calls Moonshot's OpenAI-compatible chat completions API
- Provides a small built-in tool layer for read, search, write, and shell actions

## Tests

```bash
pytest
```

## Reference sources

- `https://developers.openai.com/codex/security`
- `https://docs.anthropic.com/en/docs/claude-code/sdk`
- `https://github.com/openai/codex`
- `https://github.com/RichardAtCT/claude-code-telegram`
- `https://github.com/MoonshotAI/kimi-cli`
