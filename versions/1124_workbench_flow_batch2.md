# 修改记录

- 修改日期：2026-11-24
- 修改内容：Work Bench 第二批（D-01 / D-02 / D-04 / E-02）。新增 `backend/analysis/`：按无序 IP 对聚合 Flow（反向同 Flow）、解析 path segments（连续性校验、反序自动归一、missingLinks）；`Snapshot` 增加 `flows` 与 `Flow` 契约；前端新增 Flow 面板（成员/分类/路径/达标统计、点选高亮与业务表筛选、"改一条=改双向"提示），业务表实测列改为 6 字段（D/J/B/E/L + qosMeet）并标注单位；集成测试改为自动探测服务器环境（不可达自动 skip），新增 Flow 成员数对账断言；离线 40 业务场景验证 40 服务 → 17 Flow（成员合计 40）。同步更新 P0–P3 状态、task_split §17、README、CLAUDE.md（含 skills 调用场景）。
