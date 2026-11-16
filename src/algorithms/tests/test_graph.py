"""图构建单元测试。"""
from math_modeling.models import Link, Node
from algorithms.graph import build_graph


def _nodes(*ids):
    return [Node(node_id=i, node_type="uav", status="online") for i in ids]


def _link(lid, s, d, status="up", delay=1.0, bw=8_000_000):
    from math_modeling.models import LinkParams
    return Link(
        link_id=lid, link_type="microwave", src_node_id=s, dst_node_id=d,
        status=status,
        params=LinkParams(delay_ms=delay, jitter_ms=0.5, bandwidth_bps=bw,
                          ber=0.0, packet_loss_rate=0.0),
    )


def test_build_graph_basic():
    G = build_graph(_nodes("A", "B", "C"), [_link("L1", "A", "B"), _link("L2", "B", "C")])
    assert G.number_of_nodes() == 3
    assert G.number_of_edges() == 2


def test_down_link_and_offline_node_excluded():
    nodes = _nodes("A", "B", "C") + [Node(node_id="D", status="offline")]
    links = [
        _link("L1", "A", "B"),
        _link("L2", "B", "C", status="down"),
        _link("L3", "C", "D"),  # D offline
    ]
    G = build_graph(nodes, links)
    assert G.number_of_edges() == 1
    assert G.has_edge("A", "B")


def test_excluded_link_removed():
    G = build_graph(_nodes("A", "B"), [_link("L9", "A", "B")],
                    excluded_link_ids={"L9"})
    assert G.number_of_edges() == 0


def test_excluded_node_removed():
    # EXT001 叶子节点及其入射链路一并剔除
    nodes = _nodes("A", "B", "EXT001")
    links = [_link("L1", "A", "B"), _link("L99001", "EXT001", "A")]
    G = build_graph(nodes, links, excluded_node_ids={"EXT001"})
    assert G.number_of_nodes() == 2
    assert G.number_of_edges() == 1
    assert G.has_edge("A", "B")
    assert not G.has_node("EXT001")


def test_parallel_links_multigraph():
    # 两点间两条并行链路
    G = build_graph(_nodes("A", "B"),
                    [_link("L1", "A", "B"), _link("L2", "A", "B")])
    assert G.number_of_edges() == 2
