# 动态通信网络多智能体系统 — 前端

通信网络资源管控多智能体系统的前端工程。技术栈：React 18 + TypeScript + Vite + React Router v7 + Ant Design v5 + Zod + Zustand。

当前进度：FE-001 工程初始化、FE-002 质量工具与测试框架、FE-003 全局布局与路由、FE-004 共享类型与 DTO 适配、FE-005 API 客户端与错误处理、FE-006 Zustand 状态管理骨架、FE-007 Mock REST 与 WebSocket 已完成。

## 环境要求

| 依赖 | 版本 |
|---|---|
| Node.js | >= 20（建议 20 LTS，见 `.nvmrc`） |
| pnpm | >= 10（本项目使用 `packageManager` 字段锁定） |

## 安装
在 frontend 目录下
```bash
pnpm install
```

## 常用命令

| 命令 | 说明 |
|---|---|
| `pnpm dev` | 启动开发服务器（默认 http://localhost:5173） |
| `pnpm build` | 类型检查 + 生产构建（输出到 `dist/`） |
| `pnpm preview` | 本地预览生产构建产物 |
| `pnpm typecheck` | TypeScript 类型检查（应用 + 构建配置） |
| `pnpm lint` | ESLint 静态检查 |
| `pnpm format` | Prettier 格式化（写入） |
| `pnpm format:check` | Prettier 格式校验 |
| `pnpm test` | 运行单元/组件测试（Vitest） |
| `pnpm test:watch` | 监听模式运行测试 |
| `pnpm coverage` | 运行测试并生成覆盖率报告（含阈值检查） |

## 环境变量

工程通过 `.env.development` / `.env.test` / `.env.production` 区分环境，模板见 `.env.example`。业务代码一律通过 `src/config/env.ts` 的 `getEnvConfig()` 读取配置，**禁止**散落使用 `import.meta.env`。

| 变量 | 必填 | 说明 |
|---|---|---|
| `VITE_APP_TITLE` | 是 | 应用标题 |
| `VITE_API_BASE_URL` | 是 | 后端 API 基础地址 |
| `VITE_USE_MOCK` | 否 | 是否启用 Mock（默认 `false`） |

缺少必要配置时，读取会抛出可读错误提示而非白屏。

## 测试约定

- 测试环境统一为 `jsdom`；初始化见 `src/test/setup.ts`（每个用例结束后自动卸载组件并恢复 spy，保证测试隔离、不依赖执行顺序）。
- 组件测试统一使用 `src/test/renderWithProviders.tsx` 的 `renderWithProviders`（用与生产一致的 Provider 包裹，后续叠加 Router/Store/Query）；查询与交互 API 也可从该文件导入。
- 测试数据工厂见 `src/test/factories.ts` 的 `createFactory`；领域工厂随 FE-004 类型收敛后扩展。
- 覆盖率使用 v8 provider，阈值见 `vite.config.ts`（statements/branches/functions/lines 均为 80%），报告输出到 `coverage/`。
- Mock：MSW 的 server 生命周期（启动/重置/关闭）已由 `src/test/setup.ts` 全局接入（FE-007）；各测试用 `server.use(...)` 覆盖具体路由即可。
- 格式化：`pnpm format` 写入、`pnpm format:check` 校验，规则见 `.prettierrc.json`。

## 页面与路由

7 个一级页面 + 404 兜底页：

| 路由 | 页面 | 说明 |
|---|---|---|
| `/` | 系统总览 | 仿真摘要 / 业务 QoS / Agent 状态 / 最近实验 |
| `/topology` | 网络拓扑 | 节点/链路图、链路详情、路由路径（FE-004 起填充） |
| `/scenario` | 场景配置 | 节点/链路/业务流/动态事件配置 |
| `/simulation` | 仿真控制台 | 开始/暂停/恢复/停止/单步、事件注入 |
| `/agents` | Agent 监控 | Agent 状态、A2A 消息、任务链路 |
| `/resources` | 资源与 QoS | 带宽分配、链路质量、业务 QoS |
| `/experiments` | 实验分析 | 指标统计、对比实验、结果导出 |
| `*` | 404 | 未匹配路径的兜底页 |

路由约定：

- **单一来源**：页面路径 / 标题 / 图标 / 描述统一维护在 `src/app/pageMeta.tsx`；侧边栏菜单、面包屑、页面标题、路由配置均由它派生，避免多处重复定义产生漂移。
- **生产路由**：`src/app/routes.tsx` 的 `routeConfig` 复用 `pageMeta`，经 `createBrowserRouter`（React Router v7 数据路由）装配；页面按需 `React.lazy` + `Suspense` 懒加载。
- **测试路由**：`src/test/renderWithRouter.tsx` 用声明式 `MemoryRouter` + `Routes` 复用同一 `routeConfig`，避开数据路由在 jsdom 下 `new Request()` 触发的 AbortSignal 类不一致问题。

## 类型与数据适配（FE-004）

外部数据（服务端 JSON / 赛题样例）→ Zod 校验 → 适配器 → 页面 ViewModel。页面只消费 `types/domain/` 的稳定 ViewModel，不直接依赖服务端原始字段。

| 目录 | 职责 |
|---|---|
| `src/types/enums.ts` | 枚举（`as const` + 联合类型）+ `coerceEnum`/`coerceEnumInsensitive` 兜底 |
| `src/types/domain/` | 域对象 ViewModel（Node/Link/Flow/Scenario/Event/Run/Snapshot/RealtimeEvent） |
| `src/schemas/` | Zod 运行时校验（服务端 DTO + `contest.ts` 赛题导入） |
| `src/adapters/` | DTO → ViewModel 映射（枚举兜底、单位透传、旧字段兼容） |

字段口径：字段 `camelCase`；带宽 `bps`、时延/抖动 `ms`、ber/丢包率/可靠性 0–1；仿真时间 `simTimeMs`、源时间戳 `tsUs`（`time` 仅展示）；可选字段缺失表示「未提供」，不用 0 代替；未知枚举值兜底（见 `enums.ts` 注释）。

链路建模：控制/数据链路按独立 `linkId` + `linkPlane`（CONTROL/DATA）表达，**不根据节点对推导**；`linkType` 为介质小写串，与 `linkPlane` 正交。赛题导入兼容 `bandwitdhBps` 旧拼写、`status` 小写归一（见 `adapters/contest.ts`）。

二轮类型（Agent/Policy/MetricPoint/ResourceAllocation/Experiment 等）仍延后到对应 feature 任务（Agent 监控 / 资源与 QoS / 实验分析）。

## API 客户端与错误处理（FE-005）

`src/api/` 提供统一 HTTP 传输层：axios 单例 + 响应/错误归一化 + 各业务 API 模块。API 函数返回**服务端 DTO 类型**（`z.infer`），Zod 校验与 DTO→ViewModel 适配延后到 store 层（FE-006）接线。

| 文件 | 职责 |
|---|---|
| `src/api/types.ts` | 传输层类型（`ApiResponse`/`Page`/分页参数/字段错误），以及语义待确认的聚合 DTO 别名（标注「待与官方确认」） |
| `src/api/errors.ts` | `ApiError`（`status`/`code`/`requestId`/`details`/`fieldErrors`）+ 状态码→业务码映射 + 分类守卫（`isValidationError`/`isConflictError`/`isNetworkError` 等） |
| `src/api/client.ts` | axios 单例（`getApiClient`）、响应拦截器（解包 `data`）、错误归一化（`toApiError`）、超时/AbortSignal/幂等键/`If-Match` |
| `src/api/query.ts` | 查询参数序列化（undefined/null 丢弃、数组逗号拼接） |
| `src/api/{dashboard,scenarios,simulations,topology,flows,qos,resources}.ts` | 各域 API 函数，路径对齐接口规范 §7.6–§7.9 |

**响应封包**（§7.2）：成功 `{ code:"OK", message, data, requestId, timestamp }`、错误 `{ code, message, details, requestId, timestamp }`；响应拦截器直接解包 `data` 返回，错误则归一为 `ApiError` 抛出。

**错误分类**（§7.3）：HTTP 状态码 → 业务码（400→`INVALID_ARGUMENT`、404→`RESOURCE_NOT_FOUND`、409→`CONFLICT`、422→`VALIDATION_FAILED`、429→`RATE_LIMITED`、5xx→`INTERNAL_ERROR`/`DEPENDENCY_UNAVAILABLE`/`DEPENDENCY_TIMEOUT`）；无 HTTP 响应时归为客户端错误码（`NETWORK_ERROR`/`TIMEOUT`/`REQUEST_CANCELLED`/`UNKNOWN_ERROR`）。

**写操作语义**（§7.1）：`POST` 支持 `Idempotency-Key`；`PUT` 场景更新支持 `If-Match` / `expectedVersion` 乐观锁。

**约定**：业务代码只经 `api/` 访问数据，不直接 import axios；组件/页面不消费 DTO，store 层校验+适配后才进入 ViewModel。

## 状态管理（FE-006）

按领域拆分的 Zustand Store；页面/组件经各 `useXStore` 与 selector 读取，不在组件内直连 axios 或散落 DTO 映射。

| Store | 状态与职责 |
|---|---|
| `appStore` | 当前运行上下文 `projectId`/`scenarioId`/`runId`；仅这三者经 `persist` 持久化（刷新后可按 runId 恢复），domain 数据仍内存、按需重拉 |
| `uiStore` | 本地 UI 态：`selectedNodeId`/`selectedLinkId`/`selectedFlowId`、`wsStatus`、`displayPrefs`（不持久化） |
| `simulationStore` | 当前仿真运行 `run`（`AsyncSlice` 四态）+ 启停/调速/单步等异步 action + 实时事件折算 |
| `topologyStore` | 拓扑快照 `snapshot` + `loadTopology` + 实时事件折算；`nodesById`/`linksById`/`flowsById` 用 selector 现算，不重复存 |
| `scenarioStore` | 场景 `list`/`current`/`validateResult` + CRUD/校验/克隆 + 本地 `draft` 编辑态（与事实态分离） |

**异步状态机**（`src/stores/async.ts`）：统一 `AsyncSlice<T> = { status: idle/loading/success/error, data, error }`；`loadingSlice`/`successSlice`/`errorSlice` 保持三者一致更新，loading/error 保留上次 `data` 供刷新中展示。

**运行隔离（防串数据）**：domain store 的 `runId` 只由 `resetRun` 绑定；异步 action 回包后用 `isStaleRun` 守卫，丢弃「晚到的旧 run 请求」，防止切 run 后旧结果覆盖新 run。跨 run 实时事件同样被忽略。

**数据流**：store 异步 action 调用 `api/`（返回 DTO）→ `schema.safeParse` → adapter → 落 ViewModel；校验失败以 422 `VALIDATION_FAILED` 落 error。Agent/Resource/Metric 三个域 store 待其二轮类型补齐后再建。

## Mock 服务（FE-007）

无真实后端时，用同一套内存运行态数据驱动 REST 与 WebSocket：`VITE_USE_MOCK=true/false` 切换（开发/测试默认开、生产关），UI 顶栏显示「Mock 模式」标记。

| 文件 | 职责 |
|---|---|
| `src/mocks/random.ts` | mulberry32 可播种 PRNG，固定 seed 可复现 |
| `src/mocks/fixtures.ts` | 确定性演示数据（默认 8 节点 / 12 链路 / 3 业务流 + 时间线事件） |
| `src/mocks/world.ts` | 内存运行态仓库（scenarios/runs/拓扑/事件日志），状态转换 + 确定性 `advance/step` 事件生成 |
| `src/mocks/handlers.ts` | MSW REST handlers，读写 world，写操作触发实时事件 |
| `src/mocks/realtime.ts` | `MockRealtimeProvider`，桥接 world 事件流，支持 lastSeq 补发 |
| `src/mocks/provider.ts` | `createRealtimeProvider()` Mock 开关工厂 |
| `src/mocks/browser.ts` | MSW 浏览器 worker（`main.tsx` 在 useMock 时启动） |
| `src/api/realtime.ts` | `RealtimeProvider` 接口 + 真实 WS 空实现（§8.1/8.4 待确认） |

**一致性**：REST 写操作推进同一份 `MockWorld` 运行态并产生实时事件，WS 订阅与后续 GET 查询反映相同状态；所有运行数据按 runId 隔离，切换 run 不串数据。

**可复现**：数据与事件由固定 seed（`DEFAULT_SEED`）+ 单调计数生成，同一 seed + 相同操作序列结果一致。

## 目录结构

```text
src/
  app/            # App、Providers、路由（pageMeta / routes / router）
  pages/          # 路由页面（dashboard/topology/scenario/simulation/agents/resources/experiments/not-found）
  components/     # 通用组件（layout 布局 / common 通用 / ErrorBoundary）
  api/            # API client 与各业务 API（FE-005）
  config/         # 环境配置读取入口
  features/       # 业务 feature 模块
  stores/         # Zustand Store（app/ui/simulation/topology/scenario，FE-006）
  types/          # 枚举 + 域对象 ViewModel（domain/）
  schemas/        # Zod 运行时校验（外部 DTO）
  adapters/       # DTO → ViewModel 适配（含赛题导入兼容）
  mocks/          # MSW Mock 系统（world/handlers/fixtures/random/realtime，FE-007）
  utils/          # 公共工具函数
  styles/         # 全局样式入口
  test/           # 测试工具（renderWithProviders / renderWithRouter / setup / factories）
  main.tsx        # 入口：StrictMode → ErrorBoundary → Providers → App

tests/            # 跨模块集成测试（后续填充）
```

路径别名：`@/*` → `src/*`。
