"""Main agent: ReAct loop with LLM auto-routing (FR-001/017).

Simple query -> web_search; multi-faceted -> dispatch_subagents.
Rejects non-flat decompositions (FR-002). Returns the final answer text.
status_callback / cancel_event are forwarded to dispatch_subagents (US2/US4).
Optional `observer` receives coarse lifecycle dicts (routed / dependency_rejected /
result) so callers like the web console can render routing + decomposition
without parsing the answer text (FR-007: no internal reasoning in events).
"""
import json
from models import DependencyError, ResearchSubQuery
from observability import generate_trace_id, log_event
from tools.dispatch_subagents import dispatch_subagents
from tools.web_search import web_search


SYSTEM_PROMPT = (
    "你是一个研究型协调器。对于简单的单维度查询，直接调用 web_search 工具。"
    "对于复杂的多维度查询，则调用 dispatch_subagents 工具，并下发给多个独立的子查询。"
    '请以 JSON 格式响应：{"thought": "思考内容", "action": {"tool": "web_search" | "dispatch_subagents" | "final", '
    '"query": "搜索词" | "sub_queries": [...] | "answer": "答案文本"}}。'
    "sub_queries 中的每个条目格式为：{sub_query_id, sub_query, depends_on: []}。"
    "当研究任务全部完成后，将 tool 设置为 'final'，并附带最终答案。"
)


class MainAgent:
    def __init__(self, *, llm, search_backend=None, config=None):
        self.llm = llm
        self.search_backend = search_backend
        self.config = config or {}

    def run(self, query: str, status_callback=None, cancel_event=None,
            trace_id=None, observer=None) -> str:
        if trace_id is None:
            trace_id = generate_trace_id()
        log_event(trace_id, "request_start", query)
        history = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        max_iter = self.config.get("max_iterations", 5)
        rejected = False

        def finish(answer, partial=False, failures=None):
            if observer:
                observer({"type": "result", "answer": answer,
                          "partial": partial, "failures": failures or []})
            return answer

        for _ in range(max_iter):
            decision = self.llm.chat_json(history)
            action = decision.get("action", {})
            tool = action.get("tool")
            if tool == "web_search":
                if observer:
                    observer({"type": "routed", "tool": "web_search"})
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
                if observer:
                    observer({"type": "routed", "tool": "dispatch_subagents",
                              "sub_queries": [{"sub_query_id": s.sub_query_id,
                                               "sub_query": s.sub_query} for s in subs]})
                try:
                    result = dispatch_subagents(
                        subs, llm=self.llm, search_backend=self.search_backend,
                        config=self.config, trace_id=trace_id,
                        status_callback=status_callback, cancel_event=cancel_event,
                    )
                except DependencyError as e:
                    log_event(trace_id, "dependency_rejected", str(e))
                    if observer:
                        observer({"type": "dependency_rejected", "message": str(e)})
                    rejected = True
                    history.append({"role": "assistant", "content": json.dumps(decision, ensure_ascii=False)})
                    history.append({"role": "user", "content": (
                        f"Rejected: {e}. Re-decompose into fully independent sub-queries "
                        "(every depends_on empty) and call dispatch_subagents again.")})
                    continue
                failures = [{"task_id": t.task_id, "error": t.error} for t in result.failures]
                if result.answer is None:
                    return finish("全部子任务失败：" + ", ".join(f"{t.task_id}:{t.error}"
                                                                 for t in result.failures),
                                  partial=False, failures=failures)
                return finish(result.answer, partial=result.partial, failures=failures)
            elif tool == "final":
                return finish(action.get("answer", ""))
            else:
                history.append({"role": "user", "content": "Invalid action."})
        if rejected:
            return finish("当前系统仅支持完全独立的并行任务，请将问题拆分为独立子问题后重试。")
        return finish("未能生成回答。")
