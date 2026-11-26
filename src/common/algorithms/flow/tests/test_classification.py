"""F1/F2/F3 分类单测（`flow_classification.py`）。"""
import networkx as nx

from common.algorithms.flow.classification import (
    classify_flow,
    per_uav_demand,
    uav_access_links,
)
from common.algorithms.flow.models import FlowClass
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


def _classify(graph, services):
    return classify_flow(services, uav_access_links(graph), per_uav_demand(services))


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


def test_access_links_pick_widest_adjacent_link():
    """一个 UAV 有多条接入链路时取最粗那条（判 F1/F2 的乐观上界口径）。"""
    g = _graph()
    g.add_edge("UAV1", "GND2", key="L9", link_id="L9", link_type="microwave",
                delay_ms=1.0, jitter_ms=0.5, bandwidth_bps=50_000_000,
                ber=1e-6, packet_loss_rate=0.0005, delay=1.0)
    access = uav_access_links(g)
    assert access["UAV1"] == ("L9", 50_000_000)
    assert access["UAV2"] == ("L2", 10_000_000)


def test_per_uav_demand_splits_test_only_and_all():
    """test-only 与 test+bg 两档需求分开统计；无需求的业务不计入。"""
    svcs = [
        _svc("TSV1", "UAV1", "UAV2", 1_000_000),      # UAV1 出向 / UAV2 入向
        _svc("BGV1", "UAV1", "UAV2", 2_000_000, cat="background"),
        _svc("TSV2", "UAV2", "UAV1", 3_000_000),      # UAV2 出向 / UAV1 入向
    ]
    demand = per_uav_demand(svcs)
    # 出向：UAV1 只有 TSV1 的 1M（test-only）；UAV2 有 TSV2 的 3M
    assert demand.out_test_only["UAV1"] == 1_000_000
    assert demand.out_all["UAV1"] == 3_000_000       # TSV1 1M + BGV1 2M
    assert demand.out_test_only["UAV2"] == 3_000_000
    assert demand.out_all["UAV2"] == 3_000_000
    # 入向：UAV2 有 TSV1 的 1M + BGV1 的 2M；UAV1 有 TSV2 的 3M
    assert demand.in_test_only["UAV2"] == 1_000_000
    assert demand.in_all["UAV2"] == 3_000_000
    assert demand.in_test_only["UAV1"] == 3_000_000
    assert demand.in_all["UAV1"] == 3_000_000
    # 缺键返回 0（defaultdict 口径）
    assert demand.out_test_only["UAV3"] == 0
