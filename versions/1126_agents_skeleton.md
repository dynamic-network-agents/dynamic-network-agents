# 1126_agents_skeleton

**修改日期**：2026-11-26

**修改内容**：为未来 agent 方案补齐三层落点（承接 `1126_src_reorg`），让赛题
「多智能体协同体系设计」的要求在代码里有明确归属：

1. **`src/common/observability/`（新增）**：观测留痕与指标产出。
   `timeline.py`（`DecisionTimeline` / `EventKind`，感知/决策/下发三段时间戳）+
   `metrics.py`（`collect_metrics` / `RunMetrics`）。赛题四项指标里三项（状态感知
   时间、策略生成时间、策略下发时间）靠它产出；baseline 与 agent 共用同一套计时
   口径，对比实验才可比。本层只记录、不参与决策。
2. **`src/agents/` 三块**：赛题「多智能体协同体系设计」的四项要求各有落点——
   `ops/`（运维智能体：态势采集/拓扑感知/链路质量评估/异常检测/故障诊断/自愈建议，
   **无写权限**）、`resource/`（资源控制智能体：资源调度/路由动态调整/带宽分配/QoS
   保障）、`a2a/`（A2A 协议 `message.py` + 任务调度 `scheduler.py` + 冲突仲裁
   `arbitration.py`）、`llm/`（LLM 通道 `client.py` + `prompts.py`）。
   仲裁规则确定性（执行类 > 建议类 → 业务优先级降序 → 业务 ID 字典序兜底），
   保证同输入同输出、实验可复现。
3. **LLM 通道放 `agents/llm/` 而非 `common/llm/`**：baseline 是确定性闭环、全程不走
   LLM，放共享层会引入一条它不走的依赖。硬约束写进 `src/CLAUDE.md`：**LLM 只做
   解释/优先级增强/故障诊断建议，不生成链路**；所有写动作仍过 `common/control/`
   的下发闸门。

本轮提供**职责契约、数据结构与协同机制**，端到端编排（`agents/main.py` +
`orchestrator.py`）留待实验推进时按此接口补齐，接口保持稳定。
新增 36 个单测（`common/observability/tests/`、`agents/a2a/tests/`、
`agents/llm/tests/`），`uv run pytest src/ tests/` 134 passed / 7 skipped。
