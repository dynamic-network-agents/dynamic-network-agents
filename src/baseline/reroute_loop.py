"""主控制循环：事件/实测驱动的流级重路由（FPCB 规划器）。

策略：
- 事件触发、或到达实测检查周期且存在连续违约时，重建图、刷新业务，用
  `flow_planner.plan()` 做一次**全量规划**（先全量，规模上去后再考虑增量）。
- 只对「规划路径 != 当前路径」且通过防抖（同一 flow 两次改路间隔 ≥ ΔT）的
  flow 下发；下发按该业务自身的 src→dst 方向校验。
- 实测反馈：test 业务连续 `measured_streak` 窗 `qosMeet=false` 时触发重规划。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import networkx as nx

from api.client import SimulatorClient
from api.executor import PathExecutor
from algorithms.flow_planner import PlanConfig, plan
from algorithms.graph import build_graph, parse_links, parse_nodes
from math_modeling.flow import group_services_by_flow, service_is_test
from math_modeling.models import Service

log = logging.getLogger("reroute_loop")


@dataclass
class OrchestratorConfig:
    k: int = 30
    poll_interval: float = 1.0
    excluded_link_ids: set[str] = field(default_factory=set)
    excluded_node_ids: set[str] = field(default_factory=set)
    weights: dict[str, float] | None = None
    plan_rho: float = 0.2
    switch_min_interval_s: float = 10.0
    measured_check_interval_s: float = 10.0
    measured_streak: int = 3


class Orchestrator:
    def __init__(self, client: SimulatorClient, config: OrchestratorConfig):
        self.client = client
        self.config = config
        self.executor = PathExecutor(client)
        self.since_ts_us = 0
        self._last_switch: dict[tuple[str, str], float] = {}
        self._violation_streak: dict[tuple[str, str], int] = {}
        self._last_measured_check = 0.0

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

    # ------------------------------------------------------------------ 实测反馈
    def _update_violations(self, services: list[Service]) -> None:
        for key, svcs in group_services_by_flow(services).items():
            bad = any(
                service_is_test(s) and s.actual is not None and s.actual.qos_meet is False
                for s in svcs
            )
            self._violation_streak[key] = (
                self._violation_streak.get(key, 0) + 1 if bad else 0
            )

    def _measured_due(self, now: float) -> bool:
        if now - self._last_measured_check < self.config.measured_check_interval_s:
            return False
        self._last_measured_check = now
        return True

    # ------------------------------------------------------------------ 主循环
    def step(self, force: bool = False) -> int:
        events = self.client.get_events(since_ts_us=self.since_ts_us, limit=100)
        new_events = events.get("events", [])
        self.since_ts_us = events.get("nextSinceTsUs", self.since_ts_us)

        now = time.time()
        triggered = bool(new_events) or force
        if not triggered and not self._measured_due(now):
            return 0

        services = self.refresh_services()
        self._update_violations(services)
        if not triggered and max(self._violation_streak.values(), default=0) < self.config.measured_streak:
            return 0

        graph = self.refresh_graph()
        flows = group_services_by_flow(services)
        plans = plan(flows, graph, PlanConfig(
            k=self.config.k, rho=self.config.plan_rho, weights=self.config.weights,
        ))

        handled = 0
        for key, p in plans.items():
            if p.path is None:
                log.warning("flow %s 无静态可行路径", key)
                continue
            if self._current_link_ids(p.services) == p.path:
                continue
            if now - self._last_switch.get(key, 0.0) < self.config.switch_min_interval_s:
                continue
            rep = p.services[0]
            # flow_key 是无序端点对；下发按该业务自身的 src→dst 方向
            link_ids = p.path if rep.src_node_id == key[0] else list(reversed(p.path))
            try:
                result = self.executor.execute(
                    rep.service_id, rep.src_node_id, rep.dst_node_id, link_ids, graph=graph,
                )
                self._last_switch[key] = now
                handled += 1
                log.info("flow %s 重路由 -> %s: %s", key, rep.service_id, result.get("result"))
            except Exception as e:  # noqa: BLE001
                log.warning("flow %s 下发失败: %s", key, e)
        return handled

    @staticmethod
    def _current_link_ids(services: list[Service]) -> list[str]:
        for s in services:
            if s.path is not None:
                return s.path.link_ids
        return []

    def run(self) -> None:
        log.info("reroute_loop 启动，轮询间隔 %.1fs", self.config.poll_interval)
        while True:
            try:
                self.step()
            except KeyboardInterrupt:
                log.info("收到中断，退出")
                break
            except Exception as e:  # noqa: BLE001
                log.error("step 异常: %s", e)
            time.sleep(self.config.poll_interval)
