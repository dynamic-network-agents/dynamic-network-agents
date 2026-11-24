"""快照层接线测试：run-info 运行态 + 风险链路/整体状态。

这里的 client 用深拷贝返回，模拟"每次 HTTP 响应都是新对象"，
否则修改链路参数会连带改掉 Collector 里的 R3 基线。
"""
from __future__ import annotations

import copy

from backend.simulator_client import SimulatorError
from backend.snapshot import Collector


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        self.t += 2.0
        return self.t


class FakeSim:
    def __init__(self):
        self.run_error: SimulatorError | None = None
        self.run_info = {
            "status": "running",
            "instanceId": "INST-1",
            "suiteId": "SUITE-1",
            "scenarioId": "SCN-1",
            "scriptId": "SCRIPT-1",
            "t0Time": "2026-11-24 15:00:00",
            "t0TsUs": 1_000_000,
            "netReadyTsUs": 900_000,
            "engine": {"state": "running", "fired": 3, "total": 10},
            "services": {
                "running": 2,
                "states": {"running": 2, "pending": 1},
                "joinError": "",
            },
            "noBusiness": False,
        }
        self.nodes = [
            {"nodeId": "A", "ip": "10.0.0.1", "nodeType": "uav"},
            {"nodeId": "B", "ip": "10.0.0.2", "nodeType": "uav"},
            {"nodeId": "C", "ip": "10.0.0.3", "nodeType": "uav"},
        ]
        self.link_items = [
            {
                "linkId": "L1",
                "srcNodeId": "A",
                "dstNodeId": "B",
                "status": "down",
                "params": {"delayMs": 5, "bandwidthBps": 1e8, "packetLossRate": 0.0},
            },
            {
                "linkId": "L2",
                "srcNodeId": "B",
                "dstNodeId": "C",
                "status": "up",
                "params": {"delayMs": 10, "bandwidthBps": 1e6, "packetLossRate": 0.0},
            },
            {
                "linkId": "L3",
                "srcNodeId": "A",
                "dstNodeId": "C",
                "status": "up",
                "params": {"delayMs": 10, "bandwidthBps": 1e8, "packetLossRate": 0.0},
            },
        ]
        self.service_items = [
            {"serviceId": "S1", "srcNodeId": "A", "dstNodeId": "B"},
            {"serviceId": "S2", "srcNodeId": "B", "dstNodeId": "C"},
            {"serviceId": "S3", "srcNodeId": "A", "dstNodeId": "C"},
        ]
        self.details = {
            "S1": {
                "requirement": {"delayMs": 100, "bandwidthBps": 5e6},
                "path": {"pathId": "P01001", "segments": [{"type": "link", "id": "L1"}]},
                "actual": {"avgDelayMs": 200, "qosMeet": False},
            },
            "S2": {
                "requirement": {"bandwidthBps": 5e6},
                "path": {"pathId": "P01002", "segments": [{"type": "link", "id": "L2"}]},
                "actual": {"effBwBps": 5.1e6, "qosMeet": True},
            },
            "S3": {
                "requirement": {"bandwidthBps": 1e6},
                "path": {"pathId": "P01003", "segments": [{"type": "link", "id": "L3"}]},
                "actual": {"effBwBps": 1.1e6, "qosMeet": True},
            },
        }
        self.events: list[dict] = []

    # -- 采集接口
    def get_topology(self):
        return {
            "nodes": copy.deepcopy(self.nodes),
            "links": [{"linkId": l["linkId"]} for l in self.link_items],
        }

    def get_links_all(self, page_size=500, max_pages=20):
        return copy.deepcopy(self.link_items), 1, True

    def get_services_all(self, page_size=500, max_pages=20):
        return copy.deepcopy(self.service_items), 1, True

    def get_service(self, sid):
        return copy.deepcopy(self.details[sid])

    def get_time(self):
        return {"tsUs": 1_500_000}

    def get_events(self, since_ts_us=0, limit=500):
        return {"events": copy.deepcopy(self.events), "nextSinceTsUs": since_ts_us}

    def get_svc_meta(self):
        return {"S1": {"category": "test"}, "S2": {"category": "test"}}

    def get_run_info(self):
        if self.run_error is not None:
            raise self.run_error
        return copy.deepcopy(self.run_info)


def _collector(client: FakeSim) -> Collector:
    return Collector(client, {}, detail_ttl=0.0, stale_after_s=6.0, clock=Clock())


def test_snapshot_exposes_sim_status():
    snap = _collector(FakeSim()).snapshot()
    assert snap.sim.status == "running"
    assert snap.sim.instanceId == "INST-1"
    assert snap.sim.scriptId == "SCRIPT-1"
    assert snap.sim.t0TsUs == 1_000_000
    assert snap.sim.engineFired == 3 and snap.sim.engineTotal == 10
    assert snap.sim.servicesRunning == 2
    assert snap.sim.serviceStates == {"running": 2, "pending": 1}
    assert snap.sim.error is None


def test_run_info_instance_is_authoritative_over_events():
    client = FakeSim()
    client.events = [
        {"payload": {"instanceId": "OLD", "scenarioId": "OLD-SCN"}},
    ]
    snap = _collector(client).snapshot()
    assert snap.instance_id == "INST-1"
    assert snap.scenario_id == "SCN-1"


def test_run_info_failure_does_not_break_snapshot_health():
    client = FakeSim()
    client.run_error = SimulatorError(1006, "缺少或无效 X-Ctrl-Token")
    snap = _collector(client).snapshot()
    assert snap.health == "live"  # run-info 不是核心资源
    assert snap.sim.status == "unknown"
    assert snap.sim.instanceId is None
    assert "1006" in snap.sim.error


def test_risk_links_and_overall_status_are_wired():
    snap = _collector(FakeSim()).snapshot()
    by_id = {r.linkId: r for r in snap.riskLinks}

    assert set(by_id) == {"L1", "L2"}
    assert by_id["L1"].codes == ["R1"] and by_id["L1"].severity == "R1"
    assert by_id["L2"].codes == ["R2"] and by_id["L2"].isEstimated is True

    assert snap.riskSummary.unknown is False
    assert snap.riskSummary.total == 2
    assert snap.riskSummary.byCode == {"R1": 1, "R3": 0, "R2": 1}

    # 有 R1 → critical，且理由是具体可解释的
    assert snap.overallStatus.status == "critical"
    assert any("断开" in r for r in snap.overallStatus.reasons)


def test_r3_uses_previous_snapshot_as_baseline():
    client = FakeSim()
    collector = _collector(client)

    first = collector.snapshot()
    assert "L3" not in {r.linkId for r in first.riskLinks}

    client.link_items[2]["params"]["delayMs"] = 20.0  # 10 → 20ms，涨幅 100%
    second = collector.snapshot()

    by_id = {r.linkId: r for r in second.riskLinks}
    assert "R3" in by_id["L3"].codes
    assert any("时延" in reason for reason in by_id["L3"].reasons)


def test_risk_summary_unknown_when_health_not_live():
    client = FakeSim()
    # 分页没读完 → pagination 不完整 → health 非 live，风险数不得显示成 0
    client.get_links_all = lambda page_size=500, max_pages=20: ([], 1, False)  # type: ignore
    client.get_topology = lambda: {"nodes": copy.deepcopy(client.nodes), "links": []}  # type: ignore
    snap = _collector(client).snapshot()
    assert snap.health == "partial"
    assert snap.riskSummary.unknown is True
    assert snap.riskSummary.total is None
    assert snap.overallStatus.status == "unknown"


def test_offline_snapshot_reports_unknown_risk():
    collector = Collector(
        FakeSim(),
        {},
        offline=True,
        offline_scene={"nodes": [], "links": []},
        offline_services=[],
    )
    snap = collector.snapshot()
    assert snap.health == "offline"
    assert snap.sim.status == "unknown" and snap.sim.error == "offline"
    assert snap.riskSummary.unknown is True and snap.riskSummary.total is None
    assert snap.overallStatus.status == "unknown"
