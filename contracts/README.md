# contracts — 模块间通信契约

机器可读契约（JSON Schema，draft 2020-12），由《前后端数据模型与接口规范 v1.0》（唯一事实源）导出，供 backend / simulator / agent-platform / algorithms 生成 DTO 并与前端对齐。

## 单向导出链（拆分方案 §4.8）

```text
接口规范 md（人读源）
   └─▶ contracts/schemas/*.json（机器契约，当前手工维护）
            └─▶ datamodel-code-generator ─▶ 各模块 Pydantic DTO（阶段四/五接入）
```

- 契约由接口规范**单向导出**，不回写接口规范；接口规范是唯一事实源。
- 当前阶段：手工维护 JSON Schema（阶段一）；datamodel-code-generator / OpenAPI 快照在 backend/simulator 有 FastAPI 服务后接入（阶段四/五）。

## Schema 清单

| 文件 | 实体 | 对应规范 | 轮次 |
|---|---|---|---|
| `node.json` | NetworkNode（含 Position / Mobility / NodeResources） | §5.1 | 首轮 |
| `link.json` | NetworkLink（含 LinkParams） | §5.2 | 首轮 |
| `flow.json` | BusinessFlow（含 QosRequirement / QosMeasurement / QosViolation） | §5.3 | 首轮 |
| `scenario.json` | Scenario（含 ScenarioEvent） | §5.4 | 首轮 |
| `simulation.json` | SimulationRun | §5.5 | 首轮 |
| `network_snapshot.json` | TopologySnapshot（含 TopologySummary） | §5.5 | 首轮 |
| `qos.json` | QosSummary | §7.9 | 首轮 |
| `realtime.json` | RealtimeEventEnvelope | §8.2 | 首轮 |
| `api_payloads.json` | ScenarioValidateResult / EventInjectionResult / FieldError | §7.6/7.7 | 首轮 |

首轮边界以规范 §14「最小数据集」为准；**延后（二轮）**：Agent（§5.6）、Policy（§5.7）、ResourceAllocation（§5.8）、MetricPoint / Experiment（§5.9），以及诊断/策略类 schema（`diagnosis_result` / `candidate_policy` / `policy_execution_result`）。

## 约定

- **字段名 camelCase**；枚举**大写**；`linkType` 小写自由格式（以接口规范 §2 为准）。
- **`additionalProperties` 缺省为 true**（JSON Schema 默认），对应前端 Zod `.passthrough()` 向前兼容：未知字段不报错、由消费方按需透传。
- **枚举字段保持开放 `string`**（非 `enum` 约束）：已知值写入字段 `description`，未知值由适配层兜底、不臆造语义；需要严格枚举时再加 `enum` 与扩展标记。
- **数值范围**镜像前端 Zod：`ber` / `packetLossRate` / `utilization` / `maxPacketLossRate` / `minReliability` / `availability` ∈ [0,1]；`energyPercent` ∈ [0,100]。
- 时间戳字段为 `string`，具体格式以接口规范 §2 为准（不臆造 `format`）。

## 校验

```bash
uv run python scripts/check_contracts.py
```

校验 JSON Schema 语法（draft 2020-12）与跨文件 `$ref` 可解析性。与前端 Zod 的字段级对比、OpenAPI 快照一致性检查，待 backend/simulator 有 FastAPI 服务后接入（阶段四/五）。
