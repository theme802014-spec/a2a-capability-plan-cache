# Durable Card-change review queue

`PlanStore.observe` records an actual changed normalized supply and enqueues review
tasks in the same SQLite transaction. Identical observations create no additional
work. An initial observation establishes a baseline; it is not a change event.

Two task kinds remain separate:

- `dependency_review`: bound Skill removal/change, Card version, source, or global
  declaration changes. These have priority 0.
- `opportunity_review`: new/changed supply that might help a historical request,
  including requests previously bound to other domains. These have priority 1.

Candidates are deliberately broad and **unverified**. This release does not use a
semantic ranker to prove relevance or implement automatic targeted replanning.

## Worker protocol

```python
queue = PlanningReviewQueue("plans.db")
for task in queue.claim(limit=5, lease_seconds=60, max_attempts=3):
    queue.finish(
        task["task_id"], task["lease_token"],
        decision="unknown", reviewer="business_owner",
    )
```

Decisions are `no_change`, `needs_replan`, or `unknown`. Reviewer provenance is one
of `business_owner`, `deterministic_contract`, or `research_model`. A model label
is a source record, not expert ground truth.

Claims use `BEGIN IMMEDIATE` and unique lease tokens. Expired leases can be
reclaimed within the attempt budget; failed tasks can be explicitly retried.
Within each priority, event rotation avoids a single large event taking every
slot. Continuous high-priority work can still delay opportunities; this is not a
hard service-level fairness guarantee.

Finishing checks the lease, current plan revision, current supply revision, and
freshness. A newer Card or replacement plan supersedes unfinished old tasks; late
workers cannot record a successful result against those tasks. New changes are
compared against each plan's captured baseline, so an unreviewed addition is not
lost simply because another Card change arrived.

The queue stores references, change reasons, reviewer provenance, and status. It
does not execute A2A calls, call an LLM, rewrite plans, or grant permissions. A
`needs_replan` review result is not automatically consumed as a new plan; the
separate observed-dependency gate already blocks changed required dependencies.

`stats()` returns aggregate counts only. Request text and plan templates remain in
the plan store; production operators must define data retention and access policy.
