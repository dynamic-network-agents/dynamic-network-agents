"""端到端静态 QoS 合成（下发校验口径）。

精确对齐仿真器 netsim/openapi.py `_compose_qos`：

    D = Σ d_i                      端到端时延（累加）
    J = sqrt(Σ j_i²)               端到端抖动（均方根合成）
    B = min_i b_i                  端到端带宽（瓶颈链路最小值）
    L = 1 - Π(1 - p_i)             端到端丢包率（乘积合成）
    E ≈ Σ ε_i                      端到端误码率（小误码率近似累加）
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import networkx as nx

from common.modeling.models import LinkParams


@dataclass
class QoSMetrics:
    """一条路径合成出的五项端到端指标。"""
    delay_ms: float = 0.0
    jitter_ms: float = 0.0
    bandwidth_bps: int = 0
    ber: float = 0.0
    packet_loss_rate: float = 0.0


def compose_from_params(params: list[LinkParams]) -> QoSMetrics:
    """纯函数：由逐跳链路参数合成端到端 QoS（不依赖图，便于单测）。"""
    delay = sum(p.delay_ms for p in params)
    jitter = math.sqrt(sum(p.jitter_ms ** 2 for p in params))
    bandwidth = min((p.bandwidth_bps for p in params), default=0)

    loss = 1.0
    for p in params:
        loss *= (1.0 - p.packet_loss_rate)
    packet_loss = 1.0 - loss

    ber = sum(p.ber for p in params)

    return QoSMetrics(
        delay_ms=delay,
        jitter_ms=jitter,
        bandwidth_bps=bandwidth,
        ber=ber,
        packet_loss_rate=packet_loss,
    )


def edge_data_by_link_id(graph: nx.MultiGraph, link_id: str) -> dict:
    """按 link_id（即 MultiGraph 边 key）取边属性。找不到抛 KeyError。"""
    for u, v, key in graph.edges(keys=True):
        if key == link_id:
            return graph.get_edge_data(u, v, key)
    raise KeyError(f"链路 {link_id} 不在图中")


def compose_qos(link_ids: list[str], graph: nx.MultiGraph) -> QoSMetrics:
    """由链路 id 序列（对齐 API segments）从图里取参数并合成端到端 QoS。"""
    params: list[LinkParams] = []
    for lid in link_ids:
        data = edge_data_by_link_id(graph, lid)
        params.append(LinkParams(
            delay_ms=data["delay_ms"],
            jitter_ms=data["jitter_ms"],
            bandwidth_bps=data["bandwidth_bps"],
            ber=data["ber"],
            packet_loss_rate=data["packet_loss_rate"],
        ))
    return compose_from_params(params)
