"""Yen K-最短路径（基于 NetworkX `shortest_simple_paths`）。

`shortest_simple_paths` 不支持 MultiGraph，故先将并行边折叠成简单图
（每对节点保留权重最小的一条），再求 K-最短路径。
"""
from __future__ import annotations

import networkx as nx


def _simple_projection(graph: nx.MultiGraph, weight: str) -> nx.Graph:
    """把 MultiGraph 折叠成简单图：每对节点保留 `weight` 最小的一条边。"""
    simple = nx.Graph()
    simple.add_nodes_from(graph.nodes())
    for u, v, data in graph.edges(data=True):
        w = data.get(weight, 0.0)
        if simple.has_edge(u, v):
            if w < simple[u][v]["weight"]:
                simple[u][v]["weight"] = w
        else:
            simple.add_edge(u, v, weight=w)
    return simple


def k_shortest_paths(
    graph: nx.MultiGraph,
    src: str,
    dst: str,
    k: int,
    weight: str = "delay",
) -> list[list[str]]:
    """返回最多 k 条无环 s-t 路径（节点序列，按权重升序）。

    src == dst、src/dst 不在图中时返回空列表。
    """
    if src == dst or src not in graph or dst not in graph:
        return []
    simple = _simple_projection(graph, weight)
    paths: list[list[str]] = []
    try:
        for path in nx.shortest_simple_paths(simple, src, dst, weight="weight"):
            paths.append(path)
            if len(paths) >= k:
                break
    except nx.NetworkXNoPath:
        pass
    return paths
