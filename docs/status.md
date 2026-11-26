# Status — v0.3.0 (2026-11-25)

The public package now contains deterministic impact analysis, an opt-in reuse
policy, SQLite plan/history/observation persistence, durable Card-change review
tasks, injected concurrent refresh, request rebinding, and bounded metrics.

The full-DAG demo checks all three dependencies. Lifecycle and race demos use
synthetic planner outputs, temporary databases and no network. They demonstrate
policy and evidence consistency, not model intelligence.

The source system integrates these ideas into an actual planner. Its optional
`off`/`shadow`/`enforce` deployment modes, business adapters, authorization gates,
HTTP statistics endpoints and real model calls are **not bundled here**. Do not
interpret public tests as evidence of a production deployment or an independent
semantic accuracy evaluation.

Remaining work includes semantic opportunity adjudication, automated review-result
application, robust multi-step cross-wording reuse and independent end-to-end
benchmarks. Reviews never automatically rewrite or execute a plan. See
[evaluation-20261125.md](evaluation-20261125.md) for source-system evidence and limits.
