# B03 Work Bench — 最小可运行版本任务拆分（Mini Run）

> 项目：B03-WorkBench · 文档版本：Mini Run 1.0 · 日期：2026-11-18
> 定位：`B03_DebugConsole_task_split.md`（权威全量拆分）的**最小可运行子集**，先跑起来用于日常调试。
> 已确认决策：①「更改 service」写操作允许作为**调试例外**纳入（唯一写白名单 `POST /api/repath`）；② 技术栈 React + Vite + TS（前端）+ FastAPI（后端）。

---

## 1. 目标（7 条原始需求 → 落地口径）

1. 画出 topo 图 → 用 `/topology` 真实坐标画 2D 拓扑，节点按类型/在线态、链路按 up/down 着色。
2. 表格列出节点 → `/topology` 的 nodes（含 position/status）。
3. 表格列出链路 → `/links` 的 links（**含 5 项参数**，`/topology` 的 links 不带 params，必须用 `/links`）。
4. 展示业务（背景 + 测试），列出参数和路径 → 公开 API 无 `category`；**V1.2 起优先取实时 `GET /api/ctrl/v1/svc-meta`**（`categorySource=simulator`），失败才退回离线 `bg-service.json`（`offline_mapping`），都没有标 `unknown`。
5. 展示事件 → `GET /events?sinceTsUs={游标}` 增量读。
6. 接口实时获取，1–2s 刷新 → 前端每 2s 轮询统一快照 `GET /api/snapshot`。
7. 提供更改 service 功能 → `POST /api/repath`（唯一写白名单），候选路径取自离线 `service-paths.json`。

---

## 2. 硬约束（含调试例外）

- 后端只调用仿真器 GET；**唯一例外**：`POST /services/{serviceId}/path`，仅经 `POST /api/repath` 转发，作为调试写通道。
- 全项目仅此一个写接口；`/api/repath` 之外的任何 POST 均禁止。`WORKBENCH_ALLOW_REPATH=0` 时该接口返回 403（默认开启便于调试；正式录分时应置 0）。
- **观测通道不污染 agent 统计**：默认用 ctrl 令牌（`X-Ctrl-Token`，仿真器前端同款）调 `/api/open/v1`，请求落 `front_stat`；只有显式 `SIM_AUTH=open` 才用公开令牌（会写进 `call_stat`，即 agent 统计台账）。
- Token 只读自 `SIM_CTRL_TOKEN` / `SIM_TOKEN` / `SIM_TOKEN_FILE`（或 `run.sh` 从 `simulator/conf/gateway.json` 读取），**不进前端、不进日志、不入代码/提交**；禁止静默降级到公开令牌。
- 默认绑定 `127.0.0.1`；服务器部署经 SSH 隧道访问。
- 写操作必须明确提示「改一条业务 = 改整条 flow，影响同源目的的其他业务」，并在响应里提示该操作会被记为 `source=agent` 的 path 事件。

---

## 3. 任务清单

### 后端（`work_bench/backend/`，FastAPI）

| # | 任务 | 关键设计 | 验收 |
|---|---|---|---|
| W-01 | 工程骨架 + 配置 | `config.py` 读 env/`.env`；`main.py` 起 FastAPI + CORS（仅前端 dev origin）+ 绑 localhost | 可独立启动；Token 不进日志 |
| W-02 | 只读 simulator client | `simulator_client.py`：GET topology/nodes/links/services/service/events/time + 唯一 `set_service_path`；统一超时/错误码/脱敏 | 断连返回可识别错误，进程不崩 |
| W-03 | 统一快照 `GET /api/snapshot` | `snapshot.py`：一次聚合 nodes+links+services(详情)+events(增量)+time+instanceId+health | 前端只调这一个接口；数字与 API 对得上 |
| W-04 | 业务分类映射 + 候选路径 | `offline.py`：`bg-service.json`→category；`service-paths.json`→候选路径 | 背景/测试/unknown 可追溯；文件缺失不报错 |
| W-05 | 写白名单 `POST /api/repath` | 转发 `POST /services/{id}/path`，返回 accepted/rejected+reason | 全项目仅此一个写接口 |

### 前端（`work_bench/frontend/`，React + Vite + TS）

| # | 任务 | 关键设计 | 验收 |
|---|---|---|---|
| W-06 | 骨架 + 轮询 + 健康状态 | 每 2s 拉 `/api/snapshot`；顶部显示 LIVE/PARTIAL/DISCONNECTED + 最近更新时间 | 刷新稳定；断连可见 |
| W-07 | 拓扑图 | SVG 按真实坐标画 nodes+links，缩放/平移/自适应，节点按类型着色 | 位置稳定不跳；区分 uav/ground/air |
| W-08 | 节点表 + 链路表 | 链路表列 5 项参数 | 与 API 全量一致；缺参显 `—` 不填 0 |
| W-09 | 业务表 | 列 serviceId/type/category/src/dst/priority/status/requirement/path/actual | 背景+测试都列；`errPct` 不与 `ber` 比较 |
| W-10 | 事件列表 | 增量展示时间/类型/目标/参数摘要 | 连续轮询不重复堆积 |
| W-11 | 改 service 面板 | 选业务→候选路径下拉（来自 service-paths.json）+ 手动 segments 输入→二次确认→提交→显示响应→下轮轮询观察变化 | 能观察路径/实测变化；flow 兄弟业务联动提示 |

### 文档与验收

| # | 任务 |
|---|---|
| W-12 | 更新 `work_bench/CLAUDE.md` + `README.md`：只读条款改为「只读 + 唯一调试写例外 `POST /api/repath`」 |
| W-13 | 联调验收 + 安全回归：各表数字与仿真 API 一致；全项目搜索确认写接口仅 `repath` 一个 |

---

## 4. 明确不做（留待后续 M3+）

静态 QoS 合成、热点识别、计划/实际事件对照、What-if 本地分析、3D、历史回放。

---

## 5. 待核对事项（运行期以真实返回为准）

1. `actual` 是否含 `qosMeet` 布尔：官方接口文档未列，主项目 `CLAUDE.md` 称存在。前端**有则显示、无则留空**，不臆造。
2. 分类路径与运行实例的对应：公开 API 不直接给 `suiteId`，`bg-service.json` / `service-paths.json` 由 `BG_SERVICE_PATH` / `SERVICE_PATHS_PATH` 环境变量显式指定。
3. `POST /services/{id}/path` 被拒时返回码/`reason` 结构以实际联调为准（文档口径 1001/1004）。

---

## 6. 完成标准（Definition of Done）

- 前后端可独立启动；`run.sh` 一条命令拉起后端。
- 只读安全回归：`grep` 全项目，写接口仅 `/api/repath`；Token 不出现在前端产物/日志/代码。
- 每个列表与仿真 API 数字对得上；空数据（如当前 0 业务）优雅显示空态。
- 「改 service」能提交并观察到下一轮快照的路径/实测变化。
