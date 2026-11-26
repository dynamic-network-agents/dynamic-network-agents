"""reroute_loop 在线闭环单测（mock client，不依赖仿真器）。"""
from common.perception.events import filter_actionable
from common.control.loop import Orchestrator, OrchestratorConfig


class Clock:
    """可控单调时钟（默认从 1000s 起，避免 0 值边界）。"""

    def __init__(self, t: float = 1000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def tick(self, dt: float) -> None:
        self.t += dt


class MockClient:
    def __init__(self, topology, links, services, current_paths=None,
                 server_ts_us=1_800_000_000_000_000, actual=None, event_queue=None):
        self._topology = topology
        self._links = links
        self._services = services
        self._current_paths = current_paths or {}
        self._server_ts_us = server_ts_us
        self._actual = actual or {}          # serviceId -> qosMeet，缺省 True
        self._event_queue = list(event_queue or [])
        self.event_cursors: list[int] = []
        self.applied: list[tuple[str, list[str]]] = []
        self.service_calls = 0
        self.emit_own_events = False     # 模拟仿真器每次 set_path 写一条 pathChanged 事件
        self._event_seq = 0

    def get_time(self):
        return {"time": "00:00:00.000000", "tsUs": self._server_ts_us}

    def get_events(self, since_ts_us=0, limit=100):
        self.event_cursors.append(since_ts_us)
        events = self._event_queue.pop(0) if self._event_queue else []
        nxt = events[-1]["tsUs"] if events else since_ts_us
        return {"events": events, "nextSinceTsUs": nxt}

    def get_topology(self, type=None):
        return self._topology

    def get_links(self, **kw):
        return {"links": self._links}

    def get_services(self, **kw):
        return {"services": [{"serviceId": sid, "status": "running"} for sid in self._services]}

    def get_service(self, sid):
        self.service_calls += 1
        s = dict(self._services[sid])
        s["path"] = {
            "pathId": "P0",
            "segments": [{"type": "link", "id": lid} for lid in self._current_paths.get(sid, [])],
        }
        s["actual"] = {
            "avgDelayMs": 10.0, "jitterMs": 1.0, "effBwBps": 1_000_000,
            "errPct": 0.0, "packetLossRate": 0.0,
            "qosMeet": bool(self._actual.get(sid, True)),
        }
        return s

    def set_service_path(self, sid, src, dst, segments, request_id=None):
        ids = [seg["id"] for seg in segments]
        self.applied.append((sid, ids))
        # 仿真器按**提交顺序**把 flow 路径存进 path_info，再原样返回给同 flow 的所有业务
        self._current_paths[sid] = ids
        if self.emit_own_events:
            self._event_seq += 1
            self._event_queue.append([{
                "eventId": f"EVT{self._event_seq}", "type": "service_state_changed",
                "tsUs": self._event_seq,
                "payload": {"serviceId": sid, "status": "running", "pathChanged": True},
            }])
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


def _service(sid="TSV0001", src="UAV1", dst="UAV2", pri=4, bw=1_000_000, cat="test"):
    return {
        "serviceId": sid, "serviceType": "data", "srcNodeId": src, "dstNodeId": dst,
        "priority": pri, "category": cat, "status": "running",
        "requirement": {"delayMs": 100, "jitterMs": 10, "bandwidthBps": bw,
                        "ber": 1e-5, "packetLossRate": 0.01},
    }


def test_step_plans_and_applies_when_no_current_path():
    client = MockClient(_topology(), _links(), {"TSV0001": _service()}, current_paths={})
    orch = Orchestrator(client, OrchestratorConfig(candidate_path_count=5, min_switch_interval_s=0))
    assert orch.step(force=True) == 1
    assert client.applied == [("TSV0001", ["L1", "L2", "L3"])]


def test_step_reverses_path_for_reverse_service():
    # 业务方向 UAV2→UAV1（flow_key 排序为 (UAV1, UAV2)），下发应反转为 L3,L2,L1
    client = MockClient(
        _topology(), _links(), {"TSV0002": _service("TSV0002", "UAV2", "UAV1")},
        current_paths={},
    )
    orch = Orchestrator(client, OrchestratorConfig(candidate_path_count=5, min_switch_interval_s=0))
    assert orch.step(force=True) == 1
    assert client.applied == [("TSV0002", ["L3", "L2", "L1"])]


def test_step_skips_when_path_unchanged():
    client = MockClient(
        _topology(), _links(), {"TSV0001": _service()},
        current_paths={"TSV0001": ["L1", "L2", "L3"]},
    )
    orch = Orchestrator(client, OrchestratorConfig(candidate_path_count=5, min_switch_interval_s=0))
    assert orch.step(force=True) == 0
    assert client.applied == []


def test_event_cursor_starts_from_server_time():
    # skip_history=True：首轮用 GET /time 的 tsUs 初始化游标，不重放历史事件
    client = MockClient(_topology(), _links(), {}, server_ts_us=1_800_000_123_456_789)
    orch = Orchestrator(client, OrchestratorConfig(candidate_path_count=5, skip_history=True))
    orch.step()
    assert client.event_cursors == [1_800_000_123_456_789]
    assert orch.events.since_ts_us == 1_800_000_123_456_789


def test_event_cursor_replays_history_when_disabled():
    client = MockClient(_topology(), _links(), {}, server_ts_us=1_800_000_123_456_789)
    orch = Orchestrator(client, OrchestratorConfig(candidate_path_count=5, skip_history=False))
    orch.step()
    assert client.event_cursors == [0]


def test_event_cursor_falls_back_to_zero_without_server_time():
    class NoTimeClient(MockClient):
        def get_time(self):
            raise RuntimeError("boom")

    client = NoTimeClient(_topology(), _links(), {})
    orch = Orchestrator(client, OrchestratorConfig(candidate_path_count=5, skip_history=True))
    orch.step()
    assert client.event_cursors == [0]


# --------------------------------------------------------------------------- 双路径拓扑
def _two_path_topology():
    return {"nodes": [
        {"nodeId": "UAV1", "nodeType": "uav", "ip": "10.1.1.1", "status": "online"},
        {"nodeId": "UAV2", "nodeType": "uav", "ip": "10.1.1.2", "status": "online"},
        {"nodeId": "UAV3", "nodeType": "uav", "ip": "10.1.1.3", "status": "online"},
        {"nodeId": "GND1", "nodeType": "ground", "ip": "10.2.1.1", "status": "online"},
        {"nodeId": "GND2", "nodeType": "ground", "ip": "10.2.1.2", "status": "online"},
        {"nodeId": "GND3", "nodeType": "ground", "ip": "10.2.1.3", "status": "online"},
    ]}


def _two_path_links(bw_main=10_000_000, bw_alt=10_000_000):
    def mk(lid, s, d, delay=1.0, bw=bw_main):
        return {
            "linkId": lid, "linkType": "microwave", "srcNodeId": s, "dstNodeId": d,
            "status": "up",
            "params": {"delayMs": delay, "jitterMs": 0.5, "bandwidthBps": bw,
                       "ber": 1e-6, "packetLossRate": 0.0005},
        }
    return [
        mk("L1", "UAV1", "GND1"), mk("L2", "GND1", "GND2"), mk("L3", "GND2", "UAV2"),
        mk("L4", "UAV1", "GND3", 2.0, bw_alt), mk("L5", "GND3", "UAV2", 2.0, bw_alt),
        mk("L6", "GND2", "UAV3"),
    ]


def _orch(client, clock=None, **kw):
    base = dict(candidate_path_count=5, min_switch_interval_s=0.0, batch_pace_s=0.0,
                event_coalesce_s=0.0, batch_settle_s=10.0, verify_window_count=2,
                verify_required_votes=2, corrective_round_limit=1,
                heartbeat_interval_s=60.0)
    base.update(kw)
    clock = clock or Clock()
    return Orchestrator(client, OrchestratorConfig(**base), clock=clock,
                        sleep=lambda s: clock.tick(s))


def _settle_and_verify(orch, clock, max_steps=6):
    """推进到校验完成（不关心返回值）。"""
    clock.tick(orch.config.batch_settle_s + 0.1)
    for _ in range(max_steps):
        orch.step()
        clock.tick(1.1)


# --------------------------------------------------------------------------- 收敛相关
def test_same_path_ignores_submit_direction():
    """仿真器按提交顺序存路径：反序存回来的同一路径不应被判为「变了」。"""
    client = MockClient(_two_path_topology(), _two_path_links(), {"TSV0001": _service()},
                        current_paths={"TSV0001": ["L3", "L2", "L1"]})
    orch = _orch(client)
    assert orch.step(force=True) == 0
    assert client.applied == []


def test_own_path_change_event_is_not_actionable():
    own = {"eventId": "EVT1", "type": "service_state_changed", "tsUs": 1,
           "payload": {"serviceId": "TSV0001", "status": "running", "pathChanged": True}}
    assert filter_actionable([own]) == []

    stopped = {"eventId": "EVT2", "type": "service_state_changed", "tsUs": 2,
               "payload": {"serviceId": "TSV0001", "status": "stopped", "pathChanged": False}}
    link = {"eventId": "EVT3", "type": "link_state_changed", "tsUs": 3,
            "payload": {"linkId": "L1", "event": "param_change"}}
    assert len(filter_actionable([own, stopped, link])) == 2


def test_no_repost_after_one_batch():
    """一个 epoch 下发一次后，静置/校验/心跳阶段都不应再次下发。"""
    client = MockClient(_two_path_topology(), _two_path_links(), {"TSV0001": _service()})
    clock = Clock()
    orch = _orch(client, clock)
    assert orch.step(force=True) == 1
    assert len(client.applied) == 1

    _settle_and_verify(orch, clock)
    for _ in range(10):
        clock.tick(5.0)
        assert orch.step() == 0
    clock.tick(orch.config.heartbeat_interval_s + 1)
    assert orch.step() == 0
    assert len(client.applied) == 1


def test_settle_aborts_on_new_actionable_event():
    client = MockClient(_two_path_topology(), _two_path_links(), {"TSV0001": _service()})
    clock = Clock()
    orch = _orch(client, clock)
    assert orch.step(force=True) == 1

    ev = [{"eventId": "EVT1", "type": "link_state_changed", "tsUs": 2,
           "payload": {"linkId": "L2", "event": "link_up"}}]
    client._event_queue.append(ev)
    assert orch.step() == 0                    # 中止本批（已批后，直接重开）
    assert orch.step() == 0                    # 新 epoch：现状已是最优 → 不动
    assert len(client.applied) == 1


def test_delta_min_blocks_zero_gain_background_move():
    """背景流从 85% 的链路挪到 8.5% 的链路：Δscore=0，不应为此制造 churn。"""
    def scenario():
        client = MockClient(
            _two_path_topology(), _two_path_links(bw_alt=100_000_000),
            {"BGV0001": _service("BGV0001", bw=8_500_000, cat="background")},
            current_paths={"BGV0001": ["L1", "L2", "L3"]},
        )
        return client, _orch(client)

    client, orch = scenario()
    assert orch.step(force=True) == 0
    assert client.applied == []

    client2, orch2 = scenario()
    assert _orch(client2, min_gain_threshold=0.0).step(force=True) == 1


def test_hard_flow_costs_no_action():
    """F1（test-only 超容）：闭环不在这类 flow 上花动作（钉住机制见规划器单测）。"""
    client = MockClient(
        _two_path_topology(), _two_path_links(),
        {  # 两条 test 合计 12M > 10M 接入容量 → F1；单条 6M 静态可行
            "TSV0001": _service(bw=6_000_000),
            "TSV0002": _service("TSV0002", bw=6_000_000),
        },
        current_paths={"TSV0001": ["L1", "L2", "L3"], "TSV0002": ["L1", "L2", "L3"]},
    )
    orch = _orch(client)
    assert orch.step(force=True) == 0
    assert client.applied == []
    assert client._current_paths["TSV0001"] == ["L1", "L2", "L3"]


def test_verify_mismatch_penalizes_path_and_corrects():
    """实测违约 → 该路径进惩罚集 → 有界纠正轮换到另一条路径。"""
    client = MockClient(
        _two_path_topology(), _two_path_links(), {"TSV0001": _service()},
        actual={"TSV0001": False},
    )
    clock = Clock()
    orch = _orch(client, clock)
    assert orch.step(force=True) == 1
    first = client.applied[0][1]

    _settle_and_verify(orch, clock)
    assert len(client.applied) == 2
    assert client.applied[0][1] != client.applied[1][1]
    assert tuple(first) in orch.verifier.penalized_paths[("UAV1", "UAV2")]


def test_batch_budget_stops_optimization():
    client = MockClient(_two_path_topology(), _two_path_links(), {"TSV0001": _service()})
    clock = Clock()
    orch = _orch(client, clock, max_batches_per_run=1)
    assert orch.step(force=True) == 1
    # 再来一次可行动事件也不应再开 epoch
    client._event_queue.append([
        {"eventId": "EVT1", "type": "link_state_changed", "tsUs": 3,
         "payload": {"linkId": "L2", "event": "link_up"}},
    ])
    clock.tick(5)
    assert orch.step() == 0


def test_own_post_events_do_not_abort_batch_or_trigger_replan():
    """仿真器每次 set_path 都写 pathChanged 事件：不能因此中止本批或触发下一批。"""
    client = MockClient(
        _two_path_topology(), _two_path_links(),
        {"TSV0001": _service(), "TSV0003": _service("TSV0003", dst="UAV3")},
    )
    client.emit_own_events = True
    clock = Clock()
    orch = _orch(client, clock)
    assert orch.step(force=True) == 2                 # 两条都下发，没被自己的事件打断

    _settle_and_verify(orch, clock)
    for _ in range(10):
        clock.tick(5.0)
        assert orch.step() == 0
    assert len(client.applied) == 2
