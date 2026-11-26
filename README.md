# dynamic-network-agents

B03「资源受限环境下通信网络资源管控」多智能体管控系统。

核心理念：唯一可控杠杆是**重路由**——通过公开 HTTP API 观测网络，唯一写动作是 `POST /services/{serviceId}/path`。确定性算法负责正确性（NetworkX 构图 + K 最短路径 + 官方静态 QoS 过滤），LLM 作解释/优先级增强旁路。

## 目录结构

```
configs/         全局配置中心（app/simulator/qos/llm）
docs/            项目设计文档（project/architecture/decisions）
src/
  common/        共享底座（baseline 与 agents 共用）
    simulator/   仿真 API 适配（client + path 下发）
    perception/  感知层（冻结快照 + 事件流）
    modeling/    数学建模（node/link/service + 静态/实测 QoS）
    algorithms/  选路算法（topology 构图与容量 / path 路径级 / flow flow 级）
    control/     闭环控制（epoch 状态机 + 下发闸门 + 实测校验）
    observability/ 观测留痕与指标产出（感知/生成/下发耗时）
    config/      配置与令牌加载
    util/        公共工具
  baseline/      传统路径入口（确定性重路由闭环，不含 Agent/LLM）
  agents/        智能体入口
    ops/         运维智能体（态势采集 / 故障诊断 / 自愈建议）
    resource/    资源控制智能体（调度 / 路由调整 / QoS 保障）
    a2a/         A2A 协议 / 任务调度 / 冲突仲裁
    llm/         LLM 通道（客户端 / 调用计量 / 提示词；只解释与增强，不生成链路）
tests/           测试（含针对真实 simulator 的集成测试）
experiments/     场景库与结果报告
```

## 快速开始

```bash
uv sync                 # 安装依赖
uv run pytest           # 跑测试
uv run python -m src.baseline.main   # 启动传统路径控制循环
```

## 关键约定

- 令牌从 `simulator/conf/gateway.json` 运行时读取，勿写入代码/提交。
- QoS 判定口径（静态 vs 实测）与仿真器一致，见 `docs/common/modeling/数学建模方案.md`。
- 官方仿真器为发布件，位于同仓库 `simulator/`，禁止修改其代码。

详见根目录 `CLAUDE.md`。
