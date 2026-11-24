"""work_bench 后端单元测试：仿真 API client 的鉴权头与 svc-meta。"""
from __future__ import annotations

import pytest

from backend import simulator_client
from backend.simulator_client import SimulatorClient, SimulatorError


class _Resp:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload


def _patch(monkeypatch, payload: dict):
    calls: list[dict] = []

    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        calls.append({"method": method, "url": url, "headers": headers or {}})
        return _Resp(payload)

    monkeypatch.setattr(simulator_client.requests, "request", fake_request)
    return calls


def test_ctrl_mode_sends_ctrl_header(monkeypatch):
    calls = _patch(monkeypatch, {"code": 0, "data": {"links": []}})
    client = SimulatorClient("http://h:10100/api/open/v1", "T", auth_mode="ctrl")
    client.get_links()
    assert calls[0]["headers"]["X-Ctrl-Token"] == "T"
    assert "X-Open-Token" not in calls[0]["headers"]
    assert calls[0]["url"] == "http://h:10100/api/open/v1/links"


def test_open_mode_keeps_legacy_header(monkeypatch):
    calls = _patch(monkeypatch, {"code": 0, "data": {}})
    client = SimulatorClient("http://h/api/open/v1", "T", auth_mode="open")
    client.get_time()
    assert calls[0]["headers"]["X-Open-Token"] == "T"
    assert "X-Ctrl-Token" not in calls[0]["headers"]


def test_invalid_auth_mode_rejected():
    with pytest.raises(ValueError):
        SimulatorClient("http://h", "T", auth_mode="bogus")


def test_svc_meta_uses_ctrl_base_and_parses(monkeypatch):
    payload = {
        "code": 0,
        "data": {"meta": {"S1": {"category": "background", "serviceType": "video"}}},
    }
    calls = _patch(monkeypatch, payload)
    client = SimulatorClient(
        "http://h:10100/api/open/v1",
        "T",
        auth_mode="ctrl",
        ctrl_base_url="http://h:10100/api/ctrl/v1",
    )
    meta = client.get_svc_meta()
    assert meta["S1"]["category"] == "background"
    assert calls[0]["url"] == "http://h:10100/api/ctrl/v1/svc-meta"
    assert calls[0]["headers"]["X-Ctrl-Token"] == "T"


def test_svc_meta_unavailable_without_ctrl_base():
    client = SimulatorClient("http://h/api/open/v1", "T")
    assert client.svc_meta_available is False
    with pytest.raises(SimulatorError) as exc:
        client.get_svc_meta()
    assert exc.value.code == 1003


def test_error_envelope_raises_without_token_leak(monkeypatch):
    _patch(monkeypatch, {"code": 1002, "msg": "缺少或无效 X-Ctrl-Token"})
    client = SimulatorClient("http://h/api/open/v1", "secret-token", auth_mode="ctrl")
    with pytest.raises(SimulatorError) as exc:
        client.get_links()
    assert exc.value.code == 1002
    assert "secret-token" not in str(exc.value)
