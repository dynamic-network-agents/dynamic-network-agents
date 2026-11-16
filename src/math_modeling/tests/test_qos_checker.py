"""QoS 硬约束判定单测（含容差边界）。"""
import pytest

from math_modeling.models import Requirement
from math_modeling.path_qos import QoSMetrics
from math_modeling.qos_checker import check_qos


def _req(d=150.0, j=30.0, b=2_000_000, ber=1e-4, loss=0.05):
    return Requirement(delay_ms=d, jitter_ms=j, bandwidth_bps=b, ber=ber, packet_loss_rate=loss)


def _qos(d=0.0, j=0.0, b=3_000_000, ber=0.0, loss=0.0):
    # 默认值满足全部约束（b 需 >= 2M 下界），便于只覆盖单个字段做边界测试
    return QoSMetrics(delay_ms=d, jitter_ms=j, bandwidth_bps=b, ber=ber, packet_loss_rate=loss)


def test_all_pass():
    r = check_qos(_qos(d=100.0, j=10.0, b=3_000_000, ber=1e-5, loss=0.01), _req())
    assert r.feasible
    assert r.violations == []
    assert r.margin["delay"] == pytest.approx(50.0)
    assert r.margin["bandwidth"] == pytest.approx(1_000_000)


def test_delay_within_tolerance():
    # 超出 0.5ms < 容差 1.0ms，不违规
    assert check_qos(_qos(d=150.5), _req()).feasible


def test_delay_exceeds_tolerance():
    r = check_qos(_qos(d=151.5), _req())
    assert not r.feasible
    assert "delay" in r.violations


def test_bandwidth_at_lower_bound():
    assert check_qos(_qos(b=2_000_000), _req()).feasible
    assert not check_qos(_qos(b=1_999_999), _req()).feasible


def test_ber_tolerance_boundary():
    # 差 1e-13（< 容差 1e-12）不违规；差 1e-11 违规
    assert check_qos(_qos(ber=1e-4 + 1e-13), _req()).feasible
    assert not check_qos(_qos(ber=1e-4 + 1e-11), _req()).feasible


def test_packet_loss_tolerance_boundary():
    assert check_qos(_qos(loss=0.05 + 1e-10), _req()).feasible
    assert not check_qos(_qos(loss=0.05 + 1e-8), _req()).feasible
