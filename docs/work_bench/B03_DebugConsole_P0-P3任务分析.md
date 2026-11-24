# B03 调试控制台 — P0–P3 任务分析（可实施版）

> 文档版本：V1.0 · 日期：2026-11-24
> 依据：`B03_调试控制台企划书.md`（尤其第 9 节 P0–P3 定义）、`B03_DebugConsole_task_split.md`（Epic A–E）、`sim_src/` 事实核查（解码件行号）
> 结论先行：**P0–P3 = 企划书 M0–M3，是 MVP 边界**。当前实现已完成 P0 骨架与 P1 主体，缺口集中在"数据契约、分页完整性、Flow 建模、QoS/热点诊断"四块。

---

## 1. 范围与"完成"的定义

| 阶段 | 企划书定义（第 9 节） | 验收标准 |
|---|---|---|
| P0 | 工程与数据契约：前后端骨架、配置、统一模型、只读客户端 | 可独立启动；只注册 GET（唯一调试写例外见 §2）；Token 不出现在前端 |
| P1 | 数据采集与总览：离线加载、实时采集、统一快照、2D 拓扑 | 节点/链路/业务数量与 API 对得上；显示数据健康状态 |
| P2 | Service/Flow/Path：业务映射、Flow 聚合、共享路径展示 | 业务↔Flow 双向定位；共享路径可见 |
| P3 | QoS 与热点：静态 QoS、实测 QoS、链路负载指标 | 两套 QoS 不混淆；单位正确；热点结果可解释 |

**用途口径（已确认）**：调试为主、交付为辅。功能按"能否回答调试问题"取舍；架构图/截图/口径说明在最后半天补进竞赛报告，不为页面完整度做功能。

**明确不做**：WebSocket、3D、历史回放、What-if、事件计划/实际对照（P4 及以后）。
**本阶段延后**：E-04 热点排序、E-05 联动诊断（P3b 只做 E-03 的需求侧聚合）。

---

## 2. 已确认的设计决策

| 决策 | 结论 | 理由 |
|---|---|---|
| 数据契约 | pydantic 模型 + `snapshot_version` | 采集层就能暴露字段缺失/类型错误，而不是前端显示 `undefined` |
| WebSocket | 本阶段不做，保留 2s 轮询 | 仿真器 WS 服务（8091）20261106 起默认不启动；`/api/open/v1/ws/events` 只认公开令牌；nginx 未配 WS 转发 |
| 改路径开关 | 默认开（调试例外）；正式录分置 `WORKBENCH_ALLOW_REPATH=0` | 与既有选择一致；文档统一写"默认开 = 调试例外" |
| 数据健康阈值 | `STALE` = 最近成功采集距今 > 3×轮询（6s）；`PARTIAL` = 任一核心 GET 失败；`DISCONNECTED` = 全部失败；`OFFLINE` = 显式离线模式 | 简单可解释；用 `data_age_s` 反映本地采集新鲜度 |
| 观测通道 | ctrl 令牌（`X-Ctrl-Token`） | 调用落 `front_stat`，不计入 agent 调用统计 |
| P3 范围 | P3a（E-01/E-02）全做；P3b 只做 E-03 需求侧（`flow_count`/`service_count`/`demand_bps`/`demand_utilization`）；E-04/E-05 延后 | 调试优先：先回答"哪里不达标、为什么"，热点排序/联动不是当前瓶颈 |
| 静态 QoS 来源 | 复制公式到 workbench + 与 `src/math_modeling` 对拍测试 | 保持独立可运行，同时防止两套公式悄悄漂移 |
| Flow 视图 | 最小形态（列表+成员业务+当前路径+拓扑高亮+双向提示） | 候选路径/静态可行性等 E-01 完成后再挂进同一详情 |
| 验收 | P1/P2/P3 各一次真实运行（40 业务） | 结构性验收抓不到分页截断、实例切换这类问题 |

### 2.1 已核实的事实（改写了任务前提）

1. **flowKey 不区分方向**：`_flow_for` → `flow_of_ips` 用无序 IP 对匹配，一次下发同时装正向+反向（`openapi.py:1746`、`ctrl.py:615`、`ctrl.py:144`）。→ Flow 聚合按"无序 IP 对"分组；UI 必须提示"改一条 = 改双向"。
2. **分页参数 `page`/`size`，默认 500、上限 2000，默认不是全量**（`openapi.py:1519`）；`/topology` 不分页且返回全部链路（可用来对账）。→ 当前 `get_links()`/`get_services()` 不带分页，**超 500 会静默截断**，属 P1 正确性缺陷。
3. **`effBwBps` 是业务级收端收包速率**（≈需求×1.026），**不是链路吞吐**（`rx.py:539`、`tx.py:82`）。→ 只能标"业务实测带宽汇总估计"。
4. **`actual` 只有 6 个键**；`qosMeet` = 5 项 AND（delay +1.0ms、jitter +1e-9、带宽无容差、`errPct ≤ ber×100+1e-9`、loss +1e-9）（`core.py:106`、`:657`）。→ 逐项展示，两套误码口径分别标注。
5. **路径接口**：1004 → HTTP 409；`GET path` 的 `segments` 只有 link 元素（可能带 `auto:true`）；顺序取决于最近一次下发方向；pathId 由 `1000+seq` 生成，**不要写死格式**（`openapi.py:2058`、`:37`、`:1894`）。
6. **`/services` 有 5s 上游缓存**；列表不含 `actual`，实测值必须逐业务取详情。

---

## 3. 现状盘点

| 能力 | 状态 | 依据 |
|---|---|---|
| 前后端骨架、独立启动、单进程托管 | ✅ | `backend/main.py` + `frontend/dist` |
| 配置 + 令牌安全（ctrl/open 两通道） | ✅ | `backend/config.py` |
| 只读 client（含唯一写例外 `set_service_path`） | ✅ | `backend/simulator_client.py` |
| 统一数据契约（models / `snapshot_version`） | ✅ | `backend/models/` pydantic 契约 |
| 写开关（`WORKBENCH_ALLOW_REPATH`） | ✅ | `backend/policy.py` |
| 安全回归测试 | ✅ | `tests/test_readonly_surface.py`：写接口白名单 / 禁止仿真控制 / 令牌不入前端 |
| 离线加载（bg-service / service-paths） | ✅ | `backend/offline.py` |
| 实时采集（topology / links / services+详情 / events / time） | ✅ | `backend/snapshot.py` |
| 分页完整性 | ✅ | `page/size` 循环取全 + `/topology` 对账 |
| 统一快照 + 事件游标 | ⚠️ | 已有 `snapshot_version`；跨接口 `tsUs` 一致性仍待补（B-05） |
| 2D 拓扑（真实坐标、缩放/平移/自适应、节点形状、风险虚线、点击下钻） | ✅ | `frontend/src/TopologyView.tsx` + `components/TopologyPanel.tsx` |
| 数据健康状态 | ✅ | live/partial/stale/disconnected/offline + `data_age_s` |
| 业务分类（实时 svc-meta + 离线兜底 + 来源标注） | ✅ | `snapshot.py`、`config.py` |
| Service ↔ Flow ↔ Path | ✅ | Flow 聚合/视图/筛选 + Service 详情跨对象跳转 |
| 静态 QoS 合成 | ✅ | `analysis/qos.py`（公式+容差），逐业务/逐 Flow 标注 |
| 实测 QoS 逐项展示 | ✅ | 6 字段 + `qosMeet`，需求 vs 实测对照 |
| 链路负载 / 热点 | ⚠️ | 需求侧链路负载已做；热点排序 E-04/E-05 延后 |
| 仿真运行态（run-info） | ✅ | `snapshot.py` `_load_sim_status`；契约 `sim_src/netsim/openapi.py:2110` `_run_info()` |
| 风险链路 / 整体状态（规则 A/B） | ✅ | `analysis/risk.py` + 快照 `riskLinks`/`riskSummary`/`overallStatus`（2026-11-24 接线） |

---

## 4. P0 任务

| ID | 任务 | 状态 | 依赖 | 规模 |
|---|---|---|---|---|
| A-01 | 前后端工程骨架 | ✅ | — | — |
| A-02 | 只读 API client（包络/超时/频控退避） | ✅ | — | — |
| A-03 | 安全与运行配置（Token 只留后端、绑 localhost） | ✅ | — | — |
| A-04 | **pydantic 数据契约 + `snapshot_version`**：Snapshot/Node/Link/Service/Path 模型；前后端字段对齐 | ✅ | A-02 | M |
| A-05 | 写白名单口径统一：默认开 = 调试例外，录分置 0；文档与代码一致 | ✅/⚠️ | A-02 | S |
| A-06 | 调用治理：错误码映射（1001/1003/1004/1005/1006/2000）、重试幂等 | ⚠️ | A-02 | S |
| A-07 | 只读安全回归：全项目扫描写接口仅 repath 且可关；Token 不出前端/日志 | ✅ | A-02/A-05 | S |

**P0 验收**：`/api/health` 能说明通道与开关；前端产物与日志中 grep 不到令牌；写接口只有 `repath`，且 `WORKBENCH_ALLOW_REPATH=0` 时 403。

---

## 5. P1 任务

| ID | 任务 | 状态 | 依赖 | 规模 |
|---|---|---|---|---|
| B-01 | 离线场景加载 | ✅ | — | — |
| B-02 | 拓扑/节点/链路采集 | ✅ | A-02 | — |
| B-03 | 业务列表 + 详情（并发 + TTL 缓存） | ✅ | A-02 | — |
| B-04 | 事件增量（`sinceTsUs` 游标） | ✅ | A-02 | — |
| B-05 | 快照一致性：跨接口 `tsUs` 差异超阈值标 `partial`；实例变更重置游标/缓存 | ⚠️ | A-04、B-02~B-04 | M |
| B-06 | 数据健康补全：`STALE`/`OFFLINE`；展示最近成功采集、游标、快照时间 | ✅ | A-04 | S |
| B-07 | **分页完整性（新增，P1 正确性）**：`page/size` 循环取全；与 `/topology` 的链路总数对账；不一致标 `PARTIAL` | ✅ | A-02 | M |
| C-01 | 2D 拓扑画布 | ✅ | — | — |
| C-02 | 节点/链路状态渲染 + 参数劣化标记（R3 已做「对比上一快照」；对比离线基线未做） | ⚠️ | B-01 | S |
| C-03 | 总览指标区：5 张 KPI（在线节点/活动链路/测试业务/风险链路/整体状态）+ 诊断栏热点 Top 5 | ✅ | B-05、B-06、E-03 | M |

**P1 验收**：一次真实运行（≥40 业务）下，分页累计的链路/业务数与 `/topology`、`/services` 全量一致；断连→`DISCONNECTED`、数据滞后→`STALE`、部分接口失败→`PARTIAL` 均可见。

---

## 6. P2 任务

| ID | 任务 | 状态 | 依赖 | 规模 |
|---|---|---|---|---|
| D-01 | Flow 聚合：按**无序 IP 对**分组，成员业务列表；公开 API 读不到 flow 表，重复反向流无法检测（标注待核对） | ✅ | B-03、A-04 | M |
| D-02 | Path 对象：解析 `segments`、校验连续性、反序自动归一；记录 `pathId` 原值 | ✅ | D-01、B-02 | M |
| D-03 | 分类来源：实时 svc-meta 优先、离线兜底、`unknown` 兜底，不启用前缀推断 | ✅ | B-01、B-03 | — |
| D-04 | Flow 视图（最小形态）：列表 + 源/目的 + 成员业务 + 当前路径 + 拓扑高亮 + "改一条=改双向"提示 | ✅ | D-01、D-02、C-01 | L |
| D-05 | Service 详情与跳转：Service↔Flow↔Path↔Link；共享路径显式标注；缺失值 `unknown` | ✅ | D-02~D-04 | M |
| T-01 | Flow 分组测试：同对合并、反向同 key、不同对不误并、成员增删 | ❌ | D-01 | S |

**P2 验收**：任取一条业务能定位到 Flow 及其全部成员；反向业务归同一 Flow；拓扑高亮与该 Flow 当前路径一致；跨对象跳转不丢失上下文。**并在一次真实运行（40 业务）中核对：所有 Flow 的成员数之和 = `/services` 全量业务数。**

---

## 7. P3 任务

| ID | 任务 | 状态 | 依赖 | 规模 |
|---|---|---|---|---|
| E-01 | 静态路径 QoS：D=Σd、J=√Σj²、B=min b、L=1−∏(1−p)、E≈Σε + 容差；输出"通过/不通过/瓶颈项" | ✅ | D-02、B-02 | M |
| E-02 | 实测 QoS 诊断：6 字段逐项 + `qosMeet`；`errPct`（0–100）与 `ber`（0–1）换算与容差**分别标注** | ✅ | B-03 | S |
| E-03 | 链路负载聚合（P3b 仅需求侧）：`flow_count`/`service_count`/`demand_bps`/`capacity_bps`/`demand_utilization`；`measured_bps` 仅作估计并标注 | ✅ | D-04 | M |
| E-04 | 热点识别（结构/流量/性能三层） | ⏸ 延后 | E-03 | M |
| E-05 | 联动诊断：不达标业务 → Flow → 路径链路 → 竞争者/瓶颈项 | ⏸ 延后 | E-01~E-04 | M |
| T-02 | QoS 计算测试：单/多链路、瓶颈带宽、丢包组合、抖动合成、单位与容差、静态过但实测不达标 | ❌ | E-01/E-02 | S |
| T-03 | 热点计算测试：多低带宽 flow、少数高带宽 flow、容量变化、link down、超载、中心性高但流量低 | ❌ | E-03/E-04 | S |
| T-04 | 数据一致性测试：分页、单详情失败、游标续读、实例切换、超时、快照部分成功 | ❌ | B-05/B-07 | S |

**P3 验收**：同一业务能同时看到"静态可行/不可行"与"实测达标/不达标"，且两者结论不一致时明确标注；热点的 `demand_utilization` 可用原始字段复算；`measured_bps` 带"估计"标记。**并在一次真实运行中，用 `GET /services/{id}` 的 `actual` 与页面逐项数值抽查 3 条业务，确认无单位/容差错位。**

---

## 8. 依赖与顺序

```
P0:  A-04（契约） ──> A-07（安全回归）
              └──────> P1: B-07（分页）──> B-05（一致性）──> B-06（健康）
P1:  C-02（劣化标记）
P2:  D-01（Flow）──> D-02（Path）──> D-04（视图）──> D-05（跳转）
P3:  E-02（实测展示，可提前独立做）
      D-02 ──> E-01（静态 QoS）
      D-04 ──> E-03（需求侧负载）──> [P3b 后续：E-04 热点 → E-05 联动]
C-03：业务数/达标率/未达标数可先用 B-05/B-06 完成；热点 Top N 等 E-04（延后）。
```

**可并行**：E-02 不依赖 Flow；E-01 与 P2 的 D-04 可并行；T-02/T-04 可随对应模块同步写。
**不建议**：先做页面再补契约/分页（会返工，且"数量对得上"这条验收会失败）。

---

## 9. 风险与运行期待核对

| 风险 | 现状 | 处置 |
|---|---|---|
| 场景存在重复反向 flow | 代码按字典首个匹配 | 运行期 `list_flows` 核对一次 |
| 链路/业务 >500 | 分页逻辑已实现并单测覆盖 | 运行期以 `/topology` 对账确认 |
| 响应是否真带 `qosMeet` | 文档未列、代码会带 | 抓一次 `GET /services/{id}` 确认 |
| 反向下发后 `segments` 顺序 | 随最近一次下发方向 | D-02 不假设顺序 |
| 上游 5s 缓存造成滞后 | 请求侧不可测 | 文档注明业务列表可能滞后 ≤5s；用 `data_age_s` 反映本地采集时间 |
| 静态/实测误码两套口径 | 容差与单位不同 | E-01/E-02 分别标注，不合并判定 |
| `measured_bps` 被误读为链路利用率 | 事实已确认 ≠ 吞吐 | E-03 固定"估计"措辞 |

---

## 10. 规模说明

S ≈ 半天内；M ≈ 半天到一天；L ≈ 一天以上。**仅用于排序，不可用于排期**——没有历史速度基线，之前给的"4–6 天"是拍脑袋，已废弃。

---

## 11. 验证记录（2026-11-24，服务器环境）

- 场景：`sce20261010-conf02/sce01`，实例 `20261124-152724`，由官方 `/ui/start`（period=30）拉起。
- 快照：`health=live`，**40 业务 / 17 Flow**，成员合计 40；分页 `links=31/31`、`services=40/40`，与 `/topology` 对账一致。
- 实测 QoS：`qosMeet` 17 达标 / 18 不达标 / 5 未知；静态校验 40 条全部可行（0 不可行）。
- 链路负载（需求侧）：31 条链路；Top 需求/容量：L00013 2.57、L00017 2.51、L00005 2.31（需求带宽超过容量，但每条业务路径静态均可行）。
- 路径解析：抽查 5 个 Flow 全部 `continuous=true`、`direction=forward`。
- 复跑：`pytest backend/tests`（含自动服务器联调）49 项通过；与主项目 `src/math_modeling` 的静态 QoS 对拍 4 例通过（`tests/integration/test_workbench_qos_crosscheck.py`）。

### 11.1 期 1 后端批次（2026-11-24，本地）

对齐 `B03_Network_Workbench_UI_可行性分析.md` §7「期 1」的后端部分，新增：

- **run-info 采集**：`SimulatorClient.get_run_info()`（控制面、只认 ctrl 令牌，open 通道直接 1006 不发请求）；`_load_sim_status()` 映射为 `Snapshot.sim`，失败只记 `sim.error`，不算核心资源失败；实例/场景以 run-info 为权威，拿不到才退事件 payload。`WORKBENCH_RUNINFO` 可关（默认开）。
- **风险接线**：`build_link_risks` / `build_risk_summary` / `build_overall_status` 接入快照；R3 基线取**上一次成功采集**的链路参数（在写缓存之前取）。同时修掉 `risk.py` 里对 pydantic 模型调用 `.get()` 的隐患。
- **契约**：`Snapshot` 增加 `sim`/`riskLinks`/`riskSummary`/`overallStatus`，`snapshot_version=2`；TS 契约（`frontend/src/types.ts`）同步。
- **测试**：新增 `test_risk.py`（规则 A/B 纯函数）+ `test_snapshot_risk.py`（快照接线、R3 跨快照基线、run-info 失败降级、离线）；`test_simulator_client.py` 补 run-info 通道用例。后端 `pytest backend/tests` 80 passed / 1 skipped（collect 81；服务器联调用例不可达自动 skip）。
- **本地冒烟**：`WORKBENCH_OFFLINE=1` 读 `sce20261012-conf01/sce10`，`health=offline`、`sim.status=unknown(error=offline)`、`riskSummary.unknown=true(total=null)`、`overallStatus=unknown`，无伪造值。

### 11.2 期 1 前端批次（2026-11-24，本地）

按 `B03_Network_Workbench_UI_设计说明.md` + 可行性分析 §7「期 1」改版，原 622 行单文件拆为组件：

- **外壳**：`AppShell`（`App.tsx`）+ `Sidebar`（8 个入口，未开放项置灰并标「未开放」）+ `TopBar`（运行态/实例/场景/脚本进度/已运行/仿真时刻/健康/数据龄/最近更新；部分失败与分页提示走状态条）。
- **首行 KPI**：在线节点 / 活动链路 / 测试业务（分母=已识别分类）/ 风险链路（`riskSummary`，不可信显示「—」）/ 整体状态（规则 B + 触发理由）。
- **主区域**：拓扑（节点形状分类型、风险红色虚线、选中路径蓝色加粗、点选下钻、类型过滤、只看风险、缩放/平移/复位、缺坐标标注「布局估算」）+ 右侧诊断栏（分分类达标率、需求侧热点 Top 5、风险链路列表）。
- **第二行**：关键业务表（不达标优先、Flow 列可下钻、全部/不达标/未知筛选）、链路负载排行（需求/容量，超订标红并注明估算）、最近事件（仅 `/events` 实际事件，payload 放 tooltip）。
- **抽屉**：Service / Flow / Link / Node 四类详情共用右侧抽屉；静态 QoS 与实测并列且互相矛盾时显式标注（静态可行但实测不达标 / 反之）。
- **数据检查**：默认折叠，元信息（快照时间、数据龄、陈旧资源、分页对账、svc-meta、事件游标、采集错误）+ 展开时才渲染的原始 JSON（可复制）。
- **写操作**：改路径面板移入折叠区，保留 flow 级影响提示与二次确认；`WORKBENCH_ALLOW_REPATH=0` 时后端 403 原样展示。
- **只读回归（A-07 收口）**：新增 `tests/test_readonly_surface.py`（前端只有一处 POST 且必须在 `api.ts`；禁止 `/simulation/start` 等；后端写调用仅 `set_service_path`；令牌名不进前端；repath 开关 403）。
- **验证**：`pnpm build` 通过（JS 191.5 kB / gzip 61.5 kB，CSS 15.9 kB）；离线起后端同源托管 `GET /` 200、`/api/snapshot` 字段与 `sim/risk/overall` 正常；后端 collect 86，85 passed / 1 skipped。
- **未做（留给期 2）**：QoS 趋势（需后端 1s 采样环形缓冲）、热点综合排序 E-04、计划/实际事件分轨、超大拓扑降采样、路径对比与历史回放。

### 11.3 期 2 批次：Flow 分析页 + 候选路径静态可行性（2026-11-24，本地）

**后端**
- 新增 `analysis/candidates.py`：`build_flow_candidates()` 纯函数。候选只取离线 `service-paths.json`（公开 API 不提供候选生成），**用当前 `/links` 参数重算**静态 QoS，不采用文件里的 `metrics`（那是场景生成期的计划值）。
- 同一 Flow 的候选按链路集合去重；一条候选对**每个成员业务**分别做静态校验（成员需求可能不同），汇总 `ok/fail/unknown`；链路不全时不做部分合成，`staticQoS=null` 且全部计 unknown。
- `Collector.latest()` 缓存最近一次构建的快照，`GET /api/flow-candidates?flowKey=` 直接复用，**不触发新一轮上游采集**；无快照 503、Flow 不存在 404。
- 单测 `tests/test_flow_candidates.py` 9 项：去重、静态合成、成员校验分歧、当前路径标记与排序、缺链路、缺参数、无候选两种提示、候选编号稳定。

**前端（业务分析 · Flow 视图）**
- 左列表：搜索（flowKey / 节点 / 业务 ID）+ 四种筛选（全部 / 有不达标成员 / 静态有不可行 / 路径不连续）+ 排序（不达标数 → 静态不可行数 → 成员数）。
- 右侧详情：基本信息（src/dst IP、pathId、连续性、静态汇总、分类构成）→ 当前路径链路表（五项参数 + 状态 + 需求/容量 + 风险码）→ 成员业务表（需求 vs 实测，点击开抽屉）→ 链路上的其他 Flow（可跳转）→ 候选路径卡片（静态 D/J/B/L/E、成员可行性计数、逐成员冲突明细、当前路径标记、刷新按钮）。
- 候选值标注「按最近一次快照的链路参数重算」，并提供「刷新」重取，避免参数变化后数值悄悄过期。

**验证**：后端 collect 95（94 passed / 1 skipped）；`pnpm build` 通过（JS 204.8 kB / gzip 64.2 kB）；离线起后端用真实场景跑通 `GET /api/flow-candidates`：Flow `10.1.1.100|10.1.1.119` 返回 3 条候选（5/6/24 段，静态时延 24.1/21.5/25.7 ms，成员校验全部可行），未知 Flow 返回 404。离线模式下业务没有 `path`，因此三条候选都不标「当前路径」——这是如实结果，不是缺陷。

**未做**：趋势缓冲、热点排序 E-04、事件差分、计划/实际事件分轨、agent 动作追踪（按期 2 原计划顺延）。
