"""flow 分组与需求交集单测。"""
from math_modeling.models import Requirement, Service
from math_modeling.flow import flow_requirement, group_services_by_flow


def _svc(sid, src, dst, req=None):
    return Service(service_id=sid, src_node_id=src, dst_node_id=dst, requirement=req)


def test_group_services_by_flow():
    svcs = [_svc("A", "UAV1", "UAV2"), _svc("B", "UAV1", "UAV2"), _svc("C", "UAV2", "UAV1")]
    groups = group_services_by_flow(svcs)
    assert len(groups) == 2
    assert len(groups[("UAV1", "UAV2")]) == 2
    assert len(groups[("UAV2", "UAV1")]) == 1


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


def test_flow_requirement_ignores_missing_requirement():
    r1 = Requirement(delay_ms=150, jitter_ms=30, bandwidth_bps=2_000_000,
                     ber=1e-4, packet_loss_rate=0.05)
    rf = flow_requirement([_svc("A", "UAV1", "UAV2", r1), _svc("B", "UAV1", "UAV2")])
    assert rf.delay_ms == 150


def test_flow_requirement_empty():
    assert flow_requirement([]) is None
    assert flow_requirement([_svc("A", "UAV1", "UAV2")]) is None
