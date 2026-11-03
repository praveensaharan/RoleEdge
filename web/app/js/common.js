// Shared helpers for both screens: escaping (rule S9), API calls, live updates and the line-icon set.

/** Escape text before it goes into innerHTML. */
export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

/** JSON request; throws an Error whose message is the server's explanation. */
export async function api(path, { method = "GET", body } = {}) {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === "string" ? detail : detail?.message || `Request failed (${res.status})`);
  }
  return data;
}

/** Listen for live changes to one circle; reconnects if the connection drops. */
export function connect(circleId, onEvent) {
  let socket;
  let stopped = false;
  const open = () => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${proto}://${location.host}/ws/${circleId}`);
    socket.onmessage = (e) => onEvent(JSON.parse(e.data));
    socket.onclose = () => { if (!stopped) setTimeout(open, 1000); };
  };
  open();
  return () => { stopped = true; socket?.close(); };
}

const stroke = (d) => `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
export const ICON = {
  // RoleEdge's mark: three people (roles) and the links between them (edges); the caregiver is the one on top
  mark: `<svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="8" style="fill:var(--mark-bg,#0A0A0A)"/><path d="M9.5 22 22.5 22" stroke-width="2" stroke-linecap="round" style="stroke:var(--mark-fg,#fff);stroke-opacity:.45"/><path d="M9.5 22 16 9.5 22.5 22" fill="none" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="stroke:var(--mark-fg,#fff)"/><g style="fill:var(--mark-fg,#fff)"><circle cx="16" cy="9.5" r="3.2"/><circle cx="9.5" cy="22" r="2.7"/><circle cx="22.5" cy="22" r="2.7"/></g></svg>`,
  close: stroke('<path d="M6 6l12 12M18 6L6 18"/>'),
  play: stroke('<path d="M8 5v14l11-7z" fill="currentColor" stroke="none"/>'),
  stop: stroke('<rect x="7" y="7" width="10" height="10" rx="1.5" fill="currentColor" stroke="none"/>'),
  send: stroke('<path d="M5 12h14M13 6l6 6-6 6"/>'),
  mic: stroke('<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>'),
  assistant: stroke('<path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/>'),
  shield: stroke('<path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/>'),
  alert: stroke('<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17h.01"/>'),
  phone: stroke('<path d="M6 3h4l2 5-2.5 1.5a11 11 0 0 0 5 5L16 12l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 4 5a2 2 0 0 1 2-2z"/>'),
};

/** Like connect(), but can also send: her phone reports what is on its screen so the caregiver's mirror follows it. */
export function live(circleId, onEvent) {
  let socket;
  let stopped = false;
  let connectedBefore = false;
  const open = () => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${proto}://${location.host}/ws/${circleId}`);
    // After a dropped connection, anything that changed meanwhile was missed: tell the page to fetch it again.
    socket.onopen = () => { if (connectedBefore) onEvent({ type: "resync" }); connectedBefore = true; };
    socket.onmessage = (e) => { try { onEvent(JSON.parse(e.data)); } catch (err) { console.error(err); } };
    socket.onclose = () => { if (!stopped) setTimeout(open, 1000); };
  };
  open();
  return {
    stop() { stopped = true; socket?.close(); },
    send(message) { if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message)); },
  };
}

// ---------------------------------------------------------------- live redraws without flashing

const keyOf = (node) => (node.nodeType === 1 ? node.getAttribute("data-card") || node.getAttribute("data-key") || node.id || null : null);

/** Make the element ``el`` match ``html`` by changing only what differs. Live updates arrive many times a second
 *  while agents work; replacing the markup each time re-created every picture and video (they flashed or restarted)
 *  and lost the scroll position. Unchanged nodes, and so pictures, videos, audio and focus, stay as they are.
 *  Children with data-card, data-key or id are matched by that key; an element with data-keep is left alone (a
 *  mounted viewer lives there). */
export function morph(el, html) {
  const next = document.createElement("template");
  next.innerHTML = html;
  morphChildren(el, next.content);
}

/** The same for the element itself: ``html`` is its new outer markup (one element). */
export function morphElement(el, html) {
  const next = document.createElement("template");
  next.innerHTML = html.trim();
  if (next.content.firstElementChild) morphNode(el, next.content.firstElementChild);
}

function morphNode(from, to) {
  if (from.nodeType !== to.nodeType || from.nodeName !== to.nodeName) { from.replaceWith(to); return; }
  if (from.nodeType !== 1) { if (from.nodeValue !== to.nodeValue) from.nodeValue = to.nodeValue; return; }
  if (from.hasAttribute("data-keep")) return;
  for (const { name } of [...from.attributes]) if (!to.hasAttribute(name)) from.removeAttribute(name);
  for (const { name, value } of [...to.attributes]) if (from.getAttribute(name) !== value) from.setAttribute(name, value);
  if (from.nodeName === "INPUT" || from.nodeName === "TEXTAREA") return; // keep what someone is typing or picked
  morphChildren(from, to);
}

function morphChildren(from, to) {
  const keyed = new Map();
  for (const child of from.childNodes) { const k = keyOf(child); if (k) keyed.set(k, child); }
  const wanted = new Set([...to.childNodes].map(keyOf).filter(Boolean));
  let cursor = from.firstChild;
  const skipGone = () => { // a keyed node that is no longer wanted goes, so the nodes after it can still be matched
    while (cursor && keyOf(cursor) && !wanted.has(keyOf(cursor))) { const after = cursor.nextSibling; cursor.remove(); cursor = after; }
  };
  for (const want of [...to.childNodes]) {
    skipGone();
    const k = keyOf(want);
    let match = null;
    if (k) match = keyed.get(k) || null;
    else if (cursor && !keyOf(cursor) && cursor.nodeType === want.nodeType && cursor.nodeName === want.nodeName) match = cursor;
    if (match) {
      if (k) keyed.delete(k);
      if (match === cursor) cursor = cursor.nextSibling; else from.insertBefore(match, cursor);
      morphNode(match, want);
    } else {
      from.insertBefore(want, cursor);
    }
  }
  while (cursor) { const after = cursor.nextSibling; cursor.remove(); cursor = after; }
}
