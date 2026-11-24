"""写操作策略：全项目唯一的写动作（改 service 路径）是否放行的判定。

抽成独立模块的原因：
1. 仿真器把 `POST /services/{id}/path` 一律记成 `source=agent` 的 path 事件，
   无论用哪张令牌都躲不开；正式录分需要一键关掉，避免污染 agent-events；
2. 该判定不依赖 FastAPI/仿真器，便于单元测试。
"""
from __future__ import annotations


class RepathDisabled(PermissionError):
    """工作台写开关已关闭。"""


DISABLED_MSG = (
    "改路径已禁用（WORKBENCH_ALLOW_REPATH=0）：该写动作会被仿真器记为 source=agent 的 "
    "path 事件，正式录制/评分期间请保持关闭；调试时置 WORKBENCH_ALLOW_REPATH=1 后重启后端。"
)

EVENT_RECORD_WARNING = (
    "本次改路径已被仿真器记为 source=agent 的 path 事件（tokenId 为工作台的 ctrl 令牌）；"
    "正式跑/录分时请勿使用工作台改路径，改用官方前端或直接重跑。"
)


def ensure_repath_allowed(enabled: bool) -> None:
    if not enabled:
        raise RepathDisabled(DISABLED_MSG)
