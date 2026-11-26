import pytest
from capability_plan_cache import PlanningMetrics


def test_window_is_bounded_aggregated_and_does_not_accept_query_labels():
    metrics = PlanningMetrics(max_samples=2)
    metrics.record(source="model_direct", total_ms=200, model_calls=1, card_refresh_ms=10)
    metrics.record(source="exact_cache", total_ms=2, model_calls=0)
    metrics.record(source="exact_cache", total_ms=4, model_calls=0)
    assert metrics.summary() == {
        "window_capacity": 2, "samples": 2, "model_calls": 0, "card_refresh_ms": 0,
        "p50_ms": 2, "p95_ms": 4,
        "by_source": {"exact_cache": {"samples": 2, "model_calls": 0, "card_refresh_ms": 0,
                                        "p50_ms": 2, "p95_ms": 4}},
    }
    with pytest.raises(ValueError):
        metrics.record(source="private user question", total_ms=1, model_calls=0)


@pytest.mark.parametrize("total,calls,refresh", [(-1, 0, 0), (float("nan"), 0, 0), (2, -1, 0), (2, True, 0), (2, 0, 3)])
def test_invalid_measurements_are_rejected(total, calls, refresh):
    with pytest.raises(ValueError):
        PlanningMetrics().record(source="exact_cache", total_ms=total, model_calls=calls, card_refresh_ms=refresh)
