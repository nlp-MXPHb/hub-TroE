"""US4: user cancel tears down in-flight subagents, no lingering (FR-012, SC-002, T022)."""
import threading
import time
from tools.dispatch_subagents import dispatch_subagents
from models import ResearchSubQuery


class FakeLLM:
    def chat(self, m):
        return "AGG"

    def chat_json(self, m):
        return {}


def test_user_cancel_tears_down_inflight():
    cancel_event = threading.Event()
    subs = [ResearchSubQuery(f"s{i}", f"q{i}") for i in range(3)]

    def runner(sq):  # blocks until cancelled, then raises (cooperative)
        cancel_event.wait(5)
        raise RuntimeError("cancelled")

    holder = {}

    def run():
        holder["res"] = dispatch_subagents(subs, llm=FakeLLM(), runner=runner,
                                           config={"max_workers": 3}, cancel_event=cancel_event)

    th = threading.Thread(target=run)
    th.start()
    time.sleep(0.2)
    cancel_event.set()
    th.join(timeout=3)
    assert not th.is_alive(), "dispatch did not return after cancel"
    res = holder["res"]
    assert len(res.successes) == 0
    assert len(res.failures) == 3
