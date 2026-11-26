# 1126_baseline_rerouteloop_refactor

**修改日期**：2026-11-26

**修改内容**：重构 `src/baseline/reroute_loop.py`（原 469 行单类巨石），按职责拆为
`event_source.py`（事件游标 + 可行动事件过滤）、`snapshot.py`（冻结快照拉取）、
`dispatch_gate.py`（修复判定 + Δmin 闸门 + 批次排序，纯函数）、
`verifier.py`（1s 窗采样投票、惩罚集、纠正轮、心跳判据），
`reroute_loop.py` 只保留 `Orchestrator` 状态机（step/run）与 epoch 编排；
`OrchestratorConfig` 字段全部改为自解释命名（如 `k`→`candidate_path_count`、
`delta_min`→`min_gain_threshold`、`pace_s`→`batch_pace_s`、
`measured_check_interval_s`→`heartbeat_interval_s`），`main.py` /
`scripts/smoke_epoch.py` / `tests/test_reroute_loop.py` 同步适配（`_actionable` →
`filter_actionable`，`_penalty` → `verifier.penalized_paths`，`since_ts_us` →
`events.since_ts_us`）；`math_modeling.flow` 新增 `FlowKey` 类型别名。
行为不变：`uv run pytest src/ tests/` 85 passed / 7 skipped，
`scripts/smoke_epoch.py` 输出与重构前逐行一致（9 POST、无重复下发）。
