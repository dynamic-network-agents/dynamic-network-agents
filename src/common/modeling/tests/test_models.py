"""数据模型 from_dict 解析单元测试。"""
from common.modeling.models import (
    Actual,
    Event,
    Link,
    Node,
    Requirement,
    Service,
    ServicePath,
)


def test_node_from_dict():
    n = Node.from_dict({
        "nodeId": "UAV012", "name": "无人平台12", "nodeType": "uav",
        "ip": "10.1.12.3", "mask": "255.255.255.0",
        "position": {"x": 1520.0, "y": 830.5}, "status": "online",
    })
    assert n.node_id == "UAV012"
    assert n.node_type == "uav"
    assert n.online
    assert n.position.x == 1520.0


def test_link_from_dict():
    l = Link.from_dict({
        "linkId": "L00087", "linkType": "microwave",
        "srcNodeId": "GND005", "dstNodeId": "AIR001", "status": "up",
        "params": {"delayMs": 12.5, "jitterMs": 3.0, "bandwidthBps": 8000000,
                   "ber": 0.0001, "packetLossRate": 0.02},
    })
    assert l.link_id == "L00087"
    assert l.up
    assert l.params.delay_ms == 12.5
    assert l.params.bandwidth_bps == 8000000


def test_service_from_dict():
    s = Service.from_dict({
        "serviceId": "SVC0007", "serviceType": "video",
        "srcNodeId": "UAV012", "dstNodeId": "UAV088", "priority": 6,
        "status": "running", "category": "test",
        "requirement": {"delayMs": 150, "jitterMs": 30, "bandwidthBps": 2000000,
                        "ber": 0.0001, "packetLossRate": 0.05},
        "path": {"pathId": "P00031", "segments": [
            {"type": "link", "id": "L00201"}, {"type": "link", "id": "L00112"}]},
        "actual": {"avgDelayMs": 45.2, "jitterMs": 8.5, "effBwBps": 1950000,
                   "errPct": 0.8, "packetLossRate": 0.012, "qosMeet": True},
    })
    assert s.service_type == "video"
    assert s.is_test
    assert s.flow_key == ("UAV012", "UAV088")
    assert s.requirement.bandwidth_bps == 2000000
    assert s.path.segments[0].id == "L00201"
    assert s.actual.qos_meet is True


def test_event_from_dict():
    e = Event.from_dict({
        "eventId": "EVT003", "type": "link_state_changed",
        "time": "10:03:07.125480", "tsUs": 1800237787125480,
        "payload": {"event": "param_change", "linkId": "L00087"},
    })
    assert e.type == "link_state_changed"
    assert e.payload["linkId"] == "L00087"


def test_service_flow_grouping():
    """同源-目多业务合并为一个 flow。"""
    mk = lambda sid, s, d: Service(service_id=sid, src_node_id=s, dst_node_id=d)
    svcs = [mk("A", "UAV1", "UAV2"), mk("B", "UAV1", "UAV2"), mk("C", "UAV2", "UAV1")]
    groups: dict = {}
    for s in svcs:
        groups.setdefault(s.flow_key, []).append(s)
    # flow_key 是无序端点对：A→B 与 B→A 合并为 1 个 flow
    assert len(groups) == 1
    assert len(groups[("UAV1", "UAV2")]) == 3
