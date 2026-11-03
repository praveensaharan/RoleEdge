// The caregiver's Studio. Share anything; agents research it, propose how to explain it, make the formats you pick,
// and you approve before she sees it. Her screen is live on the right, and what she does comes back to each share.
// This file wires the page together; the cards, the share box and the side tabs live in ./workspace/.
import { api, esc, ICON, live } from "./common.js";
import { icon, loadIcons, mountViewer } from "./studio-view.js";
import { genderOf } from "./voice.js";
import { card } from "./workspace/cards.js";
import { drawRecipients, initComposer, setMode, setVoice } from "./workspace/composer.js";
import { refreshUsage, renderActivity, renderTrends } from "./workspace/insights.js";
import { $, FORMATS, formatsFor, formatText, isChild, namesFor, notify, recipient, recipientOf, state } from "./workspace/shared.js";

const DEVICE_HEIGHT = 740;
const DEVICE_WIDTH = 360;

// ---------------------------------------------------------------- start

async function start() {
  await loadIcons();
  $("mark").innerHTML = ICON.mark;
  $("reset").innerHTML = `${icon("replay", 16)}<span class="lbl">Reset demo</span>`;
  initComposer(onShared, () => { describeRecipient(); loadPhone(); });
  state.circles = await api("/api/circles");
  $("circles").innerHTML = state.circles.map((c, k) => `<button type="button" data-circle="${esc(c.id)}">${esc(c.label)}</button>`).join("");
  const wanted = new URLSearchParams(location.search).get("circle");
  await openCircle(state.circles.some((c) => c.id === wanted) ? wanted : state.circles[0].id);
  window.addEventListener("resize", fitDevice);
}

async function openCircle(circleId) {
  state.link?.stop();
  const data = await api(`/api/circles/${circleId}`);
  Object.assign(state, { circle: data.circle, items: data.items, engine: data.engine, picks: {} });
  history.replaceState(null, "", `?circle=${circleId}`);
  for (const b of $("circles").children) b.setAttribute("aria-pressed", String(b.dataset.circle === circleId));
  $("eyebrow").textContent = `Studio · ${state.circle.label}`;
  $("immediate").checked = state.circle.send_immediately;
  setVoice(state.circle.voice);
  setMode(state.mode);
  drawRecipients();
  describeRecipient();
  loadPhone();
  render();
  showTab(state.tab);
  refreshUsage();
  state.link = live(circleId, onLive);
}

/** The page's words for whoever the next share is for: the parent, or a child. */
function describeRecipient() {
  const person = recipient(), name = person.call_name;
  const lang = person.language === "ja" ? "Japanese" : "English";
  const check = isChild(person) ? `check it's right for a ${person.age}-year-old` : "check it";
  $("headline").innerHTML = `Share anything with ${esc(name)}. <span>We'll find the best way to explain it.</span>`;
  const moments = formatsFor(person).map((f) => formatText(f, person)[0]);
  $("lead").textContent = `A photo, a video, a reel, a link, a few words, or an email, message, photo or meeting from your apps. Agents research it, ${check}, `
    + `make it into moments for ${name} in ${lang} (${moments.slice(0, -1).join(", ")} or ${moments.at(-1)}), and Muse Wonder verifies the whole pack. `
    + `You approve before ${name} sees anything, and what ${name} does comes back to you.`;
  $("text").placeholder = isChild(person)
    ? `What do you want ${name} to understand? For example: a reel you saw, something from school, or how something works.`
    : `What do you want ${name} to understand? For example: a notice that came in, a reel you saw, or news from your week.`;
  $("her-title").textContent = `${name}'s screen`;
  $("her-note").textContent = `What ${name} sees right now. When something is opened it shows here, and what ${name} did comes back to the share.`;
  $("subs-toggle").hidden = person.language === "en";
}

function onLive(event) {
  if (event.type === "resync") { resync(); return; }
  if (event.type === "agent") {
    const item = state.items.find((i) => i.id === event.event.item_id);
    if (item) { (item.payload.agents ||= []).push(event.event); patch(item); }
    return;
  }
  if (event.type !== "item") return;
  upsert(event.item);
  if (state.tab === "trends" && event.item.kind === "summary") renderTrends();
  if (state.tab === "activity") renderActivity();
  refreshUsage();
}

/** The circle's settings changed on the server (a permission was allowed or stopped). */
async function refreshCircle() {
  const data = await api(`/api/circles/${state.circle.id}`).catch(() => null);
  if (data && data.circle.id === state.circle.id) state.circle = data.circle;
  if (state.tab === "activity") renderActivity();
}

/** After a dropped connection: fetch the circle again, since live updates were missed meanwhile. */
async function resync() {
  const circleId = state.circle.id;
  const data = await api(`/api/circles/${circleId}`).catch(() => null);
  if (!data || state.circle.id !== circleId) return;
  state.items = data.items;
  render();
}

function onShared(item) {
  upsert(item);
  showTab("stream");
}

/** Put a new or changed item into the stream, redrawing only its card when it's already shown. */
function upsert(item) {
  const i = state.items.findIndex((x) => x.id === item.id);
  if (i >= 0) { state.items[i] = item; patch(item); return; }
  state.items.push(item);
  render();
}

// ---------------------------------------------------------------- the stream (newest first)

function render() {
  const visible = state.items.filter((i) => !i.payload.discarded).reverse();
  keepOpenPreviews(() => {
    $("tab-stream").innerHTML = visible.length ? visible.map(card).join("")
      : `<div class="empty">Nothing shared yet. Share something with ${esc(recipient().call_name)} above: the agents take it from there.</div>`;
  });
  $("tabs").querySelector('[data-tab="stream"]').innerHTML = `Shares<span class="count">${visible.length}</span>`;
}

function patch(item) {
  const el = document.querySelector(`[data-card="${item.id}"]`);
  if (!el || item.payload.discarded) { render(); return; }
  keepOpenPreviews(() => { el.outerHTML = card(item); });
}

/** Redraw, but move any open preview into the redrawn card so it keeps playing (her engagement updates the card
 *  while you watch); previews whose card is gone are stopped. */
function keepOpenPreviews(redraw) {
  const open = [...document.querySelectorAll("#tab-stream .preview-slot:not([hidden])")];
  redraw();
  for (const slot of open) document.getElementById(slot.id)?.replaceWith(slot);
  for (const [itemId, viewer] of Object.entries(state.viewers)) {
    if (open.some((slot) => slot.isConnected && slot.id === `slot-${itemId}`)) continue;
    viewer.stop?.();
    delete state.viewers[itemId];
  }
}

$("tab-stream").onclick = async (e) => {
  const pick = e.target.closest("[data-pick]");
  if (pick) { togglePick(pick.dataset.id, pick.dataset.pick); return; }
  const view = e.target.closest("[data-view]");
  if (view) { togglePreview(view.dataset.view, view.dataset.format); return; }
  const allow = e.target.closest("[data-allow]");
  if (allow) {
    const item = await run(allow, () => api(`/api/items/${allow.dataset.id}/allow`, { method: "POST", body: { decision: allow.dataset.allow } }));
    if (item) { upsert(item); refreshCircle(); }
    return;
  }
  const make = e.target.closest("[data-make]");
  if (make) { await run(make, () => api(`/api/items/${make.dataset.make}/studio/make`, { method: "POST", body: { formats: picksFor(make.dataset.make) } })); return; }
  const own = e.target.closest("button[data-own-voice]");
  if (own) { await ownVoice(own); return; }
  const act = e.target.closest("button[data-act]");
  if (!act) return;
  const action = act.dataset.act === "discard" ? "discard" : "approve";
  const body = action === "approve" ? { allow_soft: act.dataset.act === "anyway" } : undefined;
  const item = await run(act, () => api(`/api/items/${act.dataset.id}/${action}`, { method: "POST", body }));
  if (item) upsert(item);
};

// ---------------------------------------------------------------- your own voice on a quick message

async function ownVoice(button) {
  const id = button.dataset.id;
  if (button.dataset.ownVoice === "remove") {
    const item = await run(button, () => api(`/api/items/${id}/own-voice`, { method: "DELETE" }));
    if (item) upsert(item);
    return;
  }
  if (state.ownVoice) { state.ownVoice.recorder.stop(); return; } // the second tap stops and attaches it
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    const chunks = [];
    const recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (e) => chunks.push(e.data);
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      state.ownVoice = null;
      patch(itemById(id));
      if (chunks.length) attachVoice(id, new Blob(chunks, { type: recorder.mimeType || "audio/webm" }), "my-voice.webm");
    };
    state.ownVoice = { id, recorder };
    recorder.start();
    patch(itemById(id));
  } catch (err) { notify(`The microphone isn't available: ${err.message}`); }
}

async function attachVoice(id, blob, name) {
  const box = document.querySelector(`[data-card="${id}"] .own-voice`);
  box?.classList.add("busy");
  if (box) box.querySelector(".ov-text span").textContent = "Making it clearer and writing down your words…";
  const form = new FormData();
  form.append("audio", blob, name);
  try {
    const res = await fetch(`/api/items/${id}/own-voice`, { method: "POST", body: form });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `The recording didn't work (${res.status})`);
    upsert(data);
  } catch (err) { notify(err.message); patch(itemById(id)); }
}

document.addEventListener("change", (e) => {
  const input = e.target.closest?.("input[data-own-voice-file]");
  if (input?.files?.[0]) attachVoice(input.dataset.ownVoiceFile, input.files[0], input.files[0].name);
});

/** Disable the button while the request runs; on failure re-enable it and say why. */
async function run(button, request) {
  button.disabled = true;
  try { return await request(); }
  catch (err) { notify(err.message); button.disabled = false; return null; }
}

const itemById = (id) => state.items.find((i) => i.id === id);
const picksFor = (id) => state.picks[id] || itemById(id).payload.formats || [];

function togglePick(itemId, format) {
  const picks = new Set(picksFor(itemId));
  if (picks.has(format)) picks.delete(format); else picks.add(format);
  state.picks[itemId] = FORMATS.filter((f) => picks.has(f));
  patch(itemById(itemId));
  document.querySelector(`[data-card="${itemId}"] [data-pick="${format}"]`)?.focus(); // keep keyboard focus where it was
}

function togglePreview(itemId, format) {
  const slot = $(`slot-${itemId}`);
  if (!slot) return;
  state.viewers[itemId]?.stop?.();
  if (!slot.hidden && slot.dataset.format === format) { slot.hidden = true; return; }
  slot.hidden = false;
  slot.dataset.format = format;
  const item = itemById(itemId), person = recipientOf(item);
  slot.innerHTML = `<div class="label">Preview · ${esc(formatText(format, person)[0])} · as ${esc(person.call_name)} sees it</div><div class="pv" lang="${person.language}"></div>`;
  state.viewers[itemId] = mountViewer(slot.querySelector(".pv"), format, item.payload.outputs[format], {
    lang: person.language, names: namesFor(person), printable: true, picture: item.payload.outputs.picture?.image || "",
    gender: genderOf(state.circle.caregiver.relation),
  });
}

// ---------------------------------------------------------------- her screen

function loadPhone() {
  const person = recipient();
  const subs = person.language === "ja" && $("subs").checked ? 1 : 0;
  const member = isChild(person) ? `&member=${encodeURIComponent(person.id)}` : "";
  $("phone").src = `/phone/${state.circle.id}?mirror=1&subs=${subs}${member}`;
  fitDevice();
}
$("subs").onchange = loadPhone;

function fitDevice() {
  const room = window.innerHeight - 64 - 24 - 40 - 70; // top bar, padding, the panel's title and note
  const across = ($("device").parentElement?.clientWidth || DEVICE_WIDTH) / DEVICE_WIDTH; // a narrow screen
  const scale = Math.max(.6, Math.min(1, room / DEVICE_HEIGHT, across));
  $("device").style.transform = `scale(${scale})`;
  $("device").style.marginBottom = `${-DEVICE_HEIGHT * (1 - scale)}px`;
}

// ---------------------------------------------------------------- tabs, circles, reset

function showTab(name) {
  state.tab = name;
  for (const t of $("tabs").children) t.setAttribute("aria-selected", String(t.dataset.tab === name));
  for (const v of ["stream", "trends", "activity"]) $(`tab-${v}`).hidden = v !== name;
  if (name === "trends") renderTrends();
  if (name === "activity") renderActivity();
}
$("tabs").onclick = (e) => { const b = e.target.closest("[data-tab]"); if (b) showTab(b.dataset.tab); };
$("tab-activity").onclick = async (e) => {
  const stop = e.target.closest("[data-stop]");
  if (!stop) return;
  const done = await run(stop, () => api(`/api/circles/${state.circle.id}/permissions/${encodeURIComponent(stop.dataset.stop)}/stop`, { method: "POST" }));
  if (done) { state.circle = done; renderActivity(); notify("Stopped. The assistant will ask you first next time.", { error: false }); }
};
$("circles").onclick = (e) => {
  const b = e.target.closest("[data-circle]");
  if (b && b.dataset.circle !== state.circle.id) openCircle(b.dataset.circle).catch((err) => notify(err.message));
};

$("reset").onclick = async () => {
  if (!confirm("Reload the demo circles and clear the shares?")) return;
  try {
    await api("/api/demo/reset", { method: "POST" });
    await openCircle(state.circle.id);
  } catch (err) { notify(err.message); }
};

start().catch((err) => notify(`The Studio couldn't start: ${err.message}`));
