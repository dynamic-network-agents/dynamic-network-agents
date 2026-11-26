# 文档索引

> 项目文档总入口。文档结构与 `src/` **一一对应**——每个 `src/` 目录都有对应篇章，
> 便于"从功能找代码、从代码找规格"。

---

## 1. 按角色选读路径

| 你是 | 建议读法 |
|---|---|
| **评审/评委** | [总体框架](architecture/总体框架.md) → [baseline 与 agents 的共享与对比](architecture/baseline与agents的共享与对比.md) → [智能体设计](agents/智能体设计.md) → [算法边界与停止条件](architecture/算法边界与停止条件.md) |
| **算法开发者** | [数学建模方案](common/modeling/数学建模方案.md) → [路径算法与取舍](common/algorithms/路径算法与取舍.md) → [flow 级联合选路](common/algorithms/flow级联合选路.md) → [扩展指引](common/algorithms/扩展指引.md) |
| **接入开发者** | [接口清单与语义](common/simulator/接口清单与语义.md) → [感知口径与事件机制](common/perception/感知口径与事件机制.md) |
| **闭环开发者** | [闭环状态机与收敛判据](common/control/闭环状态机与收敛判据.md) → [算法边界与停止条件](architecture/算法边界与停止条件.md) |
| **新人** | [总体框架](architecture/总体框架.md) → [模块边界与依赖方向](architecture/模块边界与依赖方向.md) → 根 `CLAUDE.md` |

---

## 2. 目录结构

```
docs/
├── index.md                    # 本文件：总索引
├── architecture/               # 跨切面（不对应单一模块）
│   ├── 总体框架.md              #   分层、依赖方向、两条闭环、数据流
│   ├── 模块边界与依赖方向.md     #   每层职责、硬约束、扩展接缝
│   ├── baseline与agents对比.md   #   共享/差异、公平对比纪律、归因方法
│   └── 算法边界与停止条件.md      #   能解/不能解、三重停止条件、参数影响
├── common/                     # ← src/common/
│   ├── simulator/接口清单与语义.md
│   ├── modeling/数学建模方案.md
│   ├── perception/感知口径与事件机制.md
│   ├── control/闭环状态机与收敛判据.md
│   └── algorithms/
│       ├── 拓扑构建与容量记账.md
│       ├── 路径算法与取舍.md
│       ├── flow级联合选路.md
│       └── 扩展指引.md
├── baseline/传统基线选路方案.md   # ← src/baseline/
├── agents/智能体设计.md           # ← src/agents/
├── simulator/                   # 仿真环境侧事实
├── competition_desc/            # 官方发布件（赛题/章程/接口/环境说明）
├── overview/                    # 项目背景与企划书
├── experiments/                 # 研发记录（实验/问题清单）
├── task_split/                  # 任务清单
└── work_bench/                  # 调试控制台
```

---

## 3. 完整索引

### 跨切面

| 文档 | 内容 |
|---|---|
| [总体框架](architecture/总体框架.md) | 分层结构、依赖方向、**Baseline 与 Agent 两条闭环流程图**、数据流、赛题要求↔落点、扩展路线 |
| [模块边界与依赖方向](architecture/模块边界与依赖方向.md) | 每层职责与不做什么、硬约束、三条扩展接缝、`src/`↔文档对应表 |
| [baseline 与 agents 的共享与对比](architecture/baseline与agents的共享与对比.md) | 共享什么/差异什么、**并排对比流程图**、公平对比纪律、差异归因流程、复现清单 |
| [算法边界与停止条件](architecture/算法边界与停止条件.md) | 能解/不能解、三重停止条件、三条"必须停"判据、指标解读纪律、参数影响 |

### 共享底座 `src/common/`

| 文档 | 对应代码 | 内容 |
|---|---|---|
| [接口清单与语义](common/simulator/接口清单与语义.md) | `common/simulator/` | 12 个接口、数据模型、错误码、路径下发受理、调用计量口径 |
| [数学建模方案](common/modeling/数学建模方案.md) | `common/modeling/` | 符号表、图模型、链路代价、**两套 QoS 合成与判定（唯一权威源）**、约束模型、代码映射 |
| [感知口径与事件机制](common/perception/感知口径与事件机制.md) | `common/perception/` | 快照字段、事件类型与注入、时间窗口、游标口径、可行动过滤（防自激） |
| [闭环状态机与收敛判据](common/control/闭环状态机与收敛判据.md) | `common/control/` | **epoch 状态机流程图**、合窗、下发闸门、实测校验与惩罚集、配置项、主循环伪代码 |
| [拓扑构建与容量记账](common/algorithms/拓扑构建与容量记账.md) | `common/algorithms/topology/` | 建图规则、EXT001 剔除、params 只能从 `/links` 取、方向容量记账 |
| [路径算法与取舍](common/algorithms/路径算法与取舍.md) | `common/algorithms/path/` | Yen K-最短、方案对比、候选过滤与排序、路径归一化 |
| [flow 级联合选路](common/algorithms/flow级联合选路.md) | `common/algorithms/flow/` | 目标函数、F1/F2/F3、两阶段贪心、局部搜索、评分口径、纯函数契约 |
| [扩展指引](common/algorithms/扩展指引.md) | `common/algorithms/` | 扩展地图、三条接口契约、已知可优化点、验证方法、四个不能踩的坑、检查清单 |

### 入口层

| 文档 | 对应代码 | 内容 |
|---|---|---|
| [传统基线选路方案](baseline/传统基线选路方案.md) | `src/baseline/` | baseline 的定位与边界、关键事实、目标函数、算法链路与取舍、场景预期、验收标准 |
| [智能体设计](agents/智能体设计.md) | `src/agents/` | 双智能体分工、A2A 协议/调度/仲裁、LLM 通道与硬边界、**端到端流程图**、数据契约、待办 |
| [智能体设计文档（旧）](agents/智能体设计文档.md) | — | **迁移指针**（内容已拆入上表各篇，保留仅供旧链接兼容） |

### 仿真环境侧

| 文档 | 内容 |
|---|---|
| [仿真器相关](simulator/仿真器相关.md) | 架构、部署、路径机制、两套 QoS 与基线未达标根因、调试建议（会话整理版） |
| [sce01 无脚本可达性分析](simulator/sce01_无脚本可达性与最优flow分析.md) | 静态可达上界与最优 flow 摆法 |
| [仿真软件接口](competition_desc/仿真软件接口.md) | **官方发布件**（接口权威源） |
| [仿真环境使用说明](competition_desc/仿真环境使用说明.md) | **官方发布件** |
| [赛题详情](competition_desc/B03资源受限环境下通信网络资源管控赛题详情描述文档.md) | **官方发布件** |
| [大赛章程](competition_desc/中国电科人工智能创新大赛章程.md) | **官方发布件** |

### 项目与过程

| 文档 | 内容 |
|---|---|
| [项目背景](overview/项目背景.md) | 仿真环境的物理意义（节点/链路/拓扑/业务/事件/脚本） |
| [项目企划书](overview/B03通信网络资源管控项目企划书.md) | 总体规划（**部分章节已被 architecture/ 承载，见文内提示**） |
| [现阶段方案](experiments/现阶段方案.md) | 研发记录系统的手工版方案 |
| [研发记录系统建设企划书](experiments/研发记录系统建设企划书.md) | 完整工具化设想 |
| [实验记录模板](experiments/实验记录模板.md) / [问题清单模板](experiments/问题清单模板.md) | 记录格式 |
| [任务清单](task_split/) | `flow_planner_task.md`（已完成）、`mini_run_task.md`（最小工程） |
| [Work Bench 文档](work_bench/) | 调试控制台的企划书、任务拆分、部署口径 |

---

## 4. 文档维护约定

- **文档结构与 `src/` 对齐**：新增 `src/` 模块时，同步在对应目录下建篇章；
- **公式单一权威源**：两套 QoS 判定公式只在
  [数学建模方案](common/modeling/数学建模方案.md) §4 定义，其他文档只做指针引用
  （避免口径漂移）；
- **代码位置随重组更新**：`src/` 重组后要 grep 一遍 `src/` 路径引用；
- **官方发布件不改**：`docs/competition_desc/` 与 `simulator/` 是官方内容，只读；
- **过程性文档不动**：`docs/experiments/`、`docs/task_split/`、`docs/work_bench/`
  是过程记录，不随结构调整。

---

## 5. 相关入口

| 位置 | 内容 |
|---|---|
| 根 `CLAUDE.md` | 项目总纲（工作准则、关键事实、命令） |
| `src/CLAUDE.md` | `src/` 模块地图与依赖方向（写代码前必读） |
| `docs/experiments/` | 实验记录与问题清单（日常记录） |
| `experiments/` | 实验编号登记与结果报告 |
