# Evaluation plan and current evidence

The full source system has separate experiments for exact plan reuse, dependency impact localization, supply-change candidate recall, and model-based semantic review. This public package does not ship private traces or claim that those experiments are a general benchmark.

Recommended measurements include incorrect reuse, missed invalidation, unrelated invalidation, new-capability recall, refresh latency, planner calls and tokens saved, review cost versus full replanning, and revision traceability.

The useful comparison is end-to-end:

```text
uncached full planning
vs.
lookup + rebind + freshness check + impact analysis + occasional review/replan
```

A cache hit rate by itself is not a correctness result.
