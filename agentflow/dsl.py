from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from agentflow.specs import AgentKind, NodeSpec, PipelineSpec


_CURRENT_DAG: ContextVar["DAG | None"] = ContextVar("_CURRENT_DAG", default=None)


@dataclass
class NodeBuilder:
    dag: "DAG"
    id: str
    agent: AgentKind
    prompt: str
    kwargs: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.dag._register(self)

    def __rshift__(self, other: "NodeBuilder | list[NodeBuilder]") -> "NodeBuilder | list[NodeBuilder]":
        if isinstance(other, list):
            for item in other:
                item.depends_on.append(self.id)
            return other
        other.depends_on.append(self.id)
        return other

    def to_spec(self) -> NodeSpec:
        return NodeSpec(id=self.id, agent=self.agent, prompt=self.prompt, depends_on=self.depends_on, **self.kwargs)


class DAG:
    def __init__(self, name: str, *, description: str | None = None, working_dir: str = ".", concurrency: int = 4):
        self.name = name
        self.description = description
        self.working_dir = working_dir
        self.concurrency = concurrency
        self._nodes: dict[str, NodeBuilder] = {}
        self._token = None

    def __enter__(self) -> "DAG":
        self._token = _CURRENT_DAG.set(self)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._token is not None:
            _CURRENT_DAG.reset(self._token)

    def _register(self, node: NodeBuilder) -> None:
        if node.id in self._nodes:
            raise ValueError(f"node {node.id!r} already exists")
        self._nodes[node.id] = node

    def to_spec(self) -> PipelineSpec:
        return PipelineSpec(
            name=self.name,
            description=self.description,
            working_dir=self.working_dir,
            concurrency=self.concurrency,
            nodes=[node.to_spec() for node in self._nodes.values()],
        )


def _current_dag() -> DAG:
    dag = _CURRENT_DAG.get()
    if dag is None:
        raise RuntimeError("No active DAG context. Use `with DAG(...):`.")
    return dag


def _node(agent: AgentKind, *, task_id: str, prompt: str, **kwargs: Any) -> NodeBuilder:
    return NodeBuilder(dag=_current_dag(), id=task_id, agent=agent, prompt=prompt, kwargs=kwargs)


def codex(*, task_id: str, prompt: str, **kwargs: Any) -> NodeBuilder:
    return _node(AgentKind.CODEX, task_id=task_id, prompt=prompt, **kwargs)


def claude(*, task_id: str, prompt: str, **kwargs: Any) -> NodeBuilder:
    return _node(AgentKind.CLAUDE, task_id=task_id, prompt=prompt, **kwargs)


def kimi(*, task_id: str, prompt: str, **kwargs: Any) -> NodeBuilder:
    return _node(AgentKind.KIMI, task_id=task_id, prompt=prompt, **kwargs)
