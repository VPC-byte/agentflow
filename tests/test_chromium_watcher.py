from __future__ import annotations

from pathlib import Path


WATCHER = Path("runs/chromium-transition/watch_and_run_two_workers.sh")


def test_chromium_watcher_keeps_launching_campaign_rounds() -> None:
    script = WATCHER.read_text(encoding="utf-8")

    assert "CAMPAIGN_ROUND_SLEEP_SECONDS" in script
    assert "campaign round=$round" in script
    assert "campaign round=$round exited rc=$round_rc" in script
    assert "round=$((round + 1))" in script


def test_chromium_watcher_active_check_only_matches_real_kimi_codex_exec() -> None:
    script = WATCHER.read_text(encoding="utf-8")

    assert "[c]odex exec .*--model moonshotai/kimi-k2.5" in script
    assert "[c]odex-openrouter|[c]odex .*moonshotai/kimi|[c]odex .*chromium" not in script


def test_chromium_watcher_uses_large_default_shard_queue() -> None:
    script = WATCHER.read_text(encoding="utf-8")

    assert 'CHROMIUM_SHARD_COUNT="${CHROMIUM_SHARD_COUNT:-24}"' in script
    assert 'CHROMIUM_CONCURRENCY="${CHROMIUM_CONCURRENCY:-4}"' in script


def test_chromium_watcher_allows_progress_when_one_worker_is_idle() -> None:
    script = WATCHER.read_text(encoding="utf-8")

    assert "run_progress_snapshot()" in script
    assert "runtime health degraded but progressing" in script
    assert "active_total=$((primary_active + secondary_active))" in script


def test_chromium_watcher_derives_progress_from_events() -> None:
    script = WATCHER.read_text(encoding="utf-8")

    assert "inferred_statuses" in script
    assert 'event_type == "node_started"' in script
    assert 'event_type == "node_trace"' in script
    assert 'event_type == "node_completed"' in script
    assert 'event_type == "node_failed"' in script
    assert 'event_type == "node_cancelled"' in script


def test_chromium_watcher_cleans_remote_orphan_auditors_before_new_run() -> None:
    script = WATCHER.read_text(encoding="utf-8")

    assert "remote_stop_auditors()" in script
    assert "stopping stale remote auditors before new campaign" in script


def test_chromium_watcher_prunes_crash_registry_rows_without_artifacts() -> None:
    script = WATCHER.read_text(encoding="utf-8")

    assert "remote_sanitize_crash_registry()" in script
    assert "missing crash artifact" in script
    assert "crashes/README.md.bak" in script


def test_chromium_watcher_prunes_non_crash_registry_rows() -> None:
    script = WATCHER.read_text(encoding="utf-8")

    assert "non-crash registry row" in script
    assert "not artifact.startswith('crashes/')" in script
    assert "No crashes found" in script
