"""Full-DAG impact demonstration; synthetic observations, no network/model calls."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from capability_plan_cache import assess_plan_impact, make_plan_cache_entry, rebind_plan, supply_delta

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))


def fixtures():
    request = load("sleep-community-request.json")
    old, new = load("agent-card-v1.json"), load("agent-card-v2.json")
    health = {
        "domain": "health", "card_version": "1", "source_id": "synthetic-health",
        "observed_at": 1100, "refresh_status": "ok", "skills": {
            "health.profile.read": {"description": "Read background"},
            "health.sleep.analyze": {"description": "Analyze sleep"},
        },
    }
    dependencies = [
        {"step_id": "s1", "domain": "health", "capability": "health.profile.read", "skill_id": "health.profile.read", "contract_fingerprint": "health-contract"},
        {"step_id": "s2", "domain": "health", "capability": "health.sleep.analyze", "skill_id": "health.sleep.analyze", "contract_fingerprint": "sleep-contract"},
        {"step_id": "s3", "domain": "community", "capability": "community.activity.recommend", "skill_id": "community.activity.recommend", "contract_fingerprint": "community-contract"},
    ]
    contracts = {dep["capability"]: {"fingerprint": dep["contract_fingerprint"]} for dep in dependencies}
    entry = make_plan_cache_entry(
        original_query=request["request"], demand_signature=request["demand_signature"],
        steps=request["steps"], dependencies=dependencies,
        supply_snapshots={"health": health, "community": old},
    )
    return entry, {"health": copy.deepcopy(health), "community": new}, contracts


def main():
    entry, current, contracts = fixtures()
    impact = assess_plan_impact({"dependencies": entry["dependencies"],
        "supplies": entry["supply_snapshots"]}, contracts.get, current, now=1100)
    rebound = rebind_plan(entry, {"request": {"query": entry["original_query"], "user_id": "synthetic-current-user"}})
    assert impact["directly_affected_steps"] == ["s3"]
    assert impact["uncertainties"] == []
    print(json.dumps({"scope": "all three DAG steps assessed; no business execution",
        "supply_delta": supply_delta(entry["supply_snapshots"]["community"], current["community"]),
        "rebound": rebound, "impact": impact}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
