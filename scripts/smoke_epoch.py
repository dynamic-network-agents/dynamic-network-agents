"""sce01 离线冒烟：真实场景 JSON + 假 client 驱动完整 epoch 状态机。

不是单测（不跑在 CI），用于观察「批次数 / POST 数 / 是否重复下发」。
用法：PYTHONPATH=src .venv/bin/python scripts/smoke_epoch.py
"""
import collections as C
import json
import sys

from common.algorithms.topology.capacity import add_load, capacity_map, directional_demand
from common.algorithms.flow.planner import normalize_path
from common.algorithms.topology.graph import build_graph
from common.control.loop import Orchestrator, OrchestratorConfig
from common.modeling.models import Link, Node, Service

SC = "simulator/data/scenarios/sce20261010-conf02/sce01/"


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def tick(self, dt):
        self.t += dt


class ScenarioClient:
    """最小仿真器替身：路径按 **flow** 存储（与 _flow_for 一致），并发 pathChanged 事件。"""

    def __init__(self):
        self.topo = json.load(open(SC + "net-topo.json"))
        self.svcs = {s["serviceId"]: dict(s, status="running")
                     for s in json.load(open(SC + "bg-service.json"))}
        installed = {s["serviceId"]: s["paths"][0]["links"]
                     for s in json.load(open(SC + "service-paths.json"))["services"]}
        self.links = [dict(l) for l in self.topo["links"]]
        self.flow_path = {}
        for s in self.svcs.values():
            k = self._key(s)
            self.flow_path.setdefault(k, list(installed.get(s["serviceId"], [])))
        self.events, self.applied, self.ts = [], [], 1000

    @staticmethod
    def _key(s):
        return tuple(sorted((s["srcNodeId"], s["dstNodeId"])))

    def _graph(self):
        return build_graph([Node.from_dict(n) for n in self.topo["nodes"]],
                           [Link.from_dict(l) for l in self.links])

    def get_time(self):
        return {"tsUs": self.ts * 1_000_000}

    def get_events(self, since_ts_us=0, limit=100):
        out = [e for e in self.events if e["tsUs"] > since_ts_us]
        return {"events": out, "nextSinceTsUs": out[-1]["tsUs"] if out else since_ts_us}

    def get_topology(self):
        return {"nodes": self.topo["nodes"]}

    def get_links(self, **kw):
        return {"links": self.links}

    def get_services(self, **kw):
        return {"services": [{"serviceId": k, "status": "running"} for k in self.svcs]}

    def get_service(self, sid):
        s = self.svcs[sid]
        k = self._key(s)
        path = self.flow_path[k]
        return dict(s, path={"segments": [{"type": "link", "id": l} for l in path]},
                    actual=self._actual(s, k, path))

    def set_service_path(self, sid, src, dst, segments, request_id=None):
        k = tuple(sorted((src, dst)))
        ids = [x["id"] for x in segments]
        self.flow_path[k] = ids
        self.applied.append((k, tuple(ids)))
        self.events.append({
            "eventId": f"E{len(self.events)}", "type": "service_state_changed",
            "tsUs": self.ts * 1_000_000,
            "payload": {"serviceId": sid, "status": "running", "pathChanged": True},
        })
        return {"result": "accepted"}

    def _actual(self, s, k, path):
        g = self._graph()
        cap = capacity_map(g)
        load = {}
        for k2, p2 in self.flow_path.items():
            norm = normalize_path(g, k2, p2)
            if not norm:
                continue
            ss = [Service.from_dict(x) for x in self.svcs.values() if self._key(x) == k2]
            add_load(load, directional_demand(k2[0], ss, norm, g))
        norm = normalize_path(g, k, path)
        if norm is None:          # 路径含已断链路：实测必然不达标
            return {"avgDelayMs": 0.0, "jitterMs": 0.0, "effBwBps": 0, "errPct": 0.0,
                    "packetLossRate": 1.0, "qosMeet": False}
        d = directional_demand(k[0], [Service.from_dict(s)], norm, g)
        util = max((load.get(kk, 0) / cap[kk[0]] for kk in d if cap.get(kk[0], 0)), default=0.0)
        return {"avgDelayMs": 10.0, "jitterMs": 1.0, "effBwBps": 1_000_000, "errPct": 0.0,
                "packetLossRate": 0.0, "qosMeet": util <= 1.0}


def main():
    client, clock = ScenarioClient(), Clock()
    orch = Orchestrator(client, OrchestratorConfig(
        candidate_path_count=30, batch_pace_s=0, event_coalesce_s=3, batch_settle_s=10,
        verify_window_count=3, verify_required_votes=2, corrective_round_limit=1,
        heartbeat_interval_s=60, min_switch_interval_s=10,
    ), clock=clock, sleep=lambda s: clock.tick(s))

    def advance(seconds, label):
        n = 0
        for _ in range(int(seconds)):
            clock.tick(1.0)
            client.ts = clock.t
            n += orch.step()
        print(f"  {label}: +{n} POST (累计 {len(client.applied)}), "
              f"phase={orch.phase.value}, batches={orch.batch_count}")

    print("== T0 首轮 ==")
    print("  force epoch POSTs:", orch.step(force=True))
    advance(40, "静置+校验")
    advance(120, "静默 2min")

    print("== 注入断链 L00005 ==")
    client.links = [l for l in client.links if l["linkId"] != "L00005"]
    client.ts = clock.t
    client.events.append({
        "eventId": "EVT-X", "type": "link_state_changed", "tsUs": client.ts * 1_000_000,
        "payload": {"linkId": "L00005", "event": "link_down"},
    })
    advance(40, "断链后处理")
    advance(180, "再静默 3min")

    print(f"\n累计下发 {len(client.applied)}，去重 {len(set(client.applied))}")
    dup = [(k, v) for k, v in C.Counter(client.applied).items() if v > 1]
    print("重复下发:", dup or "无")
    return 0 if not dup else 1


if __name__ == "__main__":
    sys.exit(main())
