"""Observed dependency impact, kept separate from reuse and execution policy."""
from __future__ import annotations

import math
from typing import Any, Callable

from .supply_changes import supply_delta


def supply_freshness(snapshot: dict, now: float, max_age: float = 120) -> str:
    if snapshot.get("refresh_status") == "failed":
        return "refresh_failed"
    observed_at = snapshot.get("observed_at")
    if (isinstance(observed_at, bool) or not isinstance(observed_at, (int, float))
            or not math.isfinite(observed_at)):
        return "unobserved"
    age = now - observed_at
    return "stale" if age > max_age or age < -5 else "fresh"


def assess_plan_impact(
    evidence: dict[str, Any],
    capability_getter: Callable[[str], dict | None],
    current_supplies: dict[str, dict],
    *, now: float, max_age: float = 120,
) -> dict:
    """Report observations; this function never executes or rewrites a plan.

    Capability getters return ``{'fingerprint': <contract digest>}``. Required
    supply uncertainty blocks reuse through the separate reuse policy. Unrelated
    uncertainty is retained as opportunity evidence, without disabling a valid
    plan. Card timestamps and source identities must be assigned by the observer.
    """
    if not math.isfinite(now) or not math.isfinite(max_age) or max_age <= 0:
        raise ValueError("finite time and positive freshness window required")
    removed, changed, unknown, opportunities, opportunity_unknown = set(), set(), set(), set(), set()
    affected = set()
    dependencies = evidence.get("dependencies") or []
    previous = evidence.get("supplies") or {}
    if not dependencies:
        unknown.add("plan_dependencies_missing")
    for dep in dependencies:
        capability_id = str(dep.get("capability") or "")
        capability = capability_getter(capability_id)
        if not capability:
            removed.add(f"capability_removed:{capability_id}")
            affected.add(str(dep.get("step_id")))
        elif not dep.get("contract_fingerprint"):
            unknown.add(f"contract_unobserved:{capability_id}")
        elif capability.get("fingerprint") != dep["contract_fingerprint"]:
            changed.add(f"manifest_changed:{capability_id}")
            affected.add(str(dep.get("step_id")))

    required_domains = {d.get("domain") for d in dependencies} - {None, ""}
    for domain in sorted(required_domains | set(previous) | set(current_supplies)):
        old, new = previous.get(domain), current_supplies.get(domain)
        required = domain in required_domains
        uncertainty = unknown if required else opportunity_unknown
        if not old or not new:
            if required:
                uncertainty.add(f"card_unobserved:{domain}")
            elif not new:
                uncertainty.add(f"opportunity_supply_unobserved:{domain}")
            else:
                freshness = supply_freshness(new, now, max_age)
                if freshness != "fresh":
                    uncertainty.add(f"card_{freshness}:{domain}")
                else:
                    try:
                        supply_delta(None, new)
                        opportunities.add(f"new_supply_needs_semantic_review:{domain}")
                    except (ValueError, TypeError):
                        uncertainty.add(f"card_malformed:{domain}")
            continue
        if old.get("domain") != domain or new.get("domain") != domain:
            uncertainty.add(f"card_domain_mismatch:{domain}")
            continue
        freshness = supply_freshness(new, now, max_age)
        if freshness != "fresh":
            uncertainty.add(f"card_{freshness}:{domain}")
            continue
        if not old.get("source_id") or old.get("source_id") != new.get("source_id"):
            uncertainty.add(f"card_source_changed:{domain}")
            continue
        try:
            delta = supply_delta(old, new)
        except (TypeError, ValueError):
            uncertainty.add(f"card_malformed:{domain}")
            continue
        bound = {d.get("skill_id") for d in dependencies if d.get("domain") == domain} - {None, ""}
        if required and not bound:
            unknown.add(f"bound_skill_unknown:{domain}")
        missing = bound - set(new["skills"])
        modified = bound & set(delta["modified_skills"])
        if missing:
            removed.add(f"bound_skill_removed:{domain}")
        if modified:
            changed.add(f"bound_skill_changed:{domain}")
        global_change = bool(delta["global_fields"] or delta["version_changed"])
        if required and delta["global_fields"]:
            changed.add(f"card_global_fields_changed:{domain}")
        if required and delta["version_changed"]:
            changed.add(f"card_version_changed:{domain}")
        for dep in dependencies:
            if dep.get("domain") == domain and (dep.get("skill_id") in missing | modified or global_change):
                affected.add(str(dep.get("step_id")))
        if delta["added_skills"] or set(delta["modified_skills"]) - bound:
            opportunities.add(f"supply_change_needs_semantic_review:{domain}")
        if not required and global_change:
            opportunities.add(f"planning_environment_changed:{domain}")

    decision = ("invalidated" if removed else "candidate_replan" if changed or opportunities
                else "unknown" if unknown else "compatible_observed")
    return {
        "schema": "planning-impact/v1", "mode": "shadow", "decision": decision,
        "reasons": sorted(removed | changed | opportunities | unknown),
        "directly_affected_steps": sorted(affected),
        "semantic_review_required": bool(opportunities),
        "uncertainties": sorted(unknown), "opportunity_uncertainties": sorted(opportunity_unknown),
        "execution_effect": "none", "compatibility_scope": "observed_dependency_fields_only",
    }
