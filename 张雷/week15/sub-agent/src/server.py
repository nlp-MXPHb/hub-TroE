"""Hydra web console: FastAPI + SSE (design: specs/002-web-console/design.md).

SSE contract (all events carry trace_id; FR-007: coarse events only, no internal
ReAct reasoning, search snippets, or intermediate values):
  start / routed / subtask_started / subtask_completed / subtask_failed /
  dependency_rejected / result / error / done

Run:
  uvicorn server:app --port 8002   (from src/, or `python src/server.py`)
Requires DEEPSEEK_API_KEY (or DASHSCOPE_API_KEY). The default web_search backend
returns empty results - plug a real backend in tools/web_search.py.
"""
import json
import os
import queue
import sys
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(__file__))  # bare module imports from src/

from config import CONFIG
from llm_client import LLMClient
from main_agent import MainAgent
from observability import generate_trace_id
from tools.web_search import default_backend

STATIC_DIR = Path(__file__).parent.parent / "static"

app = FastAPI(title="Hydra web console")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# trace_id -> threading.Event, for cooperative cancel (FR-012). Protected by lock.
_CANCELS: dict[str, threading.Event] = {}
_CANCELS_LOCK = threading.Lock()

# Injectable agent factory for tests; None = build from env (real LLM + default backend).
_agent_factory = None


class QueryRequest(BaseModel):
    question: str


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
def health():
    # "default_backend" = built-in stub (returns empty); any other name = plugged-in backend
    return {"status": "ok",
            "llm": bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")),
            "search_backend": default_backend.__name__}


@app.post("/cancel/{trace_id}")
def cancel(trace_id: str):
    with _CANCELS_LOCK:
        ev = _CANCELS.get(trace_id)
    if ev is None:
        return {"status": "unknown_trace_id"}
    ev.set()
    return {"status": "cancelled"}


@app.get("/logs/{trace_id}")
def logs(trace_id: str, limit: int = 200):
    """Operator view (US3): tail of log lines matching a Trace_ID. Read-only."""
    try:
        with open(CONFIG.log_file, encoding="utf-8") as f:
            lines = [ln.rstrip() for ln in f if f"[{trace_id}]" in ln][-limit:]
    except FileNotFoundError:
        lines = []
    return {"trace_id": trace_id, "lines": lines}


@app.post("/query")
def query(req: QueryRequest):
    trace_id = generate_trace_id()
    q = queue.Queue()
    SENTINEL = object()
    cancel_event = threading.Event()
    with _CANCELS_LOCK:
        _CANCELS[trace_id] = cancel_event

    def push(ev):
        ev = dict(ev)
        ev["trace_id"] = trace_id
        q.put(ev)

    def run():
        try:
            if _agent_factory is not None:
                agent = _agent_factory()
            else:
                api_key = (os.environ.get("DEEPSEEK_API_KEY")
                           or os.environ.get("DASHSCOPE_API_KEY") or "")
                llm = LLMClient(api_key=api_key, base_url=CONFIG.llm_base_url,
                                model=CONFIG.llm_model)
                agent = MainAgent(llm=llm, search_backend=default_backend,
                                  config={"max_workers": CONFIG.max_workers})

            def status_cb(ev_type, sub_query_id, *rest):
                if ev_type == "subtask_completed":
                    push({"type": ev_type, "sub_query_id": sub_query_id,
                          "duration": rest[0] if rest else None})
                elif ev_type == "subtask_failed":
                    push({"type": ev_type, "sub_query_id": sub_query_id,
                          "error": rest[0] if rest else "unknown"})
                else:
                    push({"type": ev_type, "sub_query_id": sub_query_id})

            def observer(ev):
                if ev["type"] == "routed" and ev.get("tool") == "dispatch_subagents":
                    # ids must be strings for the frontend (models already coerces)
                    push({"type": "routed", "mode": "dispatch",
                          "sub_queries": [{"sub_query_id": str(s["sub_query_id"]),
                                           "sub_query": s["sub_query"]}
                                          for s in ev.get("sub_queries", [])]})
                elif ev["type"] == "routed":
                    push({"type": "routed", "mode": "direct"})
                elif ev["type"] == "dependency_rejected":
                    push({"type": "dependency_rejected", "message": ev["message"]})
                elif ev["type"] == "result":
                    push({"type": "result", "answer": ev["answer"],
                          "partial": ev["partial"],
                          "failures": [{"task_id": str(f["task_id"]), "error": f["error"]}
                                       for f in ev.get("failures", [])]})

            agent.run(req.question, status_callback=status_cb,
                      cancel_event=cancel_event, trace_id=trace_id,
                      observer=observer)
            # final answer arrives via observer's result event (FR-007: coarse only)
        except Exception as e:  # fail loudly to the client, never silently
            push({"type": "error", "message": f"{type(e).__name__}: {str(e)[:200]}"})
        finally:
            with _CANCELS_LOCK:
                _CANCELS.pop(trace_id, None)
            push({"type": "done"})
            q.put(SENTINEL)

    threading.Thread(target=run, daemon=True).start()

    def event_stream():
        yield "data: " + json.dumps({"type": "start", "trace_id": trace_id,
                                     "question": req.question},
                                    ensure_ascii=False) + "\n\n"
        while True:
            ev = q.get()
            if ev is SENTINEL:
                break
            yield "data: " + json.dumps(ev, ensure_ascii=False) + "\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8002, reload=False)
