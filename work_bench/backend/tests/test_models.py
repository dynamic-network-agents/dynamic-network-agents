"""数据契约测试：字段校验、未知字段保留、快照默认值。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.models import Actual, Link, Node, Service, Snapshot


def test_snapshot_defaults():
    snap = Snapshot(health="live", received_at="2026-11-24T00:00:00Z")
    assert snap.snapshot_version == 1
    assert snap.offline is False
    assert snap.nodes == [] and snap.services == []
    assert snap.pagination.links.complete is True


def test_node_requires_node_id_and_keeps_extras():
    with pytest.raises(ValidationError):
        Node.model_validate({"name": "缺 nodeId"})
    node = Node.model_validate({"nodeId": "N1", "ip": "10.0.0.1", "extraField": 1})
    assert node.nodeId == "N1"
    assert node.model_dump()["extraField"] == 1


def test_link_params_and_requirement_share_shape():
    link = Link.model_validate(
        {
            "linkId": "L1",
            "srcNodeId": "A",
            "dstNodeId": "B",
            "params": {"delayMs": 5, "bandwidthBps": 1e6},
        }
    )
    assert link.params is not None and link.params.delayMs == 5
    svc = Service.model_validate(
        {
            "serviceId": "S1",
            "requirement": {"delayMs": 340, "ber": 9e-5},
            "path": {"pathId": "P01001", "segments": [{"type": "link", "id": "L1"}]},
            "actual": {"avgDelayMs": 330, "qosMeet": True},
        }
    )
    assert svc.requirement.ber == 9e-5
    assert svc.path.segments[0].type == "link"
    assert isinstance(svc.actual, Actual) and svc.actual.qosMeet is True


def test_actual_keeps_unknown_fields():
    actual = Actual.model_validate({"avgDelayMs": 1, "somethingNew": "x"})
    assert actual.model_dump()["somethingNew"] == "x"
