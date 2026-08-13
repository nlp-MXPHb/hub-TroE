# Hydra — 并行多 Subagent 调研 Agent

![Python](https://img.shields.io/badge/Python-%E2%89%A53.12-blue)
![Status](https://img.shields.io/badge/spec-30%2F30%20tasks%20done-brightgreen)
![Search Backend](https://img.shields.io/badge/web__search%20backend-stub%20(plug%20your%20own)-orange)

单机、I/O 密集型的并行网络调研编排系统：主控 ReAct agent 自动路由——简单问题直接调 `web_search`，多侧面问题调 `dispatch_subagents`，将查询分解为相互独立的子任务，在有界的 `ThreadPoolExecutor` 上并行运行多个 ReAct 子 agent，最后聚合成一份答案，并对部分失败容错。

遵循 Spec Kit 流程开发，完整规格见 [`specs/001-parallel-subagent-orchestration/`](specs/001-parallel-subagent-orchestration/)（宪章 v2.0.0 · spec · plan · tasks 30/30 已完成）。

## 目录

- [特性](#特性)
- [快速开始](#快速开始)
- [使用示例](#使用示例)
- [配置](#配置)
- [架构](#架构)
- [项目结构](#项目结构)
- [测试](#测试)
- [规格文档](#规格文档)
- [已知限制与 Roadmap](#已知限制与-roadmap)

## 特性

- **LLM 自主路由**（FR-001/017）：主 agent 的 ReAct 循环自行判断简单 / 多侧面查询，不是固定拓扑
- **并行执行**（FR-004）：子任务懒加载派发到有界 `ThreadPoolExecutor`，`max_workers` 可配（I/O 密集，可超过 CPU 核数）
- **线程级逻辑隔离**（FR-005，宪章 v2.0.0 Art. 2.1）：每个子 agent 是纯 `(sub_query, config) -> finding` 函数，无共享可变状态
- **扁平依赖**（FR-002）：拒绝任何带依赖关系的分解，提示用户改写为独立子问题
- **优雅降级**（FR-008/009）：≥1 个子 agent 成功即返回聚合答案并**披露失败项**；全部失败则返回全局失败信息，不向用户暴露堆栈
- **粗粒度状态事件**（FR-007）：只推送 `subtask_started / subtask_completed / subtask_failed`，不泄露内部 ReAct 推理、搜索片段或中间变量
- **全链路 Trace ID**（FR-014）：每个请求一个全局唯一 Trace_ID，可凭它在滚动日志 `logs/hydra.log` 中重建完整生命周期
- **故障隔离与清理**（FR-010~013）：全局超时（默认 300s）、ReAct 失控护栏（最大迭代数）、用户取消协同清理，结束后线程池零残留

## 快速开始

### 环境要求

- Python ≥ 3.12
- OpenAI 兼容的 LLM API（DeepSeek / DashScope）

### 安装

```bash
conda activate py312            # 项目运行环境
pip install -e ".[dev]"         # 核心依赖 openai；dev 附带 pytest
```

### 运行

```bash
export DEEPSEEK_API_KEY=sk-...  # 或 DASHSCOPE_API_KEY

python src/cli.py "对比 React、Vue 和 Svelte 在 2026 年看板项目中的适用性"
```

## 使用示例

```bash
# 默认 4 个并行 worker
python src/cli.py "比较三个前端框架的生态、性能与学习曲线"

# 自定义并行度
python src/cli.py "比较三个前端框架的生态、性能与学习曲线" --max-workers 8
```

典型输出行为：

| 输入类型 | 路由 | 输出 |
|---|---|---|
| 简单单侧面问题 | 直接 `web_search` | 单条整合答案，不派生子 agent |
| 多侧面问题 | `dispatch_subagents` | 并行调研后聚合；若有子任务失败，答案以部分结果披露开头 |
| 分解出依赖关系 | 拒绝执行（FR-002） | 提示"仅支持完全独立的并行任务，请拆分后重试" |
| 全部子任务失败 | — | 全局失败信息 + 逐项失败原因，无堆栈 |

> ⚠️ **注意**：默认 `web_search` 后端是桩实现（恒返回空结果）。接入真实搜索 API：替换 [`src/tools/web_search.py`](src/tools/web_search.py) 中的 `default_backend` 即可，工具契约保证后端异常被捕获为 `{results: [], error}` 而非抛出。

## 配置

全部阈值集中在 [`src/config.py`](src/config.py)，默认值对齐 spec 假设：

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `total_timeout` | `300.0` s | 全局超时（FR-010），到期取消所有在跑子任务 |
| `max_workers` | `4` | 线程池并发上限（FR-004）；CLI 可用 `--max-workers` 覆盖 |
| `max_iterations` | `5` | ReAct 循环最大迭代数，失控护栏（FR-011） |
| `size_cap` | `8192` 字符 | 子 agent 结果载荷上限，超限摘要/截断（FR-016） |
| `llm_model` / `llm_base_url` | `deepseek-chat` / `https://api.deepseek.com` | LLM 接入（OpenAI 兼容协议） |
| `log_file` | `logs/hydra.log` | 滚动日志，按 Trace_ID 可过滤 |

环境变量：`DEEPSEEK_API_KEY`（优先）或 `DASHSCOPE_API_KEY`（备用）。

## 架构

```
MainAgent (ReAct) ──web_search──> 直接回答（简单查询）
                └─dispatch_subagents─> Scheduler (ThreadPoolExecutor)
                                        ├─ Subagent (ReAct + web_search) ─┐
                                        ├─ Subagent (ReAct + web_search) ├─ Aggregator（部分成功容错）
                                        └─ ...                           ┘
```

四条不可协商原则（宪章 v2.0.0）：**线程与逻辑隔离 · 扁平依赖 · 优雅降级 · 最小化流式输出**。

关键设计：LLM 只用于判断性任务（路由、推理、聚合），依赖检测等确定性转换由代码完成；工具遵循不抛异常的契约；所有子 agent 输入输出均 JSON 可序列化（数据契约）。

## 项目结构

```
sub-agent/
├── src/
│   ├── cli.py                    # CLI 入口
│   ├── config.py                 # 集中配置（全部阈值可调）
│   ├── main_agent.py             # 主控 ReAct 循环 + LLM 自主路由
│   ├── llm_client.py             # OpenAI 兼容客户端（懒加载）
│   ├── subagent.py               # 子 agent ReAct 循环
│   ├── scheduler.py              # ThreadPoolExecutor 懒派发 + 状态事件
│   ├── aggregator.py             # 部分成功容错的聚合
│   ├── models.py                 # 数据模型 + 扁平依赖校验
│   ├── observability.py          # Trace_ID + 滚动日志
│   └── tools/
│       ├── web_search.py         # 搜索工具（主/子 agent 共用，后端可插拔）
│       └── dispatch_subagents.py # 并行派发工具（仅主 agent）
├── tests/                        # unit / contract / integration（注入 FakeLLM，无需 API key）
└── specs/001-parallel-subagent-orchestration/
    ├── spec.md                   # 17 条功能需求 · 8 条成功标准 · 4 个用户故事
    ├── plan.md · tasks.md        # 实施计划 · 任务清单（30/30 完成）
    ├── research.md · data-model.md
    └── contracts/tools.md        # 工具契约
```

## 测试

```bash
conda run -n py312 python -m pytest tests/ -v
```

测试全部注入 `FakeLLM` 与假搜索后端，**不需要 API key**。覆盖：分解与路由、部分失败聚合、故障隔离、超时/取消清理、状态事件不泄露内部信息、Trace_ID 全链路等。

## 规格文档

本项目按 Spec Kit 流程驱动：宪章 → 规格 → 计划 → 任务 → 实现。核心规格文件：

- **宪章** `.specify/memory/constitution.md`（v2.0.0）
- **规格** `specs/001-parallel-subagent-orchestration/spec.md`（4 个用户故事 · 17 FR · 8 SC）
- **任务清单** `specs/001-parallel-subagent-orchestration/tasks.md`（30/30 已完成）

## 已知限制与 Roadmap

- [ ] **真实搜索后端**：`web_search` 默认桩实现，接入真实搜索 API（SerpAPI / Bing / 自建检索）
- [ ] 主 agent 崩溃无自动恢复（HA/故障转移明确不在本期范围），由运维手动重启
- [ ] 单机部署；如需跨机扩展需引入进程/队列模型（当前宪章限定线程隔离）

## License

学习项目，暂未附 License。
