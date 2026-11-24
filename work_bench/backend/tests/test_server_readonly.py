"""服务器环境只读联调（自动启用）。

逻辑：
- 默认读取 `work_bench/../simulator/conf/gateway.json` 的 ctrlToken（可用 SIM_TOKEN_FILE / SIM_CTRL_TOKEN 覆盖）；
- 先探 `/health`（非 /api、无令牌、不写账），不可达则 skip；
- 只做 GET：拓扑、分页链路/业务、一次快照；不启停仿真、不改路径。

用户已授权集成测试自动使用服务器环境（10100 隧道）。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import requests

from backend.simulator_client import SimulatorClient
from backend.snapshot import Collector

BASE_URL = os.environ.get("SIM_BASE_URL", "http://127.0.0.1:10100/api/open/v1")
ORIGIN = BASE_URL.split("/api/")[0]
DEFAULT_TOKEN_FILE = Path(__file__).resolve().parents[3] / "simulator" / "conf" / "gateway.json"


def _token() -> str:
    token = os.environ.get("SIM_CTRL_TOKEN", "")
    if token:
        return token
    path = os.environ.get("SIM_TOKEN_FILE", "") or str(DEFAULT_TOKEN_FILE)
    if Path(path).exists():
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            return str(data.get("ctrlToken") or "")
        except (OSError, ValueError):
            return ""
    return ""


def _server_ready() -> bool:
    try:
        resp = requests.get(f"{ORIGIN}/health", timeout=2)
        return resp.status_code == 200 and bool(resp.json().get("ok"))
    except Exception:
        return False


def _client() -> SimulatorClient:
    token = _token()
    if not token:
        pytest.skip("未提供 ctrl 令牌（SIM_CTRL_TOKEN / SIM_TOKEN_FILE / gateway.json）")
    if not _server_ready():
        pytest.skip(f"服务器仿真器不可达：{ORIGIN}")
    ctrl_base = BASE_URL.replace("/api/open/v1", "/api/ctrl/v1")
    return SimulatorClient(BASE_URL, token, auth_mode="ctrl", ctrl_base_url=ctrl_base)


def test_server_readonly_contract_and_pagination():
    client = _client()
    topo = client.get_topology()
    links, pages, complete = client.get_links_all()
    services, spages, scomplete = client.get_services_all()

    print(
        f"\n[server] nodes={len(topo.get('nodes') or [])} "
        f"topology_links={len(topo.get('links') or [])} "
        f"links={len(links)} pages={pages} complete={complete} "
        f"services={len(services)} spages={spages} scomplete={scomplete}"
    )

    assert complete is True, "链路分页未读完：检查 WORKBENCH_PAGE_SIZE / MAX_PAGES"
    assert len(links) == len(topo.get("links") or []), "分页累计与 /topology 不一致"

    collector = Collector(client, {}, svcmeta_enabled=True)
    snap = collector.snapshot()
    print(
        f"[server] health={snap.health} snapshot_version={snap.snapshot_version} "
        f"services={len(snap.services)} flows={len(snap.flows)} instance={snap.instance_id}"
    )
    assert snap.snapshot_version == 1
    assert snap.health in ("live", "partial", "stale", "disconnected")
    assert snap.pagination.consistent is not False

    # Flow 聚合：成员数之和必须等于业务数（无业务时两者都为 0）
    member_total = sum(f.memberCount for f in snap.flows)
    assert member_total == len(snap.services), "Flow 成员数之和与业务数不一致"
    for flow in snap.flows:
        assert flow.memberCount == len(flow.memberServiceIds)
        assert flow.flowKey
        if flow.pathContinuous is False:
            print(f"[server] flow {flow.flowKey} 路径不连续（missing={flow.missingLinks}）")
