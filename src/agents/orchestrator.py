"""主控制循环：事件驱动重路由。

MVP 策略：仅在「当前路径失效（链路断开/节点下线）或静态 QoS 违约」时重路由，
不做主动寻优。状态更新采用「事件触发 → 全量重拉 → 重建图」的简化方式。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import networkx as nx

from api.client import SimulatorClient
from api.executor import PathExecutor
from algorithms.graph import build_graph, parse_links, parse_nodes
from algorithms.optimize import optimize_flow
from math_modeling.flow import flow_requirement, group_services_by_flow
from math_modeling.models import Requirement, Service
from math_modeling.path_qos import compose_qos
from math_modeling.qos_checker import check_qos

log = logging.getLogger("orchestrator")


@dataclass
class OrchestratorConfig:
    k: int = 30
    poll_interval: float = 1.0
    excluded_link_ids: set[str] = field(default_factory=set)
    excluded_node_ids: set[str] = field(default_factory=set)
    weights: dict[str, float] | None = None


class Orchestrator:
    def __init__(self, client: SimulatorClient, config: OrchestratorConfig):
        self.client = client
        self.config = config
        self.executor = PathExecutor(client)
        self.since_ts_us = 0

    # ------------------------------------------------------------------ 状态
    def refresh_graph(self) -> nx.MultiGraph:
        # 拓扑接口的 links 不带 params；链路 QoS 参数须从 /links 列表取
        nodes = parse_nodes(self.client.get_topology()["nodes"])
        links = parse_links(self.client.get_links().get("links", []))
        return build_graph(
            nodes, links,
            self.config.excluded_link_ids, self.config.excluded_node_ids,
        )

    def refresh_services(self) -> list[Service]:
        """拉 running 业务的完整详情（含 requirement/path/actual）。"""
        summaries = self.client.get_services().get("services", [])
        services: list[Service] = []
        for s in summaries:
            if s.get("status") != "running":
                continue
            services.append(Service.from_dict(self.client.get_service(s["serviceId"])))
        return services

    # ------------------------------------------------------------------ 影响分析
    def affected_flows(
        self,
        graph: nx.MultiGraph,
        services: list[Service],
    ) -> list[tuple[tuple[str, str], list[Service], Requirement]]:
        """找出路径失效或静态 QoS 违约的 flow，返回 (flow_key, services, requirement)。"""
        running = [s for s in services if s.status == "running"]
        affected: list[tuple[tuple[str, str], list[Service], Requirement]] = []
        for flow_key, svcs in group_services_by_flow(running).items():
            req = flow_requirement(svcs)
            if req is None:
                continue
            current = self._current_link_ids(svcs)
            if not current:
                affected.append((flow_key, svcs, req))
                continue
            try:
                qos = compose_qos(current, graph)
            except KeyError:
                affected.append((flow_key, svcs, req))  # 路径含断链
                continue
            if not check_qos(qos, req).feasible:
                affected.append((flow_key, svcs, req))
        return affected

    @staticmethod
    def _current_link_ids(services: list[Service]) -> list[str]:
        for s in services:
            if s.path is not None:
                return s.path.link_ids
        return []

    # ------------------------------------------------------------------ 主循环
    def step(self) -> int:
        """单轮：有新事件才刷新并处理受影响 flow；返回下发条数。"""
        events = self.client.get_events(since_ts_us=self.since_ts_us, limit=100)
        new_events = events.get("events", [])
        self.since_ts_us = events.get("nextSinceTsUs", self.since_ts_us)
        if not new_events:
            return 0
        log.info("收到 %d 条新事件", len(new_events))

        graph = self.refresh_graph()
        services = self.refresh_services()
        handled = 0
        for flow_key, svcs, req in self.affected_flows(graph, services):
            src, dst = flow_key
            link_ids = optimize_flow(graph, src, dst, req, k=self.config.k, weights=self.config.weights)
            if link_ids is None:
                log.warning("flow %s 无可行路径", flow_key)
                continue
            rep = svcs[0]
            try:
                result = self.executor.execute(rep.service_id, src, dst, link_ids, graph=graph)
                log.info("flow %s 重路由 -> %s: %s", flow_key, rep.service_id, result.get("result"))
                handled += 1
            except Exception as e:  # noqa: BLE001
                log.warning("flow %s 下发失败: %s", flow_key, e)
        return handled

    def run(self) -> None:
        log.info("orchestrator 启动，轮询间隔 %.1fs", self.config.poll_interval)
        while True:
            try:
                self.step()
            except KeyboardInterrupt:
                log.info("收到中断，退出")
                break
            except Exception as e:  # noqa: BLE001
                log.error("step 异常: %s", e)
            time.sleep(self.config.poll_interval)
