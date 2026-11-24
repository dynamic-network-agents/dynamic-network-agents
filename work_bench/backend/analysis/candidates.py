"""Flow 候选路径的静态可行性（离线候选 × 当前链路参数）。

为什么要重算：`service-paths.json` 里的 `metrics` 是**场景生成期**的估算，
运行中链路参数会被事件改写，所以静态合成必须用当前 `/links` 参数重算。

口径：
- 候选路径只来自离线文件（公开 API 不提供候选路径生成），缺失时明确写"无候选数据"；
- 一条候选对同一 Flow 的每个成员业务分别校验（各成员需求可能不同），汇总 ok/fail/unknown；
- 候选链路不全（不在当前 /links）时不做部分合成，`staticQoS=None` 且全部计 unknown；
- `isCurrent` 只表示与该 Flow 当前路径链路集合相同（顺序不敏感）。
"""
from __future__ import annotations

from typing import Optional

from .qos import check_static, compose_qos

SOURCE = "offline:service-paths.json"


def _link_ids(candidate: dict) -> list[str]:
    return [str(x) for x in (candidate.get("links") or []) if x]


def _dedupe_key(links: list[str]) -> tuple[str, ...]:
    return tuple(links)


def build_flow_candidates(
    flow: dict,
    services: list[dict],
    links: list[dict],
    candidate_paths: dict[str, list[dict]],
) -> dict:
    """返回该 Flow 的候选路径及其静态可行性（纯函数，便于单测）。"""
    member_ids = [str(x) for x in (flow.get("memberServiceIds") or [])]
    by_id = {str(s.get("serviceId")): s for s in services or [] if s.get("serviceId")}
    members = [by_id[sid] for sid in member_ids if sid in by_id]
    links_by_id = {str(l.get("linkId")): l for l in links or [] if l.get("linkId")}
    current = set(str(x) for x in (flow.get("links") or []))

    groups: dict[tuple[str, ...], dict] = {}
    for member in members:
        sid = str(member.get("serviceId"))
        for cand in candidate_paths.get(sid) or []:
            links_of_candidate = _link_ids(cand)
            if not links_of_candidate:
                continue
            key = _dedupe_key(links_of_candidate)
            entry = groups.get(key)
            if entry is None:
                entry = {
                    "links": links_of_candidate,
                    "nodes": [str(n) for n in (cand.get("nodes") or [])],
                    "pathNo": cand.get("pathNo"),
                    "serviceIds": [],
                }
                groups[key] = entry
            if sid not in entry["serviceIds"]:
                entry["serviceIds"].append(sid)

    candidates: list[dict] = []
    for key, entry in groups.items():
        cand_links = entry["links"]
        missing = [lid for lid in cand_links if lid not in links_by_id]
        link_objs = [links_by_id[lid] for lid in cand_links if lid in links_by_id]

        if missing:
            qos: Optional[dict] = None
            per_member = [
                {
                    "serviceId": sid,
                    "ok": None,
                    "violations": [f"链路不在当前 /links：{', '.join(missing)}"],
                }
                for sid in entry["serviceIds"]
            ]
        else:
            qos = compose_qos(link_objs)
            per_member = []
            for sid in entry["serviceIds"]:
                member = by_id.get(sid) or {}
                check = check_static(qos, member.get("requirement"))
                per_member.append(
                    {"serviceId": sid, "ok": check["ok"], "violations": check["violations"]}
                )

        checks = {"ok": 0, "fail": 0, "unknown": 0}
        for item in per_member:
            if item["ok"] is True:
                checks["ok"] += 1
            elif item["ok"] is False:
                checks["fail"] += 1
            else:
                checks["unknown"] += 1

        candidates.append(
            {
                "links": cand_links,
                "nodes": entry["nodes"],
                "linkCount": len(cand_links),
                "pathNo": entry["pathNo"],
                "serviceIds": entry["serviceIds"],
                "missingLinks": missing,
                "isCurrent": set(cand_links) == current and bool(current),
                "staticQoS": qos,
                "checks": checks,
                "perMember": per_member,
            }
        )

    # 当前路径优先；其次按「不可行最少 → 未知最少 → 链路最短」排序
    candidates.sort(
        key=lambda c: (
            not c["isCurrent"],
            c["checks"]["fail"],
            c["checks"]["unknown"],
            c["linkCount"],
            str(c["pathNo"]),
        )
    )
    for index, cand in enumerate(candidates, start=1):
        cand["candidateId"] = f"C{index:02d}"

    note: Optional[str] = None
    if not candidates:
        if not candidate_paths:
            note = "未加载离线候选路径（SERVICE_PATHS_PATH 未配置或文件不存在）"
        else:
            note = "该 Flow 的成员业务没有候选路径记录（离线文件里缺这些业务）"

    return {
        "flowKey": flow.get("flowKey"),
        "source": SOURCE,
        "memberCount": len(members),
        "currentLinks": [str(x) for x in (flow.get("links") or [])],
        "candidates": candidates,
        "note": note,
    }
