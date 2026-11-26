"""主控制循环：事件/实测驱动的流级重路由（epoch 状态机）。

设计要点（见 `docs/baseline/传统基线选路方案.md` §5.6-§5.9）：

**一个 epoch = 一次冻结快照 + 一次规划 + 一个下发批 + 一次校验。**

1. **触发**：只认可行动事件（链路状态/参数变化、节点上下线、业务状态变为非 running），
   **忽略自己下发产生的 `service_state_changed(pathChanged=true, status=running)`**，
   否则 POST → 事件 → 重规划 → POST 会自激成死循环（过滤见 `event_source.py`）。
   事件成簇到达时先合窗（`event_coalesce_s`）再规划，避免一条事件簇触发多次全量规划。
2. **规划是纯函数、下发是增量**：同一快照重算结果完全一致（快照见 `snapshot.py`）；
   下发闸门（修复 / Δmin）见 `dispatch_gate.py`，只有「路径失效」（修复）或
   「加权达标数增益 ≥ `min_gain_threshold`」才下发，其余一律不动。
3. **批内不重算**：批是一次计划的执行，中途重算等于换计划、把瞬态无限延长。
   批内若收到新的可行动事件，直接中止剩余下发并用新快照重开 epoch。
4. **批后静置 + 校验**：`batch_settle_s` 后按多个 1s 窗投票，比较「预测达标」与
   「实测达标」；失配的路径进惩罚集（下一轮候选剔除），纠正轮数有上限
   （`corrective_round_limit`），裁决逻辑见 `verifier.py`。
5. **静默期**：收敛后只做低频心跳（`heartbeat_interval_s`），且只对**上一轮预测达标**
   的 flow 检查 —— 物理上救不回来的 flow（F1/F2）不参与判据，否则永远不收敛。

本文件只保留「状态机 + epoch 编排」；感知（`event_source` / `snapshot`）、
闸门（`dispatch_gate`）、裁决（`verifier`）各自独立成模块。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

import networkx as nx

from common.algorithms.flow.planner import PlanConfig, plan, predicted_compliance
from common.simulator.client import SimulatorClient
from common.simulator.executor import PathExecutor
from common.control.dispatch_gate import DispatchBatch, build_dispatch_batch
from common.perception.events import EventSource
from common.perception.snapshot import SnapshotSource
from common.control.verifier import PathVerifier, VerifyOutcome
from common.modeling.flow import FlowKey

log = logging.getLogger("reroute_loop")


class Phase(Enum):
    IDLE = "idle"            # 静默：等事件 / 等心跳
    SETTLING = "settling"    # 批已下发，等数据面稳定
    VERIFYING = "verifying"  # 采样比较「预测 vs 实测」


@dataclass
class OrchestratorConfig:
    # —— 感知 ——
    candidate_path_count: int = 30         # 每 flow 的候选路径条数（K-最短）
    poll_interval_s: float = 1.0           # 主循环轮询间隔
    event_page_limit: int = 100            # 事件分页大小
    excluded_link_ids: set[str] = field(default_factory=set)  # 构图剔除的链路
    excluded_node_ids: set[str] = field(default_factory=set)  # 构图剔除的节点（如 EXT001）
    link_cost_weights: dict[str, float] | None = None         # 链路代价权重（排序用）
    bandwidth_headroom: float = 0.2        # 摆放裕度 ρ（与 utilization_limit 是两个阈值）
    # —— 下发闸门 ——
    min_gain_threshold: float = 2.0        # Δmin：优先级加权收益门槛（单位 Σ2^priority，2^1 为最小）
    min_switch_interval_s: float = 10.0    # 同一 flow 两次改路的最小间隔（防抖）
    batch_pace_s: float = 0.1              # 批内 POST 间隔（≈10 次/秒）
    max_batches_per_run: int = 60          # 全场下发批次上限（防"没有尽头"）
    # —— 收敛与节流（建议值，留作实验标定）——
    batch_settle_s: float = 10.0           # 批后静置时长
    verify_window_count: int = 5           # 校验采样窗数（1s 一窗）
    verify_required_votes: int = 3         # 判定达标/失配所需的票数
    corrective_round_limit: int = 1        # 每个 epoch 允许的有界纠正轮数
    event_coalesce_s: float = 3.0          # 事件合窗：最后一个可行动事件静默多久才规划
    heartbeat_interval_s: float = 60.0     # 静默期心跳间隔
    skip_history: bool = True              # 启动时用服务器 tsUs 初始化事件游标，跳过历史事件


class Orchestrator:
    """epoch 状态机：IDLE（触发）→ SETTLING（静置）→ VERIFYING（校验）→ …"""

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
        # —— 感知与裁决组件（各自持有自己的状态）——
        self.events = EventSource(
            client, page_limit=config.event_page_limit, skip_history=config.skip_history,
        )
        self.snapshots = SnapshotSource(
            client,
            excluded_link_ids=config.excluded_link_ids,
            excluded_node_ids=config.excluded_node_ids,
        )
        self.verifier = PathVerifier(
            client,
            window_count=config.verify_window_count,
            required_votes=config.verify_required_votes,
            corrective_round_limit=config.corrective_round_limit,
        )
        # —— 状态机 ——
        self.phase = Phase.IDLE
        self._settle_deadline = 0.0
        self._force_epoch = False
        self.batch_count = 0
        # —— 跨 epoch 节流 ——
        self._last_actionable = 0.0
        self._pending_actionable = False
        self._last_heartbeat = 0.0
        self._last_switch: dict[FlowKey, float] = {}

    # ------------------------------------------------------------------ 主循环
    def step(self, force: bool = False) -> int:
        """推进一次状态机；返回本次下发的 POST 条数（0 = 未动网）。"""
        actionable = self.events.poll_actionable()
        now = self._clock()
        if actionable:
            self._last_actionable = now
            self._pending_actionable = True
            if self.phase is Phase.SETTLING:
                log.warning(
                    "静置期内收到 %d 个可行动事件，中止本批并重开 epoch", len(actionable),
                )
                self.phase = Phase.IDLE
                self._force_epoch = True
                return 0

        if self.phase is Phase.SETTLING:
            if now < self._settle_deadline:
                return 0
            self.phase = Phase.VERIFYING
            self.verifier.begin_round(now)

        if self.phase is Phase.VERIFYING:
            return self._verify(now)

        # IDLE：决定要不要开新 epoch
        if force or self._force_epoch:
            self._force_epoch = False
            self._pending_actionable = False
            return self._run_epoch(corrective=self.verifier.corrective_pending)
        if self._pending_actionable and now - self._last_actionable >= self.config.event_coalesce_s:
            self._pending_actionable = False
            self.verifier.reset_correction()
            return self._run_epoch()
        if now - self._last_heartbeat >= self.config.heartbeat_interval_s:
            self._last_heartbeat = now
            if self.verifier.heartbeat_violation():
                log.info("心跳命中：上一轮预测达标的 flow 出现实测违约，开新 epoch")
                self.verifier.reset_correction()
                return self._run_epoch()
        return 0

    def run(self) -> None:
        log.info("reroute_loop 启动，轮询间隔 %.1fs", self.config.poll_interval_s)
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
            self._sleep(self.config.poll_interval_s)

    # ------------------------------------------------------------------ epoch
    def _run_epoch(self, corrective: bool = False) -> int:
        """冻结快照 → 规划 → 过闸门 → 下发批（可能为空 = 收敛，不动网）。"""
        if self.batch_count >= self.config.max_batches_per_run:
            log.warning(
                "已达全场批次预算 %d，停止主动优化（仅保留事件触发的修复）",
                self.config.max_batches_per_run,
            )
            return 0

        snapshot = self.snapshots.fetch()
        self.verifier.set_test_scope(snapshot.test_service_flow)
        plan_config = PlanConfig(
            candidate_path_count=self.config.candidate_path_count,
            bandwidth_headroom=self.config.bandwidth_headroom,
            link_cost_weights=self.config.link_cost_weights,
            excluded_paths=self.verifier.penalized_paths,
        )
        plans = plan(snapshot.flows, snapshot.graph, plan_config)
        predicted = predicted_compliance(plans, snapshot.graph, plan_config)
        batch = build_dispatch_batch(
            plans, snapshot.current_paths, snapshot.graph, plan_config,
            min_gain=self.config.min_gain_threshold,
            restrict_to_keys=set(self.verifier.penalized_paths) if corrective else None,
        )

        if not batch.entries:
            log.info(
                "epoch 收敛：changed=%d repair=%d Δscore=%.1f (Δmin=%.1f)，不下发",
                len(batch.changed), len(batch.repairs), batch.score_gain,
                self.config.min_gain_threshold,
            )
            self.phase = Phase.IDLE
            return 0

        applied, applied_keys = self._dispatch(batch, snapshot.graph)
        if applied == 0:
            self.phase = Phase.IDLE
            return 0

        self.verifier.record_dispatch(plans, predicted, applied_keys)
        self.batch_count += 1
        self.phase = Phase.SETTLING
        self._settle_deadline = self._clock() + self.config.batch_settle_s
        log.info(
            "epoch 下发 %d/%d 条 flow（repair=%d, Δscore=%.1f），静置 %.1fs 后校验",
            applied, len(batch.entries), len(batch.repairs), batch.score_gain,
            self.config.batch_settle_s,
        )
        return applied

    def _dispatch(self, batch: DispatchBatch, graph: nx.MultiGraph) -> tuple[int, list[FlowKey]]:
        """执行一个下发批：防抖 → 逐条 POST（批内不重算，新事件即中止）。"""
        applied = 0
        applied_keys: list[FlowKey] = []
        for key, plan_item in batch.entries:
            if not plan_item.path:
                continue
            last = self._last_switch.get(key)
            if last is not None and self._clock() - last < self.config.min_switch_interval_s:
                log.debug("flow %s 防抖中，跳过", key)
                continue
            if applied and self.events.poll_actionable():
                log.warning("批内收到新事件，中止剩余 %d 条下发", len(batch.entries) - applied)
                self._force_epoch = True
                break
            # flow_key 是无序端点对；下发按该业务自身的 src→dst 方向
            representative = plan_item.services[0]
            link_ids = (
                plan_item.path
                if representative.src_node_id == key[0]
                else list(reversed(plan_item.path))
            )
            try:
                result = self.executor.execute(
                    representative.service_id, representative.src_node_id,
                    representative.dst_node_id, link_ids, graph=graph,
                )
            except Exception as e:  # noqa: BLE001
                log.warning("flow %s 下发失败，中止本批: %s", key, e)
                break
            self._last_switch[key] = self._clock()
            applied += 1
            applied_keys.append(key)
            log.info(
                "flow %s 重路由 -> %s: %s", key, representative.service_id, result.get("result"),
            )
            if self.config.batch_pace_s > 0:
                self._sleep(self.config.batch_pace_s)
        return applied, applied_keys

    # ------------------------------------------------------------------ 校验
    def _verify(self, now: float) -> int:
        """采样期满则裁决：失配进惩罚集并（有轮次时）重开纠正 epoch。"""
        outcome: VerifyOutcome | None = self.verifier.verify(now)
        if outcome is None:
            return 0
        self.phase = Phase.IDLE
        if outcome.corrective_round:
            self._force_epoch = True
            log.info(
                "校验失配 %d 个 flow（%s），进入第 %d 轮纠正",
                len(outcome.mismatches), outcome.mismatches, outcome.corrective_round,
            )
            return 0
        if outcome.mismatches:
            log.warning(
                "校验失配 %d 个 flow（%s）但已达纠正上限，收敛为 best-effort",
                len(outcome.mismatches), outcome.mismatches,
            )
        else:
            log.info("epoch 完成：实测与预测一致")
        return 0
