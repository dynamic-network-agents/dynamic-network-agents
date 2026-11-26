"""事件感知：事件游标维护 + 可行动事件过滤。

时间口径（详见 `docs/baseline/传统基线选路方案.md` §5.6）：

- `sinceTsUs` 是仿真器事件日志**自己的**时间轴（Unix 纪元微秒，服务器时钟），
  服务端按 `event.tsUs > sinceTsUs` 严格过滤，所以只需原样回传 `nextSinceTsUs`，
  **不需要把本地时钟对齐到仿真器**。
- 启动时用 `GET /time` 的 `tsUs` 初始化游标，只是为了不从 0 开始重放历史事件
  （事件日志跨重启保留，`sinceTsUs=0` 会把上一轮的历史事件全部重放一遍）。
- 轮询、合窗、防抖等计时由调用方（`Orchestrator`）用单调时钟 `time.monotonic()`
  负责，本模块只管「取事件、认事件」。
"""
from __future__ import annotations

import logging

from common.simulator.client import SimulatorClient

log = logging.getLogger("reroute_loop.event_source")


def filter_actionable(events: list[dict]) -> list[dict]:
    """过滤出「值得重规划」的事件。

    `service_state_changed` 里 `pathChanged=true & status=running` 是**我们自己**
    下发路径的产物（仿真器 `openapi.py` 的 `_set_service_path` 收尾会 `record_service`），
    必须忽略，否则每轮下发都会触发下一轮重规划，POST → 事件 → 重规划 → POST
    会自激成死循环。
    """
    actionable: list[dict] = []
    for event in events:
        event_type = event.get("type")
        payload = event.get("payload") or {}
        if event_type in ("link_state_changed", "node_state_changed"):
            actionable.append(event)
        elif event_type == "service_state_changed":
            status = payload.get("status")
            if payload.get("pathChanged") and status == "running":
                continue  # 自己下发产生的事件，忽略
            if status in ("stopped", "failed", "finished", "pending"):
                actionable.append(event)
    return actionable


class EventSource:
    """仿真器事件日志的增量拉取器（维护 `sinceTsUs` 游标）。"""

    def __init__(
        self,
        client: SimulatorClient,
        *,
        page_limit: int = 100,
        skip_history: bool = True,
    ):
        self._client = client
        self._page_limit = page_limit
        # None = 尚未初始化（首轮用服务器时间对齐）；0 = 重放全部历史
        self.since_ts_us: int | None = None if skip_history else 0

    def poll(self) -> list[dict]:
        """拉取游标之后的新事件并推进游标；首轮先用服务器时间初始化游标。"""
        if self.since_ts_us is None:
            self.since_ts_us = self._server_time_cursor()
        page = self._client.get_events(
            since_ts_us=self.since_ts_us or 0, limit=self._page_limit,
        )
        self.since_ts_us = page.get("nextSinceTsUs", self.since_ts_us)
        return page.get("events", [])

    def poll_actionable(self) -> list[dict]:
        """`poll()` + `filter_actionable()`。"""
        return filter_actionable(self.poll())

    def _server_time_cursor(self) -> int:
        """用仿真器服务器时间初始化事件游标，跳过启动前的历史事件。

        事件日志跨重启保留（`<netsim>/logs/run/sdnlab-openapi-events*.json`，
        环形 5 万条），`sinceTsUs=0` 会把上一轮的历史事件全部重放一遍，因此
        首轮取 `GET /time` 的 `tsUs` 作为游标起点。取不到则退化为 0（重放历史，
        只会多触发一次规划，不影响正确性）。
        """
        try:
            return int(self._client.get_time().get("tsUs") or 0)
        except Exception as e:  # noqa: BLE001
            log.warning("取服务器时间失败，事件游标从 0 开始（会重放历史事件）: %s", e)
            return 0
