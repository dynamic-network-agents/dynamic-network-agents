"""单 flow 最优路径：QoS 硬过滤 → 代价升序 + 时延升序排序。"""
from __future__ import annotations

import networkx as nx

from common.modeling.models import Requirement
from common.modeling.path_qos import compose_qos
from common.modeling.qos_checker import check_qos
from common.modeling.link_quality import path_cost
from common.algorithms.path.k_shortest import k_shortest_paths
from common.algorithms.topology.graph import node_path_to_link_ids


def optimize_flow(
    graph: nx.MultiGraph,
    src: str,
    dst: str,
    requirement: Requirement,
    k: int = 30,
    weights: dict[str, float] | None = None,
) -> list[str] | None:
    """返回满足 QoS 约束且代价最小的链路 id 序列；无可行路径返回 None。"""
    candidates: list[tuple[float, float, list[str]]] = []
    for node_path in k_shortest_paths(graph, src, dst, k):
        link_ids = node_path_to_link_ids(graph, node_path)
        qos = compose_qos(link_ids, graph)
        if not check_qos(qos, requirement).feasible:
            continue
        cost = path_cost(link_ids, graph, weights)
        candidates.append((cost, qos.delay_ms, link_ids))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]))  # 代价升序，时延升序
    return candidates[0][2]
