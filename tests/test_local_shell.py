from __future__ import annotations

from pathlib import Path

import pytest

from agentflow.local_shell import kimi_shell_init_requires_interactive_bash_warning, shell_command_uses_kimi_helper


@pytest.mark.parametrize(
    "command",
    [
        "bash -lc 'command -v kimi >/dev/null && {command}'",
        "bash -lc 'type kimi >/dev/null 2>&1; {command}'",
        "bash -lc 'which kimi >/dev/null; {command}'",
        "bash -lc 'builtin type kimi >/dev/null 2>&1; {command}'",
        "echo kimi",
        "printf '%s\\n' kimi",
        "bash -lc 'echo kimi && {command}'",
        "bash -lc 'printf kimi && {command}'",
    ],
)
def test_shell_command_uses_kimi_helper_ignores_probe_commands(command: str):
    assert shell_command_uses_kimi_helper(command) is False


@pytest.mark.parametrize(
    "command",
    [
        "bash -lc 'command -v kimi >/dev/null && kimi && {command}'",
        "bash -lc 'type kimi >/dev/null 2>&1; kimi; {command}'",
        "bash -lc 'which kimi >/dev/null; kimi && {command}'",
        'eval "$(kimi)"',
        'eval `kimi`',
        'source <(kimi)',
        "bash -lc 'eval \"$(kimi)\" && {command}'",
        "bash -lc 'eval `kimi` && {command}'",
        "bash -lc 'source <(kimi) && {command}'",
    ],
)
def test_shell_command_uses_kimi_helper_detects_actual_bootstrap_after_probe(command: str):
    assert shell_command_uses_kimi_helper(command) is True


def test_kimi_shell_init_requires_interactive_bash_warning_ignores_probe_only_shell():
    target = {
        "kind": "local",
        "shell": "bash -lc 'command -v kimi >/dev/null && {command}'",
    }

    assert kimi_shell_init_requires_interactive_bash_warning(target) is None


def test_kimi_shell_init_requires_interactive_bash_warning_supports_shell_init_lists():
    target = {
        "kind": "local",
        "shell": "bash",
        "shell_init": ["command -v kimi >/dev/null 2>&1", "kimi"],
    }

    assert kimi_shell_init_requires_interactive_bash_warning(target) == (
        "`shell_init: kimi` uses bash without interactive startup; helpers from `~/.bashrc` are usually "
        "unavailable. Set `target.shell_interactive: true` or use `bash -lic`."
    )


def test_kimi_shell_init_requires_interactive_bash_warning_ignores_plain_text_kimi_output():
    target = {
        "kind": "local",
        "shell": "bash",
        "shell_init": "echo kimi",
    }

    assert kimi_shell_init_requires_interactive_bash_warning(target) is None


def test_kimi_shell_init_requires_interactive_bash_warning_detects_eval_style_shell_wrapper():
    target = {
        "kind": "local",
        "shell": "bash -lc 'eval \"$(kimi)\" && {command}'",
    }

    assert kimi_shell_init_requires_interactive_bash_warning(target) == (
        "`target.shell` uses `kimi` with bash without interactive startup; helpers from `~/.bashrc` are usually "
        "unavailable. Add `-i`, set `target.shell_interactive: true`, or use `bash -lic`."
    )


def test_kimi_shell_init_requires_interactive_bash_warning_detects_backtick_eval_shell_wrapper():
    target = {
        "kind": "local",
        "shell": "bash -lc 'eval `kimi` && {command}'",
    }

    assert kimi_shell_init_requires_interactive_bash_warning(target) == (
        "`target.shell` uses `kimi` with bash without interactive startup; helpers from `~/.bashrc` are usually "
        "unavailable. Add `-i`, set `target.shell_interactive: true`, or use `bash -lic`."
    )


def test_kimi_shell_init_requires_interactive_bash_warning_explains_explicit_bashrc_source_in_shell_wrapper(
    tmp_path: Path,
):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".bashrc").write_text(
        "case $- in\n    *i*) ;;\n      *) return;;\nesac\n\nkimi(){ :; }\n",
        encoding="utf-8",
    )
    target = {
        "kind": "local",
        "shell": "bash -lc 'source ~/.bashrc && kimi && {command}'",
    }

    assert kimi_shell_init_requires_interactive_bash_warning(target, home=home) == (
        "`target.shell` sources `~/.bashrc` before `kimi`, but `~/.bashrc` returns early for non-interactive "
        "bash on this host, so helpers defined later still do not load. Add `-i`, set `target.shell_interactive: true`, "
        "use `bash -lic`, or move the bootstrap into a login-sourced file."
    )


def test_kimi_shell_init_requires_interactive_bash_warning_explains_explicit_bashrc_source_before_shell_init(
    tmp_path: Path,
):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".bashrc").write_text(
        "[[ $- != *i* ]] && return\n\nkimi(){ :; }\n",
        encoding="utf-8",
    )
    target = {
        "kind": "local",
        "shell": "bash -lc 'source ~/.bashrc && {command}'",
        "shell_init": ["command -v kimi >/dev/null 2>&1", "kimi"],
    }

    assert kimi_shell_init_requires_interactive_bash_warning(target, home=home) == (
        "`target.shell` sources `~/.bashrc` before `shell_init`, but `~/.bashrc` returns early for non-interactive "
        "bash on this host, so helpers defined later still do not load. Add `-i`, set `target.shell_interactive: true`, "
        "use `bash -lic`, or move the bootstrap into a login-sourced file."
    )


def test_kimi_shell_init_requires_interactive_bash_warning_keeps_generic_warning_without_detected_bashrc_guard(
    tmp_path: Path,
):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".bashrc").write_text("kimi(){ :; }\n", encoding="utf-8")
    target = {
        "kind": "local",
        "shell": "bash -lc 'source ~/.bashrc && kimi && {command}'",
    }

    assert kimi_shell_init_requires_interactive_bash_warning(target, home=home) == (
        "`target.shell` uses `kimi` with bash without interactive startup; helpers from `~/.bashrc` are usually "
        "unavailable. Add `-i`, set `target.shell_interactive: true`, or use `bash -lic`."
    )
