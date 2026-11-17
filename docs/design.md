# Design: capability-aware plan caching

## Problem

A planner can spend most of its cost repeatedly deciding how to split a recurring user request into steps. Reusing the last answer is unsafe: the current request may contain different parameters, and the agent that supplied a capability may have changed.

This design caches the reusable *plan shape* and rebinds it to the current request. It does not cache the current user's business result.

## Lifecycle

```text
request
  -> demand record
  -> exact or restricted candidate lookup
  -> current-input binding and structural validation
  -> supply freshness and dependency assessment
  -> reuse, semantic review, or replan
  -> execute the DAG against current data
  -> store plan evidence and the observed supply snapshot
```

## Evidence model

A plan evidence record should preserve:

- the original request and a source-grounded demand record
- the DAG steps, ordering, input references, and dependency policy
- the selected capability and Skill identifiers
- a fingerprint of the capability contract used by each step
- the normalized Agent Card observations used at planning time
- planner, extractor, and schema versions
- a revision and the reason a newer revision replaced it

The demand record is not allowed to silently inherit from a similar cached request. A template hit can reuse a plan shape, but the current request must be bound and validated separately.

## Impact categories

- `invalidated`: a required capability or directly bound Skill disappeared, or a required contract changed in a way the local policy treats as unsafe.
- `candidate_replan`: the old plan has a changed dependency or a new/modified capability may be a better fit; semantic review is needed.
- `compatible_observed`: the observed dependency fields are unchanged and fresh enough for the local policy.
- `unknown`: freshness, source identity, or required supply evidence is missing. Unknown is not proof of compatibility.

The reference code intentionally uses conservative evidence boundaries. An Agent Card version bump alone does not prove incompatibility, and an unchanged version does not prove compatibility.

## A2A relationship

A2A Agent Cards are the supply-side input. The plan cache adds a consumer-side record of which portions of that supply were actually selected by a historical DAG. This enables targeted review instead of deleting every plan whenever a domain agent publishes a new Card.

The approach still depends on the Card exposing enough stable business semantics and input/output contract information. Public Card data should not be treated as permission to call hidden APIs.

## Safety and privacy

Store normalized capability descriptions and contract fingerprints rather than credentials, request authorization headers, personal records, or raw execution results. Keep user-specific inputs outside global plan equivalence keys unless the policy explicitly requires them.

## What this does not prove

This design is not a semantic compatibility proof, a patent opinion, or an automatic self-healing planner. A production deployment needs independent evaluation of false reuse, missed invalidation, unnecessary replanning, freshness failures, and total inference cost.
