"""路径下发执行器单测（离线，用假 client）。"""
import networkx as nx
import pytest

from api.executor import PathExecutor


class _FakeClient:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or {"result": "accepted", "pathId": "P1", "effectiveTime": "t"}

    def set_service_path(self, service_id, src, dst, segments, request_id=None):
        self.calls.append((service_id, src, dst, segments, request_id))
        return self.result


def test_build_segments():
    ex = PathExecutor(None)
    assert ex.build_segments(["L1", "L2"]) == [
        {"type": "link", "id": "L1"},
        {"type": "link", "id": "L2"},
    ]


def test_execute_success():
    c = _FakeClient()
    ex = PathExecutor(c)
    r = ex.execute("SVC1", "s", "t", ["L1", "L2"])
    assert r["result"] == "accepted"
    assert c.calls[0][3] == [{"type": "link", "id": "L1"}, {"type": "link", "id": "L2"}]


def test_execute_rejected_raises():
    c = _FakeClient({"result": "rejected", "reason": "1004"})
    ex = PathExecutor(c)
    with pytest.raises(ValueError):
        ex.execute("SVC1", "s", "t", ["L1", "L2"])


def test_execute_validate_rejects_bad_path():
    G = nx.MultiGraph()
    G.add_edge("s", "a", key="L1")
    G.add_edge("b", "t", key="L2")  # 与 L1 不连续
    ex = PathExecutor(_FakeClient())
    with pytest.raises(ValueError):
        ex.execute("SVC1", "s", "t", ["L1", "L2"], graph=G)
