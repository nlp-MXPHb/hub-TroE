# Quickstart Validation Guide

Runnable validation scenarios proving the feature end-to-end. Implementation code lives in `tasks.md` and the implementation phase; this is a validation/run guide only.

## Prerequisites
- conda env `py312` active; LLM key set (DeepSeek / DashScope); `web_search` capability available.
- Constitution v2.0.0 governing.

## Setup
- Install: `pip install -e .` (or `export PYTHONPATH=src`).
- Smoke import: `python -c "import main_agent, subagent, scheduler, aggregator, observability"`.

## Validation scenarios

1. **Simple query → direct `web_search` (no subagents)**
   - Run: submit a single-faceted query.
   - Expect: one answer; log shows `routing=web_search`; zero subagent tasks spawned (FR-017).

2. **Multi-faceted query → parallel subagents**
   - Run: submit a query needing ≥2 angles.
   - Expect: `routing=dispatch_subagents`; ≥2 `subtask_started` then `subtask_completed`; one consolidated answer (SC-001).

3. **Partial failure (5 subagents, 2 forced to fail)**
   - Expect: valid answer from 3 successes; answer prefixed with a partial-result disclosure naming the 2 failures (SC-003).

4. **All subagents fail**
   - Expect: a global-failure message with per-subagent detail; no unhandled exception or stack trace to the user (SC-004).

5. **User cancel**
   - Run: submit a multi-faceted query, cancel mid-run.
   - Expect: in-flight subagents cooperatively cancelled; pool shut down; zero lingering tasks (FR-012, SC-002).

6. **Trace_ID full-lifecycle trace**
   - Expect: filtering the log by the request's Trace_ID reveals the complete lifecycle (routing → decomposition → dispatch → each start/end/fail → aggregation), each line timestamped (SC-005).

7. **Cleanup check**
   - After any run: zero lingering subagent tasks/threads (SC-002).

## References
- Requirements/Success Criteria: [spec.md](spec.md)
- Entities & state transitions: [data-model.md](data-model.md)
- Tool schemas & guarantees: [contracts/tools.md](contracts/tools.md)
