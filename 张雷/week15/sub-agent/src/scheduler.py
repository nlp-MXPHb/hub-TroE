"""Scheduler: bounded ThreadPoolExecutor dispatch (Constitution Art. 3.1).

FR-010: global total_timeout -> cancel remaining, mark TIMED_OUT.
FR-012/013: cooperative cancel via cancel_event; pool shutdown(wait=False, cancel_futures=True);
            a subagent exception -> task FAILED, siblings continue.
Art. 2.4: status_callback emits only coarse events (subtask_started/completed/failed);
completed carries per-task duration for wall-clock stats.
"""
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from models import SubagentTask, SubQueryState
from observability import log_event

_POLL = 0.05  # poll interval so cancel_event / deadline are noticed promptly


def dispatch(sub_queries, *, runner, max_workers=4, trace_id="", status_callback=None,
             total_timeout=None, cancel_event=None):
    tasks = []
    deadline = (time.monotonic() + total_timeout) if total_timeout else None
    pool = ThreadPoolExecutor(max_workers=max_workers)
    future_to_sq = {pool.submit(runner, sq): sq for sq in sub_queries}
    started = {fut: time.monotonic() for fut in future_to_sq}
    for sq in sub_queries:
        if status_callback:
            status_callback("subtask_started", sq.sub_query_id)
    remaining = set(future_to_sq)

    def _collect(fut):
        sq = future_to_sq[fut]
        task = SubagentTask(task_id=sq.sub_query_id, sub_query_id=sq.sub_query_id)
        try:
            task.finding = fut.result()
            task.state = SubQueryState.COMPLETED
            if status_callback:
                status_callback("subtask_completed", sq.sub_query_id,
                                round(time.monotonic() - started[fut], 2))
        except Exception as e:  # FR-013: isolate failure, siblings unaffected
            task.state = SubQueryState.FAILED
            task.error = str(e)
            log_event(trace_id, "subagent_failed", f"{sq.sub_query_id}: {e}")
            if status_callback:
                status_callback("subtask_failed", sq.sub_query_id, str(e))
        tasks.append(task)

    def _cancel_remaining(state, reason):
        if cancel_event is not None:
            cancel_event.set()  # cooperative signal to running subagents
        for fut in list(remaining):
            fut.cancel()
            sq = future_to_sq[fut]
            tasks.append(SubagentTask(task_id=sq.sub_query_id, sub_query_id=sq.sub_query_id,
                                      state=state, error=reason))
            log_event(trace_id, "subagent_failed", f"{sq.sub_query_id}: {reason}")
            if status_callback:
                status_callback("subtask_failed", sq.sub_query_id, reason)

    try:
        while remaining:
            if cancel_event is not None and cancel_event.is_set():        # FR-012 user cancel
                _cancel_remaining(SubQueryState.FAILED, "cancelled")
                break
            now = time.monotonic()
            if deadline is not None and now >= deadline:                  # FR-010 global timeout
                _cancel_remaining(SubQueryState.TIMED_OUT, "total_timeout")
                break
            t = _POLL
            if deadline is not None:
                t = min(t, deadline - now)
            done, remaining = wait(remaining, timeout=t, return_when=FIRST_COMPLETED)
            for fut in done:
                _collect(fut)
    finally:
        if cancel_event is not None:
            cancel_event.set()
        pool.shutdown(wait=False, cancel_futures=True)
    return tasks
