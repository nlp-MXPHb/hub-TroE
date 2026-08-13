# Tool Contracts

External interfaces exposed by the agent framework. All inputs/outputs are JSON-serializable (Constitution Art. 3.2).

## web_search
- **Scope**: main agent + subagents.
- **Input**: `{ query: str, **opts }` (JSON-serializable).
- **Output**: `{ results: list[{title, url, snippet}], error: str | null }`.
- **Semantics**: a single search call; pure I/O; stateless.
- **Error contract**: on failure returns `{ results: [], error: str }` — it does NOT raise to the caller; the caller decides whether to treat it as empty or failed.

## dispatch_subagents
- **Scope**: main agent only.
- **Input**: `{ sub_queries: list[ResearchSubQuery], trace_id: str }`.
- **Output**: `{ aggregation: AggregationResult, status_events: list[{type, sub_query_id, error?}] }` where `type ∈ {subtask_started, subtask_completed, subtask_failed}`.
- **Semantics**: decomposition is performed by the caller (main agent) before invocation; this tool dispatches subagents to the bounded pool, emits coarse status events, and enforces `TOTAL_TIMEOUT`, the runaway guard, and cooperative cancel.
- **Contract guarantees**:
  - Returns even if some or all subagents fail (Art. 2.3 Graceful Degradation).
  - `status_events` contain only coarse events — never internal ReAct reasoning or search snippets (Art. 2.4).
  - If `sub_queries` exhibit inter-dependency, raises `DependencyError` before dispatch (FR-002).

## Subagent runner contract (internal)
- **Input**: `{ sub_query: str, config: dict (incl. trace_id, max_iterations, cancel_flag) }`.
- **Output**: `{ finding: dict }` (JSON, ≤ `size_cap`) OR raises (caught by the scheduler → marked failed).
- **Semantics**: a ReAct loop with `web_search` only; checks the `cancel_flag` at each iteration; no shared mutable state with siblings or the main agent (Art. 2.1).
