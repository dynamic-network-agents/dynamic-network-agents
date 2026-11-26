"""评分与达标判定：优先级加权达标数（Σ 2^priority(test) · 1[预测达标]）。

三个公共入口：
- `weighted_score`：按各 flow **当前计划里的路径**评分；
- `weighted_score_with_paths`：按**给定路径**评分（用于与「已装路径」对比得 Δscore）；
- `predicted_compliance`：逐 flow 的预测达标布尔（供闭环校验「预测 vs 实测」）。

达标口径：某 flow 的全部 test 业务，在其**自身方向**上的最大链路利用率
≤ `utilization_limit`（注意与摆放裕度 `bandwidth_headroom` 是两个阈值）。
"""
from __future__ import annotations

import networkx as nx

from common.algorithms.flow.models import CapacityState, FlowPlan, PlanConfig
from common.algorithms.flow.candidates import normalize_path
from common.modeling.flow import FlowKey, service_is_test
from common.modeling.models import Service


def _service_utilization(
    service: Service,
    flow_plan: FlowPlan,
    state: CapacityState,
) -> float:
    """单条业务自身方向上的最大链路利用率（只看该业务方向，不含同 flow 反向背景）。"""
    if not flow_plan.path:
        return float("inf")     # 无路径 → 不可能达标
    demand = state.demand([service], flow_plan.path, flow_plan.flow_key[0])
    best = 0.0
    for (link_id, _sign) in demand:
        capacity = state.capacity.get(link_id, 0)
        if capacity > 0:
            best = max(best, state.load.get((link_id, _sign), 0) / capacity)
    return best


def flow_meets_utilization(
    flow_plan: FlowPlan,
    state: CapacityState,
    utilization_limit: float,
) -> bool:
    """flow 的全部 test 业务是否都预测达标（无 test 视为满足）。"""
    test_services = [s for s in flow_plan.services if service_is_test(s)]
    if not test_services:
        return True
    return all(
        _service_utilization(service, flow_plan, state) <= utilization_limit
        for service in test_services
    )


def score_with_state(
    plans: dict[FlowKey, FlowPlan],
    state: CapacityState,
    utilization_limit: float,
) -> float:
    """优先级加权达标数（硬失败 flow、纯背景 flow、无路径 flow 不计）。"""
    total = 0.0
    for flow_plan in plans.values():
        if flow_plan.flow_class.hard or flow_plan.weight == 0 or not flow_plan.path:
            continue
        if flow_meets_utilization(flow_plan, state, utilization_limit):
            total += flow_plan.weight
    return total


def weighted_score(
    plans: dict[FlowKey, FlowPlan],
    graph: nx.MultiGraph,
    config: PlanConfig | None = None,
) -> float:
    """预测的优先级加权达标数（test flow 自身方向最大利用率 ≤ utilization_limit）。"""
    cfg = config or PlanConfig()
    state = CapacityState.from_graph(graph)
    state.load = state.recompute(plans)
    return score_with_state(plans, state, cfg.utilization_limit)


def weighted_score_with_paths(
    plans: dict[FlowKey, FlowPlan],
    graph: nx.MultiGraph,
    paths: dict[FlowKey, list[str] | None],
    config: PlanConfig | None = None,
) -> float:
    """按给定路径映射评估加权达标数（用于与「当前已装路径」对比得 Δscore）。

    `paths` 里缺失/失效（链路已断、不连续）的 flow 按「无路径」计，不抛异常。
    """
    cfg = config or PlanConfig()
    state = CapacityState.from_graph(graph)
    saved_paths = {key: flow_plan.path for key, flow_plan in plans.items()}
    try:
        for key, flow_plan in plans.items():
            raw = paths.get(key)
            flow_plan.path = normalize_path(graph, key, raw) if raw else None
        state.load = state.recompute(plans)
        return score_with_state(plans, state, cfg.utilization_limit)
    finally:
        for key, flow_plan in plans.items():
            flow_plan.path = saved_paths[key]


def predicted_compliance(
    plans: dict[FlowKey, FlowPlan],
    graph: nx.MultiGraph,
    config: PlanConfig | None = None,
) -> dict[FlowKey, bool]:
    """每个 flow 的预测达标布尔（供闭环校验「预测 vs 实测」）。"""
    cfg = config or PlanConfig()
    state = CapacityState.from_graph(graph)
    state.load = state.recompute(plans)
    return {
        key: flow_meets_utilization(flow_plan, state, cfg.utilization_limit)
        for key, flow_plan in plans.items()
    }
