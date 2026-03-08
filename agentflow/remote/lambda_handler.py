from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def _write_runtime_files(runtime_dir: Path, runtime_files: dict[str, str]) -> None:
    for relative_path, content in runtime_files.items():
        target = runtime_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def handler(event, context):
    runtime_root = Path(tempfile.mkdtemp(prefix="agentflow-"))
    try:
        _write_runtime_files(runtime_root, event.get("runtime_files", {}))
        env = os.environ.copy()
        env.update(event.get("env", {}))
        cwd = event.get("cwd") or str(runtime_root)
        stdin = event.get("stdin")
        timeout_seconds = int(event.get("timeout_seconds", 1800))
        completed = subprocess.run(
            event["command"],
            cwd=cwd,
            env=env,
            input=stdin,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "exit_code": completed.returncode,
            "stdout_lines": completed.stdout.splitlines(),
            "stderr_lines": completed.stderr.splitlines(),
        }
    finally:
        shutil.rmtree(runtime_root, ignore_errors=True)
