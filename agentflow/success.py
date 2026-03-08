from __future__ import annotations

from pathlib import Path

from agentflow.specs import (
    FileContainsCriterion,
    FileExistsCriterion,
    FileNonEmptyCriterion,
    NodeResult,
    NodeSpec,
    OutputContainsCriterion,
)


def evaluate_success(node: NodeSpec, result: NodeResult, working_dir: Path) -> tuple[bool, list[str]]:
    if not node.success_criteria:
        return True, ["no success criteria configured"]

    messages: list[str] = []
    output = result.output or result.final_response or ""
    passed = True

    for criterion in node.success_criteria:
        if isinstance(criterion, OutputContainsCriterion):
            haystack = output if criterion.case_sensitive else output.lower()
            needle = criterion.value if criterion.case_sensitive else criterion.value.lower()
            ok = needle in haystack
            messages.append(f"output_contains({criterion.value!r})={ok}")
        elif isinstance(criterion, FileExistsCriterion):
            ok = (working_dir / criterion.path).exists()
            messages.append(f"file_exists({criterion.path})={ok}")
        elif isinstance(criterion, FileContainsCriterion):
            path = working_dir / criterion.path
            contents = path.read_text(encoding="utf-8") if path.exists() else ""
            haystack = contents if criterion.case_sensitive else contents.lower()
            needle = criterion.value if criterion.case_sensitive else criterion.value.lower()
            ok = path.exists() and needle in haystack
            messages.append(f"file_contains({criterion.path}, {criterion.value!r})={ok}")
        elif isinstance(criterion, FileNonEmptyCriterion):
            path = working_dir / criterion.path
            ok = path.exists() and path.read_text(encoding="utf-8").strip() != ""
            messages.append(f"file_nonempty({criterion.path})={ok}")
        else:
            ok = False
            messages.append(f"unsupported success criterion: {criterion}")
        passed = passed and ok
    return passed, messages
