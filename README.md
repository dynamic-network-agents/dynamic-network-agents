# dynamic-network-agents

B03「资源受限环境下通信网络资源管控」多智能体管控系统。

核心理念：唯一可控杠杆是**重路由**——通过公开 HTTP API 观测网络，唯一写动作是 `POST /services/{serviceId}/path`。确定性算法负责正确性（NetworkX 构图 + K 最短路径 + 官方静态 QoS 过滤），LLM 作解释/优先级增强旁路。

## 目录结构

```
configs/         全局配置中心（app/simulator/qos/llm）
docs/            项目设计文档（project/architecture/decisions）
src/
  api/           仿真 API client（鉴权、轮询、path 下发、事件）
  math_modeling/ 数学建模（node/link/service/event + 静态/实测 QoS）
  algorithms/    选路算法（NetworkX 构图 + K 最短路径）
  agents/        智能体层（运维 + 资源控制 + 控制循环 + LLM 旁路）
  util/          公共工具
tests/           测试（含针对真实 simulator 的集成测试）
experiments/     场景库与结果报告
```

## 快速开始

```bash
uv sync                 # 安装依赖
uv run pytest           # 跑测试
uv run python -m src.agents.main   # 启动智能体控制循环
```

## 关键约定

- 令牌从 `simulator/conf/gateway.json` 运行时读取，勿写入代码/提交。
- QoS 判定口径（静态 vs 实测）与仿真器一致，见 `docs/math_modeling/数学建模方案.md`。
- 官方仿真器为发布件，位于同仓库 `simulator/`，禁止修改其代码。

详见根目录 `CLAUDE.md`。
