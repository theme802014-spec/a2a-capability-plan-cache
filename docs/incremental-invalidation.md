# Incremental invalidation

A full Agent Card fingerprint is too coarse for plan maintenance. The reference compares added and removed Skill identifiers, changed Skill fields, Card-level interface and mode fields, and publisher version changes.

```text
removed bound Skill / missing capability -> invalidated
changed bound contract or interface      -> candidate_replan
new unbound related Skill                 -> semantic_review_required
failed or stale Card refresh              -> unknown
unchanged fresh dependencies              -> compatible_observed
```

A version bump is review evidence, not proof that every cached plan is invalid. An unchanged version is not proof of compatibility when observed content changed.
