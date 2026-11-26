"""K-最短路径单测。"""
import networkx as nx

from common.algorithms.path.k_shortest import k_shortest_paths


def _line_graph():
    G = nx.MultiGraph()
    G.add_edge("0", "1", key="L1", delay=1.0)
    G.add_edge("1", "2", key="L2", delay=1.0)
    G.add_edge("2", "3", key="L3", delay=1.0)
    return G


def test_single_path():
    paths = k_shortest_paths(_line_graph(), "0", "3", k=5)
    assert len(paths) == 1
    assert paths[0] == ["0", "1", "2", "3"]


def test_diamond_two_paths_sorted():
    G = nx.MultiGraph()
    G.add_edge("s", "a", key="L1", delay=1.0)
    G.add_edge("s", "b", key="L2", delay=2.0)
    G.add_edge("a", "t", key="L3", delay=1.0)
    G.add_edge("b", "t", key="L4", delay=1.0)
    paths = k_shortest_paths(G, "s", "t", k=5)
    assert len(paths) == 2
    assert paths[0] == ["s", "a", "t"]  # 最短优先
    assert paths[1] == ["s", "b", "t"]


def test_src_dst_missing_or_same():
    G = nx.MultiGraph()
    G.add_node("s")
    assert k_shortest_paths(G, "s", "x", k=5) == []
    assert k_shortest_paths(G, "s", "s", k=5) == []
