# CLAUDE.md — Work Bench（B03 调试控制台）

本文件为 Claude Code 在 `work_bench/` 目录下工作时提供约束与口径。它是独立于主项目 `src/` 智能体的子项目；规划文档在 `docs/work_bench/`。

## 项目概述

**B03 Network Agent Workbench**：面向 B03 资源管控智能体研发的**只读观测、诊断与策略分析工作台**。它不重做仿真器界面，而是回答仿真器自带前端难以直接回答的问题：

1. 网络现在是什么状态（拓扑 / 节点 / 链路 / 业务）？
2. 哪些业务 QoS 不达标？静态不达标还是运行时拥塞？
3. 业务属于哪个 Flow、共享什么路径？
4. 哪些链路是真实瓶颈，承载了哪些业务？
5. 某条 Flow 迁移后可能缓解哪些链路、影响哪些业务？

**技术栈**：前端 React + Vite + TypeScript；后端 Python + FastAPI + WebSocket；图分析 NetworkX（控制台独立使用）。前后端分离，后端是唯一的仿真器 API 客户端。

**文档依据**（`docs/work_bench/`）：`B03_调试控制台企划书.md`（评审与 V1.1 优化建议）、`B03_DebugConsole_task_split.md`（任务拆分，权威任务来源）。

## 三条硬约束（最高优先级，任何任务不得违反）

1. **只读**：控制台后端只实现仿真器公开 API 的 GET 调用。**禁止** `POST /services/{serviceId}/path`、`POST /simulation/start` 及任何写接口。What-if 只在本地分析模型执行，不下发任何变更。
2. **独立**：控制台不依赖尚未稳定的 Agent `src/algorithms`。Work Bench 拥有自己的数据模型与 NetworkX 分析模块，可独立启动、独立测试。Agent 公共模块稳定后再抽取共享。
3. **Token 安全**：Token 只由后端读取；不进前端、不进 WebSocket 消息、不进日志、不入代码/提交。默认绑定 localhost。

## 数据口径（非显然，必须遵守）

- **flow 是路径控制与分析的核心对象，不是 service**。同一对源/目的 UAV 的多条业务共享一条 flow 级路径。不能把每条 Service 当作独立路径控制对象；改一条业务的路径可能影响同 flow 其他业务。界面须明确区分「业务 Service」与「路径控制对象 Flow」。
- **静态 QoS ≠ 实测 QoS**，必须分开展示。静态路径 QoS 是链路参数合成（时延求和、抖动平方和开方、带宽取最小、丢包组合、误码累加+容差）；实测 QoS 是逐秒统计（`actual.qosMeet` 为综合达标布尔）。
- **单位差异**：`actual.errPct` 是百分数（0~100），`requirement.ber` 是无量纲误码率，二者不可直接比较。逐项诊断须显式处理单位与定义差异。
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
- Flow：flowKey = srcIP + dstIP（按仿真器 `_flow_for` 实际规则规范化）
- Path：nodes[] / links[] / staticQoS / measuredQoS（关联展示）

## 目录结构（规划）

```
work_bench/
├── README.md           # 本文件：项目概览
├── CLAUDE.md           # 本文件：工作约束与口径
├── backend/
│   ├── main.py
│   ├── api/            # routes.py + websocket.py
│   ├── datasource/     # offline.py + simulator_client.py + collector.py
│   ├── models/         # snapshot/node/link/service/flow/path
│   ├── analysis/       # qos/flow/hotspot/graph/what_if
│   └── tests/
└── frontend/
    └── src/            # app/views/components/hooks/stores/types
```

当前本目录（`work_bench/`）仅有 `README.md` 与 `CLAUDE.md`，工程代码尚未创建；规划文档在 `docs/work_bench/`。

## 数据健康状态（前端必须可见）

`LIVE` / `STALE` / `PARTIAL` / `DISCONNECTED` / `OFFLINE`，并展示最近采集时间、仿真实例、仿真时间、事件游标、WebSocket 状态。不得让旧数据伪装成实时数据。

## 编码规则

- **先确认再动手**：每个 coding 任务先给方案（目标/涉及文件/关键设计/验收标准），确认后再写代码，不自行拍板。
- **不伪造数据**：缺失字段显示 `unknown`/`null`，不默认填零；不允许为了让页面好看而编造值。所有分析结果可追溯到输入字段和计算规则。
- **单元测试跟随被测模块**：后端 `backend/tests/`；算法层用固定样例 + 单元测试驱动（Flow 分组 / QoS 计算 / 热点指标 / 数据一致性 / 只读安全回归）。
- **口径可解释**：flow 数、需求带宽、实测带宽、链路容量不得混为一个指标；估算值明确标记。
- **先正确后好看**：优先级为 数据正确性 > 对象关系正确性 > 诊断解释能力 > 页面丰富度 > 视觉效果。

## 开发顺序（见 task_split.md，权威）

里程碑 M0（工程底座/安全边界）→ M1（实时总览 + 统一快照）→ M2（Service/Flow/Path 关系）→ M3（QoS 与热点诊断）→ M4（事件对照）→ M5（What-if）→ M6（历史回放 + 3D，可延后）。

**MVP 止于 M3 基础能力**。Sprint 顺序：S1 可启动/可连接/只读 → S2 统一快照 + 拓扑总览 → S3 Flow 与路径 → S4 QoS 与热点 → S5 事件对照 → S6 What-if → S7 回放/3D。

## 待确认事项（实现前必须经代码/接口实测，不得前端自行假设）

1. flowKey 规范化规则，尤其源/目的反向是否共享同一 Flow（须对齐仿真器 `_flow_for`）。
2. `/services`、`/nodes`、`/links` 分页边界与全量读取方式。
3. 服务详情/路径接口中路径字段的最终结构。
4. `actual.effBwBps` 是否可用于跨业务求和近似链路吞吐。
5. `actual.errPct` 与 `requirement.ber` 除单位外的统计口径差异。
6. 离线业务文件与实时 serviceId 的覆盖率。
7. 计划/实际事件的关联字段是否足够。
8. 仿真实例切换时事件游标与历史快照的重置规则。
9. 场景坐标是否始终可用、移动节点坐标的实时来源。

未确认内容先显示 `unknown` 或「待验证」，不在数据层固化猜测。

## 复用主项目既有事实（需保持一致）

- 链路五项参数：`delayMs` / `jitterMs` / `bandwidthBps` / `ber` / `packetLossRate`。
- 仿真器公开 API 前缀 `/api/open/v1`，鉴权头 `X-Open-Token`。
- `node_move` 事件当前存在缺陷（脚本属性结构与处理读取字段不一致、`linkTypes.json` 缺 `losMeters`），控制台必须以实际 API 观测为事实来源。
- 详见主 `CLAUDE.md`「关键事实」与 `docs/agents/智能体设计文档.md` 第 7 节（两套 QoS 判定公式与容差）。
