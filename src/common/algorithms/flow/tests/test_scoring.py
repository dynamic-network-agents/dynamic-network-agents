"""评分与达标判定单测（`flow_scoring.py`）。"""
import networkx as nx

from common.algorithms.flow.models import CapacityState, FlowClass, FlowPlan, PlanConfig
from common.algorithms.flow.scoring import (
    flow_meets_utilization,
    predicted_compliance,
    score_with_state,
    weighted_score,
    weighted_score_with_paths,
)
from common.modeling.flow import group_services_by_flow
from common.modeling.models import Requirement, Service


def _chain_graph(alt_bw=10_000_000):
    """UAV1—L1—GND1—L2—GND2—L3—UAV2，另有一条较慢的备路径 L4/L5。"""
    g = nx.MultiGraph()
    for nd, t in (("UAV1", "uav"), ("UAV2", "uav"),
                  ("GND1", "ground"), ("GND2", "ground"), ("GND3", "ground")):
        g.add_node(nd, node_type=t)

    def e(u, v, lid, delay, bw=10_000_000):
        g.add_edge(
            u, v, key=lid, link_id=lid, link_type="microwave",
            delay_ms=delay, jitter_ms=0.5, bandwidth_bps=bw,
            ber=1e-6, packet_loss_rate=0.0005, delay=delay,
        )

    e("UAV1", "GND1", "L1", 1.0)
    e("GND1", "GND2", "L2", 1.0)
    e("GND2", "UAV2", "L3", 1.0)
    e("UAV1", "GND3", "L4", 2.0, alt_bw)
    e("GND3", "GND2", "L5", 2.0, alt_bw)
    return g


def _svc(sid, src, dst, bw, pri=6, cat="test"):
    return Service(
        service_id=sid, src_node_id=src, dst_node_id=dst,
        priority=pri, category=cat,
        requirement=Requirement(
            delay_ms=100, jitter_ms=10, bandwidth_bps=bw,
            ber=1e-5, packet_loss_rate=0.01,
        ),
    )


def _plans_for(graph, services):
    """手工造一个 flow 计划（不依赖 plan()，隔离评分逻辑）。"""
    flows = group_services_by_flow(services)
    key = next(iter(flows))
    svcs = flows[key]
    return {
        key: FlowPlan(
            flow_key=key, services=svcs, requirement=svcs[0].requirement,
            weight=2 ** svcs[0].priority, flow_class=FlowClass.F3,
            candidates=[], path=["L1", "L2", "L3"],
        ),
    }


def test_weighted_score_with_paths_handles_missing_and_broken():
    g = _chain_graph()
    plans = _plans_for(g, [_svc("TSV1", "UAV1", "UAV2", 1_000_000)])
    key = ("UAV1", "UAV2")
    assert weighted_score_with_paths(plans, g, {key: ["L1", "L2", "L3"]}) == 64.0
    assert weighted_score_with_paths(plans, g, {key: None}) == 0.0
    assert weighted_score_with_paths(plans, g, {key: ["L1", "L3"]}) == 0.0   # 断链 → 不计
    assert plans[key].path is not None              # 原计划未被污染


def test_weighted_score_counts_weight_of_compliant_flows():
    g = _chain_graph()
    plans = _plans_for(g, [_svc("TSV1", "UAV1", "UAV2", 1_000_000)])
    assert weighted_score(plans, g) == 64.0


def test_hard_flow_and_background_flow_contribute_no_score():
    """F1/F2 与纯背景 flow 不计入加权达标数。"""
    g = _chain_graph()
    plans = _plans_for(g, [_svc("TSV1", "UAV1", "UAV2", 1_000_000)])
    key = next(iter(plans))
    plans[key].flow_class = FlowClass.F1
    assert weighted_score(plans, g) == 0.0

    plans[key].flow_class = FlowClass.F3
    plans[key].weight = 0.0        # 纯背景
    assert weighted_score(plans, g) == 0.0


def test_predicted_compliance_reports_per_flow():
    g = _chain_graph()
    plans = _plans_for(g, [_svc("TSV1", "UAV1", "UAV2", 1_000_000)])
    assert predicted_compliance(plans, g) == {("UAV1", "UAV2"): True}


def test_flow_meets_utilization_respects_limit():
    """利用率超过阈值即判不达标（阈值与摆放裕度是两个独立参数）。"""
    g = _chain_graph()
    plans = _plans_for(g, [_svc("TSV1", "UAV1", "UAV2", 1_000_000)])
    key = next(iter(plans))
    state = CapacityState.from_graph(g)
    state.load = state.recompute(plans)
    assert flow_meets_utilization(plans[key], state, 1.0) is True
    assert flow_meets_utilization(plans[key], state, 0.0) is False


def test_flow_without_path_never_meets():
    g = _chain_graph()
    plans = _plans_for(g, [_svc("TSV1", "UAV1", "UAV2", 1_000_000)])
    key = next(iter(plans))
    plans[key].path = None
    state = CapacityState.from_graph(g)
    assert flow_meets_utilization(plans[key], state, 1.0) is False


def test_score_with_state_uses_given_load():
    """`score_with_state` 读账本里的负载，不自己重算。

    同一份计划：账本负载为空 → 利用率 0 → 达标；负载按计划重算后 →
    利用率 = 1M/10M = 0.1，仍达标。
    """
    g = _chain_graph()
    plans = _plans_for(g, [_svc("TSV1", "UAV1", "UAV2", 1_000_000)])
    state = CapacityState.from_graph(g)
    assert score_with_state(plans, state, 1.0) == 64.0

    state.load = state.recompute(plans)
    assert score_with_state(plans, state, 1.0) == 64.0

    # 把利用率阈值压到 0.05（低于实际的 0.1）→ 不再达标
    assert score_with_state(plans, state, 0.05) == 0.0
