# B03 Work Bench — 端口、令牌与服务器部署口径

> 文档版本：V1.2 · 日期：2026-11-24
> 适用：`work_bench/`（B03 调试控制台）及其对仿真器的访问方式
> 依据：`docs/competition_desc/仿真软件接口.md`、`simulator/README.md`、`sim_src/`（解码副本，行号为解码件行号）
> 结论先行：**端口决定"怎么到达"，令牌决定"记谁的账"；两者互不影响。**

---

## 1. 为什么写这份文档

调试控制台需要 1–2s 轮询拓扑/链路/业务/事件。如果这些请求带着**智能体公开令牌**，
就会大量写进仿真器的 agent 调用台账（`llm_gateway_call_stat.log`），
进而影响「智能体行为质量 / 观测频率」这类观测与评分证据。

本文回答三件事：

1. 仿真器一共开了哪些端口、各自给谁用；
2. 接口怎么分类、令牌和接口是什么关系；
3. 本机（Mac）与服务器、以及 SSH 隧道到底怎么对应。

---

## 2. 端口全景

### 2.1 对外发布的端口（宿主机可直接访问）

| 宿主端口 | 容器端口 | 监听者 | 用途 | 谁访问 | 令牌 |
|---|---|---|---|---|---|
| **10000** | 9988 | nginx（netsim 容器） | 官方前端网页 + `/sdn-api/` `/sdn-ctrl/` `/sdn-ui/` 三个代理 | 浏览器 | 浏览器不带，nginx 服务端注入 |
| **10100** | 8080 | 控制面 `ctrl.py` | 所有 `/api/open/v1/*`、`/api/ctrl/v1/*`，以及 `/net` `/stats` `/ui/*` 等页面接口 | agent、workbench、官方前端 | open 令牌或 ctrl 令牌 |
| 10001 | 10001 | servicesim-tx 自带总览页 | 业务发送端排查页 | 人 | 内部固定 token |
| 10002 | 10002 | servicesim-rx 自带总览页 | 业务接收端排查页 | 人 | 内部固定 token |
| 10010 | 8080 | eval-app | 测评工作台 | 人 | — |
| 10110 | 4000 | LiteLLM | 大模型代理（智能体经它调模型） | agent | master key |
| 8000 | — | workbench 后端 | 控制台 API + 托管前端 | 本机浏览器（经 SSH 隧道） | — |
| 5173 | — | vite（dev） | 前端开发服务器 | 本机浏览器 | — |

> 10000 / 10010 / 10100 / 10110 是官方约定的"前端 + API"端口段，避开 8000/8080/4000 等常用端口。
> 10010 / 10110 来自 `simulator/docker/eval/.env` 的 `DEPLOY_APP_HOST_PORT` / `LITELLM_HOST_PORT`。

### 2.2 不对外发布的端口（容器内 / 仿真网络内）

| 端口 | 位置 | 用途 |
|---|---|---|
| **8090** | 每个仿真节点 IP（10.x）上 | 业务发送端内部 API（控制面下发业务、查健康） |
| **8092** | 同上 | 业务接收端内部 API |
| 8091 | netsim 容器内 | 旧拓扑 WS 推送，**20261106 起默认不启动**（`start_root.sh:108`） |
| 20000–29999/udp | 跨机部署的 `sim-media` | 业务媒体流转发口 |

8090/8092 在节点命名空间里，宿主机 `curl localhost:8090` 连不上；
只有控制面和 tx/rx 总览页会访问 `http://<节点IP>:8090/api/v1/services/health`。

---

## 3. 三条访问链路

```
① 人看网页（官方前端）
   浏览器 ──:10000──> nginx(9988) ──/sdn-api/──>  ┐
                        ├──/sdn-ctrl/───────────>  ├──> 控制面(8080)
                        └──/sdn-ui/────────────>  ┘

② 程序调 API（agent / workbench）
   程序 ──:10100──────────────────────────────────> 控制面(8080)/api/open/v1/*

③ 控制面 ↔ 业务仿真（容器内部，不对外）
   控制面(8080) ──> 节点IP:8090 (tx) / 节点IP:8092 (rx)
```

要点：

- ① 和 ② **到达的是同一个 8080**，拿到的数据完全一样。
- 10000 只转发 `/sdn-api/`、`/sdn-ctrl/`、`/sdn-ui/`；`/net`、`/stats`、`/topo_status` 这类
  无前缀页面接口只能在 10100 上访问。
- nginx 是**可选组件**：`start_root.sh` 里起不来只打印"前端不可用，核心实验不受影响"。

---

## 4. 接口分类

| 类别 | 例子 | 谁用 | 令牌 | 记账 |
|---|---|---|---|---|
| **① 公开 API** | `GET /api/open/v1/topology`、`/services`、`/services/{id}`、`POST /services/{id}/path` | 参赛 agent、workbench | `X-Open-Token`，**也接受** `X-Ctrl-Token` | 带 open 令牌 → `call_stat`；否则 → `front_stat` |
| **② 内部控制 API** | `GET /api/ctrl/v1/run-info` / `svc-meta` / `script-timeline` / `agent-calls` / `agent-events`，`POST /api/ctrl/v1/simulation/control`，`PUT /api/ctrl/v1/links/{id}/params` | 官方前端、eval | **只认** `X-Ctrl-Token`（用 open 令牌报 1006） | `front_stat` |
| **③ 前端页面接口** | `GET /net`、`/stats`、`/topo_status`、`/health`、`/ui/meta`、`POST /ui/start`、`POST /path`（Mininet 流表） | 官方前端网页 | 多数免令牌；`/ui/start` 要 ctrl 令牌 | **不记账**（不在 `/api/` 下） |
| **④ nginx 别名** | `/sdn-api/…`、`/sdn-ctrl/…`、`/sdn-ui/…` | 浏览器 | 浏览器不带，nginx 注入 | 同去掉别名后的接口 |

`/sdn-*` 不是新接口，只是"改前缀 + 服务端补令牌"。
前端 JS 永远看不到 ctrl 令牌，所以浏览器 F12 里翻不到任何 token。

---

## 5. 令牌与记账（本文核心）

### 5.1 两张卡

| 卡 | 字段 | 用途 | 能力 |
|---|---|---|---|
| 访客卡 | `conf/gateway.json` 的 `openTokens[]` | 参赛 agent | 只能进 ①；进 ②会 1006 |
| 内部工牌 | `conf/gateway.json` 的 `ctrlToken` | 官方前端 | ① 和 ② 都能进 |

### 5.2 记账规则（`sim_src/netsim/openapi.py`）

- 每个 `/api/*` 请求都会进 `_call_log`（函数在 2439 行附近）。
- **请求头里有 `X-Open-Token` → 写 `llm_gateway_call_stat.log`；否则写 `llm_gateway_front_stat.log`**（2455–2460 行）。
- `GET /api/ctrl/v1/agent-calls` 只读 `call_stat`（2156 行定义、2164 行取文件）——这就是"agent 观测统计"。
- 非 `/api/` 的页面接口不经过 `handle_http`，**完全不记账**。
- 改路径另有一本账：`path_event_stat.log`，且 `source` 被硬编码为 `'agent'`（2070、2105 行），
  `GET /api/ctrl/v1/agent-events` 只按 `source == 'agent'` 过滤（2204 行）——**换任何令牌都躲不开**。

### 5.3 频控按 IP 共享

GET 100 次/秒、提交 10 次/秒，键是来源 IP（1604–1615、1581–1601 行），**与令牌无关**。
所以经 SSH 隧道进来的请求（源 IP 变成 `127.0.0.1`）会与同一台机器上其他隧道客户端共享额度。

---

## 6. workbench 的通道选择

| 方案 | 请求 | 依赖 | 记账 |
|---|---|---|---|
| **A（采用）** | `:10100/api/open/v1/...` + `X-Ctrl-Token` | 仅 10100 | `front_stat`（不计入 agent 统计） |
| B（备选） | `:10000/sdn-api/open/v1/...`（nginx 注入） | nginx + 10000 | `front_stat` |
| C（不采用） | `:10100/net`、`/stats` | 仅 10100 | 不记账，但没有业务 QoS 数据 |

选 A 的理由：接口语义、字段、错误码与公开 API 完全一致，只换鉴权头；
10100 每份部署都有；不依赖 nginx 存活；令牌读取方式与原有 `openTokens[0]` 相同。

配置（`work_bench/backend/.env`）：

```bash
SIM_BASE_URL=http://127.0.0.1:10100/api/open/v1
SIM_AUTH=ctrl                       # 默认；ctrl=前端同款，open=显式降级
SIM_CTRL_TOKEN=                     # 或留空 + SIM_TOKEN_FILE 指向 gateway.json
SIM_CTRL_BASE_URL=                  # 留空则按 SIM_BASE_URL 推导 .../api/ctrl/v1
WORKBENCH_SVCMETA=1                 # 用 /api/ctrl/v1/svc-meta 取实时 category（仅 ctrl 通道生效）
WORKBENCH_ALLOW_REPATH=1            # 正式录分置 0，见第 7 节
```

**不做静默降级**：ctrl 模式找不到 `ctrlToken` 时，workbench 不会自动改用公开令牌，
而是空令牌 + 启动告警（health 里 `token_configured=false`）；
确实要用公开令牌必须显式 `SIM_AUTH=open`，此时日志会提示"调用会计入 agent 统计"。

---

## 7. 唯一无法隔离的写动作：改路径

`POST /services/{id}/path` 无论用哪张令牌，仿真器都记成 `source='agent'` 的 path 事件
（`openapi.py:2070`、`2105`），并出现在 `agent-events` 里（`2204` 行过滤）。

处置：

- 默认保留该能力（调试必需），成功响应里带 `warning` 字段说明已留痕；
- 正式跑/录分时置 `WORKBENCH_ALLOW_REPATH=0`，后端对 `/api/repath` 返回 403；
- 事件里的 `tokenId` 是 workbench 的 ctrl 令牌，可据此事后区分。

---

## 8. 本机（Mac）与服务器

| 项 | 本机 Mac（`mac-docker-trial/compose.local.yml`） | 服务器（`simulator/docker/netsim/compose.yml`） |
|---|---|---|
| 端口绑定 | `127.0.0.1:10000:9988`、`127.0.0.1:10100:8080`（仅本机） | `"10000:9988"`、`"10100:8080"`（0.0.0.0，局域网可访问） |
| 10001/10002 | 额外映射 | 不映射（包内原版没有） |
| 架构 | Rosetta 转译 amd64，慢、偶发超时 | 原生 x64 |
| 数据目录 | `../simulator/` bind mount | 同 |

### 8.1 目标形态（自 2026-11 起）

仿真服务、agent、workbench **全部跑在服务器**；本机只通过 SSH 隧道访问：

```bash
# 本机执行：把服务器的 workbench 8000 映射到本机 8000
ssh -L 8000:127.0.0.1:8000 user@<server>
# 浏览器打开 http://127.0.0.1:8000
```

服务器上启动 workbench（保持只绑 127.0.0.1，不对外暴露写接口）：

```bash
cd work_bench && mkdir -p logs
nohup ./backend/run.sh >> logs/workbench.log 2>&1 &
```

### 8.2 若 workbench 反而跑在本机（过渡形态）

```bash
# 本机 20100 → 服务器 10100（避免占用本机已有仿真器的 10100）
ssh -L 20100:127.0.0.1:10100 -L 20000:127.0.0.1:10000 user@<server>
# workbench 配 SIM_BASE_URL=http://127.0.0.1:20100/api/open/v1
```

### 8.3 隧道注意

- 经隧道后服务器侧看到的源 IP 是 `127.0.0.1`，与服务器本机其他隧道客户端共享频控桶；
- 隧道断开 → workbench `/api/health` 失败 → 前端显示 DISCONNECTED，属预期；
- 不要在服务器上把 8000 改成 0.0.0.0，除非前面有认证网关（`/api/repath` 是写接口）。

---

## 9. 配置速查

| 变量 | 默认 | 说明 |
|---|---|---|
| `SIM_BASE_URL` | `http://127.0.0.1:10100/api/open/v1` | 观测/写都走这个公开接口基址 |
| `SIM_AUTH` | `ctrl` | `ctrl`=前端同款；`open`=显式降级（会污染统计） |
| `SIM_CTRL_TOKEN` | 空 | 直接给 ctrl 令牌 |
| `SIM_TOKEN_FILE` | 空 | gateway.json 路径；按 `SIM_AUTH` 取对应键 |
| `SIM_CTRL_BASE_URL` | 自动推导 | 控制面接口基址（svc-meta 用） |
| `WORKBENCH_SVCMETA` | `1` | 是否用实时 svc-meta 分类 |
| `WORKBENCH_ALLOW_REPATH` | `1` | 是否允许 `/api/repath` |
| `BG_SERVICE_PATH` | 空 | svc-meta 不可用时的离线分类兜底 |
| `SERVICE_PATHS_PATH` | 空 | 改 service 的候选路径 |

启动日志只说明通道（`ctrl` / `open` / `none`），不打印任何令牌。

---

## 10. 待核对

1. `agent-calls` / `agent-events` 在官方判分中的具体权重——本仓库无判分脚本，只有"两本账"这一层代码依据。
2. `svc-meta` 的业务覆盖范围在"业务尚未启动/部分失败"时是否与 `/services` 一致——需运行期实测。
3. 服务器部署下 10001/10002 是否需要额外映射——当前依赖包内原版 compose（不映射）。
