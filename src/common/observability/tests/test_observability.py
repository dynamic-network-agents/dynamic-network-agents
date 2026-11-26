"""观测留痕与指标聚合单测（`common/observability/`）。"""
from common.observability.metrics import collect_metrics
from common.observability.timeline import DecisionTimeline, EventKind


class Clock:
    """可控单调时钟。"""

    def __init__(self, t: float = 1000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def tick(self, dt: float) -> None:
        self.t += dt


def test_timeline_records_elapsed_between_entries():
    clock = Clock()
    timeline = DecisionTimeline(clock=clock)
    timeline.mark(EventKind.PERCEPTION, "冻结快照")
    clock.tick(2.5)
    timeline.mark(EventKind.DECISION, "规划完成", gain=12.0)
    clock.tick(0.5)
    timeline.mark(EventKind.DISPATCH, "下发 3 条", flow_count=3)

    entries = timeline.entries
    assert len(entries) == 3
    assert entries[0].elapsed_s == 0.0          # 第一条无前序
    assert entries[1].elapsed_s == 2.5
    assert entries[2].elapsed_s == 0.5
    assert entries[1].detail["gain"] == 12.0


def test_timeline_filters_by_kind():
    timeline = DecisionTimeline(clock=Clock())
    timeline.mark(EventKind.PERCEPTION, "a")
    timeline.mark(EventKind.DISPATCH, "b")
    assert len(timeline.of_kind(EventKind.DISPATCH)) == 1
    assert timeline.of_kind(EventKind.DECISION) == []


def test_timeline_serializable():
    timeline = DecisionTimeline(clock=Clock())
    timeline.mark(EventKind.DECISION, "决策", k=1)
    payload = timeline.to_dicts()
    assert payload[0]["kind"] == "decision"
    assert payload[0]["detail"] == {"k": 1}


def test_collect_metrics_aggregates_durations_and_counts():
    clock = Clock()
    timeline = DecisionTimeline(clock=clock)
    timeline.mark(EventKind.PERCEPTION, "感知")
    clock.tick(1.0)
    timeline.mark(EventKind.DECISION, "决策")
    clock.tick(2.0)
    timeline.mark(EventKind.DISPATCH, "下发", flow_count=3)
    clock.tick(1.0)
    timeline.mark(EventKind.DISPATCH, "下发", flow_count=2)

    metrics = collect_metrics(
        timeline, predicted_compliant=10, measured_compliant=9, total_services=17,
    )
    assert metrics.perception["count"] == 1
    assert metrics.decision["mean_s"] == 1.0
    assert metrics.dispatch["count"] == 2
    assert metrics.dispatch["total_s"] == 3.0
    assert metrics.dispatch_count == 2
    assert metrics.dispatched_flows == 5        # 3 + 2
    assert metrics.measured_compliant == 9
    assert metrics.to_dict()["dispatch_count"] == 2


def test_collect_metrics_handles_empty_timeline():
    metrics = collect_metrics(DecisionTimeline(clock=Clock()))
    assert metrics.dispatch_count == 0
    assert metrics.perception["count"] == 0
    assert metrics.perception["mean_s"] == 0.0
