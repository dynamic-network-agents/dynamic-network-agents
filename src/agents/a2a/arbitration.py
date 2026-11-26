"""冲突仲裁：多个智能体对同一条链路/路径提出互斥动作时的裁决规则。

**为什么 baseline 不需要、agent 必须有**：baseline 是单一决策核心（贪心一次算完
全部 flow），不存在"两个决策者抢同一条路"；多智能体里运维智能体提自愈建议、
资源控制智能体提调度方案，可能指向互斥的路径。

**仲裁原则（确定性，同输入必同输出）**：

1. **角色优先**：资源控制智能体的**执行类**动作 > 运维智能体的**建议类**动作
   ——建议可以参考，但不能直接抢执行权（否则职责边界糊了）。
2. **业务优先级**：同角色内按业务 `priority` 降序（数值大者优先，与项目口径
   "8 最高、1 最低" 一致）。
3. **业务 ID 兜底**：优先级相同时按业务 ID 字典序，保证可复现。
4. **不受理的动作**：仲裁结果里明确给出被否决的动作与理由，回执由发起方转达。

仲裁只决定**动作取舍**，不产生新的网络决策——被采纳的动作仍要过
`common/control/` 的下发闸门（Δmin / 修复判定）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.a2a.message import A2AMessage, MessageKind


@dataclass
class ProposedAction:
    """一条待仲裁的动作提议。

    - `action_id`：唯一标识；
    - `actor`：发起者（智能体名）；
    - `service_id` / `flow_key`：作用对象；
    - `path`：提议的链路路径；
    - `priority`：业务优先级（越大越优先）；
    - `is_execution`：True = 要求直接执行（资源控制智能体），False = 建议
      （运维智能体的自愈建议）。
    """

    action_id: str
    actor: str
    service_id: str
    flow_key: tuple[str, str]
    path: list[str]
    priority: int = 0
    is_execution: bool = False
    reason: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def conflicts_with(self, other: "ProposedAction") -> bool:
        """是否互斥：作用同一 flow 且路径不同。"""
        return self.flow_key == other.flow_key and self.path != other.path


@dataclass
class ArbitrationResult:
    """仲裁结果：采纳哪些、否决哪些、为什么。"""

    accepted: list[ProposedAction] = field(default_factory=list)
    rejected: list[tuple[ProposedAction, str]] = field(default_factory=list)

    def accepted_paths(self) -> dict[tuple[str, str], list[str]]:
        """采纳动作按 flow 归并出的路径（每 flow 最多一条）。"""
        out: dict[tuple[str, str], list[str]] = {}
        for action in self.accepted:
            out.setdefault(action.flow_key, action.path)
        return out


def arbitrate(proposals: list[ProposedAction]) -> ArbitrationResult:
    """裁决一组互斥提议。

    规则见模块 docstring。**同样的输入必得同样的输出**（无随机、无时间依赖）。
    """
    result = ArbitrationResult()
    # 按 flow 分组：同一 flow 的多个互斥提议才需要仲裁
    by_flow: dict[tuple[str, str], list[ProposedAction]] = {}
    for proposal in proposals:
        by_flow.setdefault(proposal.flow_key, []).append(proposal)

    for flow_key, group in by_flow.items():
        if len(group) == 1:
            result.accepted.append(group[0])
            continue
        # 规则 1：执行类优先于建议类
        candidates = sorted(
            group,
            key=lambda a: (
                not a.is_execution,   # 执行类在前
                -a.priority,          # 业务优先级降序
                a.service_id,         # 业务 ID 字典序兜底
                a.action_id,
            ),
        )
        winner = candidates[0]
        result.accepted.append(winner)
        for loser in candidates[1:]:
            result.rejected.append((loser, _reject_reason(winner, loser)))
    return result


def _reject_reason(winner: ProposedAction, loser: ProposedAction) -> str:
    """给出一条可读的否决理由（回执给发起方，便于复盘）。"""
    if winner.is_execution != loser.is_execution:
        return f"执行类动作优先：采纳 {winner.actor} 的执行提议，否决 {loser.actor} 的建议"
    if winner.priority != loser.priority:
        return f"业务优先级更高：{winner.priority} > {loser.priority}"
    return f"同优先级按业务 ID 兜底：{winner.service_id} < {loser.service_id}"


def rejection_notice(
    rejected: ProposedAction,
    reason: str,
    *,
    recipient: str,
    correlation_id: str = "",
) -> A2AMessage:
    """构造一条否决回执消息。"""
    return A2AMessage(
        sender="a2a.arbitrator",
        recipient=recipient,
        kind=MessageKind.REJECT,
        payload={
            "action_id": rejected.action_id,
            "service_id": rejected.service_id,
            "flow_key": list(rejected.flow_key),
            "reason": reason,
        },
        correlation_id=correlation_id,
    )
