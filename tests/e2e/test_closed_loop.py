"""端到端闭环测试：连仿真器 → 构图 → 优化 → 下发路径（需 netsim 在线 + 有 running 业务）。"""
import pytest

from api.client import SimulatorClient
from api.executor import PathExecutor
from algorithms.graph import build_graph, parse_links, parse_nodes
from algorithms.optimize import optimize_flow
from math_modeling.flow import flow_requirement, group_services_by_flow
from math_modeling.models import Service
from util.config import load_open_token, load_settings


@pytest.fixture(scope="module")
def env():
    settings = load_settings()
    sim = settings["simulator"]
    try:
        token = load_open_token(sim.get("token_file"))
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"无令牌: {e}")
    client = SimulatorClient(
        base_url=sim["base_url"],
        token=token,
        agent_id=settings.get("app", {}).get("agent_id", ""),
    )
    try:
        client.get_time()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"仿真器不可达: {e}")
    return client, set(sim.get("excluded_node_ids", ["EXT001"]))


def test_closed_loop(env):
    client, excluded = env
    nodes = parse_nodes(client.get_topology()["nodes"])
    links = parse_links(client.get_links().get("links", []))
    graph = build_graph(nodes, links, excluded_node_ids=excluded)
    assert graph.number_of_nodes() > 0

    running = []
    for s in client.get_services().get("services", []):
        if s.get("status") == "running":
            running.append(Service.from_dict(client.get_service(s["serviceId"])))
    if not running:
        pytest.skip("无 running 业务，无法闭环测试")

    executor = PathExecutor(client)
    submitted = 0
    for (src, dst), svcs in group_services_by_flow(running).items():
        req = flow_requirement(svcs)
        if req is None:
            continue
        link_ids = optimize_flow(graph, src, dst, req, k=30)
        if link_ids is None:
            continue
        rep = svcs[0]
        result = executor.execute(rep.service_id, src, dst, link_ids, graph=graph)
        assert result.get("result") == "accepted"
        submitted += 1

    print(f"\n闭环下发 {submitted} 条路径")
    assert submitted >= 1
