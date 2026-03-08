from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ExecutionPaths:
    host_workdir: Path
    host_runtime_dir: Path
    target_workdir: str
    target_runtime_dir: str
    app_root: Path


@dataclass(slots=True)
class PreparedExecution:
    command: list[str]
    env: dict[str, str]
    cwd: str
    trace_kind: str
    runtime_files: dict[str, str] = field(default_factory=dict)
    stdin: str | None = None
