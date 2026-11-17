"""Deterministic impact analysis for cached agent plans.

This module deliberately reports observations and review candidates. It does not
claim semantic compatibility and does not authorize execution by itself.
"""
from __future__ import annotations

from typing import Any, Callable, Dict

from .supply_changes import supply_delta


def _freshness(snapshot: Dict[str, Any], now: float, max_age: float) -> str:
    if snapshot.get("refresh_status") == "failed":
        return "refresh_failed"
    observed_at = snapshot.get("observed_at")
    if not isinstance(observed_at, (int, float)) or isinstance(observed_at, bool):
        return "unobserved"
    age = now - observed_at
    return "stale" if age > max_age or age < -5 else "fresh"


def assess_plan_impact(
    evidence: Dict[str, Any],
    capability_getter: Callable[[str], Dict[str, Any] | None],
    current_supplies: Dict[str, Dict[str, Any]],
    *,
    now: float,
    max_age: float = 120,
) -> Dict[str, Any]:
    """Classify a cached plan against current capability observations.

    Results are one of ``compatible_observed``, ``candidate_replan``,
    ``invalidated``, or ``unknown``. The result is intentionally shadow-only:
    callers must apply their own policy and execution gate.
    """
    reasons, unknown, affected, opportunities = set(), set(), set(), set()
    dependencies = list(evidence.get("dependencies") or [])
    previous_supplies = evidence.get("supplies") or {}

    for dependency in dependencies:
        step_id = str(dependency.get("step_id") or "")
        capability_id = str(dependency.get("capability") or "")
        capability = capability_getter(capability_id)
        if not capability:
            reasons.add(f"capability_removed:{capability_id}")
            affected.add(step_id)
        elif dependency.get("contract_fingerprint") and capability.get("fingerprint") != dependency["contract_fingerprint"]:
            reasons.add(f"manifest_changed:{capability_id}")
            affected.add(step_id)

    required_domains = {str(item.get("domain")) for item in dependencies if item.get("domain")}
    for domain in sorted(required_domains | set(previous_supplies) | set(current_supplies)):
        old = previous_supplies.get(domain)
        new = current_supplies.get(domain)
        required = domain in required_domains
        if not new:
            if required:
                unknown.add(f"card_unobserved:{domain}")
            continue
        freshness = _freshness(new, now, max_age)
        if freshness == "refresh_failed":
            unknown.add(f"card_refresh_failed:{domain}")
            continue
        if freshness != "fresh":
            unknown.add(f"card_{freshness}:{domain}")
            continue
        if not old:
            opportunities.add(f"new_supply_needs_semantic_review:{domain}")
            continue
        if old.get("source_id") != new.get("source_id"):
            unknown.add(f"card_source_changed:{domain}")
            continue
        try:
            delta = supply_delta(old, new)
        except (TypeError, ValueError):
            unknown.add(f"card_malformed:{domain}")
            continue
        bound = {str(item.get("skill_id")) for item in dependencies if item.get("domain") == domain and item.get("skill_id")}
        missing = bound - set(new.get("skills") or {})
        modified = bound & set(delta.get("modified_skills") or {})
        if missing:
            reasons.add(f"bound_skill_removed:{domain}")
        if modified:
            reasons.add(f"bound_skill_changed:{domain}")
        if required and delta.get("global_fields"):
            reasons.add(f"card_global_fields_changed:{domain}")
        if required and delta.get("version_changed"):
            reasons.add(f"card_version_changed:{domain}")
        if missing or modified or delta.get("global_fields") or delta.get("version_changed"):
            affected.update(str(item.get("step_id")) for item in dependencies if item.get("domain") == domain)
        if set(delta.get("added_skills") or {}) - bound or set(delta.get("modified_skills") or {}) - bound:
            opportunities.add(f"supply_change_needs_semantic_review:{domain}")

    if any(item.startswith(("capability_removed", "manifest_changed", "bound_skill_removed")) for item in reasons):
        decision = "invalidated"
    elif reasons or opportunities:
        decision = "candidate_replan"
    elif unknown:
        decision = "unknown"
    else:
        decision = "compatible_observed"
    return {
        "schema": "planning-impact/v1",
        "mode": "shadow",
        "decision": decision,
        "reasons": sorted(reasons | opportunities | unknown),
        "directly_affected_steps": sorted(affected),
        "semantic_review_required": bool(opportunities),
        "uncertainties": sorted(unknown),
        "execution_effect": "none",
        "compatibility_scope": "observed_dependency_fields_only",
    }
