from __future__ import annotations

from agentflow.cloud.aws import collect_local_credentials


def test_collect_local_credentials_forwards_openrouter_key_for_codex(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-secret")

    env = collect_local_credentials("codex")

    assert env["OPENROUTER_API_KEY"] == "openrouter-secret"


def test_collect_local_credentials_forwards_openrouter_claude_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-secret")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://openrouter.ai/api")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "openrouter-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    env = collect_local_credentials("claude")

    assert env["OPENROUTER_API_KEY"] == "openrouter-secret"
    assert env["ANTHROPIC_BASE_URL"] == "https://openrouter.ai/api"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "openrouter-secret"
    assert env["ANTHROPIC_API_KEY"] == ""
