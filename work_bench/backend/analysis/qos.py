"""静态路径 QoS 合成与可行性判定。

公式（与主项目一致，独立实现 + 对拍测试）：
- 时延 D = Σ delayMs
- 抖动 J = √Σ jitterMs²
- 带宽 B = min bandwidthBps
- 丢包 L = 1 − ∏(1 − packetLossRate)
- 误码 E ≈ Σ ber

容差：时延 +1.0ms、抖动/丢包 +1e-9、误码 +1e-12、带宽无容差。
注意：这是"提交路径时的静态校验"口径，不是实测 `qosMeet`。
"""
from __future__ import annotations

import math
from typing import Optional

TOLERANCE = {
    "delayMs": 1.0,
    "jitterMs": 1e-9,
    "packetLossRate": 1e-9,
    "ber": 1e-12,
    "bandwidthBps": 0.0,
}

METRICS = ("delayMs", "jitterMs", "bandwidthBps", "packetLossRate", "ber")


def compose_qos(links: list[dict]) -> dict:
    """把路径上的链路参数合成为静态 QoS；缺参数时对应指标为 None。"""
    params = [link.get("params") or {} for link in links]
    missing: list[str] = []
    if not links:
        missing.append("no-links")

    def values(key: str) -> Optional[list[float]]:
        if not params:
            return None
        out: list[float] = []
        for p in params:
            v = p.get(key)
            if v is None:
                if key not in missing:
                    missing.append(key)
                return None
            out.append(float(v))
        return out

    delay = values("delayMs")
    jitter = values("jitterMs")
    bw = values("bandwidthBps")
    loss = values("packetLossRate")
    ber = values("ber")

    composed = {
        "linkCount": len(links),
        "delayMs": sum(delay) if delay is not None else None,
        "jitterMs": math.sqrt(sum(v * v for v in jitter)) if jitter is not None else None,
        "bandwidthBps": min(bw) if bw is not None else None,
        "packetLossRate": (
            min(1.0, max(0.0, 1.0 - math.prod(1.0 - v for v in loss)))
            if loss is not None
            else None
        ),
        "ber": sum(ber) if ber is not None else None,
        "missingParams": missing,
    }
    return composed


def check_static(composed: dict, requirement: Optional[dict]) -> dict:
    """静态可行性：逐项比较（带宽为下限，其余为上限），返回 ok/items/violations。"""
    if not requirement:
        return {"ok": None, "violations": ["无 QoS 需求"], "items": []}

    items = []
    violations = []
    unknown = False
    for metric in METRICS:
        req = requirement.get(metric)
        act = composed.get(metric)
        if req is None:
            items.append({"metric": metric, "required": None, "actual": act, "ok": None, "note": "需求未给出"})
            continue
        if act is None:
            unknown = True
            items.append(
                {"metric": metric, "required": float(req), "actual": None, "ok": None, "note": "缺链路参数"}
            )
            continue
        if metric == "bandwidthBps":
            ok = act >= float(req)
            note = "带宽下限"
        else:
            ok = act <= float(req) + TOLERANCE[metric]
            note = f"容差 +{TOLERANCE[metric]:g}"
        items.append({"metric": metric, "required": float(req), "actual": act, "ok": ok, "note": note})
        if not ok:
            violations.append(f"{metric}: 静态 {act:g} 不满足需求 {req:g}（{note}）")

    if violations:
        ok_all: Optional[bool] = False
    elif unknown:
        ok_all = None
    else:
        ok_all = True
    return {"ok": ok_all, "violations": violations, "items": items}
