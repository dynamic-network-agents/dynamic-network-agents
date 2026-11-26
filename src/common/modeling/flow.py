"""flow 分组与 flow 级需求聚合。

关键事实：路径按源/目的 IP 键控，同一对 UAV 之间的所有业务（含 background）
共用一条路径。所以优化单位是 flow（源-目 UAV 对），flow 需求取各业务需求的
交集：时延/抖动/丢包/误码取 min（最严），带宽取 max（最大需求）。

**带宽的两个口径（勿混用，勿把 max 改成 sum）**：

1. 本模块 `flow_requirement` 的带宽取 **max**——它服务于「静态漏斗判定」
   （`B = min(路径各链路带宽)` 是否 ≥ 需求）。判定对象是**单条业务**：仿真器
   提交路径时也是**逐业务**校验（`sim_src/netsim/openapi.py` 的
   `_qos_violations(comp, req)`，其中 `req` 取**提交的那条业务**的
   `svc_req[sid]`，从不跨业务聚合）。因此 flow 级聚合必须等价于「逐业务都
   通过」，各维度都取**最严**的那个值：上界型维度（时延/抖动/丢包/误码）取
   min，带宽是下界取 max。改成 sum 等于自造一条仿真器没有的硬约束，会把
   仿真器认可、实测也能部分达标的路径全部滤掉。
2. 并发**负载**的合计取 **sum**，且**按方向**：同一 flow 的多条业务同时发流、
   共用同一条链路（仿真器在链路两端各挂一个 `tbf rate bw`，A→B 与 B→A 是两个
   独立令牌桶，见 `sim_src/netsim/ctrl.py` 的 `apply_link`），跨业务、跨 flow
   的**同向**负载都要累加后与链路容量比较——这在
   `common/algorithms/topology/capacity.py` 的 `directional_demand` / `fits` 里做
   （容量口径按方向记账，见该文件头注释），不在本模块。
"""
from __future__ import annotations

from common.modeling.models import Requirement, Service

#: flow 键 = 无序端点对 `(src, dst)`（`Service.flow_key` 已排序，与仿真器 `_flow_for` 对齐）
FlowKey = tuple[str, str]


def group_services_by_flow(
    services: list[Service],
) -> dict[FlowKey, list[Service]]:
    """按 (src, dst) 分组。"""
    groups: dict[FlowKey, list[Service]] = {}
    for s in services:
        groups.setdefault(s.flow_key, []).append(s)
    return groups


def flow_requirement(services: list[Service]) -> Requirement | None:
    """flow 需求 = 组内各业务需求的交集。

    各维度取**最严**约束：上界型（时延/抖动/丢包/误码）取 min，带宽是下界取
    max（等价于「逐业务都通过仿真器的静态漏斗判定」，见模块 docstring 口径 1）。
    并发负载的**求和**在容量账本（`common/algorithms/topology/capacity.py`）里做，
    不在这里。

    无任何带 requirement 的业务时返回 None。
    """
    reqs = [s.requirement for s in services if s.requirement is not None]
    if not reqs:
        return None
    return Requirement(
        delay_ms=min(r.delay_ms for r in reqs),
        jitter_ms=min(r.jitter_ms for r in reqs),
        bandwidth_bps=max(r.bandwidth_bps for r in reqs),
        ber=min(r.ber for r in reqs),
        packet_loss_rate=min(r.packet_loss_rate for r in reqs),
    )


TEST_ID_PREFIX = "TSV"  # 当前场景库的 test 业务前缀，仅作 category 缺失时的兜底


def service_is_test(service: Service) -> bool:
    """test/background 判定（A2：只保 test）。

    优先 `service.category`（来自内部 svc-meta）；缺失时用 serviceId 前缀兜底
    （仅对当前场景库 `TSV*` 有效，官方无命名约定）。
    """
    if service.category:
        return service.category == "test"
    return service.service_id.startswith(TEST_ID_PREFIX)


def flow_weight(services: list[Service]) -> float:
    """flow 权重 = Σ 2^priority（只算 test；background 权重 0）。

    优先级方向按现状采用「8 最高、1 最低」（等官方确认）。
    """
    return float(sum(2 ** s.priority for s in services if service_is_test(s)))
