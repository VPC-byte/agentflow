from __future__ import annotations

import asyncio
import os

from agentflow.prepared import ExecutionPaths, PreparedExecution
from agentflow.runners.base import RawExecutionResult, Runner, StreamCallback
from agentflow.specs import NodeSpec


class LocalRunner(Runner):
    async def _consume_stream(self, stream, stream_name: str, buffer: list[str], on_output: StreamCallback) -> None:
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip("\n")
            buffer.append(text)
            await on_output(stream_name, text)

    async def execute(
        self,
        node: NodeSpec,
        prepared: PreparedExecution,
        paths: ExecutionPaths,
        on_output: StreamCallback,
    ) -> RawExecutionResult:
        self.materialize_runtime_files(paths.host_runtime_dir, prepared.runtime_files)
        env = os.environ.copy()
        env.update(prepared.env)
        process = await asyncio.create_subprocess_exec(
            *prepared.command,
            cwd=prepared.cwd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE if prepared.stdin is not None else None,
        )
        if prepared.stdin is not None and process.stdin is not None:
            process.stdin.write(prepared.stdin.encode("utf-8"))
            await process.stdin.drain()
            process.stdin.close()

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    self._consume_stream(process.stdout, "stdout", stdout_lines, on_output),
                    self._consume_stream(process.stderr, "stderr", stderr_lines, on_output),
                    process.wait(),
                ),
                timeout=node.timeout_seconds,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            stderr_lines.append(f"Timed out after {node.timeout_seconds}s")
            await on_output("stderr", stderr_lines[-1])
            return RawExecutionResult(exit_code=124, stdout_lines=stdout_lines, stderr_lines=stderr_lines)

        return RawExecutionResult(exit_code=process.returncode, stdout_lines=stdout_lines, stderr_lines=stderr_lines)
