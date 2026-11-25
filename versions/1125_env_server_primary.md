# 修改记录

- 修改日期：2026-11-25
- 修改内容：确认并记录双环境口径。`root@121.43.114.121`（`netsim-dev`，Ubuntu 22.04.5 x86_64）为**主运行环境**——仿真器常驻（netsim/tx/rx/sim-media/eval 全部在跑，当前 `idle` @ `sce20261010-conf02/sce01`），仓库在 `/root/dynamic-network-agents` 且与 origin 同步，项目 venv 为 Python 3.15.2（无 uv/pnpm，有 node20/npm10/compose v5.8）；服务器实测 `pytest src/ tests/` 75 passed / 3 skipped。本机 Mac 降级为**备用环境**（Rosetta 慢，仅离线单测/临时调试）。同步更新根 `CLAUDE.md` 的「技术栈 / 运行环境 / 常用命令 / 关键事实（Rosetta）」四处，明确 workbench 只绑 127.0.0.1、经 `ssh -L 8000:127.0.0.1:8000` 访问，并记录 10000/10100/10010/10110 公网暴露、`ufw` 未启用的现状。
