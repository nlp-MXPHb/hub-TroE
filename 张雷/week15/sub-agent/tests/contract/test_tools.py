"""Contract tests for web_search and dispatch_subagents (T007)."""
import pytest
from tools.web_search import web_search
from tools.dispatch_subagents import dispatch_subagents
from models import ResearchSubQuery, DependencyError, RunawayError
from subagent import run_subagent


class FakeLLM:
    def __init__(self, json_resp=None, text="AGG"):
        self._json = json_resp or {}
        self.text = text

    def chat(self, messages):
        return self.text

    def chat_json(self, messages):
        return self._json


# --- web_search contract (contracts/tools.md) ---
def test_web_search_contract_shape():
    r = web_search("q", backend=lambda q, **o: [{"title": "t", "url": "u", "snippet": "s"}])
    assert set(r) >= {"results", "error"}
    assert r["error"] is None and len(r["results"]) == 1


def test_web_search_never_raises_on_backend_error():
    def boom(q, **o):
        raise RuntimeError("backend down")
    r = web_search("q", backend=boom)
    assert r["results"] == [] and r["error"] is not None


# --- dispatch_subagents contract: rejects non-flat (FR-002) ---
def test_dispatch_rejects_dependent_subqueries():
    subs = [ResearchSubQuery("s1", "A"), ResearchSubQuery("s2", "B", depends_on=["s1"])]
    with pytest.raises(DependencyError):
        dispatch_subagents(subs, llm=FakeLLM(), runner=lambda sq: {})


# --- subagent ReAct loop (T010) ---
class FinalLLM:
    def chat_json(self, messages):
        return {"thought": "x", "action": {"tool": "final", "answer": "42"}}

    def chat(self, messages):
        return "42"


def test_subagent_returns_finding():
    sq = ResearchSubQuery("s1", "meaning of life")
    f = run_subagent(sq, {}, llm=FinalLLM(), search_backend=lambda q, **o: [], trace_id="t1")
    assert f["answer"] == "42" and f["sub_query_id"] == "s1"


class LoopLLM:
    def chat_json(self, messages):
        return {"thought": "x", "action": {"tool": "web_search", "query": "q"}}

    def chat(self, messages):
        return "x"


def test_subagent_runaway_raises():
    sq = ResearchSubQuery("s1", "q")
    with pytest.raises(RunawayError):
        run_subagent(sq, {"max_iterations": 2}, llm=LoopLLM(),
                     search_backend=lambda q, **o: [], trace_id="t1")
