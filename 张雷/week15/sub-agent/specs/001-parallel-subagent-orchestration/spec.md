# Feature Specification: Parallel Multi-Subagent Research Agent (Single-Machine, I/O-Bound)

**Feature Branch**: `[001-parallel-subagent-orchestration]`

**Created**: 2026-08-13

**Status**: Draft (revised 2026-08-13 per Constitution Amendment 2026-08-13-A)

**Input**: User description: "并行多Subagent编排系统 - 主控 ReAct agent 自主路由 web_search / dispatch_subagents；子 agent 为 ReAct(web_search)，ThreadPoolExecutor 并行；I/O 密集型多侧面调研。"

**Governing Instrument**: This feature is bound by the Hydra Constitution v2.0.0 (`.specify/memory/constitution.md`). Where this spec and the constitution conflict, the constitution prevails. The four non-negotiable tenets (Thread & Logical Isolation, Flat Dependency, Graceful Degradation, Minimal Streaming) are assumed throughout. v2.0.0 amended Art. 2.1 from OS-process isolation to thread/logical isolation to match the I/O-bound research design.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - LLM-Routed Parallel Research with Partial-Failure Tolerance (Priority: P1)

A user asks a research question. The main agent (a ReAct loop) auto-decides: for a simple single-faceted question it searches directly via `web_search`; for a multi-faceted question it calls `dispatch_subagents`, which decomposes the query into independent peer-level research sub-queries, runs each as an independent ReAct subagent (tool: `web_search`) in parallel on a thread pool, and returns one consolidated answer. If some subagents fail or time out, the system still returns a valid answer built from the successful ones, clearly disclosing which failed.

**Why this priority**: The system's sole reason to exist - answering multi-angle research questions faster than a single serial agent while never losing a whole request to one subagent failure. Without it, there is no product.

**Independent Test**: Submit a multi-faceted query that decomposes into ≥2 independent sub-queries where one subagent is intentionally made to fail; verify the system returns a consolidated answer from the survivors and names the failure. Also submit a simple query and verify it is answered by direct `web_search` with no subagents spawned.

**Acceptance Scenarios**:

1. **Given** a multi-faceted research query, **When** the user submits it, **Then** the main agent routes to `dispatch_subagents`, decomposes it into a peer-level sub-query list (count ≥2, zero inter-sub-query dependency), runs them in parallel, and returns a consolidated answer aggregating all successful findings.
2. **Given** a simple single-faceted query, **When** the user submits it, **Then** the main agent routes to direct `web_search` and returns one answer without spawning subagents.
3. **Given** 5 subagents of which 2 are forced to time out or raise, **When** the request completes, **Then** the system returns a valid aggregated answer from the 3 successful subagents and opens with a disclosure stating the result is partial and naming the 2 failures.
4. **Given** all subagents fail, **When** the request completes, **Then** the system returns a clear global-failure message with per-subagent failure detail and exposes no unhandled exception or stack trace to the user.
5. **Given** the main agent decomposes sub-queries that exhibit a dependency, **When** decomposition finishes, **Then** the system refuses to execute and prompts the user to rephrase into independent sub-queries.

---

### User Story 2 - Coarse-Grained Real-Time Status Feedback (Priority: P2)

While subagents run, the user sees real-time, coarse-grained status for each - only start, completion, and failure events with a sub-query ID and (on failure) a brief error. The user never sees internal ReAct reasoning, search snippets, or intermediate variables.

**Why this priority**: Keeps the user informed without coupling the main agent to subagent internals. Independently shippable on top of stub subagents before the engine is complete.

**Independent Test**: Drive the status channel with mock subagents that emit no internal logs; verify only the three coarse event types reach the client and no ReAct reasoning or search snippets leak.

**Acceptance Scenarios**:

1. **Given** a subagent is about to start, **When** its task is submitted to the pool, **Then** a `subtask_started` event containing the sub-query ID is pushed to the user in real time.
2. **Given** a subagent finishes normally, **When** its task completes, **Then** a `subtask_completed` event containing the sub-query ID is pushed.
3. **Given** a subagent fails or times out, **When** it terminates, **Then** a `subtask_failed` event with a brief error description is pushed - and no internal ReAct reasoning, search snippets, progress percentages, or variable values are ever pushed.

---

### User Story 3 - Full-Lifecycle Observability via Trace ID (Priority: P3)

An operator can take a single global Trace_ID and reconstruct the entire lifecycle of one user request - routing decision, decomposition, dispatch, each subagent start/finish/failure, aggregation, and any error stack - from the rolling log file.

**Why this priority**: Operability and debuggability of a multi-threaded agent system. Independently testable via log inspection with injected tasks.

**Independent Test**: Submit one request, capture its Trace_ID, then filter the log by that ID and confirm every lifecycle stage appears with timestamps.

**Acceptance Scenarios**:

1. **Given** a user request enters the system, **When** processing begins, **Then** a globally unique Trace_ID is generated and recorded against the routing decision, decomposition, dispatch, and every subagent start/end/failure log line.
2. **Given** a Trace_ID, **When** an operator filters the rolling log file by it, **Then** they can read the complete chronological lifecycle of that request, including error stacks, each line timestamped.

---

### User Story 4 - Fault Isolation, Timeout & Cancellation Cleanup (Priority: P4)

A single subagent raising an exception, hitting the runaway-loop guard, or exceeding the global timeout never affects the main agent or sibling subagents. A user cancel tears down every in-flight subagent cooperatively with no lingering tasks.

**Why this priority**: System resilience and resource hygiene. Independently testable by injecting each failure mode in isolation.

**Independent Test**: Inject a raising subagent, a dead-loop subagent, and a user cancel in separate runs; verify siblings continue, the timeout/guard fires, and the pool is shut down with zero lingering tasks afterward.

**Acceptance Scenarios**:

1. **Given** one subagent raises an exception, **When** it fails, **Then** the main agent catches it, marks that subagent failed, and all sibling subagents continue unaffected.
2. **Given** total elapsed time exceeds `TOTAL_TIMEOUT` (default 300s), **When** the deadline hits, **Then** the main agent cancels every still-running subagent and marks each as failed.
3. **Given** a subagent's ReAct loop exceeds the configured max-iterations (runaway guard), **When** the guard triggers, **Then** the main agent cancels that subagent to protect the system.
4. **Given** the user cancels a running request, **When** cancel is received, **Then** the main agent cooperatively cancels every in-flight subagent (cancel futures / cancel flag), shuts down the pool, and leaves zero lingering tasks.
5. **Given** a request has fully completed (success or failure), **When** an operator checks the pool, **Then** zero lingering subagent tasks/threads remain.

---

### Edge Cases

- **LLM emits dependent (non-flat) sub-queries**: refuse execution; return a prompt to rephrase into independent sub-queries.
- **Subagent raises an uncaught exception**: main agent catches it, marks the subagent failed, and keeps waiting for siblings.
- **Main agent crashes unexpectedly**: no auto-recovery; operator restarts manually (HA/failover is explicitly out of scope).
- **Concurrency exceeds `max_workers`**: pool queues remaining subagents and dispatches the next as earlier tasks finish and free slots.
- **`web_search` returns no results or errors for a subagent**: the subagent returns an empty/failed finding; siblings continue.
- **Subagent result payload exceeds the size cap**: summarized/truncated before return (not verbatim), to keep aggregation bounded.
- **Non-serializable object in subagent input/output**: rejected at the data-contract boundary.
- **All subagents fail**: no aggregation; return global-failure code plus per-subagent failure detail.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The main agent MUST run a ReAct loop and, based on the query, auto-route to either `web_search` (simple, single-faceted) or `dispatch_subagents` (multi-faceted); routing is LLM-decided, not a fixed topology.
- **FR-002**: When dispatching, the main agent MUST decompose the query into a peer-level, zero-dependency list of research sub-queries; it MUST reject any decomposition with inter-sub-query dependency (a DAG) and prompt the user to rephrase, rather than topologically sorting or forwarding intermediate results.
- **FR-003**: Each sub-query and its config MUST be JSON-serializable; the main agent MUST reject non-serializable values before dispatch.
- **FR-004**: Subagents MUST be dispatched lazily to a bounded `ThreadPoolExecutor` only after the sub-query list is finalized (no pre-warmed pool); concurrency MUST be capped by a configured `max_workers` (I/O-bound, so the cap MAY exceed CPU core count).
- **FR-005**: Each subagent MUST run as an independent ReAct loop on a pool thread under logical isolation - no shared mutable state, no globals or singletons - communicating only via input args (in) and its final return value (out).
- **FR-006**: Each subagent MUST expose only the `web_search` tool in its ReAct loop; it independently searches, reasons, and returns one consolidated finding.
- **FR-007**: The main agent MUST push only coarse-grained status events - `subtask_started`, `subtask_completed`, `subtask_failed` (with sub-query ID and, on failure, a brief error) - and MUST NOT push internal ReAct reasoning, search snippets, progress percentages, or intermediate variable values.
- **FR-008**: After all subagents terminate (normal, timeout, or exception), the main agent MUST count successes and failures; if ≥1 succeeded, it MUST aggregate only the successful findings into the final answer and prefix it with a partial-result disclosure naming the failed subagents.
- **FR-009**: If zero subagents succeed, the main agent MUST refuse aggregation and return a global-failure response with per-subagent failure detail, exposing no unhandled exception or stack trace to the user.
- **FR-010**: The main agent MUST enforce a global timeout (`TOTAL_TIMEOUT`, default 300s); on expiry it MUST cancel every still-running subagent and mark each failed.
- **FR-011**: The main agent MUST cancel any subagent whose ReAct loop exceeds a configured max-iterations (or sustained wall-clock) runaway guard.
- **FR-012**: On user cancel, the main agent MUST cooperatively cancel every in-flight subagent (cancel futures / cancel flag) and shut down the pool, leaving zero lingering tasks.
- **FR-013**: A single subagent's exception MUST NOT affect the main agent or sibling subagents; the main agent MUST catch it and mark that subagent failed.
- **FR-014**: The system MUST generate one globally unique Trace_ID per user request and record it across the routing decision, decomposition, dispatch, every subagent start/end/failure, and all error stacks in a timestamped rolling log file.
- **FR-015**: All subagent inputs and outputs MUST be JSON-serializable (the data contract for logging, aggregation, and traceability); file handles, DB cursors, model instances, and lambdas MUST NOT appear in the contract.
- **FR-016**: Subagent result payloads exceeding a configured size cap MUST be summarized or truncated before return (not returned verbatim) to keep aggregation bounded.
- **FR-017**: The main agent's direct `web_search` path (simple queries) MUST return a single consolidated answer without spawning subagents.

### Key Entities *(include if feature involves data)*

- **Research Sub-Query**: a single independent facet of the user's question; attributes `sub_query` (text) and `config` (JSON-serializable dict). Peer-level and zero-dependency by construction.
- **Subagent Task**: the unit of parallel work - a ReAct loop with the `web_search` tool; has a lifecycle state (started / running / completed / failed / timed-out) and a terminal finding (JSON) or captured exception.
- **Tool**: `web_search` (usable by both the main agent and subagents) and `dispatch_subagents` (main-agent only); tools are pure I/O search/reasoning primitives.
- **Trace Context**: carries the request's unique Trace_ID through the main agent's logs and every subagent's log lines for full-lifecycle reconstruction.
- **Aggregation Result**: the final user-facing output; comprises successful subagent findings, the failed-subagent list with reasons, and the disclosure prefix when partial.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A multi-faceted research query decomposes into ≥2 peer-level, zero-dependency sub-queries and returns one consolidated answer.
- **SC-002**: After any request finishes (success or failure), the count of lingering subagent tasks/threads is 0 (pool shut down).
- **SC-003**: With 2 of 5 subagents forced to fail/timeout, the system returns a valid aggregated answer from the 3 successes that explicitly discloses the 2 failures.
- **SC-004**: When all subagents fail, the user receives a clear failure message with no unhandled exception or stack trace.
- **SC-005**: A single Trace_ID lets an operator reconstruct the complete request lifecycle (routing -> decomposition -> dispatch -> each subagent start/end/failure -> aggregation) from the log file by filtering on that ID.
- **SC-006**: The coarse-grained status channel exposes only start/complete/failed events; no internal ReAct reasoning, search snippets, or variable values reach the user.
- **SC-007**: Wall-clock time for a multi-subagent query runs in parallel - bounded by the slowest single subagent plus orchestration overhead - rather than the sum of all subagents.
- **SC-008**: A single subagent's exception, timeout, or runaway loop never causes the main agent or sibling subagents to fail.

## Assumptions

- **Workload type**: I/O-bound web research (`web_search` is network-bound); threads are appropriate and the GIL is not a bottleneck. (Constitution v2.0.0 Art. 1/2.1.)
- **OS scope**: Linux / macOS. (Threads are cross-platform, but the project keeps this scope boundary.)
- **Dependencies**: an LLM is reachable via a standard API (DeepSeek / DashScope per project runtime) for routing, decomposition, and aggregation; a `web_search` capability (search API or retrieval tool) is available; `ThreadPoolExecutor` is stdlib.
- **Input data**: the user's natural-language query; sub-query config is inline JSON (no large file payloads).
- **Deployment**: single-machine; no HA/failover for the main agent - on crash, an operator restarts manually.
- **Defaults**: `TOTAL_TIMEOUT` = 300s; `max_workers` configurable (I/O-bound, may exceed CPU count); runaway guard = max-iterations; result size cap configurable. All tunable.
- **Data contract**: JSON-serializable inputs/outputs (Constitution v2.0.0 Art. 3.2); no cross-process IPC or pickle in the thread model.
