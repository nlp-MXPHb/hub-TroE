"""US4: one subagent raises -> siblings continue (FR-013, SC-008, T020)."""
from tools.dispatch_subagents import dispatch_subagents
from models import ResearchSubQuery


class FakeLLM:
    def chat(self, m):
        return "AGG"

    def chat_json(self, m):
        return {}


def test_one_subagent_raises_siblings_continue():
    subs = [ResearchSubQuery(f"s{i}", f"q{i}") for i in range(3)]

    def runner(sq):
        if sq.sub_query_id == "s1":
            raise RuntimeError("boom")
        return {"sub_query_id": sq.sub_query_id, "answer": "ok"}

    res = dispatch_subagents(subs, llm=FakeLLM(), runner=runner, config={"max_workers": 3})
    assert len(res.successes) == 2          # siblings survived
    assert len(res.failures) == 1
    assert res.failures[0].task_id == "s1"
    assert res.partial is True
