"""决策时间线：记录一次 run 里每个关键动作的**时刻**与**耗时**。

三类时间戳（对应赛题指标）：

| 事件 | 含义 | 对应指标 |
|---|---|---|
| `perception` | 感知完成（快照已冻结） | 状态感知时间 |
| `decision` | 决策完成（规划/建议已产出） | 策略生成时间 |
| `dispatch` | 下发完成（路径已 POST） | 策略下发时间 |

时间基准用**单调时钟**（`time.monotonic`），避免 NTP 调整影响计时；墙钟时间另行记录
（`wall_time`）仅用于日志与跨 run 对齐，不用于算耗时。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class EventKind(str, Enum):
    """时间线事件类型。"""

    PERCEPTION = "perception"   # 感知完成
    DECISION = "decision"       # 决策完成
    DISPATCH = "dispatch"       # 下发完成
    VERIFICATION = "verification"  # 实测校验完成


@dataclass
class TimelineEntry:
    """时间线上的一条记录。"""

    kind: EventKind
    label: str                                  # 人类可读的动作描述
    monotonic_at: float                         # 单调时钟时刻
    wall_time: float                            # 墙钟时刻（仅供日志对齐）
    elapsed_s: float = 0.0                      # 距上一条同类/相邻事件的间隔
    detail: dict = field(default_factory=dict)  # 附加信息（如 flow_key、路径、Δscore）

    def to_dict(self) -> dict:
        return {
            "kind": self.kind.value,
            "label": self.label,
            "monotonic_at": round(self.monotonic_at, 6),
            "wall_time": round(self.wall_time, 6),
            "elapsed_s": round(self.elapsed_s, 6),
            "detail": self.detail,
        }


class DecisionTimeline:
    """按时间顺序累积决策动作，并给出各类动作的耗时统计。

    用法（baseline 与 agent 相同）：

    ```
    timeline = DecisionTimeline()
    timeline.mark(EventKind.PERCEPTION, "冻结快照")
    timeline.mark(EventKind.DECISION, "规划完成", detail={"gain": 12.0})
    timeline.mark(EventKind.DISPATCH, "下发 3 条路径")
    ```
    """

    def __init__(self, *, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._entries: list[TimelineEntry] = []
        self._last_at: float | None = None

    def mark(
        self,
        kind: EventKind,
        label: str,
        *,
        wall_time: float | None = None,
        **detail,
    ) -> TimelineEntry:
        """记录一条事件；`elapsed_s` = 距上一条事件的间隔。"""
        now = self._clock()
        elapsed = 0.0 if self._last_at is None else now - self._last_at
        self._last_at = now
        entry = TimelineEntry(
            kind=kind,
            label=label,
            monotonic_at=now,
            wall_time=time.time() if wall_time is None else wall_time,
            elapsed_s=elapsed,
            detail=detail,
        )
        self._entries.append(entry)
        return entry

    @property
    def entries(self) -> list[TimelineEntry]:
        return list(self._entries)

    def of_kind(self, kind: EventKind) -> list[TimelineEntry]:
        """某类事件的所有记录。"""
        return [e for e in self._entries if e.kind is kind]

    def durations_by_kind(self) -> dict[str, list[float]]:
        """按事件类型收集 `elapsed_s`（用于算均值/分位数）。"""
        out: dict[str, list[float]] = {}
        for entry in self._entries:
            out.setdefault(entry.kind.value, []).append(entry.elapsed_s)
        return out

    def to_dicts(self) -> list[dict]:
        """导出为可 JSON 序列化的列表。"""
        return [e.to_dict() for e in self._entries]
