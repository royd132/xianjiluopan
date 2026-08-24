import { CircleDollarSign, PackageSearch, Target, Users } from 'lucide-react';

const cardPresentation = {
  product_selection: { id: 'product', type: '选品方向', icon: PackageSearch, tone: 'blue', metric: '机会分' },
  pricing: { id: 'pricing', type: '定价策略', icon: CircleDollarSign, tone: 'amber', metric: '毛利目标' },
  competitive: { id: 'competitive', type: '竞争打法', icon: Target, tone: 'violet', metric: '表达空位' },
  private_domain: { id: 'private', type: '最小市场验证', icon: Users, tone: 'green', metric: '验证状态' },
};

const evidenceTypeLabels = {
  trend: '趋势',
  review: '评论',
  customs: '海关',
  freight: '运价',
  shipping: '航运',
  fx: '汇率',
  price: '商品价格',
  social: '社媒',
  model_trace: '模型轨迹',
};

const painPositions = [
  { x: 18, y: 22, size: 58, color: '#2563eb' },
  { x: 48, y: 42, size: 43, color: '#059669' },
  { x: 72, y: 51, size: 38, color: '#d97706' },
  { x: 84, y: 67, size: 32, color: '#7c3aed' },
  { x: 37, y: 73, size: 26, color: '#64748b' },
];

export const reportModeLabels = {
  mock: '场景化 Mock',
  hybrid: '公开数据 + 明示回退',
  real: '真实数据 + Qwen',
  'mock-offline': '离线固定样例',
};

export function mapRuntimeCards(runtimeCards) {
  return runtimeCards.map((card) => {
    const presentation = cardPresentation[card.card_type];
    const data = card.card_specific_data || {};
    let metricValue = '—';
    if (card.card_type === 'product_selection') metricValue = String(Math.round((data.opportunity_score ?? data.blue_ocean_index ?? 0) * 100));
    if (card.card_type === 'pricing') metricValue = data.gross_margin_status === 'planning_hypothesis' ? `目标 ${data.gross_margin_pct || 31}%` : `${data.gross_margin_pct || 31}%`;
    if (card.card_type === 'competitive') metricValue = data.listing_audit_required ? '待审计' : `${data.expression_gap_pct ?? 0}%`;
    if (card.card_type === 'private_domain') metricValue = data.repurchase_signal_status === 'not_measured' || data.repurchase_signal_strength === 'unverified' ? '待验证' : data.repurchase_signal_strength === 'strong' ? '强' : '中';
    return {
      ...presentation,
      confidence: Math.round(card.confidence_score * 100),
      title: card.action_title,
      summary: card.action_detail,
      metricValue,
      source: `${card.evidences.length} 条证据`,
      hook: {
        audience: card.private_domain_hook.seed_audience,
        channel: card.private_domain_hook.channel,
        message: card.private_domain_hook.hook_message,
      },
      failureConditions: card.failure_conditions,
      runtimeCard: card,
    };
  });
}

export function mapRuntimeEvidence(runtimeCards) {
  const seen = new Set();
  return runtimeCards.flatMap((card) => card.evidences || []).filter((item) => {
    if (seen.has(item.evidence_id)) return false;
    seen.add(item.evidence_id);
    return true;
  }).map((item) => ({
    source: item.source_name,
    type: evidenceTypeLabels[item.source_type] || item.source_type,
    claim: item.claim,
    value: item.raw_value,
    verified: item.verified,
    url: item.url,
    observedAt: item.observed_at,
    collectedAt: item.collected_at,
    observationPeriod: item.observation_period,
    freshnessClass: item.freshness_class || 'unknown',
    marketScope: item.market_scope || 'unknown',
    sourceMarket: item.source_market,
    evidenceKind: item.evidence_kind,
    modelId: item.model_id,
  }));
}

export function mapRuntimePainPoints(items) {
  return items.map((item, index) => ({
    id: item.pain_type,
    label: item.label,
    value: Math.round(item.opportunity_index * 100),
    count: item.mentions,
    ...painPositions[index % painPositions.length],
  }));
}

export function mapRuntimeReviews(items, marketName) {
  return Object.fromEntries(items.map((item) => [item.pain_type, {
    original: item.sample_original,
    translation: item.sample_translation,
    meta: `${item.languages.join(' / ')} · ${item.market_scope === 'target_market' ? item.source_market || marketName : item.market_scope === 'category_proxy' ? `${item.source_market || marketName} 类目代理` : `跨市场 · ${item.source_market || 'global'}`} · ${item.extracted_by === 'llm' ? 'Qwen 源记录回指' : item.extracted_by === 'keyword' ? '规则源记录抽取' : 'Mock 样本'}`,
  }]));
}

export function mapRuntimeSupplySignals(items) {
  const bars = [
    [24, 32, 29, 41, 46, 58, 66],
    [32, 27, 38, 34, 44, 49, 53],
    [45, 43, 47, 42, 44, 46, 45],
  ];
  return items.map((item, index) => ({
    name: item.label,
    value: item.signal_type === 'fx' ? String(item.current_value) : `${item.change_pct >= 0 ? '+' : ''}${item.change_pct}%`,
    note: item.period,
    state: item.status,
    bars: bars[index % bars.length],
  }));
}
