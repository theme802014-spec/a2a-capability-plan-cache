"""A conservative opt-in policy for plan reuse, not business authorization."""


def cache_reuse_decision(assessment: dict) -> dict:
    decision = assessment.get("decision")
    if assessment.get("uncertainties") or decision == "unknown":
        return {"reuse": False, "opportunity": False, "reason": "required_supply_unknown"}
    if decision == "compatible_observed":
        return {"reuse": True, "opportunity": False, "reason": "observed_dependencies_unchanged"}
    reasons = assessment.get("reasons") or []
    allowed = ("supply_change_needs_semantic_review:", "new_supply_needs_semantic_review:",
               "planning_environment_changed:")
    if (decision == "candidate_replan" and not assessment.get("directly_affected_steps")
            and reasons and all(str(r).startswith(allowed) for r in reasons)):
        return {"reuse": True, "opportunity": True, "reason": "opportunity_pending"}
    return {"reuse": False, "opportunity": False, "reason": "dependency_changed_or_unproven"}


def exact_request_key(query: str) -> str:
    """Only trim trailing question punctuation; preserve decimals/signs/case."""
    value = query.strip().rstrip("。？！!?").strip()
    if not value:
        raise ValueError("nonempty request required")
    return "exact-v2:" + value
