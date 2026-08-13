<!--
Sync Impact Report (Amendment 2026-08-13-A)
===========================================
- Version change: 1.0.0 -> 2.0.0 (MAJOR)
- Trigger: /speckit-plan Constitution Check gate failed - plan-time architecture
  (ThreadPoolExecutor threads + web_search research) is structurally incompatible
  with v1.0.0 Art. 2.1 (OS process isolation). Project owner authorized
  Amendment 2026-08-13-A on 2026-08-13 (single-developer course project;
  owner's explicit choice stands in for the >=2/3 vote per Art. 6.2).
- Modified principles:
    * Preamble + Art. 1 Core Mission: "CPU-intensive parallel orchestration"
      -> "I/O-bound multi-faceted web-research orchestration"
    * Art. 2.1 Process Isolation -> Thread & Logical Isolation (REDEFINED - MAJOR)
    * Art. 3.1 Lazy Spawn (process cap CPU-1) -> Bounded Lazy Dispatch (thread pool)
    * Art. 3.2 Serialization Compact (cross-process pickle/JSON) ->
      Serializable Data Contract (JSON inputs/outputs; no cross-process IPC)
- Added sections: Amendment Proposal 2026-08-13-A (under Governance, Art. 6.2)
- Unchanged: Art. 2.2 Flat Dependency, 2.3 Graceful Degradation, 2.4 Minimal
  Streaming, 4.1 Trace ID, 5 Quality Gates, 6 Governance (procedure), 7 Ethics.
- Honest weakening (transparency): Art. 2.1 v2 thread isolation is a programming
  discipline, NOT OS-enforced. Accepted because subagents are stateless I/O-bound
  search loops; threads are technically apt (GIL does not block network I/O).
- Follow-up TODOs: spec.md revised in lockstep (FR-004/005/006/011/012/013/015/016).
-->

# Hydra Constitution

> **序言 (Preamble)**：Hydra 旨在解决单机环境下 **I/O 密集型多侧面调研任务** 的并行编排问题，信奉"简洁、隔离、坚韧"的工程哲学。本宪章确立系统的根本法则；任何设计决策、代码提交或架构演进，若与本宪章冲突，均视为无效。
>
> **核心使命 (Core Mission)**：以最低的编排开销，将一个多角度调研请求拆解为并行子调研，最大化调研吞吐、最小化端到端延迟。系统存在的唯一价值是用并行子 agent 回答多侧面问题，快于单 agent 串行搜索。任何引入额外串行瓶颈或过度同步等待的设计，必须重新评审。

## Core Principles

以下四项为不可妥协的绝对红线，任何情况下不得违背。

### I. Thread & Logical Isolation (线程与逻辑隔离定律)

每个 Subagent 作为独立的 ReAct 循环，运行在有界线程池（`ThreadPoolExecutor`）的一个线程上。

- Subagent 必须遵守**逻辑隔离**：不得通过共享可变状态、全局变量或单例对象互相通信；唯一的交互通道为：主控 -> 子 agent（子查询 + 配置参数）、子 agent -> 主控（最终调研结论 / 返回值）。
- **透明削弱声明**：与 v1.0.0 的 OS 进程隔离不同，线程隔离是**编程纪律**而非 OS 强制。此处可接受，因为子 agent 是无状态的 I/O 密集型搜索循环；线程对网络 I/O 不受 GIL 阻塞，技术选型恰当。任何引入有状态共享或长生命周期的子 agent 设计，须重新评审是否回归进程隔离。
- 依据：Amendment 2026-08-13-A（原 v1.0.0 依据用户确认项 #1(B)、#2(A)、#4）。

### II. Flat Dependency (平级无依赖定律)

主控 Agent 拆解出的所有子调研任务，必须在逻辑上完全平级（Flat）且零数据依赖（Zero Dependency）。

- 若 LLM 输出存在 DAG（有向无环图）依赖关系，系统必须拒绝执行并向用户明确提示。
- 绝不在本系统内引入拓扑排序或中间结果转发机制。
- 依据：用户确认项 #8(A)。

### III. Graceful Degradation (容错宽容定律)

系统必须实现部分成功（Partial Success）策略。

- 只要存在至少 1 个子 agent 成功返回，主控就必须聚合结果并返回有效响应。
- 不得因少数子 agent 失败而整体崩溃或抛出未处理异常。
- 依据：用户确认项 #3(B)。

### IV. Minimal Streaming (最小流式定律)

状态推送仅限粗粒度（开始 / 结束 / 失败），严禁渗入 Subagent 内部 ReAct 推理细节、搜索循环日志或中间变量。

- 子 agent 不得向主控发送逐步推理、进度百分比或中间检索片段，保持子 agent 的纯黑盒特性。
- 依据：用户确认项 #7(A)。

## Resource Governance

### Bounded Lazy Dispatch (有界懒派发准则)

- 不预热线程池；仅在主控完成拆解、子查询就绪后，按需向 `ThreadPoolExecutor` 提交任务。
- 并发度受配置的 `max_workers` 上限约束。因任务为 I/O 密集型，上限**可超过 CPU 核心数**，按"避免搜索接口限流与资源耗尽"而非"CPU 饱和"来设定。
- 依据：Amendment 2026-08-13-A（原 v1.0.0 懒加载准则依据用户确认项 #6(A)）。

### Serializable Data Contract (可序列化数据契约)

- 子 agent 的输入（子查询、配置）与输出（调研结论）必须为 **JSON 可序列化**类型，用于日志、结果聚合与链路追溯。
- 线程模型下无跨进程 IPC，不再要求 pickle；JSON 作为统一数据契约保留。
- 严禁在输入/输出契约中传递文件句柄、数据库连接、模型实例、Lambda 等不可序列化对象。

## Observability

### Trace ID Compulsion (链路追踪强制)

- 从用户请求进入系统的那一刻起，必须生成全局唯一的 `Trace_ID`。
- 该 ID 必须贯穿主控拆解、派发、子 agent 开始/结束/失败以及错误堆栈记录。
- 目的：任何运维人员或开发者都能通过 `grep Trace_ID` 还原一次完整请求的全生命周期。

## Quality Gates

任何代码合并至主分支前，必须通过以下门禁：

| 门禁项 | 阈值 / 标准 |
| --- | --- |
| 单元测试覆盖率 | 核心调度逻辑（Orchestrator & Scheduler）行覆盖率 ≥ 80%。 |
| 线程泄漏检测 | 集成测试模拟 10 个子任务并发，测试结束后活动线程数为 0（线程池已关闭、无残留）。 |
| 异常隔离测试 | 在子 agent 中模拟 `raise Exception`，主控必须捕获且不影响其他并发子 agent。 |
| 超时终结测试 | 模拟子 agent 死循环，验证主控能够在 `TOTAL_TIMEOUT` 到达后取消任务（协作式取消 + 线程池 shutdown）。 |

## Ethics & Delivery Commitment

- 系统绝不隐瞒子任务的失败事实，必须在最终回复中向用户明确披露失败数量及简要原因。
- 系统不得在用户未明确授权的情况下，利用 Subagent 进程/线程执行挖矿、网络攻击等非法计算。

## Governance

本宪章为 Hydra 项目的最高行为准则，凌驾于所有其他实践之上。

### Emergency Authority (紧急裁决权)

若遇到需求规格书（SRS）及本宪章均未覆盖的边缘场景，架构负责人拥有最终现场决策权，但事后须在 24 小时内补充修订本宪章并知会全员。

### Amendment Procedure (修订机制)

任何对本宪章的修改，必须：

1. 提出书面《修订提案》，详述原因及影响面；
2. 获得 ≥ 2/3 的核心开发成员投票通过（单开发者课程项目以负责人决策代行）；
3. 同步更新配套的需求规格书（spec）和架构设计文档；
4. 修订生效后，所有历史代码须在下一个迭代周期完成适配。

### Amendment Proposal 2026-08-13-A

- **原因**：`/speckit-plan` 阶段确认实际系统为 I/O 密集型 web 调研 agent（主控 ReAct + `web_search`/`dispatch_subagents`，子 agent ReAct + `web_search`，`ThreadPoolExecutor` 并行）。v1.0.0 的进程隔离（Art. 2.1）与线程模型结构性冲突，且 CPU 密集型使命（Art. 1）与 web 调研不符。
- **影响面**：Art. 1、2.1、3.1、3.2 重定义（MAJOR，1.0.0 -> 2.0.0）；spec.md 同步修订 FR-004/005/006/011/012/013/015/016 与标题/使命。
- **授权**：项目负责人 2026-08-13 明确选择"Amend to threads"。
- **权衡**：以"逻辑隔离（编程纪律）"替代"OS 进程隔离（强制）"，换取 I/O 密集型场景下更低的编排开销；若未来引入 CPU 密集型或 有状态子任务，须重新评估回归进程隔离。

### Versioning Policy

版本号遵循语义化版本（MAJOR.MINOR.PATCH）：删除或重定义既有原则为 MAJOR；新增原则或实质性扩展为 MINOR；措辞、笔误、非语义性精炼为 PATCH。

### Compliance Review

所有 PR / Code Review 必须核验本宪章合规性；复杂度必须被证明合理。

### Signatories

| 角色 | 签名 | 日期 |
| --- | --- | --- |
| 需求方代表（Product Owner） | （待签署） | 2026-08-13 |
| 技术负责人（Tech Lead） | （待签署） | 2026-08-13 |
| 架构师（Architect） | AI Agent 代为签署 | 2026-08-13 |

**Version**: 2.0.0 | **Ratified**: 2026-08-13 | **Last Amended**: 2026-08-13
