"""Bounded aggregate planning measurements; no query, plan, or credential fields."""
import math
from collections import deque


class PlanningMetrics:
    """The integration records measured durations and actual planner call counts.

    No instrumentation runs a planner. The source label is deliberately bounded
    so an arbitrary user request cannot accidentally become a statistics key.
    """
    SOURCES = {"exact_cache", "feature_cache", "model_direct", "fallback", "unknown"}

    def __init__(self, max_samples=1000):
        if not isinstance(max_samples, int) or isinstance(max_samples, bool) or max_samples < 1:
            raise ValueError("positive window size required")
        self._samples = deque(maxlen=max_samples)

    def record(self, *, source, total_ms, model_calls, card_refresh_ms=0):
        if source not in self.SOURCES:
            raise ValueError("unsupported source label")
        if (any(not math.isfinite(v) or v < 0 for v in (total_ms, card_refresh_ms))
                or card_refresh_ms > total_ms
                or not isinstance(model_calls, int) or isinstance(model_calls, bool) or model_calls < 0):
            raise ValueError("nonnegative measured durations and integer call count required")
        self._samples.append(dict(source=source, total_ms=total_ms, model_calls=model_calls,
                                  card_refresh_ms=card_refresh_ms))

    def summary(self):
        samples = list(self._samples)
        def stats(rows):
            durations = sorted(row["total_ms"] for row in rows)
            def percentile(p):
                return durations[max(0, math.ceil(len(durations) * p) - 1)] if durations else None
            return {"samples": len(rows), "model_calls": sum(r["model_calls"] for r in rows),
                    "card_refresh_ms": sum(r["card_refresh_ms"] for r in rows),
                    "p50_ms": percentile(0.50), "p95_ms": percentile(0.95)}
        return {"window_capacity": self._samples.maxlen, **stats(samples),
                "by_source": {source: stats([r for r in samples if r["source"] == source])
                              for source in sorted({r["source"] for r in samples})}}
