"""US2: only coarse status events; no ReAct reasoning/snippets leak (SC-006, FR-007, T016)."""
from tools.dispatch_subagents import dispatch_subagents
from models import ResearchSubQuery


class FakeLLM:
    def chat(self, m):
        return "AGG"

    def chat_json(self, m):
        return {}


def test_only_coarse_status_events_emitted():
    events = []

    def cb(typ, sid, err=None):
        events.append((typ, sid, err))

    subs = [ResearchSubQuery("s1", "A"), ResearchSubQuery("s2", "B")]

    def runner(sq):
        if sq.sub_query_id == "s2":
            raise RuntimeError("boom")
        return {"sub_query_id": sq.sub_query_id, "answer": "ok"}

    dispatch_subagents(subs, llm=FakeLLM(), runner=runner, config={"max_workers": 2},
                       status_callback=cb)
    types = {e[0] for e in events}
    assert types <= {"subtask_started", "subtask_completed", "subtask_failed"}
    # coarse only: sid is a plain id; err (when present) is a brief string, never internal state
    for typ, sid, err in events:
        assert isinstance(sid, str)
        if typ == "subtask_failed":
            assert isinstance(err, str) and "answer" not in err and "thought" not in err
    assert "subtask_started" in types
    assert "subtask_completed" in types
    assert "subtask_failed" in types
