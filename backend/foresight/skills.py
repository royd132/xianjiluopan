"""Skill Bank: versioned, retrievable, evaluable decision-skill assets.

A Skill is a reusable validation/check pattern distilled from successful runs,
human corrections, or explicit feedback. It is NOT a policy parameter tweak —
it is a named, scoped, auditable artifact that can be retrieved and injected
into future research tasks.

Lifecycle: feedback/correction -> candidate extract -> hybrid search existing ->
add/merge/discard -> versioned candidate store -> replay + holdout eval ->
human promotion gate -> active skill registry.
"""

from __future__ import annotations

from enum import StrEnum
import json
import math
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from pydantic import BaseModel, Field

from .harness import open_sqlite, stable_hash, utc_now


class SkillStatus(StrEnum):
    CANDIDATE = "candidate"
    READY = "ready"
    ACTIVE = "active"
    RETIRED = "retired"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# Skill Artifact Model
# ---------------------------------------------------------------------------

class SkillTrigger(BaseModel):
    keyword: str
    weight: float = 1.0


class SkillArtifact(BaseModel):
    skill_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str
    version: str = "0.1.0"
    scope_markets: list[str] = Field(default_factory=lambda: ["*"])
    scope_categories: list[str] = Field(default_factory=lambda: ["*"])
    triggers: list[SkillTrigger] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    evidence_policy: str = ""
    body: str = ""
    status: str = SkillStatus.CANDIDATE
    parent_id: str | None = None
    source_feedback_id: str | None = None
    created_at: str = Field(default_factory=lambda: utc_now())
    activated_at: str | None = None

    def matches_market(self, market: str) -> bool:
        return "*" in self.scope_markets or market.upper() in [m.upper() for m in self.scope_markets]

    def matches_category(self, category: str) -> bool:
        return "*" in self.scope_categories or any(
            cat.lower() in category.lower() for cat in self.scope_categories
        )

    def fingerprint(self) -> str:
        return stable_hash({
            "name": self.name,
            "description": self.description,
            "triggers": [t.model_dump() for t in self.triggers],
            "body": self.body,
            "evidence_policy": self.evidence_policy,
        })[:16]


# ---------------------------------------------------------------------------
# Skill Store (SQLite)
# ---------------------------------------------------------------------------

class SkillStore:
    """Persistent versioned skill registry with full-text search support."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = open_sqlite(self.path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS skills (
                    skill_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    version TEXT NOT NULL,
                    scope_markets TEXT NOT NULL DEFAULT '[]',
                    scope_categories TEXT NOT NULL DEFAULT '[]',
                    triggers_json TEXT NOT NULL DEFAULT '[]',
                    inputs_json TEXT NOT NULL DEFAULT '[]',
                    outputs_json TEXT NOT NULL DEFAULT '[]',
                    evidence_policy TEXT NOT NULL DEFAULT '',
                    body TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'candidate',
                    parent_id TEXT,
                    source_feedback_id TEXT,
                    fingerprint TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    activated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS skill_evaluations (
                    eval_id TEXT PRIMARY KEY,
                    skill_id TEXT NOT NULL,
                    baseline_skill_id TEXT,
                    split TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)

    def save(self, skill: SkillArtifact) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO skills(
                    skill_id, name, description, version, scope_markets, scope_categories,
                    triggers_json, inputs_json, outputs_json, evidence_policy, body,
                    status, parent_id, source_feedback_id, fingerprint, created_at, activated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    skill.skill_id,
                    skill.name,
                    skill.description,
                    skill.version,
                    json.dumps(skill.scope_markets),
                    json.dumps(skill.scope_categories),
                    json.dumps([t.model_dump() for t in skill.triggers]),
                    json.dumps(skill.inputs),
                    json.dumps(skill.outputs),
                    skill.evidence_policy,
                    skill.body,
                    skill.status,
                    skill.parent_id,
                    skill.source_feedback_id,
                    skill.fingerprint(),
                    skill.created_at,
                    skill.activated_at,
                ),
            )

    def get(self, skill_id: str) -> SkillArtifact | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM skills WHERE skill_id=?", (skill_id,)).fetchone()
        if not row:
            return None
        return self._row_to_skill(row)

    def list_all(self, status: str | None = None) -> list[SkillArtifact]:
        query = "SELECT * FROM skills"
        params: tuple[Any, ...] = ()
        if status:
            query += " WHERE status=?"
            params = (status,)
        query += " ORDER BY created_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_skill(row) for row in rows]

    def list_active(self) -> list[SkillArtifact]:
        return self.list_all(status=SkillStatus.ACTIVE)

    def find_by_name(self, name: str) -> list[SkillArtifact]:
        """Targeted lookup by name — avoids full-table scan."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM skills WHERE name=? ORDER BY created_at DESC", (name,)
            ).fetchall()
        return [self._row_to_skill(row) for row in rows]

    def status_counts(self) -> dict[str, int]:
        """Lightweight counter for health checks — no row deserialization."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM skills GROUP BY status"
            ).fetchall()
        counts = {row["status"]: row["cnt"] for row in rows}
        return {
            "total": sum(counts.values()),
            "active": counts.get(SkillStatus.ACTIVE, 0),
            "candidate": counts.get(SkillStatus.CANDIDATE, 0),
            "ready": counts.get(SkillStatus.READY, 0),
        }

    def activate(self, skill_id: str) -> SkillArtifact:
        skill = self.get(skill_id)
        if not skill:
            raise KeyError(skill_id)
        if skill.status not in {SkillStatus.READY, SkillStatus.ACTIVE}:
            raise ValueError(f"Skill {skill_id} has not passed evaluation (status={skill.status})")
        with self._connect() as conn:
            conn.execute(
                f"UPDATE skills SET status='{SkillStatus.RETIRED}' WHERE name=? AND status='{SkillStatus.ACTIVE}'",
                (skill.name,),
            )
            conn.execute(
                f"UPDATE skills SET status='{SkillStatus.ACTIVE}', activated_at=? WHERE skill_id=?",
                (utc_now(), skill_id),
            )
        return self.get(skill_id)  # type: ignore[return-value]

    def rollback(self, name: str) -> SkillArtifact:
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT * FROM skills WHERE name=? AND status IN ('{SkillStatus.ACTIVE}','{SkillStatus.RETIRED}')
                ORDER BY activated_at DESC LIMIT 2""",
                (name,),
            ).fetchall()
        if len(rows) < 2:
            raise ValueError(f"No parent version available for skill '{name}'")
        parent = self._row_to_skill(rows[1])
        with self._connect() as conn:
            conn.execute(
                f"UPDATE skills SET status='{SkillStatus.RETIRED}' WHERE name=? AND status='{SkillStatus.ACTIVE}'",
                (name,),
            )
            conn.execute(
                f"UPDATE skills SET status='{SkillStatus.ACTIVE}', activated_at=? WHERE skill_id=?",
                (utc_now(), parent.skill_id),
            )
        return self.get(parent.skill_id)  # type: ignore[return-value]

    def delete(self, skill_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM skills WHERE skill_id=?", (skill_id,))

    def record_evaluation(self, record: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO skill_evaluations(
                    eval_id, skill_id, baseline_skill_id, split, metrics_json, decision, created_at
                ) VALUES(?,?,?,?,?,?,?)""",
                (
                    record["eval_id"],
                    record["skill_id"],
                    record.get("baseline_skill_id"),
                    record["split"],
                    json.dumps(record["metrics"], ensure_ascii=False),
                    record["decision"],
                    record.get("created_at", utc_now()),
                ),
            )

    def list_evaluations(self, skill_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM skill_evaluations"
        params: tuple[Any, ...] = ()
        if skill_id:
            query += " WHERE skill_id=?"
            params = (skill_id,)
        query += " ORDER BY created_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {**dict(row), "metrics": json.loads(row["metrics_json"])}
            for row in rows
        ]

    def _row_to_skill(self, row: sqlite3.Row) -> SkillArtifact:
        d = dict(row)
        triggers = [
            SkillTrigger(**t) for t in json.loads(d.get("triggers_json", "[]"))
        ]
        return SkillArtifact(
            skill_id=d["skill_id"],
            name=d["name"],
            description=d["description"],
            version=d["version"],
            scope_markets=json.loads(d.get("scope_markets", "[]")),
            scope_categories=json.loads(d.get("scope_categories", "[]")),
            triggers=triggers,
            inputs=json.loads(d.get("inputs_json", "[]")),
            outputs=json.loads(d.get("outputs_json", "[]")),
            evidence_policy=d.get("evidence_policy", ""),
            body=d.get("body", ""),
            status=d["status"],
            parent_id=d.get("parent_id"),
            source_feedback_id=d.get("source_feedback_id"),
            created_at=d["created_at"],
            activated_at=d.get("activated_at"),
        )


# ---------------------------------------------------------------------------
# BM25 Retrieval
# ---------------------------------------------------------------------------

class SkillRetrieval:
    """Lightweight BM25 keyword retrieval over trigger keywords."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[\w\u4e00-\u9fff]+", text.lower())

    def search(
        self,
        query: str,
        skills: list[SkillArtifact],
        top_k: int = 5,
        min_score: float = 0.1,
    ) -> list[tuple[SkillArtifact, float]]:
        if not skills:
            return []
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Build document lengths and term frequencies
        doc_tokens_list = []
        for skill in skills:
            tokens = []
            for trigger in skill.triggers:
                tokens.extend(self._tokenize(trigger.keyword) * max(1, int(trigger.weight)))
            tokens.extend(self._tokenize(skill.name))
            tokens.extend(self._tokenize(skill.description))
            doc_tokens_list.append(tokens)

        avg_dl = sum(len(dt) for dt in doc_tokens_list) / max(1, len(doc_tokens_list))

        # Document frequency
        df: dict[str, int] = {}
        for dt in doc_tokens_list:
            unique = set(dt)
            for token in unique:
                df[token] = df.get(token, 0) + 1

        n = len(skills)
        results: list[tuple[SkillArtifact, float]] = []
        for idx, skill in enumerate(skills):
            dt = doc_tokens_list[idx]
            tf_map: dict[str, int] = {}
            for token in dt:
                tf_map[token] = tf_map.get(token, 0) + 1
            dl = len(dt)
            score = 0.0
            for qt in query_tokens:
                if qt not in tf_map:
                    continue
                tf = tf_map[qt]
                doc_freq = df.get(qt, 0)
                idf = math.log((n - doc_freq + 0.5) / (doc_freq + 0.5) + 1)
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * dl / max(1, avg_dl))
                score += idf * numerator / denominator
            if score >= min_score:
                results.append((skill, round(score, 4)))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


# ---------------------------------------------------------------------------
# Skill Bank: lifecycle orchestration
# ---------------------------------------------------------------------------

class SkillBank:
    """Orchestrates skill extraction, retrieval, evaluation and promotion."""

    def __init__(self, store: SkillStore) -> None:
        self.store = store
        self.retrieval = SkillRetrieval()

    # --- Extraction ---

    def extract_candidate_from_feedback(
        self,
        feedback: dict[str, Any],
        card_snapshot: dict[str, Any],
    ) -> SkillArtifact | None:
        """Distill a Skill candidate from a rejected/discussed card with explicit correction."""
        reason = feedback.get("reason", "")
        failure_type = feedback.get("failure_type", "")
        if not reason and not failure_type:
            return None

        # Build trigger keywords from failure type and card type
        card_type = card_snapshot.get("card_type", "unknown")
        keywords = self._failure_to_keywords(failure_type, card_type)
        if not keywords:
            return None

        name = self._generate_skill_name(failure_type, card_type)
        existing = self.store.find_by_name(name)

        parent = existing[0] if existing else None
        base = {
            "name": name,
            "triggers": [SkillTrigger(keyword=kw) for kw in keywords],
            "inputs": ["observations", "evidences"],
            "outputs": ["validation_findings", "failure_conditions"],
            "evidence_policy": self._failure_to_evidence_policy(failure_type),
            "body": self._build_skill_body(failure_type, reason, card_type),
            "status": SkillStatus.CANDIDATE,
            "source_feedback_id": feedback.get("feedback_id"),
        }
        if parent:
            base.update(
                description=f"Evolved from {failure_type}: {reason}",
                version=self._bump_version(parent.version),
                scope_markets=parent.scope_markets,
                scope_categories=parent.scope_categories,
                parent_id=parent.skill_id,
            )
        else:
            base["description"] = f"Extracted from {failure_type}: {reason}"

        skill = SkillArtifact(**base)
        self.store.save(skill)
        return skill

    def add_seed_skill(self, skill: SkillArtifact) -> SkillArtifact:
        """Register a pre-authored seed skill as candidate."""
        skill.status = SkillStatus.CANDIDATE
        self.store.save(skill)
        return skill

    # --- Retrieval ---

    def retrieve(
        self,
        query: str,
        market: str = "*",
        category: str = "*",
        top_k: int = 5,
        min_score: float = 0.1,
    ) -> list[tuple[SkillArtifact, float]]:
        """Retrieve active skills matching a research context."""
        active = self.store.list_active()
        scoped = [s for s in active if s.matches_market(market) and s.matches_category(category)]
        return self.retrieval.search(query, scoped, top_k, min_score)

    def retrieve_for_research(
        self,
        category: str,
        market: str,
        mode: str = "mock",
    ) -> list[dict[str, Any]]:
        """Convenience: retrieve and format skills for injection into a research task."""
        query = f"{category} {market}"
        hits = self.retrieve(query, market=market, category=category, top_k=3)
        return [
            {
                "skill_id": skill.skill_id,
                "name": skill.name,
                "version": skill.version,
                "description": skill.description,
                "evidence_policy": skill.evidence_policy,
                "body": skill.body,
                "retrieval_score": score,
            }
            for skill, score in hits
        ]

    # --- Evaluation ---

    def evaluate_candidate(self, skill_id: str) -> dict[str, Any]:
        """Evaluate a candidate skill using replay cases from the policy evaluator."""
        from .evolution import WorkflowReplayEvaluator, EVALUATION_CASES
        from .policy import DEFAULT_POLICY

        skill = self.store.get(skill_id)
        if not skill:
            raise KeyError(skill_id)
        if skill.status != SkillStatus.CANDIDATE:
            raise ValueError(f"Skill {skill_id} is not a candidate (status={skill.status})")

        evaluator = WorkflowReplayEvaluator()
        # Baseline: default policy without skill
        baseline_policy = dict(DEFAULT_POLICY)
        # Candidate: policy augmented by skill's evidence_policy
        candidate_policy = dict(DEFAULT_POLICY)
        if skill.evidence_policy:
            self._apply_evidence_policy(candidate_policy, skill.evidence_policy)

        results = {}
        passed_all = True
        for split in ("validation", "holdout"):
            baseline = evaluator.run(baseline_policy, split)
            candidate = evaluator.run(candidate_policy, split)
            improvement = candidate["accuracy"] - baseline["accuracy"]
            regression = candidate["false_publish_rate"] > baseline["false_publish_rate"]
            passed = improvement >= -0.02 and not regression
            if not passed:
                passed_all = False
            results[split] = {
                "baseline": baseline,
                "candidate": candidate,
                "improvement": improvement,
                "passed": passed,
            }

        decision = SkillStatus.READY if passed_all else SkillStatus.REJECTED
        parent_id = skill.parent_id
        record = {
            "eval_id": str(uuid4()),
            "skill_id": skill_id,
            "baseline_skill_id": parent_id,
            "split": "combined",
            "metrics": results,
            "decision": decision,
            "created_at": utc_now(),
        }
        self.store.record_evaluation(record)
        self.store.save(skill.model_copy(update={"status": decision}))
        return record

    # --- Promotion & Rollback ---

    def promote(self, skill_id: str) -> SkillArtifact:
        """Human promotion gate: only 'ready' skills can be activated."""
        skill = self.store.get(skill_id)
        if not skill:
            raise KeyError(skill_id)
        if skill.status != SkillStatus.READY:
            raise ValueError(f"Skill {skill_id} must be 'ready' before promotion (current: {skill.status})")
        return self.store.activate(skill_id)

    def rollback_skill(self, name: str) -> SkillArtifact:
        return self.store.rollback(name)

    # --- Status ---

    def status(self) -> dict[str, Any]:
        counts = self.store.status_counts()
        active = self.store.list_all(status=SkillStatus.ACTIVE)
        candidates = self.store.list_all(status=SkillStatus.CANDIDATE)
        ready = self.store.list_all(status=SkillStatus.READY)
        return {
            "total_skills": counts["total"],
            "active_count": counts["active"],
            "candidate_count": counts["candidate"],
            "ready_count": counts["ready"],
            "active_skills": [
                {"skill_id": s.skill_id, "name": s.name, "version": s.version}
                for s in active
            ],
            "candidates": [
                {"skill_id": s.skill_id, "name": s.name, "version": s.version, "status": s.status}
                for s in candidates + ready
            ],
            "evaluations": self.store.list_evaluations()[:10],
        }

    def status_counts(self) -> dict[str, int]:
        """Lightweight counter for health checks — no row deserialization."""
        return self.store.status_counts()

    # --- Internals ---

    @staticmethod
    def _failure_to_keywords(failure_type: str, card_type: str) -> list[str]:
        mapping = {
            "weak_evidence": ["evidence", "verification", "source", "proof"],
            "stale_evidence": ["freshness", "stale", "recency", "outdated"],
            "overconfident": ["confidence", "overconfident", "uncertainty", "risk"],
            "bad_action": ["action", "recommendation", "strategy", "decision"],
        }
        keywords = list(mapping.get(failure_type, mapping["weak_evidence"]))
        card_keywords = {
            "product_selection": ["选品", "product", "selection", "differentiation"],
            "pricing": ["定价", "pricing", "margin", "cost", "价格"],
            "competitive": ["竞争", "competitive", "competitor", "positioning"],
            "private_domain": ["验证", "validation", "seed", "用户", "私域"],
        }
        keywords.extend(card_keywords.get(card_type, []))
        return keywords

    @staticmethod
    def _generate_skill_name(failure_type: str, card_type: str) -> str:
        names = {
            ("weak_evidence", "pricing"): "price-margin-safety",
            ("weak_evidence", "product_selection"): "market-entry-evidence-check",
            ("weak_evidence", "competitive"): "competitive-claim-verification",
            ("stale_evidence", "pricing"): "stale-price-signal-recompute",
            ("stale_evidence", "product_selection"): "stale-demand-signal-check",
            ("overconfident", "pricing"): "pricing-confidence-calibration",
            ("overconfident", "competitive"): "competitive-confidence-cap",
            ("bad_action", "private_domain"): "validation-sample-quality",
        }
        return names.get((failure_type, card_type), f"{failure_type}-{card_type}-guard")

    @staticmethod
    def _failure_to_evidence_policy(failure_type: str) -> str:
        return {
            "weak_evidence": "require_minimum_source_evidence:3",
            "stale_evidence": "require_max_evidence_age_days:30",
            "overconfident": "apply_confidence_penalty:0.1",
            "bad_action": "require_validation_sample:30",
        }.get(failure_type, "")

    @staticmethod
    def _build_skill_body(failure_type: str, reason: str, card_type: str) -> str:
        return (
            f"# {failure_type} guard for {card_type}\n\n"
            f"## Origin\nExtracted from human feedback: {reason or 'automated detection'}\n\n"
            f"## Validation Steps\n"
            f"1. Check evidence completeness against skill evidence_policy\n"
            f"2. Verify source record grounding for all primary claims\n"
            f"3. Apply failure-condition thresholds before publishing\n\n"
            f"## Stop Conditions\n"
            f"- Evidence count below policy minimum\n"
            f"- Source records unverifiable\n"
            f"- Confidence score exceeds evidence support\n"
        )

    @staticmethod
    def _apply_evidence_policy(policy: dict[str, Any], evidence_policy: str) -> None:
        for directive in evidence_policy.split(";"):
            directive = directive.strip()
            if not directive:
                continue
            if ":" not in directive:
                continue
            key, value = directive.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key == "require_minimum_source_evidence":
                policy["minimum_source_evidence"] = max(
                    int(policy.get("minimum_source_evidence", 0)), int(value)
                )
            elif key == "require_max_evidence_age_days":
                policy["maximum_evidence_age_days"] = min(
                    int(policy.get("maximum_evidence_age_days", 45)), int(value)
                )
            elif key == "apply_confidence_penalty":
                policy["confidence_penalty"] = max(
                    float(policy.get("confidence_penalty", 0.0)), float(value)
                )
            elif key == "require_minimum_verified":
                policy["minimum_verified_evidence"] = max(
                    int(policy.get("minimum_verified_evidence", 0)), int(value)
                )

    @staticmethod
    def _bump_version(version: str) -> str:
        parts = version.split(".")
        if len(parts) == 3:
            parts[1] = str(int(parts[1]) + 1)
            parts[2] = "0"
            return ".".join(parts)
        return version


# ---------------------------------------------------------------------------
# Seed loader
# ---------------------------------------------------------------------------

SEED_DIR = Path(__file__).parent / "seed_skills"


def load_seed_skills(store: SkillStore, directory: Path = SEED_DIR) -> list[SkillArtifact]:
    """Load JSON seed skill files into the store if not already present."""
    loaded: list[SkillArtifact] = []
    if not directory.is_dir():
        return loaded
    # Use lightweight counter + targeted name lookups instead of full table scan
    all_names = set()
    with store._connect() as conn:
        rows = conn.execute("SELECT name FROM skills").fetchall()
        all_names = {row["name"] for row in rows}
    for path in sorted(directory.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        skill = SkillArtifact(**payload)
        if skill.name not in all_names:
            store.save(skill)
            loaded.append(skill)
            all_names.add(skill.name)
    return loaded
