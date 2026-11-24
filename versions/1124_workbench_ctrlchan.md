# 修改记录

- 修改日期：2026-11-24
- 修改内容：Work Bench 观测通道改为 ctrl 令牌（仿真器前端同款），调用不再进入 agent 调用统计台账。`config.py` 新增 `SIM_AUTH` / `SIM_CTRL_TOKEN` / `SIM_CTRL_BASE_URL` / `WORKBENCH_SVCMETA` / `WORKBENCH_ALLOW_REPATH` 与 `resolve_credentials()`（禁止静默降级）；`simulator_client.py` 支持 ctrl/open 两种鉴权头并新增 `get_svc_meta()`；`snapshot.py` 业务分类改为 svc-meta 实时优先、离线兜底并标注来源；新增 `policy.py`（repath 开关 + 留痕提示）与 `backend/tests/` 单测；`main.py` health 暴露通道状态、repath 支持 403；`run.sh` 自动读取 ctrlToken；前端展示分类来源与写操作提示；新增端口/令牌/部署文档，更新 README、CLAUDE.md、mini_run_task、task_split 与根 CLAUDE.md。
