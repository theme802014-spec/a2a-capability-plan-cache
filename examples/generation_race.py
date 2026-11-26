"""Isolate a Card update during planning; the stale generation must not pass."""
import copy
import tempfile
from pathlib import Path
from capability_plan_cache import PlanStore
from run_demo import fixtures

with tempfile.TemporaryDirectory() as folder:
    store = PlanStore(Path(folder) / "race.db", clock=lambda: 1100)
    entry, _, contracts = fixtures()
    for domain, card in entry["supply_snapshots"].items():
        store.observe(domain, card)
    before_generation = store.snapshot()
    new = copy.deepcopy(before_generation["community"])
    new["card_version"] = "2"
    store.observe("community", new)
    entry["supply_snapshots"] = before_generation
    store.put("race", entry)
    result = store.lookup("race", contracts.get)
    assert result["entry"] is None
    print("Captured Card v1; current Card v2; old-generation plan blocked.")
