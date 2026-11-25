"""流级优先级加权选路器（FPCB 贪心版）。

决策单位是 flow（无序端点对）；目标：最大化 Σ 2^priority(test) · 1[test 达标]。
约束：静态 QoS（用 flow 需求交集判定，等价于逐业务判定）+ 方向容量。

分类（数学建模 §6.5）：
- F1：接入链路 test-only 超容（物理无解，牺牲）
- F2：接入链路 test 放得下、test+background 超容（背景诱因，接入段实际硬失败，牺牲）
- F3：可行（正常分配）

分配顺序：F3 按权重降序先占位（高优先级先）；纯背景 flow 后填位（least-contention）；
F1/F2 只给一条静态可行路径（不投入容量优化）。

**规划器是纯函数**：输出只取决于 `(flows, graph, config)`，不看"当前已装路径"。
这样同一份快照重算两次必然得到同一结果；闭环把"要不要下发"交给调用方的
Δscore 闸门（`baseline.reroute_loop`），而不是让规划器去猜稳定性。实测：
把 incumbent 喂进贪心（现状优先）在 big 场景上既更差也不稳定（sce05 592→384），
因此不采用。
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

import networkx as nx

from algorithms.capacity import (
    DirKey,
    add_load,
    capacity_map,
    directional_demand,
    fits,
)
from algorithms.graph import node_path_to_link_ids, validate_path
from algorithms.k_shortest_paths import k_shortest_paths
from math_modeling.flow import flow_requirement, flow_weight, service_is_test
from math_modeling.link_quality import path_cost
from math_modeling.models import Requirement, Service
from math_modeling.path_qos import compose_qos
from math_modeling.qos_checker import check_qos


class FlowClass(Enum):
    F1 = "F1"   # 接入链路 test-only 超容（物理无解）
    F2 = "F2"   # 接入链路 test 放得下、test+bg 超容（实际硬失败）
    F3 = "F3"   # 可行

    @property
    def hard(self) -> bool:
        return self in (FlowClass.F1, FlowClass.F2)


@dataclass
class FlowPlan:
    flow_key: tuple[str, str]
    services: list[Service]
    requirement: Requirement
    weight: float
    cls: FlowClass
    candidates: list[list[str]] = field(default_factory=list)
    path: list[str] | None = None
    partial: bool = False


@dataclass
class PlanConfig:
    k: int = 30
    rho: float = 0.2
    weights: dict[str, float] | None = None
    local_search: bool = True
    ls_rounds: int = 10
    meet_util: float = 1.0          # 预测达标阈值：自身方向最大利用率 ≤ 该值
    # 实测违约过的路径：flow_key -> {路径元组}，规划时剔除（无其它候选时回退）
    excluded_paths: dict[tuple[str, str], set[tuple[str, ...]]] = field(default_factory=dict)


@dataclass
class UavDemand:
    out_test: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    in_test: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    out_all: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    in_all: dict[str, int] = field(default_factory=lambda: defaultdict(int))

def access_links(graph: nx.MultiGraph) -> dict[str, tuple[str, int]]:
    """UAV -> (接入链路 id, 单方向带宽)。

    返回的是「每个 UAV 一条链路」的查表，**不是 flow**：键是单个 UAV 节点，
    值是该 UAV 相邻链路里带宽最大的一条。只用于 `classify_flow` 判 F1/F2，
    不参与容量记账（容量按 `capacity_map` + `DirKey` 逐链路逐方向算）。

    为什么 UAV 有「接入链路」：仿真器端别模型把 ground→sN(交换机)、uav/air→hN(主机)，
    且两端都是主机的链路直接报错「端别模型不成立」（`sim_src/netsim/sdncommon.py`
    的 `adapt_spec`），所以 UAV 的流量只能经「UAV—地面」这类接入链路出入。

    近似口径：一个 UAV 有多条接入链路时只取最粗的那条，判 F1/F2 得到的是
    **乐观上界**（窄链路不参与比较）；要精确应改成该 UAV 全部接入链路容量之和，
    或用实际规划路径的首/末跳判定。
    """
    out: dict[str, tuple[str, int]] = {}
    for u, v, key, data in graph.edges(keys=True, data=True):
        for nd in (u, v):
            if graph.nodes[nd].get("node_type") != "uav":
                continue
            bw = int(data.get("bandwidth_bps", 0))
            cur = out.get(nd)
            if cur is None or bw > cur[1]:
                out[nd] = (key, bw)
    return out


def per_uav_demand(services: list[Service]) -> UavDemand:
    """按 UAV 汇总出/入向的 test-only 与 test+bg 带宽需求。"""
    d = UavDemand()
    for s in services:
        bps = int(s.requirement.bandwidth_bps) if s.requirement else 0
        if bps <= 0:
            continue
        d.out_all[s.src_node_id] += bps
        d.in_all[s.dst_node_id] += bps
        if service_is_test(s):
            d.out_test[s.src_node_id] += bps
            d.in_test[s.dst_node_id] += bps
    return d


def classify_flow(
    services: list[Service],
    graph: nx.MultiGraph,
    access: dict[str, tuple[str, int]],
    demand: UavDemand,
) -> FlowClass:
    """按端点接入链路的 test-only / test+bg 需求给 flow 分类。"""
    test_svcs = [s for s in services if service_is_test(s)]
    if not test_svcs:
        return FlowClass.F3
    for s in test_svcs:
        for nd, outgoing in ((s.src_node_id, True), (s.dst_node_id, False)):
            if nd not in access:
                continue
            _, cap = access[nd]
            if outgoing:
                if demand.out_test[nd] > cap:
                    return FlowClass.F1
                if demand.out_all[nd] > cap:
                    return FlowClass.F2
            else:
                if demand.in_test[nd] > cap:
                    return FlowClass.F1
                if demand.in_all[nd] > cap:
                    return FlowClass.F2
    return FlowClass.F3


def normalize_path(
    graph: nx.MultiGraph,
    flow_key: tuple[str, str],
    path: list[str] | tuple[str, ...] | None,
) -> list[str] | None:
    """把路径归一化成 `flow_key[0] → flow_key[1]` 方向；不连续/链路缺失返回 None。

    仿真器存的 flow 路径方向取决于最后一次提交的顺序，可能与本端约定相反；
    容量记账（`directional_demand`）要求路径从 `flow_key[0]` 起步，故先归一化。
    """
    if not path:
        return None
    p = list(path)
    if not validate_path(graph, p, flow_key[0], flow_key[1]):
        return p
    if not validate_path(graph, p[::-1], flow_key[0], flow_key[1]):
        return p[::-1]
    return None


def _candidates(
    graph: nx.MultiGraph,
    flow_key: tuple[str, str],
    requirement: Requirement,
    cfg: PlanConfig,
) -> list[list[str]]:
    excluded = cfg.excluded_paths.get(flow_key) or set()

    def build(skip: set[tuple[str, ...]]) -> list[list[str]]:
        scored: list[tuple[float, list[str]]] = []
        for node_path in k_shortest_paths(graph, flow_key[0], flow_key[1], cfg.k):
            link_ids = node_path_to_link_ids(graph, node_path)
            if tuple(link_ids) in skip:
                continue
            if not check_qos(compose_qos(link_ids, graph), requirement).feasible:
                continue
            scored.append((path_cost(link_ids, graph, cfg.weights), link_ids))
        scored.sort(key=lambda x: x[0])
        return [p for _, p in scored]

    cands = build(excluded)
    if not cands and excluded:
        # 排除后无候选（例如该 flow 只有一条可行路）：忽略惩罚兜底，
        # 否则 flow 会彻底失去路径，比走一条实测违约的路更糟。
        cands = build(set())
    return cands


def _local_util(
    plan: FlowPlan,
    cand: list[str],
    load: dict[DirKey, int],
    cap: dict[str, int],
    graph: nx.MultiGraph,
) -> float:
    """候选路径**自身**各方向上的最大利用率（叠加当前 load）。

    口径：只看该候选经过的链路方向。用全局最大值会在「存在不可避瓶颈」时让
    所有候选并列（都等于那个瓶颈的利用率），使 least-contention 退化成「取第一条」。
    """
    d = directional_demand(plan.flow_key[0], plan.services, cand, graph)
    best = 0.0
    for (lid, _sign), v in d.items():
        c = cap.get(lid, 0)
        if c > 0:
            best = max(best, (load.get((lid, _sign), 0) + v) / c)
    return best


def _least_contention(
    plan: FlowPlan,
    graph: nx.MultiGraph,
    load: dict[DirKey, int],
    cap: dict[str, int],
    cfg: PlanConfig,
) -> list[str] | None:
    """在静态可行候选里选「自身方向最大利用率最小」的路径；优先能装下的。

    口径修正（2026-11-25）：原来用全网最大利用率，只要网上存在一条不可避瓶颈，
    所有候选就并列成同一个值，退化成「取第一条」。现在只看候选自身链路方向。
    """
    fitting: list[tuple[float, list[str]]] = []
    fallback: list[tuple[float, list[str]]] = []
    for cand in plan.candidates:
        u = _local_util(plan, cand, load, cap, graph)
        fallback.append((u, cand))
        d = directional_demand(plan.flow_key[0], plan.services, cand, graph)
        if fits(d, load, cap, cfg.rho):
            fitting.append((u, cand))
    pool = fitting or fallback
    if not pool:
        return None
    return min(pool, key=lambda x: x[0])[1]


def _place(
    plan: FlowPlan,
    graph: nx.MultiGraph,
    load: dict[DirKey, int],
    cap: dict[str, int],
    cfg: PlanConfig,
) -> list[str] | None:
    if plan.cls.hard or plan.weight == 0:
        # F1/F2（物理无解）与纯背景：least-contention，尽量不挤占 test 链路
        return _least_contention(plan, graph, load, cap, cfg)

    # F3 test flow：第一个方向容量装得下的候选（现状在首位，故「能留就留」）
    for cand in plan.candidates:
        d = directional_demand(plan.flow_key[0], plan.services, cand, graph)
        if fits(d, load, cap, cfg.rho):
            return cand
    if plan.candidates:
        plan.partial = True
        return plan.candidates[0]
    return None


def _recompute_load(
    plans: dict[tuple[str, str], FlowPlan],
    graph: nx.MultiGraph,
) -> dict[DirKey, int]:
    load: dict[DirKey, int] = {}
    for p in plans.values():
        if p.path:
            add_load(load, directional_demand(p.flow_key[0], p.services, p.path, graph))
    return load


def _service_util(
    service: Service,
    plan: FlowPlan,
    load: dict[DirKey, int],
    cap: dict[str, int],
    graph: nx.MultiGraph,
) -> float:
    """单条业务自身方向上的最大链路利用率（只看该业务方向，不含同 flow 反向背景）。"""
    if not plan.path:
        return float("inf")     # 无路径 → 不可能达标
    d = directional_demand(plan.flow_key[0], [service], plan.path, graph)
    best = 0.0
    for key in d:
        c = cap.get(key[0], 0)
        if c > 0:
            best = max(best, load.get(key, 0) / c)
    return best


def flow_meets(
    plan: FlowPlan,
    load: dict[DirKey, int],
    cap: dict[str, int],
    graph: nx.MultiGraph,
    meet_util: float,
) -> bool:
    """flow 的全部 test 业务是否都预测达标（无 test 视为满足）。"""
    test_svcs = [s for s in plan.services if service_is_test(s)]
    if not test_svcs:
        return True
    return all(
        _service_util(s, plan, load, cap, graph) <= meet_util
        for s in test_svcs
    )


def _score(
    plans: dict[tuple[str, str], FlowPlan],
    load: dict[DirKey, int],
    cap: dict[str, int],
    graph: nx.MultiGraph,
    meet_util: float,
) -> float:
    s = 0.0
    for p in plans.values():
        if p.cls.hard or p.weight == 0 or not p.path:
            continue
        if flow_meets(p, load, cap, graph, meet_util):
            s += p.weight
    return s


def local_search(
    plans: dict[tuple[str, str], FlowPlan],
    graph: nx.MultiGraph,
    cfg: PlanConfig,
) -> float:
    """对未预测达标的 test flow 换候选路径，提升优先级加权达标数（hill-climb）。"""
    cap = capacity_map(graph)
    load = _recompute_load(plans, graph)
    best = _score(plans, load, cap, graph, cfg.meet_util)
    for _ in range(cfg.ls_rounds):
        improved = False
        for p in plans.values():
            if p.cls.hard or p.weight == 0 or not p.path:
                continue
            if flow_meets(p, load, cap, graph, cfg.meet_util):
                continue
            old = p.path
            best_cand: list[str] | None = None
            best_score = best
            best_load: dict[DirKey, int] | None = None
            for cand in p.candidates:
                if cand == old:
                    continue
                p.path = cand
                trial = _recompute_load(plans, graph)
                sc = _score(plans, trial, cap, graph, cfg.meet_util)
                if sc > best_score + 1e-9:
                    best_score, best_cand, best_load = sc, cand, trial
                p.path = old
            if best_cand is not None and best_load is not None:
                p.path = best_cand
                best, load = best_score, best_load
                improved = True
        if not improved:
            break
    return best


def plan_score(
    plans: dict[tuple[str, str], FlowPlan],
    graph: nx.MultiGraph,
    config: PlanConfig | None = None,
) -> float:
    """预测的优先级加权达标数（test flow 自身方向最大利用率 ≤ meet_util）。"""
    cfg = config or PlanConfig()
    cap = capacity_map(graph)
    load = _recompute_load(plans, graph)
    return _score(plans, load, cap, graph, cfg.meet_util)


def score_with_paths(
    plans: dict[tuple[str, str], FlowPlan],
    graph: nx.MultiGraph,
    paths: dict[tuple[str, str], list[str] | None],
    config: PlanConfig | None = None,
) -> float:
    """按给定路径映射评估加权达标数（用于与「当前已装路径」对比得 Δscore）。

    `paths` 里缺失/失效（链路已断、不连续）的 flow 按「无路径」计，不抛异常。
    """
    cfg = config or PlanConfig()
    cap = capacity_map(graph)
    saved = {k: p.path for k, p in plans.items()}
    try:
        for k, p in plans.items():
            raw = paths.get(k)
            p.path = normalize_path(graph, k, raw) if raw else None
        load = _recompute_load(plans, graph)
        return _score(plans, load, cap, graph, cfg.meet_util)
    finally:
        for k, p in plans.items():
            p.path = saved[k]


def predicted_meet(
    plans: dict[tuple[str, str], FlowPlan],
    graph: nx.MultiGraph,
    config: PlanConfig | None = None,
) -> dict[tuple[str, str], bool]:
    """每个 flow 的预测达标布尔（供闭环校验「预测 vs 实测」）。"""
    cfg = config or PlanConfig()
    cap = capacity_map(graph)
    load = _recompute_load(plans, graph)
    return {
        k: flow_meets(p, load, cap, graph, cfg.meet_util)
        for k, p in plans.items()
    }


def plan(
    flows: dict[tuple[str, str], list[Service]],
    graph: nx.MultiGraph,
    config: PlanConfig | None = None,
) -> dict[tuple[str, str], FlowPlan]:
    """为每个 flow 选一条路径；返回 flow_key -> FlowPlan。

    纯函数：同一 `(flows, graph, config)` 必然得到同一结果（无随机性）。
    是否下发由调用方按「修复失效路径 / Δscore ≥ Δmin」决定（见 `baseline.reroute_loop`）。
    """
    cfg = config or PlanConfig()
    access = access_links(graph)
    all_services = [s for svcs in flows.values() for s in svcs]
    demand = per_uav_demand(all_services)
    cap = capacity_map(graph)

    plans: dict[tuple[str, str], FlowPlan] = {}
    for key, svcs in flows.items():
        req = flow_requirement(svcs)
        if req is None:
            continue
        p = FlowPlan(
            flow_key=key,
            services=svcs,
            requirement=req,
            weight=flow_weight(svcs),
            cls=classify_flow(svcs, graph, access, demand),
        )
        p.candidates = _candidates(graph, key, req, cfg)
        plans[key] = p

    load: dict[DirKey, int] = {}
    order = sorted(
        plans.values(),
        key=lambda p: (p.cls.hard, -p.weight, p.requirement.bandwidth_bps),
    )
    for p in order:
        chosen = _place(p, graph, load, cap, cfg)
        if chosen is None:
            continue
        p.path = chosen
        add_load(load, directional_demand(p.flow_key[0], p.services, chosen, graph))

    if cfg.local_search:
        local_search(plans, graph, cfg)
    return plans
