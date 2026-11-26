# Version consistency and scoped reuse

A plan is evidence about the capabilities observed when it was generated. The
current Card cannot retroactively become the source of a previous generation.

```python
captured = store.snapshot()                  # before any model call
steps = await your_planner(request, captured)
entry = make_plan_cache_entry(
    original_query=request,
    demand_signature=demand,
    steps=steps,
    dependencies=dependencies,
    supply_snapshots=captured,
)
store.put(key, entry)                        # never substitutes current Cards
```

The caller must build the planner prompt from the same captured supply and include
planner/prompt version and context scope in the key. The entry factory copies its
inputs; it cannot prove the caller supplied the correct snapshot. A generation
that spans a Card change remains bound to the old observation and fails the next
dependency gate until explicitly regenerated or revalidated by an integration.

`PlanStore.lookup` reads the entry and supply observations in one SQLite read
transaction. It returns fresh Python objects, so a caller cannot mutate the
persisted plan accidentally. Other processes' writes are visible to later reads.
Old entry revisions are archived on replacement. SQLite methods use separate
connections; there is no process-local cache to fall out of sync.

## Required dependencies versus opportunities

Required supply that is stale, failed, malformed, from a changed source, or absent
blocks reuse. The same problems in an unrelated supply are reported under
`opportunity_uncertainties`. They do not disable unchanged execution dependencies.
A new unbound Skill creates an unverified review opportunity, not proof that the
old plan should be replaced.

`assess_plan_impact` only reports evidence. `cache_reuse_decision` is a separate,
opt-in conservative policy. Neither authorizes business execution. This package
has no business executor and no semantic compatibility proof.

## Remaining race boundary

A supplier can change again after lookup or while a task is executing. The package
does not lock remote services or provide distributed snapshot isolation. Production
integrations still need execution-time contract/permission checks and their own
concurrency policy for simultaneous plan writers. `put` is an explicit replacement,
not a distributed compare-and-swap or automatic revision promotion algorithm.
