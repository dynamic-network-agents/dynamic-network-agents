"""图路径工具单测：节点路径→链路 id、路径校验。"""
import networkx as nx

from common.algorithms.topology.graph import link_endpoints, node_path_to_link_ids, validate_path


def _diamond():
    G = nx.MultiGraph()
    G.add_edge("s", "a", key="L1", delay=1.0)
    G.add_edge("s", "b", key="L2", delay=2.0)
    G.add_edge("a", "t", key="L3", delay=1.0)
    G.add_edge("b", "t", key="L4", delay=1.0)
    return G


def test_node_path_to_link_ids():
    assert node_path_to_link_ids(_diamond(), ["s", "a", "t"]) == ["L1", "L3"]


def test_parallel_edges_pick_min_delay():
    G = nx.MultiGraph()
    G.add_edge("s", "t", key="fast", delay=1.0)
    G.add_edge("s", "t", key="slow", delay=5.0)
    assert node_path_to_link_ids(G, ["s", "t"]) == ["fast"]


def test_link_endpoints():
    G = _diamond()
    assert link_endpoints(G, "L1") in (("s", "a"), ("a", "s"))


def test_validate_path_valid():
    assert validate_path(_diamond(), ["L1", "L3"], "s", "t") == []


def test_validate_path_discontinuous():
    # L1: s-a, L4: b-t，不连续
    assert validate_path(_diamond(), ["L1", "L4"], "s", "t") != []


def test_validate_path_wrong_endpoint():
    # 只到 a，没到 t
    assert validate_path(_diamond(), ["L1"], "s", "t") != []
