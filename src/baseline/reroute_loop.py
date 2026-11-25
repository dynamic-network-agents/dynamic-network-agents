"""主控制循环：事件/实测驱动的流级重路由（FPCB 规划器 + epoch 状态机）。

设计要点（见 `docs/agents/传统基线选路方案.md` §5.6-§5.9）：

**一个 epoch = 一次冻结快照 + 一次规划 + 一个下发批 + 一次校验。**

1. **触发**：只认可行动事件（链路状态/参数变化、节点上下线、业务状态变为非 running），
   **忽略自己下发产生的 `service_state_changed(pathChanged=true, status=running)`**，
   否则 POST → 事件 → 重规划 → POST 会自激成死循环。事件成簇到达时先合窗
   （`trigger_settle_s`）再规划，避免一条事件簇触发多次全量规划。
2. **规划是纯函数、下发是增量**：同一快照重算结果完全一致；拿计划与已装路径做差集，
   只有「路径失效」（修复）或「加权达标数增益 ≥ Δmin」才下发，其余一律不动。
3. **批内不重算**：批是一次计划的执行，中途重算等于换计划、把瞬态无限延长。
   批内若收到新的可行动事件，直接中止剩余下发并用新快照重开 epoch。
4. **批后静置 + 校验**：`settle_s` 后按多个 1s 窗投票，比较「预测达标」与「实测达标」；
   失配的路径进惩罚集（下一轮候选剔除），纠正轮数有上限（`corrective_rounds`）。
5. **静默期**：收敛后只做低频心跳（`measured_check_interval_s`），且只对**上一轮预测达标**
   的 flow 检查 —— 物理上救不回来的 flow（F1/F2）不参与判据，否则永远不收敛。

时间口径：
- `sinceTsUs` 是仿真器事件日志**自己的**时间轴（Unix 纪元微秒，服务器时钟），
  服务端按 `event.tsUs > sinceTsUs` 严格过滤，所以只需原样回传 `nextSinceTsUs`，
  **不需要把本地时钟对齐到仿真器**。启动时用 `GET /time` 的 `tsUs` 初始化游标，
  只是为了不从 0 开始重放历史事件（事件日志跨重启保留）。
- 轮询周期、静置、防抖一律用单调时钟 `time.monotonic()`，墙钟被 NTP 调整不会影响计时。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

import networkx as nx

from algorithms.flow_planner import (
    FlowPlan,
    PlanConfig,
    normalize_path,
    plan,
    plan_score,
    predicted_meet,
    score_with_paths,
)
from algorithms.graph import build_graph, parse_links, parse_nodes
from api.client import SimulatorClient
from api.executor import PathExecutor
from math_modeling.flow import group_services_by_flow, service_is_test
from math_modeling.models import Service
from math_modeling.path_qos import compose_qos
from math_modeling.qos_checker import check_qos

log = logging.getLogger("reroute_loop")

FlowKey = tuple[str, str]


class Phase(Enum):
    IDLE = "idle"            # 静默：等事件 / 等心跳
    SETTLING = "settling"    # 批已下发，等数据面稳定
    VERIFYING = "verifying"  # 采样比较「预测 vs 实测」


@dataclass
class OrchestratorConfig:
    # —— 感知 ——
    k: int = 30
    poll_interval: float = 1.0
    event_page_limit: int = 100
    excluded_link_ids: set[str] = field(default_factory=set)
    excluded_node_ids: set[str] = field(default_factory=set)
    weights: dict[str, float] | None = None
    plan_rho: float = 0.2
    # —— 收敛与节流（建议值，留作实验标定）——
    delta_min: float = 2.0              # Δmin：优先级加权收益门槛（单位 Σ2^priority，2^1 为最小）
    settle_s: float = 10.0              # 批后静置时长
    verify_windows: int = 5             # 校验采样窗数（1s 一窗）
    verify_votes: int = 3               # 判定达标/失配所需的票数
    corrective_rounds: int = 1          # 每个 epoch 允许的有界纠正轮数
    trigger_settle_s: float = 3.0       # 事件合窗：最后一个可行动事件静默多久才规划
    measured_check_interval_s: float = 60.0   # 静默期心跳间隔
    switch_min_interval_s: float = 10.0       # 同一 flow 两次改路的最小间隔
    pace_s: float = 0.1                 # 批内 POST 间隔（≈10 次/秒）
    max_batches_per_run: int = 60       # 全场下发批次上限（防"没有尽头"）
    skip_history: bool = True           # 启动时用服务器 tsUs 初始化事件游标，跳过历史事件


class Orchestrator:
    def __init__(
        self,
        client: SimulatorClient,
        config: OrchestratorConfig,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.client = client
        self.config = config
        self.executor = PathExecutor(client)
        self._clock = clock
        self._sleep = sleep
        # None = 尚未初始化（首轮用服务器时间对齐）；0 = 重放全部历史
        self.since_ts_us: int | None = None if config.skip_history else 0
        # —— 状态机 ——
        self._phase = Phase.IDLE
        self._deadline = 0.0
        self._force_epoch = False
        self._corrective = 0
        self._batches = 0
        # —— 本 epoch 上下文 ——
        self._plans: dict[FlowKey, FlowPlan] = {}
        self._predicted: dict[FlowKey, bool] = {}
        self._test_flow: dict[str, FlowKey] = {}
        self._votes: list[dict[FlowKey, bool | None]] = []
        self._next_sample = 0.0
        # —— 跨 epoch ——
        self._penalty: dict[FlowKey, set[tuple[str, ...]]] = {}
        self._last_switch: dict[FlowKey, float] = {}
        self._last_actionable = 0.0
        self._pending_actionable = False
        self._last_measured = 0.0

    # ------------------------------------------------------------------ 状态
    def refresh_graph(self) -> nx.MultiGraph:
        # 拓扑接口的 links 不带 params；链路 QoS 参数须从 /links 列表取
        nodes = parse_nodes(self.client.get_topology()["nodes"])
        links = parse_links(self.client.get_links().get("links", []))
        return build_graph(
            nodes, links,
            self.config.excluded_link_ids, self.config.excluded_node_ids,
        )

    def refresh_services(self) -> list[Service]:
        """拉 running 业务的完整详情（含 requirement/path/actual）。"""
        return [self._service_detail(s) for s in self._running_ids()]

    def _running_ids(self) -> list[str]:
        summaries = self.client.get_services().get("services", [])
        return [s["serviceId"] for s in summaries if s.get("status") == "running"]

    def _service_detail(self, service_id: str) -> Service:
        return Service.from_dict(self.client.get_service(service_id))

    # ------------------------------------------------------------------ 事件
    def _align_since_ts_us(self) -> int:
        """用仿真器服务器时间初始化事件游标，跳过启动前的历史事件。

        事件日志跨重启保留（`<netsim>/logs/run/sdnlab-openapi-events*.json`，
        环形 5 万条），`sinceTsUs=0` 会把上一轮的历史事件全部重放一遍，因此
        首轮取 `GET /time` 的 `tsUs` 作为游标起点。取不到则退化为 0（重放历史，
        只会多触发一次规划，不影响正确性）。
        """
        try:
            return int(self.client.get_time().get("tsUs") or 0)
        except Exception as e:  # noqa: BLE001
            log.warning("取服务器时间失败，事件游标从 0 开始（会重放历史事件）: %s", e)
            return 0

    def _poll_events(self) -> list[dict]:
        events = self.client.get_events(
            since_ts_us=self.since_ts_us or 0, limit=self.config.event_page_limit,
        )
        self.since_ts_us = events.get("nextSinceTsUs", self.since_ts_us)
        return events.get("events", [])

    @staticmethod
    def _actionable(events: list[dict]) -> list[dict]:
        """过滤出「值得重规划」的事件。

        `service_state_changed` 里 `pathChanged=true & status=running` 是**我们自己**
        下发路径的产物（`openapi.py` 的 `_set_service_path` 收尾会 `record_service`），
        必须忽略，否则每轮下发都会触发下一轮重规划。
        """
        out: list[dict] = []
        for e in events:
            etype = e.get("type")
            payload = e.get("payload") or {}
            if etype in ("link_state_changed", "node_state_changed"):
                out.append(e)
            elif etype == "service_state_changed":
                status = payload.get("status")
                if payload.get("pathChanged") and status == "running":
                    continue
                if status in ("stopped", "failed", "finished", "pending"):
                    out.append(e)
        return out

    # ------------------------------------------------------------------ 主循环
    def step(self, force: bool = False) -> int:
        """推进一次状态机；返回本次下发的 POST 条数（0 = 未动网）。"""
        if self.since_ts_us is None:
            self.since_ts_us = self._align_since_ts_us()
        actionable = self._actionable(self._poll_events())
        now = self._clock()
        if actionable:
            self._last_actionable = now
            self._pending_actionable = True
            if self._phase is Phase.SETTLING:
                log.warning(
                    "静置期内收到 %d 个可行动事件，中止本批并重开 epoch", len(actionable),
                )
                self._phase = Phase.IDLE
                self._force_epoch = True
                return 0

        if self._phase is Phase.SETTLING:
            if now < self._deadline:
                return 0
            self._phase = Phase.VERIFYING
            self._votes = []
            self._next_sample = now
            self._deadline = now + max(self.config.verify_windows, 1) * 2.0

        if self._phase is Phase.VERIFYING:
            return self._verify(now)

        # IDLE：决定要不要开新 epoch
        if force or self._force_epoch:
            self._force_epoch = False
            self._pending_actionable = False
            return self._epoch(now, corrective=self._corrective > 0)
        if self._pending_actionable and now - self._last_actionable >= self.config.trigger_settle_s:
            self._pending_actionable = False
            self._corrective = 0
            return self._epoch(now)
        if now - self._last_measured >= self.config.measured_check_interval_s:
            self._last_measured = now
            if self._heartbeat_violation():
                log.info("心跳命中：上一轮预测达标的 flow 出现实测违约，开新 epoch")
                self._corrective = 0
                return self._epoch(now)
        return 0

    # ------------------------------------------------------------------ epoch
    def _epoch(self, now: float, corrective: bool = False) -> int:
        if self._batches >= self.config.max_batches_per_run:
            log.warning(
                "已达全场批次预算 %d，停止主动优化（仅保留事件触发的修复）",
                self.config.max_batches_per_run,
            )
            return 0

        services = self.refresh_services()
        graph = self.refresh_graph()
        flows = group_services_by_flow(services)
        self._test_flow = {
            s.service_id: k for k, svcs in flows.items() for s in svcs if service_is_test(s)
        }
        current = {k: self._current_path(svcs) for k, svcs in flows.items()}
        cfg = PlanConfig(
            k=self.config.k, rho=self.config.plan_rho, weights=self.config.weights,
            excluded_paths=self._penalty,
        )
        plans = plan(flows, graph, cfg)
        predicted = predicted_meet(plans, graph, cfg)
        score_cur = score_with_paths(plans, graph, current, cfg)
        score_new = plan_score(plans, graph, cfg)
        gain = score_new - score_cur

        repairs: list[FlowKey] = []
        changed: list[tuple[FlowKey, FlowPlan]] = []
        for key, p in plans.items():
            if not p.path:
                continue
            if self._same_path(p.path, current.get(key) or []):
                continue
            if self._needs_repair(graph, key, current.get(key) or [], p.requirement):
                repairs.append(key)
            changed.append((key, p))

        if corrective:
            only = set(self._penalty.keys())
            batch = [(k, p) for k, p in changed if k in only]
        else:
            allow_improve = gain >= self.config.delta_min
            batch = [
                (k, p) for k, p in changed
                if k in repairs or (allow_improve and not p.cls.hard)
            ]

        if not batch:
            log.info(
                "epoch 收敛：changed=%d repair=%d Δscore=%.1f (Δmin=%.1f)，不下发",
                len(changed), len(repairs), gain, self.config.delta_min,
            )
            self._phase = Phase.IDLE
            return 0

        # 修复类优先（先恢复连通），其余按 flow_key 保证可复现
        batch.sort(key=lambda x: (x[0] not in repairs, x[0]))
        applied, applied_keys = self._apply_batch(batch, graph, now)
        if applied == 0:
            self._phase = Phase.IDLE
            return 0

        self._plans = plans
        # 只对**实际下发**的 flow 做「预测 vs 实测」比较：被防抖跳过的 flow
        # 仍停在旧路径上，把它们算进预测会造成假失配。
        self._predicted = {k: predicted[k] for k in applied_keys if k in predicted}
        self._batches += 1
        self._phase = Phase.SETTLING
        self._deadline = self._clock() + self.config.settle_s
        log.info(
            "epoch 下发 %d/%d 条 flow（repair=%d, Δscore=%.1f），静置 %.1fs 后校验",
            applied, len(batch), len(repairs), gain, self.config.settle_s,
        )
        return applied

    def _apply_batch(
        self, batch: list[tuple[FlowKey, FlowPlan]], graph: nx.MultiGraph, now: float,
    ) -> tuple[int, list[FlowKey]]:
        applied = 0
        applied_keys: list[FlowKey] = []
        for key, p in batch:
            if not p.path:
                continue
            last = self._last_switch.get(key)
            if last is not None and self._clock() - last < self.config.switch_min_interval_s:
                log.debug("flow %s 防抖中，跳过", key)
                continue
            if applied and self._actionable(self._poll_events()):
                log.warning("批内收到新事件，中止剩余 %d 条下发", len(batch) - applied)
                self._force_epoch = True
                break
            rep = p.services[0]
            # flow_key 是无序端点对；下发按该业务自身的 src→dst 方向
            link_ids = p.path if rep.src_node_id == key[0] else list(reversed(p.path))
            try:
                result = self.executor.execute(
                    rep.service_id, rep.src_node_id, rep.dst_node_id, link_ids, graph=graph,
                )
            except Exception as e:  # noqa: BLE001
                log.warning("flow %s 下发失败，中止本批: %s", key, e)
                break
            self._last_switch[key] = self._clock()
            applied += 1
            applied_keys.append(key)
            log.info("flow %s 重路由 -> %s: %s", key, rep.service_id, result.get("result"))
            if self.config.pace_s > 0:
                self._sleep(self.config.pace_s)
        return applied, applied_keys

    # ------------------------------------------------------------------ 校验
    def _verify(self, now: float) -> int:
        if len(self._votes) < self.config.verify_windows and now >= self._next_sample:
            self._votes.append(self._sample_meet())
            self._next_sample = now + 1.0
            if len(self._votes) < self.config.verify_windows and now < self._deadline:
                return 0

        observed = self._vote()
        bad = [
            k for k, pred in self._predicted.items()
            if pred and observed.get(k) is False
        ]
        for key in bad:
            plan_ = self._plans.get(key)
            if plan_ is not None and plan_.path:
                self._penalty.setdefault(key, set()).add(tuple(plan_.path))

        if bad and self._corrective < self.config.corrective_rounds:
            self._corrective += 1
            self._phase = Phase.IDLE
            self._force_epoch = True
            log.info(
                "校验失配 %d 个 flow（%s），进入第 %d 轮纠正",
                len(bad), bad, self._corrective,
            )
            return 0

        self._phase = Phase.IDLE
        self._corrective = 0
        if bad:
            log.warning("校验失配 %d 个 flow（%s）但已达纠正上限，收敛为 best-effort", len(bad), bad)
        else:
            log.info("epoch 完成：实测与预测一致")
        return 0

    def _sample_meet(self) -> dict[FlowKey, bool | None]:
        """只对 test 业务采样（`actual.qosMeet`），按 flow 聚合。"""
        votes: dict[FlowKey, list[bool]] = {}
        for sid, key in self._test_flow.items():
            try:
                s = self._service_detail(sid)
            except Exception as e:  # noqa: BLE001
                log.debug("采样 %s 失败: %s", sid, e)
                continue
            if s.actual is None or s.actual.qos_meet is None:
                continue
            votes.setdefault(key, []).append(bool(s.actual.qos_meet))
        return {
            k: (None if not v else all(v)) for k, v in votes.items()
        }

    def _vote(self) -> dict[FlowKey, bool | None]:
        need = max(1, min(self.config.verify_votes, len(self._votes) or 1))
        out: dict[FlowKey, bool | None] = {}
        for key in {k for sample in self._votes for k in sample}:
            ys = sum(1 for s in self._votes if s.get(key) is True)
            ns = sum(1 for s in self._votes if s.get(key) is False)
            if ys >= need:
                out[key] = True
            elif ns >= need:
                out[key] = False
            else:
                out[key] = None
        return out

    def _heartbeat_violation(self) -> bool:
        """静默期只检查「上一轮预测达标」的 flow，硬失败 flow 不参与，避免永不收敛。"""
        observed = self._sample_meet()
        if not observed:
            return False
        if not self._predicted:
            return any(v is False for v in observed.values())
        return any(observed.get(k) is False and self._predicted.get(k) for k in observed)

    # ------------------------------------------------------------------ 工具
    @staticmethod
    def _current_path(services: list[Service]) -> list[str]:
        for s in services:
            if s.path is not None and s.path.link_ids:
                return s.path.link_ids
        return []

    @staticmethod
    def _same_path(path: list[str], current: list[str]) -> bool:
        """flow 路径比较：仿真器存的方向取决于最后一次提交，必须容忍反序。"""
        if not current:
            return False
        return list(path) == list(current) or list(path) == list(current)[::-1]

    @staticmethod
    def _needs_repair(
        graph: nx.MultiGraph, key: FlowKey, current: list[str], requirement,
    ) -> bool:
        """现状路径是否需要「修复」：无路径 / 链路已断 / 静态 QoS 已违约。"""
        if not current:
            return True
        path = normalize_path(graph, key, current)
        if path is None:
            return True
        if requirement is not None and not check_qos(
            compose_qos(path, graph), requirement,
        ).feasible:
            return True
        return False

    def run(self) -> None:
        log.info("reroute_loop 启动，轮询间隔 %.1fs", self.config.poll_interval)
        # 首轮强制规划一次：skip_history 会跳过启动前的历史事件，不能指望
        # 靠事件触发首次规划。
        try:
            self.step(force=True)
        except KeyboardInterrupt:
            log.info("收到中断，退出")
            return
        except Exception as e:  # noqa: BLE001
            log.error("首轮规划异常: %s", e)
        while True:
            try:
                self.step()
            except KeyboardInterrupt:
                log.info("收到中断，退出")
                break
            except Exception as e:  # noqa: BLE001
                log.error("step 异常: %s", e)
            self._sleep(self.config.poll_interval)
