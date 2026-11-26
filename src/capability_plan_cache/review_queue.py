"""Durable Card-change review tasks. Reviews never authorize or replace a DAG.

Direct dependency checks and new-supply opportunities are separate priorities.
All original requests stay in planner_knowledge; tasks refer to a frozen revision.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from collections import Counter
from contextlib import contextmanager

from .supply_changes import supply_delta
from .impact import supply_freshness


def revision(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def ensure_schema(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS planner_review_tasks (
            task_id TEXT PRIMARY KEY, event_id TEXT NOT NULL, domain TEXT NOT NULL,
            cache_key TEXT NOT NULL, plan_revision TEXT NOT NULL,
            supply_revision TEXT NOT NULL, priority INTEGER NOT NULL,
            kind TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0, lease_token TEXT, lease_until REAL,
            reasons_json TEXT NOT NULL, result_json TEXT, last_error_type TEXT,
            created_at REAL NOT NULL, updated_at REAL NOT NULL,
            UNIQUE(event_id, cache_key, plan_revision)
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_planner_review_status ON planner_review_tasks(status, priority, created_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_planner_review_domain ON planner_review_tasks(domain, status)")


def record_card_change(db, event_id, domain, previous, current, delta, *, now=None):
    """Run in the observation transaction, once per changed Card, without a model.

    Opportunities deliberately include other domains: old bindings must not hide
    unfulfilled cross-domain demands. These are unreviewed candidates, not matches.
    """
    now = time.time() if now is None else now
    ensure_schema(db)
    # First observation creates the baseline; it is not a change event.
    if previous is None:
        return
    db.execute("""UPDATE planner_review_tasks SET status='superseded',
        lease_token=NULL, lease_until=NULL, updated_at=?
        WHERE domain=? AND status IN ('pending','reviewing','failed')""", (now, domain))
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='planner_knowledge'").fetchone():
        return
    for key, raw in db.execute("SELECT cache_key, value_json FROM planner_knowledge").fetchall():
        # Feature entries derive from the exact plan; do not review it twice.
        if ':feature:' in key:
            continue
        try:
            value = json.loads(raw)
            deps = value.get('dependencies', [])
            bound = {dep.get('skill_id') for dep in deps if dep.get('domain') == domain}
        except (ValueError, AttributeError, TypeError):
            continue
        # Compare against THIS plan's captured supply, not only the latest
        # transition; otherwise a second change can erase an unreviewed addition.
        baseline = value.get('supply_snapshots', {}).get(domain) or previous
        try:
            plan_delta = supply_delta(baseline, current)
        except (ValueError, TypeError):
            plan_delta = delta
        source_changed = (baseline or {}).get('source_id') != current.get('source_id')
        opportunity = bool(plan_delta['added_skills'] or plan_delta['modified_skills'] or
                           plan_delta['global_fields'] or plan_delta['version_changed'] or source_changed)
        reasons = []
        direct = bool(bound and (
            bound - set(current['skills']) or bound.intersection(plan_delta['modified_skills'])
            or (plan_delta['version_changed'] and baseline)
            or (plan_delta['global_fields'] and baseline)
            or (source_changed and baseline)))
        if direct:
            reasons.append('bound_dependency_changed')
        elif opportunity:
            reasons.append('new_or_changed_supply_candidate_unverified')
        else:
            continue
        db.execute("""INSERT OR IGNORE INTO planner_review_tasks (
            task_id,event_id,domain,cache_key,plan_revision,supply_revision,priority,
            kind,reasons_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (str(uuid.uuid4()), event_id, domain, key, revision(value),
             revision([current.get('source_id'), current['fingerprint']]), 0 if direct else 1,
             'dependency_review' if direct else 'opportunity_review',
             json.dumps(reasons), now, now))


def supersede_replaced_plan(db, key, value, *, now=None):
    """Late reviews must not overwrite a newer plan, even with the same cache key."""
    ensure_schema(db)
    db.execute("""UPDATE planner_review_tasks SET status='superseded',
        lease_token=NULL,lease_until=NULL,updated_at=?
        WHERE cache_key=? AND plan_revision<>? AND status IN ('pending','reviewing','failed')""",
        (time.time() if now is None else now, key, revision(value)))


class PlanningReviewQueue:
    """An opt-in consumer can lease tasks; no background model execution here."""
    def __init__(self, database_path, *, clock=time.time, max_age=120):
        self.path = str(database_path)
        self.clock = clock
        self.max_age = max_age
        with self._connect() as db:
            ensure_schema(db)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def stats(self):
        with self._connect() as db:
            rows = db.execute("SELECT status,kind,COUNT(*) AS n FROM planner_review_tasks GROUP BY status,kind").fetchall()
        statuses, kinds = Counter(), Counter()
        for row in rows:
            statuses[row['status']] += row['n']
            kinds[row['kind']] += row['n']
        return {'total': sum(statuses.values()), 'statuses': dict(statuses), 'kinds': dict(kinds),
                'automatic_replanning': False}

    def claim(self, *, limit=1, lease_seconds=60, max_attempts=3):
        if not 1 <= limit <= 100 or not 1 <= lease_seconds <= 3600 or not 1 <= max_attempts <= 100:
            raise ValueError('invalid review lease limits')
        now = self.clock()
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("""UPDATE planner_review_tasks SET status=CASE WHEN attempts>=? THEN 'failed' ELSE 'pending' END,
                lease_token=NULL,lease_until=NULL,updated_at=? WHERE status='reviewing' AND lease_until<=?""",
                (max_attempts, now, now))
            # Direct dependency tasks first; event round-robin within a priority.
            rows = db.execute("""SELECT * FROM (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY priority,event_id ORDER BY created_at,task_id) AS turn,
                    COALESCE((SELECT MAX(other.updated_at) FROM planner_review_tasks other
                              WHERE other.event_id=planner_review_tasks.event_id AND other.attempts>0), 0) AS last_claimed
                FROM planner_review_tasks WHERE status='pending' AND attempts<?)
                ORDER BY priority,turn,last_claimed,created_at,task_id LIMIT ?""", (max_attempts, limit)).fetchall()
            tasks = []
            for row in rows:
                task = dict(row)
                token = str(uuid.uuid4())
                db.execute("""UPDATE planner_review_tasks SET status='reviewing', attempts=attempts+1,
                    lease_token=?,lease_until=?,updated_at=? WHERE task_id=?""",
                    (token, now + lease_seconds, now, task['task_id']))
                task.update(status='reviewing', lease_token=token, lease_until=now+lease_seconds,
                            attempts=task['attempts']+1)
                task.pop('turn', None)
                task.pop('last_claimed', None)
                tasks.append(task)
            return tasks

    def finish(self, task_id, lease_token, *, decision=None, reviewer=None, error_type=None):
        """Store a review only. Invalid/late leases cannot finish or change a plan."""
        if error_type is None and (decision not in {'no_change', 'needs_replan', 'unknown'} or
                                  reviewer not in {'business_owner', 'deterministic_contract', 'research_model'}):
            raise ValueError('review decision and provenance required')
        if error_type is not None and (not isinstance(error_type, str) or not error_type.isidentifier()):
            raise ValueError('store only exception class names')
        result = json.dumps({'decision': decision, 'reviewer': reviewer, 'execution_effect': 'none'})
        now = self.clock()
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            task = db.execute("SELECT * FROM planner_review_tasks WHERE task_id=?", (task_id,)).fetchone()
            if not task:
                return False
            plan = db.execute("SELECT value_json FROM planner_knowledge WHERE cache_key=?", (task['cache_key'],)).fetchone()
            if not plan or revision(json.loads(plan[0])) != task['plan_revision']:
                return False
            has_observations = db.execute("SELECT 1 FROM sqlite_master WHERE name='planner_supply_observations'").fetchone()
            if has_observations:
                row = db.execute("SELECT snapshot_json FROM planner_supply_observations WHERE domain=?", (task['domain'],)).fetchone()
                snapshot = json.loads(row[0]) if row else {}
                if (supply_freshness(snapshot, now, self.max_age) != 'fresh'
                        or revision([snapshot.get('source_id'), snapshot.get('fingerprint')]) != task['supply_revision']):
                    return False
            cursor = db.execute("""UPDATE planner_review_tasks SET status=?,result_json=?,last_error_type=?,
                lease_token=NULL,lease_until=NULL,updated_at=?
                WHERE task_id=? AND status='reviewing' AND lease_token=? AND lease_until>?""",
                ('failed' if error_type else 'reviewed', result, error_type, now, task_id, lease_token, now))
            return cursor.rowcount == 1

    def retry(self, task_id, *, max_attempts=3):
        if not 1 <= max_attempts <= 100:
            raise ValueError('invalid retry limit')
        with self._connect() as db:
            cursor = db.execute("""UPDATE planner_review_tasks SET status='pending', updated_at=?
                WHERE task_id=? AND status='failed' AND attempts<?""", (self.clock(), task_id, max_attempts))
            return cursor.rowcount == 1
