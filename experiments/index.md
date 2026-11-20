# 记录索引与编号登记

> 手工维护。**新增前先在这里占号**，再写文件，避免编号冲突。用过的号不复用。

## 实验记录（EXP）

| 编号 | 标题 / 场景 | suiteId / scenarioId / scriptId | 状态 | 日期 |
|---|---|---|---|---|
| EXP-0001 | 初始场景静态导入示例 | sce20261012-conf01 / sce01 / script-01 | ready | 2026-11-18 |
| EXP-0002 | `待占号` | — | — | — |

## 问题清单（ISS）

| 编号 | 标题 | 分类 | 优先级 | 状态 | 首次发现实验 | 日期 |
|---|---|---|---|---|---|---|
| ISS-0001 | flow 键控口径：nodeId vs IP 不一致 | NET | P1 | investigating | EXP-0001 | 2026-11-18 |
| ISS-0002 | service-paths.json 预置路径未做全局负载均衡，基线业务大面积未达标 | ALG | P1 | investigating | —（手工运行 sce20261010-conf02/sce01） | 2026-11-18 |
| ISS-0003 | 公开 API service 级入口与 flow 级生效/校验不一致 | NET | P1 | investigating | —（源码核对 netsim 镜像 openapi.py） | 2026-11-18 |
| ISS-0004 | GET path 对反向业务缺少接入链路且方向不随业务方向 | NET | P1 | investigating | —（ISS-0003 集成测试首次运行） | 2026-11-18 |
| ISS-0005 | 官方文档与实际发布件口径差异汇总（flow / 启动 / 场景文件 / 错误码） | NET | P1 | investigating | —（ISS-0003/0004 结论对照官方文档） | 2026-11-18 |

> ISS-0003 已在 `sce20261010-conf02/sce01` 运行时验证：C1/C2/C3 确认，C4 因基线已拥塞无法归因；平台行为已确认，agent 侧适配待实现。
> ISS-0004 已在首次运行复现；需重启实例（无 agent 下发）做二次确认。
> ISS-0005 汇总文档口径差异：A1-A4、B2、C1、C2 已核实；`simulation/start`（B1）、`node_move`（B3）、评测场景是否含 `service-paths.json`（D5）等待复核/官方确认。

### 分类 / 优先级 / 状态取值

- 分类：`ENV` 工程环境 / `NET` 通信网络模型 / `ALG` 资源管控算法 / `AGT` Agent 智能体 / `EXP` 实验评测
- 优先级：`P0` 阻断 / `P1` 核心功能异常 / `P2` 有绕行 / `P3` 低影响
- 状态：`open` / `investigating` / `blocked` / `fixing` / `verifying` / `resolved` / `closed` / `reopened`
