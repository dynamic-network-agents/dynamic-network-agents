"""离线验证：用场景 JSON 跑 flow_planner，检查 F1/F2/F3 分类与路径分配。

不依赖仿真器在线；场景数据缺失时 skip（`simulator/` 在 .gitignore 内）。
"""
import json
import os

import pytest

from common.algorithms.flow.planner import PlanConfig, plan
from common.algorithms.topology.graph import build_graph
from common.modeling.flow import group_services_by_flow
from common.modeling.models import Link, Node, Service

SCEN_DIR = os.path.join(
    os.path.dirname(__file__), "..", "simulator", "data", "scenarios",
    "sce20261010-conf02", "sce01",
)
TOPO = os.path.join(SCEN_DIR, "net-topo.json")
BG = os.path.join(SCEN_DIR, "bg-service.json")


def _load():
    with open(TOPO, encoding="utf-8") as f:
        topo = json.load(f)
    with open(BG, encoding="utf-8") as f:
        bg = json.load(f)
    nodes = [Node.from_dict(n) for n in topo["nodes"]]
    links = [Link.from_dict(l) for l in topo["links"]]
    services = [Service.from_dict(s) for s in bg]
    return nodes, links, services


@pytest.mark.skipif(
    not (os.path.exists(TOPO) and os.path.exists(BG)),
    reason="场景数据缺失（simulator/ 未挂载）",
)
def test_planner_offline_sce01():
    nodes, links, services = _load()
    graph = build_graph(nodes, links)
    flows = group_services_by_flow(services)
    assert len(flows) == 17                     # 40 业务 → 17 个无序 flow

    plans = plan(flows, graph, PlanConfig(candidate_path_count=30))
    assert len(plans) == 17

    # F1/F2（硬失败）应恰好是 UAV0001 的 5 条 test 业务
    hard_test = {
        s.service_id
        for p in plans.values() if p.flow_class.hard
        for s in p.services if s.is_test
    }
    assert hard_test == {"TSV0002", "TSV0005", "TSV0006", "TSV0007", "TSV0008"}

    # 每个 flow 都应有静态可行路径
    missing = [k for k, p in plans.items() if p.path is None]
    assert not missing, f"无静态可行路径的 flow: {missing}"


@pytest.mark.skipif(
    not (os.path.exists(TOPO) and os.path.exists(BG)),
    reason="场景数据缺失（simulator/ 未挂载）",
)
def test_plan_is_pure_and_installed_plan_has_no_gain():
    """同一份快照重算必须完全一致；把结果当"已装路径"回灌，Δscore 必须为 0。

    这两个性质是闭环「不再下发」的依据（下发闸门 = 修复 or Δscore ≥ Δmin）。
    """
    from common.algorithms.flow.planner import weighted_score, weighted_score_with_paths

    nodes, links, services = _load()
    graph = build_graph(nodes, links)
    flows = group_services_by_flow(services)
    cfg = PlanConfig(candidate_path_count=30, enable_local_search=True)

    first = plan(flows, graph, cfg)
    again = plan(flows, graph, cfg)
    assert {k: p.path for k, p in first.items()} == {k: p.path for k, p in again.items()}

    installed = {k: p.path for k, p in first.items() if p.path}
    gain = weighted_score(first, graph, cfg) - weighted_score_with_paths(first, graph, installed, cfg)
    assert gain == 0, f"装好之后再规划仍有增益 {gain}，闭环会反复下发"


@pytest.mark.skipif(
    not (os.path.exists(TOPO) and os.path.exists(BG)),
    reason="场景数据缺失（simulator/ 未挂载）",
)
def test_link_cut_only_reroutes_affected_flows():
    """断一条承重链路：承载它的 flow 必须改路、不得留下穿越断链的路径、分数不下降。"""
    from common.algorithms.flow.planner import weighted_score

    nodes, links, services = _load()
    flows = group_services_by_flow(services)
    cfg = PlanConfig(candidate_path_count=30, enable_local_search=True)
    base = plan(flows, build_graph(nodes, links), cfg)
    base_paths = {k: p.path for k, p in base.items() if p.path}

    cut = "L00005"
    graph2 = build_graph(nodes, [l for l in links if l.link_id != cut])
    after = plan(flows, graph2, cfg)

    affected = {k for k, p in base_paths.items() if cut in p}
    changed = {k for k in base_paths if list(after[k].path or []) != list(base_paths[k])}
    assert affected <= changed, f"承载被断链路的 flow 未改路: {affected - changed}"
    assert not [k for k, p in after.items() if not p.path], "断链后不应有 flow 失去路径"
    assert not [k for k, p in after.items() if p.path and cut in p.path]
    assert weighted_score(after, graph2, cfg) >= weighted_score(base, build_graph(nodes, links), cfg)
