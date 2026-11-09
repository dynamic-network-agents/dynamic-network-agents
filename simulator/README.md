# simulator — 动态通信网络仿真器

基于 SimPy 的离散事件仿真器，职责：场景状态推进、拓扑/链路/业务流演化、动态事件执行。

- **边界**：**执行归 simulator、计算归 algorithms** —— 路由、带宽分配、故障诊断等纯计算委托给 `algorithms`，simulator 只推进状态。
- **依赖**：`simpy`、`pydantic`、`dynamic-network-algorithms`（workspace 内进程内库）。
- **包名**：`simulator`（目录 `simulator/simulator/`）；发布名 `dynamic-network-simulator`。

## 测试

```bash
uv sync && uv run pytest simulator/tests
```

## 结构（阶段二起填充）

```text
simulator/
  simulator/        # 包根（api / core / domain / environment / topology / traffic / mobility / metrics / events）
  tests/
  pyproject.toml
  README.md
```
