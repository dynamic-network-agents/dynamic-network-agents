# 修改记录

- 修改日期：2026-11-23
- 修改内容：Work Bench 适配服务器部署（单进程 + 仅本机/SSH 隧道）。后端 `main.py` 自动托管 `frontend/dist/`（同源免 CORS、免 Node）；`config.py` 新增 `WORKBENCH_STATIC_DIR` / `WORKBENCH_CORS_ORIGINS`；`run.sh` 令牌解析改为 SIM_TOKEN > SIM_TOKEN_FILE > 自动探测 gateway.json；README 增加「服务器部署」小节，`.env.example` 补充新变量。
