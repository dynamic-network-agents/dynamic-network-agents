# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## 项目概述

这是一个**竞赛设计文档工作区（当前尚无代码）**，对应赛题 **B03「资源受限环境下通信网络资源管控」**。目标是在仿真环境中设计并实现一个多智能体协同系统，实现通信网络状态感知、故障识别、链路优选、多维资源动态调度，提升无人平台业务协同的通信保障能力。

贯穿所有文档的核心设计理念：

- 网络从"人工配置、中心调度"转向"分布式、自感知、自决策、自协同"。
- **数据面分布式自组网 + 管控面多智能体分层协调，控制面与数据面分离**；协调器（Coordinator）做统一编排与冲突仲裁，但支持中心降级自治。

## 工作准则

- 关于本项目的搜索与回答内容，**不得凭空捏造**，必须以事实为依据（如协议标准、成熟设计方案、权威白皮书）。引用协议/标准时给出编号（如 RFC 3626、MIL-STD-6016、STANAG 5522）；不确定的接口、参数或官方口径需明确标注"待与官方确认"，不臆造数值、字段或结论。

## 目录结构与关键文件

工作区按文档主题分目录存放，**当前尚无代码**（纯设计文档）：

| 路径 | 角色 |
|------|------|
| `docs/description/B03资源受限环境下通信网络资源管控赛题详情描述文档.pdf` | 赛题 PDF：任务目标、4 个子任务、输入输出、评分标准 |
| `docs/unmanned platform req/v2.0/` | **当前版本**：`无人平台动态场景需求文档_v2.0.md`、`无人平台组网设计方案_v2.0.md`、`无人平台动态通信网络仿真方案_v2.0.html` |
| `docs/unmanned platform req/v1.0/` | 归档版：需求文档/组网设计的 `.md` 主源与同名 `.html` 排版源，以及 `动态通信场景建模组网方案`、`分布式路由与组网过程讲解` |
| `docs/web search/动态通信网络资源管控多智能体系统_项目整体架构与开发设计方案.docx` | 团队的项目架构设计方案（技术栈 + 分阶段计划），后续开发的蓝本 |
| `docs/web search/数字低空网络架构、覆盖及关键技术白皮书.pdf` | 低空网络参考白皮书（86 页） |
| `docs/web search/中 华 人 民 共 和 国 民 用 航 空 行 业 标 准.pdf` | 《无人机云系统数据规范》民航行业标准草稿（74 页） |

- 无人平台需求/组网文档 **v2.0 为当前版、v1.0 为归档版**；改动优先落到 v2.0。
- `.md` 为主编辑源，同名 `.html` 为排版/渲染产物（部分文件只有其一，如 `仿真方案_v2.0` 目前仅 `.html`）。
- 根目录 `mermaid.min.js` 是本地 Mermaid 渲染库，供各 `.html` 排版源引用。
- 赛题 PDF 无现成纯文本提取文件；需要原文时用 `textutil` 提取（见「文档处理约定」）。

## 赛题要点

- **4 个子任务**：① 动态通信场景建模 ② 多智能体协同体系设计 ③ 面向通信管控任务的智能体设计 ④ 仿真实验验证。
- **至少两类必需智能体**：
  - 运维智能体：全网态势采集、拓扑感知、链路质量评估、异常检测、故障诊断、自愈建议生成。
  - 资源控制智能体：资源调度、路由动态调整、带宽分配、业务 QoS 保障。
- **约束**：小参数量 + 低比特量化大模型；语言 Python3.12+ / Java21+ / JS；运行环境 Ubuntu22.04 x64。
- **交付**：初赛交「设计方案 + 实验结果分析报告」；复赛交「源代码 + 部署包」。
- **链路数据模型**：`linkId` / `linkType` / `srcNodeId` / `dstNodeId` / `status` / `params{delayMs, jitterMs, bandwidthBps, ber, packetLossRate}` / `time` / `tsUs`。
- **评分权重**（用于排优先级）：动态场景建模 18、多智能体体系设计 36（架构 12 + 协同架构 12 + 成员智能体 12）、实验验证 24、实验结果分析 16、文档质量 6。

## 方案技术栈（来自设计文档）

- 前端：Vue3 + TypeScript + Element Plus + ECharts + Cytoscape.js
- 后端编排：Java21 + Spring Boot 3.x + Spring AI 2.x（Agent 生命周期、A2A、任务调度、RAG、策略校验）
- 算法服务：Python 3.12 + FastAPI + NetworkX + OR-Tools（拓扑分析、故障诊断、动态路由、带宽分配）
- 模型：Qwen3-4B/8B（Ollama 部署），向量检索 BGE-M3 + pgvector
- 存储：PostgreSQL + pgvector（业务数据/向量）、Redis（实时状态缓存）
- 仿真：Python SimPy + NetworkX（或官方仿真器适配层）

## 文档处理约定

- 本机**无 pandoc**；docx → 纯文本用 `/usr/bin/textutil -convert txt -stdout 文件.docx`。
- Markdown → docx：先手写 HTML（保留表格/代码块），再 `textutil -convert docx -output 输出.docx 输入.html`。
- PDF 提取文本优先用 `textutil` 或 `mdls` 查看元数据（`pypdf` 未安装）。
