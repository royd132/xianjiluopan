const API_BASE_URL = import.meta.env?.VITE_API_URL || 'http://localhost:8000';

const ADMIN_TOKEN_KEY = 'foresight.adminToken';

export class ForesightApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = 'ForesightApiError';
    this.status = status;
    this.payload = payload;
  }
}

// The backend guards every mutating route with X-Admin-Token as soon as
// FORESIGHT_ADMIN_TOKEN is set. The workbench therefore has to be able to send
// it. It is deliberately not read from a VITE_ variable: a secret bundled into
// the built assets is readable by anyone who can load the page, which would
// make that guard decorative. The operator enters it at runtime instead, and it
// lives for one tab session.
function readStoredToken() {
  try {
    return globalThis.sessionStorage?.getItem(ADMIN_TOKEN_KEY) || '';
  } catch {
    return '';
  }
}

let adminToken = readStoredToken();

function setAdminToken(token) {
  adminToken = (token || '').trim();
  try {
    if (adminToken) globalThis.sessionStorage?.setItem(ADMIN_TOKEN_KEY, adminToken);
    else globalThis.sessionStorage?.removeItem(ADMIN_TOKEN_KEY);
  } catch {
    // Storage can be unavailable (private mode, non-browser hosts). The
    // in-memory token still authorizes this session's requests.
  }
  return adminToken;
}

function withAdminToken(options) {
  if (!adminToken) return options;
  return { ...options, headers: { ...(options?.headers || {}), 'X-Admin-Token': adminToken } };
}

async function requestJson(path, options) {
  const response = await fetch(`${API_BASE_URL}${path}`, withAdminToken(options));
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ForesightApiError(
      payload.detail || `Request failed with status ${response.status}`,
      response.status,
      payload,
    );
  }
  return payload;
}

export const foresightClient = {
  getAdminToken() {
    return adminToken;
  },

  setAdminToken,

  getHealth() {
    return requestJson('/api/v1/health');
  },

  getDataStatus() {
    return requestJson('/api/v1/data/status');
  },

  getMonitoring(category, market) {
    const params = new URLSearchParams({ category, market });
    return requestJson(`/api/v1/monitoring?${params.toString()}`);
  },

  getMonitoringSubscriptions(workspaceId = 'default') {
    const params = new URLSearchParams({ workspace_id: workspaceId });
    return requestJson(`/api/v1/monitoring/subscriptions?${params.toString()}`);
  },

  createMonitoringSubscription(input) {
    return requestJson('/api/v1/monitoring/subscriptions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    });
  },

  checkMonitoringSubscription(subscriptionId) {
    return requestJson(`/api/v1/monitoring/subscriptions/${encodeURIComponent(subscriptionId)}/check`, { method: 'POST' });
  },

  deleteMonitoringSubscription(subscriptionId) {
    return requestJson(`/api/v1/monitoring/subscriptions/${encodeURIComponent(subscriptionId)}`, { method: 'DELETE' });
  },

  calculateEconomics(input) {
    return requestJson('/api/v1/economics/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    });
  },

  createResearch(request) {
    return requestJson('/api/v1/research', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
  },

  getResearch(taskId) {
    return requestJson(`/api/v1/research/${encodeURIComponent(taskId)}`);
  },

  getResearchHistory(workspaceId = 'default', limit = 50) {
    const params = new URLSearchParams({ workspace_id: workspaceId, limit: String(limit) });
    return requestJson(`/api/v1/research?${params.toString()}`);
  },

  cancelResearch(taskId) {
    return requestJson(`/api/v1/research/${encodeURIComponent(taskId)}/cancel`, {
      method: 'POST',
    });
  },

  resumeResearch(taskId) {
    return requestJson(`/api/v1/research/${encodeURIComponent(taskId)}/resume`, {
      method: 'POST',
    });
  },

  reviewCard(cardId, review) {
    return requestJson(`/api/v1/cards/${encodeURIComponent(cardId)}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(review),
    });
  },

  getEvolution() {
    return requestJson('/api/v1/evolution');
  },

  createEvolutionCandidate() {
    return requestJson('/api/v1/evolution/candidates', { method: 'POST' });
  },

  activateEvolutionPolicy(version) {
    return requestJson(`/api/v1/evolution/policies/${encodeURIComponent(version)}/activate`, {
      method: 'POST',
    });
  },

  rollbackEvolutionPolicy() {
    return requestJson('/api/v1/evolution/rollback', { method: 'POST' });
  },

  relaxEvolutionPolicy() {
    return requestJson('/api/v1/evolution/relax', { method: 'POST' });
  },

  getSkills() {
    return requestJson('/api/v1/skills');
  },

  retrieveSkills(category, market) {
    const params = new URLSearchParams({ category, market });
    return requestJson(`/api/v1/skills/retrieve?${params.toString()}`);
  },

  evaluateSkill(skillId) {
    return requestJson(`/api/v1/skills/${encodeURIComponent(skillId)}/evaluate`, { method: 'POST' });
  },

  promoteSkill(skillId) {
    return requestJson(`/api/v1/skills/${encodeURIComponent(skillId)}/promote`, { method: 'POST' });
  },

  rollbackSkill(name) {
    return requestJson(`/api/v1/skills/${encodeURIComponent(name)}/rollback`, { method: 'POST' });
  },

  submitValidationResult(taskId, result) {
    return requestJson(`/api/v1/contracts/${encodeURIComponent(taskId)}/validate-result`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(result),
    });
  },

  overrideContract(taskId, override) {
    return requestJson(`/api/v1/contracts/${encodeURIComponent(taskId)}/override`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(override),
    });
  },

  acknowledgeContract(taskId, payload = {}) {
    return requestJson(`/api/v1/contracts/${encodeURIComponent(taskId)}/acknowledge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },

  createExecutionTask(taskId, payload) {
    return requestJson(`/api/v1/contracts/${encodeURIComponent(taskId)}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },

  updateExecutionTask(taskId, executionTaskId, payload) {
    return requestJson(`/api/v1/contracts/${encodeURIComponent(taskId)}/tasks/${encodeURIComponent(executionTaskId)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },

  recordActualOutcome(taskId, payload) {
    return requestJson(`/api/v1/contracts/${encodeURIComponent(taskId)}/outcome`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },

  openResearchEvents(taskId) {
    return new EventSource(
      `${API_BASE_URL}/api/v1/research/${encodeURIComponent(taskId)}/events`,
    );
  },
};
