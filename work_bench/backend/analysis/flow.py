"""Flow 聚合：把 Service 按"无序 IP 对"归到同一个路径控制对象。

依据（已核实）：仿真器 `flow_of_ips` 用 `(ip1,ip2) in ((a,b),(b,a))` 匹配，
所以源/目的对调属于同一个 flow；一次改路径同时改双向。

公开 API 不暴露 flow 表，因此这里用**推导 key**：`"<ipLo>|<ipHi>"`。
拿不到 IP 的业务归入 `unknown:<serviceId>`，不猜。
"""
from __future__ import annotations

from typing import Optional

from ..models import Flow
from .path import parse_path
from .qos import compose_qos


def _node_ip_map(nodes: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for node in nodes or []:
        nid = node.get("nodeId")
        ip = node.get("ip")
        if nid and ip:
            out[str(nid)] = str(ip)
    return out


def _flow_key(src_ip: Optional[str], dst_ip: Optional[str], sid: str) -> str:
    if src_ip and dst_ip:
        lo, hi = sorted((src_ip, dst_ip))
        return f"{lo}|{hi}"
    return f"unknown:{sid}"


def build_flows(
    services: list[dict],
    nodes: list[dict],
    links: list[dict],
) -> list[Flow]:
    ip_by_node = _node_ip_map(nodes)
    links_by_id = {str(l["linkId"]): l for l in links or [] if l.get("linkId")}

    groups: dict[str, list[dict]] = {}
    for svc in services or []:
        sid = svc.get("serviceId")
        if not sid:
            continue
        src = svc.get("srcNodeId")
        dst = svc.get("dstNodeId")
        src_ip = ip_by_node.get(str(src)) if src else None
        dst_ip = ip_by_node.get(str(dst)) if dst else None
        key = _flow_key(src_ip, dst_ip, str(sid))
        groups.setdefault(key, []).append(svc)

    flows: list[Flow] = []
    for key, members in groups.items():
        # 取一个有路径的成员作为代表（同一 flow 共享路径）
        rep = next(
            (m for m in members if ((m.get("path") or {}).get("segments") or [])),
            members[0],
        )
        src_node = rep.get("srcNodeId")
        dst_node = rep.get("dstNodeId")
        src_ip = ip_by_node.get(str(src_node)) if src_node else None
        dst_ip = ip_by_node.get(str(dst_node)) if dst_node else None
        parsed = parse_path(
            (rep.get("path") or {}).get("segments"),
            links_by_id,
            src_node,
            dst_node,
        )

        flow_links = [links_by_id[lid] for lid in parsed["links"] if lid in links_by_id]
        flow_static = compose_qos(flow_links) if (flow_links and not parsed["missing"]) else None

        categories: dict[str, int] = {}
        meet_true = meet_false = meet_unknown = 0
        static_ok = static_fail = static_unknown = 0
        for member in members:
            cat = str(member.get("category") or "unknown")
            categories[cat] = categories.get(cat, 0) + 1
            actual = member.get("actual") or {}
            q = actual.get("qosMeet")
            if q is True:
                meet_true += 1
            elif q is False:
                meet_false += 1
            else:
                meet_unknown += 1
            chk = (member.get("staticCheck") or {}).get("ok")
            if chk is True:
                static_ok += 1
            elif chk is False:
                static_fail += 1
            else:
                static_unknown += 1

        path_ids = {
            (m.get("path") or {}).get("pathId")
            for m in members
            if (m.get("path") or {}).get("pathId")
        }
        path_id = (rep.get("path") or {}).get("pathId") or (
            sorted(path_ids)[0] if path_ids else None
        )

        flows.append(
            Flow(
                flowKey=key,
                srcNodeId=src_node,
                dstNodeId=dst_node,
                srcIp=src_ip,
                dstIp=dst_ip,
                memberServiceIds=[str(m["serviceId"]) for m in members if m.get("serviceId")],
                memberCount=len(members),
                pathId=path_id,
                links=parsed["links"],
                nodes=parsed["nodes"],
                pathContinuous=parsed["continuous"],
                direction=parsed["direction"],
                missingLinks=parsed["missing"],
                categoryCounts=categories,
                qosMeetTrue=meet_true,
                qosMeetFalse=meet_false,
                qosMeetUnknown=meet_unknown,
                staticQoS=flow_static,
                staticOkCount=static_ok,
                staticFailCount=static_fail,
                staticUnknownCount=static_unknown,
            )
        )

    flows.sort(key=lambda f: f.flowKey)
    return flows


def flow_key_for(src_ip: Optional[str], dst_ip: Optional[str], service_id: str) -> str:
    """供测试/调试使用：暴露推导规则。"""
    return _flow_key(src_ip, dst_ip, service_id)

