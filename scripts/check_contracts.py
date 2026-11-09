#!/usr/bin/env python3
"""校验 contracts/schemas/*.json 的 JSON Schema 语法与跨文件 $ref 可解析性。

对应拆分方案 §4.8 契约链的「机器契约」环节：先保证 Schema 本身合法、引用不悬空。
与前端 Zod 的字段级对比、OpenAPI 快照一致性检查，待 backend/simulator 有 FastAPI 服务后再补（阶段四/五）。

用法：`uv run python scripts/check_contracts.py`
依赖：jsonschema（根 `[tool.uv] dev-dependencies` 已含）。
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "contracts" / "schemas"


def load_schemas() -> dict[str, dict]:
    schemas: dict[str, dict] = {}
    for path in sorted(SCHEMA_DIR.glob("*.json")):
        try:
            schemas[path.name] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"[FAIL] {path.name}: 非法 JSON —— {exc}")
            raise SystemExit(1)
    return schemas


def iter_refs(node: object):
    """递归收集所有 $ref 字符串。"""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            yield ref
        for value in node.values():
            yield from iter_refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from iter_refs(item)


def resolve_pointer(document: object, fragment: str) -> bool:
    """校验 JSON Pointer（fragment 去掉前导 #）能否在 document 中解析。"""
    if fragment in ("", "#"):
        return True
    pointer = fragment.lstrip("#")
    if not pointer:
        return True
    current = document
    for raw_token in pointer.lstrip("/").split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                return False
            current = current[token]
        elif isinstance(current, list):
            try:
                current = current[int(token)]
            except (ValueError, IndexError):
                return False
        else:
            return False
    return True


def main() -> int:
    schemas = load_schemas()
    errors: list[str] = []

    for name, schema in schemas.items():
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:  # noqa: BLE001 —— 报告并继续，收集全部问题
            errors.append(f"{name}: Schema 语法校验失败 —— {exc}")
            continue

        for ref in iter_refs(schema):
            doc_part, _, fragment = ref.partition("#")
            if doc_part:
                target = schemas.get(doc_part)
                if target is None:
                    errors.append(f"{name}: 无法解析外部引用 {ref!r}（找不到 {doc_part!r}）")
                elif not resolve_pointer(target, fragment):
                    errors.append(f"{name}: 引用指针 {fragment!r} 在 {doc_part} 中不存在")
            elif not resolve_pointer(schema, fragment):
                errors.append(f"{name}: 内部引用指针 {fragment!r} 不存在")

    if errors:
        print("契约 Schema 校验失败：")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"OK：{len(schemas)} 个契约 Schema 语法合法、引用可解析。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
