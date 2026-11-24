"""Flow 聚合与路径解析测试。"""
from __future__ import annotations

from backend.analysis import build_flows, flow_key_for, parse_path

NODES = [
    {"nodeId": "U1", "ip": "10.0.0.1"},
    {"nodeId": "U2", "ip": "10.0.0.2"},
    {"nodeId": "U3", "ip": "10.0.0.3"},
]
LINKS = [
    {"linkId": "L1", "srcNodeId": "U1", "dstNodeId": "U2"},
    {"linkId": "L2", "srcNodeId": "U2", "dstNodeId": "U3"},
    {"linkId": "L3", "srcNodeId": "U1", "dstNodeId": "U3"},
]


def _svc(sid, src, dst, segments, **kw):
    base = {
        "serviceId": sid,
        "srcNodeId": src,
        "dstNodeId": dst,
        "category": "test",
        "path": {"pathId": "P01001", "segments": [{"type": "link", "id": x} for x in segments]},
        "actual": {"qosMeet": True},
    }
    base.update(kw)
    return base


def test_flow_key_is_direction_agnostic():
    assert flow_key_for("10.0.0.1", "10.0.0.2", "S1") == flow_key_for("10.0.0.2", "10.0.0.1", "S2")
    assert flow_key_for("10.0.0.1", "10.0.0.2", "S1") == "10.0.0.1|10.0.0.2"
    assert flow_key_for(None, "10.0.0.2", "S1") == "unknown:S1"


def test_reverse_services_share_one_flow():
    services = [
        _svc("S1", "U1", "U2", ["L1"]),
        _svc("S2", "U2", "U1", ["L1"], category="background"),
    ]
    flows = build_flows(services, NODES, LINKS)
    assert len(flows) == 1
    flow = flows[0]
    assert flow.flowKey == "10.0.0.1|10.0.0.2"
    assert flow.memberCount == 2
    assert set(flow.memberServiceIds) == {"S1", "S2"}
    assert flow.categoryCounts == {"test": 1, "background": 1}
    assert flow.qosMeetTrue == 2


def test_different_pairs_do_not_merge():
    services = [_svc("S1", "U1", "U2", ["L1"]), _svc("S2", "U1", "U3", ["L3"])]
    flows = build_flows(services, NODES, LINKS)
    assert len(flows) == 2


def test_service_without_ip_goes_to_unknown_flow():
    services = [_svc("S9", "UNKNOWN", "U2", [])]
    flows = build_flows(services, NODES, LINKS)
    assert flows[0].flowKey == "unknown:S9"


def test_path_forward_and_reverse():
    forward = parse_path(
        [{"type": "link", "id": "L1"}, {"type": "link", "id": "L2"}],
        {l["linkId"]: l for l in LINKS},
        "U1",
        "U3",
    )
    assert forward["direction"] == "forward"
    assert forward["continuous"] is True
    assert forward["nodes"] == ["U1", "U2", "U3"]

    reverse = parse_path(
        [{"type": "link", "id": "L2"}, {"type": "link", "id": "L1"}],
        {l["linkId"]: l for l in LINKS},
        "U1",
        "U3",
    )
    assert reverse["direction"] == "reverse"
    assert reverse["nodes"] == ["U1", "U2", "U3"]  # 已按 src→dst 归一
    assert reverse["links"] == ["L1", "L2"]        # 也已归一到 src→dst，direction 标记原始是反的


def test_path_discontinuous_and_missing():
    broken = parse_path(
        [{"type": "link", "id": "L1"}, {"type": "link", "id": "L3"}],
        {l["linkId"]: l for l in LINKS},
        "U1",
        "U3",
    )
    assert broken["continuous"] is False

    missing = parse_path(
        [{"type": "link", "id": "L1"}, {"type": "link", "id": "L9"}],
        {l["linkId"]: l for l in LINKS},
        "U1",
        "U2",
    )
    assert missing["missing"] == ["L9"]
    assert missing["links"] == ["L1"]


def test_empty_path_is_unknown_not_discontinuous():
    parsed = parse_path([], {}, "U1", "U2")
    assert parsed["continuous"] is None
    assert parsed["direction"] is None
