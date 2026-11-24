"""路径解析：把 `segments`（只有 link 元素）还原成有序链路与节点链。

口径（已核实）：
- `path.segments` 只有 `{type:"link", id, auto?}`，从不含 node 元素；
- 顺序取决于最近一次下发方向：可能相对该业务的 src→dst 是反的；
- 链路可能被删除/切除而暂时不在 `/links` 里，需标 `missing`，不能静默丢弃。
"""
from __future__ import annotations

from typing import Any, Optional


def _chain(ordered_links: list[dict]) -> tuple[list[str], bool]:
    """按给定顺序把链路串成节点序列；不连续立即返回。"""
    if not ordered_links:
        return [], True
    nodes = [str(ordered_links[0].get("srcNodeId")), str(ordered_links[0].get("dstNodeId"))]
    for link in ordered_links[1:]:
        a = str(link.get("srcNodeId"))
        b = str(link.get("dstNodeId"))
        if a == nodes[-1]:
            nodes.append(b)
        elif b == nodes[-1]:
            nodes.append(a)
        else:
            return nodes, False
    return nodes, True


def parse_path(
    segments: list[dict] | None,
    links_by_id: dict[str, dict],
    src_node: Optional[str] = None,
    dst_node: Optional[str] = None,
) -> dict[str, Any]:
    """返回 {links, nodes, continuous, direction, missing}。

    - `continuous=None` 表示没有路径数据（不是"不连续"）；
    - `direction` 只在连续且有 src/dst 时判定：forward / reverse / unknown；
    - `nodes` 已按 src→dst 方向归一（reverse 时反转）。
    """
    ids: list[str] = []
    for seg in segments or []:
        if isinstance(seg, dict) and seg.get("type") == "link" and seg.get("id"):
            ids.append(str(seg["id"]))
    if not ids:
        return {"links": [], "nodes": [], "continuous": None, "direction": None, "missing": []}

    missing = [lid for lid in ids if lid not in links_by_id]
    ordered = [links_by_id[lid] for lid in ids if lid in links_by_id]
    if not ordered:
        return {
            "links": ids,
            "nodes": [],
            "continuous": False,
            "direction": None,
            "missing": missing,
        }

    nodes, continuous = _chain(ordered)
    used = ordered
    reversed_order = False
    if not continuous and len(ordered) > 1:
        # 下发的 segments 可能是反序的（取决于最近一次下发方向），反序再试一次
        nodes2, continuous2 = _chain(list(reversed(ordered)))
        if continuous2:
            nodes, continuous = nodes2, True
            used = list(reversed(ordered))
            reversed_order = True

    direction: Optional[str] = None
    if continuous and nodes and src_node and dst_node:
        if nodes[0] == str(src_node) and nodes[-1] == str(dst_node):
            direction = "reverse" if reversed_order else "forward"
        elif nodes[0] == str(dst_node) and nodes[-1] == str(src_node):
            # 链路内部方向整体是反的；归一成 src→dst 再判定
            nodes = list(reversed(nodes))
            used = list(reversed(used))
            direction = "forward" if reversed_order else "reverse"
        else:
            direction = "unknown"

    return {
        "links": [str(link.get("linkId")) for link in used],
        "nodes": nodes,
        "continuous": continuous,
        "direction": direction,
        "missing": missing,
    }
