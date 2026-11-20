"""离线场景文件加载器：只读，文件缺失/异常不抛错，返回空映射。"""
from __future__ import annotations

import json
from pathlib import Path


def load_bg_category(path: str) -> dict[str, str]:
    """bg-service.json → {serviceId: category}。文件缺失/异常返回空 dict。"""
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    items = data if isinstance(data, list) else data.get("services", [])
    mapping: dict[str, str] = {}
    for item in items or []:
        sid = item.get("serviceId")
        cat = item.get("category")
        if sid and cat:
            mapping[str(sid)] = str(cat)
    return mapping


def load_candidate_paths(path: str) -> dict[str, list[dict]]:
    """service-paths.json → {serviceId: [{pathNo, nodes, links, metrics}]}。"""
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    result: dict[str, list[dict]] = {}
    for svc in data.get("services", []) or []:
        sid = svc.get("serviceId")
        if not sid:
            continue
        paths: list[dict] = []
        for pp in svc.get("paths", []) or []:
            paths.append(
                {
                    "pathNo": pp.get("pathNo"),
                    "nodes": pp.get("nodes", []),
                    "links": pp.get("links", []),
                    "metrics": pp.get("metrics", {}),
                }
            )
        result[str(sid)] = paths
    return result
