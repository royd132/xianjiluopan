from __future__ import annotations

from datetime import datetime, timezone

from .models import EvidenceItem, PainPoint, ResearchRequest, SupplySignal


class MockDataProvider:
    """Deterministic cold-start dataset used by the offline demo and tests."""

    async def collect(self, request: ResearchRequest) -> dict:
        now = datetime.now(timezone.utc)
        evidences = [
            EvidenceItem(
                source_name="Google Trends · Brazil",
                source_type="trend",
                claim=f'"{request.category}" 近 90 天搜索热度上升',
                raw_value="+64%",
                url="https://trends.google.com/",
                language="pt",
                collected_at=now,
                confidence=0.91,
            ),
            EvidenceItem(
                source_name="Amazon Brasil · 217 条葡语评论",
                source_type="review",
                claim="38% 的让步评论提到夜间运行噪音",
                raw_value="82 / 217",
                url="https://www.amazon.com.br/",
                language="pt",
                collected_at=now,
                confidence=0.88,
            ),
            EvidenceItem(
                source_name="UN Comtrade · HS 8509",
                source_type="customs",
                claim="巴西相关小家电品类进口额同比增长",
                raw_value="+41% YoY",
                url="https://comtradeplus.un.org/",
                language="en",
                collected_at=now,
                confidence=0.86,
            ),
            EvidenceItem(
                source_name="Marketplace Top 10 Snapshot",
                source_type="price",
                claim="Top 10 中没有产品明确以低于 30dB 为首屏卖点",
                raw_value="0 / 10",
                language="pt",
                collected_at=now,
                confidence=0.83,
            ),
            EvidenceItem(
                source_name="FBX South America",
                source_type="freight",
                claim="南美航线近 30 天运价上涨但尚未触发风险阈值",
                raw_value="+6.2%",
                language="en",
                collected_at=now,
                confidence=0.84,
            ),
        ]
        reviews = [
            {
                "language": "pt",
                "original": "Adoro o alimentador, mas o motor faz muito barulho durante a madrugada.",
                "translation": "我很喜欢这个喂食器，但电机在半夜运行时声音很大。",
                "pain_type": "noise",
                "hidden_pain": True,
            },
            {
                "language": "pt",
                "original": "Ótimo produto, porém desmontar para limpar dá muito trabalho.",
                "translation": "产品很好，不过拆开清洗非常麻烦。",
                "pain_type": "cleaning",
                "hidden_pain": True,
            },
            {
                "language": "es",
                "original": "Me gusta mucho, pero la porción nunca parece igual.",
                "translation": "我很喜欢它，但每次出粮量似乎都不一样。",
                "pain_type": "portion",
                "hidden_pain": True,
            },
            {
                "language": "en",
                "original": "Great product, however the app loses connection too often.",
                "translation": "产品不错，但应用连接经常中断。",
                "pain_type": "connectivity",
                "hidden_pain": True,
            },
        ]
        prices = [29.9, 34.9, 37.5, 39.9, 42.0, 45.9, 49.9, 52.0, 59.9, 69.0]
        trade = {"hs_code": "8509", "yoy_pct": 41.0, "market": request.market}
        freight = {"route": "South America", "change_30d_pct": 6.2, "threshold_pct": 15.0}
        return {"evidences": evidences, "reviews": reviews, "prices": prices, "trade": trade, "freight": freight}


def default_pain_points() -> list[PainPoint]:
    return [
        PainPoint(pain_type="noise", label="夜间噪音", mentions=82, sentiment_intensity=0.89, opportunity_index=0.88, languages=["pt"], sample_original="Adoro o alimentador, mas o motor faz muito barulho durante a madrugada.", sample_translation="我很喜欢这个喂食器，但电机在半夜运行时声音很大。"),
        PainPoint(pain_type="cleaning", label="清洗困难", mentions=47, sentiment_intensity=0.76, opportunity_index=0.69, languages=["pt", "es"], sample_original="Ótimo produto, porém desmontar para limpar dá muito trabalho.", sample_translation="产品很好，不过拆开清洗非常麻烦。"),
        PainPoint(pain_type="jamming", label="容易卡粮", mentions=38, sentiment_intensity=0.72, opportunity_index=0.61, languages=["pt", "en"], sample_original="Funciona bem, mas a ração trava quando os grãos são maiores.", sample_translation="运行不错，但颗粒稍大时就会卡粮。"),
        PainPoint(pain_type="portion", label="份量不准", mentions=29, sentiment_intensity=0.68, opportunity_index=0.51, languages=["es", "en"], sample_original="Me gusta mucho, pero la porción nunca parece igual.", sample_translation="我很喜欢它，但每次出粮量似乎都不一样。"),
    ]


def default_supply_signals() -> list[SupplySignal]:
    return [
        SupplySignal(signal_type="customs", label="巴西进口需求", current_value=41, unit="%", change_pct=41, period="YoY", status="positive", source="UN Comtrade"),
        SupplySignal(signal_type="freight", label="南美海运 FBX", current_value=3280, unit="USD/FEU", change_pct=6.2, period="30d", status="watch", source="FBX"),
        SupplySignal(signal_type="fx", label="USD/BRL", current_value=5.43, unit="BRL", change_pct=0.8, period="7d", status="stable", source="Reference FX"),
    ]
