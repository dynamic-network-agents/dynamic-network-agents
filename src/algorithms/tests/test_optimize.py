"""单 flow 优化单测：QoS 过滤 + 代价排序。"""
import networkx as nx

from math_modeling.models import Requirement
from algorithms.optimize import optimize_flow


def _req(d=100.0, j=50.0, b=1_000_000, ber=1e-4, loss=0.01):
    return Requirement(delay_ms=d, jitter_ms=j, bandwidth_bps=b, ber=ber, packet_loss_rate=loss)


def _graph():
    # s-a-t 可行（低时延微波），s-b-t 违约（高时延卫通）
    G = nx.MultiGraph()
    G.add_edge("s", "a", key="L1", link_type="microwave", delay_ms=10.0, jitter_ms=1.0,
               bandwidth_bps=8_000_000, ber=1e-6, packet_loss_rate=0.001, delay=10.0)
    G.add_edge("a", "t", key="L2", link_type="microwave", delay_ms=10.0, jitter_ms=1.0,
               bandwidth_bps=8_000_000, ber=1e-6, packet_loss_rate=0.001, delay=10.0)
    G.add_edge("s", "b", key="L3", link_type="satcom", delay_ms=300.0, jitter_ms=100.0,
               bandwidth_bps=100_000, ber=1e-3, packet_loss_rate=0.05, delay=300.0)
    G.add_edge("b", "t", key="L4", link_type="satcom", delay_ms=300.0, jitter_ms=100.0,
               bandwidth_bps=100_000, ber=1e-3, packet_loss_rate=0.05, delay=300.0)
    return G


def test_optimize_picks_feasible():
    link_ids = optimize_flow(_graph(), "s", "t", _req(), k=10)
    assert link_ids == ["L1", "L2"]  # s-b-t 时延 600ms 违约


def test_optimize_no_feasible():
    req = Requirement(delay_ms=5.0, jitter_ms=0.1, bandwidth_bps=100_000_000,
                      ber=1e-12, packet_loss_rate=1e-6)
    assert optimize_flow(_graph(), "s", "t", req, k=10) is None


def test_optimize_unreachable():
    G = nx.MultiGraph()
    G.add_node("s")
    G.add_node("t")
    assert optimize_flow(G, "s", "t", _req(), k=10) is None
