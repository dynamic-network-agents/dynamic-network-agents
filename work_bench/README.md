# Work Bench — B03 调试控制台

面向 **B03「资源受限环境下通信网络资源管控」** 赛题资源管控智能体的**只读网络观测、诊断与策略分析工作台**。

> 项目代号：B03-WorkBench · 文档版本：V1.2 · 日期：2026-11-24

## 这是什么

不是把仿真器界面重做一遍，而是解决仿真器自带前端难以直接回答的关键问题：

- 当前网络拓扑、节点、链路和业务究竟是什么状态？
- 多条业务如何共享同一条 flow 路径？
- 哪些链路是真实瓶颈，瓶颈上承载了哪些业务？
- 业务 QoS 不达标，是路径本身不满足静态约束，还是路径可行但运行时发生拥塞？
- 仿真脚本计划发生的扰动，是否真的在运行时发生了？

**核心定位**：面向网络资源管控智能体的**只读观测、诊断与策略分析**工作台（含唯一调试写例外：改路径）。首要职责是帮开发者快速定位问题，而非做成复杂运维平台。

> 当前已实现：拓扑图、Flow 视图（无序 IP 对聚合、路径高亮、成员筛选）、业务详情（需求 vs 实测、静态 QoS 与可行性、所属 Flow、路径链路跳转）、链路需求侧负载、总览指标条、节点/链路/业务/事件表格、1–2s 轮询、改 service 面板。见 [`docs/work_bench/B03_DebugConsole_mini_run_task.md`](../docs/work_bench/B03_DebugConsole_mini_run_task.md)。
> 端口/令牌/记账口径与部署方式见 [`docs/work_bench/B03_Workbench_端口令牌与服务器部署.md`](../docs/work_bench/B03_Workbench_端口令牌与服务器部署.md)。

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | React + Vite + TypeScript |
| 后端 | Python + FastAPI + pydantic 数据契约（当前纯 HTTP 轮询，无 WebSocket） |
| 图分析 | NetworkX（控制台独立使用） |
| 2D 拓扑 | SVG 按真实坐标（当前实现） |

## 三条硬约束

1. **只读 + 唯一调试写例外**：后端对仿真器 API 只调用 GET。**唯一写例外**是 `POST /services/{serviceId}/path`（路径下发），仅经工作台自身 `POST /api/repath` 转发（写接口白名单仅此一个）。仍禁止 `POST /simulation/start` 等任何其他写操作。正式录分可置 `WORKBENCH_ALLOW_REPATH=0` 关闭写入口。
2. **独立**：不依赖尚未稳定的 Agent 目录，可独立启动、独立测试、独立开发。
3. **Token 安全**：Token 只在后端，不向前端、WebSocket、日志泄露，默认绑定 localhost。

## 观测通道（V1.2，不污染 agent 统计）

仿真器把 API 调用记到两本账：

- 带 `X-Open-Token` → `llm_gateway_call_stat.log`（agent 统计，`/api/ctrl/v1/agent-calls` 读的就是它）；
- 其余（含 ctrl 令牌）→ `llm_gateway_front_stat.log`（前端账）。

工作台默认走**仿真器前端同款**的 ctrl 令牌调 `/api/open/v1`：接口、字段、错误码不变，只是调用不写进 agent 统计台账。

```bash
SIM_AUTH=ctrl                # 默认：ctrl 令牌；open=显式降级（会污染统计，仅排障用）
SIM_CTRL_TOKEN=              # 可直接给；留空则 run.sh 自动读 gateway.json 的 ctrlToken
SIM_TOKEN_FILE=              # 或指向 gateway.json（按 SIM_AUTH 取对应键）
WORKBENCH_SVCMETA=1          # 用 /api/ctrl/v1/svc-meta 取实时业务分类
WORKBENCH_RUNINFO=1          # 用 /api/ctrl/v1/run-info 取运行态（状态/实例/脚本进度）
WORKBENCH_ALLOW_REPATH=1     # 正式录制置 0
```

**不做静默降级**：ctrl 模式找不到 ctrlToken 时不会自动改用公开令牌，而是启动告警 + 空令牌（health 里 `token_configured=false`）。`SIM_AUTH=open` 时 svc-meta 自动关闭（open 令牌调控制面会被 1006 拒绝且会写进 agent 统计），分类只能退回离线 `bg-service.json`。

## 数据契约、分页与数据健康（V1.3）

- **契约**：`backend/models/` 用 pydantic 固化 Snapshot/Node/Link/Service/Path/Requirement/Actual；`snapshot_version` 只在破坏性变更时 +1。未知字段保留（`extra="allow"`），不因仿真器加字段而报错。
- **分页**：仿真器 `page/size` 默认 500、上限 2000。`GET /links`、`GET /services` **默认不是全量**，后端已改为循环取全，并用 `/topology` 的链路总数对账；不一致或页数超限会写进 `pagination.note` 并降级健康状态。
- **健康状态**：`live` / `partial`（部分核心失败、缓存仍新鲜）/ `stale`（有数据但超过 `WORKBENCH_STALE_AFTER_S`）/ `disconnected`（核心全失败，返回缓存并标注 `data_age_s`）/ `offline`（显式离线模式）。
- **运行态（`sim`）**：来自控制面 `GET /api/ctrl/v1/run-info`（只认 ctrl 令牌），含 `status`（running/paused/joining/finished/idle）、当前实例/场景/脚本、`t0TsUs` 仿真起点与引擎进度。取不到时 `status=unknown` + `error` 说明原因，不伪造。注意 `t0TsUs` 是起点，**当前仿真时间**仍取 `/time` 的 `tsUs`。
- **风险链路与整体状态**：`riskLinks`（规则 A：R1 断 / R2 需求超订 / R3 相对上一快照劣化）、`riskSummary`（`unknown=true` 时 `total=null`，不显示成 0）、`overallStatus`（规则 B）。R2 是**需求侧估算**，文案写"需求超订"不写"带宽阻塞"；口径见 `docs/work_bench/B03_Network_Workbench_UI_可行性分析.md` §8 与 `backend/analysis/risk.py`。
- **离线模式**：`WORKBENCH_OFFLINE=1` + `NET_TOPO_PATH`（+ `BG_SERVICE_PATH`）只读场景文件，服务状态标 `unknown`、`actual=null`，不会伪装成实时数据。

## 快速开始（最小可运行版）

**前提**：仿真器已启动（API 在 `http://127.0.0.1:10100`）。

```bash
# 1) 后端依赖
cd work_bench/backend && uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt

# 2) 前端依赖
cd ../frontend && pnpm install

# 3) 启动后端（令牌由 run.sh 自动从 simulator/conf/gateway.json 读取 ctrlToken，不打印不落盘）
cd ..
./backend/run.sh

# 4) 另开终端启动前端（dev 模式）
cd frontend && pnpm dev
```

打开 http://localhost:5173/ （前端已代理 `/api` 到后端 `127.0.0.1:8000`）。

- `SERVICE_PATHS_PATH` 可选（「改 service」候选路径，来自 `service-paths.json`）；不设置则候选路径为空。
- `BG_SERVICE_PATH` 变为**可选兜底**：分类默认取实时 `svc-meta`，只有 svc-meta 不可用时才读离线 `bg-service.json`。
- 后端接口：`GET /api/health`、`GET /api/snapshot`（前端唯一数据源，2s 轮询）、`GET /api/candidates?serviceId=`、`POST /api/repath`（唯一写白名单）。

## 服务器部署（单进程 + SSH 隧道）

目标形态：**仿真器、agent、workbench 全部跑在服务器**；本机只通过 SSH 隧道访问。

服务器（Ubuntu 22.04.5 x64，Python 3.12+）**无需 Node**——前端 `frontend/dist/` 在本地构建后随目录拷过去，后端自动同源托管。

```bash
# 1) 本地构建并同步目录（dist/ 被 gitignore，需手动带上）
cd work_bench/frontend && pnpm build
rsync -av --exclude node_modules --exclude backend/.venv \
  ./ user@<服务器IP>:/path/to/work_bench/

# 2) 服务器上装后端依赖
cd /path/to/work_bench/backend
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt

# 3) 配置（backend/.env，或导出环境变量）
#    SIM_BASE_URL=http://127.0.0.1:10100/api/open/v1
#    SIM_AUTH=ctrl
#    SIM_TOKEN_FILE=/path/to/simulator/conf/gateway.json
#    # 可选：SERVICE_PATHS_PATH=/path/to/service-paths.json
#    # 可选：WORKBENCH_ALLOW_REPATH=0（正式录分）
#    # 可选：WORKBENCH_OFFLINE=1 + NET_TOPO_PATH=/path/to/net-topo.json（离线只读）
#    # 可选：WORKBENCH_STALE_AFTER_S=6 / WORKBENCH_PAGE_SIZE=500 / WORKBENCH_MAX_PAGES=20

# 4) 启动（后台常驻，默认绑 127.0.0.1:8000）
cd /path/to/work_bench
mkdir -p logs
nohup ./backend/run.sh >> logs/workbench.log 2>&1 &
```

清理日志（不必停服务）：`: > logs/workbench.log`；彻底删除目录后需重启后端。

本机访问（隧道，不对外暴露写接口）：

```bash
ssh -L 8000:127.0.0.1:8000 user@<服务器IP>
# 本地浏览器打开 http://127.0.0.1:8000/
```

- 后端自动检测 `frontend/dist/`：存在则同源托管前端（一条进程一个端口），不存在则退回纯 API（dev 模式走 `pnpm dev` + vite 代理）。
- 若确需局域网直连，可 `WORKBENCH_HOST=0.0.0.0 ./backend/run.sh`，但**写接口 `/api/repath` 会暴露给网内**，务必配合防火墙/反向代理加认证。
- 过渡形态（workbench 仍在本机、连服务器仿真器）：`ssh -L 20100:127.0.0.1:10100 user@<服务器IP>`，并把 `SIM_BASE_URL` 指到 `http://127.0.0.1:20100/api/open/v1`。

## 目录结构（最小可运行版）

```
work_bench/
├── README.md               # 本文件：概览 + 快速开始 + 部署
├── CLAUDE.md               # Claude Code 工作约束与口径
├── backend/                # FastAPI 后端（最小版）
│   ├── main.py             # 路由：health / snapshot / candidates / flow-candidates / repath（含写开关）
│   ├── models/             # pydantic 数据契约（Snapshot/Flow/Service/...）
│   ├── analysis/           # flow 聚合 / path / 静态 QoS / 链路负载 / 风险规则 / 候选可行性
│   ├── config.py           # env/.env 配置 + ctrl/open 令牌解析
│   ├── simulator_client.py # 独立仿真 API client（GET + 唯一 set_service_path + svc-meta）
│   ├── offline.py          # bg-service.json / service-paths.json 加载
│   ├── snapshot.py         # 统一快照聚合 + svc-meta 分类降级
│   ├── policy.py           # 写动作放行判定（repath 开关）
│   ├── tests/              # 单测（契约/分页/健康/Flow/QoS/风险/run-info/只读回归）
│   ├── requirements.txt
│   ├── run.sh              # 一键启动（自动读 ctrlToken）
│   └── .env.example
└── frontend/               # React + Vite + TS 前端
    └── src/
        ├── App.tsx         # 外壳：2s 轮询 + 选中态 + 实例切换清理
        ├── TopologyView.tsx# SVG 拓扑（真实坐标、缩放/平移、风险虚线与节点形状）
        ├── components/     # Sidebar/TopBar/KpiCards/TopologyPanel/DiagnosticsPanel/FlowAnalysisPage/
        │                   # CriticalServicesTable/LinkLoadTable/EventTimeline/
        │                   # DetailDrawer（Service/Flow/Link/Node）/DataInspector/RepathPanel
        ├── lib/            # format.ts（空值/单位）/ derive.ts（KPI 与达标率口径）/ selection.ts
        ├── api.ts          # 只读 GET + /api/repath 转发
        └── types.ts        # 与后端快照契约对齐
```

> 规划文档与全量任务拆分在 `docs/work_bench/`；最小可运行版范围见 `docs/work_bench/B03_DebugConsole_mini_run_task.md`。

## 测试

```bash
# 后端单测（用 workbench 自己的 venv；pytest 属于 dev 依赖）
cd work_bench/backend
uv pip install --python .venv/bin/python -r requirements-dev.txt
cd ..
backend/.venv/bin/python -m pytest backend/tests -q

# 服务器环境只读联调（自动）：可达则运行，不可达自动 skip；不启停仿真、不改路径
backend/.venv/bin/python -m pytest backend/tests/test_server_readonly.py -q -s
```

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

- [`docs/work_bench/B03_Workbench_端口令牌与服务器部署.md`](../docs/work_bench/B03_Workbench_端口令牌与服务器部署.md) — 端口全景、接口四分类、令牌与记账规则、本机/服务器/SSH 隧道
- [`docs/work_bench/B03_DebugConsole_P0-P3任务分析.md`](../docs/work_bench/B03_DebugConsole_P0-P3任务分析.md) — P0–P3 任务分解、实现状态、依赖顺序与验收
- [`docs/work_bench/B03_调试控制台企划书.md`](../docs/work_bench/B03_调试控制台企划书.md) — 评审与 V1.1 优化建议（定位、必须修正的关键问题、页面结构、技术选型）
- [`docs/work_bench/B03_DebugConsole_task_split.md`](../docs/work_bench/B03_DebugConsole_task_split.md) — 任务拆分（Epic A–H、测试、Sprint 顺序、MVP 验收清单，**权威任务来源**）
- [`CLAUDE.md`](CLAUDE.md) — Claude Code 在此目录工作时的约束与口径
