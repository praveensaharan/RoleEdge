// The two server endpoints (src/carecircle/chat/app.py). Errors become Error(message).

export async function fetchModels() {
  const res = await fetch("/api/models");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();  // {providers: [{id, label, models, efforts}], defaults: {meta, azure}}
}

/**
 * @param {{provider: string, model: string, effort: string, system: string, messages: object[]}} body
 * @returns {Promise<{text: string, usage: object, model: string, note: string|null, latency_s: number}>}
 */
export async function postChat(body) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
  return data;
}
