"""候选路径单测（`flow_candidates.py`）：路径归一化 + 候选生成/排除/兜底。"""
import networkx as nx

from common.algorithms.flow.candidates import candidate_paths, normalize_path
from common.algorithms.flow.models import PlanConfig
from common.modeling.models import Requirement


def _chain_graph(alt_bw=10_000_000):
    """UAV1—L1—GND1—L2—GND2—L3—UAV2，另有一条较慢的备路径 L4/L5。"""
    g = nx.MultiGraph()
    for nd, t in (("UAV1", "uav"), ("UAV2", "uav"),
                  ("GND1", "ground"), ("GND2", "ground"), ("GND3", "ground")):
        g.add_node(nd, node_type=t)

    def e(u, v, lid, delay, bw=10_000_000):
        g.add_edge(
            u, v, key=lid, link_id=lid, link_type="microwave",
            delay_ms=delay, jitter_ms=0.5, bandwidth_bps=bw,
            ber=1e-6, packet_loss_rate=0.0005, delay=delay,
        )

    e("UAV1", "GND1", "L1", 1.0)
    e("GND1", "GND2", "L2", 1.0)
    e("GND2", "UAV2", "L3", 1.0)
    e("UAV1", "GND3", "L4", 2.0, alt_bw)
    e("GND3", "GND2", "L5", 2.0, alt_bw)
    return g


def _requirement(bandwidth=1_000_000):
    return Requirement(
        delay_ms=100, jitter_ms=10, bandwidth_bps=bandwidth,
        ber=1e-5, packet_loss_rate=0.01,
    )


def test_normalize_path_accepts_reversed_and_rejects_broken():
    g = _chain_graph()
    key = ("UAV1", "UAV2")
    assert normalize_path(g, key, ["L1", "L2", "L3"]) == ["L1", "L2", "L3"]
    assert normalize_path(g, key, ["L3", "L2", "L1"]) == ["L1", "L2", "L3"]
    assert normalize_path(g, key, ["L1", "L3"]) is None      # 不连续
    assert normalize_path(g, key, []) is None
    assert normalize_path(g, key, None) is None


def test_candidate_paths_sorted_by_cost():
    """候选按链路代价升序（更短的路径在前）。"""
    g = _chain_graph()
    candidates = candidate_paths(
        g, ("UAV1", "UAV2"), _requirement(), PlanConfig(candidate_path_count=5),
    )
    assert candidates[0] == ["L1", "L2", "L3"]
    assert ["L4", "L5", "L3"] in candidates


def test_candidate_paths_excludes_penalized_path():
    g = _chain_graph()
    key = ("UAV1", "UAV2")
    config = PlanConfig(
        candidate_path_count=5, excluded_paths={key: {("L1", "L2", "L3")}},
    )
    candidates = candidate_paths(g, key, _requirement(), config)
    assert ["L1", "L2", "L3"] not in candidates


def test_candidate_paths_falls_back_when_all_excluded():
    """全部候选被排除时必须兜底（否则该 flow 彻底失去路径）。"""
    g = _chain_graph()
    key = ("UAV1", "UAV2")
    config = PlanConfig(
        candidate_path_count=5,
        excluded_paths={key: {("L1", "L2", "L3"), ("L4", "L5", "L3")}},
    )
    assert candidate_paths(g, key, _requirement(), config)


def test_candidate_paths_filters_static_qos_violations():
    """静态 QoS 不满足的路径硬过滤掉。

    两条候选的合成 QoS：L1+L2+L3 时延 3ms、L4+L5+L3 时延 5ms（抖动 RMS 相同）。
    时延判定容差 +1.0ms，故需求 3ms 时 5ms 路径被滤掉、3ms 路径保留。
    """
    g = _chain_graph()
    strict = Requirement(
        delay_ms=3.0, jitter_ms=2.0, bandwidth_bps=1_000_000,
        ber=1e-5, packet_loss_rate=0.01,
    )
    candidates = candidate_paths(
        g, ("UAV1", "UAV2"), strict, PlanConfig(candidate_path_count=5),
    )
    assert candidates == [["L1", "L2", "L3"]]
