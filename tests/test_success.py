from pathlib import Path

from agentflow.specs import NodeResult, NodeSpec
from agentflow.success import evaluate_success


def test_success_criteria_cover_output_and_files(tmp_path: Path):
    target = tmp_path / "artifact.txt"
    target.write_text("hello success world", encoding="utf-8")
    node = NodeSpec.model_validate(
        {
            "id": "writer",
            "agent": "codex",
            "prompt": "x",
            "success_criteria": [
                {"kind": "output_contains", "value": "success"},
                {"kind": "file_exists", "path": "artifact.txt"},
                {"kind": "file_contains", "path": "artifact.txt", "value": "hello"},
                {"kind": "file_nonempty", "path": "artifact.txt"},
            ],
        }
    )
    result = NodeResult(node_id="writer", output="success")
    passed, messages = evaluate_success(node, result, tmp_path)
    assert passed is True
    assert any("file_exists" in message for message in messages)
