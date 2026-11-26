"""流级优先级加权选路器（FPCB 贪心版）—— 公共门面。

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
Δscore 闸门（`common/control/dispatch_gate.py`），而不是让规划器去猜稳定性。实测：
把 incumbent 喂进贪心（现状优先）在 big 场景上既更差也不稳定（sce05 592→384），
因此不采用。

模块分工（实现细节见各子模块）：
- `flow_models.py`：数据模型（`FlowClass` / `FlowPlan` / `PlanConfig` / `CapacityState`）
- `flow_classification.py`：F1/F2/F3 分类
- `flow_candidates.py`：路径归一化 + K-最短候选生成
- `flow_scoring.py`：达标判定与优先级加权评分
- `flow_placement.py`：两阶段贪心放置 + 局部搜索
"""
from __future__ import annotations

import networkx as nx

from common.algorithms.flow.candidates import candidate_paths, normalize_path
from common.algorithms.flow.classification import (
    classify_flow,
    per_uav_demand,
    uav_access_links,
)
from common.algorithms.flow.models import (
    CapacityState,
    FlowClass,
    FlowPlan,
    PlanConfig,
    UavDemand,
)
from common.algorithms.flow.placement import local_search, place_flow
from common.algorithms.flow.scoring import (
    flow_meets_utilization,
    predicted_compliance,
    weighted_score,
    weighted_score_with_paths,
)
from common.modeling.flow import FlowKey, flow_requirement, flow_weight
from common.modeling.models import Service

__all__ = [
    # —— 数据模型 ——
    "CapacityState",
    "FlowClass",
    "FlowPlan",
    "PlanConfig",
    "UavDemand",
    # —— 分类 ——
    "classify_flow",
    "per_uav_demand",
    "uav_access_links",
    # —— 候选 ——
    "candidate_paths",
    "normalize_path",
    # —— 评分 ——
    "flow_meets_utilization",
    "predicted_compliance",
    "weighted_score",
    "weighted_score_with_paths",
    # —— 放置 ——
    "local_search",
    "place_flow",
    # —— 主入口 ——
    "plan",
]


def plan(
    flows: dict[FlowKey, list[Service]],
    graph: nx.MultiGraph,
    config: PlanConfig | None = None,
) -> dict[FlowKey, FlowPlan]:
    """为每个 flow 选一条路径；返回 flow_key -> FlowPlan。

    纯函数：同一 `(flows, graph, config)` 必然得到同一结果（无随机性）。
    是否下发由调用方按「修复失效路径 / Δscore ≥ Δmin」决定
    （见 `common/control/dispatch_gate.py`）。
    """
    cfg = config or PlanConfig()
    access = uav_access_links(graph)
    all_services = [s for services in flows.values() for s in services]
    demand = per_uav_demand(all_services)

    # ---- 阶段一：为每条 flow 建计划对象 + 生成候选路径 ----
    # 无任何带 requirement 业务的 flow 直接不参与优化（requirement 为 None）。
    # 候选 = K-最短路径里**静态 QoS 硬过滤**后按链路代价升序的路径；
    # 静态判定的带宽口径是「逐业务漏斗判定」的等价聚合（flow.py 的 max），
    # 不是并发负载的求和（求和在 capacity.py 的容量账本里做）。
    plans: dict[FlowKey, FlowPlan] = {}
    for key, services in flows.items():
        requirement = flow_requirement(services)
        if requirement is None:
            continue
        flow_plan = FlowPlan(
            flow_key=key,
            services=services,
            requirement=requirement,
            weight=flow_weight(services),
            flow_class=classify_flow(services, access, demand),
        )
        flow_plan.candidates = candidate_paths(graph, key, requirement, cfg)
        plans[key] = flow_plan

    # ---- 阶段二：贪心放置（先 test 后背景，边放边记负载）----
    # 容量账本：图 + 每条链路的**单向**容量 + 当前已占方向负载（初始全 0）。
    # 容量取自图上的运行期 bandwidth_bps（来自 get_links()），不是 linkTypes.json 标称值；
    # 仿真器 >1000Mbps 会封顶（sim_src/netsim/sdncommon.py 的 _bw_mbit）。
    state = CapacityState.from_graph(graph)
    # 放置顺序 = 谁能先占位：
    #   1) flow_class.hard 升序 → F3(可行) 先放，F1/F2(物理无解) 最后放；
    #   2) -weight 降序 → 优先级加权高的 test flow 先占（weight=Σ2^priority，只算 test）；
    #   3) 带宽降序 → 同权重时大块先安置，剩下的小块更容易被别的 flow 用上。
    placement_order = sorted(
        plans.values(),
        key=lambda p: (p.flow_class.hard, -p.weight, p.requirement.bandwidth_bps),
    )
    for flow_plan in placement_order:
        # place_flow：F3 test flow 取「第一条方向容量装得下」的候选，都装不下则
        # 退化到最便宜的静态可行路径并打 degraded；F1/F2 与纯背景 flow 走
        # least-contention（挑自身方向利用率最小的，尽量不挤占 test 链路）。
        chosen = place_flow(flow_plan, state, cfg)
        if chosen is None:
            continue          # 连静态可行候选都没有 → 该 flow 不分配路径
        flow_plan.path = chosen
        # 把该 flow 的方向需求（按业务**求和**、按方向记账）累加进账本，
        # 后面的 flow 就自动避开已被占用的链路方向。
        state.add(state.demand(flow_plan.services, chosen, flow_plan.flow_key[0]))

    # ---- 阶段三：局部搜索（hill-climb）----
    # 对预测不达标的 test flow 逐个换候选路径；改一条路径要重算整份负载
    # （recompute），只有优先级加权达标数提升才接受。
    if cfg.enable_local_search:
        local_search(plans, graph, cfg)
    return plans
