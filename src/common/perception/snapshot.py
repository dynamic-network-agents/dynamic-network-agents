"""网络快照：一次 epoch 内被冻结的「业务 + 拓扑 + 现状路径」视图。

**规划是纯函数**：同一快照重算结果完全一致。所以每个 epoch 开头把规划所需的
全部输入一次性拉齐放进 `NetworkSnapshot`，epoch 内不再回头读仿真器（批内不重算），
避免拿「自己刚造出来的中间态」求最优。

拉取顺序为「先业务后拓扑」：事件轮询发生在快照之前（`Orchestrator.step`），
三者共同构成本 epoch 的冻结视图。
"""
from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from common.algorithms.topology.graph import build_graph, parse_links, parse_nodes
from common.simulator.client import SimulatorClient
from common.modeling.flow import FlowKey, group_services_by_flow, service_is_test
from common.modeling.models import Service


@dataclass
class NetworkSnapshot:
    """一个 epoch 的冻结输入：图、按 flow 分组的业务、现状路径、test 采样范围。"""

    graph: nx.MultiGraph
    flows: dict[FlowKey, list[Service]]          # flow_key -> 组内业务
    current_paths: dict[FlowKey, list[str]]      # flow_key -> 现状路径（可能为空）
    test_service_flow: dict[str, FlowKey]        # test 业务 serviceId -> flow_key


def installed_path(services: list[Service]) -> list[str]:
    """flow 的现状路径：取组内第一条非空路径（同 flow 业务共用一条路径）。"""
    for service in services:
        if service.path is not None and service.path.link_ids:
            return service.path.link_ids
    return []


class SnapshotSource:
    """从仿真器拉取 `NetworkSnapshot`。"""

    def __init__(
        self,
        client: SimulatorClient,
        *,
        excluded_link_ids: set[str] | None = None,
        excluded_node_ids: set[str] | None = None,
    ):
        self._client = client
        self._excluded_link_ids = excluded_link_ids or set()
        self._excluded_node_ids = excluded_node_ids or set()

    def fetch(self) -> NetworkSnapshot:
        """拉 running 业务详情 + 拓扑/链路，组装成冻结快照。"""
        services = self._running_services()
        graph = self._build_graph()
        flows = group_services_by_flow(services)
        return NetworkSnapshot(
            graph=graph,
            flows=flows,
            current_paths={key: installed_path(svcs) for key, svcs in flows.items()},
            test_service_flow={
                service.service_id: key
                for key, svcs in flows.items()
                for service in svcs
                if service_is_test(service)
            },
        )

    def _running_services(self) -> list[Service]:
        """拉 running 业务的完整详情（含 requirement/path/actual）。"""
        summaries = self._client.get_services().get("services", [])
        running_ids = [s["serviceId"] for s in summaries if s.get("status") == "running"]
        return [Service.from_dict(self._client.get_service(sid)) for sid in running_ids]

    def _build_graph(self) -> nx.MultiGraph:
        # 拓扑接口的 links 不带 params；链路 QoS 参数须从 /links 列表取
        nodes = parse_nodes(self._client.get_topology()["nodes"])
        links = parse_links(self._client.get_links().get("links", []))
        return build_graph(
            nodes, links, self._excluded_link_ids, self._excluded_node_ids,
        )
