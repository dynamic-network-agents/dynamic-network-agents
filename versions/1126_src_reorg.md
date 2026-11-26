# 1126_src_reorg

**修改日期**：2026-11-26

**修改内容**：重组 `src/` 目录结构（**纯移动 + import 改写，不改任何算法逻辑**），
为后续引入 `agents/` 智能体入口留出清晰边界。顶层从「6 个平铺包」改为
「2 个入口 + 1 个共享底座」：

```
src/
├── common/          # 共享底座（baseline 与 agents 共用）
│   ├── simulator/   # 仿真器 HTTP 适配（← api/）
│   ├── perception/  # 感知层：冻结快照 + 事件流（← baseline/snapshot.py + event_source.py）
│   ├── modeling/    # 数学建模（← math_modeling/）
│   ├── algorithms/  # 算法库按领域三分：topology/（← graph.py + capacity.py）
│   │                #   path/（← k_shortest_paths.py + optimize.py）
│   │                #   flow/（← flow_planner.py 等 6 个）
│   ├── control/     # 闭环控制（← baseline/reroute_loop.py + dispatch_gate.py + verifier.py）
│   ├── config/      # 配置加载（← util/config.py）
│   └── util/        # 通用工具（预留）
├── baseline/        # 传统路径入口
└── agents/          # 智能体入口（预留）
```

依赖方向（单向无环）：`modeling ← topology/path/flow ← perception ← simulator
← control ← baseline/agents`。**感知层与闭环控制独立成层**，是为了让 baseline
与 agents 的对比实验公平——唯一差异只能是「谁来做规划决策」。

同步改写 46 个文件共 150 行 import；单测随被测模块下移
（`common/modeling/tests/`、`common/algorithms/{topology,path,flow}/tests/` 等）；
各包新建带职责说明的 `__init__.py`；`pyproject.toml` wheel `packages` 更新；
`src/CLAUDE.md`（模块地图/依赖方向/热路径）、根 `CLAUDE.md`（目录表）、
`README.md`（目录块）同步。修正两处依赖包深度的 `Path(__file__).parents[2]`
→ `parents[3]`（`common/modeling/link_quality.py`、`common/config/settings.py`）。

**行为不变**：`uv run pytest src/ tests/` 98 passed / 7 skipped（与重组前一致）；
`scripts/plan_dump.py` 黄金快照逐位一致（得分 244.0）；`scripts/smoke_epoch.py`
输出逐行一致（9 POST、无重复下发）；`scripts/feasible_bound.py` 正常运行；
`python -m src.baseline.main` 仍能启动。
