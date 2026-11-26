"""传统路径（baseline）：确定性事件驱动重路由闭环，不含 Agent / LLM。

入口 `main.py`（`uv run python -m src.baseline.main`），控制循环在
`common/control/loop.py`，感知在 `common/perception/`，规划算法在
`common/algorithms/flow/`。

未来 Agent 模块（运维/资源控制/LLM 旁路）另建于 `src/agents/`，复用同一套
`common/` 底座，只替换决策核心。
"""
