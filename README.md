# 动态通信网络多智能体系统

赛题 **B03「资源受限环境下通信网络资源管控」** 多智能体协同系统。核心理念：**数据面分布式自组网 + 管控面多智能体分层协调，控制面与数据面分离**。

## 模块

| 目录 | 角色 | 状态 |
|---|---|---|
| `frontend/` | 前端工作台（React 18 + TS + Vite） | 已有代码（FE-001~008） |
| `backend/` | 主业务后端 / API 集成层（FastAPI） | 阶段一起建骨架 |
| `simulator/` | 动态通信网络仿真器（SimPy） | 阶段一起建骨架 |
| `agent-platform/` | LLM 多智能体平台（Ollama/Qwen） | 阶段一起建骨架 |
| `algorithms/` | 确定性算法库（NetworkX + OR-Tools，进程内库） | 阶段一起建骨架 |
| `contracts/` | 模块间通信契约（JSON Schema） | 阶段一起建骨架 |
| `docs/` | 设计文档主源（赛题/仿真/frontend/overview） | 已有 |

数据模型与接口以 `docs/frontend/前后端数据模型与接口规范_v1.0.md` 为**唯一事实源**；模块拆分见 `docs/overview/动态通信网络多智能体项目目录拆分方案.md`。

## Python 侧快速开始（backend / simulator / agent-platform / algorithms）

```bash
uv sync                 # 安装全部成员 + 开发依赖（首次生成 uv.lock）
make test               # 单元测试
make lint               # ruff 静态检查
make typecheck          # mypy 类型检查
make check-contracts    # 契约 Schema 校验
make check              # 以上全部
```

- 依赖管理：uv workspace（根 `pyproject.toml` 的 `[tool.uv.workspace]`）。
- 目标环境：Ubuntu 22.04 + Python 3.12（`.python-version`）。

## 前端快速开始

见 `frontend/README.md`（pnpm）。
