"""校验器：批后静置的「预测 vs 实测」采样投票 + 惩罚集 + 静默期心跳。

对应设计要点 4/5（见 `docs/baseline/传统基线选路方案.md` §5.8）：

- **多窗投票**：批下发后静置，按多个 1s 窗对 test 业务的 `actual.qosMeet` 采样，
  票数过门槛（`required_votes`）才判定该 flow 达标/失配，抵消瞬态抖动。
- **惩罚集**：预测达标但实测失配的 flow，本轮路径记入 `penalized_paths`，
  下一轮规划经 `PlanConfig.excluded_paths` 剔除（无其它候选时回退）。
- **有界纠正**：纠正轮数上限 `corrective_round_limit`，用尽后收敛为 best-effort，
  不再无限换路径。
- **静默期心跳**：只检查**上一轮预测达标**的 flow —— 物理上救不回来的 flow
  （F1/F2）不参与判据，否则永远不收敛。

本模块负责「怎么采、怎么判、罚哪条路径」；**状态转移与日志**由 `Orchestrator` 负责。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from common.simulator.client import SimulatorClient
from common.algorithms.flow.planner import FlowPlan
from common.modeling.flow import FlowKey
from common.modeling.models import Service

log = logging.getLogger("reroute_loop.verifier")


@dataclass
class VerifyOutcome:
    """一轮校验的结论（`verify()` 返回 None 表示窗口未满、继续采样）。"""

    mismatches: list[FlowKey] = field(default_factory=list)  # 预测达标但实测失配
    corrective_round: int = 0                                 # >0：进入第 N 轮纠正；0：不纠正


class PathVerifier:
    """「预测 vs 实测」的采样与裁决（跨 epoch 持有惩罚集）。"""

    def __init__(
        self,
        client: SimulatorClient,
        *,
        window_count: int = 5,
        required_votes: int = 3,
        corrective_round_limit: int = 1,
    ):
        self._client = client
        self._window_count = max(window_count, 1)
        self._required_votes = required_votes
        self._corrective_round_limit = corrective_round_limit
        # —— 跨 epoch ——
        self.penalized_paths: dict[FlowKey, set[tuple[str, ...]]] = {}  # 惩罚集
        self._corrective_round = 0
        # —— 本 epoch 上下文 ——
        self._plans: dict[FlowKey, FlowPlan] = {}     # 本轮下发的计划（失配时取其路径记罚）
        self._predicted: dict[FlowKey, bool] = {}     # 实际下发 flow 的预测达标
        self._test_service_flow: dict[str, FlowKey] = {}  # test 业务采样范围
        # —— 本轮采样 ——
        self._votes: list[dict[FlowKey, bool | None]] = []
        self._next_sample = 0.0
        self._sample_deadline = 0.0

    # ---------------------------------------------------------------- 本 epoch 上下文
    def set_test_scope(self, test_service_flow: dict[str, FlowKey]) -> None:
        """登记 test 业务采样范围（每 epoch 刷新；心跳也用上一轮的范围）。"""
        self._test_service_flow = test_service_flow

    def record_dispatch(
        self,
        plans: dict[FlowKey, FlowPlan],
        predicted: dict[FlowKey, bool],
        applied_keys: list[FlowKey],
    ) -> None:
        """登记本轮**实际下发**的计划与预测。

        只记 applied 的 flow：被防抖跳过的 flow 仍停在旧路径上，
        把它们算进预测会造成假失配。
        """
        self._plans = plans
        self._predicted = {k: predicted[k] for k in applied_keys if k in predicted}

    # ---------------------------------------------------------------- 纠正轮状态
    @property
    def corrective_pending(self) -> bool:
        """上一轮校验是否要求纠正（Orchestrator 开 epoch 时读取）。"""
        return self._corrective_round > 0

    def reset_correction(self) -> None:
        """清除纠正状态（事件/心跳触发的全新 epoch 不沿用纠正轮）。"""
        self._corrective_round = 0

    # ---------------------------------------------------------------- 校验轮
    def begin_round(self, now: float) -> None:
        """静置结束、开始采样：清空票箱，设 1s 采样节拍与超时截止。"""
        self._votes = []
        self._next_sample = now
        # 采样总时长上界 = 窗数 × 2s（窗数不足 1 时按 1 窗计）
        self._sample_deadline = now + max(self._window_count, 1) * 2.0

    def verify(self, now: float) -> VerifyOutcome | None:
        """到点采一窗；窗口期满则汇总投票并裁决，否则返回 None 继续采样。"""
        if len(self._votes) < self._window_count and now >= self._next_sample:
            self._votes.append(self._sample_meet())
            self._next_sample = now + 1.0
            if len(self._votes) < self._window_count and now < self._sample_deadline:
                return None
        return self._resolve()

    def _resolve(self) -> VerifyOutcome:
        """汇总投票 → 找出失配 → 记入惩罚集 → 判定是否还有纠正轮次。"""
        observed = self._tally()
        mismatches = [
            key for key, predicted in self._predicted.items()
            if predicted and observed.get(key) is False
        ]
        for key in mismatches:
            plan = self._plans.get(key)
            if plan is not None and plan.path:
                self.penalized_paths.setdefault(key, set()).add(tuple(plan.path))
        if mismatches and self._corrective_round < self._corrective_round_limit:
            self._corrective_round += 1
            return VerifyOutcome(mismatches=mismatches, corrective_round=self._corrective_round)
        self._corrective_round = 0
        return VerifyOutcome(mismatches=mismatches)

    def _sample_meet(self) -> dict[FlowKey, bool | None]:
        """只对 test 业务采样（`actual.qosMeet`），按 flow 聚合。"""
        votes: dict[FlowKey, list[bool]] = {}
        for service_id, key in self._test_service_flow.items():
            try:
                service = Service.from_dict(self._client.get_service(service_id))
            except Exception as e:  # noqa: BLE001
                log.debug("采样 %s 失败: %s", service_id, e)
                continue
            if service.actual is None or service.actual.qos_meet is None:
                continue
            votes.setdefault(key, []).append(bool(service.actual.qos_meet))
        return {key: (None if not flags else all(flags)) for key, flags in votes.items()}

    def _tally(self) -> dict[FlowKey, bool | None]:
        """多窗投票：达标/失配任一侧票数过门槛才定，否则记 None（样本不足）。"""
        need = max(1, min(self._required_votes, len(self._votes) or 1))
        outcome: dict[FlowKey, bool | None] = {}
        for key in {k for sample in self._votes for k in sample}:
            meet_votes = sum(1 for s in self._votes if s.get(key) is True)
            miss_votes = sum(1 for s in self._votes if s.get(key) is False)
            if meet_votes >= need:
                outcome[key] = True
            elif miss_votes >= need:
                outcome[key] = False
            else:
                outcome[key] = None
        return outcome

    # ---------------------------------------------------------------- 静默期心跳
    def heartbeat_violation(self) -> bool:
        """静默期心跳：上一轮预测达标的 flow 出现实测违约？（否则不触发 epoch）"""
        observed = self._sample_meet()
        if not observed:
            return False
        if not self._predicted:
            return any(v is False for v in observed.values())
        return any(
            observed.get(key) is False and self._predicted.get(key)
            for key in observed
        )
