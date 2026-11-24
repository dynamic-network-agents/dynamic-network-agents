"""数据健康状态测试：live / partial / stale / disconnected / offline。"""
from __future__ import annotations

from backend.simulator_client import SimulatorError
from backend.snapshot import Collector


class FakeClient:
    def __init__(self):
        self.fail: set[str] = set()
        self.topology = {
            "nodes": [{"nodeId": "N1", "position": {"x": 0, "y": 0}}],
            "links": [{"linkId": "L1"}],
        }
        self.link_items = [
            {"linkId": "L1", "srcNodeId": "N1", "dstNodeId": "N2", "params": {"delayMs": 1}}
        ]
        self.service_items = [{"serviceId": "S1"}]
        self.detail = {
            "requirement": {"delayMs": 10},
            "path": {"pathId": "P01001", "segments": []},
            "actual": {"avgDelayMs": 9, "qosMeet": True},
        }
        self.meta = {"S1": {"category": "test"}}

    def _guard(self, name: str) -> None:
        if name in self.fail:
            raise SimulatorError(2000, f"boom {name}")

    def get_topology(self):
        self._guard("topology")
        return self.topology

    def get_links_all(self, page_size=500, max_pages=20):
        self._guard("links")
        return self.link_items, 1, True

    def get_services_all(self, page_size=500, max_pages=20):
        self._guard("services")
        return self.service_items, 1, True

    def get_service(self, sid):
        self._guard("detail")
        return self.detail

    def get_time(self):
        self._guard("time")
        return {"tsUs": 123}

    def get_events(self, since_ts_us=0, limit=500):
        self._guard("events")
        return {"events": [], "nextSinceTsUs": since_ts_us}

    def get_svc_meta(self):
        self._guard("svcmeta")
        return self.meta


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _collector(client, clock):
    return Collector(client, {}, detail_ttl=0.0, stale_after_s=6.0, clock=clock)


def test_live_when_all_core_ok():
    clock = Clock()
    snap = _collector(FakeClient(), clock).snapshot()
    assert snap.health == "live"
    assert snap.pagination.links.count == 1
    assert snap.pagination.topology_links == 1
    assert snap.pagination.consistent is True
    assert snap.services[0].category == "test"
    assert snap.services[0].categorySource == "simulator"


def test_partial_when_core_fails_but_cache_fresh():
    clock = Clock()
    client = FakeClient()
    collector = _collector(client, clock)
    collector.snapshot()
    clock.t = 1.0
    client.fail.add("links")
    snap = collector.snapshot()
    assert snap.health == "partial"
    assert snap.stale_resources == ["links"]
    assert len(snap.links) == 1  # 用缓存，不丢数据


def test_stale_when_core_still_failing_past_window():
    clock = Clock()
    client = FakeClient()
    collector = _collector(client, clock)
    collector.snapshot()
    clock.t = 7.0
    client.fail.add("links")
    snap = collector.snapshot()
    assert snap.health == "stale"
    assert snap.data_age_s == 7.0
    assert "links" in snap.errors[0] or any("links" in e for e in snap.errors)


def test_disconnected_when_all_core_fail():
    clock = Clock()
    client = FakeClient()
    collector = _collector(client, clock)
    collector.snapshot()
    clock.t = 2.0
    client.fail.update({"topology", "links", "services"})
    snap = collector.snapshot()
    assert snap.health == "disconnected"
    assert len(snap.nodes) == 1 and len(snap.links) == 1  # 仍返回缓存
    assert set(snap.stale_resources) == {"topology", "links", "services"}


def test_offline_snapshot_from_scene():
    collector = Collector(
        FakeClient(),
        {"BGV1": "background"},
        offline=True,
        offline_scene={
            "scenarioId": "sce01",
            "nodes": [{"nodeId": "N1"}],
            "links": [{"linkId": "L1", "srcNodeId": "N1", "dstNodeId": "N2"}],
        },
        offline_services=[{"serviceId": "BGV1", "requirement": {"delayMs": 100}}],
    )
    snap = collector.snapshot()
    assert snap.health == "offline" and snap.offline is True
    assert snap.scenario_id == "sce01"
    assert snap.services[0].category == "background"
    assert snap.services[0].status == "unknown"
    assert snap.services[0].actual is None
