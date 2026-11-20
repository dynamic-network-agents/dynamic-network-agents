# Work Bench — B03 调试控制台

面向 **B03「资源受限环境下通信网络资源管控」** 赛题资源管控智能体的**只读网络观测、诊断与策略分析工作台**。

> 项目代号：B03-WorkBench · 文档版本：V1.1 · 日期：2026-11-18

## 这是什么

不是把仿真器界面重做一遍，而是解决仿真器自带前端难以直接回答的关键问题：

- 当前网络拓扑、节点、链路和业务究竟是什么状态？
- 多条业务如何共享同一条 flow 路径？
- 哪些链路是真实瓶颈，瓶颈上承载了哪些业务？
- 业务 QoS 不达标，是路径本身不满足静态约束，还是路径可行但运行时发生拥塞？
- 仿真脚本计划发生的扰动，是否真的在运行时发生了？

**核心定位**：面向网络资源管控智能体的**只读观测、诊断与策略分析**工作台（含唯一调试写例外：改路径）。首要职责是帮开发者快速定位问题，而非做成复杂运维平台。

> 当前已实现「最小可运行版」（Mini Run）：拓扑图、节点/链路/业务/事件表格、1–2s 轮询、改 service 面板。见 [`docs/work_bench/B03_DebugConsole_mini_run_task.md`](../docs/work_bench/B03_DebugConsole_mini_run_task.md)。

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | React + Vite + TypeScript |
| 后端 | Python + FastAPI + WebSocket |
| 图分析 | NetworkX（控制台独立使用） |
| 2D 拓扑 | react-force-graph / ECharts（优先真实坐标布局） |
| 表格 / 图表 | Ant Design Table / ECharts |

## 三条硬约束

1. **只读 + 唯一调试写例外**：后端对仿真器公开 API 只调用 GET。**唯一写例外**是 `POST /services/{serviceId}/path`（路径下发），仅经工作台自身 `POST /api/repath` 转发（写接口白名单仅此一个）。仍禁止 `POST /simulation/start` 等任何其他写操作。
2. **独立**：不依赖尚未稳定的 Agent 目录，可独立启动、独立测试、独立开发。
3. **Token 安全**：Token 只在后端，不向前端、WebSocket、日志泄露，默认绑定 localhost。

## 快速开始（最小可运行版）

**前提**：仿真器已启动（公开 API 在 `http://127.0.0.1:10100`）。

```bash
# 1) 后端依赖
cd work_bench/backend && uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt

# 2) 前端依赖
cd ../frontend && pnpm install

# 3) 启动后端（Token 由 run.sh 自动从 simulator/conf/gateway.json 读取，不打印不落盘）
cd ..
BG_SERVICE_PATH=$PWD/../simulator/data/scenarios/<conf>/<sce>/bg-service.json \
SERVICE_PATHS_PATH=$PWD/../simulator/data/scenarios/<conf>/<sce>/service-paths.json \
./backend/run.sh

# 4) 另开终端启动前端
cd frontend && pnpm dev
```

打开 http://localhost:5173/ （前端已代理 `/api` 到后端 `127.0.0.1:8000`）。

- `BG_SERVICE_PATH` / `SERVICE_PATHS_PATH` 可选：前者用于业务「背景/测试」分类，后者用于「改 service」候选路径；不设置则分类显示 `unknown`、候选路径为空。
- 后端接口：`GET /api/health`、`GET /api/snapshot`（前端唯一数据源，2s 轮询）、`GET /api/candidates?serviceId=`、`POST /api/repath`（唯一写白名单）。

## 目录结构（最小可运行版）

```
work_bench/
├── README.md               # 本文件：概览 + 快速开始
├── CLAUDE.md               # Claude Code 工作约束与口径
├── backend/                # FastAPI 后端（最小版）
│   ├── main.py             # 路由：health / snapshot / candidates / repath
│   ├── config.py           # env/.env 配置 + Token 读取
│   ├── simulator_client.py # 独立仿真 API client（GET + 唯一 set_service_path）
│   ├── offline.py          # bg-service.json / service-paths.json 加载
│   ├── snapshot.py         # 统一快照聚合 + 采集器状态
│   ├── requirements.txt
│   ├── run.sh              # 一键启动
│   └── .env.example
└── frontend/               # React + Vite + TS 前端（最小版）
    └── src/                # App.tsx（页面+轮询+表格+改 service）/ TopologyView.tsx / api.ts / types.ts
```

> 规划文档与全量任务拆分在 `docs/work_bench/`；最小可运行版范围见 `docs/work_bench/B03_DebugConsole_mini_run_task.md`。

## 核心数据模型

```
Service ──flowKey──▶ Flow ──pathId──▶ Path
```

- **Service**：业务（serviceId / type / category / priority / requirement / actual / status）
- **Flow**：路径控制对象（flowKey = srcIP+dstIP，成员业务共享路径）
- **Path**：路径（nodes[] / links[] / staticQoS / measuredQoS）

**关键认知**：路径是 flow 级，不是 service 级。同一对源/目的 UAV 的多条业务共享一条路径，改一条会影响同 flow 其他业务。

## 里程碑

| 里程碑 | 内容 | 优先级 |
|---|---|---|
| M0 | 工程底座、只读客户端、数据契约、安全边界 | P0 |
| M1 | 离线数据 + 实时采集 + 统一快照 + 2D 拓扑 | P1 |
| M2 | Service / Flow / Path 关系建模与视图 | P1 |
| M3 | 静态/实测 QoS、链路负载、热点诊断 | P1/P2 |
| M4 | 计划事件与实际事件对照 | P2 |
| M5 | 候选路径比较与 What-if 分析 | P2 |
| M6 | 历史回放 + 3D（可延后） | P3 |

**MVP 止于 M3 基础能力**。3D、历史回放、自动路径下发、仿真启动均不在 MVP 范围。

## 开发顺序原则

**数据正确性 > 对象关系正确性 > 诊断解释能力 > 页面丰富度 > 视觉效果**。

## 文档索引

- [`docs/work_bench/B03_调试控制台企划书.md`](../docs/work_bench/B03_调试控制台企划书.md) — 评审与 V1.1 优化建议（定位、必须修正的关键问题、页面结构、技术选型）
- [`docs/work_bench/B03_DebugConsole_task_split.md`](../docs/work_bench/B03_DebugConsole_task_split.md) — 任务拆分（Epic A–H、测试、Sprint 顺序、MVP 验收清单，**权威任务来源**）
- [`CLAUDE.md`](CLAUDE.md) — Claude Code 在此目录工作时的约束与口径
