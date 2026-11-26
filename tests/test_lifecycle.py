"""SQLite-isolated integration tests; deterministic time, no model or HTTP."""
import copy
import math
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from capability_plan_cache import (
    PlanStore, PlanningReviewQueue, assess_plan_impact, cache_reuse_decision,
    exact_request_key, make_plan_cache_entry, rebind_plan,
)


def supply(domain="community", version="1"):
    return {"domain": domain, "card_version": version, "source_id": "synthetic-" + domain,
            "observed_at": 1000, "refresh_status": "ok",
            "skills": {"task.handle": {"description": "Synthetic public task"}}}


def entry_for(store, domains=("community",)):
    return make_plan_cache_entry(original_query="Synthetic question?", demand_signature={},
        steps=[{"id": "s" + str(i), "inputs": {"query": "$request.query"}, "depends_on": []}
               for i, _ in enumerate(domains)],
        dependencies=[{"step_id": "s" + str(i), "domain": d, "capability": d,
                       "skill_id": "task.handle", "contract_fingerprint": "contract"}
                      for i, d in enumerate(domains)], supply_snapshots=store.snapshot())


def getter(_):
    return {"fingerprint": "contract"}


@pytest.fixture
def state(tmp_path):
    clock = [1000.0]
    store = PlanStore(tmp_path / "plans.db", clock=lambda: clock[0])
    store.observe("community", supply())
    store.observe("health", supply("health"))
    store.put("key", entry_for(store))
    return store, clock


def test_restart_version_change_replan_rollback_history(state):
    store, clock = state
    reopened = PlanStore(store.path, clock=lambda: clock[0])
    assert reopened.lookup("key", getter)["entry"]
    reopened.observe("community", supply(version="2"))
    assert reopened.lookup("key", getter)["entry"] is None
    queue = PlanningReviewQueue(store.path, clock=lambda: clock[0])
    assert queue.stats()["kinds"] == {"dependency_review": 1}
    replacement = entry_for(reopened)
    replacement["revision"] = 2
    reopened.put("key", replacement)
    assert queue.stats()["statuses"] == {"superseded": 1}
    assert store.lookup("key", getter)["entry"]["revision"] == 2
    reopened.observe("community", supply(version="1"))
    assert store.lookup("key", getter)["entry"] is None
    reopened.put("key", entry_for(reopened))
    assert store.lookup("key", getter)["entry"]
    assert store.history_count() == 2


def test_generation_race_does_not_relabel_evidence(state):
    store, _ = state
    captured = entry_for(store)
    store.observe("community", supply(version="2"))
    store.put("key", captured)
    result = store.lookup("key", getter)
    assert result["entry"] is None
    assert "card_version_changed:community" in result["assessment"]["reasons"]


@pytest.mark.parametrize("bad", ["stale", "source", "malformed", "failed"])
def test_unrelated_bad_supply_does_not_block_required_domains(state, bad):
    store, _ = state
    current = store.snapshot()
    old = copy.deepcopy(current)
    if bad == "stale":
        current["health"]["observed_at"] = 0
    elif bad == "source":
        current["health"]["source_id"] = "other"
    elif bad == "malformed":
        current["health"]["skills"] = "invalid"
    else:
        current["health"]["refresh_status"] = "failed"
    e = entry_for(store)
    result = assess_plan_impact({"dependencies": e["dependencies"], "supplies": old}, getter, current, now=1000)
    assert result["uncertainties"] == []
    assert result["opportunity_uncertainties"]
    assert cache_reuse_decision(result)["reuse"]
    # The identical failure becomes blocking when health is an actual dependency.
    result = assess_plan_impact({"dependencies": entry_for(store, ("health",))["dependencies"],
                                "supplies": old}, getter, current, now=1000)
    assert not cache_reuse_decision(result)["reuse"]


def test_new_unbound_skill_only_queues_opportunity(state):
    store, clock = state
    changed = supply()
    changed["skills"]["new.skill"] = {"description": "Possible future use"}
    store.observe("community", changed)
    hit = store.lookup("key", getter)
    assert hit["entry"] and hit["policy"]["opportunity"]
    queue = PlanningReviewQueue(store.path, clock=lambda: clock[0])
    assert queue.stats()["kinds"] == {"opportunity_review": 1}
    assert queue.stats()["automatic_replanning"] is False
    store.observe("community", changed)
    assert queue.stats()["total"] == 1


def test_direct_change_only_marks_bound_step_in_full_dag(state):
    store, _ = state
    store.put("full", entry_for(store, ("health", "community")))
    changed = supply()
    changed["skills"]["task.handle"]["description"] = "Changed public task"
    store.observe("community", changed)
    result = store.lookup("full", getter)
    assert result["assessment"]["directly_affected_steps"] == ["s1"]
    assert not result["policy"]["reuse"]


def test_missing_skill_invalidates_but_contract_change_is_review_candidate(state):
    store, _ = state
    changed = supply()
    changed["skills"] = {}
    store.observe("community", changed)
    assert store.lookup("key", getter)["assessment"]["decision"] == "invalidated"
    store.observe("community", supply())
    result = store.lookup("key", lambda _: {"fingerprint": "changed"})
    assert result["assessment"]["decision"] == "candidate_replan"
    assert not result["policy"]["reuse"]


def test_required_failure_retains_snapshot_but_blocks_reuse(state):
    store, clock = state
    store.observe_failure("community", "TimeoutError")
    assert store.snapshot()["community"]["skills"] == supply()["skills"]
    assert not store.lookup("key", getter)["policy"]["reuse"]
    with pytest.raises(ValueError):
        store.observe_failure("community", "secret message or URL")
    clock[0] += 500
    store.observe("community", supply())
    assert store.lookup("key", getter)["policy"]["reuse"]


@pytest.mark.parametrize("timestamp", [float("nan"), float("inf"), True, "1000", -9999])
def test_invalid_time_does_not_confirm_freshness(state, timestamp):
    store, _ = state
    current = store.snapshot()
    current["community"]["observed_at"] = timestamp
    e = entry_for(store)
    result = assess_plan_impact({"dependencies": e["dependencies"], "supplies": e["supply_snapshots"]},
                                getter, current, now=1000)
    assert not cache_reuse_decision(result)["reuse"]


def test_rebind_is_input_only_and_fails_missing_slot(state):
    store, _ = state
    e = entry_for(store)
    e["workflow"]["steps"][0]["description"] = "$request.query"
    bound = rebind_plan(e, {"request": {"query": "new current value"}})
    assert bound["workflow"]["steps"][0]["inputs"] == {"query": "new current value"}
    assert bound["workflow"]["steps"][0]["description"] == "$request.query"
    assert e["workflow"]["steps"][0]["inputs"] == {"query": "$request.query"}
    with pytest.raises(ValueError):
        rebind_plan(e, {"request": {}})


@pytest.mark.parametrize("left,right", [("1.5元", "15元"), ("-5度", "5度"),
    ("1/2", "12"), ("商品A", "商品a"), ("先查A，再查B", "先查A再查B")])
def test_exact_key_preserves_significant_information(left, right):
    assert exact_request_key(left) != exact_request_key(right)


def test_empty_dependency_or_missing_contract_does_not_authorize_reuse(state):
    store, _ = state
    e = entry_for(store)
    e["dependencies"] = []
    store.put("bad", e)
    assert store.lookup("bad", getter)["entry"] is None
    e = entry_for(store)
    e["dependencies"][0].pop("contract_fingerprint")
    store.put("bad", e)
    assert store.lookup("bad", getter)["entry"] is None


def test_lease_guards_expiry_retries_and_revision_replacement(state):
    store, clock = state
    store.observe("community", supply(version="2"))
    queue = PlanningReviewQueue(store.path, clock=lambda: clock[0])
    task = queue.claim(lease_seconds=2)[0]
    assert not queue.finish(task["task_id"], "wrong", decision="no_change", reviewer="business_owner")
    clock[0] += 3
    assert not queue.finish(task["task_id"], task["lease_token"], decision="no_change", reviewer="business_owner")
    next_task = queue.claim()[0]
    assert next_task["attempts"] == 2
    store.put("key", entry_for(store))
    assert not queue.finish(next_task["task_id"], next_task["lease_token"], decision="needs_replan", reviewer="business_owner")
    assert queue.stats()["statuses"] == {"superseded": 1}


def test_failed_supply_cannot_be_reviewed_as_current(state):
    store, clock = state
    store.observe("community", supply(version="2"))
    queue = PlanningReviewQueue(store.path, clock=lambda: clock[0])
    task = queue.claim()[0]
    store.observe_failure("community", "ConnectError")
    assert not queue.finish(task["task_id"], task["lease_token"], decision="no_change", reviewer="business_owner")


def test_two_consumers_cannot_claim_same_task(state):
    store, clock = state
    store.observe("community", supply(version="2"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: PlanningReviewQueue(store.path, clock=lambda: clock[0]).claim(), range(2)))
    assert sorted(map(len, results)) == [0, 1]


def test_review_records_provenance_without_modifying_plan(state):
    store, clock = state
    store.observe("community", supply(version="2"))
    queue = PlanningReviewQueue(store.path, clock=lambda: clock[0])
    task = queue.claim()[0]
    assert queue.finish(task["task_id"], task["lease_token"], decision="needs_replan", reviewer="deterministic_contract")
    assert queue.stats()["statuses"] == {"reviewed": 1}
    assert store.lookup("key", getter)["entry"] is None


def test_read_results_are_not_shared_mutable_state(state):
    store, _ = state
    store.lookup("key", getter)["entry"]["workflow"]["steps"].clear()
    assert store.lookup("key", getter)["entry"]["workflow"]["steps"]


def test_repeated_version_transition_gets_new_review_event(state):
    store, clock = state
    queue = PlanningReviewQueue(store.path, clock=lambda: clock[0])
    store.observe("community", supply(version="2"))
    store.observe("community", supply(version="1"))
    store.observe("community", supply(version="2"))
    assert queue.stats()["total"] == 2  # v1 return matches saved plan; no work
    assert queue.stats()["statuses"] == {"pending": 1, "superseded": 1}


def test_failure_before_baseline_then_success_is_recoverable(tmp_path):
    store = PlanStore(tmp_path / "recover.db", clock=lambda: 1000)
    store.observe_failure("community", "ConnectError")
    store.observe("community", supply())
    store.put("new", entry_for(store))
    assert store.lookup("new", getter)["entry"]
    assert PlanningReviewQueue(store.path).stats()["total"] == 0


def test_review_priority_failure_retry_budget_and_late_supply(state):
    store, clock = state
    # Health update creates an opportunity for community-bound request.
    changed = supply("health")
    changed["skills"]["new"] = {}
    store.observe("health", changed)
    store.observe("community", supply(version="2"))
    queue = PlanningReviewQueue(store.path, clock=lambda: clock[0])
    tasks = queue.claim(limit=2, max_attempts=2)
    assert [task["kind"] for task in tasks] == ["dependency_review", "opportunity_review"]
    direct = tasks[0]
    assert queue.finish(direct["task_id"], direct["lease_token"], error_type="RuntimeError")
    assert queue.retry(direct["task_id"], max_attempts=2)
    second = queue.claim(max_attempts=2)[0]
    assert second["attempts"] == 2
    assert queue.finish(second["task_id"], second["lease_token"], error_type="RuntimeError")
    assert not queue.retry(second["task_id"], max_attempts=2)
    old_opportunity = tasks[1]
    store.observe("health", supply("health", version="2"))
    assert not queue.finish(old_opportunity["task_id"], old_opportunity["lease_token"],
                            decision="no_change", reviewer="business_owner")


def test_pending_addition_survives_next_unrelated_card_change(state):
    store, clock = state
    changed = supply()
    changed["skills"].update({"new": {}, "unused": {}})
    store.observe("community", changed)
    changed["skills"].pop("unused")
    store.observe("community", changed)
    queue = PlanningReviewQueue(store.path, clock=lambda: clock[0])
    assert queue.stats()["statuses"] == {"superseded": 1, "pending": 1}
    assert queue.claim()[0]["kind"] == "opportunity_review"
