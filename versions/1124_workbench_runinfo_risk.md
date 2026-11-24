# 修改记录

- 修改日期：2026-11-24
- 修改内容：Work Bench「期 1」后端批次（run-info + 风险接线）。新增 `SimulatorClient.get_run_info()`（控制面 `/api/ctrl/v1/run-info`，只认 ctrl 令牌，open 通道直接 1006 不发请求）与 `snapshot._load_sim_status()`，快照新增 `sim`（状态/实例/场景/脚本/t0TsUs/引擎进度/业务状态），实例与场景以 run-info 为权威、失败退回事件 payload；`analysis/risk.py` 接入快照，产出 `riskLinks`（R1 断 / R2 需求超订 / R3 相对上次成功快照劣化）、`riskSummary`（不可信时 `total=null`）、`overallStatus`（unknown/critical/alarm/normal），R3 基线在写缓存前取上一轮链路参数；顺带修掉 `risk.py` 对 pydantic 模型调用 `.get()` 的隐患。契约 `snapshot_version` 升到 2，TS 契约同步。新增 `test_risk.py`、`test_snapshot_risk.py`，`test_simulator_client.py` 补 run-info 用例；后端 80 passed / 1 skipped（collect 81），静态 QoS 对拍 4 例仍通过；离线冒烟确认无伪造值。README / P0–P3 任务分析 / 企划书 §4.2 同步。
