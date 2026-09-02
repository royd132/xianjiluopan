const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export class ForesightApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = 'ForesightApiError';
    this.status = status;
    this.payload = payload;
  }
}

async function requestJson(path, options) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
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
  getHealth() {
    return requestJson('/api/v1/health');
  },

  getMonitoring(category, market) {
    const params = new URLSearchParams({ category, market });
    return requestJson(`/api/v1/monitoring?${params.toString()}`);
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

  openResearchEvents(taskId) {
    return new EventSource(
      `${API_BASE_URL}/api/v1/research/${encodeURIComponent(taskId)}/events`,
    );
  },
};
