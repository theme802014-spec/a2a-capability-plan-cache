# Capability Aware Agent Plan Cache

Reference implementation for a capability aware plan cache in multi-agent systems. The current release is v0.2.0.

The project explores a narrow question:

> When a user request is decomposed into an executable DAG, how can the system reuse that plan while still detecting changes in the agents and skills that supplied the plan?

The reference design keeps three objects separate:

- **Demand signature**: what the user is trying to accomplish, including constraints and ordering evidence.
- **Supply observation**: a normalized, secret-free snapshot of an Agent Card and its skills.
- **Plan evidence**: the cached DAG, its selected capabilities, contract fingerprints, and the supply observations used at planning time.

A later Agent Card observation can then produce a deterministic impact report:

```text
compatible_observed
candidate_replan
invalidated
unknown
```

The impact analyzer is deliberately shadow-only. It reports direct dependency changes and semantic review opportunities; a production caller must apply its own freshness, compatibility, authorization, rollout, and execution policy.

## Scope

Included:

- source-grounded demand extraction validation
- normalized Agent Card supply diffs
- dependency-aware plan impact classification
- small unit-testable Python modules
- design notes and limitations

Excluded:

- production service URLs and credentials
- user data, health records, response caches, and SQLite databases
- business-specific agent adapters
- an assertion of patent novelty or universal originality

The implementation is adapted from an independent 13B multi-agent system and reduced to a standalone reference package. The current release documents the mechanism and its observed boundaries; it does not claim that the full production gate or automatic replanning loop is complete.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
pytest -q
```

## Design notes

Start with [docs/architecture.md](docs/architecture.md), then read [docs/data-model.md](docs/data-model.md), [docs/lifecycle.md](docs/lifecycle.md), and [docs/incremental-invalidation.md](docs/incremental-invalidation.md). Run [examples/run_demo.py](examples/run_demo.py) to see the synthetic end-to-end flow. See [docs/evaluation.md](docs/evaluation.md), [docs/prior-art.md](docs/prior-art.md), and [docs/status.md](docs/status.md) for evidence and limits.

## License

Apache-2.0. See [LICENSE](LICENSE).
