"""flow 分组与 flow 级需求聚合。

关键事实：路径按源/目的 IP 键控，同一对 UAV 之间的所有业务（含 background）
共用一条路径。所以优化单位是 flow（源-目 UAV 对），flow 需求取各业务需求的
交集：时延/抖动/丢包/误码取 min（最严），带宽取 max（最大需求）。
"""
from __future__ import annotations

from math_modeling.models import Requirement, Service


def group_services_by_flow(
    services: list[Service],
) -> dict[tuple[str, str], list[Service]]:
    """按 (src, dst) 分组。"""
    groups: dict[tuple[str, str], list[Service]] = {}
    for s in services:
        groups.setdefault(s.flow_key, []).append(s)
    return groups


def flow_requirement(services: list[Service]) -> Requirement | None:
    """flow 需求 = 组内各业务需求的交集。

    无任何带 requirement 的业务时返回 None。
    """
    reqs = [s.requirement for s in services if s.requirement is not None]
    if not reqs:
        return None
    return Requirement(
        delay_ms=min(r.delay_ms for r in reqs),
        jitter_ms=min(r.jitter_ms for r in reqs),
        bandwidth_bps=max(r.bandwidth_bps for r in reqs),
        ber=min(r.ber for r in reqs),
        packet_loss_rate=min(r.packet_loss_rate for r in reqs),
    )
