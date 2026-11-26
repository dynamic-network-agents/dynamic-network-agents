"""A2A 协同层单测：消息协议、冲突仲裁、任务调度。"""
from agents.a2a.arbitration import ProposedAction, arbitrate, rejection_notice
from agents.a2a.message import A2AMessage, MessageBus, MessageKind
from agents.a2a.scheduler import (
    ScheduleConfig,
    TaskRole,
    TaskScheduler,
    WorkItem,
)


def _action(action_id, actor, *, flow=("A", "B"), path=("L1",), priority=1, execution=False):
    return ProposedAction(
        action_id=action_id, actor=actor, service_id=f"S{action_id}",
        flow_key=flow, path=list(path), priority=priority, is_execution=execution,
    )


# --------------------------------------------------------------------------- 消息
def test_message_roundtrip():
    msg = A2AMessage(sender="ops", recipient="ctl", kind=MessageKind.SITUATION, payload={"a": 1})
    restored = A2AMessage.from_dict(msg.to_dict())
    assert restored.kind is MessageKind.SITUATION
    assert restored.payload == {"a": 1}


def test_bus_delivers_by_priority_then_arrival():
    bus = MessageBus()
    bus.publish(A2AMessage("a", "ctl", MessageKind.REQUEST, priority=0))
    bus.publish(A2AMessage("b", "ctl", MessageKind.DECISION, priority=5))
    bus.publish(A2AMessage("c", "ctl", MessageKind.SITUATION, priority=0))

    got = bus.receive("ctl")
    assert [m.sender for m in got] == ["b", "a", "c"]   # 优先级降序，同级按到达序
    assert bus.receive("ctl") == []                    # 取走即清空


def test_bus_keeps_history_for_replay():
    bus = MessageBus()
    bus.publish(A2AMessage("a", "ctl", MessageKind.DIAGNOSIS))
    bus.publish(A2AMessage("b", "ops", MessageKind.REQUEST))
    assert len(bus.history) == 2
    assert len(bus.peek("ctl")) == 1


# --------------------------------------------------------------------------- 仲裁
def test_no_conflict_all_accepted():
    result = arbitrate([
        _action("a1", "ops", flow=("A", "B"), path=("L1",)),
        _action("a2", "ctl", flow=("C", "D"), path=("L9",)),
    ])
    assert len(result.accepted) == 2
    assert result.rejected == []


def test_execution_beats_advice():
    """规则 1：执行类动作优先于建议类。"""
    result = arbitrate([
        _action("advise", "ops", path=("L1",), priority=8, execution=False),
        _action("exec", "ctl", path=("L2",), priority=1, execution=True),
    ])
    assert [a.action_id for a in result.accepted] == ["exec"]
    assert "执行类动作优先" in result.rejected[0][1]


def test_higher_business_priority_wins():
    """规则 2：同角色内按业务优先级降序。"""
    result = arbitrate([
        _action("low", "ctl", path=("L1",), priority=2, execution=True),
        _action("high", "ctl", path=("L2",), priority=7, execution=True),
    ])
    assert [a.action_id for a in result.accepted] == ["high"]
    assert "业务优先级更高" in result.rejected[0][1]


def test_service_id_breaks_tie_deterministically():
    """规则 3：优先级相同时按业务 ID 字典序（可复现）。"""
    result = arbitrate([
        _action("z", "ctl", path=("L1",), priority=4, execution=True),
        _action("a", "ctl", path=("L2",), priority=4, execution=True),
    ])
    assert [a.action_id for a in result.accepted] == ["a"]
    # 再跑一次，结果必须一致（确定性）
    again = arbitrate([
        _action("z", "ctl", path=("L1",), priority=4, execution=True),
        _action("a", "ctl", path=("L2",), priority=4, execution=True),
    ])
    assert [a.action_id for a in again.accepted] == ["a"]


def test_accepted_paths_keeps_one_per_flow():
    result = arbitrate([
        _action("x", "ctl", flow=("A", "B"), path=("L1",), priority=3, execution=True),
        _action("y", "ctl", flow=("A", "B"), path=("L2",), priority=5, execution=True),
    ])
    assert result.accepted_paths() == {("A", "B"): ["L2"]}


def test_rejection_notice_carries_reason():
    rejected = _action("advise", "ops", path=("L1",), priority=1)
    notice = rejection_notice(rejected, "执行类动作优先", recipient="ops")
    assert notice.kind is MessageKind.REJECT
    assert notice.payload["action_id"] == "advise"
    assert "执行类" in notice.payload["reason"]


# --------------------------------------------------------------------------- 调度
def test_scheduler_orders_by_role_dependency():
    scheduler = TaskScheduler(ScheduleConfig(max_items_per_round=10))
    items = [
        WorkItem(TaskRole.DISPATCH, "d1"),
        WorkItem(TaskRole.DECISION, "x1"),
        WorkItem(TaskRole.DIAGNOSIS, "g1"),
        WorkItem(TaskRole.PERCEPTION, "p1"),
    ]
    result = scheduler.schedule_round(items)
    assert [i.role for i in result.scheduled] == [
        TaskRole.PERCEPTION, TaskRole.DIAGNOSIS, TaskRole.DECISION, TaskRole.DISPATCH,
    ]


def test_scheduler_respects_budget_and_keeps_early_roles():
    """预算截断时保留感知/诊断（不能只剩发而没有依据）。"""
    scheduler = TaskScheduler(ScheduleConfig(max_items_per_round=2))
    items = [
        WorkItem(TaskRole.DISPATCH, "d1"), WorkItem(TaskRole.DISPATCH, "d2"),
        WorkItem(TaskRole.PERCEPTION, "p1"), WorkItem(TaskRole.DIAGNOSIS, "g1"),
    ]
    result = scheduler.schedule_round(items)
    assert len(result.scheduled) == 2
    assert result.scheduled[0].role is TaskRole.PERCEPTION
    assert result.scheduled[1].role is TaskRole.DIAGNOSIS
    assert len(result.skipped) == 2
    assert "预算" in result.reason_skipped


def test_scheduler_counts_planned_llm_calls():
    scheduler = TaskScheduler(ScheduleConfig(max_items_per_round=10))
    items = [
        WorkItem(TaskRole.DIAGNOSIS, "g1", llm_required=True),
        WorkItem(TaskRole.PERCEPTION, "p1"),
    ]
    result = scheduler.schedule_round(items)
    assert result.llm_calls_planned == 1


def test_scheduler_stops_at_max_rounds():
    scheduler = TaskScheduler(ScheduleConfig(max_items_per_round=10, max_rounds=1))
    items = [WorkItem(TaskRole.PERCEPTION, "p1")]
    scheduler.schedule_round(items)
    assert scheduler.exhausted is True
    result = scheduler.schedule_round(items)
    assert result.scheduled == []
    assert "最大轮数" in result.reason_skipped
