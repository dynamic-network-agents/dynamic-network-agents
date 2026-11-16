"""智能体入口：加载配置/令牌 → 构建 client → 启动控制循环。"""
from __future__ import annotations

import logging

from api.client import SimulatorClient
from agents.orchestrator import Orchestrator, OrchestratorConfig
from util.config import load_open_token, load_settings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    settings = load_settings()
    app = settings["app"]
    sim = settings["simulator"]
    qos = settings.get("qos", {})

    token = load_open_token(sim.get("token_file"))

    client = SimulatorClient(
        base_url=sim["base_url"],
        token=token,
        agent_id=app.get("agent_id", ""),
        timeout=app.get("http_timeout_sec", 6.0),
    )
    config = OrchestratorConfig(
        k=app.get("k_shortest_paths", 30),
        poll_interval=app.get("poll_interval_sec", 1.0),
        excluded_node_ids=set(sim.get("excluded_node_ids", ["EXT001"])),
        weights=qos.get("link_cost_weights"),
    )
    Orchestrator(client, config).run()


if __name__ == "__main__":
    main()
