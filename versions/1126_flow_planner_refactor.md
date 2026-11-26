# 1126_flow_planner_refactor

**修改日期**：2026-11-26

**修改内容**：重构 `src/algorithms/flow_planner.py`（原 469 行单文件）为
`flow_planner.py`（门面，重导出公共 API + `plan()` 编排）+ `flow_models.py`
（`FlowClass`/`FlowPlan`/`PlanConfig`/`CapacityState` 容量账本）/
`flow_classification.py`（F1/F2/F3 分类）/`flow_candidates.py`（路径归一化 +
K-最短候选生成）/`flow_scoring.py`（达标判定 + 加权评分）/`flow_placement.py`
（两阶段贪心 + 局部搜索）。消除六个函数反复传递 `graph+load+cap` 的问题
（合并为 `CapacityState`）；删除 `classify_flow` 的死参数 `graph`；公共 API 改名
（`plan_score`→`weighted_score`、`score_with_paths`→`weighted_score_with_paths`、
`predicted_meet`→`predicted_compliance`、`flow_meets`→`flow_meets_utilization`、
`access_links`→`uav_access_links`）；`PlanConfig` 字段改名
（`k`→`candidate_path_count`、`rho`→`bandwidth_headroom`、`weights`→`link_cost_weights`、
`local_search`→`enable_local_search`、`ls_rounds`→`local_search_rounds`、
`meet_util`→`utilization_limit`）；`FlowPlan.cls`→`flow_class`、
`FlowPlan.partial`→`degraded`。同步 `baseline/reroute_loop.py`、
`baseline/dispatch_gate.py`、`scripts/feasible_bound.py`、`scripts/plan_dump.py`
（新增黄金快照工具）、`tests/test_planner_offline.py`；单测按模块拆分到
`src/algorithms/tests/test_flow_{classification,candidates,scoring,planner}.py`。
**算法未改**：新增 `scripts/plan_dump.py` 做重构前后黄金快照比对，sce01 上
paths/classes/weights/得分逐位一致（244.0）；`uv run pytest src/ tests/`
98 passed / 7 skipped；`scripts/smoke_epoch.py` 输出与重构前一致。
