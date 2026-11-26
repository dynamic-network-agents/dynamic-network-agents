"""候选路径：路径归一化 + K-最短候选生成（静态 QoS 硬过滤 + 代价排序）。

候选来源是 Yen K-最短（`k_shortest_paths`），逐条做静态 QoS 合成与判定
（`compose_qos` + `check_qos`），**不满足需求硬过滤**，剩余按链路代价升序排列。
"""
from __future__ import annotations

import networkx as nx

from common.algorithms.flow.models import PlanConfig
from common.algorithms.topology.graph import node_path_to_link_ids, validate_path
from common.algorithms.path.k_shortest import k_shortest_paths
from common.modeling.flow import FlowKey
from common.modeling.link_quality import path_cost
from common.modeling.models import Requirement
from common.modeling.path_qos import compose_qos
from common.modeling.qos_checker import check_qos


def normalize_path(
    graph: nx.MultiGraph,
    flow_key: FlowKey,
    path: list[str] | tuple[str, ...] | None,
) -> list[str] | None:
    """把路径归一化成 `flow_key[0] → flow_key[1]` 方向；不连续/链路缺失返回 None。

    仿真器存的 flow 路径方向取决于最后一次提交的顺序，可能与本端约定相反；
    容量记账（`directional_demand`）要求路径从 `flow_key[0]` 起步，故先归一化。
    """
    if not path:
        return None
    link_ids = list(path)
    if not validate_path(graph, link_ids, flow_key[0], flow_key[1]):
        return link_ids
    if not validate_path(graph, link_ids[::-1], flow_key[0], flow_key[1]):
        return link_ids[::-1]
    return None


def candidate_paths(
    graph: nx.MultiGraph,
    flow_key: FlowKey,
    requirement: Requirement,
    config: PlanConfig,
) -> list[list[str]]:
    """该 flow 的静态可行候选路径（按链路代价升序）。

    实测违约过的路径（`config.excluded_paths`）优先剔除；若剔除后一条不剩，
    则忽略惩罚回退——flow 彻底失去路径比走一条实测违约的路更糟。
    """
    excluded = config.excluded_paths.get(flow_key) or set()
    feasible = _feasible_candidates(graph, flow_key, requirement, config, excluded)
    if not feasible and excluded:
        feasible = _feasible_candidates(graph, flow_key, requirement, config, set())
    return feasible


def _feasible_candidates(
    graph: nx.MultiGraph,
    flow_key: FlowKey,
    requirement: Requirement,
    config: PlanConfig,
    skip: set[tuple[str, ...]],
) -> list[list[str]]:
    """K-最短 → 跳过被排除的 → 静态 QoS 硬过滤 → 按代价升序。"""
    scored: list[tuple[float, list[str]]] = []
    for node_path in k_shortest_paths(
        graph, flow_key[0], flow_key[1], config.candidate_path_count,
    ):
        link_ids = node_path_to_link_ids(graph, node_path)
        if tuple(link_ids) in skip:
            continue
        if not check_qos(compose_qos(link_ids, graph), requirement).feasible:
            continue
        scored.append((path_cost(link_ids, graph, config.link_cost_weights), link_ids))
    scored.sort(key=lambda item: item[0])
    return [link_ids for _, link_ids in scored]
