"""传统路径（baseline）：确定性事件驱动重路由闭环，不含 Agent / LLM。

入口 `main.py`（`python -m src.baseline.main`），控制循环在 `reroute_loop.py`。
共用层 `api` / `algorithms` / `math_modeling` / `util` 不在本包内；
未来 Agent 模块（运维/资源控制/LLM 旁路）另建于 `src/agents/` 并复用这些共用层。
"""
