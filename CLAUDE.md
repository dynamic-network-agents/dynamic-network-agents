# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

赛题 **B03「资源受限环境下通信网络资源管控」**（中国电科"网信杯"，54所）。目标是构建一个**资源控制智能体**，运行在官方无人机群通信网络仿真器之上，在动态扰动下保障业务 QoS。

核心理念：**唯一可控杠杆是"重路由"** —— 智能体通过公开 HTTP API 观测网络，唯一的写动作是 `POST /services/{serviceId}/path` 重分配业务路径。没有带宽分配、队列调度、准入控制、跳频等接口，一切决策都归约为"为业务选路径"。

## 赛题要点

- 4 个子任务：① 动态场景建模 ② 多智能体协同体系设计 ③ 面向通信管控任务的智能体设计 ④ 仿真实验验证。
- 至少两类智能体：运维智能体（态势采集/拓扑感知/链路质量评估/异常检测/故障诊断/自愈建议）、资源控制智能体（资源调度/路由调整/带宽分配/QoS 保障）。
- 约束：小参数量 + 低比特量化大模型；Python 3.12+ / Java 21+ / JS；Ubuntu 22.04.5 x64。
- 初赛评分：动态场景建模 18、多智能体体系设计 36、实验验证 24、结果分析 16、文档质量 6。初赛 12/15 前提交设计方案 + 实验结果分析报告。

## 工作准则

- **不得修改仿真器发布件**：`simulator/` 下的代码、`gen_scripts/`、`conf/`、`data/` 均为官方发布件，只能读取、不能改代码（仅有的例外见「关键事实」）。智能体改动只落在 `src/`、`configs/`、`tests/`、`experiments/` 目录。
- **查仿真器实现先看 `sim_src/`**：这是从 `simulator/images/*.tar` 解出的只读源码副本（netsim 为 base85+zlib 解码件，servicesim 为明文），只供检索/核对，不参与构建、不被 `src/` import、不提交（已 gitignore）。运行行为仍以 `simulator/` 发布件与镜像为准；工作约束见 `sim_src/CLAUDE.md`。
- **令牌/密钥不入代码**：`simulator/conf/gateway.json` 的 `openTokens[]`、`ctrlToken`，以及 `simulator/docker/eval/.env` 的 `LLM_API_KEY`、`LITELLM_MASTER_KEY` 都是真实密钥，禁止写入代码或提交。
- **以官方口径为准**：QoS 判定、接口字段、错误码以权威文档为准；不确定的口径标注「待核对」，不臆造数值/字段/结论。
- **证据纪律（硬性）**：任何结论都必须有**需求文档、官方接口文档或仿真器源码（`sim_src/`）**的直达依据，并给出可核对的位置（文件+行/函数）。**场景数据、抽样观测、经验推断只能当佐证，不能当依据**；不得由"某几个场景里是这样"推出"系统/模型一定是这样"。依据不足时写「待核对」并说明**缺哪份证据**，不要用"通常/一般都是/应该是"填补。
- **场景生成走技能**：用 `.agents/skills/scenario-gen/` 生成场景库，不要手工改场景数据；生成后 `validate_library.py --conf gen_conf<NN>` 必须零违规才算完成。

## 编码规则

- **任务流程（先确认再动手）**：每个 coding 任务先给出方案（目标、涉及文件、关键设计、验收标准），询问是否可行；有需要确认的点先向我提问、征求意见，**等我确认后才开始写代码**，不自行拍板。
- **测试布局**：单元测试跟随被测文件，在对应模块目录下建 `tests/` 子目录（如 `src/common/modeling/tests/`、`src/common/simulator/tests/`）；集成测试与端到端测试统一放外层 `tests/`，分 `tests/integration/`、`tests/e2e/` 两个子目录。
- **设计模式**：遵循 SOLID 原则 + 组合优于继承 + 迪米特法则（单一职责、开闭、里氏替换、接口隔离、依赖倒置、合成复用、迪米特）。
- **版本记录**：每次 coding 之后，若有较大功能更新，在 `versions/` 下新增一条记录，文件名 `日期_task_subtask.md`（如 `1116_miniruntask_T04.md`），内容为「修改日期 + 修改内容」的简洁描述，不罗列细节。

## 设计原则（决策口径）

- **确定性热路径 + LLM 冷路径**：重路由热路径用确定性算法（NetworkX K-最短路径 + 官方静态 QoS 过滤），LLM 只做解释/优先级增强，不直接生成链路。LLM 对评分是**必需**的（「智能体行为质量」「模型选型」两个指标都要求接入），但对控制不是。
- **双重 QoS 必须同时建模**：静态路径 QoS（提交时校验，拒绝则 1004）≠ 实测 QoS（逐秒评分 `actual.qosMeet`）。静态通过不代表实测达标。
- **flow 级而非 service 级**：路径按源/目的 IP 键控，同一对 UAV 之间的所有业务（含 background）共用一条路径，改一个会影响同对端点其他业务。优化单位是 flow（源-目 UAV 对）。

## 目录结构

| 路径 | 角色 |
|---|---|
| `simulator/` | 官方仿真环境（发布件，勿改）。`conf/`（`gateway.json` 令牌、`linkTypes.json` 链路参数**权威源**、`servicesim.json`）、`data/`（场景生成参数 + 场景库）、`gen_scripts/`（生成器）、`docker/`（compose） |
| `sim_src/` | 从官方镜像解出的只读源码副本（`netsim/` 解码件 + `servicesim/` 明文），供检索与口径核对；不参与构建、不 import、不提交。来源/体量/刷新见 `sim_src/README.md`，检索约束见 `sim_src/CLAUDE.md` |
| `docs/` | 分析与设计文档主源（见「文档索引」） |
| `mac-docker-trial/` | 本机跑 amd64 镜像的 Compose + `start-netsim.sh` |
| `.agents/skills/scenario-gen/` | 场景库生成技能（SKILL.md + params 参考 + 校验脚本） |
| `src/` | 源码：`common/`（共享底座：`simulator` 仿真 API 适配、`perception` 感知层、`modeling` 数据模型 + QoS 计算、`algorithms` 构图 + 选路、`control` 闭环控制、`observability` 观测留痕与指标、`config` 配置加载、`util` 工具）、`baseline/`（传统路径入口）、`agents/`（智能体入口：`ops` 运维智能体、`resource` 资源控制智能体、`a2a` 协同协议/调度/仲裁、`llm` LLM 通道）。模块地图与依赖方向见 `src/CLAUDE.md` |
| `configs/` | 全局配置（`app.yaml` / `simulator.yaml` / `qos.yaml` / `llm.yaml`） |
| `tests/` | 集成测试与端到端测试（`integration/`、`e2e/`）；单元测试在 `src/*/tests/` 下跟随被测模块 |
| `experiments/` | 实验记录 + 问题清单（手工版）：`README.md` 工作流、`index.md` 编号登记、`exp/EXP-*.md`、`iss/ISS-*.md` |
| `work_bench/` | B03 Work Bench 调试控制台（只读观测/诊断工作台）子项目，独立于 `src/`；已实现最小可运行版（观测走 ctrl 令牌，不进 agent 调用统计）。工作约束见该目录 `CLAUDE.md` |
| `docs/work_bench/` | Work Bench 文档（评审企划书、任务拆分、端口令牌与服务器部署口径） |
| `.claude/`、`.vscode/` | 最小化编辑器/权限配置 |

- 无关的兄弟项目 `../react/my-app`（React，有独立 CLAUDE.md）不属于本赛题。


## 技术栈

- 智能体热路径：Python 3.12 + NetworkX（图建模、K-最短路径）
- 接入：HTTP + JSON 公开 API（`http://{IP}:10100/api/open/v1`，头 `X-Open-Token`，也接受 `X-Ctrl-Token`）；LLM 经 eval 代理 `:10110/v1`（OpenAI 兼容）
- 运行：Docker Compose（`netsim` / `servicesim` tx,rx / `eval`）；**主环境为服务器 x64**，本机 Mac 仅备用（Rosetta 跑 linux/amd64 镜像）。

## 运行环境（两套，服务器为主）

**主环境：服务器 `root@121.43.114.121`（主机名 `netsim-dev`，Ubuntu 22.04.5 x86_64，4 vCPU / 7G 内存，已配 SSH 免密）。**
自 2026-11-25 起，**仿真器、agent、baseline、work_bench 一律在服务器上跑**，本机只做编辑与经 SSH 隧道访问（`ssh -L 8000:127.0.0.1:8000 root@121.43.114.121` → `http://127.0.0.1:8000`）。不要在服务器上把 workbench 绑到 0.0.0.0。

**备用环境：本机 Mac**（Apple Silicon，镜像 linux/amd64 靠 Rosetta 转译，慢且控制面易超时）。只用于离线单测和临时调试：`uv run pytest src/ tests/` 实测 71 passed / 7 skipped（仿真器不在线时集成/e2e 自动 skip）。

- 完整启动/停止 runbook：`simulator/README.md`（Linux x64 + 本机 Mac，端口表、就绪信号、日志噪音）、`mac-docker-trial/README.md`（Mac 实际路径：`docker compose -f mac-docker-trial/compose.local.yml ...`，OVS/Rosetta 说明）。

## 关键事实（非显然，已核实）

- **路径是 flow 级不是 service 级**：`_flow_for(src,dst)` 按 src/dst IP 键控，同对 UAV 业务共用一条路径。API 不按 `category` 过滤，`background` 业务也可重路由。
- **公开 API 无 `category` 字段**（自测核实）：test/background 分层只在内部 `/api/ctrl/v1/svc-meta`（需 ctrlToken，公开 token 拿不到）。业务详情仅含 `requirement`/`path`/`actual`（`qosMeet` 布尔）/`priority`/`status`。MVP 统一保护所有 running 业务，暂不区分 test/background。
- **观测调用分两本账**：带 `X-Open-Token` → `llm_gateway_call_stat.log`（`GET /api/ctrl/v1/agent-calls` 读的就是它，即 agent 调用统计）；带 `X-Ctrl-Token` 或不带 → `llm_gateway_front_stat.log`。`/api/open/v1` 的 GET/POST 都接受 ctrl 令牌（`_auth_query`/`_auth`），所以工作台用 ctrl 令牌调公开接口可做到"语义不变、不进 agent 统计"。**唯一例外是改路径**：`path_event_stat.log` 硬编码 `source='agent'`，任何令牌都躲不开，只能靠 `WORKBENCH_ALLOW_REPATH=0` 关闭（详见 `docs/work_bench/B03_Workbench_端口令牌与服务器部署.md`）。
- **`/topology` 的 links 不带 `params`**：链路 5 项 QoS 参数只出现在 `GET /links` 列表；构图必须用 `get_links()` 而非 `get_topology()["links"]`，否则参数全为 0。
- **`node_move` 当前是失效的**：两处缺陷——脚本 `attrs` 用 `fromX/fromY/toX/toY`，而 `_move_start` 读 `from`/`to` 对象（不匹配→零位移）；`conf/linkTypes.json` 缺 `losMeters`（读作 0→"无 LOS，移动被忽略"）。`conf/` 从宿主机 bind-mount，所以修复要改 `simulator/conf/linkTypes.json`。
- **EXT001 不是业务端点**：它是合成的"外部引接点"（1Gbps 光纤连第一个地面节点），满足实验模型，标准业务路径永不穿越它，`packetsFwd` 恒为 0。`gateway.json` 的 `extraLinkIds` 是**并行链路 labKey→linkId 稳定 ID 映射**，不是"排除表"；EXT001 按 nodeId（`EXT001`）剔除。
- **`eval/.env` 有真实密钥与过期路径**：含 `LLM_API_KEY`、`LITELLM_MASTER_KEY`（勿入代码），且 `DEPLOY_*_HOST` 指向 `/Users/cc/freelancer/feature/env-sim/simulator`（不存在），本地跑 eval 前要改成本仓库的 `simulator/`。
- **`conf/`、`data/`、`assets/`、`logs/` bind-mount 进容器**：镜像本身不带 conf；改 `simulator/conf/...` 在容器内生效（需重启）。
- **无害日志噪音**：`sch_htb: quantum of class ... is big`（tc 把 >1Gbps 限到 1000Mbps）、`上报重试 ... Connection refused (8091)`（禁用的 WS 通道）均属预期。
- **`sim_src/` 是解码副本，不是上游源码**：netsim 的 `.py` 由 `base85+zlib` 包装，变量名被重命名（`x001` 等）、注释被剥离；引用行号时注明是解码件行号。带宽 1000Mbps 封顶发生在 `sdncommon._bw_mbit()`（建 Mininet 链路时）；`ctrl.seed_baseline_link_params()` 会用 `net-topo.json` 原始值重新 `apply_link`，`/links` 的返回值又受运行期覆盖，因此不要只凭一处代码断言带宽，以运行期 `/links` 与启动日志为准。
- **两套 QoS 判定必须统一**（公式见 `docs/common/modeling/数学建模方案.md` §4，唯一权威源）：静态 $D=\sum d$、$J=\sqrt{\sum j^2}$、$B=\min b$、$L=1-\prod(1-p)$、$E\approx\sum\varepsilon$；实测用逐秒统计。容差：时延 +1.0、抖动/丢包 +1e-9、误码 +1e-12、带宽无容差。
- **`POST /simulation/start` 当前镜像未实现**（自测返回 1003「未知接口」）；起测试走 UI 的 `POST /sdn-ui/start`（nginx 服务端注入 ctrl 令牌，非公开 token）。
- **Rosetta 下控制面会打挂**（仅影响 Mac 备用环境）：40 业务跑约 11 分钟后单线程 `ctrl.py(:8080)` 全接口超时，属已知转译限制；正式跑/评测一律用服务器 x64。

## 常用命令

- **装依赖**：服务器上项目 venv 已就绪，**不要重装**（无 uv）；本机备用环境用 `uv sync`（uv + Python 3.14，生成 `.venv`）。
- **跑全部测试（服务器）**：`ssh root@121.43.114.121` → `cd /root/dynamic-network-agents && .venv/bin/python -m pytest src/ tests/`。
- **跑全部测试（本机）**：`uv run pytest src/ tests/`（离线单测常跑；`tests/integration`、`tests/e2e` 需 netsim 在线，否则自动 skip）。
- **跑单个测试**：`uv run pytest src/common/modeling/tests/test_qos_checker.py::test_xxx`（服务器上把 `uv run pytest` 换成 `.venv/bin/python -m pytest`）。
- **起 workbench（服务器）**：`cd /root/dynamic-network-agents/work_bench && mkdir -p logs && nohup ./backend/run.sh >> logs/workbench.log 2>&1 &`；本机 `ssh -L 8000:127.0.0.1:8000 root@121.43.114.121`，浏览器开 `http://127.0.0.1:8000`。
- **查仿真状态（服务器）**：`docker ps`；`curl -H "X-Ctrl-Token: $(...gateway.json ctrlToken...)" 127.0.0.1:10100/api/ctrl/v1/run-info`（令牌勿打印）。
- **起仿真器（服务器，已在跑）**：官方 compose（`simulator/docker/netsim`、`servicesim/{tx,rx}`、`eval`），**勿随意 down**；确需重建网络后 tx/rx 要**重启**（不是 `up -d`）。
- **起仿真器（Mac，备用）**：`docker compose -f mac-docker-trial/compose.local.yml up -d netsim` → 等 `[start] 就绪` → `up -d tx rx`；停止 `... down`。
- **生成场景库**：走 `.agents/skills/scenario-gen/` 技能；生成后 `validate_library.py --conf gen_conf<NN>` 零违规。
- **检索仿真器实现**：`rg -n "netem|tbf|corrupt" sim_src/netsim/`、`rg -n "qos_meet|errPct" sim_src/servicesim/`。先看 `sim_src/netsim/openapi.py`（API/QoS/选路）与 `sim_src/netsim/ctrl.py`（tc/OVS/事件）。
- **查令牌**：`python3 -c "import json;print(json.load(open('simulator/conf/gateway.json'))['openTokens'][0])"`（勿打印到日志/提交）。

## 文档索引

**总入口**：`docs/index.md`（文档结构与 `src/` 一一对应，含按角色的阅读路径）。

- 权威接口/使用（发布件）：`docs/competition_desc/仿真软件接口.md`、`docs/competition_desc/仿真环境使用说明.md`。
- **总体框架与边界**：`docs/architecture/总体框架.md`（分层/依赖/两条闭环）、`docs/architecture/模块边界与依赖方向.md`、`docs/architecture/baseline与agents的共享与对比.md`、`docs/architecture/算法边界与停止条件.md`。
- 已核实的决策/实现细节（错误码、事件注入、镜像内代码位置）：`docs/common/simulator/接口清单与语义.md`。
- 数学建模（可实施版，公式对齐仿真器口径，**两套 QoS 唯一权威源**）：`docs/common/modeling/数学建模方案.md`；最小化工程任务清单：`docs/task_split/mini_run_task.md`。
- 算法规格：`docs/common/algorithms/`（拓扑构建与容量记账 / 路径算法与取舍 / flow级联合选路 / 扩展指引）。
- 闭环与感知：`docs/common/control/闭环状态机与收敛判据.md`、`docs/common/perception/感知口径与事件机制.md`。
- 入口侧：`docs/baseline/传统基线选路方案.md`、`docs/agents/智能体设计.md`。
- 拓扑/链路/业务/事件的物理含义（带结论来源分层）：`docs/overview/项目背景.md`。
- 企划书 / 目标架构（感知→图模型→协调器→运维/资源智能体→NetworkX + QoS 过滤→LLM）：`docs/overview/B03通信网络资源管控项目企划书.md`（**立项规划文档，部分章节已被 `docs/architecture/` 承载，见文内现状提示**）。
- 运维 runbook：`simulator/README.md`、`mac-docker-trial/README.md`、`simulator/docker/eval/readme.md`（两个 LLM/模型选型评分要求）。
- **仿真器源码副本**：`sim_src/README.md`（来源、体量、排除项、刷新方式）、`sim_src/CLAUDE.md`（检索口径、核心入口、硬约束）。
- **仿真器会话整理版**：`docs/simulator/仿真器相关.md`（架构/端口/部署、netem+tbf 落地细节、Mac 控制面超时、路径/QoS、光纤瓶颈画像、源码地图）。
- **场景静态可达性分析**：`docs/simulator/sce01_无脚本可达性与最优flow分析.md`（接入段上界推导、各方案达标数、最优 flow 摆法、复现脚本 `scripts/feasible_bound.py`）。
- **Work Bench 调试控制台**：`work_bench/CLAUDE.md`（工作约束与口径）、`work_bench/README.md`（概览/部署）、`docs/work_bench/B03_调试控制台企划书.md`（评审与 V1.1 建议）、`docs/work_bench/B03_DebugConsole_task_split.md`（任务拆分，权威来源）、`docs/work_bench/B03_DebugConsole_mini_run_task.md`（最小可运行版）、`docs/work_bench/B03_DebugConsole_P0-P3任务分析.md`（P0–P3 任务/状态/验收）、`docs/work_bench/B03_Workbench_端口令牌与服务器部署.md`（端口/令牌/记账/SSH 隧道）。
- **研发记录**：`docs/experiments/现阶段方案.md`（手工版方案 + 演进路线）、`docs/experiments/研发记录系统建设企划书.md`（完整工具化设想）、`docs/experiments/实验记录模板.md`、`docs/experiments/问题清单模板.md`；日常操作手册 `experiments/README.md`。
