# AGENTS.md

本文件为 **frontend 前端模块**的工作准则，供 Codex 在本目录及子目录工作时遵循。项目级通用规则见仓库根目录 `AGENTS.md`；两者冲突时以本文件（更具体）为准。

> 本文件与同目录 `CLAUDE.md` 描述同一套模块约定：Codex 读取 `AGENTS.md`，Claude Code 读取
> `CLAUDE.md`。两者应保持一致，改动时同步更新。

## 模块定位

通信网络资源管控多智能体系统的前端工作台，承载场景配置、仿真控制、网络拓扑可视化、Agent 协同与 QoS 监控、实验分析等页面。前端只消费稳定契约，不重复定义字段与接口。

- **模块边界**：执行 frontend 任务时只允许改动 `frontend/`，不得修改 `backend/`、agents、algorithms 等其他模块代码；反之亦然。

## 技术栈与版本约束

- 框架：React **18** + TypeScript + Vite（**用 React 18 而非 19**，与 Ant Design v5 官方兼容）
- 包管理器：pnpm（`packageManager` 字段锁定）
- 运行环境：Node >= 20（`.nvmrc` 固定 20 LTS）
- 规划库（**按需引入，不提前预装**）：Ant Design、AntV G6、ECharts、React Router、Zustand、Axios、MSW、React Hook Form + Zod（可选）
- 测试：Vitest + React Testing Library + MSW + Playwright

## 目录结构（路径别名 `@/*` → `src/*`）

```text
src/
  app/            # App、Providers、路由（pageMeta 单一来源 / routes / router）
  pages/          # 路由页面（dashboard/topology/scenario/simulation/agents/resources/experiments/not-found）
  api/            # API client 与各业务 API
  features/       # 业务 feature 模块（scenario/simulation/topology/agents/resources/experiments）
  components/     # 通用组件（layout/topology/charts/common）
  stores/         # Zustand Store
  types/          # 枚举 + 域对象 ViewModel（domain/）
  schemas/        # Zod 运行时校验（外部 DTO）
  adapters/       # DTO → ViewModel 适配（含赛题导入兼容）
  mocks/          # MSW Mock
  utils/          # 公共工具
  config/         # 环境配置读取入口
  styles/         # 全局样式
  test/           # 测试工具（renderWithProviders / renderWithRouter / setup / factories）
tests/
  integration/    # 跨模块集成测试
  e2e/            # 浏览器级流程
```

- 单元/组件测试与组件同目录；跨模块集成测试放 `tests/integration`；浏览器级流程放 `tests/e2e`。

## 工程命令

| 命令 | 说明 |
|---|---|
| `cd frontend` | 进入前端目录下 |
| `pnpm install` | 安装依赖 |
| `pnpm dev` | 启动开发服务器 |
| `pnpm build` | 类型检查 + 生产构建 |
| `pnpm typecheck` | TypeScript 类型检查 |
| `pnpm lint` | ESLint 静态检查 |
| `pnpm format` / `pnpm format:check` | Prettier 格式化（写入/校验） |
| `pnpm test` | Vitest 单元/组件测试 |
| `pnpm coverage` | 测试 + 覆盖率报告（含阈值检查） |

## 环境变量规则

- 分层文件 `.env.development` / `.env.test` / `.env.production`，模板 `.env.example`。
- 业务代码一律经 `src/config/env.ts` 的 `getEnvConfig()` 读取，**禁止散落 `import.meta.env`**。
- 缺少必要配置时抛可读错误，不允许白屏。

## 代码与数据约定

- 数据模型与接口以 `docs/frontend/前后端数据模型与接口规范_v1.0.md` 为**唯一事实源**；设计稿只做页面/交互，页面/组件不重复定义字段与接口。
- 控制链路与数据链路按独立 `linkId` / `linkPlane`（CONTROL/DATA）表达，**不根据节点对推导不存在的链路**。
- 仿真时间统一为 `simTimeMs`；墙上时钟用 `timestamp`。
- 字段 `camelCase`、枚举大写、`linkType` 小写自由格式（以接口规范为准）。
- 测试环境统一 `jsdom`；组件测试用 `src/test/renderWithProviders.tsx` 的 `renderWithProviders`；测试数据工厂用 `src/test/factories.ts` 的 `createFactory`；覆盖率阈值 80%（`pnpm coverage`）。

## 设计原则（coding 规则）

遵循经典设计原则（SOLID + 组合优于继承 + 迪米特法则，原则本体见根目录 `AGENTS.md`）。落地到 React + TypeScript：

- **单一职责（SRP）**：一个组件/hook/store/适配器只做一件事；组件过大或职责混杂时拆成子组件或自定义 hook；一个 Store 只管理一个领域的状态。
- **开闭原则（OCP）**：通过 props、组合、自定义 hook、适配器/策略扩展能力，避免在一处堆满 `if/switch` 分支；新增 DTO 类型时新增适配器，而非改动既有适配器。
- **里氏替换（LSP）**：组件与函数通过 props/接口契约协作，替换实现不破坏行为；Mock 与真实 API、不同 Provider 实现同一接口可互换。
- **接口隔离（ISP）**：类型/接口小而专一；组件 props 只暴露所需字段（必要时用 `Pick`/`Omit`），不把整个大对象层层下传。
- **依赖倒置（DIP）**：组件不直接依赖 Axios/具体服务，经 `api/` 模块或注入的客户端访问数据；页面消费稳定 ViewModel，不依赖服务端原始 DTO 字段。
- **合成复用（CRP）**：优先组合组件、HOC、自定义 hook 复用逻辑，避免类继承（React 函数组件天然倾向组合）。
- **迪米特法则（LoD）**：组件只与自己的 props/store/context 交互，不深挖嵌套对象；用 selector 取所需的最小状态切片，避免 `a.b.c.d` 式取用。

## Skill 引用约定

> `.claude/skills/` 为 Claude Code 专用 skill 目录；Codex 按自身 skill 机制处理（以当前会话「可用 skill」列表为准），不读取本目录的 Claude skill。

本模块在 `.claude/skills/` 下有前端相关 Claude skill。这些 skill 不会自动触发，Claude Code 需按本约定在对应任务中显式调用后再动手：

| Skill | 触发时机 |
|---|---|
| `frontend-design` | 新建页面/组件或改造既有 UI 的视觉设计（配色、字体、布局方向）时 |
| `vercel-react-best-practices` | 编写、审查或重构 React 组件、数据获取、打包与性能优化时 |
| `web-design-guidelines` | 审查 UI 代码的可访问性 / UX / Web 规范符合度时 |
| `api-contract-forge` | 从接口规范 / JSON 生成前端类型、构建或校验 API 契约时（FE-005 及后续） |
| `dataviz` | 创建任何图表 / 网络拓扑 / 仪表盘 / KPI 面板等可视化时（先读，再写第一行图表代码） |

- 其余非前端专用 Claude skill（如 `handoff` 会话交接、`grilling` 方案拷问）按需手动调用，不在本约定内。

## Task 执行与版本记录

- 任务以 **FE-xxx** 编号，归属 M0–M5 里程碑与 P0/P1/P2 优先级；**一个 Task 对应一个可验收结果**。
- 功能代码与对应单元/集成测试**同一 PR 提交**；PR 描述含 Task ID、功能说明、测试命令/结果、截图（适用时）、接口变更。
- 单步、调速、策略审批、事件补发等**未确认能力用 feature flag**，不假设后端支持。
- 每次大的代码改动在 `version/` 目录新增 `FE-xxx.md` 版本记录（日期、改动点、功能描述）。
- 每次 coding 任务先拆分子任务、列出任务描述，经用户确认后再开始；不确定的点或可选方案先提出，不自行决定；涉及前端设计（配色、布局、交互范式、文案风格等）风格不一致的点，先找用户确认。

## 文档约定

- 前端文档扁平存放、v1.0 为当前版；改内容改 `.md`，不回填 `.html`。
