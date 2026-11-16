"""路径下发执行器：校验 → 构造 segments → 提交 → 解析回执。"""
from __future__ import annotations

import networkx as nx

from api.client import SimulatorClient
from algorithms.graph import validate_path


class PathExecutor:
    def __init__(self, client: SimulatorClient):
        self.client = client

    @staticmethod
    def build_segments(link_ids: list[str]) -> list[dict]:
        return [{"type": "link", "id": lid} for lid in link_ids]

    @staticmethod
    def validate(graph: nx.MultiGraph, link_ids: list[str], src: str, dst: str) -> list[str]:
        return validate_path(graph, link_ids, src, dst)

    def execute(
        self,
        service_id: str,
        src: str,
        dst: str,
        link_ids: list[str],
        graph: nx.MultiGraph | None = None,
        request_id: str | None = None,
    ) -> dict:
        """校验（可选）后提交路径；rejected 抛 ValueError，accepted 返回回执。"""
        if graph is not None:
            problems = self.validate(graph, link_ids, src, dst)
            if problems:
                raise ValueError(f"路径校验失败: {problems}")
        segments = self.build_segments(link_ids)
        result = self.client.set_service_path(service_id, src, dst, segments, request_id=request_id)
        if result.get("result") == "rejected":
            raise ValueError(f"路径被拒绝: {result.get('reason', 'unknown')}")
        return result
