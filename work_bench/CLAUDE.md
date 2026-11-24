# CLAUDE.md — Work Bench（B03 调试控制台）

本文件为 Claude Code 在 `work_bench/` 目录下工作时提供约束与口径。它是独立于主项目 `src/` 智能体的子项目；规划文档在 `docs/work_bench/`。

## 项目概述

**B03 Network Agent Workbench**：面向 B03 资源管控智能体研发的**只读观测、诊断与策略分析工作台**。它不重做仿真器界面，而是回答仿真器自带前端难以直接回答的问题：

1. 网络现在是什么状态（拓扑 / 节点 / 链路 / 业务）？
2. 哪些业务 QoS 不达标？静态不达标还是运行时拥塞？
3. 业务属于哪个 Flow、共享什么路径？
4. 哪些链路是真实瓶颈，承载了哪些业务？
5. 某条 Flow 迁移后可能缓解哪些链路、影响哪些业务？

**技术栈**：前端 React + Vite + TypeScript；后端 Python + FastAPI（当前纯 HTTP 轮询，无 WebSocket）；图分析 NetworkX（控制台独立使用）。前后端分离，后端是唯一的仿真器 API 客户端。

**文档依据**（`docs/work_bench/`）：`B03_调试控制台企划书.md`（评审与 V1.1 优化建议）、`B03_DebugConsole_task_split.md`（任务拆分，权威任务来源）、`B03_DebugConsole_mini_run_task.md`（最小可运行版任务拆分，当前实现范围）、`B03_Workbench_端口令牌与服务器部署.md`（端口/令牌/记账口径与部署方式，V1.2 起）、`B03_DebugConsole_P0-P3任务分析.md`（P0–P3 任务、状态与验收）。

## 三条硬约束（最高优先级，任何任务不得违反）

1. **只读 + 唯一调试写例外 + 观测不污染 agent 统计**：控制台后端对仿真器 API 只实现 GET 调用。**唯一写例外**是 `POST /services/{serviceId}/path`，且只经工作台自身的 `POST /api/repath` 转发——全项目写接口白名单仅此一个。仍**禁止** `POST /simulation/start` 及任何其他写接口。改一条业务 = 改整条 flow，会影响同源目的的其他业务，界面必须明确提示。其余 What-if 只在本地分析模型执行，不下发变更。
   - 观测通道固定走 ctrl 令牌（`X-Ctrl-Token`，仿真器前端同款）：调用落 `front_stat`，**不得**写进 `call_stat`（`GET /api/ctrl/v1/agent-calls` 读的 agent 统计台账）。
   - 禁止静默降级：找不到 ctrl 令牌时报错并告警，只有显式 `SIM_AUTH=open` 才允许改用公开令牌；open 通道下 svc-meta 自动关闭（避免每轮 1006 噪声）。
   - 写开关 `WORKBENCH_ALLOW_REPATH=0` 时 `/api/repath` 必须返回 403（默认开启便于调试；正式录分时应置 0）。
2. **独立**：控制台不依赖尚未稳定的 Agent `src/algorithms`。Work Bench 拥有自己的数据模型与 NetworkX 分析模块，可独立启动、独立测试。Agent 公共模块稳定后再抽取共享。
3. **Token 安全**：Token 只由后端读取；不进前端、不进 WebSocket 消息、不进日志、不入代码/提交。`ctrlToken` 等同于此前的公开令牌，同样不得泄漏。默认绑定 localhost。

## 数据口径（非显然，必须遵守）

- **flow 是路径控制与分析的核心对象，不是 service**。同一对源/目的 UAV 的多条业务共享一条 flow 级路径。不能把每条 Service 当作独立路径控制对象；改一条业务的路径可能影响同 flow 其他业务。界面须明确区分「业务 Service」与「路径控制对象 Flow」。
- **静态 QoS ≠ 实测 QoS**，必须分开展示。静态路径 QoS 是链路参数合成（时延求和、抖动平方和开方、带宽取最小、丢包组合、误码累加+容差）；实测 QoS 是逐秒统计（`actual.qosMeet` 为综合达标布尔）。
- **单位差异**：`actual.errPct` 是百分数（0~100），`requirement.ber` 是无量纲误码率，二者不可直接比较。逐项诊断须显式处理单位与定义差异。
- **业务分类来源必须标注**：优先实时 `GET /api/ctrl/v1/svc-meta`（`categorySource=simulator`）；失败退回离线 `bg-service.json`（`offline_mapping`）；都没有标 `unknown`。不得把离线计划当实时事实。
- **热点三层次**：结构热点（度数/介数）、流量热点（flow 数/业务数/需求带宽）、性能热点（链路劣化/QoS 不达标）。`flow_count` ≠ 链路利用率；不得把中心性直接等同于拥塞。
- **事实 / 推断 / 离线配置三分离**：实时 API 是事实；分析值为计算结果（标记 `is_estimated`）；离线场景文件（`net-topo.json`、`bg-service.json`、`scripts/script-NN.json`）是计划/配置，不是当前状态。
- **计划事件 ≠ 已发生事件**。脚本事件是「计划」，实际事件来自 `GET /events`。不得用脚本移动事件直接驱动节点位置动画；实际位置只由实时观测更新。

## 核心数据模型

```
Service ──flowKey──▶ Flow ──pathId──▶ Path
                       │
                       ├── memberServiceIds[]
                       ├── srcNodeId / dstNodeId
                       └── pathSegments[] (nodes[] + links[])
```

- Service：serviceId / serviceType / category / priority / requirement / actual / status
- Flow：flowKey = `"<ipLo>|<ipHi>"`（无序 IP 对推导；公开 API 不暴露仿真器 flow 表，属推导值）
- Path：nodes[] / links[] / staticQoS / measuredQoS（关联展示）

## 目录结构（现状）

```
work_bench/
├── README.md                 # 项目概览 + 部署/快速开始
├── CLAUDE.md                 # 本文件：工作约束与口径
├── backend/
│   ├── main.py               # 路由：health / snapshot / candidates / flow-candidates / repath（含写开关）
│   ├── models/               # pydantic 数据契约（Snapshot/Node/Link/Service/Flow/Path/Actual）
│   ├── analysis/             # 本地分析：flow / path / qos / load / risk（规则 A/B）/ candidates（候选可行性）
│   ├── config.py             # env/.env + 令牌解析（ctrl/open 两种通道）
│   ├── simulator_client.py   # 仿真 API client（GET + 唯一 set_service_path + svc-meta）
│   ├── snapshot.py           # 统一快照聚合（含 svc-meta 分类与降级）
│   ├── offline.py            # bg-service.json / service-paths.json 加载
│   ├── policy.py             # 写动作放行判定（repath 开关/留痕提示）
│   ├── run.sh                # 一键启动（自动读 gateway.json 的 ctrlToken）
│   └── tests/                # 单测：令牌解析 / 请求头 / svc-meta 降级 / 写开关
└── frontend/src/             # App.tsx（外壳/轮询）/ TopologyView.tsx / components/（页面组件）/ lib/（口径与格式化）/ api.ts / types.ts
```

规划目标态（`api/`、`datasource/`、`models/`、`analysis/` 分层）见 `docs/work_bench/B03_DebugConsole_task_split.md`；当前已拆出 `models/` 与 `analysis/`，路由仍集中在 `main.py`。

## 数据健康状态（前端必须可见）

`LIVE` / `STALE` / `PARTIAL` / `DISCONNECTED` / `OFFLINE`，并展示最近采集时间、仿真实例、仿真时间、事件游标。不得让旧数据伪装成实时数据。**核心资源失败时返回缓存**，并给出 `data_age_s` 与 `stale_resources`；分页不完整/与 `/topology` 对账不一致也算非 live。`svc_meta` 拉取失败不算 PARTIAL（属增强项，退离线映射并在界面标注）。离线模式（`WORKBENCH_OFFLINE=1`）服务状态标 `unknown`、`actual=null`，不得伪装成实时值。

## 编码规则

- **先确认再动手**：每个 coding 任务先给方案（目标/涉及文件/关键设计/验收标准），确认后再写代码，不自行拍板。
- **不伪造数据**：缺失字段显示 `unknown`/`null`，不默认填零；不允许为了让页面好看而编造值。所有分析结果可追溯到输入字段和计算规则。
- **单元测试跟随被测模块**：后端 `backend/tests/`；算法层用固定样例 + 单元测试驱动（Flow 分组 / QoS 计算 / 热点指标 / 数据一致性 / 只读安全回归）。
- **口径可解释**：flow 数、需求带宽、实测带宽、链路容量不得混为一个指标；估算值明确标记。
- **先正确后好看**：优先级为 数据正确性 > 对象关系正确性 > 诊断解释能力 > 页面丰富度 > 视觉效果。

## Skills 使用（`.claude/skills/`）

项目内的 skill 不会被本会话自动加载（需手动读 `SKILL.md` 并按其执行）。前端/契约类改动按以下场景使用：

| 场景 | Skill | 时点 |
|---|---|---|
| 新页面/新面板/改版 | `frontend-design` | 动手写组件前读 |
| 写/改 React 组件、状态、渲染 | `vercel-react-best-practices` | 编码时对照 |
| 页面完成后自检（a11y/交互/规范） | `web-design-guidelines` | 提交前复核 |
| 图表、仪表盘、可视化 | `dataviz` | 出现图表时 |
| 改 pydantic ↔ TS 契约、查字段不一致 | `api-contract-forge` | 每次动契约时 |
| 方案/决策压力测试 | `grilling` | 重大设计决策前 |
| 会话交接 | `handoff` | 换会话/换代理时 |

纯后端改动（不涉及 UI/契约）不强制走前端 skill，但契约变更必须过 `api-contract-forge` 的检查口径。

## 运行与测试

```bash
# 后端单测（workbench 自己的 venv；pytest 是 dev 依赖）
cd work_bench/backend
uv pip install --python .venv/bin/python -r requirements-dev.txt
cd ..
backend/.venv/bin/python -m pytest backend/tests -q

# 服务器环境只读联调（自动；不可达自动 skip；不启停仿真、不改路径）
backend/.venv/bin/python -m pytest backend/tests/test_server_readonly.py -q -s

# 前端构建
cd frontend && pnpm build
```

## 开发顺序（见 task_split.md，权威）

里程碑 M0（工程底座/安全边界）→ M1（实时总览 + 统一快照）→ M2（Service/Flow/Path 关系）→ M3（QoS 与热点诊断）→ M4（事件对照）→ M5（What-if）→ M6（历史回放 + 3D，可延后）。

**MVP 止于 M3 基础能力**。Sprint 顺序：S1 可启动/可连接/只读 → S2 统一快照 + 拓扑总览 → S3 Flow 与路径 → S4 QoS 与热点 → S5 事件对照 → S6 What-if → S7 回放/3D。

## 待确认事项（实现前必须经代码/接口实测，不得前端自行假设）

1. ~~flowKey 反向是否同 Flow~~ 已确认：`flow_of_ips` 用**无序 IP 对**匹配，反向同一 flow（2026-11-24 核查）。
2. ~~分页边界~~ 已确认：`page/size`，默认 500、上限 2000；已改为循环取全 + `/topology` 对账。
3. 服务详情/路径接口中路径字段的最终结构。
4. `actual.effBwBps` 是否可用于跨业务求和近似链路吞吐。
5. `actual.errPct` 与 `requirement.ber` 除单位外的统计口径差异。
6. `svc-meta` 的业务覆盖范围（业务未启动/部分失败时是否与 `/services` 一致）。
7. 计划/实际事件的关联字段是否足够。
8. 仿真实例切换时事件游标与历史快照的重置规则。
9. 场景坐标是否始终可用、移动节点坐标的实时来源。
10. 服务器部署下 10001/10002 是否需要额外端口映射（当前沿用包内原版 compose，不映射）。

未确认内容先显示 `unknown` 或「待验证」，不在数据层固化猜测。

## 复用主项目既有事实（需保持一致）

- 链路五项参数：`delayMs` / `jitterMs` / `bandwidthBps` / `ber` / `packetLossRate`。
- 仿真器公开 API 前缀 `/api/open/v1`：`X-Open-Token` 与 `X-Ctrl-Token` 都被接受；只有带 `X-Open-Token` 的请求才写 agent 统计台账（`llm_gateway_call_stat.log`）。
- flowKey 不分方向（无序 IP 对）；一次改路径同时改双向，命中的是同源/目的对的全部业务。
- 分页参数是 `page`/`size`（默认 500、上限 2000）；`/topology` 不分页，可用于对账。
- `actual` 只有 6 键；`qosMeet` 容差：delay +1.0ms、jitter/loss +1e-9、带宽无容差、`errPct ≤ ber×100+1e-9`。
- `node_move` 事件当前存在缺陷（脚本属性结构与处理读取字段不一致、`linkTypes.json` 缺 `losMeters`），控制台必须以实际 API 观测为事实来源。
- 详见主 `CLAUDE.md`「关键事实」与 `docs/agents/智能体设计文档.md` 第 7 节（两套 QoS 判定公式与容差），端口/令牌细节见 `docs/work_bench/B03_Workbench_端口令牌与服务器部署.md`。
