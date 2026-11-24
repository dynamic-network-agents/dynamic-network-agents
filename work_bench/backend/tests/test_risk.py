"""风险链路（规则 A）与整体状态（规则 B）单元测试。

口径来源：`docs/work_bench/B03_Network_Workbench_UI_可行性分析.md` §8。
规则是纯函数，这里只用固定样例驱动，不连仿真器。
"""
from __future__ import annotations

from backend.analysis.risk import (
    build_link_risks,
    build_overall_status,
    build_risk_summary,
)
from backend.models import Link, LinkLoad


def _link(link_id="L1", status="up", delay=10.0, loss=0.0, bw=1e8):
    return {
        "linkId": link_id,
        "status": status,
        "params": {"delayMs": delay, "packetLossRate": loss, "bandwidthBps": bw},
    }


def _load(link_id="L1", util=None, capacity=1e8, demand=0.0):
    return {
        "linkId": link_id,
        "demandUtilization": util,
        "capacityBps": capacity,
        "demandBps": demand,
    }


# ---------------------------------------------------------------- 规则 A
def test_no_risk_when_link_healthy():
    risks = build_link_risks([_link()], [_load(util=0.4)], [])
    assert risks == []


def test_down_link_is_r1():
    risks = build_link_risks([_link(status="down")], [_load(util=0.1)], [])
    assert len(risks) == 1
    assert risks[0]["codes"] == ["R1"]
    assert risks[0]["severity"] == "R1"
    assert risks[0]["isEstimated"] is False


def test_over_subscription_is_r2_and_marked_estimated():
    risks = build_link_risks([_link()], [_load(util=1.5)], [])
    assert risks[0]["codes"] == ["R2"]
    assert risks[0]["isEstimated"] is True
    assert "估算" in risks[0]["reasons"][0]


def test_over_subscription_requires_positive_capacity():
    # 容量未知/为 0 时不能算"超订"，否则会把缺参当成 100% 超载
    risks = build_link_risks([_link()], [_load(util=1.5, capacity=0)], [])
    assert risks == []


def test_delay_rise_is_r3():
    prev = [_link(delay=10.0)]
    risks = build_link_risks([_link(delay=16.0)], [_load(util=0.1)], prev)
    assert risks[0]["codes"] == ["R3"]
    assert risks[0]["severity"] == "R3"


def test_small_delay_rise_is_not_r3():
    risks = build_link_risks([_link(delay=14.0)], [_load(util=0.1)], [_link(delay=10.0)])
    assert risks == []


def test_loss_rise_is_r3():
    prev = [_link(loss=0.0)]
    risks = build_link_risks([_link(loss=0.02)], [_load(util=0.1)], prev)
    assert risks[0]["codes"] == ["R3"]
    assert "丢包" in risks[0]["reasons"][0]


def test_small_loss_rise_is_not_r3():
    risks = build_link_risks([_link(loss=0.005)], [_load(util=0.1)], [_link(loss=0.0)])
    assert risks == []


def test_first_snapshot_has_no_r3_baseline():
    # 没有上一次快照时可比较字段缺失，不能凭空判劣化
    risks = build_link_risks([_link(delay=99.0, loss=0.9)], [_load(util=0.1)], [])
    assert risks == []


def test_severity_prefers_r1_over_r3_over_r2():
    risks = build_link_risks(
        [_link(status="down", delay=16.0)],
        [_load(util=2.0)],
        [_link(status="up", delay=10.0)],
    )
    assert len(risks) == 1
    assert risks[0]["severity"] == "R1"
    assert set(risks[0]["codes"]) == {"R1", "R2", "R3"}


def test_risks_sorted_by_severity_then_link_id():
    links = [
        _link("L9", status="down"),
        _link("L1"),
        _link("L2"),
    ]
    loads = [_load("L1", util=2.0), _load("L2", util=0.1), _load("L9", util=0.1)]
    prev = [_link("L2", delay=10.0)]  # L2 时延 16→R3
    links[2] = _link("L2", delay=16.0)
    risks = build_link_risks(links, loads, prev)
    assert [r["linkId"] for r in risks] == ["L9", "L2", "L1"]


def test_accepts_pydantic_models():
    # 采集层传进来的是模型；曾经这里用 dict.get 会 AttributeError
    link = Link.model_validate({**_link(), "srcNodeId": "A", "dstNodeId": "B"})
    load = LinkLoad.model_validate(_load(util=1.2))
    risks = build_link_risks([link], [load], [])
    assert risks[0]["codes"] == ["R2"]
    assert risks[0]["linkId"] == "L1"


# ---------------------------------------------------------------- 汇总
def test_summary_counts_by_code():
    risks = [
        {"linkId": "L1", "codes": ["R1"], "severity": "R1", "reasons": [], "isEstimated": False},
        {"linkId": "L2", "codes": ["R2", "R3"], "severity": "R3", "reasons": [], "isEstimated": True},
    ]
    summary = build_risk_summary(risks, links_ok=True, health="live")
    assert summary["total"] == 2
    assert summary["byCode"] == {"R1": 1, "R3": 1, "R2": 1}
    assert summary["unknown"] is False


def test_summary_unknown_when_health_not_live():
    summary = build_risk_summary([], links_ok=True, health="partial")
    assert summary["unknown"] is True
    assert summary["total"] is None  # 不能把"不可信"显示成 0
    assert "partial" in summary["note"]


def test_summary_unknown_when_links_unavailable():
    summary = build_risk_summary([], links_ok=False, health="live")
    assert summary["unknown"] is True and summary["total"] is None
    assert "链路数据不可用" in summary["note"]


# ---------------------------------------------------------------- 规则 B
def _svc(meet):
    return {"serviceId": "S", "actual": {"qosMeet": meet}}


def test_overall_unknown_when_health_not_live():
    out = build_overall_status("stale", [], [_svc(True)])
    assert out["status"] == "unknown"
    assert out["reasons"] and "stale" in out["reasons"][0]


def test_overall_critical_when_link_down():
    out = build_overall_status("live", [{"codes": ["R1"]}], [_svc(True)])
    assert out["status"] == "critical"
    assert any("断开" in r for r in out["reasons"])


def test_overall_critical_when_bad_ratio_over_30_percent():
    services = [_svc(False)] * 2 + [_svc(True)] * 3  # 2/5 = 40%
    out = build_overall_status("live", [], services)
    assert out["status"] == "critical"


def test_overall_alarm_when_bad_ratio_below_threshold():
    services = [_svc(False)] + [_svc(True)] * 4  # 1/5 = 20%
    out = build_overall_status("live", [], services)
    assert out["status"] == "alarm"


def test_overall_alarm_when_risk_without_r1_or_bad_service():
    out = build_overall_status("live", [{"codes": ["R2"]}], [_svc(True)])
    assert out["status"] == "alarm"


def test_overall_normal_when_all_meet_and_no_risk():
    out = build_overall_status("live", [], [_svc(True)])
    assert out["status"] == "normal"


def test_overall_ignores_unknown_qos_in_ratio():
    # 5 条业务里 1 条不达标、4 条取不到实测值：分母只算可判定的 1 条 → 100% > 30%
    services = [_svc(False)] + [_svc(None)] * 4
    out = build_overall_status("live", [], services)
    assert out["status"] == "critical"
