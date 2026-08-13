# Data Model

All entities are JSON-serializable (Constitution v2.0.0 Art. 3.2). There is no cross-process IPC in the thread model; JSON is the data contract for logging, aggregation, and traceability.

## ResearchSubQuery
A single independent facet of the user's question.
- `sub_query_id`: str (unique within a request)
- `sub_query`: str (the facet text, non-empty)
- `config`: dict (JSON; e.g., `max_iterations`, `locale`, `trace_id`)
- **Validation**: `sub_query` non-empty; `config` JSON-serializable (FR-003); zero dependency on sibling sub-queries (FR-002).
- **Relationships**: 1 request → N `ResearchSubQuery` (peer-level).

## SubagentTask
The unit of parallel work — a ReAct loop with `web_search`.
- `task_id`: str
- `sub_query_id`: str (FK → ResearchSubQuery)
- `state`: enum `{started, running, completed, failed, timed_out}`
- `finding`: dict | null (JSON finding on success)
- `error`: str | null (brief error on failure)
- **State transitions**: `started → running → (completed | failed | timed_out)`. Terminal states are immutable.
- **Validation**: terminal `finding` MUST be JSON-serializable and ≤ `size_cap` (FR-016).

## Tool
- `name`: str (`web_search` | `dispatch_subagents`)
- `scope`: enum `{main_only, main_and_sub}` — `web_search`: `main_and_sub`; `dispatch_subagents`: `main_only`.
- `contract`: see [contracts/tools.md](contracts/tools.md).

## TraceContext
- `trace_id`: str (globally unique)
- `created_at`: ISO-8601 timestamp
- **Propagation**: passed into every `SubagentTask` via `config`; logged on every state change (FR-014).

## AggregationResult
- `successes`: list[SubagentTask] (`state=completed`)
- `failures`: list[SubagentTask] (`state ∈ {failed, timed_out}`)
- `answer`: str (LLM-generated from `successes`; prefixed with partial-result disclosure when `failures` is non-empty)
- `partial`: bool
- **Validation**: if `len(successes) == 0` → no `answer`; return global failure (FR-009).
