"""Evidence freshness budgets.

A single ``observed_at`` age threshold conflates two unrelated failures:

* **Upstream publication lag.** A monthly series like GSCPI is published about a
  month after the reference period it describes, and the annual trade series lag
  by more than that. The newest observation that *can exist today* is therefore
  already weeks old. Judging it with a flat recency threshold rejects healthy
  evidence as "stale" and, worse, rejects it forever once the cache ages past
  the threshold.
* **Local cache staleness.** A daily source we downloaded months ago keeps
  claiming to be current. That is an operational failure and deserves its own
  message telling the operator to re-run the download script.

This module answers the two questions separately:

* :func:`observation_age_budget_days` — how old an observation may be before it
  is a real signal problem, derived from the source's own release rhythm.
* :func:`cache_age_budget_days` — how old our local snapshot may be before it
  must be re-fetched.

The cadence allowance is a *floor-raiser*, never a floor-lowerer: a policy that
tightens ``maximum_evidence_age_days`` still cannot demand data fresher than the
upstream source physically publishes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .models import EvidenceItem


@dataclass(frozen=True, slots=True)
class SourceCadence:
    """Declared release rhythm of one upstream source."""

    source_prefix: str
    label: str
    refresh_interval_days: int
    publication_lag_days: int
    freshness_class: str

    @property
    def freshest_possible_age_days(self) -> int:
        """Age of the newest observation that can exist right now."""
        return self.refresh_interval_days + self.publication_lag_days


# Longest matching prefix wins, so more specific entries may be added later
# without reordering. Source names come from the providers and are stable.
SOURCE_CADENCES: tuple[SourceCadence, ...] = (
    SourceCadence("ECB reference rates", "ECB 参考汇率（每交易日）", 1, 1, "live"),
    SourceCadence(
        "Federal Reserve Bank of New York · GSCPI",
        "NY Fed 全球供应链压力指数（月度）",
        30,
        30,
        "recent",
    ),
    SourceCadence("UN Comtrade local cache", "UN Comtrade 海关数据（年度）", 365, 270, "structural"),
    SourceCadence(
        "World Bank / UNCTAD · LSCI",
        "World Bank 班轮运输连接度（年度）",
        365,
        180,
        "structural",
    ),
    SourceCadence("Olist", "Olist 公开数据集（静态快照）", 365, 365, "historical"),
    SourceCadence("Amazon Reviews 2023", "Amazon Reviews 2023（静态快照）", 365, 365, "historical"),
)

# Cache keys used by the providers, mapped to the source name they describe, so
# pre-flight health checks and the decision gate agree on one registry.
CACHE_SOURCES: dict[str, str] = {
    "fx": "ECB reference rates via Frankfurter",
    "trade": "UN Comtrade local cache",
    "gscpi": "Federal Reserve Bank of New York · GSCPI",
    "lsci": "World Bank / UNCTAD · LSCI",
    "olist": "Olist public dataset",
    "amazon_metadata": "Amazon Reviews 2023 · product metadata",
    "reviews": "Amazon Reviews 2023 · review sample",
}

# Newer keys are read through ``.get`` so policies persisted before they existed
# keep working unchanged.
DEFAULT_OBSERVATION_AGE_DAYS = 45
DEFAULT_PUBLICATION_GRACE_DAYS = 15
DEFAULT_CACHE_AGE_DAYS = 90
DEFAULT_CACHE_REFRESH_TOLERANCE = 3


def resolve_cadence(source_name: str) -> SourceCadence | None:
    """Return the declared cadence for a source name, if one is registered."""

    match: SourceCadence | None = None
    for entry in SOURCE_CADENCES:
        if source_name.startswith(entry.source_prefix) and (
            match is None or len(entry.source_prefix) > len(match.source_prefix)
        ):
            match = entry
    return match


def cadence_label(source_name: str) -> str:
    cadence = resolve_cadence(source_name)
    return cadence.label if cadence else "未登记来源"


def _int_policy(policy: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(policy.get(key, default))
    except (TypeError, ValueError):
        return default


def age_in_days(now: datetime, then: datetime) -> int:
    """Whole days between two instants, never negative.

    A file written microseconds ago can carry an mtime a hair ahead of the
    clock read afterwards, and ``timedelta.days`` floors toward negative
    infinity — so an unclamped age reports -1 for a brand new snapshot.
    """

    return max(0, (now - then).days)


def observation_age_days(evidence: EvidenceItem, now: datetime) -> int:
    return age_in_days(now, evidence.observed_at or evidence.collected_at)


def cache_age_days(evidence: EvidenceItem, now: datetime) -> int:
    return age_in_days(now, evidence.collected_at)


def observation_age_budget_days(evidence: EvidenceItem, policy: dict[str, Any]) -> int:
    """How old an observation may be before it counts as a real staleness bug."""

    floor = _int_policy(policy, "maximum_evidence_age_days", DEFAULT_OBSERVATION_AGE_DAYS)
    cadence = resolve_cadence(evidence.source_name)
    if cadence is None:
        return floor
    grace = _int_policy(policy, "source_publication_grace_days", DEFAULT_PUBLICATION_GRACE_DAYS)
    return max(floor, cadence.freshest_possible_age_days + grace)


def _cache_budget(cadence: SourceCadence | None, policy: dict[str, Any]) -> int:
    floor = _int_policy(policy, "maximum_cache_age_days", DEFAULT_CACHE_AGE_DAYS)
    if cadence is None:
        return floor
    tolerance = _int_policy(policy, "cache_refresh_tolerance", DEFAULT_CACHE_REFRESH_TOLERANCE)
    return max(floor, cadence.refresh_interval_days * tolerance + cadence.publication_lag_days)


def cache_age_budget_days(evidence: EvidenceItem, policy: dict[str, Any]) -> int:
    """How old our local snapshot may be before it must be re-fetched."""

    return _cache_budget(resolve_cadence(evidence.source_name), policy)


def cache_age_budget_for_source(source_key: str, policy: dict[str, Any]) -> int:
    """Cache budget for a dataset key such as ``"fx"`` or ``"gscpi"``."""

    source_name = CACHE_SOURCES.get(source_key)
    return _cache_budget(resolve_cadence(source_name) if source_name else None, policy)
