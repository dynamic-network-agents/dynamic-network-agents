# 修改记录

- 修改日期：2026-11-23
- 修改内容：清掉 `src/` 遗留的疑问型 todo 并修正相关口径。`flow_planner.access_links` 补明「UAV→最粗接入链路」查表语义与端别模型依据（`sdncommon.adapt_spec`：ground→交换机、uav/air→主机，主机直连链路报错），标注多接入链路时的乐观上界；`reroute_loop` 记录「先取事件后建图」的成本与快照一致性理由，事件游标改用 `GET /time` 的 `tsUs` 初始化（新增 `OrchestratorConfig.skip_history`），轮询与防抖改用 `time.monotonic()`，`run()` 首轮强制全量规划一次；`measured_qos.test_meet_rate` 改走 `flow.service_is_test`（category 优先、`TSV*` 兜底），与 planner 的 test 口径统一，docstring 由「待核对」改为已知限制；`SimulatorClient` 记录响应包络的 `last_ts_us`。补 4 条游标单测与 1 条 `TSV` 兜底单测。根 `CLAUDE.md` 增补「证据纪律」工作准则。
