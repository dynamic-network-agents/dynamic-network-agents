# 修改记录

- 修改日期：2026-11-24
- 修改内容：Work Bench「期 2」首批——Flow 分析页 + 候选路径静态可行性。后端新增 `analysis/candidates.py`（候选去重、按当前 `/links` 参数重算静态 QoS、逐成员校验汇总 ok/fail/unknown、缺链路不做部分合成）与只读接口 `GET /api/flow-candidates?flowKey=`（复用 `Collector.latest()` 的最近快照，不触发新采集；无快照 503、未知 Flow 404）；新增 9 项单测。前端新增「业务分析 · Flow 视图」独立页：Flow 列表（搜索 + 四种筛选 + 按不达标/静态不可行/成员数排序）、详情（基本信息、当前路径五项参数与风险、成员业务需求 vs 实测、链路上其他 Flow 跳转、候选路径卡片含静态合成与逐成员冲突、当前路径标记、刷新）；侧栏接通路由（全局总览 / 业务分析），其余入口仍置灰。验证：后端 collect 95（94 passed / 1 skipped）、`pnpm build` 通过（JS 204.8 kB / gzip 64.2 kB）、离线真实场景 HTTP 冒烟通过。文档同步 P0–P3 §11.3、UI 可行性分析期 2 状态、README 与 `work_bench/CLAUDE.md`。
