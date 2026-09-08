/**
 * State store for Radar Macro Intelligence Terminal
 */

export const state = {
  filters: {
    search: "",
    jurisdiction: "all",
    stances: ["HAWKISH", "DOVISH", "PIVOT", "NEUTRAL"],
    severities: ["CRITICAL", "WARNING", "OPPORTUNITY", "INFO"],
    category: "all",
    page: 1,
    pageSize: 30,
  },
  metrics: {},
  bulletins: [],
  totalBulletins: 0,
  selectedBulletin: null,
  isSyncing: false,
  sources: [],
  activeTab: "feed",
  portfolio: null,
};

export const listeners = new Set();

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function notify() {
  listeners.forEach((fn) => fn(state));
}

export function updateFilters(partial) {
  state.filters = { ...state.filters, ...partial };
  notify();
}
