/**
 * REST API Client for Radar Macro Intelligence Terminal
 */

const API_BASE = "";
let _localSettingsToken = null;

async function ensureLocalToken() {
  if (_localSettingsToken) return _localSettingsToken;
  const res = await fetch(`${API_BASE}/api/settings`);
  if (res.ok) {
    const data = await res.json();
    if (data && data.local_token) {
      _localSettingsToken = data.local_token;
    }
  }
  return _localSettingsToken;
}

export const MacroAPI = {
  async getMetrics() {
    const res = await fetch(`${API_BASE}/api/metrics`);
    if (!res.ok) throw new Error(`Metrics HTTP ${res.status}`);
    return await res.json();
  },

  async getBulletins(params = {}) {
    const query = new URLSearchParams();
    if (params.search) query.set("search", params.search);
    if (params.severity && params.severity.length > 0) query.set("severity", params.severity.join(","));
    if (params.stance && params.stance.length > 0) query.set("stance", params.stance.join(","));
    if (params.jurisdiction && params.jurisdiction !== "all") query.set("jurisdiction", params.jurisdiction);
    if (params.category && params.category !== "all") query.set("category", params.category);
    if (params.page) query.set("page", params.page);
    if (params.pageSize) query.set("page_size", params.pageSize);

    const res = await fetch(`${API_BASE}/api/bulletins?${query.toString()}`);
    if (!res.ok) throw new Error(`Bulletins HTTP ${res.status}`);
    return await res.json();
  },

  async getSources() {
    const res = await fetch(`${API_BASE}/api/sources`);
    if (!res.ok) throw new Error(`Sources HTTP ${res.status}`);
    return await res.json();
  },

  async triggerIngest({ category = null, jurisdiction = null, batchSize = 8 } = {}) {
    const res = await fetch(`${API_BASE}/api/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        category,
        jurisdiction: jurisdiction === "all" ? null : jurisdiction,
        batch_size: batchSize,
      }),
    });
    if (!res.ok) throw new Error(`Ingest HTTP ${res.status}`);
    return await res.json();
  },

  async getPortfolio(userKey = "default_user", refreshAi = false) {
    const query = new URLSearchParams({ user_key: userKey });
    if (refreshAi) query.set("refresh_ai", "true");
    const res = await fetch(`${API_BASE}/api/portfolio?${query.toString()}`);
    if (!res.ok) throw new Error(`Portfolio HTTP ${res.status}`);
    return await res.json();
  },

  async updatePortfolio(weights, userKey = "default_user") {
    const res = await fetch(`${API_BASE}/api/portfolio`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ weights, user_key: userKey }),
    });
    if (!res.ok) throw new Error(`Portfolio update HTTP ${res.status}`);
    return await res.json();
  },

  async getMemoryDigests() {
    const res = await fetch(`${API_BASE}/api/memory`);
    if (!res.ok) throw new Error(`Memory digests HTTP ${res.status}`);
    return await res.json();
  },

  async getSettings() {
    const res = await fetch(`${API_BASE}/api/settings`);
    if (!res.ok) throw new Error(`Settings HTTP ${res.status}`);
    const data = await res.json();
    if (data && data.local_token) {
      _localSettingsToken = data.local_token;
    }
    return data;
  },

  async updateSettings(payload) {
    const token = await ensureLocalToken();
    const headers = { "Content-Type": "application/json" };
    if (token) headers["X-Radar-Local-Token"] = token;
    const res = await fetch(`${API_BASE}/api/settings`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Update settings HTTP ${res.status}`);
    return await res.json();
  },

  async testSettings(payload) {
    const token = await ensureLocalToken();
    const headers = { "Content-Type": "application/json" };
    if (token) headers["X-Radar-Local-Token"] = token;
    const res = await fetch(`${API_BASE}/api/settings/test`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Test credentials HTTP ${res.status}`);
    return await res.json();
  },

  async getAgentMemo() {
    const res = await fetch(`${API_BASE}/api/agent/memo`);
    if (!res.ok) throw new Error(`Agent memo HTTP ${res.status}`);
    return await res.json();
  },

  async postAgentMemo(payload) {
    const res = await fetch(`${API_BASE}/api/agent/memo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Post memo HTTP ${res.status}`);
    return await res.json();
  },
};

