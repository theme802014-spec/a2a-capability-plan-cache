"""Plan cache evidence and safe current-request rebinding."""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict


def fingerprint(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_plan_cache_entry(*, original_query: str, demand_signature: Dict[str, Any], steps: list[Dict[str, Any]], dependencies: list[Dict[str, Any]], supply_snapshots: Dict[str, Any], planner_version: str = "planner-v1", revision: int = 1) -> Dict[str, Any]:
    """Create serializable plan evidence without answers or credentials."""
    workflow = {"steps": copy.deepcopy(steps)}
    return {
        "schema": "plan-cache-entry/v1",
        "entry_id": fingerprint({"query": original_query, "workflow": workflow})[:24],
        "original_query": original_query,
        "demand_signature": copy.deepcopy(demand_signature),
        "workflow": workflow,
        "dependencies": copy.deepcopy(dependencies),
        "supply_snapshots": copy.deepcopy(supply_snapshots),
        "planner_version": planner_version,
        "revision": revision,
        "status": "active",
        "plan_fingerprint": fingerprint(workflow),
    }


def rebind_plan(entry: Dict[str, Any], current_request: Dict[str, Any]) -> Dict[str, Any]:
    """Bind explicit ``$request.*`` values without mutating stored evidence."""
    request = current_request.get("request") or {}

    def replace(value: Any) -> Any:
        if isinstance(value, str) and value.startswith("$request."):
            key = value[len("$request."):]
            if key not in request:
                raise ValueError(f"missing current request slot: {key}")
            return copy.deepcopy(request[key])
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        if isinstance(value, list):
            return [replace(item) for item in value]
        return value

    def bind_inputs(workflow):
        for step in workflow.get("steps", []):
            step["inputs"] = replace(step.get("inputs", {}))
        return workflow

    return {"workflow": bind_inputs(copy.deepcopy(entry.get("workflow") or {"steps": []})), "request": copy.deepcopy(request), "source_entry_id": entry.get("entry_id")}
