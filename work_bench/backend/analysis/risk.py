"""链路风险（规则 A）与整体状态（规则 B）。

口径来源：`docs/work_bench/B03_Network_Workbench_UI_可行性分析.md` §8。

规则 A（风险链路，计入计数）：
- R1 断：`link.status == "down"`；
- R2 超订：`demandUtilization > 1.0` 且容量 > 0（**需求侧估算**，不是实测吞吐）；
- R3 劣化：相对上一次成功快照，`delayMs` 涨幅 ≥ 50% 或 `packetLossRate` 绝对涨幅 ≥ 0.01；
- R4 承压不在这里算（只进热点排序），避免与"业务不达标"重复计数。

规则 B（整体状态）：
- `health != "live"` → unknown；
- 有 R1，或 `qosMeet == false` 业务占比 > 30% → critical（异常）；
- 有任一风险链路，或有 `qosMeet == false` 业务 → alarm（告警）；
- 否则 normal（正常）。

本模块是纯函数：不发起网络请求、不读写文件，便于单测与复算。
"""
from __future__ import annotations

from typing import Optional

# 阈值是初值，待运行期调；集中在此便于一处修改。
R3_DELAY_RISE = 0.5
R3_LOSS_RISE = 0.01
CRITICAL_BAD_RATIO = 0.30

SEVERITY_ORDER = ("R1", "R3", "R2")

STATUS_UNKNOWN = "unknown"
STATUS_CRITICAL = "critical"
STATUS_ALARM = "alarm"
STATUS_NORMAL = "normal"


def _num(value) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_dict(item) -> dict:
    """同时接受 pydantic 模型与 dict（快照内两种形态都会出现）。"""
    if item is None:
        return {}
    if isinstance(item, dict):
        return item
    dump = getattr(item, "model_dump", None)
    return dump() if callable(dump) else {}


def _degradation_reason(link: dict, prev_params: dict) -> Optional[str]:
    """R3：返回劣化描述；不满足或无法比较时返回 None。"""
    cur = _as_dict(link.get("params"))
    if not prev_params:
        return None
    parts: list[str] = []

    cur_delay = _num(cur.get("delayMs"))
    prev_delay = _num(prev_params.get("delayMs"))
    if cur_delay is not None and prev_delay is not None and prev_delay > 0:
        rise = (cur_delay - prev_delay) / prev_delay
        if rise >= R3_DELAY_RISE:
            parts.append(
                f"时延 {prev_delay:g}→{cur_delay:g}ms（+{rise * 100:.0f}%）"
            )

    cur_loss = _num(cur.get("packetLossRate"))
    prev_loss = _num(prev_params.get("packetLossRate"))
    if cur_loss is not None and prev_loss is not None:
        rise = cur_loss - prev_loss
        if rise >= R3_LOSS_RISE:
            parts.append(
                f"丢包 {prev_loss:.4f}→{cur_loss:.4f}（+{rise * 100:.2f}pp）"
            )

    return "；".join(parts) if parts else None


def build_link_risks(
    links: list[dict],
    link_loads: list[dict],
    prev_links: list[dict],
) -> list[dict]:
    """按规则 A 计算风险链路；返回按严重度（R1 > R3 > R2）再按 linkId 排序的列表。"""
    loads: dict[str, dict] = {}
    for load in link_loads or []:
        item = _as_dict(load)
        if item.get("linkId"):
            loads[str(item["linkId"])] = item
    prev: dict[str, dict] = {}
    for link in prev_links or []:
        item = _as_dict(link)
        if item.get("linkId"):
            prev[str(item["linkId"])] = _as_dict(item.get("params"))

    out: list[dict] = []
    for link in links or []:
        link = _as_dict(link)
        link_id = link.get("linkId")
        if not link_id:
            continue
        link_id = str(link_id)
        codes: list[str] = []
        reasons: list[str] = []

        if str(link.get("status") or "").strip().lower() == "down":
            codes.append("R1")
            reasons.append("链路断开（status=down）")

        load = _as_dict(loads.get(link_id))
        util = _num(load.get("demandUtilization"))
        capacity = _num(load.get("capacityBps"))
        if util is not None and capacity is not None and capacity > 0 and util > 1.0:
            codes.append("R2")
            reasons.append(f"需求/容量 {util:.2f}（需求侧估算，非实测吞吐）")

        degraded = _degradation_reason(link, prev.get(link_id) or {})
        if degraded:
            codes.append("R3")
            reasons.append(degraded)

        if not codes:
            continue

        severity = next(code for code in SEVERITY_ORDER if code in codes)
        out.append(
            {
                "linkId": link_id,
                "codes": codes,
                "severity": severity,
                "reasons": reasons,
                "isEstimated": "R2" in codes,
            }
        )

    out.sort(key=lambda item: (SEVERITY_ORDER.index(item["severity"]), item["linkId"]))
    return out


def build_risk_summary(
    risks: list[dict], links_ok: bool, health: str
) -> dict:
    """风险汇总。数据不可信时 `unknown=True` 且 `total=None`，不得显示成 0。"""
    by_code = {code: 0 for code in SEVERITY_ORDER}
    for risk in risks or []:
        for code in risk.get("codes") or []:
            if code in by_code:
                by_code[code] += 1
    unknown = not links_ok or health != "live"
    return {
        "total": None if unknown else len(risks or []),
        "byCode": by_code,
        "unknown": unknown,
        "note": None
        if not unknown
        else ("链路数据不可用" if not links_ok else f"数据健康为 {health}"),
    }


def build_overall_status(
    health: str, risks: list[dict], services: list[dict]
) -> dict:
    """按规则 B 计算整体状态，并给出可读的触发理由。"""
    if health != "live":
        return {
            "status": STATUS_UNKNOWN,
            "reasons": [f"数据健康为 {health}，暂不判定整体状态"],
        }

    judged = 0
    bad = 0
    for service in services or []:
        service = _as_dict(service)
        actual = _as_dict(service.get("actual"))
        meet = actual.get("qosMeet")
        if meet is None:
            continue
        judged += 1
        if meet is False:
            bad += 1

    ratio = (bad / judged) if judged else 0.0
    has_r1 = any("R1" in (risk.get("codes") or []) for risk in risks or [])

    reasons: list[str] = []
    if has_r1:
        reasons.append("存在断开的链路")
    if judged:
        reasons.append(f"{bad}/{judged} 业务 QoS 不达标")
    if risks:
        reasons.append(f"{len(risks)} 条风险链路")

    if has_r1 or (judged and ratio > CRITICAL_BAD_RATIO):
        return {"status": STATUS_CRITICAL, "reasons": reasons}

    if risks or bad > 0:
        return {"status": STATUS_ALARM, "reasons": reasons}

    return {"status": STATUS_NORMAL, "reasons": ["无风险链路，业务全部达标"]}
