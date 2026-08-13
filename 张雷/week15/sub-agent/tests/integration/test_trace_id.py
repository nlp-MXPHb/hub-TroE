"""US3: one Trace_ID reconstructs the full lifecycle from the log (SC-005, FR-014, T018)."""
import uuid
from tools.dispatch_subagents import dispatch_subagents
from models import ResearchSubQuery


class FinalLLM:
    """Makes the real subagent runner return a final answer immediately (logs started/completed)."""
    def chat_json(self, m):
        return {"thought": "x", "action": {"tool": "final", "answer": "ok"}}

    def chat(self, m):
        return "ANS"


def test_trace_id_full_lifecycle_in_log():
    trace_id = "trace-test-" + uuid.uuid4().hex  # globally unique
    subs = [ResearchSubQuery("s1", "A")]
    dispatch_subagents(subs, llm=FinalLLM(), search_backend=lambda q, **o: [],
                       config={"max_workers": 1}, trace_id=trace_id)
    lines = open("logs/hydra.log", encoding="utf-8").read().splitlines()
    traced = [l for l in lines if f"[{trace_id}]" in l]
    stages = " ".join(traced)
    assert "dispatch" in stages
    assert "subagent_started" in stages
    assert "subagent_completed" in stages
    assert "aggregate" in stages
    assert len(traced) >= 3  # multiple lifecycle events, all under one Trace_ID
