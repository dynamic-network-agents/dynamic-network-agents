"""传统路径入口：加载配置/令牌 → 构建 client → 启动重路由控制循环。

当前最小运行版本不含 Agent/LLM，闭环由确定性算法驱动；
未来 Agent 模块的入口应另建于 `src/agents/`，复用同一套 `common/` 底座
（感知 `common/perception/`、闭环控制 `common/control/`、算法 `common/algorithms/`）。
"""
from __future__ import annotations

import logging

from common.config.settings import load_open_token, load_settings
from common.control.loop import Orchestrator, OrchestratorConfig
from common.simulator.client import SimulatorClient


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
        candidate_path_count=app.get("k_shortest_paths", 30),
        poll_interval_s=app.get("poll_interval_sec", 1.0),
        event_page_limit=app.get("event_page_limit", 100),
        excluded_node_ids=set(sim.get("excluded_node_ids", ["EXT001"])),
        link_cost_weights=qos.get("link_cost_weights"),
        bandwidth_headroom=app.get("bandwidth_headroom", 0.2),
        min_gain_threshold=app.get("reroute_min_gain", 2.0),
        batch_settle_s=app.get("settle_sec", 10.0),
        verify_window_count=app.get("verify_windows", 5),
        verify_required_votes=app.get("verify_votes", 3),
        corrective_round_limit=app.get("corrective_rounds", 1),
        event_coalesce_s=app.get("trigger_settle_sec", 3.0),
        heartbeat_interval_s=app.get("heartbeat_sec", 60.0),
        min_switch_interval_s=app.get("min_switch_interval_sec", 10.0),
        batch_pace_s=app.get("batch_pace_sec", 0.1),
        max_batches_per_run=app.get("max_batches_per_run", 60),
    )
    Orchestrator(client, config).run()


if __name__ == "__main__":
    main()
