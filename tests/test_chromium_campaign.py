from __future__ import annotations

from collections import Counter

import examples.chromium_kimi_campaign as campaign


def test_chromium_campaign_default_uses_large_shard_queue(monkeypatch) -> None:
    monkeypatch.delenv("CHROMIUM_SHARD_COUNT", raising=False)

    selected = campaign._selected_components()

    assert len(selected) == campaign.DEFAULT_SHARD_COUNT
    assert len(selected) > len(campaign.COMPONENT_BUCKETS)


def test_chromium_campaign_repeats_component_buckets_with_pass_labels(monkeypatch) -> None:
    monkeypatch.setenv("CHROMIUM_SHARD_COUNT", "24")

    selected = campaign._selected_components()

    assert len(selected) == 24
    assert any("pass 2" in target for target in selected)


def test_chromium_shards_balance_across_workers(monkeypatch) -> None:
    monkeypatch.setenv("CHROMIUM_SHARD_COUNT", "24")
    monkeypatch.setenv("CHROMIUM_WORKER_HOSTS", "primary.example,secondary.example")

    shards = campaign._shards()

    assert len(shards) == 24
    assert Counter(shard["host"] for shard in shards) == {
        "primary.example": 12,
        "secondary.example": 12,
    }
    assert len({shard["workspace"] for shard in shards}) == 24


def test_chromium_prompt_keeps_negative_notes_out_of_crash_registry() -> None:
    prompt = campaign.PROMPT_PATH.read_text(encoding="utf-8")

    assert "Do NOT append no-crash" in prompt
    assert "crashes/README.md is only for TRUE crash records" in prompt
