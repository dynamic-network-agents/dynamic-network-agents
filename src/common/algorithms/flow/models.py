"""规划器的数据模型与配置：flow 分类、flow 计划、规划配置、UAV 需求汇总、容量账本。

本模块只放**结构体**，不含算法；依赖方向上处于 `algorithms` 内其他 flow_* 模块的
最底层（不依赖它们，避免循环导入）。

命名口径：
- `flow_class` 指 F1/F2/F3 三类（不用 `cls`，避开 classmethod 惯例）；
- `bandwidth_headroom`（摆放裕度 ρ）与 `utilization_limit`（预测达标阈值）是
  **两个不同的阈值**，勿混用：前者是「摆放时留多少余量」，后者是「判定某 flow
  预测达标时允许的最大链路利用率」。
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

import networkx as nx

from common.algorithms.topology.capacity import (
    DirKey,
    add_load,
    capacity_map,
    directional_demand,
    fits,
)
from common.modeling.flow import FlowKey
from common.modeling.models import Requirement, Service


class FlowClass(Enum):
    """flow 的可行性分类（数学建模 §6.5）。"""

    F1 = "F1"   # 接入链路 test-only 超容（物理无解）
    F2 = "F2"   # 接入链路 test 放得下、test+bg 超容（实际硬失败）
    F3 = "F3"   # 可行

    @property
    def hard(self) -> bool:
        """是否硬失败（F1/F2 物理上救不回来，不投入动作预算）。"""
        return self in (FlowClass.F1, FlowClass.F2)


@dataclass
class FlowPlan:
    """一个 flow 的规划结果：分类、需求、候选路径与最终选中的路径。"""

    flow_key: FlowKey
    services: list[Service]
    requirement: Requirement
    weight: float
    flow_class: FlowClass
    candidates: list[list[str]] = field(default_factory=list)
    path: list[str] | None = None
    #: 是否「退化分配」——没有候选装得下剩余容量，只能退到最便宜的静态可行路径
    degraded: bool = False


@dataclass
class PlanConfig:
    """规划参数。"""

    candidate_path_count: int = 30          # 每 flow 的候选路径条数（K-最短）
    bandwidth_headroom: float = 0.2         # 摆放裕度 ρ：负载 ≤ bw·(1-ρ)
    link_cost_weights: dict[str, float] | None = None   # 链路代价权重（候选排序）
    enable_local_search: bool = True        # 是否做局部搜索（hill-climb）
    local_search_rounds: int = 10           # 局部搜索轮数上限
    utilization_limit: float = 1.0          # 预测达标阈值：自身方向最大利用率 ≤ 该值
    # 实测违约过的路径：flow_key -> {路径元组}，规划时剔除（无其它候选时回退）
    excluded_paths: dict[FlowKey, set[tuple[str, ...]]] = field(default_factory=dict)


@dataclass
class UavDemand:
    """按 UAV 汇总的出入向带宽需求（bps），分 test-only 与 test+bg 两档。

    缺键返回 0（`defaultdict`）：分类时「该 UAV 无此方向需求」等价于 0。
    """

    out_test_only: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    in_test_only: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    out_all: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    in_all: dict[str, int] = field(default_factory=lambda: defaultdict(int))


@dataclass
class CapacityState:
    """容量账本：图 + 单向容量表 + 当前方向负载。

    规划期的容量判断都读同一份账本（原先这些参数在六个函数间反复传递），
    负载随贪心放置累积，局部搜索时按需整体重算。
    """

    graph: nx.MultiGraph
    capacity: dict[str, int] = field(default_factory=dict)   # link_id -> 单向带宽
    load: dict[DirKey, int] = field(default_factory=dict)    # (link_id, sign) -> 已占带宽

    @classmethod
    def from_graph(cls, graph: nx.MultiGraph) -> "CapacityState":
        """按图建一份空账本（负载为 0）。"""
        return cls(graph=graph, capacity=capacity_map(graph), load={})

    def demand(self, services: list[Service], path: list[str], flow_src: str) -> dict[DirKey, int]:
        """这些业务走这条路径时的方向需求。"""
        return directional_demand(flow_src, services, path, self.graph)

    def add(self, demand: dict[DirKey, int]) -> None:
        """把一份方向需求累加进负载。"""
        add_load(self.load, demand)

    def fits(self, demand: dict[DirKey, int], bandwidth_headroom: float) -> bool:
        """叠加后是否仍不超过 `bw·(1-ρ)`。"""
        return fits(demand, self.load, self.capacity, bandwidth_headroom)

    def with_load(self, load: dict[DirKey, int]) -> "CapacityState":
        """换一份负载（同图同容量表），用于「试算某个候选」而不污染当前账本。"""
        return CapacityState(graph=self.graph, capacity=self.capacity, load=load)

    def recompute(self, plans: dict[FlowKey, "FlowPlan"]) -> dict[DirKey, int]:
        """按当前各 flow 的路径重算整份负载（返回新 dict，不改本账本）。"""
        load: dict[DirKey, int] = {}
        for flow_plan in plans.values():
            if flow_plan.path:
                add_load(
                    load,
                    directional_demand(
                        flow_plan.flow_key[0], flow_plan.services, flow_plan.path, self.graph,
                    ),
                )
        return load
