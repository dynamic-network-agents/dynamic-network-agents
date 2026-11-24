"""数据契约（pydantic）。

目的：把"仿真器返回什么"与"前端消费什么"固化成可校验的模型，
让字段缺失/类型错误在采集层就暴露，而不是变成前端的 `undefined`。

约定：
- 所有模型 `extra="allow"`：仿真器新增字段不丢，也不因未知字段报错；
- 字段名与仿真器/现有快照保持一致（前端 types.ts 对齐）；
- `snapshot_version` 只在结构发生破坏性变更时 +1。
"""
from __future__ import annotations

from .snapshot import (
    Actual,
    Flow,
    Link,
    LinkLoad,
    LinkParams,
    LinkRisk,
    Node,
    OverallStatus,
    Pagination,
    QoSComposed,
    Position,
    Requirement,
    ResourcePage,
    RiskSummary,
    Service,
    ServicePath,
    SimStatus,
    Snapshot,
    StaticCheck,
    StaticCheckItem,
    SvcMeta,
    SvcMetaStatus,
)

__all__ = [
    "Actual",
    "Flow",
    "Link",
    "LinkLoad",
    "LinkParams",
    "LinkRisk",
    "Node",
    "OverallStatus",
    "Pagination",
    "QoSComposed",
    "Position",
    "Requirement",
    "ResourcePage",
    "RiskSummary",
    "Service",
    "ServicePath",
    "SimStatus",
    "Snapshot",
    "StaticCheck",
    "StaticCheckItem",
    "SvcMeta",
    "SvcMetaStatus",
]
