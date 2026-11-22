"""方向性容量记账单测。"""
import networkx as nx
import pytest

from algorithms.capacity import (
    add_load,
    capacity_map,
    directional_demand,
    fits,
    max_utilization,
    remove_load,
)
from math_modeling.models import Requirement, Service


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
