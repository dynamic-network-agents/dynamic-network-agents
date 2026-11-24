# 修改记录

- 修改日期：2026-11-24
- 修改内容：Work Bench 第一批（A-04 / B-07 / B-06）落地。新增 `backend/models/` pydantic 数据契约（Snapshot/Node/Link/Service/Path/Requirement/Actual，`snapshot_version=1`，未知字段保留）；链路与业务改为 `page/size` 循环取全，并用 `/topology` 链路总数对账，分页不完整/不一致降级健康状态；数据健康补齐 `partial/stale/disconnected/offline`，核心失败时返回缓存并标注 `data_age_s`、`stale_resources`；新增显式离线模式（`WORKBENCH_OFFLINE` + `NET_TOPO_PATH`，服务状态 `unknown`、`actual=null`）。补充单测（契约/分页/健康/离线）与服务器只读联调测试（`WORKBENCH_IT=1`），并把测试命令切到 workbench 自己的 venv（新增 `requirements-dev.txt`）。前端补 `pagination`/`data_age_s` 展示。文档同步 P0–P3 任务状态与 task_split §17。
