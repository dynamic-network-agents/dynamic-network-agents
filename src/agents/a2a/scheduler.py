"""任务调度：把运维/控制两类智能体的工作项排成一条确定的执行序列。

**调度模型**：两个智能体**不是并行跑**的——仿真环境是单线程轮询的观测源，
并行只会引入竞态与不可复现。因此调度是「角色轮转」：

```
运维感知 → 运维诊断 → 控制决策 → 控制下发 → 仲裁 → 回到运维感知
```

每一轮产出一组「工作项」，`TaskScheduler` 决定**谁先做、做什么**，并保证：

- **依赖序**：控制决策依赖运维诊断的结果，故必须在其后；
- **预算**：每轮最多处理 N 个工作项（防止 LLM 调用打满预算）；
- **可复现**：同样的输入 + 同样的仲裁结果 → 同样的执行序（无时间/随机依赖）。

LLM 调用预算在此统一管控：`max_items_per_round` 与 `max_rounds` 是两个硬闸门，
避免"没有尽头"的 LLM 循环——这与 baseline 的 `max_batches_per_run` 同一思想。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TaskRole(str, Enum):
    """工作项角色。"""

    PERCEPTION = "perception"   # 运维：态势采集
    DIAGNOSIS = "diagnosis"     # 运维：异常检测与故障诊断
    DECISION = "decision"       # 控制：资源调度决策
    DISPATCH = "dispatch"       # 控制：路径下发


#: 角色在单轮内的执行顺序（依赖序）。
ROUND_ORDER: tuple[TaskRole, ...] = (
    TaskRole.PERCEPTION,
    TaskRole.DIAGNOSIS,
    TaskRole.DECISION,
    TaskRole.DISPATCH,
)


@dataclass
class WorkItem:
    """一个待处理工作项。"""

    role: TaskRole
    key: str                              # 作用对象标识（flow_key / 事件 id / 服务 id）
    payload: dict = field(default_factory=dict)
    llm_required: bool = False            # 是否需要 LLM 参与


@dataclass
class ScheduleConfig:
    """调度预算。"""

    max_items_per_round: int = 8    # 单轮最多处理的工作项数（LLM 调用预算）
    max_rounds: int = 0             # 全场轮数上限（0 = 不限，由场景事件窗口收敛）


@dataclass
class ScheduleResult:
    """一轮调度的结果。"""

    scheduled: list[WorkItem] = field(default_factory=list)
    skipped: list[WorkItem] = field(default_factory=list)
    reason_skipped: str = ""

    @property
    def llm_calls_planned(self) -> int:
        """本轮预计的 LLM 调用次数（用于预算预估）。"""
        return sum(1 for item in self.scheduled if item.llm_required)


class TaskScheduler:
    """按依赖序 + 预算产出每一轮的执行序列。"""

    def __init__(self, config: ScheduleConfig | None = None):
        self.config = config or ScheduleConfig()
        self.rounds_done = 0

    def schedule_round(self, items: list[WorkItem]) -> ScheduleResult:
        """排一轮：按 `ROUND_ORDER` 排序 → 截断到预算 → 记轮数。

        截断时保留**高优先级角色在前**（感知/诊断先于决策/下发），保证被预算
        截断时不会只剩下发而没有依据。
        """
        if self.config.max_rounds and self.rounds_done >= self.config.max_rounds:
            return ScheduleResult(reason_skipped="已达最大轮数上限")

        ordered = sorted(
            items,
            key=lambda item: (
                ROUND_ORDER.index(item.role),
                item.key,
            ),
        )
        limit = self.config.max_items_per_round
        if limit and len(ordered) > limit:
            skipped = ordered[limit:]
            ordered = ordered[:limit]
            result = ScheduleResult(scheduled=ordered, skipped=skipped,
                                    reason_skipped=f"超出单轮预算 {limit} 项")
        else:
            result = ScheduleResult(scheduled=ordered)
        self.rounds_done += 1
        return result

    @property
    def exhausted(self) -> bool:
        """是否已耗尽全场轮数预算（停止条件之一）。"""
        return bool(self.config.max_rounds) and self.rounds_done >= self.config.max_rounds
