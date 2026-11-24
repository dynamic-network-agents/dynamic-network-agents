"""只读安全回归（A-07）：写接口白名单 + 令牌不出前端。

约束来源：`work_bench/CLAUDE.md` 三条硬约束。
这个测试不连仿真器，只扫描源码，因此任何一次前端/后端改动都会立刻暴露越界。
"""
from __future__ import annotations

import re
from pathlib import Path

WORKBENCH = Path(__file__).resolve().parents[2]
FRONTEND_SRC = WORKBENCH / "frontend" / "src"
BACKEND = WORKBENCH / "backend"

FRONTEND_SUFFIXES = {".ts", ".tsx"}
SKIP_DIRS = {".venv", "__pycache__", "node_modules", "dist"}


def _iter_files(root: Path, suffixes: set[str]):
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        if SKIP_DIRS.intersection(path.parts):
            continue
        yield path


def _frontend_files():
    return list(_iter_files(FRONTEND_SRC, FRONTEND_SUFFIXES))


def _backend_files():
    return [
        p
        for p in _iter_files(BACKEND, {".py"})
        if "tests" not in p.parts  # 测试代码可以描述这些约束
    ]


def test_frontend_only_posts_to_repath():
    """前端只允许一个 POST（经工作台 /api/repath 转发），且必须在 api.ts。"""
    offenders = [
        str(p.relative_to(WORKBENCH))
        for p in _frontend_files()
        if re.search(r"""["']POST["']""", p.read_text(encoding="utf-8"))
    ]
    assert offenders == ["frontend/src/api.ts"], (
        "前端出现额外的 POST 调用（只读约束）：" + ", ".join(offenders)
    )


def test_frontend_never_calls_simulation_control():
    """禁止仿真控制写接口（启停/案例加载等），前端与后端都不该出现。"""
    pattern = re.compile(r"/simulation/(start|stop|reset)|/sdn-ui/start")
    hits = [
        str(p.relative_to(WORKBENCH))
        for p in [*_frontend_files(), *_backend_files()]
        if pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert hits == [], "出现了仿真控制接口调用：" + ", ".join(hits)


def test_backend_write_calls_are_whitelisted():
    """后端只有 set_service_path 一处写调用，且路径必须是 /services/{id}/path。"""
    writers = []
    for p in _backend_files():
        text = p.read_text(encoding="utf-8")
        if re.search(r"""_request\(\s*["']POST["']""", text):
            writers.append(p.name)
    assert writers == ["simulator_client.py"], f"后端写调用越界：{writers}"

    client = (BACKEND / "simulator_client.py").read_text(encoding="utf-8")
    assert 'f"/services/{service_id}/path"' in client
    assert client.count('"POST"') == 1, "simulator_client 出现多个 POST 调用"


def test_tokens_never_reach_frontend():
    """令牌只由后端读取：前端源码里不得出现令牌头或令牌字段名。"""
    forbidden = ("X-Ctrl-Token", "X-Open-Token", "ctrlToken", "openTokens", "LLM_API_KEY")
    hits = [
        f"{p.name}: {name}"
        for p in _frontend_files()
        for name in forbidden
        if name in p.read_text(encoding="utf-8")
    ]
    assert hits == [], "前端出现令牌痕迹：" + ", ".join(hits)


def test_repath_gate_is_enforced_by_backend():
    """写开关关闭时 /api/repath 必须 403（policy 层判定）。"""
    main = (BACKEND / "main.py").read_text(encoding="utf-8")
    policy = (BACKEND / "policy.py").read_text(encoding="utf-8")
    assert "policy.ensure_repath_allowed(config.ALLOW_REPATH)" in main
    assert "status_code=403" in main
    assert "WORKBENCH_ALLOW_REPATH" in policy
