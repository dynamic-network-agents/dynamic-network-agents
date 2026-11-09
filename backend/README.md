# backend — 主业务后端 / API 集成层

FastAPI 服务，职责：Agent 生命周期、A2A 协同、任务调度、RAG、策略校验，并向 `simulator` / `agent-platform` / `algorithms` 编排调用。

- **定位**：管控面与数据面的集成枢纽；对外提供 REST + WebSocket，契约对齐 `contracts/`。
- **依赖**：`fastapi`、`uvicorn`；存储 SQLite、Redis 按需引入（阶段四）。
- **包名**：`backend`（目录 `backend/backend/`）；发布名 `dynamic-network-backend`。

## 测试

```bash
uv sync && uv run pytest backend/tests
```

## 结构（阶段四起填充）

```text
backend/
  backend/          # 包根（main / api / core / domain / services / integrations）
  tests/            # 单元与集成测试
  pyproject.toml
  README.md
```
