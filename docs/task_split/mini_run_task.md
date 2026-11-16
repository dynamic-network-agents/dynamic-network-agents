# 最小化工程（七个文件闭环）任务清单

> 目的：把草稿里"七个文件组成的最小工程"拆成可执行、可勾选的任务。依赖顺序与《数学建模方案.md》§8 映射总表对齐。
> 目录结构已对齐企划书：`src/{api,math_modeling,algorithms,agents,util}` + `configs/`（全局配置）+ `tests/` + `experiments/`。
> 时间锚点：2026-12-15 初赛提交。

---

## 阶段 0：工程骨架

- [ ] **T0.1** `pyproject.toml` + `.env.example`（项目根，非 `agent/`）
  - 依赖仅 `networkx`、`requests`、`pyyaml`、`pytest`；Python 3.12+
  - 验收：`uv sync` 成功（生成 `uv.lock`）
- [ ] **T0.2** `configs/*.yaml` + 令牌加载函数
  - `configs/app.yaml`（轮询间隔、超时 6s、K、ρ）、`configs/simulator.yaml`（Base URL、`token_file`）、`configs/qos.yaml`（容差、代价权重 $w_k$）
  - **令牌不写进代码/仓库**，运行时读 `configs/simulator.yaml` 的 `token_file` → `simulator/conf/gateway.json` 的 `openTokens[0]`
  - 验收：脚本能打印 Base URL + 令牌（脱敏）
- [ ] **T0.3** `src/math_modeling/models.py` — 节点/链路/业务/路径/事件 5 类 dataclass
  - 字段对齐 API：链路含 `params` 5 项；业务含 `requirement` 5 项 + `actual`；事件含 `type/payload`
  - 验收：每个 dataclass 有 `from_api_json()` 单测

> 依赖：无。可与 T1 并行。

---

## 阶段 1：接入仿真器

- [ ] **T1.1** `src/api/client.py` — 封装 12 个接口
  - GET topology/nodes/links/services/events/time、POST path、POST start
  - 统一解析 `{code,msg,data}` 包络；统一超时+异常；错误码 1001~1006/2000 分类；频控 1005 退避
  - 验收：`tests/test_simulator_connection.py` 能打印节点数/链路数/业务数/仿真时间
- [ ] **T1.2** 幂等与重试
  - 提交类请求生成唯一 `requestId`；超时重传带 `X-Retry-Of`
  - 验收：同一 requestId 重复提交不重复生效
- [ ] **T1.3** `src/algorithms/graph.py` — 实时状态 + NetworkX 图
  - `nx.MultiGraph`（并行链路）；只收 `status=up` 链路 + `online` 节点；剔除 `EXT001`；维护事件游标 `sinceTsUs`
  - 验收：拉一次拓扑 → 图节点/边数与 API 一致

> 依赖：T0.3。验收前提：`mac-docker-trial` 的 netsim 已 `[start] 就绪`。

---

## 阶段 2：数学内核（纯函数，可离线单测）

- [ ] **T2.1** `src/math_modeling/path_qos.py` — 静态 QoS 合成
  - 精确实现 $D=\sum d$、$J=\sqrt{\sum j^2}$、$B=\min b$、$L=1-\prod(1-p)$、$E\approx\sum\varepsilon$
  - 验收：人工构造路径，五项指标与手算一致
- [ ] **T2.2** `src/math_modeling/qos_checker.py` — 五项硬约束判定
  - **容差原样保留**：时延 +1.0、抖动/丢包 +1e-9、误码 +1e-12、带宽无容差
  - 返回 `{feasible, violations[], margin{}}`
  - 验收：边界用例（恰好相等、差 1e-9）判定正确
- [ ] **T2.3** `src/math_modeling/link_quality.py` — 链路代价 $c_e$
  - 按 `linkTypes.json` 类型区间归一化 + 加权和
  - 验收：同类型链路代价单调性正确
- [ ] **T2.4** flow 分组 + flow 需求 $R_f$
  - `group_services_by_flow()`（`src/math_modeling/models.py`）；$R_f$ 取交集（时延/丢包 `min`、带宽 `max`）
  - 验收：同源-目多业务合并为一个 flow，需求正确

> 依赖：T0.3。验收标准即《数学建模方案》P0 第一条：**五项指标与仿真器 `_compose_qos` 一致、判定与 API 1004 一致**。

---

## 阶段 3：路径优化

- [ ] **T3.1** `src/algorithms/k_shortest_paths.py` — Yen K-最短
  - `nx.shortest_simple_paths`，权重用 `delay`，K 可配
  - 验收：给定图输出 K 条无环 s-t 路径
- [ ] **T3.2** 单 flow 优化（`src/algorithms/optimize.py::optimize_flow`）
  - QoS 硬过滤 → 代价升序 + 裕度降序取第一；无解返回 `None` 并告警（不降级 best-effort）
  - 验收：已知可行/不可行场景输出正确
- [ ] **T3.3** `src/api/executor.py` — 路径下发
  - 校验链路段**连续**（相邻段共享端点）；构造 `segments` + `requestId`；解析 `accepted/rejected`；读取 `effectiveTime`
  - 验收：能对一条真实业务成功下发一条路径并收到回执

> 依赖：T1、T2、T3.1。T3.3 是第一个"真正改网络"的动作，需要 netsim 在线。

---

## 阶段 4：跑通闭环

- [ ] **T4.1** `src/agents/main.py` + `src/agents/orchestrator.py` — 主循环
  - 轮询 `/events`（≤10s）→ 增量更新图 → 找受影响 flow → 重算 → 切换门槛（失效/实测违约/收益>$\Delta_{\min}$）→ 下发 → 复查 `actual.qosMeet`
  - 验收：人工触发一次链路中断，程序自动算出替代路径并下发，实测达标
- [ ] **T4.2** `src/math_modeling/measured_qos.py` — 实测反馈
  - 拉 `services[].actual`，统计 test 保障率
  - 验收：输出每轮 test 业务 `qosMeet` 汇总

> 依赖：全部前置。先不碰多智能体和 LLM。

---

## 建议节奏（对齐 12/15 初赛倒排）

- **11/16–19**：T0 + T1（能连仿真器、能建图）
- **11/20–24**：T2（数学内核离线单测通过，与 T1 并行更省时间）
- **11/25–29**：T3（能自动重路由单条业务）
- **11/30–12/4**：T4（闭环跑通 + 三类扰动验证）
