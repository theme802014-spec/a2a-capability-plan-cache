"""Persistent lifecycle using a deterministic planner stub, never an LLM."""
import copy
import json
import tempfile
from pathlib import Path

from capability_plan_cache import PlanStore, PlanningReviewQueue, exact_request_key
from run_demo import fixtures


def run(path):
    now = 1100.0
    store = PlanStore(path, clock=lambda: now)
    entry, _, contracts = fixtures()
    for domain, supply in entry["supply_snapshots"].items():
        store.observe(domain, supply)
    key = "demo-planner-v1:" + exact_request_key(entry["original_query"])
    rows = []
    # In a real integration, capture supplies before calling the planner.
    captured = store.snapshot()
    entry["supply_snapshots"] = captured
    store.put(key, entry)  # synthetic planner stub output
    rows.append({"phase": "initial_plan", "planner_stub_calls": 1})
    reopened = PlanStore(path, clock=lambda: now)
    assert reopened.lookup(key, contracts.get)["entry"] is not None
    rows.append({"phase": "restart_hit", "planner_stub_calls": 0})

    # An unrelated supplier outage does not block the full DAG.
    reopened.observe_failure("catalog", "TimeoutError")
    hit = reopened.lookup(key, contracts.get)
    assert hit["entry"] is not None
    rows.append({"phase": "unrelated_failure", "reuse": True,
                 "opportunity_uncertainties": hit["assessment"]["opportunity_uncertainties"]})

    # Freeze evidence BEFORE the synthetic model returns; update during planning.
    changed = copy.deepcopy(captured["community"])
    changed["card_version"] = "2"
    reopened.observe("community", changed)
    blocked = reopened.lookup(key, contracts.get)
    assert blocked["entry"] is None
    queue = PlanningReviewQueue(path, clock=lambda: now)
    rows.append({"phase": "version_change", "reuse": False, "queue": queue.stats()})

    # Old captured evidence cannot be relabelled with the new Card by put().
    reopened.put(key, entry)
    assert reopened.lookup(key, contracts.get)["entry"] is None
    rows.append({"phase": "old_generation_evidence", "reuse": False})

    next_entry = copy.deepcopy(entry)
    next_entry["supply_snapshots"] = reopened.snapshot()
    next_entry["revision"] = 2
    reopened.put(key, next_entry)  # explicit synthetic replan, not queue auto-action
    assert reopened.lookup(key, contracts.get)["entry"] is not None
    rows.append({"phase": "explicit_replan_then_hit", "planner_stub_calls": 1,
                 "history_revisions": reopened.history_count(), "queue": queue.stats()})
    return rows


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as folder:
        print(json.dumps(run(Path(folder) / "demo.db"), indent=2))
