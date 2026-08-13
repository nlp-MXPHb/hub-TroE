"""Constitution Quality Gates: thread-leak (10 concurrent -> 0 residual) + exception isolation (T028)."""
import threading
import time
from tools.dispatch_subagents import dispatch_subagents
from models import ResearchSubQuery


class FakeLLM:
    def chat(self, m):
        return "AGG"

    def chat_json(self, m):
        return {}


def test_no_thread_leak_after_10_concurrent():
    subs = [ResearchSubQuery(f"s{i}", f"q{i}") for i in range(10)]

    def runner(sq):
        return {"answer": "ok"}

    res = dispatch_subagents(subs, llm=FakeLLM(), runner=runner, config={"max_workers": 10})
    assert len(res.successes) == 10
    time.sleep(0.5)  # let pool worker threads exit after shutdown
    workers = [t for t in threading.enumerate() if "ThreadPoolExecutor" in t.name]
    assert workers == [], f"lingering worker threads: {workers}"


def test_exception_isolation_does_not_crash_master():
    subs = [ResearchSubQuery(f"s{i}", f"q{i}") for i in range(4)]

    def runner(sq):
        if sq.sub_query_id in {"s0", "s3"}:
            raise RuntimeError("boom")
        return {"answer": "ok"}

    res = dispatch_subagents(subs, llm=FakeLLM(), runner=runner, config={"max_workers": 4})
    assert len(res.successes) == 2 and len(res.failures) == 2
    assert res.answer and "部分子任务" in res.answer  # master still returns a valid response
