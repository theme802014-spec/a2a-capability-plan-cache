# Lifecycle and policy boundary

1. Normalize the request and extract a bounded demand record during planning.
2. Use exact or restricted feature lookup to find a candidate plan.
3. Rebind the candidate to current request values and validate its structure.
4. Check Agent Card freshness, source identity, and dependency changes.
5. Choose reuse, semantic review, invalidation, or replanning.
6. Execute the DAG against current user data and downstream services.
7. Store evidence using the supply snapshot captured before generation; archive replaced entries. This reference does not validate business success.

The reference analyzer reports observations; the separate store applies an opt-in conservative reuse policy. Unknown freshness, missing Card evidence, and semantic ambiguity remain visible instead of being silently treated as compatible.
