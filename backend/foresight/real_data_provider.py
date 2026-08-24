from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .data import (
    CATEGORY_PROFILES,
    GENERIC_CATEGORY_PROFILE,
    MockDataProvider,
    resolve_category,
    resolve_market,
)
from .model_adapters import ModelAdapterError, QwenReviewExtractor, ReviewRecord
from .models import EvidenceItem, PainPoint, ResearchRequest, SupplySignal
from .providers import (
    ConnectorDataError,
    FxCsvConnector,
    GscpiCsvConnector,
    LsciCsvConnector,
    PublicSignalConnectors,
    TradeCsvConnector,
)


class ProviderUnavailableError(RuntimeError):
    """Raised when a requested evidence mode cannot satisfy its contract."""


FX_FILES = {
    "BR": "USD_BRL.csv",
    "MX": "USD_MXN.csv",
    "MY": "USD_MYR.csv",
    "US": "EUR_USD.csv",
}

CATEGORY_REVIEW_FILES = {
    "pet_feeder": "Pet_Supplies.sample.jsonl",
    "portable_blender": "Home_and_Kitchen.sample.jsonl",
    "noise_cancelling_headphones": "Electronics.sample.jsonl",
    "coffee_grinder": "Home_and_Kitchen.sample.jsonl",
    "generic": "Home_and_Kitchen.sample.jsonl",
}

CATEGORY_RELEVANCE_TERMS = {
    "pet_feeder": ("feeder", "automatic feed", "food dispenser", "portion"),
    "portable_blender": ("blender", "smoothie", "juicer", "blendjet"),
    "noise_cancelling_headphones": ("headphone", "earbud", "noise cancel", "anc"),
    "coffee_grinder": ("coffee grinder", "burr grinder", "grind coffee", "coffee mill"),
    "generic": (),
}

OLIST_CATEGORIES = {
    "pet_feeder": "pet_shop",
    "portable_blender": "eletroportateis",
    "noise_cancelling_headphones": "audio",
    "coffee_grinder": "eletroportateis",
    "generic": "utilidades_domesticas",
}

WORLD_BANK_MARKETS = {"BR": "BRA", "MX": "MEX", "MY": "MYS", "US": "USA"}


def _observed_at(value: str | int) -> datetime:
    text = str(value).strip()
    if len(text) == 4 and text.isdigit():
        return datetime(int(text), 12, 31, tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

PAIN_PATTERNS = {
    "noise": (r"\bnoisy\b", r"\btoo loud\b", r"\bbuzzing\b", r"\bhumming\b"),
    "cleaning": (r"\bhard to clean\b", r"\bdifficult to clean\b", r"\bhassle to clean\b"),
    "jamming": (r"\bjam(?:s|med|ming)?\b", r"\bclog(?:s|ged|ging)?\b"),
    "portion": (r"\bportion.{0,20}(wrong|inaccurate|inconsistent)\b",),
    "leakage": (r"\bleak(?:s|ed|ing)?\b", r"\bdrip(?:s|ped|ping)?\b"),
    "power": (r"\bweak motor\b", r"\bunderpowered\b", r"\bnot powerful enough\b"),
    "battery": (r"\bbattery.{0,20}(die|drain|short|charge)\b",),
    "comfort": (r"\buncomfortable\b", r"\bhurts?.{0,20}(ear|head)\b", r"\btoo tight\b"),
    "anc": (r"\bnoise cancellation.{0,20}(weak|poor|not)\b", r"\banc.{0,20}(fail|weak|not)\b"),
    "weight": (r"\btoo (heavy|bulky|large)\b",),
    "consistency": (r"\binconsistent.{0,20}(grind|result)\b",),
    "static": (r"\bstatic.{0,20}(mess|grounds|coffee)\b",),
    "retention": (r"\bretains?.{0,20}(grounds|coffee)\b", r"\bgrounds remain\b"),
    "durability": (r"\bstopped working\b", r"\bbroke.{0,30}(day|week|month)\b"),
}

PAIN_LABELS = {
    "noise": "运行噪音",
    "cleaning": "清洗困难",
    "jamming": "卡住或堵塞",
    "portion": "份量不准",
    "leakage": "漏液",
    "power": "动力不足",
    "battery": "续航缩水",
    "comfort": "长时间使用不适",
    "anc": "降噪效果弱",
    "weight": "体积或重量偏大",
    "consistency": "输出一致性差",
    "static": "静电飞粉",
    "retention": "残留过多",
    "durability": "耐用性不足",
}


class RealDataProvider:
    """Public-data provider with Qwen-grounded review extraction."""

    provider_version = "1.0.0"

    def __init__(
        self,
        datasets_dir: Path | str = "datasets",
        model_adapter: QwenReviewExtractor | None = None,
        mock_provider: MockDataProvider | None = None,
        signal_connectors: PublicSignalConnectors | None = None,
    ) -> None:
        self.datasets_dir = Path(datasets_dir).expanduser().resolve()
        self.fx_dir = self.datasets_dir / "fx"
        self.reviews_dir = self.datasets_dir / "reviews"
        self.trade_path = self.datasets_dir / "trade" / "comtrade_imports.csv"
        self.gscpi_path = self.datasets_dir / "freight" / "gscpi_monthly.csv"
        self.lsci_path = self.datasets_dir / "shipping" / "lsci.csv"
        self.olist_dir = self.datasets_dir / "olist"
        self.amazon_metadata_dir = self.datasets_dir / "amazon_metadata"
        self.signal_connectors = signal_connectors or PublicSignalConnectors(
            fx=FxCsvConnector(self.fx_dir, FX_FILES),
            trade=TradeCsvConnector(self.trade_path),
            gscpi=GscpiCsvConnector(self.gscpi_path),
            lsci=LsciCsvConnector(self.lsci_path, WORLD_BANK_MARKETS),
        )
        self.model_adapter = model_adapter or QwenReviewExtractor()
        self.mock_provider = mock_provider or MockDataProvider()
        self._review_cache: dict[str, list[dict[str, Any]]] = {}
        self._olist_cache: dict[str, dict[str, Any]] = {}
        self._strict_product_ids: set[str] | None = None

    def data_status(self) -> dict[str, Any]:
        review_files = [self.reviews_dir / filename for filename in set(CATEGORY_REVIEW_FILES.values())]
        signal_status = self.signal_connectors.status()
        checks = {
            "fx": signal_status["fx"],
            "reviews": all(path.is_file() for path in review_files),
            "trade": signal_status["trade"],
            "gscpi": signal_status["gscpi"],
            "lsci": signal_status["lsci"],
            "olist": all(
                (self.olist_dir / filename).is_file()
                for filename in (
                    "olist_order_items_dataset.csv",
                    "olist_order_reviews_dataset.csv",
                    "olist_products_dataset.csv",
                )
            ),
            "amazon_metadata": (self.amazon_metadata_dir / "Pet_Supplies.relevant.jsonl").is_file(),
            "amazon_product_reviews": (self.reviews_dir / "Pet_Supplies.product_matched.jsonl").is_file(),
            "qwen": self.model_adapter.configured,
        }
        return {
            **checks,
            "hybrid_ready": all(checks[name] for name in ("fx", "reviews", "trade", "gscpi")),
            "real_ready": all(checks[name] for name in ("fx", "reviews", "trade", "gscpi", "qwen")),
            "datasets_dir": str(self.datasets_dir),
        }

    def scenario_capabilities(self) -> list[dict[str, Any]]:
        status = self.data_status()
        profiles = [*CATEGORY_PROFILES, GENERIC_CATEGORY_PROFILE]
        capabilities: list[dict[str, Any]] = []
        for market in FX_FILES:
            for profile in profiles:
                category_key = str(profile["key"])
                amazon_price = category_key == "pet_feeder" and status["amazon_metadata"]
                olist_price = market == "BR" and category_key in OLIST_CATEGORIES and status["olist"]
                price_source = (
                    "Amazon Reviews 2023 商品快照"
                    if amazon_price
                    else "Olist 2016-2018 历史成交"
                    if olist_price
                    else None
                )
                runtime_missing = [
                    name
                    for name in ("fx", "reviews", "trade", "gscpi", "qwen")
                    if not status[name]
                ]
                blocking_reasons = [f"runtime:{name}" for name in runtime_missing]
                if not price_source:
                    blocking_reasons.append("source_backed_price")
                known_gaps = []
                if market != "BR" or not status["olist"]:
                    known_gaps.append("native_market_reviews")
                known_gaps.append("current_competitor_listings")
                capabilities.append(
                    {
                        "market": market,
                        "category_key": category_key,
                        "real_available": not blocking_reasons,
                        "hybrid_available": bool(status["hybrid_ready"]),
                        "price_source": price_source,
                        "review_scope": "target-market category proxy" if market == "BR" and status["olist"] else "cross-market product reviews",
                        "blocking_reasons": blocking_reasons,
                        "known_gaps": known_gaps,
                        "missing_signals": blocking_reasons,
                    }
                )
        return capabilities

    def scenario_capability(self, category: str, market: str) -> dict[str, Any]:
        category_key = str(resolve_category(category)["key"])
        market_code = market.upper()
        capability = next(
            (
                item
                for item in self.scenario_capabilities()
                if item["market"] == market_code and item["category_key"] == category_key
            ),
            None,
        )
        if capability is None:
            raise ProviderUnavailableError(f"Unsupported market/category scenario: {market_code}/{category_key}")
        return capability

    def monitoring_snapshot(self, category: str, market: str) -> dict[str, Any]:
        profile = resolve_category(category)
        market_code = market.upper()
        fx = self._fx_signal(market_code)
        trade = self._trade_signal(market_code, str(profile["hs_code"]))
        gscpi = self._gscpi_signal()
        lsci = self._lsci_signal(market_code)
        signals = [
            {
                "key": "fx",
                "label": fx["label"],
                "observed_at": fx["latest_date"],
                "value": fx["latest_value"],
                "change_pct": fx["change_pct"],
                "threshold": "abs(30d) >= 5%",
                "triggered": abs(fx["change_pct"]) >= 5,
            },
            {
                "key": "trade",
                "label": f'{market_code} HS{profile["hs_code"]} 进口额',
                "observed_at": str(trade["latest_year"]),
                "value": trade["latest_value"],
                "change_pct": trade["change_pct"],
                "threshold": "abs(YoY) >= 20%",
                "triggered": abs(trade["change_pct"]) >= 20,
            },
            {
                "key": "gscpi",
                "label": "全球供应链压力指数 GSCPI",
                "observed_at": gscpi["latest_date"],
                "value": gscpi["latest_value"],
                "change_pct": gscpi["change_pct"],
                "threshold": "指数 >= 1 或月变动 >= 15%",
                "triggered": gscpi["latest_value"] >= 1 or abs(gscpi["change_pct"]) >= 15,
            },
        ]
        if lsci:
            signals.append(
                {
                    "key": "lsci",
                    "label": f"{market_code} 班轮运输连接度",
                    "observed_at": str(lsci["latest_year"]),
                    "value": lsci["latest_value"],
                    "change_pct": lsci["change_pct"],
                    "threshold": "结构性基线，不触发短期告警",
                    "triggered": False,
                }
            )
        return {
            "category": category,
            "category_key": profile["key"],
            "market": market_code,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "schedule_status": "manual_snapshot",
            "signals": signals,
            "trigger_count": sum(item["triggered"] for item in signals),
            "capability": self.scenario_capability(category, market_code),
        }

    async def collect_hybrid(self, request: ResearchRequest) -> dict[str, Any]:
        return await self._collect(request, strict_model=False)

    async def collect_real(self, request: ResearchRequest) -> dict[str, Any]:
        status = self.data_status()
        if not status["real_ready"]:
            missing = [name for name in ("fx", "reviews", "trade", "gscpi", "qwen") if not status[name]]
            raise ProviderUnavailableError("Real mode is missing: " + ", ".join(missing))
        capability = self.scenario_capability(request.category, request.market)
        if not capability["real_available"]:
            raise ProviderUnavailableError(
                "Real mode is unavailable for this market/category: "
                + ", ".join(capability["blocking_reasons"])
            )
        return await self._collect(request, strict_model=True)

    async def _collect(self, request: ResearchRequest, strict_model: bool) -> dict[str, Any]:
        status = self.data_status()
        if not status["hybrid_ready"]:
            missing = [name for name in ("fx", "reviews", "trade", "gscpi") if not status[name]]
            raise ProviderUnavailableError("Public dataset cache is missing: " + ", ".join(missing))

        category = resolve_category(request.category)
        market = resolve_market(request.market)
        category_key = str(category["key"])
        relevant_reviews = self._relevant_reviews(category_key)
        model_error: str | None = None
        pain_points: list[PainPoint] = []
        if self.model_adapter.configured:
            try:
                pain_points = await self._llm_pain_points(request.category, relevant_reviews)
            except ModelAdapterError as exc:
                model_error = str(exc)
                if strict_model:
                    raise ProviderUnavailableError(f"Grounded Qwen extraction failed: {exc}") from exc
        elif strict_model:
            raise ProviderUnavailableError("Real mode requires QWEN_API_KEY and QWEN_MODEL")

        if not pain_points:
            pain_points = self._keyword_pain_points(relevant_reviews)
        fallback_scope: list[str] = []
        if not pain_points:
            mock = await self.mock_provider.collect(request)
            pain_points = [
                point.model_copy(
                    update={
                        "source": "cold-start-profile",
                        "extracted_by": "mock",
                        "verification": {"reason": "no category-relevant review pain point"},
                    }
                )
                for point in mock["pain_points"]
            ]
            fallback_scope.append("pain_points")

        now = datetime.now(timezone.utc)
        fx = self._fx_signal(request.market.upper())
        trade = self._trade_signal(request.market.upper(), str(category["hs_code"]))
        gscpi = self._gscpi_signal()
        lsci = self._lsci_signal(request.market.upper()) if status["lsci"] else None
        olist = self._olist_market_data(category_key) if request.market.upper() == "BR" and status["olist"] else None
        amazon_price = self._amazon_price_data(category_key) if status["amazon_metadata"] else None
        if strict_model and not (amazon_price or (olist and olist["prices"])):
            raise ProviderUnavailableError(
                "Real mode requires a source-backed price snapshot for this category and market"
            )
        evidences = self._evidence_items(
            now,
            request,
            category_key,
            pain_points,
            fx,
            trade,
            gscpi,
            lsci,
            olist,
            amazon_price,
        )
        supply_signals = [
            SupplySignal(
                signal_type="customs",
                label=f'{request.market.upper()} HS{category["hs_code"]} 进口额',
                current_value=trade["latest_value"],
                unit="USD",
                change_pct=trade["change_pct"],
                period=f'YoY ({trade["latest_year"]})',
                status="positive" if trade["change_pct"] >= 0 else "watch",
                source="UN Comtrade local cache",
            ),
            SupplySignal(
                signal_type="freight",
                label="全球供应链压力指数 GSCPI",
                current_value=gscpi["latest_value"],
                unit="标准差",
                change_pct=gscpi["change_pct"],
                period="MoM",
                status="alert" if gscpi["latest_value"] >= 1 else "watch" if gscpi["latest_value"] >= 0 else "stable",
                source="Federal Reserve Bank of New York",
            ),
            SupplySignal(
                signal_type="fx",
                label=fx["label"],
                current_value=fx["latest_value"],
                unit=fx["unit"],
                change_pct=fx["change_pct"],
                period="30d",
                status="alert" if abs(fx["change_pct"]) >= 5 else "stable",
                source="ECB via Frankfurter",
            ),
        ]
        if lsci:
            supply_signals.append(
                SupplySignal(
                    signal_type="shipping_connectivity",
                    label=f'{request.market.upper()} 班轮运输连接度',
                    current_value=lsci["latest_value"],
                    unit="指数",
                    change_pct=lsci["change_pct"],
                    period=f'{lsci["latest_year"]} YoY',
                    status="positive" if lsci["change_pct"] >= 0 else "watch",
                    source="World Bank / UNCTAD LSCI",
                )
            )

        if amazon_price and amazon_price["prices"]:
            prices = amazon_price["prices"]
            anchor_price = round(amazon_price["median_price"], 1)
            price_data_mode = "amazon_2023_listing_snapshot"
            price_currency = "USD"
            price_currency_symbol = "US$"
        elif olist and olist["prices"]:
            prices = olist["prices"]
            anchor_price = round(olist["median_price"], 1)
            price_data_mode = "historical_transactions"
            price_currency = "BRL"
            price_currency_symbol = "R$"
        else:
            anchor_price = round(float(category["base_price"]) * float(market["price_factor"]), 1)
            prices = [round(anchor_price * multiplier, 1) for multiplier in (0.68, 0.76, 0.84, 0.91, 0.96, 1, 1.07, 1.15, 1.27, 1.42)]
            price_data_mode = "modeled_anchor"
            price_currency = "USD"
            price_currency_symbol = "US$"
        native_language = str(market["review_language"])
        missing_signals = ["current_competitor_price_feed"]
        native_language_source = bool(olist and olist["reviews"] and native_language == "pt")
        if native_language != "en" and not native_language_source:
            missing_signals.append(f"native_{native_language}_reviews")
        scenario = {
            "market_name": market["name"],
            "marketplace": market["marketplace"],
            "language_label": market["language_label"],
            "review_count": len(relevant_reviews),
            "primary_pain": pain_points[0].label,
            "primary_pain_mentions": pain_points[0].mentions,
            "differentiator": category["differentiator"],
            "secondary_differentiator": category["secondary_differentiator"],
            "proof_metric": category["proof_metric"],
            "generic_promise": category["generic_promise"],
            "seed_audience": category["seed_audience"],
            "hook_message": category["hook_message"],
            "channel": market["channel"],
            "community": market["community"],
            "anchor_price": anchor_price,
            "gross_margin_pct": category["gross_margin_pct"],
            "gross_margin_status": "planning_hypothesis",
            "blue_ocean_index": round(
                min(
                    0.95,
                    0.45
                    + pain_points[0].opportunity_index * 0.35
                    + max(-0.1, min(0.15, trade["change_pct"] / 200)),
                ),
                2,
            ),
            "opportunity_score_basis": "grounded_review_pain + UN_Comtrade_growth",
            "opportunity_score_calibration": "heuristic_v1_not_outcome_calibrated",
            "gap_competitors": 0,
            "competitive_data_mode": "not_collected",
            "repurchase_signal": "unverified",
            "freight_metric": "GSCPI 月度变化",
            "monitoring_status": "public-data-cache",
            "mock_scope": ", ".join(fallback_scope) if fallback_scope else "none",
            "data_mode": request.mode,
            "price_data_mode": price_data_mode,
            "price_currency": price_currency,
            "price_currency_symbol": price_currency_symbol,
            "price_period": amazon_price["period"] if amazon_price else olist["period"] if olist else "cold-start hypothesis",
            "native_language_source": native_language == "en" or native_language_source,
            "missing_signals": missing_signals,
            "llm_extraction": bool(pain_points and pain_points[0].extracted_by == "llm"),
            "model_error": model_error,
        }
        reviews = [
            {
                "language": "en",
                "original": (row.get("text") or row.get("title") or "")[:240],
                "translation": "",
                "pain_type": self._infer_pain_type(row),
                "hidden_pain": int(row.get("rating", 3)) <= 3,
                "rating": int(row.get("rating", 3)),
                "source_record_id": str(row.get("parent_asin") or row.get("asin") or "unknown"),
            }
            for row in relevant_reviews[:100]
        ]
        if olist:
            reviews = [
                {
                    "language": "pt",
                    "original": row["text"][:240],
                    "translation": "",
                    "pain_type": "native_market_voice",
                    "hidden_pain": row["rating"] <= 3,
                    "rating": row["rating"],
                    "source_record_id": row["record_id"],
                }
                for row in olist["reviews"][:100]
            ] + reviews
        return {
            "evidences": evidences,
            "reviews": reviews,
            "prices": prices,
            "trade": {
                "hs_code": category["hs_code"],
                "yoy_pct": trade["change_pct"],
                "market": request.market.upper(),
                "latest_year": trade["latest_year"],
                "latest_value_usd": trade["latest_value"],
            },
            "freight": {
                "route": "global supply chain",
                "change_30d_pct": gscpi["change_pct"],
                "threshold_pct": 15.0,
                "gscpi_value": gscpi["latest_value"],
                "gscpi_date": gscpi["latest_date"],
            },
            "pain_points": pain_points,
            "supply_signals": supply_signals,
            "scenario": scenario,
        }

    def _load_reviews(self, category_key: str) -> list[dict[str, Any]]:
        if category_key in self._review_cache:
            return self._review_cache[category_key]
        matched_path = self.reviews_dir / "Pet_Supplies.product_matched.jsonl"
        path = (
            matched_path
            if category_key == "pet_feeder" and matched_path.is_file()
            else self.reviews_dir / CATEGORY_REVIEW_FILES.get(category_key, CATEGORY_REVIEW_FILES["generic"])
        )
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    row = json.loads(line)
                    if path == matched_path and row.get("parent_asin") not in self._amazon_strict_product_ids():
                        continue
                    rows.append(row)
        self._review_cache[category_key] = rows
        return rows

    def _relevant_reviews(self, category_key: str) -> list[dict[str, Any]]:
        rows = self._load_reviews(category_key)
        if category_key == "pet_feeder" and (self.reviews_dir / "Pet_Supplies.product_matched.jsonl").is_file():
            return sorted(rows, key=lambda row: (int(row.get("rating", 3)) <= 3, int(row.get("helpful_vote", 0))), reverse=True)
        terms = CATEGORY_RELEVANCE_TERMS.get(category_key, ())
        if not terms:
            return rows[:200]
        relevant = []
        for row in rows:
            text = f'{row.get("title", "")} {row.get("text", "")}'.casefold()
            if any(term in text for term in terms):
                relevant.append(row)
        return sorted(relevant, key=lambda row: (int(row.get("rating", 3)) <= 3, int(row.get("helpful_vote", 0))), reverse=True)

    async def _llm_pain_points(self, category: str, reviews: list[dict[str, Any]]) -> list[PainPoint]:
        records = [
            ReviewRecord(
                record_id=f"r{index:03d}",
                rating=int(row.get("rating", 3)),
                title=str(row.get("title") or ""),
                text=str(row.get("text") or ""),
            )
            for index, row in enumerate(reviews[: self.model_adapter.max_reviews], start=1)
        ]
        source_ids = {
            record.record_id: str(row.get("parent_asin") or row.get("asin") or record.record_id)
            for record, row in zip(records, reviews, strict=False)
        }
        extracted = await self.model_adapter.extract(category, records)
        prompt_hash = self.model_adapter.prompt_fingerprint(category, records)
        by_id = {record.record_id: record for record in records}
        points = []
        for item in extracted:
            ids = item["review_ids"]
            ratings = [by_id[record_id].rating for record_id in ids]
            intensity = sum((6 - rating) / 5 for rating in ratings) / len(ratings)
            points.append(
                PainPoint(
                    pain_type=item["pain_type"],
                    label=item["label"],
                    mentions=item["mentions"],
                    sentiment_intensity=round(max(0.2, min(1.0, intensity)), 3),
                    opportunity_index=round(min(1.0, item["mentions"] / max(3, len(records)) * 3), 3),
                    languages=["en"],
                    sample_original=item["sample_original"],
                    sample_translation=item["sample_translation"],
                    source="Amazon Reviews 2023",
                    source_market="global",
                    market_scope="cross_market",
                    extracted_by="llm",
                    verification={
                        "model": self.model_adapter.model,
                        "adapter_version": self.model_adapter.adapter_version,
                        "review_ids": ids,
                        "source_record_ids": [source_ids[record_id] for record_id in ids],
                        "review_count_sampled": len(records),
                        "prompt_sha256": prompt_hash,
                    },
                )
            )
        return points

    def _keyword_pain_points(self, reviews: list[dict[str, Any]]) -> list[PainPoint]:
        matches: dict[str, list[dict[str, Any]]] = {name: [] for name in PAIN_PATTERNS}
        for row in reviews:
            text = f'{row.get("title", "")} {row.get("text", "")}'
            for pain_type, patterns in PAIN_PATTERNS.items():
                if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns):
                    matches[pain_type].append(row)
        points = []
        for pain_type, rows in matches.items():
            if not rows:
                continue
            ratings = [int(row.get("rating", 3)) for row in rows]
            source_ids = [str(row.get("parent_asin") or row.get("asin") or "unknown") for row in rows[:10]]
            points.append(
                PainPoint(
                    pain_type=pain_type,
                    label=PAIN_LABELS[pain_type],
                    mentions=len(rows),
                    sentiment_intensity=round(sum((6 - value) / 5 for value in ratings) / len(ratings), 3),
                    opportunity_index=round(min(1.0, len(rows) / max(3, len(reviews)) * 3), 3),
                    languages=["en"],
                    sample_original=str(rows[0].get("text") or rows[0].get("title") or "")[:240],
                    sample_translation=f"规则抽取：{PAIN_LABELS[pain_type]}",
                    source="Amazon Reviews 2023",
                    source_market="global",
                    market_scope="cross_market",
                    extracted_by="keyword",
                    verification={"source_record_ids": source_ids, "review_count_scanned": len(reviews)},
                )
            )
        return sorted(points, key=lambda point: point.mentions, reverse=True)[:5]

    def _fx_signal(self, market: str) -> dict[str, Any]:
        try:
            return dict(self.signal_connectors.fx.snapshot(market))
        except ConnectorDataError as exc:
            raise ProviderUnavailableError(str(exc)) from exc

    def _trade_signal(self, market: str, hs_code: str) -> dict[str, Any]:
        try:
            return dict(self.signal_connectors.trade.snapshot(market, hs_code))
        except ConnectorDataError as exc:
            raise ProviderUnavailableError(str(exc)) from exc

    def _gscpi_signal(self) -> dict[str, Any]:
        try:
            return dict(self.signal_connectors.gscpi.snapshot())
        except ConnectorDataError as exc:
            raise ProviderUnavailableError(str(exc)) from exc

    def _lsci_signal(self, market: str) -> dict[str, Any] | None:
        try:
            snapshot = self.signal_connectors.lsci.snapshot(market)
            return dict(snapshot) if snapshot else None
        except ConnectorDataError as exc:
            raise ProviderUnavailableError(str(exc)) from exc

    def _olist_market_data(self, category_key: str) -> dict[str, Any] | None:
        if category_key in self._olist_cache:
            return self._olist_cache[category_key]
        target_category = OLIST_CATEGORIES.get(category_key)
        if not target_category:
            return None
        with (self.olist_dir / "olist_products_dataset.csv").open(newline="", encoding="utf-8-sig") as handle:
            product_ids = {
                row["product_id"]
                for row in csv.DictReader(handle)
                if row["product_category_name"] == target_category
            }
        with (self.olist_dir / "olist_order_items_dataset.csv").open(newline="", encoding="utf-8-sig") as handle:
            items = [row for row in csv.DictReader(handle) if row["product_id"] in product_ids]
        if not items:
            return None
        order_ids = {row["order_id"] for row in items}
        prices = sorted(float(row["price"]) for row in items if row.get("price"))
        with (self.olist_dir / "olist_order_reviews_dataset.csv").open(newline="", encoding="utf-8-sig") as handle:
            reviews = [
                {
                    "record_id": row["review_id"],
                    "rating": int(row["review_score"]),
                    "title": row.get("review_comment_title") or "",
                    "text": row.get("review_comment_message") or "",
                }
                for row in csv.DictReader(handle)
                if row["order_id"] in order_ids and (row.get("review_comment_message") or "").strip()
            ]
        reviews.sort(key=lambda row: (row["rating"] <= 3, len(row["text"])), reverse=True)
        middle = len(prices) // 2
        median = prices[middle] if len(prices) % 2 else (prices[middle - 1] + prices[middle]) / 2
        result = {
            "category": target_category,
            "prices": prices,
            "median_price": median,
            "reviews": reviews,
            "period": "2016-2018",
            "order_count": len(order_ids),
        }
        self._olist_cache[category_key] = result
        return result

    def _amazon_price_data(self, category_key: str) -> dict[str, Any] | None:
        if category_key != "pet_feeder":
            return None
        path = self.amazon_metadata_dir / "Pet_Supplies.relevant.jsonl"
        rows = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                haystack = f'{row.get("title", "")} {" ".join(row.get("features") or [])}'.casefold()
                if any(term in haystack for term in ("automatic pet feeder", "automatic cat feeder", "automatic dog feeder")):
                    rows.append(row)
        prices = sorted(
            float(row["price"])
            for row in rows
            if isinstance(row.get("price"), (int, float)) and 10 <= float(row["price"]) <= 300
        )
        if len(prices) < 10:
            return None
        middle = len(prices) // 2
        median = prices[middle] if len(prices) % 2 else (prices[middle - 1] + prices[middle]) / 2
        return {
            "prices": prices,
            "median_price": median,
            "period": "Amazon Reviews 2023 metadata snapshot",
            "product_count": len(rows),
            "priced_product_count": len(prices),
        }

    def _amazon_strict_product_ids(self) -> set[str]:
        if self._strict_product_ids is not None:
            return self._strict_product_ids
        path = self.amazon_metadata_dir / "Pet_Supplies.relevant.jsonl"
        if not path.is_file():
            self._strict_product_ids = set()
            return self._strict_product_ids
        product_ids = set()
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                haystack = f'{row.get("title", "")} {" ".join(row.get("features") or [])}'.casefold()
                if any(term in haystack for term in ("automatic pet feeder", "automatic cat feeder", "automatic dog feeder")):
                    if row.get("parent_asin"):
                        product_ids.add(str(row["parent_asin"]))
        self._strict_product_ids = product_ids
        return product_ids

    def _evidence_items(
        self,
        now: datetime,
        request: ResearchRequest,
        category_key: str,
        pain_points: list[PainPoint],
        fx: dict[str, Any],
        trade: dict[str, Any],
        gscpi: dict[str, Any],
        lsci: dict[str, Any] | None,
        olist: dict[str, Any] | None,
        amazon_price: dict[str, Any] | None,
    ) -> list[EvidenceItem]:
        evidences = [
            EvidenceItem(
                source_name="ECB reference rates via Frankfurter",
                source_type="fx",
                claim=f'{fx["label"]} 近约30个交易日变动 {fx["change_pct"]:+.2f}%',
                raw_value=f'{fx["latest_date"]}: {fx["latest_value"]} {fx["unit"]}',
                url="https://frankfurter.dev/",
                collected_at=now,
                observed_at=_observed_at(fx["latest_date"]),
                observation_period=f'{fx["previous_date"]} to {fx["latest_date"]}',
                freshness_class="live",
                market_scope="target_market",
                source_market=request.market.upper(),
                confidence=0.96,
                verified=True,
                source_record_ids=[fx["latest_date"], fx["previous_date"]],
            ),
            EvidenceItem(
                source_name=f'UN Comtrade local cache · {request.market.upper()}',
                source_type="customs",
                claim=f'{request.market.upper()} 相关 HS 进口额同比 {trade["change_pct"]:+.1f}%',
                raw_value=f'{trade["latest_year"]}: USD {trade["latest_value"]:,.0f}',
                url="https://comtradeplus.un.org/",
                collected_at=now,
                observed_at=_observed_at(trade["latest_year"]),
                observation_period=str(trade["latest_year"]),
                freshness_class="structural",
                market_scope="target_market",
                source_market=request.market.upper(),
                confidence=0.92,
                verified=True,
                source_record_ids=[f'{request.market.upper()}:{trade["latest_year"]}'],
            ),
            EvidenceItem(
                source_name="Federal Reserve Bank of New York · GSCPI",
                source_type="shipping",
                claim=f'全球供应链压力指数最新为 {gscpi["latest_value"]:+.3f} 个标准差',
                raw_value=f'{gscpi["latest_date"]}: {gscpi["latest_value"]:+.3f}',
                url="https://www.newyorkfed.org/research/policy/gscpi",
                collected_at=now,
                observed_at=_observed_at(gscpi["latest_date"]),
                observation_period=gscpi["latest_date"],
                freshness_class="recent",
                market_scope="macro",
                source_market="global",
                confidence=0.95,
                verified=True,
                source_record_ids=[gscpi["latest_date"]],
            ),
        ]
        if lsci:
            evidences.append(
                EvidenceItem(
                    source_name="World Bank / UNCTAD · LSCI",
                    source_type="shipping",
                    claim=f'{request.market.upper()} 班轮运输连接度同比 {lsci["change_pct"]:+.1f}%',
                    raw_value=f'{lsci["latest_year"]}: {lsci["latest_value"]:.3f}',
                    url="https://data.worldbank.org/indicator/IS.SHP.GCNW.XQ",
                    collected_at=now,
                    observed_at=_observed_at(lsci["latest_year"]),
                    observation_period=str(lsci["latest_year"]),
                    freshness_class="structural",
                    market_scope="target_market",
                    source_market=request.market.upper(),
                    confidence=0.9,
                    verified=True,
                    source_record_ids=[f'{request.market.upper()}:{lsci["latest_year"]}'],
                )
            )
        if olist:
            prices = olist["prices"]
            p25 = prices[int((len(prices) - 1) * 0.25)]
            p75 = prices[int((len(prices) - 1) * 0.75)]
            evidences.append(
                EvidenceItem(
                    source_name=f'Olist public dataset · {olist["category"]}',
                    source_type="price",
                    claim=f'{olist["order_count"]} 个巴西历史订单形成真实成交价格先验',
                    raw_value=f'{olist["period"]}: P25=R${p25:.2f}, median=R${olist["median_price"]:.2f}, P75=R${p75:.2f}',
                    url="https://github.com/olist/work-at-olist-data",
                    language="pt",
                    collected_at=now,
                    observed_at=_observed_at("2018"),
                    observation_period=olist["period"],
                    freshness_class="historical",
                    market_scope="category_proxy",
                    source_market="BR",
                    confidence=0.78,
                    verified=True,
                    source_record_ids=[olist["category"], olist["period"]],
                )
            )
            if olist["reviews"]:
                review = olist["reviews"][0]
                evidences.append(
                    EvidenceItem(
                        source_name=f'Olist avaliações · {olist["category"]}',
                        source_type="review",
                        claim="巴西目标类目的低评分原语评价已进入证据链",
                        raw_value=review["text"][:240],
                        url="https://github.com/olist/work-at-olist-data",
                        language="pt",
                        collected_at=now,
                        observed_at=_observed_at("2018"),
                        observation_period=olist["period"],
                        freshness_class="historical",
                        market_scope="category_proxy",
                        source_market="BR",
                        confidence=0.82,
                        verified=True,
                        source_record_ids=[review["record_id"]],
                    )
                )
        if amazon_price:
            prices = amazon_price["prices"]
            p25 = prices[int((len(prices) - 1) * 0.25)]
            p75 = prices[int((len(prices) - 1) * 0.75)]
            evidences.append(
                EvidenceItem(
                    source_name="Amazon Reviews 2023 · product metadata",
                    source_type="price",
                    claim=f'{amazon_price["product_count"]} 个自动喂食器商品快照形成价格区间',
                    raw_value=f'P25=US${p25:.2f}, median=US${amazon_price["median_price"]:.2f}, P75=US${p75:.2f}',
                    url="https://amazon-reviews-2023.github.io/",
                    collected_at=now,
                    observed_at=_observed_at("2023"),
                    observation_period=amazon_price["period"],
                    freshness_class="historical",
                    market_scope="cross_market",
                    source_market="global",
                    confidence=0.86,
                    verified=True,
                    source_record_ids=[amazon_price["period"]],
                )
            )
        for point in pain_points[:2]:
            verification = point.verification
            ids = list(verification.get("source_record_ids") or verification.get("review_ids") or [])
            evidences.append(
                EvidenceItem(
                    source_name=f"Amazon Reviews 2023 · {category_key}",
                    source_type="review",
                    claim=f'{point.mentions} 条入模评论支持“{point.label}”',
                    raw_value=point.sample_original,
                    url="https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023",
                    collected_at=now,
                    observed_at=_observed_at("2023"),
                    observation_period="Amazon Reviews 2023 snapshot",
                    freshness_class="historical",
                    market_scope=point.market_scope,
                    source_market=point.source_market,
                    confidence=round(point.sentiment_intensity, 2),
                    verified=point.extracted_by != "mock",
                    evidence_kind="derived" if point.extracted_by != "mock" else "mock",
                    source_record_ids=ids,
                    derivation_method=point.extracted_by,
                    model_id=verification.get("model"),
                )
            )
        return evidences

    def _infer_pain_type(self, row: dict[str, Any]) -> str:
        text = f'{row.get("title", "")} {row.get("text", "")}'
        for pain_type, patterns in PAIN_PATTERNS.items():
            if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns):
                return pain_type
        return "generic"
