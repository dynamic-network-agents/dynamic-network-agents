"""仿真器 HTTP 适配层：公开 API client 与路径下发执行器。

- `client.py`：`SimulatorClient`，封装 `/topology` `/links` `/services` `/events`
  `/time` 等只读接口与 `set_service_path` 写接口；令牌与错误码语义见
  `docs/common/simulator/`。
- `executor.py`：`PathExecutor`，把「链路 id 序列」组装成 `segments` 并提交，
  提交前用 `common.algorithms.topology.graph.validate_path` 校验连续性。

本层只做协议适配，不含任何决策逻辑。
"""
