"""运行指标聚合：把时间线折算成赛题要的可比指标。

覆盖指标：

| 指标 | 定义 | 来源 |
|---|---|---|
| 状态感知时间 | 从事件出现到感知完成 | `PERCEPTION` 条目的 `elapsed_s` |
| 策略生成时间 | 从感知完成到决策完成 | `DECISION` 条目的 `elapsed_s` |
| 策略下发时间 | 从决策完成到下发完成 | `DISPATCH` 条目的 `elapsed_s` |
| 动作计数 | 下发次数 / 涉及 flow 数 | `DISPATCH` 条目的 `detail` |
| 业务保障能力 | 预测达标数 / 实测达标数 | 由控制层回填 |

**关键**：baseline 与 agent 用**同一个** `RunMetrics` 聚合器，两侧指标才可比。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from common.observability.timeline import DecisionTimeline, EventKind


def _summarize(values: list[float]) -> dict[str, float]:
    """一组耗时的均值/极值/中位数（空组返回零值字典）。"""
    if not values:
        return {"count": 0, "mean_s": 0.0, "min_s": 0.0, "max_s": 0.0, "p50_s": 0.0, "total_s": 0.0}
    ordered = sorted(values)
    mid = len(ordered) // 2
    p50 = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
    return {
        "count": len(ordered),
        "mean_s": sum(ordered) / len(ordered),
        "min_s": ordered[0],
        "max_s": ordered[-1],
        "p50_s": p50,
        "total_s": sum(ordered),
    }


@dataclass
class RunMetrics:
    """一次 run（整场仿真）的指标汇总。"""

    perception: dict[str, float] = field(default_factory=dict)
    decision: dict[str, float] = field(default_factory=dict)
    dispatch: dict[str, float] = field(default_factory=dict)
    dispatch_count: int = 0
    dispatched_flows: int = 0
    predicted_compliant: int = 0
    measured_compliant: int = 0
    total_services: int = 0

    def to_dict(self) -> dict:
        return {
            "perception": self.perception,
            "decision": self.decision,
            "dispatch": self.dispatch,
            "dispatch_count": self.dispatch_count,
            "dispatched_flows": self.dispatched_flows,
            "predicted_compliant": self.predicted_compliant,
            "measured_compliant": self.measured_compliant,
            "total_services": self.total_services,
        }


def collect_metrics(
    timeline: DecisionTimeline,
    *,
    predicted_compliant: int = 0,
    measured_compliant: int = 0,
    total_services: int = 0,
) -> RunMetrics:
    """从时间线聚合出运行指标。

    - `perception` / `decision` / `dispatch` 三组耗时取各自条目的 `elapsed_s`；
    - `dispatch_count` = `DISPATCH` 条目数；`dispatched_flows` = 各条目
      `detail["flow_count"]` 之和（缺省按 1 计）。
    """
    durations = timeline.durations_by_kind()
    dispatches = timeline.of_kind(EventKind.DISPATCH)
    return RunMetrics(
        perception=_summarize(durations.get(EventKind.PERCEPTION.value, [])),
        decision=_summarize(durations.get(EventKind.DECISION.value, [])),
        dispatch=_summarize(durations.get(EventKind.DISPATCH.value, [])),
        dispatch_count=len(dispatches),
        dispatched_flows=sum(int(e.detail.get("flow_count", 1)) for e in dispatches),
        predicted_compliant=predicted_compliant,
        measured_compliant=measured_compliant,
        total_services=total_services,
    )
