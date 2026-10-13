import test from 'node:test';
import assert from 'node:assert/strict';
import { buildSellerSpriteTask } from '../src/features/integrations/sellerSpriteAdapter.js';

test('SellerSprite adapter emits a research hand-off task without inventing evidence', () => {
  const task = buildSellerSpriteTask({
    category: '宠物自动喂食器',
    market: { code: 'BR', name: '巴西' },
    generatedAt: '2026-10-04T00:00:00.000Z',
    mode: 'hybrid',
    cards: [{ id: 'product', title: '做静音款', summary: '夜间不扰民', runtimeCard: { card_specific_data: { anchor_price: 199, price_currency: 'BRL' } } }],
    evidence: [{ source: 'Olist', type: '评论', claim: '历史评价', observedAt: '2018', verified: true, sourceRecordIds: ['B012345678', 'not-an-asin'] }],
  });

  assert.equal(task.schema_version, 'seller-assistant.task.v1');
  assert.equal(task.product.locale, 'pt-BR');
  assert.equal(task.pricing.anchor_price, 199);
  assert.equal(task.evidence_refs.length, 1);
  assert.equal(task.evidence_refs[0].claim, '历史评价');
  assert.deepEqual(task.asin_list, []);
  assert.deepEqual(task.integrations.sellersprite.asin_list, []);
  assert.equal(task.tasks.length, 4);
  assert.equal(task.integrations.sellersprite.supported, false);
});

test('SellerSprite adapter marks supported Amazon marketplaces', () => {
  const task = buildSellerSpriteTask({
    category: 'portable blender',
    market: { code: 'US', name: '美国' },
    generatedAt: '2026-10-04T00:00:00.000Z',
    cards: [],
    evidence: [],
  });

  assert.equal(task.integrations.sellersprite.supported, true);
  assert.equal(task.integrations.sellersprite.marketplace, 'US');
  assert.equal(task.integrations.sellersprite.endpoint, 'https://api.sellersprite.com/v1/product/research');
  assert.equal(task.integrations.sellersprite.requires_secret_key, true);
});

test('SellerSprite adapter includes the Mexico Amazon marketplace', () => {
  const task = buildSellerSpriteTask({
    category: 'portable blender',
    market: { code: 'MX', name: '墨西哥' },
    cards: [],
    evidence: [],
  });

  assert.equal(task.integrations.sellersprite.supported, true);
  assert.equal(task.integrations.sellersprite.marketplace, 'MX');
});

test('SellerSprite adapter exports only verified ASINs from real SellerSprite evidence', () => {
  const task = buildSellerSpriteTask({
    category: 'portable blender',
    market: { code: 'US', name: '美国' },
    generatedAt: '2026-10-04T00:00:00.000Z',
    mode: 'real',
    cards: [],
    evidence: [{
      source: 'SellerSprite · Amazon product research',
      type: '商品价格',
      claim: 'US listing',
      sourceRecordIds: ['B012345678', 'not-an-asin'],
      verified: true,
      evidenceKind: 'source',
      marketScope: 'target_market',
      sourceMarket: 'US',
    }],
  });

  assert.deepEqual(task.asin_list, ['B012345678']);
  assert.deepEqual(task.integrations.sellersprite.asin_list, ['B012345678']);
});
