"""Run the synthetic end-to-end impact example."""
from __future__ import annotations
import json
from pathlib import Path
from capability_plan_cache import assess_plan_impact, make_plan_cache_entry, rebind_plan, supply_delta
ROOT = Path(__file__).resolve().parents[1]
def load(name):
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))
def main():
    request, card_v1, card_v2 = load("sleep-community-request.json"), load("agent-card-v1.json"), load("agent-card-v2.json")
    entry = make_plan_cache_entry(original_query=request["request"], demand_signature=request["demand_signature"], steps=request["steps"], dependencies=[
        {"step_id":"s1","domain":"health","capability":"health.profile.read","skill_id":"health.profile.read","contract_fingerprint":"health-contract"},
        {"step_id":"s2","domain":"health","capability":"health.sleep.analyze","skill_id":"health.sleep.analyze","contract_fingerprint":"sleep-contract"},
        {"step_id":"s3","domain":"community","capability":"community.activity.recommend","skill_id":"community.activity.recommend","contract_fingerprint":"community-contract"}], supply_snapshots={"community":card_v1})
    rebound = rebind_plan(entry, {"request":{"query":request["request"],"user_id":"current-user"}})
    impact = assess_plan_impact({"dependencies":entry["dependencies"],"supplies":{"community":card_v1}}, lambda _: {"fingerprint":"community-contract"}, {"community":card_v2}, now=1100)
    print(json.dumps({"supply_delta":supply_delta(card_v1, card_v2),"rebound":rebound,"impact":impact}, ensure_ascii=False, indent=2))
if __name__ == "__main__": main()
