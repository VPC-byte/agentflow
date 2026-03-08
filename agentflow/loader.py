from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from agentflow.specs import PipelineSpec


def load_pipeline_from_path(path: str | Path) -> PipelineSpec:
    path = Path(path)
    data = path.read_text(encoding="utf-8")
    return load_pipeline_from_text(data)


def load_pipeline_from_text(data: str) -> PipelineSpec:
    parsed: Any
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError:
        parsed = yaml.safe_load(data)
    return PipelineSpec.model_validate(parsed)
