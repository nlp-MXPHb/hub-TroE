"""Shared data-model entities (Constitution Art. 3.2: JSON-serializable data contract)."""
from dataclasses import dataclass, field
from enum import Enum
import json


class SubQueryState(Enum):
    STARTED = "started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class DependencyError(Exception):
    """Raised when sub-queries are not flat/zero-dependency (FR-002)."""


class RunawayError(Exception):
    """Raised when a subagent ReAct loop exceeds max_iterations (FR-011)."""


@dataclass
class ResearchSubQuery:
    sub_query_id: str
    sub_query: str
    config: dict = field(default_factory=dict)
    depends_on: list = field(default_factory=list)   # MUST be empty for flat (FR-002)

    def __post_init__(self):
        # LLMs may emit numeric sub-query IDs; the data contract requires strings
        # (status events, log lines, failure lists all format them as text).
        self.sub_query_id = str(self.sub_query_id)


@dataclass
class SubagentTask:
    task_id: str
    sub_query_id: str
    state: SubQueryState = SubQueryState.STARTED
    finding: dict | None = None
    error: str | None = None
    # state transitions: started -> running -> (completed | failed | timed_out); terminal immutable


@dataclass
class TraceContext:
    trace_id: str
    created_at: str = ""


@dataclass
class AggregationResult:
    successes: list
    failures: list
    answer: str | None
    partial: bool


def is_json_serializable(x) -> bool:
    try:
        json.dumps(x)
        return True
    except (TypeError, ValueError):
        return False


def validate_flat(sub_queries: list) -> None:
    """FR-002: reject any decomposition with inter-task dependency (a DAG). Deterministic (code).
    FR-003: each sub-query config MUST be JSON-serializable."""
    for sq in sub_queries:
        if sq.depends_on:
            raise DependencyError(
                f"sub_query {sq.sub_query_id} depends on {sq.depends_on}; "
                "system supports only fully independent parallel tasks."
            )
    for sq in sub_queries:
        if not sq.sub_query or not sq.sub_query.strip():
            raise ValueError(f"sub_query {sq.sub_query_id} is empty")
        if not is_json_serializable(sq.config):
            raise TypeError(f"sub_query {sq.sub_query_id} config is not JSON-serializable (FR-003)")
