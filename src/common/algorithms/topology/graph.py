"""NetworkX 图构建：把节点/链路模型转成时变无向图 G(t)。

规则（对齐仿真器与 CLAUDE.md）：
- 只收 status=up 链路 + status=online 节点；
- 并行链路用 nx.MultiGraph（两点间可能多条 linkId 不同的链路）；
- 剔除外部引接节点 EXT001（合成的"外部引接点"，非业务端点，业务路径永不穿越）；
- 边属性携带 5 项链路参数 + delay 权重（最短路径用）。

注：EXT001 是建网时合成的叶子节点（nodeId 固定为 `EXT001`，仅一条光纤连
第一个地面节点），业务 src/dst 都是 UAV/AIR，本就不会穿越它；这里按 nodeId
显式剔除，避免把 1Gbps 光纤误当可用的业务链路。
"""
from __future__ import annotations

import networkx as nx

from common.modeling.models import Link, Node


def build_graph(
    nodes: list[Node],
    links: list[Link],
    excluded_link_ids: set[str] | frozenset[str] = frozenset(),
    excluded_node_ids: set[str] | frozenset[str] = frozenset(),
) -> nx.MultiGraph:
    G = nx.MultiGraph()

    online_ids = {n.node_id for n in nodes if n.online and n.node_id not in excluded_node_ids}
    for n in nodes:
        if n.online and n.node_id not in excluded_node_ids:
            G.add_node(
                n.node_id,
                name=n.name,
                node_type=n.node_type,
                ip=n.ip,
                status=n.status,
            )

    for l in links:
        if not l.up:
            continue
        if l.link_id in excluded_link_ids:
            continue
        # 两端节点不得为被剔除的外部引接节点，且必须在线、已入图
        if l.src_node_id in excluded_node_ids or l.dst_node_id in excluded_node_ids:
            continue
        if l.src_node_id not in online_ids or l.dst_node_id not in online_ids:
            continue
        p = l.params
        G.add_edge(
            l.src_node_id,
            l.dst_node_id,
            key=l.link_id,
            link_id=l.link_id,
            link_type=l.link_type,
            delay_ms=p.delay_ms if p else 0.0,
            jitter_ms=p.jitter_ms if p else 0.0,
            bandwidth_bps=p.bandwidth_bps if p else 0,
            ber=p.ber if p else 0.0,
            packet_loss_rate=p.packet_loss_rate if p else 0.0,
            delay=p.delay_ms if p else 0.0,  # 最短路径权重
        )

    return G


def parse_nodes(raw: list[dict]) -> list[Node]:
    return [Node.from_dict(n) for n in raw]


def parse_links(raw: list[dict]) -> list[Link]:
    return [Link.from_dict(l) for l in raw]


def link_endpoints(graph: nx.MultiGraph, link_id: str) -> tuple[str, str]:
    """返回链路两端节点 (u, v)。找不到抛 KeyError。"""
    for u, v, key in graph.edges(keys=True):
        if key == link_id:
            return (u, v)
    raise KeyError(f"链路 {link_id} 不在图中")


def node_path_to_link_ids(graph: nx.MultiGraph, node_path: list[str]) -> list[str]:
    """节点路径 -> 链路 id 序列；每跳在并行链路中取时延最小者。"""
    link_ids: list[str] = []
    for i in range(len(node_path) - 1):
        u, v = node_path[i], node_path[i + 1]
        best_key: str | None = None
        best_delay: float | None = None
        for key, data in graph[u][v].items():
            d = data.get("delay", 0.0)
            if best_delay is None or d < best_delay:
                best_delay = d
                best_key = key
        if best_key is None:
            raise KeyError(f"节点 {u} 与 {v} 之间无链路")
        link_ids.append(best_key)
    return link_ids


def validate_path(graph: nx.MultiGraph, link_ids: list[str], src: str, dst: str) -> list[str]:
    """校验链路序列是否从 src 连续贯通到 dst；返回问题列表（空 = 合法）。"""
    problems: list[str] = []
    if not link_ids:
        return ["空路径"]
    current = src
    for lid in link_ids:
        try:
            u, v = link_endpoints(graph, lid)
        except KeyError:
            problems.append(f"链路 {lid} 不存在或已断开")
            continue
        if current not in (u, v):
            problems.append(f"链路 {lid} 与前一跳不连续（当前节点 {current}）")
        current = v if u == current else u
    if current != dst:
        problems.append(f"路径终点 {current} != 目的 {dst}")
    return problems
