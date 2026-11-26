"""下发闸门：纯函数判定「本 epoch 哪些 flow 值得下发」。

对应设计要点 2（见 `docs/baseline/传统基线选路方案.md` §5.7）：规划是纯函数、
下发是增量 —— 拿规划结果与已装路径做差集，只有两类条目进入下发批：

1. **修复**：现状路径失效（无路径 / 链路已断 / 静态 QoS 已违约），必须动；
2. **增益**：加权达标数增益 ≥ Δmin（`min_gain`），且不是硬失败 flow（F1/F2
   物理上救不回来，为它换路径只是无意义的 churn）。

纠正轮（`restrict_to_keys`）例外：只动实测违约过的 flow，换到惩罚集之外的路径。

本模块只做「选哪些 flow、什么顺序」，不碰网络、不看时钟，可离线单测。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from common.algorithms.flow.planner import (
    FlowPlan,
    PlanConfig,
    normalize_path,
    weighted_score,
    weighted_score_with_paths,
)
from common.modeling.flow import FlowKey
from common.modeling.models import Requirement
from common.modeling.path_qos import compose_qos
from common.modeling.qos_checker import check_qos


@dataclass
class DispatchBatch:
    """一次 epoch 的下发决定（`entries` 为空 = 收敛，不动网）。"""

    entries: list[tuple[FlowKey, FlowPlan]] = field(default_factory=list)  # 已排序：修复优先
    repairs: list[FlowKey] = field(default_factory=list)                   # 其中属「修复」的 flow
    changed: list[FlowKey] = field(default_factory=list)                   # 与现状不同的全部 flow
    score_gain: float = 0.0                                                # Δscore（新计划 − 现状）


def same_path(path: list[str], current: list[str]) -> bool:
    """flow 路径比较：仿真器存的方向取决于最后一次提交，必须容忍反序。"""
    if not current:
        return False
    return list(path) == list(current) or list(path) == list(current)[::-1]


def needs_repair(
    graph: nx.MultiGraph, key: FlowKey, current: list[str], requirement: Requirement | None,
) -> bool:
    """现状路径是否需要「修复」：无路径 / 链路已断 / 静态 QoS 已违约。"""
    if not current:
        return True
    path = normalize_path(graph, key, current)
    if path is None:
        return True
    if requirement is not None and not check_qos(
        compose_qos(path, graph), requirement,
    ).feasible:
        return True
    return False


def build_dispatch_batch(
    plans: dict[FlowKey, FlowPlan],
    current_paths: dict[FlowKey, list[str]],
    graph: nx.MultiGraph,
    plan_config: PlanConfig,
    *,
    min_gain: float,
    restrict_to_keys: set[FlowKey] | None = None,
) -> DispatchBatch:
    """在「规划结果 vs 现状」的差集上过闸门，产出排序后的下发批。

    - `min_gain`：Δmin 门槛（优先级加权达标数增益，单位 Σ2^priority）。
    - `restrict_to_keys`：非 None 时为纠正轮模式，只放行这些 flow（实测违约过的），
      忽略 Δmin 门槛。
    """
    score_gain = (
        weighted_score(plans, graph, plan_config)
        - weighted_score_with_paths(plans, graph, current_paths, plan_config)
    )

    changed: list[FlowKey] = []
    repairs: list[FlowKey] = []
    candidates: list[tuple[FlowKey, FlowPlan]] = []
    for key, plan in plans.items():
        if not plan.path:
            continue
        current = current_paths.get(key) or []
        if same_path(plan.path, current):
            continue
        if needs_repair(graph, key, current, plan.requirement):
            repairs.append(key)
        changed.append(key)
        candidates.append((key, plan))

    if restrict_to_keys is not None:
        entries = [(k, p) for k, p in candidates if k in restrict_to_keys]
    else:
        allow_improve = score_gain >= min_gain
        entries = [
            (k, p) for k, p in candidates
            if k in repairs or (allow_improve and not p.flow_class.hard)
        ]

    # 修复类优先（先恢复连通），其余按 flow_key 保证可复现
    entries.sort(key=lambda item: (item[0] not in repairs, item[0]))
    return DispatchBatch(entries=entries, repairs=repairs, changed=changed, score_gain=score_gain)
