"""智能体模块：运维智能体 + 资源控制智能体 + A2A 协同层 + LLM 通道。

对应赛题「多智能体协同体系设计」的四项要求：

| 赛题要求 | 本包落点 |
|---|---|
| 至少两类智能体 | `ops/`（运维智能体）、`resource/`（资源控制智能体） |
| A2A 通信协议 | `a2a/message.py`（消息类型 + 进程内总线） |
| 动态自决策 / 任务调度 | `a2a/scheduler.py`（角色轮转 + 预算闸门） |
| 冲突仲裁策略 | `a2a/arbitration.py`（确定性仲裁规则） |

**与 baseline 的关系**：两侧共用 `common/` 全部底座——感知层
（`common/perception/`）看到同一份快照，闭环控制（`common/control/`）用同一套
epoch 状态机 / 下发闸门 / 实测校验，算法（`common/algorithms/`）是同一个确定性内核。
**唯一的差异是决策核心**：baseline 直接用规划器输出，agent 侧由两个智能体分工
（运维给态势与诊断 → 资源控制给调度决策），并可用 LLM 增强优先级与解读。

**LLM 通道在 `agents/llm/`**（不放 `common/`）：baseline 是确定性闭环，全程不需要
LLM；放进共享层会给 baseline 引入一条它不走的依赖。LLM 只做解释、优先级增强与
故障诊断建议，**不生成链路**——路径永远由 `common/algorithms/` 产出。

**当前状态**：本包提供职责契约、数据结构与协同机制（A2A 协议/调度/仲裁），
端到端编排（`main.py` + `orchestrator.py`）随实验推进补齐，接口保持稳定。
"""
