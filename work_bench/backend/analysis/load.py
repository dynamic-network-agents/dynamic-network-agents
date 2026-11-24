"""链路需求侧负载聚合（E-03）。

口径：
- flowCount / serviceCount：经过该链路的 Flow / 业务数（竞争者数量，不等于负载）；
- demandBps：经过该链路的业务 `requirement.bandwidthBps` 之和（需求侧）；
- capacityBps：链路当前带宽；
- demandUtilization = demandBps / capacityBps；
- measuredBps：业务 `actual.effBwBps` 汇总，**只是估计**（业务级收包速率，不是链路吞吐）。
"""
from __future__ import annotations

from typing import Optional


def build_link_loads(links: list[dict], flows: list, services: list[dict]) -> list[dict]:
    service_by_id = {str(s["serviceId"]): s for s in services or [] if s.get("serviceId")}
    acc: dict[str, dict] = {}
    for link in links or []:
        lid = link.get("linkId")
        if not lid:
            continue
        acc[str(lid)] = {
            "flows": set(),
            "services": set(),
            "demand": 0.0,
            "measured": 0.0,
            "hasMeasured": False,
        }

    for flow in flows or []:
        for lid in getattr(flow, "links", []) or []:
            rec = acc.get(str(lid))
            if rec is None:
                continue
            rec["flows"].add(flow.flowKey)
            for sid in getattr(flow, "memberServiceIds", []) or []:
                svc = service_by_id.get(str(sid))
                if svc is None:
                    continue
                rec["services"].add(str(sid))
                req = svc.get("requirement") or {}
                if req.get("bandwidthBps") is not None:
                    rec["demand"] += float(req["bandwidthBps"])
                act = svc.get("actual") or {}
                if act.get("effBwBps") is not None:
                    rec["measured"] += float(act["effBwBps"])
                    rec["hasMeasured"] = True

    out: list[dict] = []
    for link in links or []:
        lid = str(link.get("linkId"))
        rec = acc.get(lid)
        if rec is None:
            continue
        capacity: Optional[float] = (link.get("params") or {}).get("bandwidthBps")
        capacity = float(capacity) if capacity is not None else None
        demand = rec["demand"]
        util = (demand / capacity) if capacity else None
        out.append(
            {
                "linkId": lid,
                "flowCount": len(rec["flows"]),
                "serviceCount": len(rec["services"]),
                "demandBps": demand,
                "capacityBps": capacity,
                "demandUtilization": util,
                "measuredBps": rec["measured"] if rec["hasMeasured"] else None,
                "measuredIsEstimate": True,
                "flowKeys": sorted(rec["flows"]),
            }
        )
    out.sort(key=lambda x: (x["demandUtilization"] is None, -(x["demandUtilization"] or 0)))
    return out
