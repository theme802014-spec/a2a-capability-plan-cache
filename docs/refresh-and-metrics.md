# Concurrent refresh and planning metrics

`SupplyRefresher` accepts an injected async fetcher, keeping network configuration,
credentials, raw Card parsing, protocol validation, and normalization in the
integration layer. The fetcher returns a normalized observation with a stable
`source_id`. Supplied URLs and authorization values are never emitted as metrics.

Refreshes run concurrently per domain, sharing one in-flight batch per refresher
instance. The interval is capped at half the configured freshness window. Endpoint
changes or an opaque `context_id` revision bypass throttling; change that revision
when authentication changes. Do not put secrets in it.

Each fetch has an `asyncio.wait_for` timeout. Failed siblings do not cancel successful
siblings. Failed observations retain the previous successful snapshot but mark it
failed; a cache read cannot renew its freshness. Persistence may add latency beyond
the fetch timeout. Single-flight coordination is per instance/process, not a
cross-process distributed lock.

`PlanningMetrics` holds a bounded window of explicitly supplied measurements:

```python
metrics.record(
    source="exact_cache", total_ms=2.4, card_refresh_ms=0.0, model_calls=0,
)
print(metrics.summary())
```

It exposes sample counts, actual model-call totals, refresh-duration totals and
nearest-rank P50/P95, overall and by bounded source label. It rejects arbitrary
source text to keep user questions out of metrics. It is a per-process helper;
no HTTP statistics endpoint or monitoring service is bundled.

For valid comparisons, measure the full planning path: lookup, input binding,
Card refresh, gate, review overhead, planner repair and miss fallback. Keep that
separate from downstream business execution and final answer composition.
