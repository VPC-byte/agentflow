from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


def _write_executable(path: Path, body: str) -> None:
    path.write_text(f"#!/usr/bin/env bash\nset -euo pipefail\n{body}", encoding="utf-8")
    path.chmod(0o755)


def _write_fake_shell_home(home: Path, *, kimi_body: str) -> None:
    bin_dir = home / "bin"
    bin_dir.mkdir(parents=True)
    (home / ".profile").write_text(
        'if [ -f "$HOME/.bashrc" ]; then . "$HOME/.bashrc"; fi\n',
        encoding="utf-8",
    )
    (home / ".bashrc").write_text('export PATH="$HOME/bin:$PATH"\n', encoding="utf-8")
    _write_executable(bin_dir / "kimi", kimi_body)
    _write_executable(bin_dir / "codex", 'printf "codex-cli 0.0.0\\n"\n')
    _write_executable(bin_dir / "claude", 'printf "Claude Code 0.0.0\\n"\n')


def test_verify_local_kimi_shell_script_times_out_when_kimi_hangs(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _write_fake_shell_home(home, kimi_body="sleep 5\n")

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "verify-local-kimi-shell.sh"
    python_bin = repo_root / ".venv" / "bin" / "python"

    started_at = time.monotonic()
    completed = subprocess.run(
        ["bash", str(script_path)],
        capture_output=True,
        cwd=repo_root,
        env={
            **os.environ,
            "AGENTFLOW_LOCAL_VERIFY_TIMEOUT_SECONDS": "0.2",
            "AGENTFLOW_PYTHON": str(python_bin if python_bin.exists() else Path(sys.executable)),
            "HOME": str(home),
        },
        text=True,
        timeout=5,
    )
    elapsed = time.monotonic() - started_at

    assert completed.returncode == 124
    assert "~/.profile: present" in completed.stdout
    assert "Timed out after 0.2s: env" in completed.stderr
    assert elapsed < 3
