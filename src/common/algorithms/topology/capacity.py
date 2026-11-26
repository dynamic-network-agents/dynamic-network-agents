"""方向性链路容量记账（全双工 TBF，按方向）。

仿真器 `apply_link` 对链路两端各挂一个 `rate=bw` 的 TBF，A→B 与 B→A 是
两个独立令牌桶，所以容量必须**按方向**记账，不能把两方向加总后对一个 bw。

方向键 `(link_id, sign)`：sign 由该跳 `(tail, head)` 按节点 id 字典序定
（`tail < head` → +1，否则 -1）。两个方向各自与 `bw*(1-rho)` 比较。

口径：容量记账用**求和**（同 flow 多业务叠加在同一链路上，负载相加），
与静态 QoS 判定用的漏斗带宽 `B=min b` 不同，勿混用。
"""
from __future__ import annotations

from collections import defaultdict

import networkx as nx

from common.algorithms.topology.graph import link_endpoints
from common.modeling.models import Service

DirKey = tuple[str, int]


def capacity_map(graph: nx.MultiGraph) -> dict[str, int]:
    """link_id -> 单方向带宽（bps）。"""
    out: dict[str, int] = {}
    for _u, _v, key, data in graph.edges(keys=True, data=True):
        out[key] = int(data.get("bandwidth_bps", 0))
    return out


def _dir_sign(tail: str, head: str) -> int:
    return 1 if tail < head else -1


def directional_demand(
    flow_src: str,
    services: list[Service],
    path: list[str],
    graph: nx.MultiGraph,
) -> dict[DirKey, int]:
    """flow 在 path 各链路上的方向需求（bps，含 test 与 background）。

    `flow_src` 是 flow 的名义源（无序对里字典序较小者）；服务方向与之相反时
    按反向遍历 path。

    **这里是「并发负载求和」的唯一口径**：同一 flow 的多条业务同时发流、共用
    同一条链路，同向负载相加（跨业务、跨 flow 都一样，见 `add_load`）。与之
    相对，`common/modeling/flow.py` 的 `flow_requirement` 取 max——那是「逐业务
    漏斗判定」的聚合，两者不是一回事（详见 flow.py 模块 docstring）。
    """
    total: dict[DirKey, int] = defaultdict(int)
    for s in services:
        bps = int(s.requirement.bandwidth_bps) if s.requirement else 0
        if bps <= 0:
            continue
        reverse = s.src_node_id != flow_src
        seq = list(reversed(path)) if reverse else list(path)
        current = s.src_node_id
        for lid in seq:
            u, v = link_endpoints(graph, lid)
            if current not in (u, v):
                raise ValueError(
                    f"路径与业务 {s.service_id} 不连续：{current} 不在 {lid} 端点 ({u}, {v})"
                )
            tail = current
            head = v if u == current else u
            total[(lid, _dir_sign(tail, head))] += bps
            current = head
    return dict(total)


def add_load(load: dict[DirKey, int], demand: dict[DirKey, int]) -> None:
    for k, v in demand.items():
        load[k] = load.get(k, 0) + v


def remove_load(load: dict[DirKey, int], demand: dict[DirKey, int]) -> None:
    for k, v in demand.items():
        load[k] = load.get(k, 0) - v


def fits(
    demand: dict[DirKey, int],
    load: dict[DirKey, int],
    capacity: dict[str, int],
    rho: float = 0.2,
) -> bool:
    """方向需求叠加后是否不超过 `bw*(1-rho)`。"""
    for (lid, sign), d in demand.items():
        cap = capacity.get(lid, 0) * (1.0 - rho)
        if load.get((lid, sign), 0) + d > cap:
            return False
    return True


def utilization(
    load: dict[DirKey, int],
    capacity: dict[str, int],
) -> dict[DirKey, float]:
    out: dict[DirKey, float] = {}
    for (lid, sign), v in load.items():
        cap = capacity.get(lid, 0)
        out[(lid, sign)] = (v / cap) if cap > 0 else 0.0
    return out


def max_utilization(load: dict[DirKey, int], capacity: dict[str, int]) -> float:
    u = utilization(load, capacity)
    return max(u.values()) if u else 0.0
