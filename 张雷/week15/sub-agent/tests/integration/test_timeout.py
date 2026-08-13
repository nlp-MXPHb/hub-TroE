"""US4: TOTAL_TIMEOUT cancels outstanding subagents (FR-010, T021)."""
import threading
import time
from tools.dispatch_subagents import dispatch_subagents
from models import ResearchSubQuery, SubQueryState


class FakeLLM:
    def chat(self, m):
        return "AGG"

    def chat_json(self, m):
        return {}


def test_total_timeout_cancels_outstanding():
    cancel_event = threading.Event()
    subs = [ResearchSubQuery(f"s{i}", f"q{i}") for i in range(3)]

    def runner(sq):  # cooperative: blocks, checking cancel_event
        for _ in range(100):
            if cancel_event.wait(0.05):
                raise RuntimeError("cancelled")
        return {"answer": "ok"}

    t0 = time.monotonic()
    res = dispatch_subagents(subs, llm=FakeLLM(), runner=runner,
                             config={"max_workers": 3, "total_timeout": 0.3},
                             cancel_event=cancel_event)
    elapsed = time.monotonic() - t0
    assert elapsed < 1.5                          # returned promptly, did not run full 5s
    assert len(res.successes) == 0
    assert len(res.failures) == 3
    assert all(t.state == SubQueryState.TIMED_OUT for t in res.failures)
