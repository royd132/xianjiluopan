from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class CardType(str, Enum):
    PRODUCT_SELECTION = "product_selection"
    PRICING = "pricing"
    COMPETITIVE = "competitive"
    PRIVATE_DOMAIN = "private_domain"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ResearchRequest(BaseModel):
    category: str = Field(min_length=2, max_length=100)
    market: str = Field(default="BR", min_length=2, max_length=5)
    workspace_id: str = Field(default="default", min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    mode: Literal["mock", "hybrid", "real"] = "mock"
    languages: list[str] = Field(default_factory=lambda: ["pt", "en", "es"])
    planned_investment: float | None = Field(default=None, ge=0, description="Planned first-order investment amount (CNY)")
    investment_stage: str | None = Field(default=None, max_length=60, description="e.g. 首批备货, 打样, 广告测试")


class EvidenceItem(BaseModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid4()))
    source_name: str
    source_type: Literal[
        "trend",
        "review",
        "customs",
        "freight",
        "shipping",
        "fx",
        "price",
        "social",
        "model_trace",
    ]
    claim: str
    raw_value: str
    url: str | None = None
    language: str = "en"
    collected_at: datetime
    observed_at: datetime | None = None
    observation_period: str | None = None
    freshness_class: Literal["live", "recent", "historical", "structural", "unknown"] = "unknown"
    market_scope: Literal["target_market", "cross_market", "category_proxy", "macro", "unknown"] = "unknown"
    source_market: str | None = None
    confidence: float = Field(ge=0, le=1)
    verified: bool = True
    evidence_kind: Literal["source", "derived", "mock"] = "source"
    source_record_ids: list[str] = Field(default_factory=list)
    derivation_method: str | None = None
    model_id: str | None = None


class PrivateDomainHook(BaseModel):
    seed_audience: str
    channel: str
    hook_message: str
    expected_conversion_hint: str | None = None


class FailureCondition(BaseModel):
    condition: str
    metric_to_watch: str
    threshold: str
    action_on_trigger: Literal["recalculate", "abort", "watch"]


class DecisionCard(BaseModel):
    card_id: str = Field(default_factory=lambda: str(uuid4()))
    card_type: CardType
    version: int = 1
    action_title: str
    action_detail: str
    confidence: ConfidenceLevel
    confidence_score: float = Field(ge=0, le=1)
    validity_days: int = Field(default=14, ge=1, le=90)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    evidences: list[EvidenceItem] = Field(min_length=3)
    private_domain_hook: PrivateDomainHook
    failure_conditions: list[FailureCondition] = Field(min_length=1)
    data_sources: list[str]
    collection_timestamp: datetime
    ai_generated: bool = True
    c2pa_signature: str | None = None
    human_review_status: Literal["pending", "approved", "rejected", "discussed"] = "pending"
    human_reviewer: str | None = None
    human_reviewed_at: datetime | None = None
    card_specific_data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def fill_expiry(self) -> "DecisionCard":
        if self.expires_at is None:
            self.expires_at = self.generated_at + timedelta(days=self.validity_days)
        return self


class PainPoint(BaseModel):
    pain_type: str
    label: str
    mentions: int
    sentiment_intensity: float = Field(ge=0, le=1)
    opportunity_index: float = Field(ge=0, le=1)
    hidden_pain: bool = True
    languages: list[str]
    sample_original: str
    sample_translation: str
    source: str = "unknown"
    source_market: str | None = None
    market_scope: Literal["target_market", "cross_market", "category_proxy", "unknown"] = "unknown"
    extracted_by: Literal["llm", "keyword", "mock"] = "mock"
    verification: dict[str, Any] = Field(default_factory=dict)


class SupplySignal(BaseModel):
    signal_type: str
    label: str
    current_value: float
    unit: str
    change_pct: float
    period: str
    status: Literal["positive", "stable", "watch", "alert"]
    source: str


class ResearchResult(BaseModel):
    task_id: str
    request: ResearchRequest
    cards: list[DecisionCard]
    pain_points: list[PainPoint]
    supply_signals: list[SupplySignal]
    evidence_count: int
    agents_completed: list[str]
    mode: str
    started_at: datetime
    completed_at: datetime
    trace_id: str
    contract: DecisionContract | None = None


class ReviewRequest(BaseModel):
    status: Literal["approved", "rejected", "discussed"]
    reviewer: str = "demo-user"
    reason: str | None = None
    failure_type: Literal["weak_evidence", "stale_evidence", "overconfident", "bad_action"] | None = None


class ProviderReloadRequest(BaseModel):
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?$", max_length=40)


class FeedbackRecord(BaseModel):
    feedback_id: str = Field(default_factory=lambda: str(uuid4()))
    card_id: str
    task_id: str
    feedback_type: Literal["approved", "rejected", "discussed", "auto_feedback"]
    user_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str | None = None
    failure_type: Literal["weak_evidence", "stale_evidence", "overconfident", "bad_action"] | None = None


# ---------------------------------------------------------------------------
# Decision Contract — first-order investment decision artifact
# ---------------------------------------------------------------------------


class DecisionVerdict(str, Enum):
    GO = "GO"
    VALIDATE = "VALIDATE"
    STOP = "STOP"


class EvidenceCheckpoint(BaseModel):
    """One dimension of evidence maturity."""

    question: str
    status: Literal["pass", "partial", "gap"]
    basis: str = ""


class EvidenceCoverage(BaseModel):
    """Decision evidence maturity — how many required questions are answered."""

    checkpoints: list[EvidenceCheckpoint]

    @property
    def maturity(self) -> str:
        passed = sum(1 for c in self.checkpoints if c.status == "pass")
        return f"{passed} / {len(self.checkpoints)}"

    @property
    def gaps(self) -> list[str]:
        return [c.question for c in self.checkpoints if c.status == "gap"]

    @property
    def ready(self) -> bool:
        return all(c.status != "gap" for c in self.checkpoints)


class ValidationCriteria(BaseModel):
    """Structured promotion gates (GO threshold) and stop gates (abort threshold).

    Three-state logic:
      - All promotion gates pass → GO
      - Any stop gate triggers → STOP
      - Otherwise (gray zone) → VALIDATE
    """

    min_sample_count: int = 30
    min_intent_rate: float = 0.12
    max_cpc: float | None = None
    min_pain_confirmation_rate: float | None = None
    # Stop gates — explicit abort thresholds (lower than promotion gates)
    stop_intent_rate: float = 0.05
    stop_sample_count: int = 10


class DecisionContract(BaseModel):
    """First-order investment decision contract.

    Replaces the 'report' paradigm with a concrete Go/Validate/Stop decision
    tied to a specific capital commitment.
    """

    contract_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    verdict: DecisionVerdict
    planned_investment: float | None = None
    investment_stage: str | None = None
    allowed_investment: float | None = None
    core_basis: list[str] = Field(default_factory=list)
    biggest_unknown: str = ""
    experiment_design: str | None = None
    experiment_budget: float | None = None
    promotion_criteria: ValidationCriteria = Field(default_factory=ValidationCriteria)
    stop_conditions: list[str] = Field(default_factory=list)
    validity_days: int = 14
    recalculation_triggers: list[str] = Field(default_factory=list)
    evidence_coverage: EvidenceCoverage
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    system_verdict: DecisionVerdict | None = None
    human_override: DecisionVerdict | None = None
    override_reason: str | None = None
    override_by: str | None = None
    override_at: datetime | None = None


class ValidationResultRequest(BaseModel):
    """User-submitted validation results for re-evaluation."""

    actual_spend: float = Field(ge=0)
    metrics: dict[str, Any] = Field(default_factory=dict, description="e.g. click_count, intent_rate, cpc, sample_feedback_count")
    outcome: Literal["positive", "negative", "inconclusive"] = "inconclusive"
    notes: str | None = None


class OverrideRequest(BaseModel):
    """Human override of a system verdict. Separate from validation submission.
    Only GO and STOP are allowed — overriding to VALIDATE would create
    inconsistent allowed_investment state.
    """

    target_verdict: Literal[DecisionVerdict.GO, DecisionVerdict.STOP]
    reason: str = Field(min_length=1, description="Why the human disagrees with the system verdict")
    operator: str = Field(default="demo-user", min_length=1)
