"""方向性容量记账单测。"""
import networkx as nx
import pytest

from common.algorithms.topology.capacity import (
    add_load,
    capacity_map,
    directional_demand,
    fits,
    max_utilization,
    remove_load,
)
from common.modeling.models import Requirement, Service


def _graph():
    g = nx.MultiGraph()
    g.add_node("GND1", node_type="ground")
    g.add_node("UAV1", node_type="uav")
    g.add_edge(
        "UAV1", "GND1", key="L1", link_id="L1", link_type="microwave",
        delay_ms=1.0, jitter_ms=1.0, bandwidth_bps=10_000_000,
        ber=1e-6, packet_loss_rate=0.001, delay=1.0,
    )
    return g


def _svc(sid, src, dst, bw):
    return Service(
        service_id=sid, src_node_id=src, dst_node_id=dst,
        requirement=Requirement(
            delay_ms=100, jitter_ms=10, bandwidth_bps=bw,
            ber=1e-5, packet_loss_rate=0.01,
        ),
    )


def test_capacity_map():
    assert capacity_map(_graph()) == {"L1": 10_000_000}


def test_directional_demand_opposite_signs():
    g = _graph()
    fwd = directional_demand("UAV1", [_svc("A", "UAV1", "GND1", 4_000_000)], ["L1"], g)
    rev = directional_demand("UAV1", [_svc("B", "GND1", "UAV1", 4_000_000)], ["L1"], g)
    assert set(fwd) != set(rev)          # 方向相反 → sign 相反
    assert list(fwd.values()) == [4_000_000]
    assert list(rev.values()) == [4_000_000]


def test_directional_demand_sums_same_flow_services():
    """口径锁定：同一 flow 的多条业务在**同向**上负载相加（sum）。

    与 `flow.py` 的 flow 需求聚合（max，逐业务漏斗判定）是两层口径，勿混用。
    """
    g = _graph()
    demand = directional_demand(
        "UAV1",
        [_svc("A", "UAV1", "GND1", 4_000_000), _svc("B", "UAV1", "GND1", 3_000_000)],
        ["L1"], g,
    )
    assert list(demand.values()) == [7_000_000]      # 4M + 3M，同向累加


def test_directional_demand_opposite_direction_not_added():
    """反向业务走另一个方向的桶，不与正向负载相加（跨方向求和无物理意义）。"""
    g = _graph()
    demand = directional_demand(
        "UAV1",
        [_svc("A", "UAV1", "GND1", 4_000_000), _svc("B", "GND1", "UAV1", 3_000_000)],
        ["L1"], g,
    )
    assert sorted(demand.values()) == [3_000_000, 4_000_000]   # 两个方向各一桶


def test_fits_boundary_and_overload():
    g = _graph()
    cap = capacity_map(g)
    load: dict = {}
    d1 = directional_demand("UAV1", [_svc("A", "UAV1", "GND1", 4_000_000)], ["L1"], g)
    d2 = directional_demand("UAV1", [_svc("B", "UAV1", "GND1", 4_000_000)], ["L1"], g)
    add_load(load, d1)
    assert fits(d2, load, cap, rho=0.2)          # 8M == 10M*0.8 边界
    add_load(load, d2)
    d3 = directional_demand("UAV1", [_svc("C", "UAV1", "GND1", 5_000_000)], ["L1"], g)
    assert not fits(d3, load, cap, rho=0.2)      # 4M+5M=9M > 8M
    remove_load(load, d2)
    assert fits(d2, load, cap, rho=0.2)


def test_max_utilization():
    g = _graph()
    cap = capacity_map(g)
    load: dict = {}
    add_load(
        load,
        directional_demand("UAV1", [_svc("A", "UAV1", "GND1", 5_000_000)], ["L1"], g),
    )
    assert max_utilization(load, cap) == pytest.approx(0.5)
