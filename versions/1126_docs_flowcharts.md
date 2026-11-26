# 1126_docs_flowcharts

**修改日期**：2026-11-26

**修改内容**：为 Baseline 与 Agent 两条闭环补齐**正式流程图**（承接 `1126_docs_reorg`），
把此前只存在于 ASCII 简图与讨论中的流程升级为可渲染的 mermaid 图。

**新增 6 张流程图**（mermaid 为仓库既有惯例，企划书 §3.2 已在用）：

| 位置 | 图 | 内容 |
|---|---|---|
| `docs/architecture/总体框架.md` §3.1 | Baseline 闭环流程图 | T0 → IDLE（轮询/合窗/冻结快照/规划/闸门/下发）→ SETTLING（静置 + 中止重开）→ VERIFYING（采样投票/惩罚集/有界纠正）→ 收敛回 IDLE，附三重停止条件 |
| `docs/architecture/总体框架.md` §3.2 | Agent 闭环流程图 | 感知 → 协同层（调度/A2A/仲裁）→ 运维智能体 → LLM 通道 → 资源控制智能体 → 共用闸门 → 共用确定性内核 → POST → 共用校验 |
| `docs/architecture/baseline与agents的共享与对比.md` §1.2 | **并排对比图** | 左右两条决策路径汇入同一闸门/内核/校验/指标，用配色标注「共用（橙）/baseline 独有（绿）/agent 独有（蓝）」 |
| `docs/common/control/闭环状态机与收敛判据.md` §1 | epoch 状态机图（`stateDiagram-v2`） | IDLE / PLANNING / SETTLING / VERIFYING 四态与全部迁移边，含「中止重开」「有界纠正」回边 |
| `docs/agents/智能体设计.md` §3.2 | 角色轮转图 | 运维感知 → 运维诊断 → 控制决策 → 控制下发 → 仲裁 → 回环 |
| `docs/agents/智能体设计.md` §6 | Agent 端到端流程图 | 启动/T0/基线窗口 → 主循环全链 → 三重停止条件 |

**校验**：7 个 mermaid 块（含企划书原有 1 个）经 **mermaid v11 真实解析器**
（`mermaid.parse()`）全部通过；并用 jsdom + 几何 polyfill 实际 `render()` 成功
（SVG 16–44KB，节点/连线数符合预期），提取 SVG 文本标签核对图内容与设计意图一致。

同步更新 `docs/index.md` 的索引条目，标注哪些篇章含流程图。
