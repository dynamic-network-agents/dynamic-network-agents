"""链路质量代价：归一化 + 加权和。

归一化基准 = simulator/conf/linkTypes.json 的链路类型取值区间（权威源）。
- 时延/抖动/丢包/误码：正向指标（越小越好），(v - lo)/(hi - lo)；
- 带宽：反向指标（越大越好），(hi - v)/(hi - lo)；
- 越界值 clamp 到 [0,1]（链路劣化后参数可能超出类型静态区间）。

代价仅用于可行路径之间的排序，不用于 QoS 判定。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import networkx as nx

from common.modeling.models import Link, LinkParams
from common.modeling.path_qos import edge_data_by_link_id

# 默认代价权重（与 configs/qos.yaml 的 link_cost_weights 一致）
DEFAULT_WEIGHTS: dict[str, float] = {
    "delay": 0.4,
    "jitter": 0.15,
    "bandwidth": 0.25,
    "packet_loss": 0.1,
    "ber": 0.1,
}

# src/common/modeling/link_quality.py -> 项目根目录（上溯三级）
_REPO_ROOT = Path(__file__).resolve().parents[3]
_LINK_TYPES_FILE = _REPO_ROOT / "simulator" / "conf" / "linkTypes.json"


@lru_cache(maxsize=1)
def _type_ranges() -> dict[str, dict[str, tuple[float, float]]]:
    """链路类型 -> {指标 -> (lo, hi)}，读一次并缓存。"""
    with _LINK_TYPES_FILE.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    out: dict[str, dict[str, tuple[float, float]]] = {}
    for t in raw["types"]:
        out[t["id"]] = {
            "delayMs": (float(t["delayMs"][0]), float(t["delayMs"][1])),
            "jitterMs": (float(t["jitterMs"][0]), float(t["jitterMs"][1])),
            "bandwidthBps": (float(t["bandwidthBps"][0]), float(t["bandwidthBps"][1])),
            "ber": (float(t["ber"][0]), float(t["ber"][1])),
            "packetLossRate": (float(t["packetLossRate"][0]), float(t["packetLossRate"][1])),
        }
    return out


def _normalize(value: float, lo: float, hi: float) -> float:
    """正向指标归一化到 [0,1]，越界 clamp。"""
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def _normalize_bandwidth(value: float, lo: float, hi: float) -> float:
    """带宽反向指标归一化：值越大代价越低。"""
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (hi - value) / (hi - lo)))


def _cost(link_type: str, params: LinkParams | None, weights: dict[str, float]) -> float:
    r = _type_ranges().get(link_type)
    if r is None or params is None:
        return 1.0  # 未知类型 / 缺参数 → 最大代价（惩罚）
    d = _normalize(params.delay_ms, *r["delayMs"])
    j = _normalize(params.jitter_ms, *r["jitterMs"])
    b = _normalize_bandwidth(params.bandwidth_bps, *r["bandwidthBps"])
    p = _normalize(params.packet_loss_rate, *r["packetLossRate"])
    e = _normalize(params.ber, *r["ber"])
    return (weights.get("delay", 0.0) * d
            + weights.get("jitter", 0.0) * j
            + weights.get("bandwidth", 0.0) * b
            + weights.get("packet_loss", 0.0) * p
            + weights.get("ber", 0.0) * e)


def link_cost(link: Link, weights: dict[str, float] | None = None) -> float:
    """单条链路的综合代价（0~1，越小越好）。"""
    return _cost(link.link_type, link.params, weights or DEFAULT_WEIGHTS)


def path_cost(
    link_ids: list[str],
    graph: nx.MultiGraph,
    weights: dict[str, float] | None = None,
) -> float:
    """一条路径的综合代价 = 逐跳 link_cost 累加。"""
    w = weights or DEFAULT_WEIGHTS
    total = 0.0
    for lid in link_ids:
        data = edge_data_by_link_id(graph, lid)
        params = LinkParams(
            delay_ms=data["delay_ms"],
            jitter_ms=data["jitter_ms"],
            bandwidth_bps=data["bandwidth_bps"],
            ber=data["ber"],
            packet_loss_rate=data["packet_loss_rate"],
        )
        total += _cost(data["link_type"], params, w)
    return total
