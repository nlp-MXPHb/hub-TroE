"""Main agent: ReAct loop with LLM auto-routing (FR-001/017).

Simple query -> web_search; multi-faceted -> dispatch_subagents.
Rejects non-flat decompositions (FR-002). Returns the final answer text.
status_callback / cancel_event are forwarded to dispatch_subagents (US2/US4).
"""
import json
from models import DependencyError, ResearchSubQuery
from observability import generate_trace_id, log_event
from tools.dispatch_subagents import dispatch_subagents
from tools.web_search import web_search

SYSTEM_PROMPT = (
    "You are a research orchestrator. For a simple single-faceted query, call web_search. "
    "For a multi-faceted query, call dispatch_subagents with independent sub-queries. "
    'Respond with JSON: {"thought": str, "action": {"tool": "web_search"|"dispatch_subagents"|"final", '
    '"query": str | "sub_queries": [...] | "answer": str}}. '
    "sub_queries items: {sub_query_id, sub_query, depends_on: []}. "
    "When the research is done, return tool='final' with the final answer."
)


class MainAgent:
    def __init__(self, *, llm, search_backend=None, config=None):
        self.llm = llm
        self.search_backend = search_backend
        self.config = config or {}

    def run(self, query: str, status_callback=None, cancel_event=None) -> str:
        trace_id = generate_trace_id()
        log_event(trace_id, "request_start", query)
        history = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        max_iter = self.config.get("max_iterations", 5)
        rejected = False
        for _ in range(max_iter):
            decision = self.llm.chat_json(history)
            action = decision.get("action", {})
            tool = action.get("tool")
            if tool == "web_search":
                res = web_search(action.get("query", ""), backend=self.search_backend)
                if res["results"]:
                    content = f"results: {json.dumps(res['results'], ensure_ascii=False)}"
                else:
                    err = f" (error: {res['error']})" if res["error"] else ""
                    content = (f"results: []{err} - no results. Do not re-search; "
                               "return tool='final' with your best-effort answer.")
                history.append({"role": "assistant", "content": json.dumps(decision, ensure_ascii=False)})
                history.append({"role": "user", "content": content})
            elif tool == "dispatch_subagents":
                subs = [ResearchSubQuery(**s) for s in action.get("sub_queries", [])]
                try:
                    result = dispatch_subagents(
                        subs, llm=self.llm, search_backend=self.search_backend,
                        config=self.config, trace_id=trace_id,
                        status_callback=status_callback, cancel_event=cancel_event,
                    )
                except DependencyError as e:
                    log_event(trace_id, "dependency_rejected", str(e))
                    rejected = True
                    history.append({"role": "assistant", "content": json.dumps(decision, ensure_ascii=False)})
                    history.append({"role": "user", "content": (
                        f"Rejected: {e}. Re-decompose into fully independent sub-queries "
                        "(every depends_on empty) and call dispatch_subagents again.")})
                    continue
                if result.answer is None:
                    return "全部子任务失败：" + ", ".join(f"{t.task_id}:{t.error}" for t in result.failures)
                return result.answer
            elif tool == "final":
                return action.get("answer", "")
            else:
                history.append({"role": "user", "content": "Invalid action."})
        if rejected:
            return "当前系统仅支持完全独立的并行任务，请将问题拆分为独立子问题后重试。"
        return "未能生成回答。"
