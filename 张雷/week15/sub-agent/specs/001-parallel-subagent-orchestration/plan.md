# Implementation Plan: Parallel Multi-Subagent Research Agent

**Branch**: `001-parallel-subagent-orchestration` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)

**Input**: spec.md (revised per Constitution Amendment 2026-08-13-A) + user plan-time input (ReAct main agent routing `web_search`/`dispatch_subagents`; subagents ReAct + `web_search`; `ThreadPoolExecutor` parallelism).

## Summary

A single-machine, I/O-bound web-research agent. The main agent is a ReAct loop that auto-routes simple queries to `web_search` and multi-faceted queries to `dispatch_subagents`, which decomposes the query into peer-level, zero-dependency sub-queries and runs each as an independent ReAct subagent (tool: `web_search`) in parallel on a bounded `ThreadPoolExecutor`. Features partial-failure-tolerant aggregation, coarse-grained status, and a global Trace_ID. Aligned with Constitution v2.0.0 (Thread & Logical Isolation).

## Technical Context

**Language/Version**: Python 3.12 (conda env `py312`)

**Primary Dependencies**: LLM SDK (DeepSeek / DashScope), `web_search` capability (search API / retrieval tool), `ThreadPoolExecutor` (stdlib)

**Storage**: Local rolling log files (Trace_ID)

**Testing**: pytest

**Target Platform**: Linux / macOS

**Project Type**: Agent framework (library + CLI)

**Performance Goals**: Multi-subagent query wall-clock bounded by the slowest subagent + orchestration overhead (parallel, not serial-sum)

**Constraints**: `TOTAL_TIMEOUT`=300s; bounded `max_workers`; `max_iterations` runaway guard; JSON data contract; cooperative thread cancellation (Python threads cannot be force-killed)

**Scale/Scope**: Single-machine; a handful of subagents per query

## Constitution Check

*Constitution v2.0.0. GATE: PASS (re-evaluated post-amendment).*

| Article | Verdict |
| --- | --- |
| 1. Core Mission (I/O-bound research) | ✅ matches `web_search` research |
| 2.1 Thread & Logical Isolation | ✅ `ThreadPoolExecutor` + independent ReAct loops, no shared mutable state |
| 2.2 Flat Dependency | ✅ peer-level zero-dependency sub-queries (FR-002) |
| 2.3 Graceful Degradation | ✅ partial-success aggregation (FR-008/009) |
| 2.4 Minimal Streaming | ✅ coarse events only (FR-007) |
| 3.1 Bounded Lazy Dispatch | ✅ on-demand `ThreadPoolExecutor`, `max_workers` cap (FR-004) |
| 3.2 Serializable Data Contract | ✅ JSON inputs/outputs (FR-015) |
| 4.1 Trace ID | ✅ global Trace_ID (FR-014) |

## Project Structure

### Documentation (this feature)

```text
specs/001-parallel-subagent-orchestration/
├── plan.md              # this file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── contracts/
│   └── tools.md         # Phase 1
├── quickstart.md        # Phase 1
└── tasks.md             # Phase 2 (/speckit-tasks - not yet created)
```

### Source Code (repository root)

```text
src/
├── main_agent.py        # ReAct loop + LLM routing (web_search / dispatch_subagents)
├── subagent.py          # ReAct loop (web_search only)
├── tools/
│   ├── web_search.py
│   └── dispatch_subagents.py
├── scheduler.py         # bounded ThreadPoolExecutor, timeout, runaway guard, cancel
├── aggregator.py        # partial-success aggregation + disclosure
├── observability.py     # Trace_ID + rolling log
└── config.py            # TOTAL_TIMEOUT, max_workers, max_iterations, size_cap
tests/
├── unit/
├── integration/
└── contract/
```

**Structure Decision**: Single-project layout (template Option 1). ReAct loops live in `main_agent.py` / `subagent.py`; all parallelism/cancellation is isolated in `scheduler.py`; tools are pluggable under `tools/`; observability and config are cross-cutting modules.

## Complexity Tracking

No violations. The v1.0.0 Art. 2.1 conflict was resolved by **redefining** the principle via Amendment 2026-08-13-A (Constitution v2.0.0), not by waiving complexity.
