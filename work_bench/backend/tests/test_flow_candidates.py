"""候选路径静态可行性测试（纯函数，不连仿真器）。"""
from __future__ import annotations

from backend.analysis.candidates import build_flow_candidates


def _link(link_id: str, delay=10.0, bw=1e8, loss=0.0, jitter=1.0, ber=1e-6) -> dict:
    return {
        "linkId": link_id,
        "srcNodeId": "A",
        "dstNodeId": "B",
        "status": "up",
        "params": {
            "delayMs": delay,
            "jitterMs": jitter,
            "bandwidthBps": bw,
            "packetLossRate": loss,
            "ber": ber,
        },
    }


LINKS = [
    _link("L1", delay=10.0, bw=1e8),
    _link("L2", delay=20.0, bw=5e7),
    _link("L3", delay=30.0, bw=2e7),
]

FLOW = {"flowKey": "10.0.0.1|10.0.0.2", "memberServiceIds": ["S1", "S2"], "links": ["L1", "L2"]}

SERVICES = [
    {
        "serviceId": "S1",
        "requirement": {"delayMs": 40, "bandwidthBps": 1e7, "packetLossRate": 0.05, "ber": 1e-3},
    },
    {
        "serviceId": "S2",
        "requirement": {"delayMs": 20, "bandwidthBps": 1e7, "packetLossRate": 0.05, "ber": 1e-3},
    },
]

# S1/S2 走同一条候选 → 应去重成一条
PATHS = {
    "S1": [{"pathNo": 1, "nodes": ["A", "B"], "links": ["L1", "L2"]}],
    "S2": [{"pathNo": 1, "nodes": ["A", "B"], "links": ["L1", "L2"]}],
}


def test_candidates_are_deduped_across_members():
    out = build_flow_candidates(FLOW, SERVICES, LINKS, PATHS)
    assert len(out["candidates"]) == 1
    cand = out["candidates"][0]
    assert cand["serviceIds"] == ["S1", "S2"]
    assert out["memberCount"] == 2


def test_static_qos_composed_from_current_link_params():
    out = build_flow_candidates(FLOW, SERVICES, LINKS, PATHS)
    qos = out["candidates"][0]["staticQoS"]
    assert qos["linkCount"] == 2
    assert qos["delayMs"] == 30.0  # 10 + 20
    assert qos["bandwidthBps"] == 5e7  # min(1e8, 5e7)
    assert qos["ber"] == 2e-6
    assert qos["missingParams"] == []


def test_per_member_checks_can_disagree():
    out = build_flow_candidates(FLOW, SERVICES, LINKS, PATHS)
    cand = out["candidates"][0]
    # 时延 30ms：S1 上限 40 → 可行；S2 上限 20 → 不可行
    by_member = {m["serviceId"]: m for m in cand["perMember"]}
    assert by_member["S1"]["ok"] is True
    assert by_member["S2"]["ok"] is False
    assert cand["checks"] == {"ok": 1, "fail": 1, "unknown": 0}


def test_current_path_is_marked_and_sorted_first():
    # S1 的当前路径是 L1+L2（顺序无关）
    out = build_flow_candidates(
        {**FLOW, "links": ["L2", "L1"]},
        SERVICES,
        LINKS,
        {**PATHS, "S1": PATHS["S1"] + [{"pathNo": 2, "nodes": [], "links": ["L3"]}]},
    )
    first = out["candidates"][0]
    assert first["isCurrent"] is True
    assert first["links"] == ["L1", "L2"]


def test_missing_link_disables_partial_composition():
    out = build_flow_candidates(
        FLOW,
        SERVICES,
        LINKS,
        {"S1": [{"pathNo": 9, "nodes": [], "links": ["L1", "L999"]}]},
    )
    cand = out["candidates"][0]
    assert cand["staticQoS"] is None
    assert cand["missingLinks"] == ["L999"]
    assert cand["checks"] == {"ok": 0, "fail": 0, "unknown": 1}
    assert "L999" in cand["perMember"][0]["violations"][0]


def test_incomplete_data_counts_as_unknown():
    links_without_params = [{k: v for k, v in _link("L1").items() if k != "params"}]
    out = build_flow_candidates(
        {"flowKey": "f", "memberServiceIds": ["S1"], "links": ["L1"]},
        SERVICES,
        links_without_params,
        {"S1": [{"pathNo": 1, "nodes": [], "links": ["L1"]}]},
    )
    cand = out["candidates"][0]
    assert cand["staticQoS"]["missingParams"]
    assert cand["checks"]["unknown"] == 1


def test_note_when_candidate_file_missing():
    out = build_flow_candidates(FLOW, SERVICES, LINKS, {})
    assert out["candidates"] == []
    assert "未加载离线候选路径" in out["note"]


def test_note_when_flow_has_no_candidate_records():
    out = build_flow_candidates(FLOW, SERVICES, LINKS, {"OTHER": []})
    assert out["candidates"] == []
    assert "没有候选路径记录" in out["note"]


def test_candidate_ids_are_stable():
    out = build_flow_candidates(FLOW, SERVICES, LINKS, PATHS)
    assert out["candidates"][0]["candidateId"] == "C01"
