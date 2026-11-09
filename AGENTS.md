# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

> 本文件与根目录 `CLAUDE.md` 描述同一套仓库约定：Codex 读 `AGENTS.md`，Claude Code 读
> `CLAUDE.md`。两者应保持一致，改动时同步更新。

## 项目概述

赛题 **B03「资源受限环境下通信网络资源管控」**：在仿真环境中设计多智能体协同系统，实现通信网络状态感知、故障识别、链路优选、多维资源动态调度。

核心理念：**数据面分布式自组网 + 管控面多智能体分层协调，控制面与数据面分离**；协调器（Coordinator）统一编排与冲突仲裁，支持中心降级自治。

## 工作准则

- **模块边界**：代码改动严格限定在任务所属模块内。执行 frontend 任务只允许改 `frontend/`；执行 backend/simulator/agent-platform/algorithms 任务同样不得改 `frontend/`。跨模块的契约、CI、数据模型等共享变更，先说明并征得确认后再改。
- **不得凭空捏造**：以事实为依据（协议标准、成熟方案、权威白皮书），引用协议/标准给出编号（如 RFC 3626、MIL-STD-6016、STANAG 5522）；不确定的接口、参数、官方口径标注「待与官方确认」，不臆造数值、字段或结论。
- **任务流程**：每个 coding 任务先拆子任务、列出任务描述，经用户确认后再写代码；遇不确定点或多个可选方案先提出让用户选，不自行拍板。

## 设计原则（coding 规则）

遵循 SOLID + 组合优于继承 + 迪米特法则（单一职责、开闭、里氏替换、接口隔离、依赖倒置、合成复用、迪米特）。各模块落地细则见子模块 `AGENTS.md`（如 `frontend/AGENTS.md`）。

## 目录结构

| 路径 | 角色 |
|---|---|
| `frontend/` | 前端工作台（React 18 + TS + Vite，已有代码，见 `frontend/README.md`） |
| `backend/` | 主业务后端 / API 集成层（FastAPI） |
| `simulator/` | 动态通信网络仿真器（SimPy） |
| `agent-platform/` | LLM 多智能体平台（Ollama/Qwen） |
| `algorithms/` | 确定性算法库（进程内库：NetworkX + OR-Tools） |
| `contracts/` | 模块间通信契约（由接口规范导出） |
| `docs/` | 设计文档主源（赛题/仿真/frontend/overview） |

- 当前仅 `frontend/`、`docs/` 有内容；其余模块为空占位、随任务逐步建立（拆分方案见 `docs/overview/动态通信网络多智能体项目目录拆分方案.md`）。
- 数据模型与接口以 `docs/frontend/前后端数据模型与接口规范_v1.0.md` 为**唯一事实源**；设计稿只做页面/交互，不重复定义字段与接口。
- 前端文档 v1.0 为当前版（扁平存放）；仿真/需求文档 v2.1 为当前版、v1.0 为归档版。

## 赛题要点

- 4 个子任务：① 动态场景建模 ② 多智能体协同体系设计 ③ 面向通信管控任务的智能体设计 ④ 仿真实验验证。
- 至少两类智能体：运维智能体（态势采集/拓扑感知/链路质量/异常检测/故障诊断/自愈建议）、资源控制智能体（资源调度/路由调整/带宽分配/QoS 保障）。
- 约束：小参数量 + 低比特量化大模型；Python3.12+ / Java21+ / JS；Ubuntu22.04 x64。
- 评分权重（排优先级）：动态场景建模 18、多智能体体系设计 36、实验验证 24、结果分析 16、文档质量 6。

## 技术栈

- 前端：React 18 + TypeScript + Vite + Ant Design + AntV G6 + ECharts + Zustand + Axios + WebSocket + MSW
- backend：Python 3.12 + FastAPI（Agent 生命周期、A2A、任务调度、RAG、策略校验）
- simulator：Python 3.12 + SimPy
- agent-platform：Qwen3-4B/8B（Ollama），向量检索 BGE-M3 + FAISS
- algorithms：Python 3.12 + NetworkX + OR-Tools（进程内库）
- 存储：SQLite、Redis（按需）

## 运行环境

目标 Ubuntu 22.04.5 Desktop x64。依赖按需安装、不提前预装，必要时用 Docker 封装。

## 文档处理约定

- `.md` 为主编辑源，同名 `.html` 为渲染产物；改内容改 `.md`，不回填 `.html`。
- docx→文本 / PDF 提取用 `/usr/bin/textutil`；Markdown→docx 先写 HTML 再 `textutil -convert docx`。
