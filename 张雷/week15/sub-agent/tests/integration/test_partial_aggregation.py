"""Integration: partial failure + all-fail (SC-003/004, T009)."""
from tools.dispatch_subagents import dispatch_subagents
from models import ResearchSubQuery


class FakeLLM:
    def chat(self, messages):
        return "AGG"

    def chat_json(self, messages):
        return {}


def _runner(fail_ids):
    def r(sq):
        if sq.sub_query_id in fail_ids:
            raise RuntimeError("boom")
        return {"sub_query_id": sq.sub_query_id, "answer": "ok"}
    return r


def test_partial_failure_returns_disclosure():
    subs = [ResearchSubQuery(f"s{i}", f"q{i}") for i in range(5)]
    res = dispatch_subagents(subs, llm=FakeLLM(), runner=_runner({"s1", "s3"}),
                             config={"max_workers": 5})
    assert len(res.successes) == 3 and len(res.failures) == 2
    assert res.partial is True
    assert "部分子任务" in res.answer
    assert "2" in res.answer


def test_all_failure_returns_no_answer():
    subs = [ResearchSubQuery(f"s{i}", f"q{i}") for i in range(3)]
    res = dispatch_subagents(subs, llm=FakeLLM(), runner=_runner({"s0", "s1", "s2"}),
                             config={"max_workers": 3})
    assert res.answer is None
    assert len(res.failures) == 3
