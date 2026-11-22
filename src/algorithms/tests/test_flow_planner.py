"""流级规划器单测（F1/F2/F3 分类 + 贪心分配）。"""
import networkx as nx

from algorithms.flow_planner import (
    FlowClass,
    PlanConfig,
    access_links,
    classify_flow,
    per_uav_demand,
    plan,
    plan_score,
)
from math_modeling.flow import group_services_by_flow
from math_modeling.models import Requirement, Service


def _graph():
    g = nx.MultiGraph()
    for nd, t in (("UAV1", "uav"), ("UAV2", "uav"),
                  ("GND1", "ground"), ("GND2", "ground")):
        g.add_node(nd, node_type=t)

    def e(u, v, lid, bw):
        g.add_edge(
            u, v, key=lid, link_id=lid, link_type="microwave",
            delay_ms=1.0, jitter_ms=0.5, bandwidth_bps=bw,
            ber=1e-6, packet_loss_rate=0.0005, delay=1.0,
        )

    e("UAV1", "GND1", "L1", 10_000_000)
    e("UAV2", "GND2", "L2", 10_000_000)
    e("GND1", "GND2", "L3", 100_000_000)
    return g


def _svc(sid, src, dst, bw, pri=4, cat="test"):
    return Service(
        service_id=sid, src_node_id=src, dst_node_id=dst,
        priority=pri, category=cat,
        requirement=Requirement(
            delay_ms=100, jitter_ms=10, bandwidth_bps=bw,
            ber=1e-5, packet_loss_rate=0.01,
        ),
    )


def _classify(graph, services):
    return classify_flow(services, graph, access_links(graph), per_uav_demand(services))


def test_classify_f3():
    g = _graph()
    svcs = [_svc("TSV1", "UAV1", "UAV2", 1_000_000)]
    assert _classify(g, svcs) == FlowClass.F3


def test_classify_f1_test_only_over_capacity():
    g = _graph()
    svcs = [_svc("TSV1", "UAV1", "UAV2", 12_000_000)]
    assert _classify(g, svcs) == FlowClass.F1


def test_classify_f2_background_pushes_over():
    g = _graph()
    svcs = [
        _svc("TSV1", "UAV1", "UAV2", 1_000_000),
        _svc("BGV1", "UAV1", "UAV2", 10_000_000, cat="background"),
    ]
    assert _classify(g, svcs) == FlowClass.F2


def test_plan_assigns_paths_and_weights():
    g = _graph()
    svcs = [
        _svc("TSV1", "UAV1", "UAV2", 1_000_000, pri=8),
        _svc("BGV1", "UAV1", "UAV2", 1_000_000, pri=4, cat="background"),
    ]
    flows = group_services_by_flow(svcs)
    plans = plan(flows, g, PlanConfig(k=5))
    assert len(plans) == 1
    p = next(iter(plans.values()))
    assert p.cls == FlowClass.F3
    assert p.path is not None
    assert p.weight == 2 ** 8


def test_local_search_does_not_decrease_score():
    g = _graph()
    svcs = [
        _svc("TSV1", "UAV1", "UAV2", 1_000_000, pri=8),
        _svc("BGV1", "UAV1", "UAV2", 1_000_000, cat="background"),
    ]
    flows = group_services_by_flow(svcs)
    greedy = plan(flows, g, PlanConfig(k=5, local_search=False))
    improved = plan(flows, g, PlanConfig(k=5, local_search=True))
    assert plan_score(improved, g) >= plan_score(greedy, g)
