"""规划器门面与编排单测（`flow_planner.py`）：`plan()` 的端到端行为。"""
import networkx as nx

from common.algorithms.flow.models import FlowClass, PlanConfig
from common.algorithms.flow.planner import plan, weighted_score
from common.modeling.flow import group_services_by_flow
from common.modeling.models import Requirement, Service


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


def test_plan_assigns_paths_and_weights():
    g = _graph()
    svcs = [
        _svc("TSV1", "UAV1", "UAV2", 1_000_000, pri=8),
        _svc("BGV1", "UAV1", "UAV2", 1_000_000, pri=4, cat="background"),
    ]
    flows = group_services_by_flow(svcs)
    plans = plan(flows, g, PlanConfig(candidate_path_count=5))
    assert len(plans) == 1
    p = next(iter(plans.values()))
    assert p.flow_class == FlowClass.F3
    assert p.path is not None
    assert p.weight == 2 ** 8


def test_local_search_does_not_decrease_score():
    g = _graph()
    svcs = [
        _svc("TSV1", "UAV1", "UAV2", 1_000_000, pri=8),
        _svc("BGV1", "UAV1", "UAV2", 1_000_000, cat="background"),
    ]
    flows = group_services_by_flow(svcs)
    greedy = plan(flows, g, PlanConfig(candidate_path_count=5, enable_local_search=False))
    improved = plan(flows, g, PlanConfig(candidate_path_count=5, enable_local_search=True))
    assert weighted_score(improved, g) >= weighted_score(greedy, g)


def test_plan_is_pure_same_input_same_output():
    """规划器是纯函数：同一快照重算两次结果完全一致（闭环不动点的依据）。"""
    g = _graph()
    svcs = [_svc("TSV1", "UAV1", "UAV2", 1_000_000, pri=8)]
    flows = group_services_by_flow(svcs)
    config = PlanConfig(candidate_path_count=5)
    first = plan(flows, g, config)
    again = plan(flows, g, config)
    assert {k: p.path for k, p in first.items()} == {k: p.path for k, p in again.items()}


def test_plan_skips_flow_without_requirement():
    """无任何带 requirement 的业务时该 flow 不参与优化。"""
    g = _graph()
    svcs = [Service(
        service_id="TSV1", src_node_id="UAV1", dst_node_id="UAV2",
        priority=4, category="test", requirement=None,
    )]
    flows = group_services_by_flow(svcs)
    assert plan(flows, g, PlanConfig(candidate_path_count=5)) == {}
