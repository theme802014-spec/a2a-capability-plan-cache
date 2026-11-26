# Source-system evidence and public reproduction — 2026-11-25

Two evidence levels must remain distinct. The numbers below summarize internal
source-system reports. The public package includes synthetic tests and demos,
not the private services, original prompt/response traces, or a standalone
reproduction of the historical model benchmark. Treat those numbers as reported
case-study observations, not independently reproduced public benchmarks.

## Controlled lifecycle replay (source C-037)

24 historical evaluation requests, temporary SQLite, network prohibited, no new
model or business calls. "Needs planning" means the cache path requires fallback;
it is not a count of newly executed model calls in this offline replay.

| Controlled scenario | Reuse without model | Needs planning |
|---|---:|---:|
| Supply unchanged | 23 | 1 |
| Unused Skill removed | 23 | 1 |
| Bound community Skill removed | 15 | 9 |
| Bound Skill description changed | 15 + 15 review opportunities | 9 |
| Community Card version changed | 15 + 15 review opportunities | 9 |
| New unbound community Skill | 23 + 23 review opportunities | 1 |
| All supply stale | 0 | 24 |
| Community refresh failed | 15 | 9 |

The missing baseline hit was already not reusable. This replay checks engineering
policy, not semantic correctness or user-request accuracy.

## Actual Planner path (source C-030, 2026-11-17)

120 requests per round, real planning model, local Agent Card services, isolated
database, zero business execution calls.

| Round | Model requests (including repair) | Cache hits | Planning wall time |
|---|---:|---:|---:|
| First | 57 | 67 | 159.032 s |
| Repeated | 11 | 112 | 27.094 s |

The 83.0% reduction compares first and repeated rounds. The first round already
benefited from structural reuse; this is **not** an uncached baseline comparison.
Cards did not change during this run. Card-evolution behavior comes from separate
controlled tests. These numbers predate the 2026-11-25 changes and must not be
presented as performance measurements of this public v0.3.0 package.

## Small segmented trace example (source C-028 v2, 2026-11-17)

Three read-only requests, first/repeated pair. First planning durations were
approximately 2.278, 1.957, and 1.960 seconds with one planner call each. Repeated
planning durations were approximately 1.6, 1.6, and 2.1 milliseconds with zero
planner calls and the version gate enabled.

Total request time still included business agents and answer composition. The
sample is too small for a general latency claim or attribution of all end-to-end
improvement to plan caching.

## Negative result retained (source C-034/C-035)

A structural-bucket/embedding prototype suggested 19 reusable plans on 72 requests.
All 19 were already covered by the existing feature cache: incremental coverage
was **zero**. Apparent speedup against full planning is not evidence of a new
semantic-generalization gain. The prototype is not included as a production path.
Its control failures motivated stricter multi-goal and explicit-order boundaries.

## What can be reproduced here

- full-DAG step localization and unrelated-supplier failure isolation;
- capture-before-generation version consistency;
- SQLite restart, history and explicit replacement lifecycle;
- durable review tasks, deduplication, leases and supersession;
- exact-key information preservation and current-request placeholder binding;
- concurrent refresh behavior using deterministic injected fetchers;
- bounded planning metric aggregation.

Public tests have synthetic contracts and controlled expectations. Passing them is
not independent semantic labelling. New-capability relevance, alternate-wording
multi-step reuse, business result quality, concurrency throughput and full-chain
cost savings still require separate evaluation.
