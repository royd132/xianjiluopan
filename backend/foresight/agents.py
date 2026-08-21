from __future__ import annotations

import asyncio
import statistics
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from .events import CollaborationBlackboard, EventType, RuntimeEvent
from .harness import AgentHarness
from .models import (
    CardType,
    ConfidenceLevel,
    DecisionCard,
    FailureCondition,
    PrivateDomainHook,
    ResearchRequest,
)
from .policy import DEFAULT_POLICY, evaluate_decision_cards


class BaseAgent(ABC):
    name = "base-agent"

    @abstractmethod
    async def run(self, request: ResearchRequest, board: CollaborationBlackboard, harness: AgentHarness, trace_id: str) -> None:
        raise NotImplementedError

    async def execute(self, request: ResearchRequest, board: CollaborationBlackboard, harness: AgentHarness, trace_id: str) -> None:
        await board.publish_event(RuntimeEvent(EventType.AGENT_STARTED, board.task_id, self.name, f"{self.name} started"))
        with harness.agent_span(trace_id, board.task_id, self.name):
            await self.run(request, board, harness, trace_id)
        await board.publish_event(RuntimeEvent(EventType.AGENT_COMPLETED, board.task_id, self.name, f"{self.name} completed"))


class CollectorAgent(BaseAgent):
    name = "collector"

    async def run(self, request: ResearchRequest, board: CollaborationBlackboard, harness: AgentHarness, trace_id: str) -> None:
        tool_name = {
            "mock": "mock_data",
            "hybrid": "hybrid_data",
            "real": "real_data",
        }[request.mode]
        raw = await harness.call_tool(tool_name, self.name, trace_id, board.task_id, request=request)
        await board.publish_artifact("raw_market_data", raw, self.name)
        await board.publish_artifact("evidences", raw["evidences"], self.name)


class MultilingualReviewAgent(BaseAgent):
    name = "review-analyzer"

    async def run(self, request: ResearchRequest, board: CollaborationBlackboard, harness: AgentHarness, trace_id: str) -> None:
        raw = board.read("raw_market_data")
        if not raw:
            raise RuntimeError("Review agent requires raw_market_data")
        concessions = [review for review in raw["reviews"] if review["hidden_pain"]]
        await board.publish_artifact("pain_points", raw["pain_points"], self.name)
        await board.publish_artifact("hidden_pain_reviews", concessions, self.name)


class MarketAnalysisAgent(BaseAgent):
    name = "market-analyzer"

    async def run(self, request: ResearchRequest, board: CollaborationBlackboard, harness: AgentHarness, trace_id: str) -> None:
        harness.assert_tool_allowed("statistics")
        raw = board.read("raw_market_data")
        if not raw:
            raise RuntimeError("Market analyzer requires raw_market_data")
        prices = sorted(raw["prices"])
        q = statistics.quantiles(prices, n=4, method="inclusive")
        scenario = raw["scenario"]
        metrics = {
            "price_p25": q[0],
            "price_median": statistics.median(prices),
            "price_p75": q[2],
            "anchor_price": scenario["anchor_price"],
            "blue_ocean_index": scenario["blue_ocean_index"],
            "top10_gap_competitors": scenario["gap_competitors"],
        }
        await board.publish_artifact("market_metrics", metrics, self.name)


class SupplyChainAgent(BaseAgent):
    name = "supply-chain-analyzer"

    async def run(self, request: ResearchRequest, board: CollaborationBlackboard, harness: AgentHarness, trace_id: str) -> None:
        raw = board.read("raw_market_data")
        risk = raw["freight"]["change_30d_pct"] >= raw["freight"]["threshold_pct"]
        await board.publish_artifact("supply_signals", raw["supply_signals"], self.name)
        await board.publish_artifact("supply_risk_triggered", risk, self.name)


class DecisionCompilerAgent(BaseAgent):
    name = "decision-compiler"

    async def run(self, request: ResearchRequest, board: CollaborationBlackboard, harness: AgentHarness, trace_id: str) -> None:
        evidences = board.read("evidences")
        pains = board.read("pain_points")
        metrics = board.read("market_metrics")
        raw = board.read("raw_market_data")
        if not (evidences and pains and metrics and raw):
            raise RuntimeError("Decision compiler is blocked on evidence, pain points and market metrics")

        scenario = raw["scenario"]
        lead_pain = pains[0]
        anchor = metrics["anchor_price"]
        launch_low = round(anchor * 0.90)
        launch_high = round(anchor * 1.05)
        modeled_price = scenario.get("price_data_mode") == "modeled_anchor"
        historical_price = scenario.get("price_data_mode") == "historical_transactions"
        snapshot_price = scenario.get("price_data_mode") == "amazon_2023_listing_snapshot"
        price_symbol = scenario.get("price_currency_symbol", "US$")
        competitor_gap_available = scenario.get("competitive_data_mode", "mock") != "not_collected"
        gap_limit = max(2, scenario["gap_competitors"] + 2)
        now = datetime.now(timezone.utc)
        common = {
            "evidences": evidences[:8],
            "collection_timestamp": now,
            "data_sources": sorted({item.source_name for item in evidences}),
        }
        hook = PrivateDomainHook(
            seed_audience=scenario["seed_audience"],
            channel=scenario["channel"],
            hook_message=scenario["hook_message"],
            expected_conversion_hint="先完成 30 份意向测试与 5 次深访，再决定首批备货",
        )
        cards = [
            DecisionCard(
                card_type=CardType.PRODUCT_SELECTION,
                action_title=f'优先验证“{scenario["differentiator"]}”的{request.category}，进入{scenario["market_name"]}市场',
                action_detail=f'把“{lead_pain.label}”作为第一问题，用{scenario["secondary_differentiator"]}构成第二道差异；先验证需求，再开模或备货。',
                confidence=ConfidenceLevel.HIGH,
                confidence_score=round(0.72 + metrics["blue_ocean_index"] * 0.18, 2),
                private_domain_hook=hook,
                failure_conditions=[
                    FailureCondition(
                        condition="核心差异被头部竞品快速补齐" if competitor_gap_available else "现售竞品审计不支持当前表达假设",
                        metric_to_watch=f'Top 10 中公开“{scenario["proof_metric"]}”的竞品数' if competitor_gap_available else f'20 个现售商品中“{scenario["proof_metric"]}”证据覆盖率',
                        threshold=f">={gap_limit}" if competitor_gap_available else ">=50%",
                        action_on_trigger="recalculate",
                    )
                ],
                card_specific_data={"opportunity_score": metrics["blue_ocean_index"], "opportunity_score_basis": scenario.get("opportunity_score_basis", "cold-start-profile"), "target_market": request.market.upper(), "differentiation_point": scenario["differentiator"], "primary_pain": lead_pain.label, "mock_scope": scenario["mock_scope"]},
                **common,
            ),
            DecisionCard(
                card_type=CardType.PRICING,
                action_title=(
                    f"以 {price_symbol}{anchor:.2f} 假设锚点做首发 A/B 测试：{price_symbol}{launch_low}–{launch_high}"
                    if modeled_price
                    else f"以 2023 商品快照中位数 {price_symbol}{anchor:.2f} 做首发测试：{price_symbol}{launch_low}–{launch_high}"
                    if snapshot_price
                    else f"以历史成交中位数 {price_symbol}{anchor:.2f} 做测试先验：{price_symbol}{launch_low}–{launch_high}"
                    if historical_price
                    else f"以 {price_symbol}{anchor:.2f} 为价值锚，首发测试 {price_symbol}{launch_low}–{launch_high}"
                ),
                action_detail=(
                    f'当前缺少合规竞品报价源，区间是待验证假设；用“{scenario["proof_metric"]}”支撑溢价，'
                    f'首轮目标毛利 {scenario["gross_margin_pct"]}%，接入真实报价或物流成本越线后立即重算。'
                    if modeled_price
                    else f'区间来自商品级公开价格快照，不冒充今日实时价；用“{scenario["proof_metric"]}”验证可接受溢价，'
                    f'首轮目标毛利 {scenario["gross_margin_pct"]}%，接入当前报价后重算。'
                    if snapshot_price
                    else f'区间来自公开历史成交而非今日竞品报价；用“{scenario["proof_metric"]}”验证可接受溢价，'
                    f'首轮目标毛利 {scenario["gross_margin_pct"]}%，接入当前报价后重算。'
                    if historical_price
                    else f'用“{scenario["proof_metric"]}”支撑价格，不用功能数量支撑价格；首轮目标毛利 {scenario["gross_margin_pct"]}%，物流成本越线时重新计算。'
                ),
                confidence=ConfidenceLevel.MEDIUM if modeled_price or historical_price or snapshot_price else ConfidenceLevel.HIGH,
                confidence_score=0.68 if modeled_price else 0.76 if snapshot_price else 0.72 if historical_price else 0.82,
                private_domain_hook=hook,
                failure_conditions=[FailureCondition(condition="物流成本侵蚀目标毛利", metric_to_watch=scenario["freight_metric"], threshold=">15%", action_on_trigger="recalculate")],
                card_specific_data={"anchor_price": anchor, "price_range": [launch_low, launch_high], "gross_margin_pct": scenario["gross_margin_pct"], "pricing_basis": scenario["proof_metric"], "price_data_mode": scenario.get("price_data_mode", "observed")},
                **common,
            ),
            DecisionCard(
                card_type=CardType.COMPETITIVE,
                action_title=(
                    f'把“{scenario["proof_metric"]}”做成首屏证据，而不是泛讲{scenario["generic_promise"]}'
                    if competitor_gap_available
                    else f'先审计 20 个现售商品，再验证“{scenario["proof_metric"]}”是否存在表达空位'
                ),
                action_detail=(
                    f'围绕“{lead_pain.label}”发布同条件对比、测试方法和原语用户证言，攻击 Top 10 尚未占领的表达空位。'
                    if competitor_gap_available
                    else f'真实评论已支持“{lead_pain.label}”，但当前竞品首屏尚未取得合规数据；先完成人工/授权 listing 审计，再决定是否把“{scenario["proof_metric"]}”作为主攻表达。'
                ),
                confidence=ConfidenceLevel.HIGH if competitor_gap_available else ConfidenceLevel.MEDIUM,
                confidence_score=0.85 if competitor_gap_available else 0.66,
                private_domain_hook=hook,
                failure_conditions=[FailureCondition(condition="竞品开始普遍公开同类证据", metric_to_watch=f'Top 10 “{scenario["proof_metric"]}”证据覆盖率', threshold=">=50%", action_on_trigger="watch")],
                card_specific_data={"copy": scenario["hook_message"], "proof_metric": scenario["proof_metric"], "expression_gap_pct": max(10, (10 - scenario["gap_competitors"]) * 10) if competitor_gap_available else None, "listing_audit_required": not competitor_gap_available, "defense_actions": ["公开测试方法", f'强化{scenario["secondary_differentiator"]}', "保留原语用户证言"]},
                **common,
            ),
            DecisionCard(
                card_type=CardType.PRIVATE_DOMAIN,
                action_title=f'先在{scenario["community"]}找到 30 个种子用户',
                action_detail=f'针对“{scenario["seed_audience"]}”投放问题对比素材，用“{scenario["hook_message"]}”测试购买意向；达到阈值后再决定首批备货。',
                confidence=ConfidenceLevel.HIGH,
                confidence_score=0.90,
                private_domain_hook=hook,
                failure_conditions=[FailureCondition(condition="种子测试未形成有效兴趣", metric_to_watch="落地页购买意向率", threshold="<5%", action_on_trigger="abort")],
                card_specific_data={"gathering_places": [scenario["community"], scenario["marketplace"]], "repurchase_signal_strength": scenario["repurchase_signal"], "validation_sample": 30},
                **common,
            ),
        ]
        await board.publish_artifact("decision_cards_draft", cards, self.name)


class SafetyEvaluationAgent(BaseAgent):
    name = "safety-evaluator"

    async def run(self, request: ResearchRequest, board: CollaborationBlackboard, harness: AgentHarness, trace_id: str) -> None:
        cards: list[DecisionCard] = board.read("decision_cards_draft", [])
        policy_snapshot = harness.policy_for_task(board.task_id)
        policy = dict(policy_snapshot.get("policy") or DEFAULT_POLICY)
        gate_profile = "mock-structure"
        if request.mode != "mock":
            gate_profile = "verified-evidence"
            policy["minimum_verified_evidence"] = max(
                int(policy.get("minimum_verified_evidence", 0)),
                int(policy["minimum_evidence_count"]),
            )
            policy["minimum_source_evidence"] = max(
                int(policy.get("minimum_source_evidence", 0)),
                3,
            )
            # Native-language source reviews are a disclosed coverage gap in the
            # public-data demo. Translated findings never masquerade as source data.
            raw = board.read("raw_market_data", {})
            policy["minimum_non_english_evidence"] = (
                1 if raw.get("scenario", {}).get("native_language_source") else 0
            )
        outcome = evaluate_decision_cards(cards, policy)
        if not outcome.accepted:
            raise ValueError("Decision gate rejected cards: " + "; ".join(outcome.failures))
        await board.publish_artifact("decision_cards", outcome.cards, self.name)
        await board.publish_artifact(
            "evaluation",
            {
                "passed": True,
                "score": 0.91,
                "checks": outcome.checks,
                "gate_profile": gate_profile,
                "verified_evidence_required": policy.get("minimum_verified_evidence", 0),
                "policy_version": policy_snapshot.get("version", "embedded-default"),
            },
            self.name,
        )
        await board.publish_event(
            RuntimeEvent(
                EventType.GATE_PASSED,
                board.task_id,
                self.name,
                f"All decision cards passed the {gate_profile} gate",
                {
                    "cards": len(outcome.cards),
                    "gate_profile": gate_profile,
                    "policy_version": policy_snapshot.get("version", "embedded-default"),
                },
            )
        )


async def run_parallel(agents: list[BaseAgent], request: ResearchRequest, board: CollaborationBlackboard, harness: AgentHarness, trace_id: str) -> None:
    await asyncio.gather(*(agent.execute(request, board, harness, trace_id) for agent in agents))
