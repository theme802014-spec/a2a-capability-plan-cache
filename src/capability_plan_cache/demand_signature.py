"""Source-grounded demand records for observation, never cache equivalence proofs.

The planner extracts semantics in its existing call. Validation checks structure and
verbatim provenance only; it cannot prove interpretation or completeness.
"""
from __future__ import annotations

import copy
import hashlib
import json

SCHEMA = "planning-demand/v2"
EXTRACTOR_VERSION = "planner-demand-v2"
OPERATIONS = {"read", "query", "consult", "analyze", "recommend", "navigate", "compare", "other"}
CONSTRAINT_KINDS = {"current_condition", "budget", "location", "time", "prohibition", "other"}


def _fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def unavailable_demand(query, reason):
    return {"schema": SCHEMA, "extractor_version": EXTRACTOR_VERSION,
            "request_fingerprint": _fingerprint(query),
            "context_scope": "first_turn_without_external_context",
            "semantic_extraction": "unavailable", "reason": reason,
            "execution_effect": "none"}


def extract_demand_record(query, raw):
    """Accept bounded planner output, with evidence anchored in the current request.

    Missing/invalid extraction leaves the DAG usable. No Skill ID is inferred from
    the DAG and no additional model call or keyword classifier is introduced.
    """
    if raw is None:
        return unavailable_demand(query, "model_signature_missing")
    try:
        if not isinstance(query, str) or not isinstance(raw, dict):
            raise ValueError
        if set(raw) != {"goals", "constraints", "stored_profile", "ordering"}:
            raise ValueError

        def text(value, *, evidence=False):
            if not isinstance(value, str) or not value.strip() or len(value) > 500:
                raise ValueError
            if evidence and value not in query:
                raise ValueError
            return value

        def items(value):
            if not isinstance(value, list) or len(value) > 16:
                raise ValueError
            return value

        goals, identifiers = [], set()
        for goal in items(raw["goals"]):
            if not isinstance(goal, dict) or set(goal) != {"id", "operation", "target", "evidence"}:
                raise ValueError
            goal_id = text(goal["id"])
            if goal_id in identifiers or goal["operation"] not in OPERATIONS:
                raise ValueError
            identifiers.add(goal_id)
            goals.append({"id": goal_id, "operation": goal["operation"],
                          "target": text(goal["target"]), "evidence": text(goal["evidence"], evidence=True)})
        if not goals:
            raise ValueError
        constraints = []
        for constraint in items(raw["constraints"]):
            if (not isinstance(constraint, dict) or set(constraint) != {"kind", "evidence"}
                    or constraint["kind"] not in CONSTRAINT_KINDS):
                raise ValueError
            constraints.append({"kind": constraint["kind"],
                                "evidence": text(constraint["evidence"], evidence=True)})
        profile = raw["stored_profile"]
        if not isinstance(profile, dict) or set(profile) != {"usage", "evidence"}:
            raise ValueError
        if profile["usage"] not in {"requested", "forbidden", "unspecified"}:
            raise ValueError
        if profile["usage"] == "unspecified":
            if profile["evidence"] != "":
                raise ValueError
        else:
            text(profile["evidence"], evidence=True)
        ordering = []
        for edge in items(raw["ordering"]):
            if not isinstance(edge, dict) or set(edge) != {"before", "after", "evidence"}:
                raise ValueError
            if edge["before"] not in identifiers or edge["after"] not in identifiers or edge["before"] == edge["after"]:
                raise ValueError
            ordering.append({"before": edge["before"], "after": edge["after"],
                             "evidence": text(edge["evidence"], evidence=True)})
        # Reject cycles in declared user ordering, independently of executable DAG IDs.
        pending = set(identifiers)
        while pending:
            roots = {item for item in pending if not any(
                edge["after"] == item and edge["before"] in pending for edge in ordering)}
            if not roots:
                raise ValueError
            pending -= roots
        content = {"goals": goals, "constraints": constraints,
                   "stored_profile": copy.deepcopy(profile), "ordering": ordering}
        record = unavailable_demand(query, "")
        record.pop("reason")
        return {**record, **content, "semantic_extraction": "model_extracted_unverified",
                "validation": "structure_and_source_only",
                "record_fingerprint": _fingerprint(content)}
    except (ValueError, TypeError, KeyError):
        return unavailable_demand(query, "invalid_structure_or_source")


def demand_for_request(query, record):
    """A template hit must never relabel another request's extracted demand."""
    if not isinstance(record, dict) or record.get("request_fingerprint") != _fingerprint(query):
        return unavailable_demand(query, "no_extraction_for_current_request")
    if record.get("schema") != SCHEMA or record.get("extractor_version") != EXTRACTOR_VERSION:
        return unavailable_demand(query, "unsupported_signature_version")
    if record.get("semantic_extraction") == "model_extracted_unverified":
        checked = extract_demand_record(query, {key: record.get(key) for key in (
            "goals", "constraints", "stored_profile", "ordering")})
        if checked.get("record_fingerprint") != record.get("record_fingerprint"):
            return unavailable_demand(query, "stored_signature_validation_failed")
        return checked
    if record.get("semantic_extraction") != "unavailable":
        return unavailable_demand(query, "unsupported_extraction_status")
    return copy.deepcopy(record)
