"""通信网络资源控制智能体（Resource Agent）：资源调度、路由动态调整、带宽分配、业务 QoS 保障。

赛题职责（原文）：基于运维感知结果和无人平台业务协同需求，进行资源调度、路由动态
调整、带宽分配、业务 QoS 保障。

**与运维智能体的分工**：运维给「哪里坏了、为什么坏、建议怎么修」；本智能体给
「怎么调度、谁优先、路径怎么走」。

**关键约束（三条硬线）**：

1. **LLM 不生成链路**。LLM 只给**优先级建议**（哪条业务更该被保障）与态势解读；
   路径永远由 `common/algorithms/flow/` 的确定性内核在候选集中选。
2. **写动作必须过闸门**。本智能体产出的调整方案，最终仍由 `common/control/` 的
   下发闸门判定（修复失效路径 or Δscore ≥ Δmin），不在本层直接 POST。
3. **冲突让位于仲裁**。若与其他智能体的提议互斥，交 `agents/a2a/arbitration.py`
   裁决，不由本层单方拍板。

本模块目前提供**职责契约与数据结构**；具体决策实现（如何融合 LLM 建议与确定性
结果）随实验推进补齐，接口保持稳定。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from common.modeling.flow import FlowKey


@dataclass
class PriorityHint:
    """一条优先级调整建议（来自 LLM 或规则）。"""

    service_id: str
    suggested_priority: int
    reason: str = ""
    source: str = "llm"        # llm / rule

    def to_dict(self) -> dict[str, Any]:
        return {
            "service_id": self.service_id,
            "suggested_priority": self.suggested_priority,
            "reason": self.reason,
            "source": self.source,
        }


@dataclass
class ResourceDecision:
    """资源控制智能体的决策产物。"""

    priority_hints: list[PriorityHint] = field(default_factory=list)
    target_flows: list[FlowKey] = field(default_factory=list)   # 打算介入的 flow
    summary: str = ""                                            # 面向人的解读
    explanation: str = ""                                        # 决策依据（可复盘）

    def to_dict(self) -> dict[str, Any]:
        return {
            "priority_hints": [h.to_dict() for h in self.priority_hints],
            "target_flows": [list(k) for k in self.target_flows],
            "summary": self.summary,
            "explanation": self.explanation,
        }


@dataclass
class DispatchPlan:
    """待下发的路径调整方案（尚未过闸门、未 POST）。"""

    flow_key: FlowKey
    service_id: str
    path: list[str]
    reason: str = ""
    source: str = "deterministic"    # deterministic / llm_hint

    def to_dict(self) -> dict[str, Any]:
        return {
            "flow_key": list(self.flow_key),
            "service_id": self.service_id,
            "path": list(self.path),
            "reason": self.reason,
            "source": self.source,
        }
