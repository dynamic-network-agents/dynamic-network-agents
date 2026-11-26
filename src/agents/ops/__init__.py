"""通信网络运维智能体（Ops Agent）：态势采集、拓扑感知、链路质量评估、异常检测、故障诊断、自愈建议。

赛题职责（原文）：负责全网态势采集、拓扑感知、链路质量评估、异常事件检测、故障诊断、
自愈建议生成。

**与资源控制智能体的分工**：

| | 运维智能体 | 资源控制智能体 |
|---|---|---|
| 输入 | 事件 + 快照 | 运维的态势/诊断结论 + 业务需求 |
| 输出 | 异常清单、诊断、自愈建议 | 优先级建议、路径调整决策 |
| 写动作 | **无**（只读 + 建议） | 有（路径下发） |

**关键约束**：运维智能体**没有写权限**——它只产出建议（A2A 消息），实际下发由资源
控制智能体执行，且仍要过 `common/control/` 的下发闸门。这既是职责边界，也是安全边界。

本模块目前提供**职责契约与数据结构**；具体推理实现（如何检测异常、如何归因）随
实验推进补齐，接口保持稳定。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AnomalyType(str, Enum):
    """异常类型。"""

    LINK_DOWN = "link_down"               # 链路断开
    LINK_DEGRADED = "link_degraded"       # 链路质量劣化（参数变化）
    NODE_DOWN = "node_down"               # 节点下线
    SERVICE_VIOLATION = "service_violation"  # 业务 QoS 违约


@dataclass
class Anomaly:
    """一条异常记录。"""

    target: str                     # 作用对象（link_id / node_id / service_id）
    anomaly_type: AnomalyType
    evidence: str = ""              # 判定依据（实测数据 / 事件）
    severity: str = "medium"        # high / medium / low

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "type": self.anomaly_type.value,
            "evidence": self.evidence,
            "severity": self.severity,
        }


@dataclass
class Diagnosis:
    """故障诊断结论。"""

    cause: str = ""
    confidence: float = 0.0
    affected_flows: list[tuple[str, str]] = field(default_factory=list)
    advice: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cause": self.cause,
            "confidence": self.confidence,
            "affected_flows": [list(k) for k in self.affected_flows],
            "advice": self.advice,
        }


@dataclass
class SituationReport:
    """全网态势报告（运维智能体 → 资源控制智能体的主要产物）。"""

    anomalies: list[Anomaly] = field(default_factory=list)
    diagnosis: Diagnosis = field(default_factory=Diagnosis)
    degraded_links: list[str] = field(default_factory=list)   # 质量劣化但未断的链路
    summary: str = ""                                          # 面向人的一句话解读

    def to_dict(self) -> dict[str, Any]:
        return {
            "anomalies": [a.to_dict() for a in self.anomalies],
            "diagnosis": self.diagnosis.to_dict(),
            "degraded_links": list(self.degraded_links),
            "summary": self.summary,
        }

    def affected_flow_keys(self) -> set[tuple[str, str]]:
        """受影响 flow 集合（供控制智能体圈定处理范围）。"""
        return set(self.diagnosis.affected_flows)
