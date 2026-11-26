"""SQLite reference store. No background planner, network, or business execution."""
from __future__ import annotations

import copy
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager

from .impact import assess_plan_impact
from .plan_cache import fingerprint
from .reuse_policy import cache_reuse_decision
from .review_queue import ensure_schema, record_card_change, supersede_replaced_plan
from .supply_changes import supply_delta


class PlanStore:
    """Explicit writes and guarded lookups, shared through SQLite across processes.

    Keys must encode the caller's planner version and context scope. Only use
    global exact keys for context-free plan templates, never personalized answers.
    Every method uses a new connection; there is no stale process-local hot cache.
    """
    def __init__(self, path, *, clock=time.time, max_age=120):
        self.path, self.clock, self.max_age = str(path), clock, max_age
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS planner_knowledge (cache_key TEXT PRIMARY KEY, value_json TEXT NOT NULL)")
            db.execute("""CREATE TABLE IF NOT EXISTS planner_version_history (
                id INTEGER PRIMARY KEY, cache_key TEXT NOT NULL, value_json TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS planner_supply_observations (
                domain TEXT PRIMARY KEY, snapshot_json TEXT NOT NULL)""")
            ensure_schema(db)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def snapshot(self):
        """Capture this before invoking a planner; pass it to the entry factory."""
        with self._connect() as db:
            return {domain: json.loads(raw) for domain, raw in db.execute(
                "SELECT domain,snapshot_json FROM planner_supply_observations")}

    def observe(self, domain, normalized_supply):
        """Persist a normalized observation and queue changes atomically.

        Supply fingerprints are recomputed locally. Observer time and source
        identity are not taken from untrusted Card fields in this reference API.
        """
        current = copy.deepcopy(normalized_supply)
        current.update(domain=domain, observed_at=self.clock(), refresh_status="ok")
        current.pop("last_error_type", None)
        content = {k: v for k, v in current.items() if k not in {
            "fingerprint", "observed_at", "refresh_status", "last_attempt_at"}}
        current["fingerprint"] = fingerprint(content)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT snapshot_json FROM planner_supply_observations WHERE domain=?", (domain,)).fetchone()
            previous = json.loads(row[0]) if row else None
            baseline = previous if previous and isinstance(previous.get("skills"), dict) else None
            delta = supply_delta(baseline, current)
            changed = baseline and (previous.get("fingerprint") != current["fingerprint"]
                                    or previous.get("source_id") != current.get("source_id"))
            db.execute("INSERT OR REPLACE INTO planner_supply_observations VALUES (?,?)",
                       (domain, json.dumps(current, ensure_ascii=False)))
            if changed:
                # A fresh event ID preserves repeated transitions and rollbacks.
                # Repeated identical observations create no work.
                event = str(uuid.uuid4())
                record_card_change(db, event, domain, baseline, current, delta, now=self.clock())
        return current

    def observe_failure(self, domain, error_type):
        if not isinstance(error_type, str) or not error_type.isidentifier():
            raise ValueError("exception class name required; do not store messages")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT snapshot_json FROM planner_supply_observations WHERE domain=?", (domain,)).fetchone()
            current = json.loads(row[0]) if row else {"domain": domain}
            current.update(refresh_status="failed", last_attempt_at=self.clock(), last_error_type=error_type)
            db.execute("INSERT OR REPLACE INTO planner_supply_observations VALUES (?,?)", (domain, json.dumps(current)))

    def put(self, key, entry):
        """Save captured planning evidence, never relabel it using current supply."""
        raw = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT value_json FROM planner_knowledge WHERE cache_key=?", (key,)).fetchone()
            if old and old[0] != raw:
                db.execute("INSERT INTO planner_version_history(cache_key,value_json) VALUES (?,?)", (key, old[0]))
            db.execute("INSERT OR REPLACE INTO planner_knowledge VALUES (?,?)", (key, raw))
            supersede_replaced_plan(db, key, entry, now=self.clock())

    def lookup(self, key, capability_getter):
        """Return an independent entry only if the observed-dependency gate permits."""
        with self._connect() as db:
            # Read the entry and all supplies from the same SQLite snapshot.
            db.execute("BEGIN")
            row = db.execute("SELECT value_json FROM planner_knowledge WHERE cache_key=?", (key,)).fetchone()
            supplies = {d: json.loads(raw) for d, raw in db.execute(
                "SELECT domain,snapshot_json FROM planner_supply_observations")}
        if not row:
            return {"entry": None, "policy": {"reuse": False, "reason": "miss"}, "assessment": None}
        entry = json.loads(row[0])
        assessment = assess_plan_impact({"dependencies": entry.get("dependencies", []),
            "supplies": entry.get("supply_snapshots", {})}, capability_getter, supplies,
            now=self.clock(), max_age=self.max_age)
        policy = cache_reuse_decision(assessment)
        return {"entry": entry if policy["reuse"] else None, "policy": policy, "assessment": assessment}

    def history_count(self):
        with self._connect() as db:
            return db.execute("SELECT COUNT(*) FROM planner_version_history").fetchone()[0]
