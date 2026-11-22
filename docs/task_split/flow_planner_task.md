# 传统基线选路（FPCB）任务清单

> 目的：把《传统基线选路方案（FPCB）》（`docs/agents/传统基线选路方案.md`）拆成可执行、可勾选的任务。
> 原则：**先离线（不接仿真器）验证算法正确，再接在线闭环**；先做贪心，局部搜索作为增强。
> 依赖：`docs/math_modeling/数学建模方案.md` §6.2/§6.5；`src/CLAUDE.md` 的模块边界。
> 状态（2026-11-22）：T0–T2、T3.1、T4.1–T4.2（代码 + mock 单测）、T5.1–T5.2 已完成；**T3.2（对比 optimize_flow）、T5.3（实验记录）以及在线真机验证待做**。

---

## 阶段 0：口径对齐（必须先做）

> 已定决策（2026-11-22）：**A1** 优先级按现状（8 高，等官方确认）、**A2** 只保 test、**A3** flow_key 改无序。

- [x] **T0.1** `src/math_modeling/models.py`：`Service.flow_key` 改为**无序**端点对（**已定：改**，A3）
  - 改为 `tuple(sorted((src_node_id, dst_node_id)))`。
  - 验收：同一对 UAV 的正反两条业务落在同一个 flow_key 下（单测）。
- [x] **T0.2** 更新 `src/math_modeling/flow.py` 与调用方
  - `group_services_by_flow` / `flow_requirement` 适配无序 key；`reroute_loop` 下发按业务自身方向校验。
  - 验收：`pytest src/math_modeling/tests/` 通过。
- [x] **T0.3** test/background 分类（**已定：只保 test**，A2）
  - `flow.service_is_test`：优先 `category`，缺省 `TSV*` 前缀兜底。
  - `flow.flow_weight = Σ2^priority(test)`。
  - 验收：sce01 能正确标出 10 条 test（TSV0001~0010）。

> 依赖：无。A1 按现状（8 高），A2/A3 已定。

---

## 阶段 1：容量记账（纯函数，可离线单测）

- [x] **T1.1** 新增 `src/algorithms/capacity.py`
  - `directional_demand` / `add_load` / `remove_load` / `fits` / `utilization` / `max_utilization`。
  - **按方向**、**求和**（不是 max），test+bg 都算。
- [x] **T1.2** 单测 `src/algorithms/tests/test_capacity.py`
  - 覆盖：方向相反、边界、超载、利用率。

---

## 阶段 2：规划器离线版

- [x] **T2.1** 新增 `src/algorithms/flow_planner.py`（贪心版）
  - `classify_flow`（F1/F2/F3）、`plan(flows, G, cfg)`。
  - 流程：静态可行候选 → 分类 → test 权重降序贪心 → 纯背景 least-contention → F1/F2 least-contention。
  - 验收：sce01 输出 17 个 flow 各一条静态可行路径。
- [x] **T2.2** 局部搜索 `local_search`
  - 对未预测达标的 test flow 换候选路径（hill-climb，按优先级加权达标数）。
  - 验收：sce01 上贪心 180 → 局部搜索 244（TSV0010 102%→95%），不引入静态违规。

---

## 阶段 3：离线验证（不接仿真器）

- [x] **T3.1** 离线验证 `tests/test_planner_offline.py`
  - 输入 sce01 的 `net-topo.json` + `bg-service.json`；断言 17 flow、硬失败集 = UAV0001 的 5 条、所有 flow 有静态可行路径。
- [ ] **T3.2** 与现状对比
  - 对比 `optimize_flow` 单 flow 结果：优先级加权达标数不降。**待做**。

> 依赖：T0、T1、T2。

---

## 阶段 4：在线闭环

- [x] **T4.1** 接 `src/api/executor.py` 下发
  - `PathExecutor.execute`（segments + requestId）；防抖由 `switch_min_interval_s` 承担，频控退避由 client 承担。
  - 验收：mock 单测覆盖「有当前路径/无当前路径/反向业务」。
  - **在线真机下发待验证。**
- [x] **T4.2** `src/baseline/reroute_loop.py` 接入规划器
  - 事件/实测触发 → 重建图 → `plan()` 全量重算 → 防抖下发。
  - 实测反馈：test 连续 `measured_streak` 窗 `qosMeet=false` 触发重规划。
  - 验收：`tests/test_reroute_loop.py` mock 通过；**在线链路中断重路由待验证**。

---

## 阶段 5：收尾

- [x] **T5.1** 全量测试 `pytest src/ tests/`（离线全绿）
- [x] **T5.2** 版本记录 `versions/1122_flowplanner_T0-T4.md`
- [ ] **T5.3** 实验记录：在 `experiments/exp/` 新增一条（T0 静态 + 动态事件各一）。**待在线跑**。

---

## 建议节奏

- **D1–D2**：T0 + T1（口径对齐 + 容量记账，纯离线）
- **D3–D4**：T2.1 贪心版 + T3 离线验证（先证明算法对）
- **D5**：T2.2 局部搜索（可选）
- **D6–D7**：T4 在线闭环 + T5 收尾

> 关键卡点：**T3.1 的离线结果必须与人工分析一致**（F1 集合、可达上限），否则先查数据/口径，不要急着接在线。
