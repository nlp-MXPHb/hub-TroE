---

description: "Task list for Parallel Multi-Subagent Research Agent"
---

# Tasks: Parallel Multi-Subagent Research Agent

**Input**: Design documents from `/specs/001-parallel-subagent-orchestration/` (plan.md, spec.md, research.md, data-model.md, contracts/tools.md, quickstart.md)

**Prerequisites**: plan.md (required), spec.md (required), constitution v2.0.0 (governs)

**Tests**: INCLUDED - the Constitution v2.0.0 Quality Gates explicitly mandate unit coverage ≥80% (Orchestrator & Scheduler), thread-leak detection, exception-isolation, and timeout tests. TDD: write tests first, ensure they FAIL, then implement.

**Organization**: Tasks grouped by user story (spec.md US1-US4) so each story is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1-US4)
- Exact file paths in descriptions; paths are project-relative (`src/`, `tests/`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create project structure per plan: `src/`, `src/tools/`, `tests/unit/`, `tests/integration/`, `tests/contract/`, and `pyproject.toml` at repo root
- [x] T002 [P] Create configuration module with defaults (`TOTAL_TIMEOUT=300`, `max_workers`, `max_iterations`, `size_cap`) in `src/config.py`

**Checkpoint**: Project skeleton ready

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 [P] Implement observability primitives (global `Trace_ID` generation + timestamped rolling log) in `src/observability.py`
- [x] T004 [P] Implement `web_search` tool per contract (input `{query, **opts}` -> output `{results, error}`; never raises) in `src/tools/web_search.py`
- [x] T005 [P] Define shared data-model entities (`ResearchSubQuery`, `SubagentTask` + state enum, `Tool`, `TraceContext`, `AggregationResult`) in `src/models.py` (per data-model.md)
- [x] T006 [P] Implement LLM client wrapper (DeepSeek / DashScope) for ReAct reasoning in `src/llm_client.py`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - LLM-Routed Parallel Research with Partial-Failure Tolerance (Priority: P1) 🎯 MVP

**Goal**: Main ReAct agent routes simple queries to `web_search` and multi-faceted queries to `dispatch_subagents`; subagents (ReAct + `web_search`) run in parallel on a bounded `ThreadPoolExecutor`; successful findings are aggregated with partial-failure disclosure.

**Independent Test**: Submit a multi-faceted query (≥2 angles) with one subagent forced to fail -> verify a consolidated answer from survivors + failure disclosure. Submit a simple query -> verify direct `web_search`, no subagents.

### Tests for User Story 1 (write first, must FAIL)

- [x] T007 [P] [US1] Contract test for `web_search` and `dispatch_subagents` tool contracts in `tests/contract/test_tools.py`
- [x] T008 [P] [US1] Integration test: multi-faceted query -> ≥2 parallel subagents -> consolidated answer (SC-001) in `tests/integration/test_parallel_research.py`
- [x] T009 [P] [US1] Integration test: 2/5 subagents fail -> partial disclosure (SC-003); all fail -> global failure, no stack trace (SC-004) in `tests/integration/test_partial_aggregation.py`
- [x] T015 [P] [US1] Unit test: dependency detection rejects DAG sub-queries (FR-002) in `tests/unit/test_decomposition.py`

### Implementation for User Story 1

- [x] T010 [P] [US1] Implement subagent ReAct loop (tool: `web_search` only; check cancel flag each iteration; `max_iterations` cap) in `src/subagent.py`
- [x] T011 [P] [US1] Implement bounded `ThreadPoolExecutor` dispatch + `Future` collection in `src/scheduler.py`
- [x] T012 [P] [US1] Implement partial-success aggregation + disclosure prefix (FR-008/009) in `src/aggregator.py`
- [x] T013 [US1] Implement `dispatch_subagents` tool (dependency validation + dispatch + collect; no status events yet) in `src/tools/dispatch_subagents.py` (depends T010, T011, T012)
- [x] T014 [US1] Implement main agent ReAct loop + LLM auto-routing (`web_search` vs `dispatch_subagents`, FR-001/017) and dependency rejection (FR-002) in `src/main_agent.py` (depends T013)

**Checkpoint**: User Story 1 fully functional and independently testable (MVP)

---

## Phase 4: User Story 2 - Coarse-Grained Real-Time Status Feedback (Priority: P2)

**Goal**: Emit only coarse status events (`subtask_started`/`subtask_completed`/`subtask_failed` with sub-query ID + brief error); never leak ReAct reasoning or search snippets.

**Independent Test**: Drive dispatch with mock subagents emitting no internal logs; verify only the three coarse event types reach the client.

### Tests for User Story 2 (write first, must FAIL)

- [x] T016 [P] [US2] Integration test: only coarse events emitted, no ReAct reasoning/snippets leak (SC-006, FR-007) in `tests/integration/test_status_events.py`

### Implementation for User Story 2

- [x] T017 [US2] Add coarse status-event emission to `dispatch_subagents` (subtask_started/completed/failed) in `src/tools/dispatch_subagents.py` (extends T013)

**Checkpoint**: User Stories 1 AND 2 both work independently

---

## Phase 5: User Story 3 - Full-Lifecycle Observability via Trace ID (Priority: P3)

**Goal**: One global Trace_ID per request propagates through routing, decomposition, dispatch, each subagent start/end/failure, and aggregation, so an operator can reconstruct the full lifecycle from the log.

**Independent Test**: Submit one request, filter the log by its Trace_ID, confirm every lifecycle stage appears with timestamps.

### Tests for User Story 3 (write first, must FAIL)

- [x] T018 [P] [US3] Integration test: filter log by Trace_ID reconstructs full lifecycle (SC-005, FR-014) in `tests/integration/test_trace_id.py`

### Implementation for User Story 3

- [x] T019 [US3] Wire Trace_ID propagation through `main_agent` -> `scheduler` -> `subagent` log lines (FR-014) across `src/main_agent.py`, `src/scheduler.py`, `src/subagent.py` (observability primitives from T003)

**Checkpoint**: All user stories independently functional

---

## Phase 6: User Story 4 - Fault Isolation, Timeout & Cancellation Cleanup (Priority: P4)

**Goal**: A single subagent exception/timeout/runaway loop never affects the main agent or siblings; global timeout and user cancel tear down in-flight subagents cooperatively with zero lingering tasks.

**Independent Test**: Inject a raising subagent, a dead-loop subagent, and a user cancel in separate runs; verify siblings continue, guards fire, and the pool shuts down with zero lingering tasks.

### Tests for User Story 4 (write first, must FAIL)

- [x] T020 [P] [US4] Integration test: one subagent raises -> siblings continue (FR-013, SC-008) in `tests/integration/test_fault_isolation.py`
- [x] T021 [P] [US4] Integration test: `TOTAL_TIMEOUT` cancels outstanding subagents (FR-010) in `tests/integration/test_timeout.py`
- [x] T022 [P] [US4] Integration test: user cancel tears down in-flight subagents, zero lingering tasks (FR-012, SC-002) in `tests/integration/test_cancel.py`

### Implementation for User Story 4

- [x] T023 [US4] Implement global timeout (`TOTAL_TIMEOUT`) cancel of outstanding subagents in `src/scheduler.py` (FR-010)
- [x] T024 [US4] Implement runaway-guard cancel (`max_iterations` exceeded) in `src/subagent.py` and `src/scheduler.py` (FR-011)
- [x] T025 [US4] Implement cooperative cancel (cancel flag + `Future.cancel` + `shutdown(wait=False, cancel_futures=True)`) in `src/scheduler.py` (FR-012/013)

**Checkpoint**: Resilience complete; all constitution Quality Gates addressable

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements spanning multiple user stories

- [x] T026 [P] Implement result size-cap truncation before return (FR-016) in `src/aggregator.py`
- [x] T027 [P] Implement JSON-serializability validation at the data-contract boundary (FR-003/015) in `src/models.py`
- [x] T028 Constitution Quality Gates: unit coverage ≥80% for `scheduler`/`aggregator`; thread-leak test (10 concurrent -> 0 residual); exception-isolation + timeout tests in `tests/integration/test_quality_gates.py`
- [x] T029 [P] Add CLI entry point + usage docs in `src/cli.py` and `README.md`
- [x] T030 Run `quickstart.md` validation scenarios end-to-end (7 scenarios) and confirm pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately. T001 before T002.
- **Foundational (Phase 2)**: Depends on Setup; BLOCKS all user stories. T003-T006 parallel.
- **User Stories (Phase 3-6)**: All depend on Foundational. Each story's tests before its implementation.
- **Polish (Phase 7)**: Depends on all user stories complete.

### User Story Dependencies

- **US1 (P1)**: Starts after Foundational. No dependencies on other stories. (MVP)
- **US2 (P2)**: Starts after Foundational; extends `dispatch_subagents` from US1 (T013 -> T017). Independently testable.
- **US3 (P3)**: Starts after Foundational; wires Trace_ID into US1 modules. Independently testable.
- **US4 (P4)**: Starts after Foundational; extends `scheduler`/`subagent` from US1. Independently testable.

### Within Each User Story

- Tests written FIRST and FAIL before implementation
- Tools/models before services; services before orchestration
- Core implementation before integration
- Story complete and tested before next priority

### Parallel Opportunities

- Foundational T003-T006: all parallel (different files)
- US1 tests T007/T008/T009/T015: parallel; US1 impl T010/T011/T012: parallel (then T013 -> T014 sequential)
- US4 tests T020/T021/T022: parallel
- Polish T026/T027/T029: parallel (different files)
- Different user stories can be worked in parallel by different developers once Foundational is done

---

## Parallel Example: User Story 1

```bash
# Launch US1 tests together (write first, must fail):
Task: "Contract test in tests/contract/test_tools.py"
Task: "Integration test in tests/integration/test_parallel_research.py"
Task: "Integration test in tests/integration/test_partial_aggregation.py"
Task: "Unit test in tests/unit/test_decomposition.py"

# Then launch US1 independent modules together:
Task: "Implement src/subagent.py"
Task: "Implement src/scheduler.py"
Task: "Implement src/aggregator.py"
# Then sequential: src/tools/dispatch_subagents.py -> src/main_agent.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test US1 independently (parallel research + partial aggregation + simple-query routing)
5. Demo if ready

### Incremental Delivery

1. Setup + Foundational -> foundation ready
2. + US1 -> test -> demo (MVP)
3. + US2 (status events) -> test -> demo
4. + US3 (Trace_ID) -> test -> demo
5. + US4 (fault/timeout/cancel) -> test -> demo
6. Polish (size cap, JSON validation, quality gates, CLI) -> final

### Parallel Team Strategy

With multiple developers after Foundational:
- Developer A: US1 (MVP critical path)
- Developer B: US2 / US3 (can start once US1 modules exist they extend)
- Developer C: US4

---

## Notes

- Constitution v2.0.0 governs: Thread & Logical Isolation (no shared mutable state), Flat Dependency, Graceful Degradation, Minimal Streaming, Bounded Lazy Dispatch, JSON data contract, Trace_ID.
- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to its user story for traceability
- Tests are mandatory here (Constitution Quality Gates), written first and failing before impl
- Commit after each task or logical group; stop at any checkpoint to validate independently
