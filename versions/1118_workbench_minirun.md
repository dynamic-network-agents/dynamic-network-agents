# 修改记录

- 修改日期：2026-11-18
- 修改内容：落地 Work Bench 最小可运行版（Mini Run）。落文档 `docs/work_bench/B03_DebugConsole_mini_run_task.md`；实现后端（`work_bench/backend/`：FastAPI + 独立 SimulatorClient + 统一快照 `/api/snapshot` + 业务分类/候选路径离线加载 + 唯一调试写白名单 `POST /api/repath`）；实现前端（`work_bench/frontend/`：React+Vite+TS，2s 轮询快照、SVG 真实坐标拓扑、节点/链路/业务/事件表格、改 service 面板）；更新 `work_bench/CLAUDE.md` 与 `README.md` 只读条款为「只读 + 唯一调试写例外」；根 `.gitignore` 补充 node_modules/.pnpm-store/.uv-cache。
