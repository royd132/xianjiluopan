const localeForMarket = {
  BR: 'pt-BR',
  MX: 'es-MX',
  MY: 'ms-MY',
  US: 'en-US',
  JP: 'ja-JP', UK: 'en-GB', DE: 'de-DE', FR: 'fr-FR', IT: 'it-IT',
  ES: 'es-ES', CA: 'en-CA', IN: 'en-IN',
};

const sellerSpriteMarkets = new Set(['US', 'JP', 'UK', 'DE', 'FR', 'IT', 'ES', 'CA', 'IN', 'MX']);

function cardData(card) {
  return card?.runtimeCard?.card_specific_data || {};
}

/**
 * Stable data contract for the SellerSprite research hand-off.
 * This is deliberately data-only: no fake in-page app and no guessed deep link.
 */
export function buildSellerSpriteTask({ category, market, generatedAt, mode, cards = [], evidence = [], contract = null }) {
  const productCard = cards.find((card) => card.id === 'product') || cards[0] || {};
  const pricingCard = cards.find((card) => card.id === 'pricing') || {};
  const privateCard = cards.find((card) => card.id === 'private') || {};
  const product = cardData(productCard);
  const pricing = cardData(pricingCard);
  const hook = privateCard.runtimeCard?.private_domain_hook || privateCard.hook || {};
  const marketCode = String(market?.code || market || 'BR').toUpperCase();
  const supported = sellerSpriteMarkets.has(marketCode);
  // A record ID is not an ASIN without source and marketplace provenance.
  const asinEvidence = supported && ['real', 'hybrid'].includes(mode) ? evidence.filter((item) =>
    item.verified && item.evidenceKind === 'source' && item.type === '商品价格'
    && item.source?.startsWith('SellerSprite · Amazon product research')
    && item.marketScope === 'target_market' && item.sourceMarket === marketCode) : [];
  const asinList = [...new Set(asinEvidence.flatMap((item) => item.sourceRecordIds || [])
    .map((value) => String(value).trim().toUpperCase()).filter((value) => /^[A-Z0-9]{10}$/.test(value)))];

  return {
    schema_version: 'seller-assistant.task.v1',
    source_app: 'foresight-compass',
    generated_at: generatedAt || new Date().toISOString(),
    evidence_mode: mode || 'unknown',
    integrations: {
      sellersprite: {
        supported: sellerSpriteMarkets.has(marketCode),
        marketplace: sellerSpriteMarkets.has(marketCode) ? marketCode : null,
        endpoint: 'https://api.sellersprite.com/v1/product/research',
        keyword: category,
        requires_secret_key: true,
        asin_count: asinList.length,
        asin_list: asinList,
      },
    },
    product: {
      category,
      market: marketCode,
      market_name: market?.name || marketCode,
      locale: localeForMarket[marketCode] || 'en-US',
      action_title: productCard.title || category,
      differentiator: product.differentiator || productCard.summary || '',
    },
    listing_draft: {
      audience: hook.seed_audience || hook.audience || '',
      channel: hook.channel || '',
      message: hook.message || hook.hook_message || '',
      title_seed: productCard.title || category,
      localization_required: true,
    },
    pricing: {
      anchor_price: product.anchor_price ?? pricing.anchor_price ?? null,
      currency: product.price_currency || pricing.price_currency || null,
      price_data_mode: product.price_data_mode || pricing.price_data_mode || 'evidence_review_required',
      gross_margin_target_pct: pricing.gross_margin_pct ?? product.gross_margin_pct ?? null,
      landed_cost_required: true,
    },
    fulfillment: {
      hs_code: product.hs_code || pricing.hs_code || null,
      logistics_review_required: true,
      customs_review_required: true,
      returns_and_support_review_required: true,
    },
    validation: {
      verdict: contract?.verdict || 'VALIDATE',
      experiment_design: contract?.experiment_design || '',
      experiment_budget: contract?.experiment_budget ?? null,
      stop_conditions: contract?.stop_conditions || [],
      execution_tasks: contract?.execution_tasks || [],
    },
    evidence_refs: evidence.slice(0, 30).map((item) => ({
      source: item.source,
      type: item.type,
      claim: item.claim,
      observed_at: item.observedAt || null,
      url: item.url || null,
      verified: Boolean(item.verified),
      source_record_ids: item.sourceRecordIds || [],
    })),
    asin_list: asinList,
    tasks: [
      { id: 'localize_listing', label: '完成目标市场语言本地化', required: true },
      { id: 'confirm_landed_cost', label: '补齐采购、头程、税费和平台费', required: true },
      { id: 'review_compliance', label: '复核 HS 编码、标签和产品合规', required: true },
      { id: 'run_pilot', label: '按实验预算创建小流量验证', required: true },
    ],
  };
}

export function downloadSellerSpriteTask(task) {
  const blob = new Blob([JSON.stringify(task, null, 2)], { type: 'application/json' });
  downloadBlob(blob, `sellersprite-research-task-${task.product.market}-${Date.now()}.json`);
}

function downloadBlob(blob, filename) {
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

export function sellerSpriteAsinCsv(task) {
  const rows = [
    ['asin', 'marketplace', 'keyword', 'source_app'],
    ...task.asin_list.map((asin) => [asin, task.product.market, task.integrations.sellersprite.keyword, task.source_app]),
  ];
  const csv = rows.map((row) => row.map((value) => {
    const text = String(value ?? '');
    const safe = /^[\s]*[=+\-@]/.test(text) ? `'${text}` : text;
    return `"${safe.replaceAll('"', '""')}"`;
  }).join(',')).join('\r\n');
  return `\ufeff${csv}`;
}

export function downloadSellerSpriteAsins(task) {
  if (!task.integrations.sellersprite.supported || !task.asin_list.length) {
    throw new Error('当前报告没有目标站点的 SellerSprite ASIN');
  }
  downloadBlob(new Blob([sellerSpriteAsinCsv(task)], { type: 'text/csv;charset=utf-8' }),
    `sellersprite-asins-${task.product.market}-${Date.now()}.csv`);
}
