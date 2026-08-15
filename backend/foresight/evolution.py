from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .harness import MemoryStore
from .models import (
    CardType,
    ConfidenceLevel,
    DecisionCard,
    EvidenceItem,
    FailureCondition,
    FeedbackRecord,
    PrivateDomainHook,
)
from .policy import DEFAULT_POLICY, evaluate_decision_cards


FIXTURE_NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)
EVALUATION_DATASET_PATH = Path(__file__).with_name("evaluation_data") / "decision_cards_v1.jsonl"


@dataclass(frozen=True, slots=True)
class ReplayCase:
    case_id: str
    split: str
    card: DecisionCard
    should_publish: bool
    source_kind: str

    def fingerprint_value(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "split": self.split,
            "card": self.card.model_dump(mode="json"),
            "should_publish": self.should_publish,
            "source_kind": self.source_kind,
        }


def _replay_card(
    case_id: str,
    evidence_count: int,
    non_english: int,
    hook: bool = True,
    evidence_age_days: int = 2,
) -> DecisionCard:
    evidences = [
        EvidenceItem(
            evidence_id=f"{case_id}-evidence-{index}",
            source_name=f"Replay source {index}",
            source_type="review" if index < non_english else "price",
            claim=f"Replay claim {index}",
            raw_value=f"value-{index}",
            language="pt" if index < non_english else "en",
            collected_at=FIXTURE_NOW - timedelta(days=evidence_age_days),
            confidence=0.9,
        )
        for index in range(evidence_count)
    ]
    return DecisionCard(
        card_id=case_id,
        card_type=CardType.PRODUCT_SELECTION,
        action_title="Replay-gated market opportunity",
        action_detail="A complete decision artifact used by the offline evolution harness.",
        confidence=ConfidenceLevel.HIGH,
        confidence_score=0.88,
        generated_at=FIXTURE_NOW,
        evidences=evidences,
        private_domain_hook=PrivateDomainHook(
            seed_audience="replay audience",
            channel="authorized test channel",
            hook_message="validated hook" if hook else "",
        ),
        failure_conditions=[
            FailureCondition(
                condition="Replay signal reverses",
                metric_to_watch="evidence strength",
                threshold="< target",
                action_on_trigger="recalculate",
            )
        ],
        data_sources=sorted({item.source_name for item in evidences}),
        collection_timestamp=FIXTURE_NOW - timedelta(days=evidence_age_days),
        card_specific_data={"evaluation_case": case_id},
    )


def load_evaluation_cases(path: Path = EVALUATION_DATASET_PATH) -> tuple[ReplayCase, ...]:
    cases: list[ReplayCase] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            split = str(payload["split"])
            if split not in {"validation", "holdout"}:
                raise ValueError(f"Invalid evaluation split at {path}:{line_number}")
            case_id = str(payload["case_id"])
            cases.append(
                ReplayCase(
                    case_id=case_id,
                    split=split,
                    card=_replay_card(
                        case_id,
                        int(payload["evidence_count"]),
                        int(payload["non_english"]),
                        hook=bool(payload.get("hook", True)),
                        evidence_age_days=int(payload.get("evidence_age_days", 2)),
                    ),
                    should_publish=bool(payload["should_publish"]),
                    source_kind=str(payload.get("source_kind", "synthetic_fixture")),
                )
            )
    if not cases:
        raise ValueError(f"Evaluation dataset is empty: {path}")
    return tuple(cases)


EVALUATION_CASES = load_evaluation_cases()


class WorkflowReplayEvaluator:
    """Replay complete decision artifacts through the production publication gate."""

    def __init__(self, cases: tuple[ReplayCase, ...] = EVALUATION_CASES) -> None:
        self.cases = cases

    def dataset_fingerprint(self, split: str | None = None) -> str:
        values = [
            case.fingerprint_value()
            for case in self.cases
            if split is None or case.split == split
        ]
        payload = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def run(self, policy: dict[str, Any], split: str) -> dict[str, Any]:
        cases = [case for case in self.cases if case.split == split]
        tp = fp = tn = fn = 0
        case_results = []
        for case in cases:
            outcome = evaluate_decision_cards([case.card], policy, now=FIXTURE_NOW)
            predicted = outcome.accepted
            expected = case.should_publish
            if predicted and expected:
                tp += 1
            elif predicted and not expected:
                fp += 1
            elif not predicted and not expected:
                tn += 1
            else:
                fn += 1
            case_results.append(
                {
                    "case_id": case.case_id,
                    "expected_publish": expected,
                    "predicted_publish": predicted,
                    "failure_count": len(outcome.failures),
                }
            )
        total = len(cases) or 1
        precision = tp / (tp + fp) if tp + fp else 1.0
        recall = tp / (tp + fn) if tp + fn else 1.0
        result = {
            "cases": len(cases),
            "accuracy": (tp + tn) / total,
            "precision": precision,
            "recall": recall,
            "false_publish_rate": fp / total,
            "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
            "dataset_sha256": self.dataset_fingerprint(split),
            "execution_path": [
                "DecisionCard schema",
                "shared decision gate",
                "publish-or-reject decision",
            ],
        }
        if split == "validation":
            result["case_results"] = case_results
        return result


def evaluate_policy(policy: dict[str, Any], split: str) -> dict[str, Any]:
    return WorkflowReplayEvaluator().run(policy, split)


class FeedbackFlywheel:
    """Layer 1/2 evolution: collect feedback and distill reusable memory."""

    def __init__(self, memory: MemoryStore) -> None:
        self.memory = memory

    def record(self, feedback: FeedbackRecord, card: dict[str, Any]) -> dict[str, Any] | None:
        payload = feedback.model_dump(mode="json")
        self.memory.append_feedback(payload)
        namespace = {
            "approved": "positive_cases",
            "rejected": "negative_cases",
            "discussed": "discussion_cases",
            "auto_feedback": "negative_cases",
        }[feedback.feedback_type]
        self.memory.put(namespace, feedback.feedback_id, {"feedback": payload, "card": card})
        if feedback.feedback_type not in {"rejected", "auto_feedback"}:
            return None
        failure = {
            "failure_id": str(uuid4()),
            "task_id": feedback.task_id,
            "card_id": feedback.card_id,
            "failure_type": feedback.failure_type or "weak_evidence",
            "reason": feedback.reason or "人工驳回：需要更严格的证据门槛",
            "feedback_id": feedback.feedback_id,
            "card_snapshot": card,
            "status": "open",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.memory.append_failure_case(failure)
        return failure

    def distill_patterns(self, feedback_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        rows = feedback_rows if feedback_rows is not None else self.memory.list_feedback()
        counts = Counter(row["feedback_type"] for row in rows)
        total = sum(counts.values())
        return {
            "feedback_count": total,
            "approval_rate": counts["approved"] / total if total else 0.0,
            "dominant_signal": counts.most_common(1)[0][0] if counts else "none",
            "signals": dict(counts),
        }


class EvolutionEngine:
    """Versioned policy evolution with validation, holdout and rollback gates."""

    def __init__(self, memory: MemoryStore) -> None:
        self.memory = memory
        self.evaluator = WorkflowReplayEvaluator()
        if not self.memory.active_policy():
            self.memory.save_policy("policy-v1", DEFAULT_POLICY, "ready", None)
            self.memory.activate_policy("policy-v1")

    def active_policy(self) -> dict[str, Any]:
        active = self.memory.active_policy()
        if not active:
            raise RuntimeError("No active decision policy")
        return active

    def generate_candidate(self) -> dict[str, Any]:
        failures = self.memory.list_failure_cases("open")
        if not failures:
            raise ValueError("At least one rejected decision card is required before evolution")
        baseline = self.active_policy()
        policy = dict(baseline["policy"])
        failure_types = Counter(item["failure_type"] for item in failures)
        if failure_types["stale_evidence"]:
            policy["maximum_evidence_age_days"] = max(14, policy["maximum_evidence_age_days"] - 15)
        if failure_types["overconfident"]:
            policy["confidence_penalty"] = min(0.2, policy["confidence_penalty"] + 0.05)
        if failure_types["weak_evidence"] or not any(failure_types.values()):
            policy["minimum_evidence_count"] = max(4, policy["minimum_evidence_count"])
            policy["minimum_non_english_evidence"] = max(2, policy["minimum_non_english_evidence"])

        versions = self.memory.list_policies()
        next_number = max((int(item["version"].split("v")[-1]) for item in versions), default=1) + 1
        version = f"policy-v{next_number}"
        self.memory.save_policy(version, policy, "candidate", baseline["version"])
        return self.evaluate_candidate(version, [item["failure_id"] for item in failures])

    def evaluate_candidate(self, version: str, failure_ids: list[str] | None = None) -> dict[str, Any]:
        candidate = self.memory.get_policy(version)
        if not candidate:
            raise KeyError(version)
        baseline_version = candidate["parent_version"] or self.active_policy()["version"]
        baseline = self.memory.get_policy(baseline_version)
        if not baseline:
            raise KeyError(baseline_version)
        metrics = {
            "validation": {
                "baseline": self.evaluator.run(baseline["policy"], "validation"),
                "candidate": self.evaluator.run(candidate["policy"], "validation"),
            },
            "holdout": {
                "baseline": self.evaluator.run(baseline["policy"], "holdout"),
                "candidate": self.evaluator.run(candidate["policy"], "holdout"),
            },
        }
        val = metrics["validation"]
        holdout = metrics["holdout"]
        improvement = val["candidate"]["accuracy"] - val["baseline"]["accuracy"]
        passed = (
            improvement >= 0.05
            and val["candidate"]["precision"] >= val["baseline"]["precision"]
            and holdout["candidate"]["accuracy"] >= holdout["baseline"]["accuracy"]
            and holdout["candidate"]["recall"] >= holdout["baseline"]["recall"] - 0.05
            and holdout["candidate"]["false_publish_rate"] <= holdout["baseline"]["false_publish_rate"]
        )
        decision = "ready" if passed else "rejected"
        self.memory.save_policy(version, candidate["policy"], decision, baseline_version)
        record = {
            "run_id": str(uuid4()),
            "baseline_version": baseline_version,
            "candidate_version": version,
            "decision": decision,
            "metrics": {
                **metrics,
                "validation_improvement": improvement,
                "failure_ids": failure_ids or [],
                "gates": {
                    "validation_improvement": improvement >= 0.05,
                    "validation_precision_non_regression": (
                        val["candidate"]["precision"] >= val["baseline"]["precision"]
                    ),
                    "holdout_accuracy_non_regression": (
                        holdout["candidate"]["accuracy"] >= holdout["baseline"]["accuracy"]
                    ),
                    "holdout_recall_non_regression": (
                        holdout["candidate"]["recall"] >= holdout["baseline"]["recall"] - 0.05
                    ),
                    "holdout_false_publish_non_regression": (
                        holdout["candidate"]["false_publish_rate"]
                        <= holdout["baseline"]["false_publish_rate"]
                    ),
                },
                "reproducibility": {
                    "evaluation_schema_version": 4,
                    "validation_dataset_sha256": self.evaluator.dataset_fingerprint("validation"),
                    "holdout_dataset_sha256": self.evaluator.dataset_fingerprint("holdout"),
                    "candidate_policy_sha256": hashlib.sha256(
                        json.dumps(candidate["policy"], sort_keys=True).encode("utf-8")
                    ).hexdigest(),
                    "baseline_policy_sha256": hashlib.sha256(
                        json.dumps(baseline["policy"], sort_keys=True).encode("utf-8")
                    ).hexdigest(),
                },
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.memory.record_evolution_run(record)
        return record

    def activate(self, version: str) -> dict[str, Any]:
        policy = self.memory.get_policy(version)
        if not policy:
            raise KeyError(version)
        self.memory.activate_policy(version)
        latest_run = next(
            (run for run in self.memory.list_evolution_runs() if run["candidate_version"] == version), None
        )
        if latest_run:
            self.memory.resolve_failures(latest_run["metrics"].get("failure_ids", []))
        return self.active_policy()

    def rollback(self) -> dict[str, Any]:
        active = self.active_policy()
        parent = active.get("parent_version")
        if not parent:
            raise ValueError("The baseline policy has no parent version")
        self.memory.activate_policy(parent)
        return self.active_policy()

    def status(self) -> dict[str, Any]:
        return {
            "active_policy": self.active_policy(),
            "failure_cases": self.memory.list_failure_cases(),
            "feedback_summary": FeedbackFlywheel(self.memory).distill_patterns(),
            "policy_versions": self.memory.list_policies(),
            "evolution_runs": self.memory.list_evolution_runs(),
            "evaluation_dataset": {
                "schema_version": 4,
                "dataset_file": EVALUATION_DATASET_PATH.name,
                "source_kinds": sorted({case.source_kind for case in EVALUATION_CASES}),
                "claim_boundary": "synthetic replay fixture; not merchant outcome data",
                "execution_path": "DecisionCard -> shared decision gate -> publish/reject",
                "validation": sum(case.split == "validation" for case in EVALUATION_CASES),
                "holdout": sum(case.split == "holdout" for case in EVALUATION_CASES),
                "validation_sha256": self.evaluator.dataset_fingerprint("validation"),
                "holdout_sha256": self.evaluator.dataset_fingerprint("holdout"),
            },
        }
