"""静态 QoS 合成公式单测（对手算值）。"""
import pytest
import networkx as nx

from common.modeling.models import LinkParams
from common.modeling.path_qos import compose_from_params, compose_qos


def _p(d=0.0, j=0.0, b=0, ber=0.0, loss=0.0):
    return LinkParams(delay_ms=d, jitter_ms=j, bandwidth_bps=b, ber=ber, packet_loss_rate=loss)


def test_single_link_identity():
    q = compose_from_params([_p(d=10.0, j=3.0, b=8_000_000, ber=1e-4, loss=0.02)])
    assert q.delay_ms == 10.0
    assert q.jitter_ms == 3.0
    assert q.bandwidth_bps == 8_000_000
    assert q.ber == pytest.approx(1e-4)
    assert q.packet_loss_rate == pytest.approx(0.02)


def test_two_links_composition():
    q = compose_from_params([
        _p(d=10.0, j=3.0, b=8_000_000, ber=1e-4, loss=0.02),
        _p(d=5.0, j=4.0, b=6_000_000, ber=2e-4, loss=0.01),
    ])
    assert q.delay_ms == 15.0
    assert q.jitter_ms == pytest.approx(5.0)          # sqrt(3² + 4²)
    assert q.bandwidth_bps == 6_000_000               # min(8M, 6M)
    assert q.ber == pytest.approx(3e-4)               # 1e-4 + 2e-4
    # 丢包 = 1 - (1-0.02)(1-0.01) = 1 - 0.9702 = 0.0298
    assert q.packet_loss_rate == pytest.approx(0.0298)


def test_empty_params():
    q = compose_from_params([])
    assert q.delay_ms == 0.0
    assert q.jitter_ms == 0.0
    assert q.bandwidth_bps == 0
    assert q.packet_loss_rate == 0.0


def test_compose_qos_from_graph():
    G = nx.MultiGraph()
    G.add_edge("A", "B", key="L1", link_type="microwave",
               delay_ms=10.0, jitter_ms=3.0, bandwidth_bps=8_000_000,
               ber=1e-4, packet_loss_rate=0.02)
    G.add_edge("B", "C", key="L2", link_type="microwave",
               delay_ms=5.0, jitter_ms=4.0, bandwidth_bps=6_000_000,
               ber=2e-4, packet_loss_rate=0.01)
    q = compose_qos(["L1", "L2"], G)
    assert q.delay_ms == 15.0
    assert q.bandwidth_bps == 6_000_000


def test_compose_qos_missing_link_raises():
    G = nx.MultiGraph()
    with pytest.raises(KeyError):
        compose_qos(["L404"], G)
