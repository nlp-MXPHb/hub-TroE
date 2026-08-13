"""Integration: multi-faceted query -> parallel subagents -> consolidated answer (SC-001, T008)."""
from main_agent import MainAgent
from tools.dispatch_subagents import dispatch_subagents
from models import ResearchSubQuery


class FakeLLM:
    def __init__(self, text="CONSOLIDATED ANSWER"):
        self.text = text

    def chat(self, messages):
        return self.text

    def chat_json(self, messages):
        return {}


def _runner(findings):
    def r(sq):
        return {"sub_query_id": sq.sub_query_id, "answer": findings.get(sq.sub_query_id, "result")}
    return r


def test_parallel_dispatch_aggregates_all_successes():
    subs = [ResearchSubQuery("s1", "A"), ResearchSubQuery("s2", "B"), ResearchSubQuery("s3", "C")]
    res = dispatch_subagents(subs, llm=FakeLLM(),
                             runner=_runner({"s1": "r1", "s2": "r2", "s3": "r3"}),
                             config={"max_workers": 3})
    assert len(res.successes) == 3 and len(res.failures) == 0
    assert res.partial is False
    assert "CONSOLIDATED" in res.answer


# --- main agent routing (T014): dispatch path end-to-end ---
class RoutingLLM:
    """chat_json: 1st call -> dispatch; later calls -> subagent final. chat -> aggregation text."""
    def __init__(self):
        self.n = 0

    def chat_json(self, messages):
        self.n += 1
        if self.n == 1:
            return {"thought": "r", "action": {"tool": "dispatch_subagents",
                    "sub_queries": [{"sub_query_id": "s1", "sub_query": "A", "depends_on": []}]}}
        return {"thought": "x", "action": {"tool": "final", "answer": "sub finding"}}

    def chat(self, messages):
        return "FINAL CONSOLIDATED"


def test_main_agent_routes_dispatch_and_aggregates():
    agent = MainAgent(llm=RoutingLLM(), search_backend=lambda q, **o: [], config={"max_workers": 2})
    answer = agent.run("research this topic from multiple angles")
    assert "FINAL CONSOLIDATED" in answer
