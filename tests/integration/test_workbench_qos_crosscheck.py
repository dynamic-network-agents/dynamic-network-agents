"""对拍测试：workbench 静态 QoS vs 主项目 `src/math_modeling`。

目的：workbench 独立实现（不 import `src/`），但公式与容差必须与主项目一致；
两边用同一组 golden case，结果逐项相等、可行性判定一致。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# 直接按文件加载 workbench 的纯函数模块，避免触发 backend 包的 pydantic 依赖
_QOS_PATH = ROOT / "work_bench" / "backend" / "analysis" / "qos.py"
_spec = importlib.util.spec_from_file_location("wb_qos", _QOS_PATH)
assert _spec and _spec.loader
_wb_qos = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_wb_qos)
compose_qos = _wb_qos.compose_qos
check_static = _wb_qos.check_static

from math_modeling.models import LinkParams, Requirement  # noqa: E402
from math_modeling.path_qos import compose_from_params  # noqa: E402
from math_modeling.qos_checker import check_qos  # noqa: E402

CASES = [
    [(5.0, 3.0, 1_000_000, 1e-5, 0.01), (7.0, 4.0, 500_000, 2e-5, 0.02)],
    [(0.5, 1.3, 7_400_000_000, 8e-8, 0.0002)],
    [(452.9, 125.9, 12_000_000, 8e-6, 0.0006), (5.1, 5.0, 26_000_000, 1e-5, 0.0006)],
]


def _wb_links(rows):
    return [
        {
            "linkId": f"L{i}",
            "srcNodeId": "A",
            "dstNodeId": "B",
            "params": {
                "delayMs": d,
                "jitterMs": j,
                "bandwidthBps": b,
                "ber": ber,
                "packetLossRate": loss,
            },
        }
        for i, (d, j, b, ber, loss) in enumerate(rows, 1)
    ]


def _src_params(rows):
    return [
        LinkParams(
            delay_ms=d,
            jitter_ms=j,
            bandwidth_bps=int(b),
            ber=ber,
            packet_loss_rate=loss,
        )
        for (d, j, b, ber, loss) in rows
    ]


@pytest.mark.parametrize("rows", CASES)
def test_compose_matches_main_project(rows):
    wb = compose_qos(_wb_links(rows))
    src = compose_from_params(_src_params(rows))

    assert wb["delayMs"] == pytest.approx(src.delay_ms)
    assert wb["jitterMs"] == pytest.approx(src.jitter_ms)
    assert wb["bandwidthBps"] == pytest.approx(src.bandwidth_bps)
    assert wb["packetLossRate"] == pytest.approx(src.packet_loss_rate)
    assert wb["ber"] == pytest.approx(src.ber)


def test_verdict_matches_on_boundary_cases():
    rows = CASES[1]  # 单链路：0.5ms / 1.3ms / 7.4Gbps / 8e-8 / 0.0002
    wb = compose_qos(_wb_links(rows))
    src = compose_from_params(_src_params(rows))

    requirements = [
        # 恰好落在容差内（时延 +1.0）
        dict(delayMs=0.3, jitterMs=1.3, bandwidthBps=7_400_000_000, ber=8e-8, packetLossRate=0.0002),
        # 时延超容差
        dict(delayMs=-0.6, jitterMs=1.3, bandwidthBps=7_400_000_000, ber=8e-8, packetLossRate=0.0002),
        # 带宽差 1bps（无容差）
        dict(delayMs=0.5, jitterMs=1.3, bandwidthBps=7_400_000_001, ber=8e-8, packetLossRate=0.0002),
        # 误码贴容差
        dict(delayMs=0.5, jitterMs=1.3, bandwidthBps=7_400_000_000, ber=8e-8 - 1e-12, packetLossRate=0.0002),
    ]
    for req in requirements:
        wb_chk = check_static(wb, req)
        src_req = Requirement(
            delay_ms=req["delayMs"],
            jitter_ms=req["jitterMs"],
            bandwidth_bps=req["bandwidthBps"],
            ber=req["ber"],
            packet_loss_rate=req["packetLossRate"],
        )
        src_chk = check_qos(src, src_req)
        assert wb_chk["ok"] is src_chk.feasible, (req, wb_chk, src_chk.violations)
