"""规划器黄金快照：dump `plan()` 的结果与加权得分，便于重构前后 diff。

用法：PYTHONPATH=src python scripts/plan_dump.py [场景目录] > before.json
"""
import json
import os
import sys

from common.algorithms.flow.planner import PlanConfig, plan, weighted_score
from common.algorithms.topology.graph import build_graph
from common.modeling.flow import group_services_by_flow
from common.modeling.models import Link, Node, Service

SCEN_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "simulator", "data", "scenarios", "sce20261010-conf02", "sce01",
)


def main() -> int:
    scen = sys.argv[1] if len(sys.argv) > 1 else SCEN_DIR
    topo = json.load(open(os.path.join(scen, "net-topo.json"), encoding="utf-8"))
    bg = json.load(open(os.path.join(scen, "bg-service.json"), encoding="utf-8"))
    nodes = [Node.from_dict(n) for n in topo["nodes"]]
    links = [Link.from_dict(l) for l in topo["links"]]
    services = [Service.from_dict(s) for s in bg]
    graph = build_graph(nodes, links)
    flows = group_services_by_flow(services)

    out = {}
    for label, cfg in (
        ("greedy", PlanConfig(candidate_path_count=30, enable_local_search=False)),
        ("full", PlanConfig(candidate_path_count=30, enable_local_search=True)),
    ):
        plans = plan(flows, graph, cfg)
        out[label] = {
            "score": weighted_score(plans, graph, cfg),
            "paths": {"|".join(k): (p.path or []) for k, p in sorted(plans.items())},
            "classes": {"|".join(k): p.flow_class.value for k, p in sorted(plans.items())},
            "weights": {"|".join(k): p.weight for k, p in sorted(plans.items())},
            "degraded": {"|".join(k): p.degraded for k, p in sorted(plans.items())},
        }
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
