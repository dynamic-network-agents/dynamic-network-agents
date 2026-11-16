"""仿真器连接集成测试（T1 验收）。

需 netsim 已 [start] 就绪；未就绪时自动 skip。
运行：uv run pytest tests/test_simulator_connection.py -s
"""
import pytest

from util.config import load_open_token, load_settings
from api.client import SimulatorClient, SimulatorError


@pytest.fixture(scope="module")
def client():
    settings = load_settings()
    sim = settings["simulator"]
    try:
        token = load_open_token(sim.get("token_file"))
    except Exception as e:
        pytest.skip(f"无法读取令牌: {e}")
    c = SimulatorClient(
        base_url=sim["base_url"],
        token=token,
        agent_id=settings.get("app", {}).get("agent_id", ""),
        timeout=settings.get("app", {}).get("http_timeout_sec", 6.0),
    )
    # 探活：连不上则跳过
    try:
        c.get_time()
    except Exception as e:
        pytest.skip(f"仿真器不可达（netsim 未就绪？）: {e}")
    return c


def test_get_time(client):
    data = client.get_time()
    assert "tsUs" in data


def test_topology_nodes_links(client):
    topo = client.get_topology()
    assert "nodes" in topo and "links" in topo
    print(f"\n节点数={len(topo['nodes'])} 链路数={len(topo['links'])}")


def test_services_list(client):
    data = client.get_services()
    print(f"\n业务数={len(data.get('services', []))}")


def test_events_poll(client):
    data = client.get_events(since_ts_us=0, limit=100)
    assert "events" in data and "nextSinceTsUs" in data
    print(f"\n历史事件数={len(data.get('events', []))}")
