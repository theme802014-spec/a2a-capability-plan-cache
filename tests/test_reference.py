from capability_plan_cache import assess_plan_impact, extract_demand_record, supply_delta


def test_demand_record_requires_verbatim_evidence():
    record = extract_demand_record(
        "先读取我的档案，再分析睡眠",
        {
            "goals": [{"id": "g1", "operation": "read", "target": "读取档案", "evidence": "读取我的档案"}],
            "constraints": [],
            "stored_profile": {"usage": "requested", "evidence": "我的档案"},
            "ordering": [],
        },
    )
    assert record["semantic_extraction"] == "model_extracted_unverified"
    assert record["goals"][0]["evidence"] == "读取我的档案"


def test_supply_delta_is_field_level_and_secret_free():
    old = {"card_version": "1", "skills": {"health.read": {"description": "read"}}}
    new = {"card_version": "2", "skills": {"health.read": {"description": "read v2"}, "health.analyze": {}}}
    delta = supply_delta(old, new)
    assert delta["added_skills"] == ["health.analyze"]
    assert delta["modified_skills"] == {"health.read": ["description"]}
    assert delta["version_changed"] is True


def test_impact_distinguishes_direct_changes_from_new_opportunities():
    old_supply = {
        "domain": "health",
        "source_id": "same",
        "observed_at": 100.0,
        "refresh_status": "ok",
        "card_version": "1",
        "skills": {"health.read": {"description": "read"}},
    }
    current = {
        "health": {
            "domain": "health",
            "source_id": "same",
            "observed_at": 100.0,
            "refresh_status": "ok",
            "card_version": "2",
            "skills": {"health.read": {"description": "read v2"}, "health.analyze": {}},
        }
    }
    result = assess_plan_impact(
        {"dependencies": [{"step_id": "s1", "capability": "health.read", "skill_id": "health.read", "domain": "health"}], "supplies": {"health": old_supply}},
        lambda _: {"fingerprint": "same-contract"},
        current,
        now=100.0,
    )
    assert result["decision"] == "candidate_replan"
    assert result["directly_affected_steps"] == ["s1"]
    assert result["semantic_review_required"] is True
