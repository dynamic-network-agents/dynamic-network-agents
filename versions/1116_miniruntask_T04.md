# 修改记录

- 修改日期：2026-11-16
- 修改内容：完成最小化工程闭环（T0–T4）。搭建工程骨架（pyproject + configs/*.yaml + util/config + math_modeling/models）；接入仿真器（api/client 封装 12 接口 + algorithms/graph 构图）；数学内核（path_qos/qos_checker/link_quality/flow/measured_qos）；路径优化（k_shortest/optimize/executor）；闭环（orchestrator/main）+ 实机自测修复（构图改由 get_links 取带 params 的链路、extraLinkIds 语义纠正且 EXT001 改按 nodeId 剔除、确认公开 API 无 category 后 MVP 统一保护所有 running 业务）。
