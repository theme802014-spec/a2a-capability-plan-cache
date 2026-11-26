# Capability Aware Agent Plan Cache

[![Tests](https://github.com/theme802014-spec/a2a-capability-plan-cache/actions/workflows/test.yml/badge.svg)](https://github.com/theme802014-spec/a2a-capability-plan-cache/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

**Capability-aware plan caching for A2A multi-agent DAGs.** This reference implementation separates user demand, Agent Card supply, and executable plan evidence so a capability change can trigger targeted review instead of deleting every cached plan.

The current release is **v0.3.0**.

## What problem does this solve?

LLM planners repeatedly pay the cost of decomposing similar user requests into multi-agent DAGs. Reusing the last answer is unsafe because the current request and the underlying agent capabilities may have changed.

This project caches the **plan shape**, not the previous answer:

```text
user request
  → demand signature
  → executable multi-agent DAG
  → selected Agent / Skill dependencies
  → Agent Card observation
  → targeted impact analysis after a capability change
  → reuse, semantic review, invalidation, or replanning
```

The design keeps three objects separate:

- **Demand signature**: what the user is trying to accomplish, including constraints and ordering evidence.
- **Supply observation**: a normalized, secret-free snapshot of an Agent Card and its skills.
- **Plan cache entry**: the DAG, selected capabilities, contract fingerprints, and supply evidence used when the plan was created.

## 30-second demo

```bash
git clone https://github.com/theme802014-spec/a2a-capability-plan-cache.git
cd a2a-capability-plan-cache
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
python3 examples/run_demo.py
python3 examples/lifecycle_demo.py
python3 examples/generation_race.py
pytest -q
```

The synthetic example models a three-step workflow:

```text
read health background
        ↓
analyze sleep
        ↓
recommend community activities
```

The demo then changes the community Agent Card. The analyzer reports:

```json
{
  "decision": "candidate_replan",
  "directly_affected_steps": ["s3"],
  "semantic_review_required": true
}
```

Only the community step is directly affected in this example. The demo uses synthetic data and makes no network calls.

## Why this is different from answer caching

| Approach | Cached object | Understands capability changes | Can target affected steps |
|---|---|---:|---:|
| Answer cache | Final response | No | No |
| Prompt/KV cache | Context prefix | No | No |
| Basic plan cache | DAG or plan template | Usually no | Usually no |
| This reference | Demand + DAG + capability evidence | Yes, conservatively | Yes, as a review signal |

The impact analyzer reports observations; `cache_reuse_decision` is a separate opt-in policy. `PlanStore.lookup` applies that policy, while business authorization and execution remain the caller's responsibility.

## New in v0.3.0

- **Full-DAG fault isolation:** failed or stale unrelated suppliers do not disable unchanged execution dependencies.
- **Generation-time evidence:** capture supply before planning; a Card update cannot relabel an older generation as current.
- **SQLite lifecycle:** restart-safe plans, observations and archived replacement revisions.
- **Durable review queue:** direct dependency tasks and opportunity candidates, with priorities, leases, retries and stale-task supersession.
- **Concurrent refresh:** injected fetchers, per-instance single-flight batches, timeout and configuration-revision handling.
- **Cost visibility:** bounded aggregate P50/P95, planner call counts and refresh time without request text.

The lifecycle demo uses a planner stub and a temporary database. It covers generation, restart hit, unrelated failure, version change, stale-generation rejection, explicit replacement and renewed reuse. Nothing calls an LLM or a business service.

Read [version consistency](docs/version-consistency.md), [review queue](docs/review-queue.md), and [refresh and metrics](docs/refresh-and-metrics.md). [Evaluation notes](docs/evaluation-20261125.md) distinguish source-system case studies from publicly reproducible synthetic tests.

## Repository map

```text
src/capability_plan_cache/
  demand_signature.py  Source-grounded demand validation
  supply_changes.py    Field-level Agent Card diffs
  impact.py            Conservative dependency-aware assessment
  plan_cache.py        Plan evidence and current-request rebinding
  reuse_policy.py      Conservative reuse gate and exact keys
  store.py             SQLite plans, revisions and observations
  review_queue.py      Durable change-review tasks
  supply_refresh.py    Injected concurrent refresh
  metrics.py           Bounded planning statistics

examples/
  run_demo.py          Full-DAG impact demonstration
  lifecycle_demo.py    Persistent lifecycle with planner stub
  generation_race.py   Card update during generation
  *.json               Demand, plan, and Agent Card fixtures

schemas/
  *.schema.json        Demand, supply, and plan evidence schemas

docs/
  architecture.md      System flow
  data-model.md        Record definitions
  lifecycle.md         Cache lifecycle and policy boundary
  incremental-invalidation.md  Change classification
  evaluation.md        Metrics and evidence limits
  prior-art.md         Relationship to adjacent work
  status.md            Implementation status
```

## Design boundary

The public package intentionally excludes:

- production service URLs and credentials
- user data, health records, response caches, and SQLite databases
- business-specific agent adapters
- an assertion of patent novelty or universal originality

The implementation was reduced from an independent 13B multi-agent system into a standalone reference package. It includes a conservative reference cache gate and persistence. Production adapters, semantic compatibility proofs and automatic review-driven replanning are outside this package.

## Contributing

The most useful contributions are reproducible examples, failure cases, evaluation protocols, and discussion of Agent Card input/output compatibility. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

Do not submit credentials, personal records, private Agent Cards, raw authorization headers, or production cache/database files. See [SECURITY.md](SECURITY.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
