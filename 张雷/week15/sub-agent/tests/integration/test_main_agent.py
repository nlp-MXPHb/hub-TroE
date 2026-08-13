"""Main-agent routing paths: direct web_search (simple) and all-subagents-fail (T014 coverage)."""
from main_agent import MainAgent


class WebSearchLLM:
    """1st call -> web_search; 2nd -> final answer (simple-query path)."""
    def __init__(self):
        self.n = 0

    def chat_json(self, m):
        self.n += 1
        if self.n == 1:
            return {"action": {"tool": "web_search", "query": "q"}}
        return {"action": {"tool": "final", "answer": "simple answer"}}

    def chat(self, m):
        return "x"


class AllFailLLM:
    """1st call -> dispatch; later -> always web_search (subagents never finalize -> runaway)."""
    def __init__(self):
        self.n = 0

    def chat_json(self, m):
        self.n += 1
        if self.n == 1:
            return {"action": {"tool": "dispatch_subagents",
                    "sub_queries": [{"sub_query_id": "s1", "sub_query": "A", "depends_on": []}]}}
        return {"action": {"tool": "web_search", "query": "q"}}

    def chat(self, m):
        return "x"


def test_main_agent_simple_query_uses_websearch_then_final():
    agent = MainAgent(llm=WebSearchLLM(),
                      search_backend=lambda q, **o: [{"title": "t", "url": "u", "snippet": "s"}])
    assert agent.run("a simple single-faceted question") == "simple answer"


def test_main_agent_all_subagents_fail_returns_failure_message():
    agent = MainAgent(llm=AllFailLLM(), search_backend=lambda q, **o: [],
                      config={"max_iterations": 2})
    ans = agent.run("multi-faceted question")
    assert "全部子任务失败" in ans
