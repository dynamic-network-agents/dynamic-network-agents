# ISS-0005 邮件草稿：致 B03 出题组的设计确认

> 状态：草稿（未发送）  
> 关联问题：`experiments/iss/ISS-0005.md`  
> 创建时间：2026-11-18  
> 用途：第一封事实确认邮件；语气为「确认设计预期」，不写「文档错误 / 平台 bug」。

## 一、五个问题的浓缩版

| # | 我们观察到的现象 | 想请出题组确认的设计点 |
|---|---|---|
| 1 | T0（无事件）40 条初始业务按 `paths[0]` 逐业务静态合成 **0/40 违规**；但按 flow 聚合后至少 **10 条链路需求带宽超容量**（如 L00013 66.89/26 Mbps、L00017 72.92/29 Mbps）；运行时 background/test 出现较多 `actual.qosMeet=false` | 初始不达标是否是设计预期（即 `service-paths.json` 只保证“单业务静态可行”，全局拥塞正是要 agent 重路由解决的问题）？还是应给出全局可行的初始分配？运行时是否确实只取 `paths[0]`？评测场景是否保证包含 `service-paths.json`？ |
| 2 | `TSV0005`（UAV0002→UAV0001）与 `BGV0009/BGV0020`（UAV0001→UAV0002）属于同一 flow，共用同一条路径 | flow 是否按无向节点对/IP 对键控、不区分 src→dst 方向？同一对节点的所有业务（含 background）是否必须共用一条路？能否按方向或业务分开？ |
| 3 | 对 `TSV0005` 一次 POST，三条同 flow 业务的 GET path 同时变成同一 `pathId/source=agent`；候选路径对 `TSV0005` 静态可行、但对兄弟业务 jitter 违规（15.23 > 11），平台仍 `accepted`；body 的 `src/dst` 可覆盖且不校验一致性 | 一次改全 flow 是否是设计预期？受理校验是否应覆盖同 flow 全部业务（带宽 max、时延/抖动/丢包/误码取最严）？当前是否要求调用方自行承担兄弟业务约束？`src/dst` 覆盖是有意设计还是契约限制？ |
| 4 | 无 `path_info` 时，反向业务 GET path 只剩 `L00015→L00012`，缺接入链路 `L00019/L00017`；直接回写 POST 报 1001 段列表不连续。下发过路径后，三条业务返回同一份 canonical 段列表，但反向业务首段不接源节点 | GET 设计上应返回业务源→宿方向的完整路径，还是 flow 规范方向？如果是后者，能否在文档/响应中明确方向（如 `direction/flowId`）并说明安全恢复方法？反向业务缺接入链路是预期表示还是缺陷？ |
| 5 | 文档只描述 `GET /events` 轮询；日志出现 `ws://127.0.0.1:8091/topo ... Connection refused`；同 flow 改路后是否逐业务通知、平台是否自动重算、`node_move` 派生事件是否生效均不确定 | 平台是否只支持轮询、不支持服务端推送？flow 改路后同 flow 的 B/C 是否都收到 `service_state_changed(pathChanged=true)`？`source=system` 的自动重算触发条件是什么？`node_move` 在评测镜像是否应生效？ |

---

## 二、邮件正文（可直接复制）

**主题：B03 参赛队咨询：关于 flow 级路径、初始加载与事件通知的设计确认**

尊敬的 B03 出题组老师：

您好！我们是参加 B03「资源受限环境下通信网络资源管控」的参赛队。我们在官方发布件（`netsim:latest`、`servicesim 1.0.5`，场景 `sce20261010-conf02/sce01`）上做闭环调试时，观察到一些接口行为与我们的理解不完全一致。想确认这些是否属于设计预期，以便在方案和实验中采用正确口径。以下现象均已在本地复现；如我们的理解有偏差，也请老师指正。

### 一、发现与测试方法（摘要）

**1. 静态核对**

- 读取 `net-topo.json`、`bg-service.json`、`service-paths.json`；
- 对 sce01 的 40 条初始业务，按各自 `paths[0].links` 的链路参数合成端到端 QoS（`D=Σd、J=√Σj²、B=min、L=1-∏(1-p)、E≈Σε`），与 `requirement` 比较：**逐业务 0/40 违规**；
- 按无向 `(srcNodeId, dstNodeId)` 归并为 **17 个 flow**，累加每个 flow 的 `requirement.bandwidthBps`，映射到 `paths[0]` 的链路，与 `net-topo.json` 的链路带宽比较：**至少 10 条链路超过 100%**，例如：
  - `L00013`：66.89 Mbps / 26 Mbps，约 257%；
  - `L00017`：72.92 Mbps / 29 Mbps，约 251%；
  - `L00021`：55.54 Mbps / 23 Mbps，约 242%。

**2. 运行时验证**

- 通过 UI 启动 sce01（公开 `POST /simulation/start` 在当前镜像返回 1003「未知接口」，故走 `/sdn-ui/start`）；
- 使用公开 API（`X-Open-Token`）读取 `/services`、`/services/{id}`、`/services/{id}/path`；
- 选取 `UAV0001/UAV0002` flow：`TSV0005`（UAV0002→UAV0001）、`BGV0009/BGV0020`（UAV0001→UAV0002）；
- 对 `TSV0005` 调用一次 `POST /services/TSV0005/path`，候选路径为 `L00019→L00011→L00010→L00009→L00015→L00017`；观察返回 `accepted`、`pathId=P01005`、`source=agent`，并复查三条业务的 GET path 与 actual；
- 在无 `path_info` 的干净实例上，读取反向业务 `TSV0005` 的 GET path，并尝试把返回值直接回写；
- 轮询 `/events`，并观察 WS 8091 的连接日志；
- 运行实例：`instanceId=20261118-164030`，`t0TsUs=1794991230346425`；复现测试：`tests/integration/test_iss0003_flow_path_contract.py`；
- 辅助核对：只读查看发布镜像中的 `openapi.py`（`_flow_for`、`_set_service_path`、`_service_path_obj`、`_install_service_path`）。

**3. 环境说明**

- 本机为 Apple Silicon + Docker Desktop/Rosetta 运行 `linux/amd64` 镜像；40 业务约 11 分钟后控制面出现过超时，因此运行结论主要取自 T0 后早期窗口；flow 级行为同时有源码核对支持，建议在官方 x64 环境复核。

### 二、待确认的五个问题

**1. 初始加载与 T0 达标状态**

我们在 T0（无事件）看到：40 条初始业务按 `paths[0]` 逐业务静态校验 **0/40 违规**，但按 flow 聚合后至少 10 条链路需求带宽超过容量；运行时 background/test 业务出现较多 `actual.qosMeet=false`。想确认：

- (a) 这是否是设计预期——即 `service-paths.json` 只保证「单业务静态可行」，不保证全局容量/实测达标，T0 拥塞正是需要智能体重路由解决的问题？
- (b) 还是说 `service-paths.json` 应给出全局可行的初始分配，当前现象属于场景生成/数据问题？
- (c) 运行时初始引流是否确实只取 `paths[0]`，`paths[1]/paths[2]` 仅作为候选？评测场景是否保证包含 `service-paths.json`？

**2. 同一对节点的 flow 粒度**

以 `UAV0001/UAV0002` 为例，`TSV0005`（UAV0002→UAV0001）与 `BGV0009/BGV0020`（UAV0001→UAV0002）在平台侧属于同一 flow，共用同一条路径。想确认：

- (a) flow 是否按无向节点对/IP 对键控，不区分 src→dst 方向？
- (b) 同一对节点之间的所有业务（含 background）是否在设计上必须共用一条路径，不能按方向或业务分开？
- (c) 如果是，公开 API 是否计划暴露 flow 标识，或提供 flow 级查询/设置入口？

**3. POST path 的影响范围与校验**

我们实测对 `TSV0005` 调用一次 POST，`TSV0005/BGV0009/BGV0020` 三条业务的 GET path 同时变为同一 `pathId`、`source=agent`。想确认：

- (a) 这是设计预期吗？
- (b) 如果是，受理校验是否应覆盖同 flow 全部业务（带宽取 max，时延/抖动/丢包/误码取最严）？当前平台只按 URL 中 `serviceId` 的 `requirement` 校验；我们构造的候选路径对 `TSV0005` 静态可行，但对 `BGV0009/BGV0020` 的 jitter 已违规（15.23 > 11，约 38.5%），仍返回 `accepted`。是否要求调用方自行承担同 flow 约束？
- (c) body 中的 `srcNodeId/dstNodeId` 可以覆盖业务端点且不校验一致性，这是有意设计还是应视为契约限制？

**4. GET path 的表示与恢复**

在无 `path_info` 的干净实例上，反向业务 `TSV0005` 的 GET path 只返回 `L00015→L00012`，缺少两端接入链路 `L00019/L00017`；直接将该 `segments` 回写 POST 返回 `1001 段列表不连续`。对同一 flow 下发过路径后，三条业务都返回同一份 canonical 段列表，但反向业务的首段不接其源节点。想确认：

- (a) `GET /services/{id}/path` 设计上应返回业务源→宿方向的完整路径，还是 flow 规范方向？
- (b) 如果是后者，能否在文档/响应中明确方向（例如 `direction/flowId`），并说明调用方应如何安全恢复路径？
- (c) 反向业务缺接入链路是预期表示，还是缺陷？

**5. 事件通知**

官方文档只描述了 `GET /events` 轮询；我们在日志中看到向 `ws://127.0.0.1:8091/topo` 的上报重试 `Connection refused`。想确认：

- (a) 平台是否只支持轮询、不支持服务端推送？这是设计如此，还是当前构建的限制？
- (b) 当 flow 级路径被修改（例如对 A 业务 POST），同 flow 的 B/C 业务是否都会收到 `service_state_changed` 且 `pathChanged=true`，还是只通知被调用的 A？
- (c) 链路/节点事件发生后，平台是否会自动重算路径（`source=system`）？触发条件是什么，是否产生对应事件？
- (d) 文档描述了 `node_move` 派生的链路/节点事件；我们这边 `node_move` 似乎未生效（脚本 `attrs` 用 `fromX/fromY/toX/toY`，代码读 `from`/`to`；`linkTypes.json` 缺 `losMeters`）。评测镜像是否会修复，或应按当前行为设计场景？

### 三、补充确认（如方便一并答复）

- 评测镜像是否实现公开 `POST /api/open/v1/simulation/start`？当前镜像返回 1003「未知接口」，是否有官方推荐的公开起测方式？
- `actual.qosMeet` 是否会在评测环境中稳定提供？公开 API 是否能获得 test/background 标识（`category`）？

我们目前的应对是：以 flow 为单位聚合需求、本地做静态校验、下发后复查同 flow 所有业务的 `qosMeet`，并且不直接用 GET path 做恢复。希望通过这封邮件确认上述设计口径，避免在实验和报告中按错误假设展开。

如需要，我们可以提供复现脚本、脱敏日志、静态核算表和相关场景数据（不含令牌）。麻烦老师确认哪些行为属于设计预期、哪些属于当前构建的限制或缺陷。

感谢老师的时间！

[参赛队名称]  
[联系人 / 联系方式]  
2026-11-18

---

## 三、发送前检查清单

1. **语气**：草稿使用「文档未展开 / 我们理解不确定 / 想确认设计预期」，未写「文档错误」或「平台 bug」。
2. **可删减**：如不想暴露「只读查看镜像源码」，可删掉「辅助核对」一条，只保留运行现象。
3. **附件**：建议附脱敏的「sce01 静态核算表」（40 业务/17 flow/超容链路清单）和复现脚本；不要附令牌、`gateway.json` 原文或完整内部 ISS 文档。
4. **第 5 点**：如果实际现象不是 a-d（例如事件丢失、顺序、`sinceTsUs` 游标、`service_state_changed` 不及时），发送前替换为具体现象。
5. **第 1 点**：若出题组回复「初始拥塞是预期，agent 负责重路由」，则 ISS-0002 的定性从「场景数据问题」转为「设计预期」，实验报告应把 T0 拥塞写成基线特征，而不是缺陷。
6. **占位符**：发送前替换 `[参赛队名称]`、`[联系人 / 联系方式]`；确认日期。
7. **敏感信息**：邮件与附件中不要出现 `openTokens`、`ctrlToken`、`LLM_API_KEY`、`LITELLM_MASTER_KEY` 等密钥。
