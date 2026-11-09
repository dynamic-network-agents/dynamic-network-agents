# algorithms — 确定性算法库（进程内库）

无状态纯计算的确定性算法库，输入输出确定、可复现；以进程内 Python 库被 `simulator` / `backend` / `agent-platform` import 调用，无独立进程、无 HTTP 面。

- **职责**：拓扑分析（graph）、路由计算（routing）、带宽分配（allocation）、故障诊断（diagnosis）；对外数据结构遵循 `contracts/` 契约，经 `interfaces/` 适配。
- **边界**：**计算归 algorithms、执行归 simulator**。
- **依赖**：`networkx`、`ortools`。
- **包名**：`algorithms`（目录 `algorithms/algorithms/`）；发布名 `dynamic-network-algorithms`。

## 测试

```bash
uv sync && uv run pytest algorithms/tests
```

## 结构（阶段二起填充）

```text
algorithms/
  algorithms/       # 包根（graph / routing / allocation / diagnosis / interfaces）
  tests/
  pyproject.toml
  README.md
```
