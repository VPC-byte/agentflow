"""Helpers for externally launching Chromium and connecting over CDP."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import tempfile
import time
from typing import Iterator
from urllib import request


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_cdp(port: int, process: subprocess.Popen[str], timeout_seconds: int) -> None:
    url = f"http://127.0.0.1:{port}/json/version"
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Chromium exited during startup with code {process.returncode}")
        try:
            with request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001 - startup can fail in several transient ways.
            last_error = exc
        time.sleep(0.25)

    raise TimeoutError(f"Timed out waiting for Chromium CDP on {url}: {last_error}")


def _process_tree(root_pid: int) -> list[int]:
    parents: dict[int, int] = {}
    for stat_path in Path("/proc").glob("[0-9]*/stat"):
        try:
            text = stat_path.read_text(encoding="utf-8", errors="replace")
            pid = int(stat_path.parent.name)
            close_paren = text.rfind(")")
            fields = text[close_paren + 2 :].split()
            ppid = int(fields[1])
        except (OSError, ValueError, IndexError):
            continue
        parents[pid] = ppid

    descendants: list[int] = []
    queue = [root_pid]
    while queue:
        current = queue.pop(0)
        children = [pid for pid, ppid in parents.items() if ppid == current]
        descendants.extend(children)
        queue.extend(children)
    return descendants


def _sanitizer_env() -> dict[str, str]:
    env = {
        "ASAN_OPTIONS": ":".join(
            [
                "abort_on_error=1",
                "allocator_may_return_null=1",
                "detect_leaks=0",
                "detect_odr_violation=0",
                "fast_unwind_on_malloc=0",
                "handle_abort=1",
                "print_suppressions=0",
                "strict_string_checks=1",
                "symbolize=1",
            ]
        ),
        "UBSAN_OPTIONS": "print_stacktrace=1:halt_on_error=1",
    }
    symbolizer = shutil.which("llvm-symbolizer")
    if symbolizer:
        env["ASAN_SYMBOLIZER_PATH"] = symbolizer
    return env


@dataclass
class BrowserSession:
    process: subprocess.Popen[str]
    port: int
    log_dir: Path
    user_data_dir: Path
    playwright: object
    browser: object
    context: object
    page: object

    @property
    def chrome_pid(self) -> int:
        return int(self.process.pid)

    def renderer_pids(self) -> list[int]:
        descendants = _process_tree(self.chrome_pid)
        renderers: list[int] = []
        for pid in descendants:
            cmdline_path = Path("/proc") / str(pid) / "cmdline"
            try:
                cmdline = cmdline_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "--type=renderer" in cmdline:
                renderers.append(pid)
        return renderers

    def open_file(self, path: str | Path, *, wait_until: str = "load", timeout: int = 15000) -> object:
        uri = Path(path).resolve().as_uri()
        return self.page.goto(uri, wait_until=wait_until, timeout=timeout)

    def stdout_text(self) -> str:
        return (self.log_dir / "chrome_stdout.log").read_text(encoding="utf-8", errors="replace")

    def stderr_text(self) -> str:
        return (self.log_dir / "chrome_stderr.log").read_text(encoding="utf-8", errors="replace")


@contextmanager
def start_browser(
    chromium_path: str | Path,
    *,
    log_dir: str | Path,
    extra_args: list[str] | None = None,
    env: dict[str, str] | None = None,
    startup_timeout: int = 45,
) -> Iterator[BrowserSession]:
    """Launch Chromium as an external process and connect with Playwright CDP."""

    from playwright.sync_api import sync_playwright

    chromium = Path(chromium_path)
    if not chromium.exists():
        raise FileNotFoundError(f"Chromium binary does not exist: {chromium}")

    logs = Path(log_dir).resolve()
    logs.mkdir(parents=True, exist_ok=True)
    user_data_dir = Path(tempfile.mkdtemp(prefix="chrome-profile-", dir=str(logs)))
    port = _free_port()

    stdout_file = (logs / "chrome_stdout.log").open("w", encoding="utf-8")
    stderr_file = (logs / "chrome_stderr.log").open("w", encoding="utf-8")

    launch_env = os.environ.copy()
    launch_env.update(_sanitizer_env())
    if env:
        launch_env.update(env)

    command = [
        str(chromium),
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-sync",
        "--enable-logging=stderr",
        "--v=0",
        "about:blank",
    ]
    if extra_args:
        command[1:1] = extra_args

    process = subprocess.Popen(
        command,
        stdout=stdout_file,
        stderr=stderr_file,
        text=True,
        env=launch_env,
        start_new_session=True,
    )

    playwright = None
    browser = None
    try:
        _wait_for_cdp(port, process, startup_timeout)
        playwright = sync_playwright().start()
        browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.pages[0] if context.pages else context.new_page()
        yield BrowserSession(
            process=process,
            port=port,
            log_dir=logs,
            user_data_dir=user_data_dir,
            playwright=playwright,
            browser=browser,
            context=context,
            page=page,
        )
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=5)
            except Exception:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except Exception:
                    pass
        stdout_file.close()
        stderr_file.close()
        shutil.rmtree(user_data_dir, ignore_errors=True)
