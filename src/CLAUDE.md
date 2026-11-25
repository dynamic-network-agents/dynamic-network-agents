# CLAUDE.md — src/（资源控制智能体源码）

本文件约束在 `src/` 下写代码时的模块边界、依赖方向与数据口径。它是根 `CLAUDE.md` 的**细化**，不是重复；根文件仍是权威来源（工作准则、编码规则、令牌安全、赛题要点以根为准）。

## 模块地图（自底向上，禁止反向依赖）

| 目录 | 职责 | 关键文件 | 允许依赖 |
|---|---|---|---|
| `util/` | 配置加载 + 令牌读取，**无 IO 之外的业务逻辑** | `config.py`（`load_settings` / `load_open_token`） | 仅 stdlib / 第三方（yaml、json），不依赖任何 src 模块 |
| `math_modeling/` | 纯数据模型 + QoS 计算，**无 IO、无 NetworkX 图依赖** | `models.py`（数据模型）、`flow.py`（flow 分组/需求聚合）、`path_qos.py`（静态 QoS 合成）、`qos_checker.py`（容差判定）、`link_quality.py`（代价归一化）、`measured_qos.py`（实测达标率） | 仅自身模块间（`models` ← `path_qos` ← `qos_checker` / `link_quality`；`models` ← `flow`） |
| `algorithms/` | NetworkX 构图 + K-最短 + 优化选路 | `graph.py`（`build_graph` / `validate_path`）、`k_shortest_paths.py`（Yen）、`optimize.py`（`optimize_flow`） | `math_modeling` + `networkx` |
| `api/` | 仿真 HTTP client + 路径下发 | `client.py`（`SimulatorClient`）、`executor.py`（`PathExecutor`） | `client.py` 仅 `requests`；`executor.py` 依赖 `algorithms.graph`（校验用） |
| `baseline/` | 传统路径：确定性事件驱动重路由闭环 + 入口（无 Agent/LLM） | `reroute_loop.py`（`Orchestrator.step/run`）、`main.py`（入口） | `api` + `algorithms` + `math_modeling` + `util` |
| `agents/` | **预留**：未来 Agent 模块（运维/资源控制/LLM 旁路），当前仅有 `__init__.py` | 尚无 | 未来复用 `api` / `algorithms` / `math_modeling` / `util` |

**硬约束（违反即架构异味）**：
- `math_modeling` 不得 import `algorithms` / `api` / `baseline` / `agents` / `util`（必须保持纯、无 IO、可独立单测）。
- `algorithms` 不得 import `api` / `baseline` / `agents`。
- `baseline` 是当前唯一入口层；`agents` 为预留目录，引入前不得被任何模块 import。
- `util` 是唯一直接读 `simulator/conf/gateway.json` 令牌与 `configs/*.yaml` 的模块；其他层拿配置/令牌一律经由 `util` 或参数注入，不得自行拼路径读文件。

## 核心数据模型与口径（非显然，已在代码落地）

### flow 是优化单位，不是 service
- `Service.flow_key`（`models.py`）= `(src_node_id, dst_node_id)` 元组。
- `group_services_by_flow`（`flow.py`）按 flow_key 分组；同一对源/目的 UAV 的所有业务（含 background）共用一条路径。
- `flow_requirement`（`flow.py`）取组内业务需求**交集**：时延/抖动/丢包/误码取 `min`（最严），带宽取 `max`（最大需求）。无任何带 requirement 业务时返回 `None`（该 flow 不参与优化）。

### 两套 QoS 必须分开，代码已分文件
- **静态（提交校验口径）**：`path_qos.py` 的 `compose_from_params` / `compose_qos`，公式严格对齐仿真器 `_compose_qos`：
  - `D = Σ delay_ms`（累加）
  - `J = sqrt(Σ jitter_ms²)`（均方根）
  - `B = min(bandwidth_bps)`（瓶颈链路）
  - `L = 1 - Π(1 - packet_loss_rate)`（乘积）
  - `E = Σ ber`（小误码率近似累加）
- **实测（逐秒统计）**：`models.py` 的 `Actual`（`avg_delay_ms` / `jitter_ms` / `eff_bw_bps` / `err_pct` / `packet_loss_rate` / `qos_meet`），综合达标只认 `actual.qos_meet` 布尔。

### 容差（`qos_checker.py` `Tolerances`，硬编码，勿改）
- 时延 `+1.0`、抖动 `+1e-9`、丢包 `+1e-9`、误码 `+1e-12`、带宽**无容差**。`check_qos` 返回 `QoSResult(feasible, violations, margin)`，`margin` 语义：时延/抖动/丢包/误码为 `req - 实际`（正=有余量），带宽为 `实际 - req`。

### 单位差异（易踩坑）
- `Actual.err_pct` 是**百分数（0~100）**，`Requirement.ber` 是**无量纲误码率**，二者不可直接比较（见 `models.py` 字段注释）。
- 链路代价（`link_quality.py`）仅用于可行路径之间**排序**，不参与 QoS 判定；归一化基准是 `simulator/conf/linkTypes.json` 的类型取值区间（权威源），越界 clamp 到 `[0,1]`。

### 构图规则（`algorithms/graph.py` `build_graph`）
- 只收 `status=up` 链路 + `status=online` 节点；并行链路用 `nx.MultiGraph`（两点间可有多条 linkId 不同的边）。
- **按 nodeId 显式剔除 `EXT001`**（合成外部引接点，非业务端点，`packetsFwd` 恒 0），避免 1Gbps 光纤被误当业务链路。
- 边属性携带 5 项链路参数 + `delay` 权重（K-最短路径用）。
- **关键**：构图必须用 `get_links()` 的链路列表（带 params），不能用 `get_topology()["links"]`（不带 params，参数会全为 0）。

## 热路径：确定性算法 + LLM 冷路径

- 重路由热路径（`baseline/reroute_loop.py` 的 `Orchestrator.step` → `algorithms.flow_planner.plan`）用确定性算法：K-最短路径 → `compose_qos` 静态合成 → `check_qos` 硬过滤 → 方向容量贪心 + 局部搜索。LLM 只做解释/优先级增强，**不直接生成链路**。
- **闭环是 epoch 状态机**（`reroute_loop.py`，口径见 `docs/agents/传统基线选路方案.md` §5.6–§5.10）：
  - 一次 epoch = 冻结快照 + 一次规划 + 一个下发批 + 静置校验；**批内不重算**；
  - **规划器是纯函数**（输出只看 flows/graph/config，不看已装路径）；下发是增量：拿 `plan` 与
    `installed` 做差集，且只有「修复失效路径」或「加权达标数增益 ≥ Δmin」才下发；
  - 只认可行动事件（`link_state_changed`/`node_state_changed`/业务非 running），**必须过滤自己下发产生的 `service_state_changed(pathChanged=true, running)`**，否则自激成死循环；
  - 收敛判据：`plan - installed = ∅`（可证明）+ 可达集上预测=实测连续 H 窗；**F1/F2 不入判据**（物理不可达，否则永不收敛）。
- 规划器选项（`PlanConfig`）：`rho`（摆放裕度，默认 0.2）、`meet_util`（预测达标阈值，默认 1.0）、
  `excluded_paths`（实测违约路径惩罚集）。注意 `rho` 与 `meet_util`
  是两个不同阈值，勿混用。
- 闭环常量在 `configs/app.yaml`（`reroute_min_gain` / `settle_sec` / `verify_windows` /
  `corrective_rounds` / `trigger_settle_sec` / `heartbeat_sec` / `min_switch_interval_sec` /
  `batch_pace_sec` / `max_batches_per_run`），默认值为建议值，待实验标定。
- `optimize_flow`（`algorithms/optimize.py`）是早期单 flow 选路，**已不在闭环里**，仅保留做离线对比（T3.2）。

## 待核对事项（写代码前勿自行拍板，需对照仿真器/接口实测）

1. **flow 键控口径（已定 A3：改无序）**：代码原 `flow_key = (src_node_id, dst_node_id)` 是**有序**的，而仿真器 `_flow_for` 按**无序**端点对匹配。**决定改为 `tuple(sorted(...))`**，与仿真器对齐；改动见 `docs/task_split/flow_planner_task.md` T0.1。
2. **`category` 无字段（已定 A2：只保 test）**：公开 API 无 `category`。**决定只保 test**：主路径用 `ctrlToken` 调内部 `/api/ctrl/v1/svc-meta` 取 `category`；拿不到 `ctrlToken` 时用 `serviceId` 前缀 `TSV*` 兜底或退化为统一保护所有 `running`。不再以「MVP 统一保护所有 running」为默认策略。
3. 其余「待核对」口径以根 `CLAUDE.md`「关键事实」为准（`node_move` 失效、`simulation/start` 未实现、`extraLinkIds` 真义等）。

## 测试布局（与根一致）

- 单元测试跟随被测模块，在 `src/*/tests/` 下（如 `src/math_modeling/tests/test_path_qos.py`、`src/algorithms/tests/test_graph.py`）。
- `math_modeling` 与 `algorithms` 的纯函数（`compose_from_params`、`check_qos`、`group_services_by_flow`、`build_graph`）应优先用固定样例做纯单测，不依赖仿真器在线。
- 集成/e2e 在外层 `tests/integration/`、`tests/e2e/`，仿真器离线时自动 skip。

## 编码规则

- 先给方案（目标/涉及文件/关键设计/验收标准），确认后再写代码；SOLID + 组合优于继承 + 迪米特；令牌不入代码、不打印、不提交（详见根 `CLAUDE.md`）。
- 版本记录：较大功能更新后在 `versions/` 新增一条 `日期_task_subtask.md`。
