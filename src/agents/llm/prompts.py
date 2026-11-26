"""提示词模板：两类智能体的系统提示与任务提示。

**设计原则**：

1. **不诱导生成链路**。提示词里明确要求模型**只输出优先级建议 / 诊断结论 / 解读文本**，
   路径由确定性算法产出——模型提路径会被下游忽略，还白白消耗预算。
2. **输出结构化**。要求 JSON 输出并给出字段说明，便于 `parse_json_object` 解析；
   解析失败走确定性兜底，不阻塞闭环。
3. **上下文最小化**。只喂必要的观测（受影响的 flow、链路质量、实测 QoS），
   不把整个拓扑塞进提示词——省 token 也降幻觉。
4. **同输入同提示词**。模板渲染是纯函数，便于复现。
"""
from __future__ import annotations

import json
from typing import Any

# —— 运维智能体 ——
OPS_SYSTEM = """你是通信网络运维智能体，负责态势采集、拓扑感知、链路质量评估、异常事件检测、故障诊断与自愈建议生成。
只输出 JSON，不要输出链路路径或具体路由方案——路径由下游确定性算法负责。
输出格式：{"anomalies":[{"target":"...","type":"link_down|link_degraded|service_violation","evidence":"...","severity":"high|medium|low"}],
"diagnosis":{"cause":"...","confidence":0.0,"affected_flows":["..."]},
"healing_advice":["..."]}"""

DIAGNOSIS_PROMPT = """仿真环境检测到以下受影响对象，请诊断原因并给出自愈建议。

受影响 flow 与现状：
{context}

最近的事件：
{events}

请给出：异常清单（逐个对象）、根因判断（含置信度）、自愈建议列表。
只输出 JSON。"""

# —— 资源控制智能体 ——
CONTROL_SYSTEM = """你是通信网络资源控制智能体，负责资源调度、路由动态调整、带宽分配与业务 QoS 保障。
你可以调整业务的优先级排序，但**不要输出具体链路路径**——路径由下游确定性算法在候选集中选择。
输出格式：{"priority_hints":[{"service_id":"...","suggested_priority":1,"reason":"..."}],
"summary":"面向人的一句话态势解读"}"""

PRIORITY_PROMPT = """当前有若干业务需要争用有限带宽，请依据业务类型与保障重要性给出优先级排序建议。

业务清单（service_id / 类型 / 优先级 / 需求带宽 / 是否 test）：
{businesses}

当前预测达标情况：{compliance}

请输出 priority_hints（只对建议调整的业务给出）与 summary。
只输出 JSON。"""

EXPLANATION_PROMPT = """请用不超过 5 句话，向非专业的评审说明当前网络发生了什么、采取了什么措施、效果如何。

本轮观测：
{context}

本轮动作：
{actions}

实测与预测：
{outcome}

请给出简洁的中文解读，不要输出 JSON。"""


def render(template: str, **kwargs: Any) -> str:
    """渲染模板（占位符缺失时留空串，不抛异常——避免因提示词拼装错误中断闭环）。"""
    return template.format(**{k: kwargs.get(k, "") for k in _placeholders(template)})


def _placeholders(template: str) -> list[str]:
    import string
    return [name for _, name, _, _ in string.Formatter().parse(template) if name]


def render_json_context(payload: Any, *, max_chars: int = 4000) -> str:
    """把上下文对象渲染成紧凑 JSON 文本（超长则截断，防提示词爆掉）。"""
    text = json.dumps(payload, ensure_ascii=False, default=str, indent=None)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...(truncated)"
