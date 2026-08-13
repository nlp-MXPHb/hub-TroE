# Research: Parallel Multi-Subagent Research Agent

Phase 0 consolidation. The primary open question (constitution conflict) is resolved by Amendment 2026-08-13-A; remaining items are best-practice decisions.

## D1: Execution model — ThreadPoolExecutor (threads), not processes
- **Decision**: Subagents run as threads on a bounded `ThreadPoolExecutor`.
- **Rationale**: Workload is I/O-bound web search; the GIL does not block network I/O; threads avoid multiprocessing IPC/pickle overhead. Constitution amended to v2.0.0 (Art. 2.1 → Thread & Logical Isolation) to align governance with this.
- **Alternatives rejected**: `multiprocessing` / `ProcessPoolExecutor` — IPC + serialization overhead is unjustified for stateless I/O-bound search loops, and would require pickling LLM/search clients (often non-serializable).

## D2: Isolation discipline for threads
- **Decision**: Logical isolation — each subagent is a pure function of `(sub_query, config) -> finding`; no shared mutable state, no globals/singletons; communication only via args (in) and return value (out).
- **Rationale**: Threads share memory, so isolation is a programming discipline, not OS-enforced (documented weakening in Constitution v2.0.0). Stateless ReAct loops make this safe.
- **Alternatives rejected**: OS process isolation (see D1).

## D3: Cancellation in Python threads
- **Decision**: Cooperative cancellation — a cancel flag checked at ReAct-loop iteration boundaries, plus `Future.cancel()` for not-yet-started tasks; on global timeout or user cancel, `ThreadPoolExecutor.shutdown(wait=False, cancel_futures=True)`.
- **Rationale**: Python threads cannot be force-killed; `SIGTERM`/`terminate()` apply to processes, not threads. Cooperative cancel is the only sound option.
- **Alternatives rejected**: Daemon threads + process exit — leaves in-flight network calls unbounded; violates cleanup gate (SC-002).

## D4: ReAct loop bounds (runaway guard)
- **Decision**: Each subagent ReAct loop is capped at `max_iterations`; exceeding the cap → cancel + mark failed.
- **Rationale**: Prevents infinite reasoning loops; satisfies the Quality Gate timeout/loop test.
- **Alternatives rejected**: Pure per-subagent wall-clock — harder to attribute; iteration cap is deterministic and testable.

## D5: Result size cap
- **Decision**: Subagent findings exceeding `size_cap` are summarized/truncated before return.
- **Rationale**: Keeps aggregation and the final LLM context bounded; honors Constitution Art. 3.2 (data contract).
- **Alternatives rejected**: Stream large results — violates Minimal Streaming (Art. 2.4).

## D6: Trace_ID propagation into threads
- **Decision**: Trace_ID generated at request entry and passed into each subagent via `config`; every subagent log line includes it.
- **Rationale**: Threads share the process but logs need per-request correlation; explicit propagation (not implicit thread-local inheritance) is clearer and testable.

**Status**: All NEEDS CLARIFICATION resolved. No open unknowns remain for Phase 1.
