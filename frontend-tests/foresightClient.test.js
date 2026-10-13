import assert from 'node:assert/strict';
import test from 'node:test';

import { foresightClient } from '../src/api/foresightClient.js';


function stubFetch(response) {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return response || { ok: true, status: 200, json: async () => ({}) };
  };
  return calls;
}


test('an authorized workbench sends the admin token on writes', async () => {
  const calls = stubFetch();
  foresightClient.setAdminToken('competition-secret');

  await foresightClient.reviewCard('card-1', { status: 'approved' });

  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.headers['X-Admin-Token'], 'competition-secret');
  assert.equal(calls[0].options.headers['Content-Type'], 'application/json');
});


test('no token header is sent until the operator enters one', async () => {
  const calls = stubFetch();
  foresightClient.setAdminToken('');

  await foresightClient.getHealth();
  assert.equal(calls[0].options?.headers?.['X-Admin-Token'], undefined);

  foresightClient.setAdminToken('  abc  ');
  await foresightClient.getHealth();
  assert.equal(calls[1].options.headers['X-Admin-Token'], 'abc');

  foresightClient.setAdminToken('   ');
  await foresightClient.getHealth();
  assert.equal(calls[2].options?.headers?.['X-Admin-Token'], undefined);
});


test('every mutating route the workbench calls is covered', async () => {
  const calls = stubFetch();
  foresightClient.setAdminToken('competition-secret');

  await foresightClient.createEvolutionCandidate();
  await foresightClient.activateEvolutionPolicy('policy-v2');
  await foresightClient.rollbackEvolutionPolicy();
  await foresightClient.evaluateSkill('skill-1');
  await foresightClient.promoteSkill('skill-1');
  await foresightClient.rollbackSkill('price-margin-safety');
  await foresightClient.cancelResearch('task-1');
  await foresightClient.resumeResearch('task-1');
  await foresightClient.submitValidationResult('task-1', { actual_spend: 1800, metrics: {} });
  await foresightClient.overrideContract('task-1', { target_verdict: 'GO' });

  assert.equal(calls.length, 10);
  for (const call of calls) {
    assert.equal(call.options.headers['X-Admin-Token'], 'competition-secret', call.url);
  }
});


test('a rejected write surfaces the backend detail and status', async () => {
  stubFetch({
    ok: false,
    status: 401,
    json: async () => ({ detail: 'A valid X-Admin-Token header is required' }),
  });
  foresightClient.setAdminToken('');

  await assert.rejects(
    () => foresightClient.createEvolutionCandidate(),
    (error) => error.status === 401 && /X-Admin-Token/.test(error.message),
  );
});
