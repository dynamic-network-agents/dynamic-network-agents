# flow 级联合选路

> 定位：**`src/common/algorithms/flow/` 的算法规格**——F1/F2/F3 分类、两阶段贪心、
> 局部搜索、评分口径。
> 关联：候选生成见 [路径算法与取舍](路径算法与取舍.md)；目标函数与约束见
> [数学建模方案](../modeling/数学建模方案.md) §6。

---

## 1. 决策单位与目标

决策单位是 **flow**（无序端点对），不是 service。目标：

$$\max \sum_{f \in F} \alpha_f \cdot \mathbb{1}[\text{flow } f \text{ 预测达标}]$$

其中 $\alpha_f = \sum_{s \in f,\,s \text{ 为 test}} 2^{priority(s)}$（项目口径：**8 最高、1 最低**）。
纯背景 flow 权重为 0。

约束：
- **静态 QoS**（用 flow 需求交集判定，等价于逐业务判定）；
- **方向容量**：链路方向负载 ≤ $b_e(1-\rho)$。

---

## 2. 三类 flow（F1/F2/F3）

判据是**端点接入链路**的方向需求：

| 类 | 判据 | 处理 |
| --- | --- | --- |
| **F1** | 接入链路**纯 test** 方向需求 > 容量 | 物理容量墙，牺牲 |
| **F2** | test 放得下，但 test+background 超容 | 背景诱因，尽力保 test，不保证 |
| **F3** | 全放得下 | 正常分配 |

**代码**：`src/common/algorithms/flow/classification.py::classify_flow`

**近似口径（重要）**：`access_links`（`uav_access_links`）返回的是「每个 UAV 一条链路」
的查表——取该 UAV 相邻链路里**带宽最大**的一条，只用于判 F1/F2，不参与容量记账。
一个 UAV 有多条接入链路时只取最粗的那条，故判出的 F1/F2 得到的是**乐观上界**
（窄链路不参与比较）。要精确应改成全部接入链路容量之和，或用实际规划路径的首/末跳判定。

> **为什么要分类**：F1/F2 是**物理不可行**，不是路由问题。为它们换路径只是浪费
> 动作预算——闭环对硬失败 flow「钉住」（现状可用就不动）。

---

## 3. 两阶段贪心

**代码**：`src/common/algorithms/flow/placement.py::place_flow`

1. **Test 优先**：非硬失败的 flow 按 $w_f$ 降序，逐条选"静态可行 + 方向容量装得下"的最便宜路径；装不下则退化为"最便宜静态可行路径"并标 `degraded`。
2. **背景填位**：纯背景 flow 在剩余容量里选"最大链路利用率最小"的路径（least-contention），不改混合 flow（混合 flow 已随 test 一起定）。

**least-contention 的口径修正（2026-11-25）**：原来用**全网**最大利用率，只要网上存在
一条不可避瓶颈，所有候选就并列成同一个值，退化成"取第一条"。现在只看**候选自身**
经过的链路方向（`path_utilization`）。

---

## 4. 局部搜索

**代码**：`src/common/algorithms/flow/placement.py::local_search`

对**未预测达标**的 test flow 逐个换候选路径，只要优先级加权达标数提升就接受
（hill-climb），轮数上限 `local_search_rounds`。

> **复杂度**：每次试算候选都**全量重算**负载（O(flows × candidates × flows)）。
> 本轮**刻意不优化**——保持与重构前行为逐位一致。优化方向见
> [扩展指引](扩展指引.md) §3。

---

## 5. 评分口径

**代码**：`src/common/algorithms/flow/scoring.py`

| 函数 | 用途 |
|---|---|
| `flow_meets_utilization` | 单 flow 是否预测达标（全部 test 业务的自身方向最大利用率 ≤ `utilization_limit`） |
| `score_with_state` | 按给定负载算优先级加权达标数 |
| `weighted_score` | 按各 flow **当前计划里的路径**评分 |
| `weighted_score_with_paths` | 按**给定路径**评分（用于与「已装路径」对比得 Δscore） |
| `predicted_compliance` | 逐 flow 的预测达标布尔（供闭环校验「预测 vs 实测」） |

**达标判据**：某 flow 的**全部 test 业务**，在其**自身方向**上的最大链路利用率
≤ `utilization_limit`（默认 1.0）。

> **`bandwidth_headroom` 与 `utilization_limit` 是两个不同阈值，勿混用**：
> 前者是**摆放时留多少余量**（$\rho$，默认 0.2），后者是**判定达标时允许多大利用率**
> （默认 1.0）。

---

## 6. 纯函数契约

规划器输出只取决于 `(flows, graph, config)`，**不看当前已装路径**：同一份快照重算两次
必然完全一致（离线已验证）。

**为什么必须纯**：
- 闭环的不动点可证——一次批下发完成 → `installed == plan` → 再规划（同快照）差集为空 → 静默；
- 离线可复现——给定场景 JSON 就能算出确定结果，不必连仿真器；
- 可对比——baseline 与 agent 用同一份快照跑，差异只来自决策核心。

**为什么不把 incumbent 喂进贪心**（现状优先）：实测在规模场景上既更差也不稳定
（sce05 592→384）。

**代价**：`weighted_score_with_paths` 为评估「给定路径」需临时改写 `plans` 里的
`p.path` 再恢复（`try/finally`）——这是纯函数契约下的必要妥协，注意别让异常路径
留下污染。

---

## 7. 本场景预期（sce20261010-conf02/sce01）

- 40 条业务 → **17 个 flow**，其中 **8 个含 test**（6 混合 + 2 纯 test）。
- **F1 为 0 个**：所有 UAV 的 test-only 需求最高只到 60%（UAV0001 出/入 35%/60%）。
- **F2 硬失败 3 个 flow / 5 条 test 业务**：TSV0002/0005/0006/0007/0008。
- 静态可达性上界分析见 [sce01 无脚本可达性与最优 flow 摆法](../../simulator/sce01_无脚本可达性与最优flow分析.md)。

---

## 8. 代码位置

| 模块 | 职责 |
| --- | --- |
| `flow/models.py` | `FlowClass` / `FlowPlan` / `PlanConfig` / `CapacityState` 容量账本 |
| `flow/classification.py` | F1/F2/F3 分类 |
| `flow/candidates.py` | 路径归一化 + K-最短候选生成 |
| `flow/scoring.py` | 达标判定与加权评分 |
| `flow/placement.py` | 两阶段贪心 + 局部搜索 |
| `flow/planner.py` | 门面：重导出公共 API + `plan()` 编排 |

---

## 9. 验收标准

见 [传统基线选路方案](../../baseline/传统基线选路方案.md) §7。
