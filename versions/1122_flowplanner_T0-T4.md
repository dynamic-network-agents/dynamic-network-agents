# 修改记录

- 修改日期：2026-11-22
- 修改内容：落地 FPCB 传统基线选路（T0–T4）。新增 `src/algorithms/capacity.py`（方向性链路容量记账：全双工按方向求和）与 `src/algorithms/flow_planner.py`（F1/F2/F3 分类 + 优先级加权贪心 + 局部搜索）；`models.flow_key` 改无序端点对，新增 `flow.service_is_test`/`flow_weight`；`reroute_loop` 接入规划器并加实测反馈与防抖；补 `tests/test_capacity.py`、`tests/test_flow_planner.py`、`tests/test_planner_offline.py`、`tests/test_reroute_loop.py`（sce01 离线验证：17 flow、硬失败 5 条、局部搜索加权 180→244）。同步更新 `docs/agents/传统基线选路方案.md`、`docs/task_split/flow_planner_task.md`、`docs/math_modeling/数学建模方案.md`、`src/CLAUDE.md` 的口径与映射。
