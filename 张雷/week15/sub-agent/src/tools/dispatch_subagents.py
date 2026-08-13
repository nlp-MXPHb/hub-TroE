"""dispatch_subagents tool (main-agent only; contracts/tools.md).

Validates flat dependency (FR-002), dispatches subagents in parallel via the scheduler,
and aggregates results with partial-success tolerance. `runner` is injectable for testing.
"""
import threading
import subagent as subagent_mod
from aggregator import aggregate
from models import validate_flat
from observability import log_event
from scheduler import dispatch


def dispatch_subagents(sub_queries, *, llm, search_backend=None, config=None,
                       trace_id="", runner=None, status_callback=None, cancel_event=None):
    config = config or {}
    validate_flat(sub_queries)  # FR-002 -> DependencyError before any dispatch
    max_workers = config.get("max_workers", 4)
    size_cap = config.get("size_cap", 8192)
    total_timeout = config.get("total_timeout")
    if cancel_event is None:
        cancel_event = threading.Event()
    if runner is None:
        def runner(sq):
            return subagent_mod.run_subagent(
                sq, config, llm=llm, search_backend=search_backend,
                cancel_event=cancel_event, trace_id=trace_id, size_cap=size_cap,
            )
    log_event(trace_id, "dispatch", f"{len(sub_queries)} subagents")
    tasks = dispatch(sub_queries, runner=runner, max_workers=max_workers, trace_id=trace_id,
                     status_callback=status_callback, total_timeout=total_timeout,
                     cancel_event=cancel_event)
    return aggregate(tasks, llm=llm, trace_id=trace_id, size_cap=size_cap)
