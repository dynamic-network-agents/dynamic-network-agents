"""A2A 消息协议：智能体之间的统一通信格式。

一条消息 = 谁发的（`sender`）、发给谁（`recipient`）、什么类型（`kind`）、
带什么载荷（`payload`）、什么时候发的（`sent_at`）。

消息类型按赛题分工划分：

- `SITUATION`（态势）：运维智能体 → 资源控制智能体，通报全网状态与异常；
- `DIAGNOSIS`（诊断）：运维智能体 → 资源控制智能体，给出故障定位与自愈建议；
- `REQUEST`（请求）：资源控制智能体 → 运维智能体，请求补充感知或复核；
- `DECISION`（决策）：资源控制智能体 → 全体，宣告将要下发的路径调整；
- `REJECT`（拒绝）：冲突仲裁后的否决回执（携带仲裁理由）。

**载荷保持可序列化**（dict），便于落盘、复盘与 RAG 检索——RAG 知识库里的
「故障案例库」正是这些消息的沉淀。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageKind(str, Enum):
    """A2A 消息类型。"""

    SITUATION = "situation"   # 运维 → 控制：全网态势
    DIAGNOSIS = "diagnosis"   # 运维 → 控制：故障诊断与自愈建议
    REQUEST = "request"       # 控制 → 运维：请求补充感知/复核
    DECISION = "decision"     # 控制 → 全体：宣告路径调整
    REJECT = "reject"         # 任意 → 发送方：仲裁否决回执


@dataclass
class A2AMessage:
    """一条 A2A 消息。"""

    sender: str
    recipient: str
    kind: MessageKind
    payload: dict[str, Any] = field(default_factory=dict)
    sent_at: float = field(default_factory=time.time)
    correlation_id: str = ""   # 关联同一任务的 id（请求→回执）
    priority: int = 0          # 越大越先处理（0 = 普通）

    def to_dict(self) -> dict[str, Any]:
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "kind": self.kind.value,
            "payload": self.payload,
            "sent_at": self.sent_at,
            "correlation_id": self.correlation_id,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "A2AMessage":
        return cls(
            sender=raw["sender"],
            recipient=raw["recipient"],
            kind=MessageKind(raw["kind"]),
            payload=raw.get("payload", {}),
            sent_at=raw.get("sent_at", 0.0),
            correlation_id=raw.get("correlation_id", ""),
            priority=int(raw.get("priority", 0)),
        )


class MessageBus:
    """进程内消息总线：按收件人投递，支持按优先级 + 到达序出队。

    刻意做成**同步内存实现**——赛题的 A2A 是「逻辑协议」而非分布式通信，
    同步实现才能保证实验可复现（无并发竞态）。
    """

    def __init__(self) -> None:
        self._inbox: dict[str, list[A2AMessage]] = {}
        self._history: list[A2AMessage] = []

    def publish(self, message: A2AMessage) -> None:
        """投递一条消息（同时进入历史，便于复盘）。"""
        self._inbox.setdefault(message.recipient, []).append(message)
        self._history.append(message)

    def receive(self, recipient: str) -> list[A2AMessage]:
        """取出并清空某收件人的消息（按优先级降序，同优先级按到达序）。"""
        messages = self._inbox.pop(recipient, [])
        return sorted(messages, key=lambda m: (-m.priority, m.sent_at))

    def peek(self, recipient: str) -> list[A2AMessage]:
        """查看某收件人的待处理消息（不清空）。"""
        return list(self._inbox.get(recipient, []))

    @property
    def history(self) -> list[A2AMessage]:
        """全部已投递消息（按时间序）。"""
        return list(self._history)
