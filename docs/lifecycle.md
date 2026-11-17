# Lifecycle and policy boundary

1. Normalize the request and extract a bounded demand record during planning.
2. Use exact or restricted feature lookup to find a candidate plan.
3. Rebind the candidate to current request values and validate its structure.
4. Check Agent Card freshness, source identity, and dependency changes.
5. Choose reuse, semantic review, invalidation, or replanning.
6. Execute the DAG against current user data and downstream services.
7. Store successful evidence as a new revision while retaining older revisions.

The reference analyzer is shadow-only. Unknown freshness, missing Card evidence, and semantic ambiguity remain visible instead of being silently treated as compatible.
