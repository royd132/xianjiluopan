from __future__ import annotations

import asyncio
import statistics
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from .data import MockDataProvider, default_pain_points, default_supply_signals
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

    def __init__(self, provider: MockDataProvider) -> None:
        self.provider = provider

    async def run(self, request: ResearchRequest, board: CollaborationBlackboard, harness: AgentHarness, trace_id: str) -> None:
        raw = await harness.call_tool(
            "mock_data",
            self.name,
            trace_id,
            board.task_id,
            request=request,
        )
        await board.publish_artifact("raw_market_data", raw, self.name)
        await board.publish_artifact("evidences", raw["evidences"], self.name)


class MultilingualReviewAgent(BaseAgent):
    name = "review-analyzer"

    async def run(self, request: ResearchRequest, board: CollaborationBlackboard, harness: AgentHarness, trace_id: str) -> None:
        raw = board.read("raw_market_data")
        if not raw:
            raise RuntimeError("Review agent requires raw_market_data")
        pains = default_pain_points()
        concessions = [review for review in raw["reviews"] if review["hidden_pain"]]
        await board.publish_artifact("pain_points", pains, self.name)
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
        metrics = {
            "price_p25": q[0],
            "price_median": statistics.median(prices),
            "price_p75": q[2],
            "anchor_price": 49.9,
            "blue_ocean_index": 0.86,
            "top10_silent_competitors": 0,
        }
        await board.publish_artifact("market_metrics", metrics, self.name)


class SupplyChainAgent(BaseAgent):
    name = "supply-chain-analyzer"

    async def run(self, request: ResearchRequest, board: CollaborationBlackboard, harness: AgentHarness, trace_id: str) -> None:
        raw = board.read("raw_market_data")
        signals = default_supply_signals()
        risk = raw["freight"]["change_30d_pct"] >= raw["freight"]["threshold_pct"]
        await board.publish_artifact("supply_signals", signals, self.name)
        await board.publish_artifact("supply_risk_triggered", risk, self.name)


class DecisionCompilerAgent(BaseAgent):
    name = "decision-compiler"

    async def run(self, request: ResearchRequest, board: CollaborationBlackboard, harness: AgentHarness, trace_id: str) -> None:
        evidences = board.read("evidences")
        pains = board.read("pain_points")
        metrics = board.read("market_metrics")
        if not (evidences and pains and metrics):
            raise RuntimeError("Decision compiler is blocked on evidence, pain points and market metrics")
        now = datetime.now(timezone.utc)
        common = {
            "evidences": evidences[:4],
            "collection_timestamp": now,
            "data_sources": sorted({item.source_name for item in evidences}),
        }
        cards = [
            DecisionCard(
                card_type=CardType.PRODUCT_SELECTION,
                action_title=f"做静音款{request.category}，切入巴西市场",
                action_detail="主打夜间运行不扰眠，并把易拆洗作为第二差异点。",
                confidence=ConfidenceLevel.HIGH,
                confidence_score=0.88,
                private_domain_hook=PrivateDomainHook(seed_audience="养宠且夜班/浅眠人群", channel="WhatsApp 本地养宠群", hook_message="让它半夜别吵醒你", expected_conversion_hint="先进行 30 份意向测试"),
                failure_conditions=[FailureCondition(condition="静音卖点被快速补齐", metric_to_watch="Top10 静音款数量", threshold=">=2", action_on_trigger="recalculate")],
                card_specific_data={"blue_ocean_index": metrics["blue_ocean_index"], "target_market": request.market, "differentiation_point": "低于30dB + 易拆洗"},
                **common,
            ),
            DecisionCard(
                card_type=CardType.PRICING,
                action_title="锚定 US$49.90，首发价控制在 US$44–52",
                action_detail="以静音电机和易拆洗结构支撑约 18% 溢价，目标毛利 31%。",
                confidence=ConfidenceLevel.HIGH,
                confidence_score=0.82,
                private_domain_hook=PrivateDomainHook(seed_audience="已购买自动喂食器且抱怨噪音的人群", channel="WhatsApp/邮件候补名单", hook_message="安静升级，不增加夜间负担"),
                failure_conditions=[FailureCondition(condition="物流成本侵蚀毛利", metric_to_watch="FBX 南美运价 7 日变化", threshold=">15%", action_on_trigger="recalculate")],
                card_specific_data={"anchor_price": 49.9, "price_range": [44, 52], "gross_margin_pct": 31},
                **common,
            ),
            DecisionCard(
                card_type=CardType.COMPETITIVE,
                action_title="把分贝数变成可验证卖点，而不是泛讲智能",
                action_detail="详情页首屏展示夜间运行分贝对比，攻击 Top10 的共同表达空位。",
                confidence=ConfidenceLevel.HIGH,
                confidence_score=0.85,
                private_domain_hook=PrivateDomainHook(seed_audience="对睡眠和宠物作息敏感的养宠用户", channel="TikTok Shop 内容 + WhatsApp 群", hook_message="听得见的差异，低于30dB"),
                failure_conditions=[FailureCondition(condition="竞品开始普遍公开分贝参数", metric_to_watch="Top10 分贝参数覆盖率", threshold=">=50%", action_on_trigger="watch")],
                card_specific_data={"copy": "夜间不扰眠，定时喂养更安心", "defense_actions": ["公开分贝测试", "强化易拆洗结构", "保留原语用户证言"]},
                **common,
            ),
            DecisionCard(
                card_type=CardType.PRIVATE_DOMAIN,
                action_title="用养宠 + 夜班/浅眠人群完成首轮种子验证",
                action_detail="在巴西本地 WhatsApp 养宠群投放静音对比素材，先验证卖点再备货。",
                confidence=ConfidenceLevel.HIGH,
                confidence_score=0.91,
                private_domain_hook=PrivateDomainHook(seed_audience="养宠 + 夜班/浅眠人群", channel="WhatsApp 巴西本地养宠群", hook_message="让它半夜别吵醒你", expected_conversion_hint="30份意向 + 5次深访"),
                failure_conditions=[FailureCondition(condition="种子测试未形成有效兴趣", metric_to_watch="落地页意向率", threshold="<5%", action_on_trigger="abort")],
                card_specific_data={"gathering_places": ["WhatsApp 养宠群", "Facebook 本地猫犬社区"], "repurchase_signal_strength": "strong"},
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
                "policy_version": policy_snapshot.get("version", "embedded-default"),
            },
            self.name,
        )
        await board.publish_event(RuntimeEvent(EventType.GATE_PASSED, board.task_id, self.name, "All decision cards passed the HITL preflight gate", {"cards": len(outcome.cards), "policy_version": policy_snapshot.get("version", "embedded-default")}))


async def run_parallel(agents: list[BaseAgent], request: ResearchRequest, board: CollaborationBlackboard, harness: AgentHarness, trace_id: str) -> None:
    await asyncio.gather(*(agent.execute(request, board, harness, trace_id) for agent in agents))
