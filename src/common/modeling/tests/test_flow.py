"""flow 分组与需求交集单测。"""
from common.modeling.models import Requirement, Service
from common.modeling.flow import (
    flow_requirement,
    flow_weight,
    group_services_by_flow,
    service_is_test,
)


def _svc(sid, src, dst, req=None, category="", priority=4):
    return Service(
        service_id=sid,
        src_node_id=src,
        dst_node_id=dst,
        requirement=req,
        category=category,
        priority=priority,
    )


def test_group_services_by_flow_merges_opposite_directions():
    """A→B 与 B→A 是同一个无序 flow（对齐仿真器 _flow_for）。"""
    svcs = [
        _svc("A", "UAV1", "UAV2"),
        _svc("B", "UAV1", "UAV2"),
        _svc("C", "UAV2", "UAV1"),
    ]
    groups = group_services_by_flow(svcs)
    assert len(groups) == 1
    assert len(groups[("UAV1", "UAV2")]) == 3


def test_flow_requirement_intersection():
    r1 = Requirement(delay_ms=150, jitter_ms=30, bandwidth_bps=2_000_000,
                     ber=1e-4, packet_loss_rate=0.05)
    r2 = Requirement(delay_ms=100, jitter_ms=20, bandwidth_bps=3_000_000,
                     ber=1e-5, packet_loss_rate=0.03)
    rf = flow_requirement([_svc("A", "UAV1", "UAV2", r1), _svc("B", "UAV1", "UAV2", r2)])
    assert rf.delay_ms == 100            # min
    assert rf.jitter_ms == 20            # min
    assert rf.bandwidth_bps == 3_000_000  # max
    assert rf.ber == 1e-5                # min
    assert rf.packet_loss_rate == 0.03   # min


def test_flow_requirement_bandwidth_uses_max_not_sum():
    """口径锁定：flow 级带宽取 max（逐业务漏斗判定），**不是** sum。

    sum 属于并发负载口径，在 `common/algorithms/topology/capacity.py` 的
    `directional_demand` 里按方向累加。本用例防止有人把 max「改成 sum」。
    """
    r1 = Requirement(delay_ms=150, jitter_ms=30, bandwidth_bps=4_000_000,
                     ber=1e-4, packet_loss_rate=0.05)
    r2 = Requirement(delay_ms=100, jitter_ms=20, bandwidth_bps=6_000_000,
                     ber=1e-5, packet_loss_rate=0.03)
    svcs = [_svc("A", "UAV1", "UAV2", r1), _svc("B", "UAV2", "UAV1", r2)]
    rf = flow_requirement(svcs)
    assert rf.bandwidth_bps == 6_000_000            # max
    assert rf.bandwidth_bps != 10_000_000           # 不是 sum
    # 其余维度仍取最严（min）
    assert rf.delay_ms == 100
    assert rf.ber == 1e-5


def test_flow_requirement_ignores_missing_requirement():
    r1 = Requirement(delay_ms=150, jitter_ms=30, bandwidth_bps=2_000_000,
                     ber=1e-4, packet_loss_rate=0.05)
    rf = flow_requirement([_svc("A", "UAV1", "UAV2", r1), _svc("B", "UAV1", "UAV2")])
    assert rf.delay_ms == 150


def test_flow_requirement_empty():
    assert flow_requirement([]) is None
    assert flow_requirement([_svc("A", "UAV1", "UAV2")]) is None


def test_service_is_test_category_and_prefix():
    assert service_is_test(_svc("X", "UAV1", "UAV2", category="test"))
    assert not service_is_test(_svc("X", "UAV1", "UAV2", category="background"))
    # category 缺失 → 前缀兜底（仅当前场景库）
    assert service_is_test(_svc("TSV0001", "UAV1", "UAV2", category=""))
    assert not service_is_test(_svc("BGV0001", "UAV1", "UAV2", category=""))


def test_flow_weight_only_test():
    test_svc = _svc("TSV1", "UAV1", "UAV2", category="test", priority=8)
    bg_svc = _svc("BGV1", "UAV1", "UAV2", category="background", priority=8)
    assert flow_weight([test_svc, bg_svc]) == 2 ** 8
    assert flow_weight([bg_svc]) == 0.0
