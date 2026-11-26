# Capability-aware Agent Plan Cache v0.3.0

This version adds a persistent, testable capability-change lifecycle to the
reference package.

- Scope required-supply failures to the plan's actual dependencies; retain
  unrelated uncertainty separately as opportunity evidence.
- Separate observed impact from an explicit conservative reuse policy.
- Capture planning-time supply and block old-generation evidence after a change.
- Store plans, replaced revisions and supply observations in SQLite.
- Queue direct dependency reviews separately from new-supply opportunities.
- Deduplicate observations, lease tasks, retry within bounds and supersede stale
  tasks when a plan or Card is replaced.
- Inject concurrent Card fetchers with single-flight refresh and timeouts.
- Add bounded aggregate planning metrics without request/plan text.
- Check the full three-step DAG in the demo and add persistent lifecycle/race demos.
- Document source-system measurements separately from public synthetic evidence.

API notes: impact results add `opportunity_uncertainties`. Manifest fingerprint
changes now produce `candidate_replan` (blocked by policy), rather than claiming a
proven incompatible contract. Missing binding evidence is unknown and blocked.
`rebind_plan` replaces placeholders only in step inputs and raises `ValueError`
when a current request slot is absent, instead of silently binding `None`.

No automatic semantic replan worker, production HTTP service, or business executor
is included. The version is prepared locally; publication is a separate step.
