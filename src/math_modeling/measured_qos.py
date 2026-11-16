"""实测 QoS 反馈：test 业务保障率。

「待核对」：公开 API 无 `category` 字段，`Service.category` 恒为空，
`is_test` 恒为 False，因此本函数经公开 API 数据会恒返回 None。
test/background 分层需 ctrlToken 调内部 /api/ctrl/v1/svc-meta 才能取得；
MVP 阶段统一保护所有 running 业务，暂不依赖此口径。
"""
from __future__ import annotations

from math_modeling.models import Service


def test_meet_rate(services: list[Service]) -> float | None:
    """test 业务实测达标率（0~1）。

    只统计有实测数据（actual.qos_meet 非空）的 test 业务；
    无任何可统计的 test 业务返回 None。
    """
    test_svcs = [
        s for s in services
        if s.is_test and s.actual is not None and s.actual.qos_meet is not None
    ]
    if not test_svcs:
        return None
    met = sum(1 for s in test_svcs if s.actual.qos_meet)
    return met / len(test_svcs)
