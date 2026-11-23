"""实测 QoS 反馈：test 业务保障率。

已知限制（已核实，非待办）：公开 API 无 `category` 字段，`Service.category`
恒为空、`Service.is_test` 恒为 False；test/background 分层只有 ctrlToken 调内部
`/api/ctrl/v1/svc-meta` 才能取得。为与 planner 的 test 口径一致，本模块用
`flow.service_is_test()`（category 优先，缺失时按 `TSV*` 前缀兜底）判定。
"""
from __future__ import annotations

from math_modeling.flow import service_is_test
from math_modeling.models import Service


def test_meet_rate(services: list[Service]) -> float | None:
    """test 业务实测达标率（0~1）。

    只统计有实测数据（actual.qos_meet 非空）的 test 业务；
    无任何可统计的 test 业务返回 None。
    """
    test_svcs = [
        s for s in services
        if service_is_test(s) and s.actual is not None and s.actual.qos_meet is not None
    ]
    if not test_svcs:
        return None
    met = sum(1 for s in test_svcs if s.actual.qos_meet)
    return met / len(test_svcs)
