"""Deterministic changes in observed Card fields, not semantic compatibility proofs."""
from __future__ import annotations

import json


def _same(left, right):
    # JSON persistence turns tuples into lists; compare the serialized contract.
    return json.dumps(left, sort_keys=True, ensure_ascii=False) == json.dumps(right, sort_keys=True, ensure_ascii=False)


def supply_delta(previous, current):
    """Return identifiers/field names only, without echoing descriptions or inputs.

    Compare content rather than trusting the publisher's version bump or stored
    aggregate hash. Callers must separately establish freshness and source identity.
    """
    if not isinstance(current, dict) or not isinstance(current.get("skills"), dict):
        raise ValueError("Malformed current supply observation")
    if any(not isinstance(k, str) or not isinstance(v, dict) for k, v in current["skills"].items()):
        raise ValueError("Malformed skill observation")
    if previous is None:
        return {"schema": "planning-supply-delta/v1", "baseline_available": False,
                "added_skills": sorted(current["skills"]), "removed_skills": [],
                "modified_skills": {}, "global_fields": [], "version_changed": False}
    if not isinstance(previous, dict) or not isinstance(previous.get("skills"), dict):
        raise ValueError("Malformed previous supply observation")
    old, new = previous["skills"], current["skills"]
    modified = {}
    for skill_id in sorted(set(old) & set(new)):
        if not isinstance(old[skill_id], dict) or not isinstance(new[skill_id], dict):
            raise ValueError("Malformed skill observation")
        fields = [field for field in sorted(set(old[skill_id]) | set(new[skill_id]))
                  if not _same(old[skill_id].get(field), new[skill_id].get(field))]
        if fields:
            modified[skill_id] = fields
    fields = [field for field in ("card_name", "card_description", "card_exposure",
                                  "defaultInputModes", "defaultOutputModes", "interfaces")
              if not _same(previous.get(field), current.get(field))]
    return {"schema": "planning-supply-delta/v1", "baseline_available": True,
            "added_skills": sorted(set(new) - set(old)), "removed_skills": sorted(set(old) - set(new)),
            "modified_skills": modified, "global_fields": fields,
            "version_changed": previous.get("card_version") != current.get("card_version")}
