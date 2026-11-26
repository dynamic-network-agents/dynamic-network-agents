"""flow 可行性分类：F1（物理无解）/ F2（背景诱因）/ F3（可行）。

判据是**端点接入链路**的方向需求：test-only 装不下 → F1；test 装得下但
test+background 装不下 → F2；都装得下 → F3。F1/F2 属硬失败（物理容量墙，
不是路由问题），闭环对它们「钉住」不做动作。
"""
from __future__ import annotations

import networkx as nx

from common.algorithms.flow.models import FlowClass, UavDemand
from common.modeling.flow import service_is_test
from common.modeling.models import Service


def uav_access_links(graph: nx.MultiGraph) -> dict[str, tuple[str, int]]:
    """UAV -> (接入链路 id, 单方向带宽)。

    返回的是「每个 UAV 一条链路」的查表，**不是 flow**：键是单个 UAV 节点，
    值是该 UAV 相邻链路里带宽最大的一条。只用于 `classify_flow` 判 F1/F2，
    不参与容量记账（容量按 `capacity_map` + `DirKey` 逐链路逐方向算）。

    为什么 UAV 有「接入链路」：仿真器端别模型把 ground→sN(交换机)、uav/air→hN(主机)，
    且两端都是主机的链路直接报错「端别模型不成立」（`sim_src/netsim/sdncommon.py`
    的 `adapt_spec`），所以 UAV 的流量只能经「UAV—地面」这类接入链路出入。

    近似口径：一个 UAV 有多条接入链路时只取最粗的那条，判 F1/F2 得到的是
    **乐观上界**（窄链路不参与比较）；要精确应改成该 UAV 全部接入链路容量之和，
    或用实际规划路径的首/末跳判定。
    """
    widest: dict[str, tuple[str, int]] = {}
    for node_u, node_v, link_key, data in graph.edges(keys=True, data=True):
        for node_id in (node_u, node_v):
            if graph.nodes[node_id].get("node_type") != "uav":
                continue
            bandwidth = int(data.get("bandwidth_bps", 0))
            current = widest.get(node_id)
            if current is None or bandwidth > current[1]:
                widest[node_id] = (link_key, bandwidth)
    return widest


def per_uav_demand(services: list[Service]) -> UavDemand:
    """按 UAV 汇总出/入向的 test-only 与 test+bg 带宽需求。"""
    demand = UavDemand()
    for service in services:
        bandwidth = int(service.requirement.bandwidth_bps) if service.requirement else 0
        if bandwidth <= 0:
            continue
        demand.out_all[service.src_node_id] += bandwidth
        demand.in_all[service.dst_node_id] += bandwidth
        if service_is_test(service):
            demand.out_test_only[service.src_node_id] += bandwidth
            demand.in_test_only[service.dst_node_id] += bandwidth
    return demand


def classify_flow(
    services: list[Service],
    access: dict[str, tuple[str, int]],
    demand: UavDemand,
) -> FlowClass:
    """按端点接入链路的 test-only / test+bg 需求给 flow 分类。"""
    test_services = [s for s in services if service_is_test(s)]
    if not test_services:
        return FlowClass.F3
    for service in test_services:
        endpoints = (
            (service.src_node_id, True),
            (service.dst_node_id, False),
        )
        for node_id, is_outgoing in endpoints:
            if node_id not in access:
                continue
            _, capacity = access[node_id]
            if is_outgoing:
                if demand.out_test_only[node_id] > capacity:
                    return FlowClass.F1
                if demand.out_all[node_id] > capacity:
                    return FlowClass.F2
            else:
                if demand.in_test_only[node_id] > capacity:
                    return FlowClass.F1
                if demand.in_all[node_id] > capacity:
                    return FlowClass.F2
    return FlowClass.F3
