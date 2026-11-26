"""QoS 硬约束判定（五项，逐项带容差）。

容差对齐仿真器 netsim/openapi.py `_qos_violations`（硬编码，勿改）：

    D <= req.delay_ms + 1.0
    J <= req.jitter_ms + 1e-9
    B >= req.bandwidth_bps          （无容差）
    L <= req.packet_loss_rate + 1e-9
    E <= req.ber + 1e-12
"""
from __future__ import annotations

from dataclasses import dataclass, field

from common.modeling.models import Requirement
from common.modeling.path_qos import QoSMetrics


@dataclass(frozen=True)
class Tolerances:
    delay_ms: float = 1.0
    jitter_ms: float = 1e-9
    packet_loss: float = 1e-9
    ber: float = 1e-12
    bandwidth: float = 0.0


@dataclass
class QoSResult:
    feasible: bool
    violations: list[str] = field(default_factory=list)
    # 每项剩余裕度（正=有余量，负=已违约）。时延/抖动/丢包/误码为 req-实际；带宽为 实际-req。
    margin: dict[str, float] = field(default_factory=dict)


def check_qos(qos: QoSMetrics, req: Requirement, tol: Tolerances = Tolerances()) -> QoSResult:
    violations: list[str] = []
    margin: dict[str, float] = {}

    # 时延（上界）
    if qos.delay_ms > req.delay_ms + tol.delay_ms:
        violations.append("delay")
    margin["delay"] = req.delay_ms - qos.delay_ms

    # 抖动（上界）
    if qos.jitter_ms > req.jitter_ms + tol.jitter_ms:
        violations.append("jitter")
    margin["jitter"] = req.jitter_ms - qos.jitter_ms

    # 带宽（下界）
    if qos.bandwidth_bps < req.bandwidth_bps - tol.bandwidth:
        violations.append("bandwidth")
    margin["bandwidth"] = qos.bandwidth_bps - req.bandwidth_bps

    # 丢包（上界）
    if qos.packet_loss_rate > req.packet_loss_rate + tol.packet_loss:
        violations.append("packet_loss")
    margin["packet_loss"] = req.packet_loss_rate - qos.packet_loss_rate

    # 误码（上界）
    if qos.ber > req.ber + tol.ber:
        violations.append("ber")
    margin["ber"] = req.ber - qos.ber

    return QoSResult(feasible=len(violations) == 0, violations=violations, margin=margin)
