import assert from 'node:assert/strict';
import test from 'node:test';

import {
  mapRuntimeCards,
  mapRuntimeEvidence,
  mapRuntimePainPoints,
} from '../src/features/research/runtimeMappers.js';


const evidence = {
  evidence_id: 'e-1',
  source_name: 'ECB',
  source_type: 'fx',
  claim: 'USD/BRL moved by 5%',
  raw_value: '5.67',
  verified: true,
  observed_at: '2026-08-20T00:00:00Z',
  collected_at: '2026-08-24T00:00:00Z',
  freshness_class: 'live',
  market_scope: 'target_market',
  source_market: 'BR',
  evidence_kind: 'source',
};

const runtimeCard = {
  card_id: 'card-1',
  card_type: 'pricing',
  confidence_score: 0.82,
  action_title: 'Protect margin during FX volatility',
  action_detail: 'Recompute the launch price when the exchange rate moves.',
  card_specific_data: {
    gross_margin_status: 'planning_hypothesis',
    gross_margin_pct: 31,
  },
  evidences: [evidence, evidence],
  private_domain_hook: {
    seed_audience: 'Brazilian pet owners',
    channel: 'WhatsApp',
    hook_message: 'Quiet feeding at night',
  },
  failure_conditions: ['FX observation is stale'],
};


test('runtime cards keep evidence and failure conditions visible', () => {
  const [card] = mapRuntimeCards([runtimeCard]);

  assert.equal(card.id, 'pricing');
  assert.equal(card.metricValue, '目标 31%');
  assert.equal(card.source, '2 条证据');
  assert.deepEqual(card.failureConditions, ['FX observation is stale']);
});


test('runtime evidence is deduplicated by evidence id', () => {
  const mapped = mapRuntimeEvidence([runtimeCard]);

  assert.equal(mapped.length, 1);
  assert.equal(mapped[0].type, '汇率');
  assert.equal(mapped[0].marketScope, 'target_market');
  assert.equal(mapped[0].verified, true);
});


test('pain points map opportunity values to stable visual positions', () => {
  const [pain] = mapRuntimePainPoints([
    { pain_type: 'noise', label: 'Night noise', opportunity_index: 0.88, mentions: 42 },
  ]);

  assert.equal(pain.value, 88);
  assert.equal(pain.count, 42);
  assert.equal(pain.x, 18);
  assert.equal(pain.size, 58);
});
