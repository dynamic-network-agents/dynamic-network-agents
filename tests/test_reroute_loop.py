"""reroute_loop 在线闭环单测（mock client，不依赖仿真器）。"""
from baseline.reroute_loop import Orchestrator, OrchestratorConfig


class MockClient:
    def __init__(self, topology, links, services, current_paths=None):
        self._topology = topology
        self._links = links
        self._services = services
        self._current_paths = current_paths or {}
        self.applied: list[tuple[str, list[str]]] = []

    def get_events(self, since_ts_us=0, limit=100):
        return {"events": [], "nextSinceTsUs": since_ts_us}

    def get_topology(self, type=None):
        return self._topology

    def get_links(self, **kw):
        return {"links": self._links}

    def get_services(self, **kw):
        return {"services": [{"serviceId": sid, "status": "running"} for sid in self._services]}

    def get_service(self, sid):
        s = dict(self._services[sid])
        s["path"] = {
            "pathId": "P0",
            "segments": [{"type": "link", "id": lid} for lid in self._current_paths.get(sid, [])],
        }
        return s

    def set_service_path(self, sid, src, dst, segments, request_id=None):
        self.applied.append((sid, [seg["id"] for seg in segments]))
        return {"result": "accepted", "pathId": "P1"}


def _topology():
    return {"nodes": [
        {"nodeId": "UAV1", "nodeType": "uav", "ip": "10.1.1.1", "status": "online"},
        {"nodeId": "UAV2", "nodeType": "uav", "ip": "10.1.1.2", "status": "online"},
        {"nodeId": "GND1", "nodeType": "ground", "ip": "10.2.1.1", "status": "online"},
        {"nodeId": "GND2", "nodeType": "ground", "ip": "10.2.1.2", "status": "online"},
    ]}


def _links():
    def mk(lid, s, d, bw=10_000_000):
        return {
            "linkId": lid, "linkType": "microwave", "srcNodeId": s, "dstNodeId": d,
            "status": "up",
            "params": {"delayMs": 1.0, "jitterMs": 0.5, "bandwidthBps": bw,
                       "ber": 1e-6, "packetLossRate": 0.0005},
        }
    return [mk("L1", "UAV1", "GND1"), mk("L2", "GND1", "GND2"), mk("L3", "GND2", "UAV2")]


def _service(sid="TSV0001", src="UAV1", dst="UAV2", pri=4):
    return {
        "serviceId": sid, "serviceType": "data", "srcNodeId": src, "dstNodeId": dst,
        "priority": pri, "category": "test", "status": "running",
        "requirement": {"delayMs": 100, "jitterMs": 10, "bandwidthBps": 1_000_000,
                        "ber": 1e-5, "packetLossRate": 0.01},
    }


def test_step_plans_and_applies_when_no_current_path():
    client = MockClient(_topology(), _links(), {"TSV0001": _service()}, current_paths={})
    orch = Orchestrator(client, OrchestratorConfig(k=5, switch_min_interval_s=0))
    assert orch.step(force=True) == 1
    assert client.applied == [("TSV0001", ["L1", "L2", "L3"])]


def test_step_reverses_path_for_reverse_service():
    # 业务方向 UAV2→UAV1（flow_key 排序为 (UAV1, UAV2)），下发应反转为 L3,L2,L1
    client = MockClient(
        _topology(), _links(), {"TSV0002": _service("TSV0002", "UAV2", "UAV1")},
        current_paths={},
    )
    orch = Orchestrator(client, OrchestratorConfig(k=5, switch_min_interval_s=0))
    assert orch.step(force=True) == 1
    assert client.applied == [("TSV0002", ["L3", "L2", "L1"])]


def test_step_skips_when_path_unchanged():
    client = MockClient(
        _topology(), _links(), {"TSV0001": _service()},
        current_paths={"TSV0001": ["L1", "L2", "L3"]},
    )
    orch = Orchestrator(client, OrchestratorConfig(k=5, switch_min_interval_s=0))
    assert orch.step(force=True) == 0
    assert client.applied == []
