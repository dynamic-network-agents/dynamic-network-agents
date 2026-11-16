"""实测 QoS 反馈单测。"""
import pytest

from math_modeling.models import Actual, Service
from math_modeling.measured_qos import test_meet_rate as meet_rate


def _svc(category, meet):
    actual = Actual(avg_delay_ms=0.0, jitter_ms=0.0, eff_bw_bps=0, err_pct=0.0,
                    packet_loss_rate=0.0, qos_meet=meet)
    return Service(service_id="x", category=category, actual=actual)


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
