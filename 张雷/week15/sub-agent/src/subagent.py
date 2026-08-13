"""Subagent: independent ReAct loop with web_search only.

Constitution Art. 2.1 (Thread & Logical Isolation): pure function of
(sub_query, config) -> finding dict; no shared mutable state. Checks a cancel
flag each iteration; raises RunawayError when max_iterations is exceeded (FR-011).
FR-015: finding MUST be JSON-serializable before return.
"""
import json
from models import RunawayError, is_json_serializable
from observability import log_event
from tools.web_search import web_search

SYSTEM_PROMPT = (
    "You are a research subagent. Investigate the sub-query using web_search, "
    "then return a final answer. Each step respond with JSON: "
    '{"thought": str, "action": {"tool": "web_search"|"final", "query": str|"answer": str}}. '
    "When you have enough information, set tool='final' with the answer text."
)


def run_subagent(sub_query, config, *, llm, search_backend=None,
                 cancel_event=None, trace_id="", size_cap=8192) -> dict:
    log_event(trace_id, "subagent_started", sub_query.sub_query_id)
    max_iter = config.get("max_iterations", 5)
    history = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": sub_query.sub_query},
    ]
    finding = None
    for _ in range(max_iter):
        if cancel_event is not None and cancel_event.is_set():
            raise RunawayError("cancelled")
        decision = llm.chat_json(history)
        action = decision.get("action", {})
        tool = action.get("tool")
        if tool == "web_search":
            res = web_search(action.get("query", ""), backend=search_backend)
            if res["results"]:
                content = f"search_results: {json.dumps(res['results'], ensure_ascii=False)}"
            else:
                err = f" (error: {res['error']})" if res["error"] else ""
                content = (f"search_results: []{err} - no results. Do not re-search; "
                           "return tool='final' with your best-effort answer or state "
                           "that no information was found.")
            history.append({"role": "assistant", "content": json.dumps(decision, ensure_ascii=False)})
            history.append({"role": "user", "content": content})
        elif tool == "final":
            finding = {"sub_query_id": sub_query.sub_query_id, "answer": action.get("answer", "")}
            break
        else:
            history.append({"role": "user", "content": "Invalid action; return a final answer."})
    if finding is None:
        raise RunawayError(f"exceeded max_iterations={max_iter} without a final answer")
    if not is_json_serializable(finding):  # FR-015
        raise TypeError("subagent finding is not JSON-serializable")
    if len(json.dumps(finding, ensure_ascii=False)) > size_cap:
        finding["answer"] = finding["answer"][:size_cap]   # FR-016 size cap
    log_event(trace_id, "subagent_completed", sub_query.sub_query_id)
    return finding
