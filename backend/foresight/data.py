from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import EvidenceItem, PainPoint, ResearchRequest, SupplySignal


MARKET_PROFILES: dict[str, dict[str, Any]] = {
    "BR": {
        "name": "巴西",
        "trend_source": "Google Trends · Brazil",
        "marketplace": "Amazon Brasil",
        "review_language": "pt",
        "language_label": "葡萄牙语",
        "trend_growth": 64,
        "import_growth": 41,
        "price_factor": 1.00,
        "review_factor": 1.00,
        "route": "South America",
        "freight_label": "南美海运 FBX",
        "freight_value": 3280,
        "freight_change": 6.2,
        "fx_label": "USD/BRL",
        "fx_value": 5.43,
        "fx_unit": "BRL",
        "channel": "WhatsApp 本地兴趣群",
        "community": "WhatsApp 与 Facebook 本地兴趣社区",
    },
    "US": {
        "name": "美国",
        "trend_source": "Google Trends · United States",
        "marketplace": "Amazon US",
        "review_language": "es",
        "language_label": "英语/西班牙语",
        "trend_growth": 38,
        "import_growth": 18,
        "price_factor": 1.12,
        "review_factor": 0.86,
        "route": "North America",
        "freight_label": "北美航线 FBX",
        "freight_value": 2470,
        "freight_change": 4.8,
        "fx_label": "USD 指数",
        "fx_value": 103.2,
        "fx_unit": "DXY",
        "channel": "Reddit 垂直社区 + 邮件候补名单",
        "community": "Reddit、Facebook Group 与垂直论坛",
    },
    "MY": {
        "name": "马来西亚",
        "trend_source": "Google Trends · Malaysia",
        "marketplace": "Shopee Malaysia",
        "review_language": "ms",
        "language_label": "马来语/英语",
        "trend_growth": 46,
        "import_growth": 27,
        "price_factor": 0.88,
        "review_factor": 0.72,
        "route": "Southeast Asia",
        "freight_label": "东南亚航线运价",
        "freight_value": 1860,
        "freight_change": 3.7,
        "fx_label": "USD/MYR",
        "fx_value": 4.47,
        "fx_unit": "MYR",
        "channel": "TikTok Shop 内容 + WhatsApp 社群",
        "community": "TikTok Shop、Shopee Live 与 WhatsApp 社群",
    },
    "MX": {
        "name": "墨西哥",
        "trend_source": "Google Trends · Mexico",
        "marketplace": "Mercado Libre México",
        "review_language": "es",
        "language_label": "西班牙语",
        "trend_growth": 52,
        "import_growth": 33,
        "price_factor": 0.92,
        "review_factor": 0.80,
        "route": "Latin America North",
        "freight_label": "拉美北线运价",
        "freight_value": 2940,
        "freight_change": 7.1,
        "fx_label": "USD/MXN",
        "fx_value": 18.74,
        "fx_unit": "MXN",
        "channel": "WhatsApp 社群 + Mercado Libre 问答区",
        "community": "Facebook 兴趣群、WhatsApp 社群与 Mercado Libre 问答区",
    },
}


CATEGORY_PROFILES: list[dict[str, Any]] = [
    {
        "key": "pet_feeder",
        "keywords": ("宠物", "喂食", "pet", "feeder"),
        "hs_code": "8509",
        "base_price": 49.9,
        "review_total": 217,
        "blue_ocean_index": 0.86,
        "gap_competitors": 0,
        "differentiator": "低噪电机 + 易拆洗料仓",
        "secondary_differentiator": "大颗粒防卡粮结构",
        "proof_metric": "夜间运行分贝",
        "generic_promise": "智能喂养",
        "seed_audience": "养宠且夜班/浅眠的人群",
        "hook_message": "让它半夜别吵醒你",
        "gross_margin_pct": 31,
        "repurchase_signal": "strong",
        "pains": [
            ("noise", "夜间噪音", 82, 0.89, 0.88),
            ("cleaning", "清洗困难", 47, 0.76, 0.69),
            ("jamming", "容易卡粮", 38, 0.72, 0.61),
            ("portion", "份量不准", 29, 0.68, 0.51),
        ],
    },
    {
        "key": "portable_blender",
        "keywords": ("榨汁", "果汁", "blender", "juicer"),
        "hs_code": "8509",
        "base_price": 39.9,
        "review_total": 184,
        "blue_ocean_index": 0.79,
        "gap_competitors": 1,
        "differentiator": "倒置防漏 + 可拆洗刀组",
        "secondary_differentiator": "冰块实测与杯盖安全锁",
        "proof_metric": "倒置 30 分钟防漏测试",
        "generic_promise": "便携大功率",
        "seed_audience": "通勤、健身且会在办公室现榨的人群",
        "hook_message": "装进包里不漏，30 秒喝上鲜榨",
        "gross_margin_pct": 34,
        "repurchase_signal": "medium",
        "pains": [
            ("leakage", "杯盖漏液", 74, 0.87, 0.84),
            ("cleaning", "刀组难清洗", 61, 0.79, 0.74),
            ("power", "冰块打不碎", 43, 0.75, 0.65),
            ("battery", "续航缩水", 28, 0.66, 0.48),
        ],
    },
    {
        "key": "noise_cancelling_headphones",
        "keywords": ("耳机", "降噪", "headphone", "earbud", "anc"),
        "hs_code": "8518",
        "base_price": 69.9,
        "review_total": 263,
        "blue_ocean_index": 0.74,
        "gap_competitors": 2,
        "differentiator": "久戴舒适 + 通勤降噪",
        "secondary_differentiator": "眼镜人群夹头压力优化",
        "proof_metric": "2 小时佩戴舒适度 + 地铁降噪曲线",
        "generic_promise": "旗舰音质",
        "seed_audience": "单程通勤超过 45 分钟且经常戴眼镜的人群",
        "hook_message": "不是更大声，是戴两小时仍然舒服",
        "gross_margin_pct": 36,
        "repurchase_signal": "medium",
        "pains": [
            ("comfort", "久戴夹头", 79, 0.86, 0.81),
            ("anc", "人声降噪弱", 58, 0.78, 0.71),
            ("battery", "续航虚标", 42, 0.72, 0.59),
            ("weight", "收纳体积大", 31, 0.61, 0.45),
        ],
    },
    {
        "key": "coffee_grinder",
        "keywords": ("咖啡", "磨豆", "coffee", "grinder"),
        "hs_code": "8509",
        "base_price": 59.9,
        "review_total": 156,
        "blue_ocean_index": 0.82,
        "gap_competitors": 1,
        "differentiator": "低残粉 + 刻度复现",
        "secondary_differentiator": "静电控制与易清洁粉道",
        "proof_metric": "残粉重量 + 粒径一致性",
        "generic_promise": "专业研磨",
        "seed_audience": "手冲入门升级、希望每天复现配方的人群",
        "hook_message": "昨天好喝的那杯，今天也能复现",
        "gross_margin_pct": 33,
        "repurchase_signal": "medium",
        "pains": [
            ("consistency", "研磨一致性差", 68, 0.88, 0.86),
            ("static", "静电飞粉", 55, 0.79, 0.74),
            ("retention", "残粉过多", 41, 0.75, 0.68),
            ("noise", "晨间噪音", 27, 0.61, 0.43),
        ],
    },
]


GENERIC_CATEGORY_PROFILE: dict[str, Any] = {
    "key": "generic",
    "keywords": (),
    "hs_code": "8516",
    "base_price": 44.9,
    "review_total": 168,
    "blue_ocean_index": 0.68,
    "gap_competitors": 2,
    "differentiator": "易维护结构 + 本地化说明",
    "secondary_differentiator": "关键性能公开实测",
    "proof_metric": "核心性能对比测试",
    "generic_promise": "功能更多",
    "seed_audience": "正在寻找同类产品替代方案的高意向用户",
    "hook_message": "先把最影响使用的那个问题解决掉",
    "gross_margin_pct": 30,
    "repurchase_signal": "medium",
    "pains": [
        ("instructions", "本地化说明不足", 62, 0.79, 0.75),
        ("cleaning", "维护清洁麻烦", 49, 0.73, 0.66),
        ("durability", "耐用性不稳定", 37, 0.71, 0.58),
        ("support", "售后响应慢", 25, 0.64, 0.46),
    ],
}


PAIN_PHRASES = {
    "noise": {"pt": "faz barulho demais à noite", "es": "hace demasiado ruido por la mañana", "ms": "terlalu bising ketika digunakan", "en": "it is too noisy during use"},
    "cleaning": {"pt": "é difícil desmontar para limpar", "es": "es difícil de desmontar y limpiar", "ms": "sukar dibuka dan dibersihkan", "en": "it is difficult to take apart and clean"},
    "jamming": {"pt": "entope com facilidade", "es": "se atasca con facilidad", "ms": "mudah tersekat", "en": "it jams too easily"},
    "portion": {"pt": "a quantidade nunca é consistente", "es": "la cantidad nunca es consistente", "ms": "sukatannya tidak konsisten", "en": "the portion is never consistent"},
    "leakage": {"pt": "a tampa vaza dentro da bolsa", "es": "la tapa gotea dentro de la bolsa", "ms": "penutupnya bocor di dalam beg", "en": "the lid leaks inside my bag"},
    "power": {"pt": "não consegue triturar gelo", "es": "no puede triturar hielo", "ms": "tidak mampu menghancurkan ais", "en": "it cannot crush ice"},
    "battery": {"pt": "a bateria dura menos do que o prometido", "es": "la batería dura menos de lo prometido", "ms": "bateri tahan lebih singkat daripada dijanjikan", "en": "the battery lasts less than promised"},
    "comfort": {"pt": "aperta a cabeça depois de uma hora", "es": "aprieta la cabeza después de una hora", "ms": "terasa ketat selepas sejam", "en": "it clamps too hard after an hour"},
    "anc": {"pt": "o cancelamento de vozes é fraco", "es": "la cancelación de voces es débil", "ms": "pembatalan suara manusia lemah", "en": "voice cancellation is weak"},
    "weight": {"pt": "ocupa espaço demais na bolsa", "es": "ocupa demasiado espacio en la bolsa", "ms": "mengambil terlalu banyak ruang", "en": "it takes up too much space"},
    "consistency": {"pt": "a moagem muda em cada uso", "es": "la molienda cambia en cada uso", "ms": "hasil kisaran berubah setiap kali", "en": "the grind changes every time"},
    "static": {"pt": "o pó gruda e espalha por todo lado", "es": "el polvo se pega y vuela por todas partes", "ms": "serbuk melekat dan berterbangan", "en": "the grounds stick and scatter everywhere"},
    "retention": {"pt": "retém muito café dentro", "es": "retiene demasiado café dentro", "ms": "terlalu banyak serbuk tertinggal", "en": "too many grounds remain inside"},
    "instructions": {"pt": "as instruções locais são confusas", "es": "las instrucciones locales son confusas", "ms": "arahan tempatan mengelirukan", "en": "the local instructions are confusing"},
    "durability": {"pt": "parece menos durável do que o esperado", "es": "parece menos duradero de lo esperado", "ms": "kurang tahan lama daripada dijangka", "en": "it feels less durable than expected"},
    "support": {"pt": "o suporte demora a responder", "es": "el soporte tarda en responder", "ms": "sokongan lambat memberi respons", "en": "support takes too long to respond"},
}


def resolve_market(market: str) -> dict[str, Any]:
    return MARKET_PROFILES.get(market.upper(), MARKET_PROFILES["US"])


def resolve_category(category: str) -> dict[str, Any]:
    normalized = category.casefold()
    for profile in CATEGORY_PROFILES:
        if any(keyword.casefold() in normalized for keyword in profile["keywords"]):
            return profile
    return GENERIC_CATEGORY_PROFILE


def _pain_points(request: ResearchRequest, category: dict[str, Any], market: dict[str, Any]) -> list[PainPoint]:
    language = market["review_language"]
    template = {
        "pt": "Gosto muito deste produto, mas {phrase}.",
        "es": "Me gusta mucho este producto, pero {phrase}.",
        "ms": "Saya suka produk ini, tetapi {phrase}.",
        "en": "I like this product, but {phrase}.",
    }.get(language, "I like this product, but {phrase}.")
    result = []
    for pain_type, label, mentions, intensity, opportunity in category["pains"]:
        phrase = PAIN_PHRASES.get(pain_type, {}).get(language, label)
        result.append(
            PainPoint(
                pain_type=pain_type,
                label=label,
                mentions=max(8, round(mentions * market["review_factor"])),
                sentiment_intensity=intensity,
                opportunity_index=opportunity,
                languages=[language, "en"] if language != "en" else ["en"],
                sample_original=template.format(phrase=phrase),
                sample_translation=f"我很喜欢这个{request.category}，但{label}。",
            )
        )
    return result


def _supply_signals(market: dict[str, Any]) -> list[SupplySignal]:
    return [
        SupplySignal(signal_type="customs", label=f'{market["name"]}相关品类进口需求', current_value=market["import_growth"], unit="%", change_pct=market["import_growth"], period="YoY", status="positive", source="UN Comtrade"),
        SupplySignal(signal_type="freight", label=market["freight_label"], current_value=market["freight_value"], unit="USD/FEU", change_pct=market["freight_change"], period="30d", status="watch", source="FBX / reference index"),
        SupplySignal(signal_type="fx", label=market["fx_label"], current_value=market["fx_value"], unit=market["fx_unit"], change_pct=0.8, period="7d", status="stable", source="Reference FX"),
    ]


class MockDataProvider:
    """Deterministic scenario-aware cold-start data for demos and tests."""

    async def collect(self, request: ResearchRequest) -> dict:
        now = datetime.now(timezone.utc)
        market = resolve_market(request.market)
        category = resolve_category(request.category)
        pain_points = _pain_points(request, category, market)
        supply_signals = _supply_signals(market)
        review_count = max(60, round(category["review_total"] * market["review_factor"]))
        primary_pain = pain_points[0]
        pain_share = round(primary_pain.mentions / review_count * 100)
        anchor_price = round(category["base_price"] * market["price_factor"], 1)
        price_multipliers = (0.68, 0.76, 0.84, 0.91, 0.96, 1.00, 1.07, 1.15, 1.27, 1.42)
        prices = [round(anchor_price * multiplier, 1) for multiplier in price_multipliers]

        evidences = [
            EvidenceItem(
                source_name=market["trend_source"],
                source_type="trend",
                claim=f'“{request.category}”在{market["name"]}近 90 天搜索热度上升',
                raw_value=f'+{market["trend_growth"]}%',
                url="https://trends.google.com/",
                language=market["review_language"],
                collected_at=now,
                confidence=0.89,
                verified=False,
                evidence_kind="mock",
            ),
            EvidenceItem(
                source_name=f'{market["marketplace"]} · {review_count} 条{market["language_label"]}评论样本',
                source_type="review",
                claim=f'{pain_share}% 的让步评论集中提到“{primary_pain.label}”',
                raw_value=f'{primary_pain.mentions} / {review_count}',
                language=market["review_language"],
                collected_at=now,
                confidence=0.86,
                verified=False,
                evidence_kind="mock",
            ),
            EvidenceItem(
                source_name=f'UN Comtrade · HS {category["hs_code"]}',
                source_type="customs",
                claim=f'{market["name"]}相关品类进口额同比增长',
                raw_value=f'+{market["import_growth"]}% YoY',
                url="https://comtradeplus.un.org/",
                language="en",
                collected_at=now,
                confidence=0.84,
                verified=False,
                evidence_kind="mock",
            ),
            EvidenceItem(
                source_name=f'{market["marketplace"]} Top 10 Snapshot',
                source_type="price",
                claim=f'Top 10 中仅 {category["gap_competitors"]} 款把“{category["proof_metric"]}”作为首屏证据',
                raw_value=f'{category["gap_competitors"]} / 10',
                language=market["review_language"],
                collected_at=now,
                confidence=0.82,
                verified=False,
                evidence_kind="mock",
            ),
            EvidenceItem(
                source_name=market["freight_label"],
                source_type="freight",
                claim=f'{market["route"]}近 30 天运价变化尚未触发 15% 风险阈值',
                raw_value=f'+{market["freight_change"]}%',
                language="en",
                collected_at=now,
                confidence=0.81,
                verified=False,
                evidence_kind="mock",
            ),
        ]

        reviews = [
            {
                "language": market["review_language"],
                "original": pain.sample_original,
                "translation": pain.sample_translation,
                "pain_type": pain.pain_type,
                "hidden_pain": True,
            }
            for pain in pain_points
        ]
        scenario = {
            "market_name": market["name"],
            "marketplace": market["marketplace"],
            "language_label": market["language_label"],
            "review_count": review_count,
            "primary_pain": primary_pain.label,
            "primary_pain_mentions": primary_pain.mentions,
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
            "blue_ocean_index": category["blue_ocean_index"],
            "gap_competitors": category["gap_competitors"],
            "repurchase_signal": category["repurchase_signal"],
            "freight_metric": f'{market["freight_label"]} 7 日变化',
            "monitoring_status": "registered",
            "mock_scope": f'{category["key"]} × {request.market.upper()}',
        }
        trade = {"hs_code": category["hs_code"], "yoy_pct": market["import_growth"], "market": request.market.upper()}
        freight = {"route": market["route"], "change_30d_pct": market["freight_change"], "threshold_pct": 15.0}
        return {
            "evidences": evidences,
            "reviews": reviews,
            "prices": prices,
            "trade": trade,
            "freight": freight,
            "pain_points": pain_points,
            "supply_signals": supply_signals,
            "scenario": scenario,
        }


def default_pain_points(request: ResearchRequest | None = None) -> list[PainPoint]:
    request = request or ResearchRequest(category="宠物自动喂食器", market="BR")
    return _pain_points(request, resolve_category(request.category), resolve_market(request.market))


def default_supply_signals(market: str = "BR") -> list[SupplySignal]:
    return _supply_signals(resolve_market(market))
