"""分页读取测试：仿真器 page/size（默认 500、上限 2000）。"""
from __future__ import annotations

from backend import simulator_client
from backend.simulator_client import SimulatorClient


class _Resp:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def json(self):
        return self._payload


def _client():
    return SimulatorClient("http://h/api/open/v1", "T", auth_mode="ctrl")


def _patch_pages(monkeypatch, page_items):
    calls = []

    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        page = int((params or {}).get("page", 1))
        size = int((params or {}).get("size", 500))
        calls.append({"url": url, "page": page, "size": size})
        return _Resp({"code": 0, "data": {"links": page_items[page], "services": page_items[page]}})

    monkeypatch.setattr(simulator_client.requests, "request", fake_request)
    return calls


def test_get_links_all_reads_until_short_page(monkeypatch):
    items = {
        1: [{"linkId": f"L{i}"} for i in range(500)],
        2: [{"linkId": "L500"} for _ in range(10)],
    }
    calls = _patch_pages(monkeypatch, items)
    links, pages, complete = _client().get_links_all(page_size=500, max_pages=20)
    assert len(links) == 510
    assert pages == 2
    assert complete is True
    assert calls[0]["size"] == 500
    assert [c["page"] for c in calls] == [1, 2]


def test_get_services_all_marks_incomplete_at_max_pages(monkeypatch):
    full = [{"serviceId": f"S{i}"} for i in range(500)]
    calls = _patch_pages(monkeypatch, {1: full, 2: full, 3: full})
    services, pages, complete = _client().get_services_all(page_size=500, max_pages=2)
    assert len(services) == 1000
    assert pages == 2
    assert complete is False  # 达到页数上限，不能声称读全
    assert len(calls) == 2


def test_page_size_clamped_to_protocol_max(monkeypatch):
    calls = _patch_pages(monkeypatch, {1: [{"linkId": "L1"}]})
    _client().get_links_all(page_size=99999, max_pages=1)
    assert calls[0]["size"] == 2000
