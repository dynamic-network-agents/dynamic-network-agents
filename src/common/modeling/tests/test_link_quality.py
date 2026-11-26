"""链路代价模型单测（归一化单调性 + 区间）。"""
from common.modeling.models import Link, LinkParams
from common.modeling.link_quality import link_cost


def _link(delay=10.0, bw=8_000_000):
    return Link(
        link_id="L1", link_type="microwave", src_node_id="A", dst_node_id="B",
        status="up",
        params=LinkParams(delay_ms=delay, jitter_ms=5.0, bandwidth_bps=bw,
                          ber=1e-5, packet_loss_rate=0.01),
    )


def test_cost_in_unit_interval():
    assert 0.0 <= link_cost(_link()) <= 1.0


def test_delay_monotonic_increasing():
    # 时延越大代价越高
    assert link_cost(_link(delay=1.0)) < link_cost(_link(delay=20.0))


def test_bandwidth_monotonic_decreasing():
    # 带宽越大代价越低
    assert link_cost(_link(bw=32_000_000)) < link_cost(_link(bw=2_000_000))


def test_unknown_type_max_cost():
    l = _link()
    l.link_type = "unknown"
    assert link_cost(l) == 1.0


def test_missing_params_max_cost():
    l = _link()
    l.params = None
    assert link_cost(l) == 1.0
