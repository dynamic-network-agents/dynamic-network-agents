"""静态 QoS 合成与链路需求侧负载测试。"""
from __future__ import annotations

import math

import pytest

from backend.analysis import build_flows, build_link_loads, check_static, compose_qos


def _link(lid, d, j, b, loss, ber):
    return {
        "linkId": lid,
        "srcNodeId": "A",
        "dstNodeId": "B",
        "params": {
            "delayMs": d,
            "jitterMs": j,
            "bandwidthBps": b,
            "packetLossRate": loss,
            "ber": ber,
        },
    }


def test_compose_formulas():
    qos = compose_qos([_link("L1", 5, 3, 1e6, 0.01, 1e-5), _link("L2", 7, 4, 5e5, 0.02, 2e-5)])
    assert qos["linkCount"] == 2
    assert qos["delayMs"] == 12
    assert qos["jitterMs"] == pytest.approx(5.0)  # sqrt(3²+4²)
    assert qos["bandwidthBps"] == 5e5           # min
    assert qos["packetLossRate"] == pytest.approx(1 - 0.99 * 0.98)
    assert qos["ber"] == pytest.approx(3e-5)
    assert qos["missingParams"] == []


def test_compose_marks_missing_params():
    link = _link("L1", 5, 3, 1e6, 0.01, 1e-5)
    del link["params"]["jitterMs"]
    qos = compose_qos([link])
    assert qos["jitterMs"] is None
    assert "jitterMs" in qos["missingParams"]


def test_compose_empty_links():
    qos = compose_qos([])
    assert qos["linkCount"] == 0
    assert "no-links" in qos["missingParams"]


def test_check_static_pass_with_tolerance():
    qos = compose_qos([_link("L1", 340, 15, 1e6, 0.03, 1e-5)])
    chk = check_static(qos, {"delayMs": 339, "jitterMs": 15, "bandwidthBps": 1e6,
                             "packetLossRate": 0.03, "ber": 1e-5})
    # 时延允许 +1.0：340 <= 339+1.0
    assert chk["ok"] is True
    assert chk["violations"] == []


def test_check_static_delay_violation():
    qos = compose_qos([_link("L1", 341, 15, 1e6, 0.03, 1e-5)])
    chk = check_static(qos, {"delayMs": 339, "jitterMs": 15, "bandwidthBps": 1e6,
                             "packetLossRate": 0.03, "ber": 1e-5})
    assert chk["ok"] is False
    assert any("delayMs" in v for v in chk["violations"])


def test_check_static_bandwidth_has_no_tolerance():
    qos = compose_qos([_link("L1", 1, 1, 999_999, 0, 0)])
    chk = check_static(qos, {"bandwidthBps": 1_000_000})
    assert chk["ok"] is False


def test_check_static_unknown_when_no_requirement_or_missing():
    qos = compose_qos([_link("L1", 1, 1, 1e6, 0, 0)])
    assert check_static(qos, None)["ok"] is None

    partial = compose_qos([_link("L1", 1, 1, 1e6, 0, 0)])
    partial["ber"] = None
    chk = check_static(partial, {"ber": 1e-6})
    assert chk["ok"] is None


def test_link_load_aggregates_shared_flows():
    links = [
        _link("L1", 1, 1, 1e6, 0, 0),
        _link("L2", 1, 1, 2e6, 0, 0),
    ]
    nodes = [{"nodeId": "U1", "ip": "10.0.0.1"}, {"nodeId": "U2", "ip": "10.0.0.2"},
             {"nodeId": "U3", "ip": "10.0.0.3"}]
    services = [
        {"serviceId": "S1", "srcNodeId": "U1", "dstNodeId": "U2",
         "requirement": {"bandwidthBps": 4e5}, "actual": {"effBwBps": 4.1e5},
         "path": {"segments": [{"type": "link", "id": "L1"}]}},
        {"serviceId": "S2", "srcNodeId": "U1", "dstNodeId": "U2",
         "requirement": {"bandwidthBps": 2e5}, "actual": {"effBwBps": 2.1e5},
         "path": {"segments": [{"type": "link", "id": "L1"}]}},
        {"serviceId": "S3", "srcNodeId": "U2", "dstNodeId": "U3",
         "requirement": {"bandwidthBps": 1e6}, "actual": {"effBwBps": 1e6},
         "path": {"segments": [{"type": "link", "id": "L2"}]}},
    ]
    flows = build_flows(services, nodes, links)
    loads = {x["linkId"]: x for x in build_link_loads(links, flows, services)}

    l1 = loads["L1"]
    assert l1["flowCount"] == 1
    assert l1["serviceCount"] == 2
    assert l1["demandBps"] == pytest.approx(6e5)
    assert l1["demandUtilization"] == pytest.approx(0.6)
    assert l1["measuredBps"] == pytest.approx(6.2e5)
    assert l1["measuredIsEstimate"] is True

    assert loads["L2"]["demandUtilization"] == pytest.approx(0.5)


def test_link_load_capacity_missing_gives_none_utilization():
    links = [{"linkId": "L1", "srcNodeId": "A", "dstNodeId": "B", "params": {}}]
    loads = build_link_loads(links, [], [])
    assert loads[0]["capacityBps"] is None
    assert loads[0]["demandUtilization"] is None
