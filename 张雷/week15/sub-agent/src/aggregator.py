"""Aggregator: partial-success aggregation (Constitution Art. 2.3).

>=1 success -> synthesize an answer from successes; prefix a disclosure if any failed (FR-008).
0 successes  -> refuse aggregation, answer=None (FR-009).
FR-016: enforce size cap on findings before synthesis (defense in depth).
"""
import json
from models import AggregationResult, SubQueryState
from observability import log_event

DISCLOSURE = "以下结果基于部分子任务生成，另有 {n} 项任务失败：{names}。\n"


def aggregate(tasks, *, llm, trace_id="", size_cap=8192) -> AggregationResult:
    successes = [t for t in tasks if t.state == SubQueryState.COMPLETED]
    failures = [t for t in tasks if t.state != SubQueryState.COMPLETED]
    log_event(trace_id, "aggregate", f"successes={len(successes)} failures={len(failures)}")
    if not successes:
        return AggregationResult(successes=[], failures=failures, answer=None, partial=False)
    findings = [t.finding for t in successes if t.finding]
    for f in findings:  # FR-016 size cap
        if isinstance(f, dict) and isinstance(f.get("answer"), str) and len(f["answer"]) > size_cap:
            f["answer"] = f["answer"][:size_cap]
    messages = [
        {"role": "system", "content": "Synthesize one consolidated answer from the research findings. Return plain text."},
        {"role": "user", "content": json.dumps(findings, ensure_ascii=False)},
    ]
    answer = llm.chat(messages)
    if failures:
        names = ", ".join(t.task_id for t in failures)
        answer = DISCLOSURE.format(n=len(failures), names=names) + answer
    return AggregationResult(successes=successes, failures=failures, answer=answer, partial=bool(failures))
