"""共享底座（common）：baseline 与 agents 共用的能力层。

分层（依赖单向，无环）：

```
modeling  ←  topology / path / flow  ←  perception  ←  simulator  ←  control  ←  baseline / agents
                （纯计算，无 IO）        （快照/事件）   （HTTP 适配）   （闭环编排）
```

各子包职责：

- `modeling`：数学建模——数据模型、静态/实测 QoS、链路代价归一化。纯计算，无 IO。
- `algorithms`：算法库，按领域三分——`topology`（图与容量记账）、`path`（路径级）、
  `flow`（flow 级联合选路）。纯计算，依赖 `modeling` + networkx。
- `perception`：感知层——冻结快照（拓扑/业务/现状路径）与事件流（游标 + 可行动过滤）。
  baseline 与 agents 必须看到**同一个**网络视图，否则对比实验不可信。
- `simulator`：仿真器 HTTP 适配——公开 API client 与路径下发执行器。
- `control`：闭环控制——epoch 状态机、下发闸门、实测校验。agents 可复用同一套，
  只替换决策核心，从而保证对比实验的唯一差异是「谁来做规划决策」。
- `config`：配置加载（`configs/*.yaml` 与令牌读取的唯一入口）。
- `util`：通用工具（预留）。
"""
