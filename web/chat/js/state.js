// All mutable app state lives here, so it is easy to see what can change.

/** Saved user preferences (localStorage keys: model, effort, speak, system). */
export const prefs = {
  get: (key, fallback = "") => localStorage.getItem(key) ?? fallback,
  set: (key, value) => localStorage.setItem(key, value),
};

export const state = {
  providers: {},        // id -> {id, label, models, efforts}
  history: [],          // conversation sent to the server: [{role, text, images}]
  pending: [],          // image data URLs attached to the next message
  effort: prefs.get("effort", "low"),
  busy: false,
  totals: { input: 0, cached: 0, output: 0, reasoning: 0, requests: 0 },
};

export function resetConversation() {
  state.history = [];
  for (const key of Object.keys(state.totals)) state.totals[key] = 0;
}

export function addUsage(usage) {
  for (const key of ["input", "cached", "output", "reasoning"]) state.totals[key] += usage[key] || 0;
  state.totals.requests += 1;
}
