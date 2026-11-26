"""路径放置：两阶段贪心（test 优先 → 背景填位）+ 局部搜索。

放置口径：
- **F1/F2 与纯背景 flow**：走 least-contention（在静态可行候选里选「自身方向最大
  利用率最小」的路径），尽量不挤占 test 链路；
- **F3 test flow**：选第一条方向容量装得下的候选；都装不下就退到最便宜的一条
  静态可行路径，并标记 `degraded`。

局部搜索对**未预测达标**的 test flow 逐个换候选路径，只要优先级加权达标数提升
就接受（hill-climb）。
"""
from __future__ import annotations

import networkx as nx

from common.algorithms.flow.models import CapacityState, FlowPlan, PlanConfig
from common.algorithms.flow.scoring import flow_meets_utilization, score_with_state
from common.modeling.flow import FlowKey


def path_utilization(
    flow_plan: FlowPlan,
    candidate: list[str],
    state: CapacityState,
) -> float:
    """候选路径**自身**各方向上的最大利用率（叠加当前 load）。

    口径：只看该候选经过的链路方向。用全局最大值会在「存在不可避瓶颈」时让
    所有候选并列（都等于那个瓶颈的利用率），使 least-contention 退化成「取第一条」。
    """
    demand = state.demand(flow_plan.services, candidate, flow_plan.flow_key[0])
    best = 0.0
    for (link_id, sign), value in demand.items():
        capacity = state.capacity.get(link_id, 0)
        if capacity > 0:
            best = max(best, (state.load.get((link_id, sign), 0) + value) / capacity)
    return best


def least_contention_path(
    flow_plan: FlowPlan,
    state: CapacityState,
    config: PlanConfig,
) -> list[str] | None:
    """在静态可行候选里选「自身方向最大利用率最小」的路径；优先能装下的。

    口径修正（2026-11-25）：原来用全网最大利用率，只要网上存在一条不可避瓶颈，
    所有候选就并列成同一个值，退化成「取第一条」。现在只看候选自身链路方向。
    """
    fitting: list[tuple[float, list[str]]] = []
    fallback: list[tuple[float, list[str]]] = []
    for candidate in flow_plan.candidates:
        utilization = path_utilization(flow_plan, candidate, state)
        fallback.append((utilization, candidate))
        demand = state.demand(flow_plan.services, candidate, flow_plan.flow_key[0])
        if state.fits(demand, config.bandwidth_headroom):
            fitting.append((utilization, candidate))
    pool = fitting or fallback
    if not pool:
        return None
    return min(pool, key=lambda item: item[0])[1]


def place_flow(
    flow_plan: FlowPlan,
    state: CapacityState,
    config: PlanConfig,
) -> list[str] | None:
    """给一个 flow 选一条路径（不写回 `flow_plan.path`，由调用方决定）。"""
    if flow_plan.flow_class.hard or flow_plan.weight == 0:
        # F1/F2（物理无解：接入段 test-only 或 test+bg 已超容）与纯背景 flow：
        # 不参与容量竞争，least-contention 尽量不挤占 test 链路
        return least_contention_path(flow_plan, state, config)

    # F3 test flow：第一个方向容量装得下的候选（现状在首位，故「能留就留」）
    for candidate in flow_plan.candidates:
        demand = state.demand(flow_plan.services, candidate, flow_plan.flow_key[0])
        if state.fits(demand, config.bandwidth_headroom):
            return candidate
    if flow_plan.candidates:
        # 都装不下 → 退化：退到最便宜的静态可行路径并打标记（调用方会看到 degraded）。
        # 此时该 flow 的并发负载可能超过链路容量，实测大概率不达标；
        # 静态判定本身仍是通过的（瓶颈带宽 ≥ 单业务需求），所以不能直接判死。
        flow_plan.degraded = True
        return flow_plan.candidates[0]
    return None


def local_search(
    plans: dict[FlowKey, FlowPlan],
    graph: nx.MultiGraph,
    config: PlanConfig,
) -> float:
    """对未预测达标的 test flow 换候选路径，提升优先级加权达标数（hill-climb）。"""
    state = CapacityState.from_graph(graph)
    state.load = state.recompute(plans)
    best = score_with_state(plans, state, config.utilization_limit)
    for _ in range(config.local_search_rounds):
        improved = False
        for flow_plan in plans.values():
            if flow_plan.flow_class.hard or flow_plan.weight == 0 or not flow_plan.path:
                continue
            if flow_meets_utilization(flow_plan, state, config.utilization_limit):
                continue
            original_path = flow_plan.path
            best_candidate: list[str] | None = None
            best_score = best
            best_load: dict | None = None
            for candidate in flow_plan.candidates:
                if candidate == original_path:
                    continue
                flow_plan.path = candidate
                # 换了任一条 flow 的路径，整份负载都要重算（别的 flow 的占用不变，
                # 但本 flow 的占用变了），用重算后的负载试算加权达标数
                trial_load = state.recompute(plans)
                score = score_with_state(
                    plans, state.with_load(trial_load), config.utilization_limit,
                )
                if score > best_score + 1e-9:
                    best_score, best_candidate, best_load = score, candidate, trial_load
                flow_plan.path = original_path
            if best_candidate is not None and best_load is not None:
                flow_plan.path = best_candidate
                best, state.load = best_score, best_load
                improved = True
        if not improved:
            break
    return best
