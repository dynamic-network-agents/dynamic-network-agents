"""离线验证：用场景 JSON 跑 flow_planner，检查 F1/F2/F3 分类与路径分配。

不依赖仿真器在线；场景数据缺失时 skip（`simulator/` 在 .gitignore 内）。
"""
import json
import os

import pytest

from algorithms.flow_planner import PlanConfig, plan
from algorithms.graph import build_graph
from math_modeling.flow import group_services_by_flow
from math_modeling.models import Link, Node, Service

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

    plans = plan(flows, graph, PlanConfig(k=30))
    assert len(plans) == 17

    # F1/F2（硬失败）应恰好是 UAV0001 的 5 条 test 业务
    hard_test = {
        s.service_id
        for p in plans.values() if p.cls.hard
        for s in p.services if s.is_test
    }
    assert hard_test == {"TSV0002", "TSV0005", "TSV0006", "TSV0007", "TSV0008"}

    # 每个 flow 都应有静态可行路径
    missing = [k for k, p in plans.items() if p.path is None]
    assert not missing, f"无静态可行路径的 flow: {missing}"
