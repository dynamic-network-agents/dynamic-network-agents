"""flow 域算法：多 flow 联合选路（FPCB 传统基线的规划器）。

决策单位是 flow（无序端点对）；目标：最大化 Σ 2^priority(test) · 1[test 达标]。
约束：静态 QoS（用 flow 需求交集判定）+ 方向容量。

模块分工：

| 模块 | 职责 |
|---|---|
| `models.py` | `FlowClass`（F1/F2/F3）、`FlowPlan`、`PlanConfig`、`CapacityState` 容量账本 |
| `classification.py` | F1/F2/F3 分类（按端点接入链路方向需求） |
| `candidates.py` | 路径归一化 + K-最短候选生成（静态 QoS 硬过滤 + 代价排序） |
| `scoring.py` | 达标判定与优先级加权评分 |
| `placement.py` | 两阶段贪心放置（test 优先 → 背景填位）+ 局部搜索 |
| `planner.py` | 门面：重导出公共 API + `plan()` 编排 |

**规划器是纯函数**：输出只取决于 `(flows, graph, config)`，不看「当前已装路径」——
同一快照重算两次必然同结果；「要不要下发」交给调用方的 Δscore 闸门
（`common.control.dispatch_gate`）。
"""
