"""实测 QoS 反馈单测。"""
import pytest

from math_modeling.models import Actual, Service
from math_modeling.measured_qos import test_meet_rate as meet_rate


def _svc(category, meet, service_id="x"):
    actual = Actual(avg_delay_ms=0.0, jitter_ms=0.0, eff_bw_bps=0, err_pct=0.0,
                    packet_loss_rate=0.0, qos_meet=meet)
    return Service(service_id=service_id, category=category, actual=actual)


def test_meet_rate_basic():
    svcs = [
        _svc("test", True),
        _svc("test", False),
        _svc("test", True),
        _svc("background", False),  # 不计入
    ]
    assert meet_rate(svcs) == pytest.approx(2 / 3)


def test_meet_rate_no_data():
    # qos_meet 为 None（实测填充中）→ 不计
    assert meet_rate([_svc("test", None)]) is None
    assert meet_rate([]) is None


def test_meet_rate_falls_back_to_tsv_prefix():
    # 公开 API 无 category：按 serviceId 前缀兜底，口径与 planner 的 service_is_test 一致
    svcs = [
        _svc("", True, service_id="TSV0001"),
        _svc("", False, service_id="TSV0002"),
        _svc("", False, service_id="BGV0001"),  # background，不计入
    ]
    assert meet_rate(svcs) == pytest.approx(1 / 2)
