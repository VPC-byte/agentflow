#!/usr/bin/env python3
"""Minimal Chromium reproducer skeleton for campaign shards."""

from __future__ import annotations

import os
from pathlib import Path

from utils import start_browser


AGENT_DIR = Path(__file__).resolve().parent
CHROMIUM_PATH = os.environ.get(
    "CHROMIUM_PATH",
    "/home/ubuntu/campaigns/chromium/src/out/asan/chrome",
)
INPUT_HTML = AGENT_DIR / "input.html"


def main() -> None:
    if not INPUT_HTML.exists():
        INPUT_HTML.write_text(
            "<!doctype html><meta charset='utf-8'><title>chromium shard</title>\n",
            encoding="utf-8",
        )

    with start_browser(CHROMIUM_PATH, log_dir=str(AGENT_DIR)) as session:
        session.open_file(INPUT_HTML)
        session.page.wait_for_timeout(int(os.environ.get("POC_WAIT_MS", "2000")))
        print(f"chrome_pid={session.chrome_pid}")
        print(f"renderer_pids={session.renderer_pids()}")

    stderr_tail = (AGENT_DIR / "chrome_stderr.log").read_text(
        encoding="utf-8",
        errors="replace",
    )[-4000:]
    if stderr_tail.strip():
        print("chrome_stderr_tail_begin")
        print(stderr_tail)
        print("chrome_stderr_tail_end")


if __name__ == "__main__":
    main()
