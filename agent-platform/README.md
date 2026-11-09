# agent-platform — LLM 多智能体平台

多智能体运行时与协同编排：运维智能体（态势采集/拓扑感知/链路质量/异常检测/故障诊断/自愈建议）、资源控制智能体（资源调度/路由调整/带宽分配/QoS 保障），协调器统一编排与冲突仲裁。

- **模型**：Qwen3-4B/8B（Ollama），小参数量 + 低比特量化；向量检索 BGE-M3 + FAISS（按需引入）。
- **依赖**：当前仅 `pydantic`（DTO）；Ollama 客户端、RAG 依赖按需引入。
- **包名**：`agent_platform`（目录 `agent-platform/agent_platform/`）；发布名 `dynamic-network-agent-platform`。

## 测试

```bash
uv sync && uv run pytest agent-platform/tests
```
