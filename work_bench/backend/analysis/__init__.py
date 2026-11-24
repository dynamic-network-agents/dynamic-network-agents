"""本地分析层：flow 聚合、路径解析、静态 QoS、链路负载、风险判定、候选可行性（不依赖 Agent `src/`）。"""
from .candidates import build_flow_candidates
from .flow import build_flows, flow_key_for
from .load import build_link_loads
from .path import parse_path
from .qos import METRICS, check_static, compose_qos
from .risk import build_link_risks, build_overall_status, build_risk_summary

__all__ = [
    "METRICS",
    "build_flow_candidates",
    "build_flows",
    "build_link_loads",
    "build_link_risks",
    "build_overall_status",
    "build_risk_summary",
    "check_static",
    "compose_qos",
    "flow_key_for",
    "parse_path",
]
