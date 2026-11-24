"""work_bench 后端单元测试：快照分类降级链路与写开关。"""
from __future__ import annotations

import pytest

from backend import policy
from backend.simulator_client import SimulatorError
from backend.snapshot import _load_svc_meta, _with_detail


class _FakeClient:
    def __init__(self, meta=None, meta_error=None, detail=None, detail_error=None):
        self._meta = meta or {}
        self._meta_error = meta_error
        self._detail = detail or {}
        self._detail_error = detail_error

    def get_svc_meta(self):
        if self._meta_error is not None:
            raise self._meta_error
        return self._meta

    def get_service(self, sid):
        if self._detail_error is not None:
            raise self._detail_error
        return self._detail


def test_svc_meta_ok_maps_category():
    live, status = _load_svc_meta(
        _FakeClient(meta={"S1": {"category": "background"}, "S2": {}}), True
    )
    assert live == {"S1": "background"}
    assert status.ok is True and status.count == 1


def test_svc_meta_error_degrades_without_raising():
    live, status = _load_svc_meta(_FakeClient(meta_error=SimulatorError(1006, "拒绝")), True)
    assert live == {}
    assert status.ok is False
    assert "1006" in status.error


def test_svc_meta_disabled():
    live, status = _load_svc_meta(_FakeClient(meta={"S1": {"category": "test"}}), False)
    assert live == {}
    assert status.enabled is False and status.ok is False
    assert status.error == "disabled"


def test_category_priority_live_then_offline_then_unknown():
    client = _FakeClient(detail={"requirement": {"delayMs": 1}, "path": None, "actual": None})
    svc = {"serviceId": "S1"}

    out = _with_detail(client, svc, {"S1": "test"}, {"S1": "background"})
    assert (out.category, out.categorySource) == ("background", "simulator")

    out = _with_detail(client, svc, {"S1": "test"}, {})
    assert (out.category, out.categorySource) == ("test", "offline_mapping")

    out = _with_detail(client, svc, {}, {})
    assert (out.category, out.categorySource) == ("unknown", "unknown")


def test_detail_error_is_isolated():
    client = _FakeClient(detail_error=SimulatorError(2000, "超时"))
    out = _with_detail(client, {"serviceId": "S1"}, {}, {})
    assert out.detailError == "2000: 超时"
    assert out.requirement is None


def test_repath_gate():
    policy.ensure_repath_allowed(True)  # 不抛
    with pytest.raises(policy.RepathDisabled) as exc:
        policy.ensure_repath_allowed(False)
    assert "WORKBENCH_ALLOW_REPATH" in str(exc.value)
