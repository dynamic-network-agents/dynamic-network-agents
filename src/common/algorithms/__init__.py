"""算法库：按领域三分的纯计算层。

| 子包 | 领域 | 内容 |
|---|---|---|
| `topology` | 图与容量 | `graph.py` 建图与路径工具、`capacity.py` 方向容量记账 |
| `path` | 路径级 | `k_shortest.py` Yen K-最短、`single_flow.py` 单 flow 选路 |
| `flow` | flow 级 | `planner.py` 门面 + `models/classification/candidates/scoring/placement` |

依赖方向单向：`topology` / `path` / `flow` → `common.modeling`（+ networkx）。
三者互不依赖，可独立扩展与单测。

**扩展指引**（详见 `docs/common/algorithms/`）：
- 新增**候选路径算法** → 落 `path/`，由 `flow/candidates.py` 编排调用；
- 新增**flow 级优化策略** → 落 `flow/`，保持「纯函数」契约（输入
  `(flows, graph, config)`，输出与已装路径无关），由 `flow/planner.py` 门面统一暴露；
- 新增**图/容量口径** → 落 `topology/`，注意 `capacity.py` 的方向记账语义
  （全双工按方向求和，与静态 QoS 的漏斗带宽 `B=min b` 不同）。
"""
