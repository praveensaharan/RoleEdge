// The share box: words, photos and videos, a link or a voice note; "Research first" (the Studio swarm) or "Quick
// message" (one rewrite, no research). Nothing here reaches her: a share becomes a card that waits for your approval.
import { api, esc, ICON } from "../common.js";
import { icon } from "../studio-view.js";
import { $, isChild, notify, recipient, recipients, state } from "./shared.js";

const MAX_FILES = 6; // the server's limits (studio_routes.py), checked here first so you hear about them before uploading
const MAX_FILE_BYTES = 50_000_000;
const ALLOWED = new Set(["image/jpeg", "image/png", "image/webp", "image/gif", "video/mp4", "video/quicktime", "video/webm",
  "audio/webm", "audio/ogg", "audio/mpeg", "audio/mp4", "audio/x-m4a", "audio/aac", "audio/wav", "audio/x-wav"]);
const allowed = (f) => ALLOWED.has(f.type.split(";")[0].trim().toLowerCase());
const SOCIAL_VIDEO = /(^|\.)(instagram\.com|tiktok\.com|facebook\.com|fb\.watch|youtube\.com|youtu\.be)$/i;
const thumbs = new WeakMap(); // File -> object URL, so a redraw doesn't leak a new URL each time

/** Wire the share box. `onShared(item)` gets the new card's item; `onRecipient()` runs when "Explain it to" changes. */
export function initComposer(onShared, onRecipient) {
  // back from Google's sign-in page
  const params = new URLSearchParams(location.search);
  const back = params.get("connect");
  if (back) {
    const said = { google: "Your Google account is connected. Her questions about deliveries and your week now use your own Gmail and Calendar.",
      failed: "Google sign-in didn't finish. Try again from Apps.", cancelled: "Google sign-in was cancelled. The demo accounts still answer." }[back];
    if (said) setTimeout(() => notify(said, { error: back === "failed" }), 600);
    params.delete("connect");
    history.replaceState(null, "", `${location.pathname}${params.toString() ? `?${params}` : ""}`);
  }
  const [media, link, voice, app] = document.querySelectorAll("[data-attach]");
  media.innerHTML = `${icon("video", 16)}Photo or video`;
  link.innerHTML = `${icon("link", 16)}Link`;
  voice.innerHTML = `${icon("volume", 16)}Voice note`;
  app.innerHTML = `${icon("document", 16)}Apps`;
  $("link-icon").innerHTML = icon("link", 16);
  $("link-close").innerHTML = ICON.close;
  $("mode").innerHTML = `<button type="button" data-mode="studio">${icon("activity", 15)}Research first</button><button type="button" data-mode="quick" title="One rewrite in her words, no research">Quick message</button>`;
  $("voice").innerHTML = `<button type="button" data-voice="mine">My voice</button><button type="button" data-voice="assistant">Assistant</button>`;

  $("voice").onclick = async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    setVoice(b.dataset.voice);
    await api(`/api/circles/${state.circle.id}/settings`, { method: "PATCH", body: { voice: b.dataset.voice } }).catch((err) => notify(err.message));
  };
  $("mode").onclick = (e) => { const b = e.target.closest("button"); if (b && !b.disabled) setMode(b.dataset.mode); };
  $("for").onclick = (e) => {
    const b = e.target.closest("[data-to]");
    if (b && b.dataset.to !== state.to) { setRecipient(b.dataset.to); onRecipient(); }
  };
  $("immediate").onchange = async (e) => {
    try { state.circle = await api(`/api/circles/${state.circle.id}/settings`, { method: "PATCH", body: { send_immediately: e.target.checked } }); }
    catch (err) { e.target.checked = !e.target.checked; notify(err.message); }
  };

  document.querySelector(".attach-row").onclick = (e) => {
    const b = e.target.closest("[data-attach]");
    if (!b) return;
    if (b.dataset.attach === "media") $("file").click();
    if (b.dataset.attach === "link") { $("link-row").hidden = false; $("link").focus(); setMode("studio"); }
    if (b.dataset.attach === "voice") toggleRecording(b);
    if (b.dataset.attach === "app") toggleApps(b);
  };
  $("apps").onclick = async (e) => {
    const tab = e.target.closest("[data-app-tab]");
    if (tab) { showApp(tab.dataset.appTab); return; }
    const connect = e.target.closest("[data-connect]");
    if (connect) { openConnect(connect.dataset.connect); return; }
    const disconnect = e.target.closest("[data-disconnect]");
    if (disconnect) {
      try { await api(`/api/circles/${state.circle.id}/connect/${disconnect.dataset.disconnect}/disconnect`, { method: "POST" }); await reloadApps(disconnect.dataset.disconnect); notify("Disconnected. The demo account answers again.", { error: false }); }
      catch (err) { notify(err.message); }
      return;
    }
    if (e.target.closest("[data-connect-notion]")) { connectNotion(); return; }
    if (e.target.closest("[data-add-open]")) { const f = $("apps").querySelector(".app-add:not(.app-connect)"); f.hidden = !f.hidden; if (!f.hidden) f.querySelector("input, textarea")?.focus(); return; }
    if (e.target.closest("[data-add-cancel]")) { $("apps").querySelector(".app-add:not(.app-connect)").hidden = true; return; }
    const remove = e.target.closest("[data-remove]");
    if (remove) {
      try { await api(`/api/circles/${state.circle.id}/apps/${openApp}/items/${remove.dataset.remove}`, { method: "DELETE" }); showApp(openApp); }
      catch (err) { notify(err.message); }
      return;
    }
    const page = e.target.closest("[data-ref]");
    if (!page) return;
    state.ref = { ref: page.dataset.ref, title: page.dataset.title, app: page.dataset.app, thumb: page.dataset.thumb || "" };
    toggleApps(document.querySelector('[data-attach="app"]'), false);
    setMode("studio");
    drawAttachments();
  };
  $("link-close").onclick = () => { $("link").value = ""; $("link-row").hidden = true; };
  $("link").onchange = () => {
    let host = "";
    try { host = new URL($("link").value.trim()).hostname; } catch { return; }
    if (SOCIAL_VIDEO.test(host) && !state.files.some((f) => f.type.startsWith("video/"))) {
      notify("The agents will open the reel, save its video and caption, and watch it whole. A post that is only photos, or one behind a login, needs the pictures or the video attached.", { error: false });
    }
  };
  $("file").onchange = () => { addFiles([...$("file").files]); $("file").value = ""; };
  $("attachments").onclick = (e) => {
    if (e.target.closest("[data-drop-ref]")) { state.ref = null; drawAttachments(); return; }
    const b = e.target.closest("[data-drop]");
    if (!b) return;
    const [dropped] = state.files.splice(Number(b.dataset.drop), 1);
    forget(dropped);
    drawAttachments();
  };
  $("composer").ondragover = (e) => e.preventDefault();
  $("composer").ondrop = (e) => { e.preventDefault(); addFiles([...e.dataTransfer.files]); };
  $("composer").onsubmit = (e) => { e.preventDefault(); share(onShared); };
  $("text").onkeydown = (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) $("composer").requestSubmit(); };
}

/** Draw "Explain it to" for the open circle: the parent, then each child with their age. */
export function drawRecipients() {
  if (!recipients().some((m) => m.id === state.to)) state.to = "";
  $("for").innerHTML = recipients().map((m, k) => `<button type="button" data-to="${k ? esc(m.id) : ""}">`
    + `${esc(m.call_name)}`
    + `<small>${m.age ?? ""}</small></button>`).join("");
  setRecipient(state.to);
}

function setRecipient(to) {
  state.to = to;
  for (const b of $("for").children) b.setAttribute("aria-pressed", String(b.dataset.to === to));
  const child = isChild(recipient());
  const quick = $("mode").querySelector('[data-mode="quick"]');
  quick.disabled = child; // quick messages are for the parent; a child's pack always gets research and a safety review
  quick.title = child ? "For children, everything is researched and reviewed first." : "";
  if (child) setMode("studio"); else hint();
}

export function setVoice(voice) {
  state.voice = voice;
  for (const b of $("voice").children) b.setAttribute("aria-pressed", String(b.dataset.voice === voice));
  hint();
}

export function setMode(mode) {
  state.mode = mode;
  for (const b of $("mode").children) b.setAttribute("aria-pressed", String(b.dataset.mode === mode));
  $("send").innerHTML = mode === "studio" ? `${icon("activity", 16)}Research and plan` : `${icon("send", 16)}Prepare message`;
  hint();
}

function hint() {
  if (!state.circle) return;
  const voice = state.voice === "mine" ? "in your voice" : "from your assistant";
  const person = recipient(), name = person.call_name;
  $("compose-hint").textContent = state.mode === "quick" ? `Quick: rewritten for ${name} ${voice}, no research.`
    : isChild(person) ? `Research first, then a child-safety review: a minute or two, a few cents. Nothing reaches ${name} until you approve.`
    : `Research first: a minute or two, a few cents. Nothing reaches ${name} until you approve.`;
  // a reel's caption often names what the video only shows (a film's title, the sites in a list); a saved video loses it
  if (state.mode !== "quick" && state.files.some((f) => f.type.startsWith("video/"))) $("compose-hint").textContent += " Paste the reel's caption too, if it has one.";
}

// ---------------------------------------------------------------- attachments

function addFiles(files) {
  const usable = files.filter((f) => allowed(f) && f.size <= MAX_FILE_BYTES);
  const room = MAX_FILES - state.files.length;
  if (usable.length < files.length) notify("Only photos (JPEG, PNG, WebP, GIF), videos and voice notes up to 50 MB can be shared.");
  else if (usable.length > room) notify(`Up to ${MAX_FILES} files per share.`);
  state.files.push(...usable.slice(0, Math.max(0, room)));
  if (usable.length) setMode("studio");
  drawAttachments();
}

function forget(file) {
  if (file && thumbs.has(file)) { URL.revokeObjectURL(thumbs.get(file)); thumbs.delete(file); }
}

function thumb(file) {
  if (!thumbs.has(file)) thumbs.set(file, URL.createObjectURL(file));
  return thumbs.get(file);
}

// ---------------------------------------------------------------- apps: the demo accounts (Gmail, Slack, Google Photos,
// Zoom), Notion, and the apps not connected yet, one tab each; pick an item to share it

let brands = null; // the apps' own marks, monochrome (web/app/brands.json)
let apps = []; // GET /api/connectors
let openApp = "";
const brandMark = (slug, size = 18) => {
  const b = brands?.icons[slug];
  return b ? `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="${esc(b.path)}"/></svg>` : "";
};
// Times in the family's own time zone (a meeting at 19:00 in Tokyo is 19:00 on the card, wherever you are)
const tz = () => state.circle?.parent?.timezone || undefined;
const fmt = (iso, opts) => { const d = new Date(iso); return Number.isNaN(+d) ? "" : d.toLocaleString([], { timeZone: tz(), ...opts }); };
const when = (iso) => {
  const day = (x) => fmt(x, { year: "numeric", month: "numeric", day: "numeric" });
  return day(iso) === day(new Date().toISOString()) ? fmt(iso, { hour: "2-digit", minute: "2-digit" }) : fmt(iso, { month: "short", day: "numeric" });
};

async function toggleApps(button, open = $("apps").hidden) {
  $("apps").hidden = !open;
  button.setAttribute("aria-expanded", String(open));
  if (!open) return;
  $("apps").innerHTML = `<div class="apps-loading">Loading your apps…</div>`;
  try {
    brands ||= await fetch("/assets/brands.json").then((r) => r.json()).catch(() => ({ icons: {} }));
    apps = await api(`/api/connectors?circle=${encodeURIComponent(state.circle.id)}`);
    const tabs = apps.map((a) => `<button type="button" class="app-tab" role="tab" data-app-tab="${esc(a.id)}">
      <span class="app-icon">${brandMark(a.id, 15) || icon(a.icon, 15)}</span><span>${esc(a.label)}</span><i class="st ${a.connected ? (a.demo ? "demo" : "on") : ""}"></i></button>`).join("");
    $("apps").innerHTML = `<div class="app-tabs" role="tablist" aria-label="Apps">${tabs}</div><div class="app-pane" role="tabpanel"></div>`;
    showApp(openApp && apps.some((a) => a.id === openApp) ? openApp : apps[0].id);
  } catch (err) {
    $("apps").innerHTML = `<div class="apps-loading">${esc(err.message)}</div>`;
  }
}

async function showApp(id) {
  openApp = id;
  const app = apps.find((a) => a.id === id);
  if (!app) return;
  $("apps").querySelectorAll("[data-app-tab]").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.appTab === id)));
  const pane = $("apps").querySelector(".app-pane");
  const status = app.connected ? (app.demo ? `<span class="badge info"><i></i>Demo account</span>` : `<span class="badge ok"><i></i>${app.own ? "Your account" : "Connected"}</span>`)
    : `<span class="badge"><i></i>Not connected</span>`;
  // your own account, or the demo one: connect or disconnect right here (Gmail and Calendar by Google sign-in, Notion by its secret)
  const own = app.can_connect ? (app.own ? `<button type="button" class="btn ghost sm" data-disconnect="${esc(app.id)}">Disconnect</button>`
    : `<button type="button" class="btn sm" data-connect="${esc(app.id)}">Connect your own</button>`) : "";
  const head = `<header class="pane-head"><span class="app-icon lg">${brandMark(app.id, 20) || icon(app.icon, 20)}</span><div><b>${esc(app.label)}</b><small>${esc(app.detail)}</small></div>${status}${own}</header>`
    + (app.can_connect && !app.own ? connectPanel(app) : "");
  if (!app.connected) { pane.innerHTML = `${head}<p class="app-note">Nothing to share from ${esc(app.label)} yet.</p>`; return; }
  pane.innerHTML = `${head}<div class="apps-loading">Loading…</div>`;
  let items;
  try { items = await api(`/api/connectors/${app.id}/items?circle=${encodeURIComponent(state.circle.id)}`); }
  catch (err) { if (openApp === id) pane.innerHTML = `${head}<p class="app-note">${esc(err.message)}</p>`; return; }
  if (openApp !== id) return; // another tab was opened meanwhile
  const parent = state.circle.parent.call_name;
  const context = { zoom: `Work meetings tell RoleEdge when you're busy: ${parent} only hears that you're in a meeting, and until when.`,
                    gmail: `Deliveries and trips can help answer ${parent}; work mail stays yours.`,
                    slack: `Questions from ${parent} that need you arrive here as one-tap answers.`,
                    googlecalendar: `${parent} can ask when you're visiting or free: she hears family events and trips, and only "busy" for work.` }[app.id];
  const add = app.demo && ADDABLE[app.id] ? addForm(app) : "";
  pane.innerHTML = head.replace("</header>", add ? `<button type="button" class="btn outline sm" data-add-open>${icon("edit", 14)}Add</button></header>` : "</header>") +
    add + (context ? `<p class="app-context">${icon("lock", 13)}${esc(context)}</p>` : "") + (items.length ? appItems(app, items) : `<p class="app-note">Nothing here yet.</p>`) +
    `<p class="app-foot">Pick one to share it. What it says is read as data and goes through the same checks as anything you type.${add ? " What you add stays in this demo account, and the agents pick it up like anything else here." : ""}</p>`;
  const form = pane.querySelector(".app-add:not(.app-connect)");
  if (form) {
    form.querySelector("[data-add-submit]").onclick = () => addItem(app, form);
    form.onkeydown = (e) => { if (e.key === "Enter" && e.target.tagName === "INPUT") { e.preventDefault(); addItem(app, form); } }; // not the share box's submit
  }
}

// ---------------------------------------------------------------- your own accounts

/** The panel under an app that can be connected: Google sign-in, Notion's secret, or what the server still needs. */
function connectPanel(app) {
  const google = app.id === "gmail" || app.id === "googlecalendar";
  const body = app.setup ? `<p class="app-note">${esc(app.setup)}</p>`
    : google ? `<p class="app-note">You'll sign in with Google and allow read-only access${app.id === "gmail" ? " to your mail" : " to your calendar"}. Nothing is ever sent or changed. Until then, and after you disconnect, this demo account answers.</p>
      <div class="add-actions"><button type="button" class="btn ghost sm" data-connect-close>Cancel</button><a class="btn sm" href="/api/connect/google/start?circle=${encodeURIComponent(state.circle.id)}&which=gmail,googlecalendar">Sign in with Google</a></div>`
    : `<p class="app-note">Create an internal integration at notion.so/my-integrations, share your family pages with it, and paste its secret here. It is stored encrypted and only read.</p>
      <div class="add-fields"><label class="wide"><span>Integration secret</span><input type="password" name="notion-secret" autocomplete="off" placeholder="ntn_…"></label></div>
      <p class="add-error" hidden></p><div class="add-actions"><button type="button" class="btn ghost sm" data-connect-close>Cancel</button><button type="button" class="btn sm" data-connect-notion>Connect Notion</button></div>`;
  return `<div class="app-add app-connect" hidden><b>Connect your own ${esc(app.label)}</b>${body}</div>`;
}

function openConnect() {
  const panel = $("apps").querySelector(".app-connect");
  if (!panel) return;
  panel.hidden = !panel.hidden;
  panel.querySelector("input")?.focus();
  panel.querySelector("[data-connect-close]")?.addEventListener("click", () => { panel.hidden = true; }, { once: true });
}

async function connectNotion() {
  const panel = $("apps").querySelector(".app-connect");
  const input = panel.querySelector('[name="notion-secret"]');
  const error = panel.querySelector(".add-error");
  try {
    const done = await api(`/api/circles/${state.circle.id}/connect/notion`, { method: "POST", body: { token: input.value.trim() } });
    input.value = "";
    await reloadApps("notion");
    notify(`Connected ${done.account}: ${done.pages} pages shared with it.`, { error: false });
  } catch (err) { error.textContent = err.message; error.hidden = false; }
}

async function reloadApps(id) {
  apps = await api(`/api/connectors?circle=${encodeURIComponent(state.circle.id)}`);
  $("apps").querySelectorAll("[data-app-tab]").forEach((t) => {
    const a = apps.find((x) => x.id === t.dataset.appTab);
    t.querySelector(".st")?.classList.toggle("demo", Boolean(a?.demo));
    t.querySelector(".st")?.classList.toggle("on", Boolean(a && a.connected && !a.demo));
  });
  showApp(id);
}

// What you can add to each demo app: the fields of a new mail, message, meeting or event.
const ADDABLE = {
  gmail: { verb: "Add a mail", fields: [["sender", "From", "Amazon <shipment-tracking@amazon.com>"], ["title", "Subject", "Your parcel arrives Thursday"],
    ["body", "Message", "Your order arrives Thursday between 2 PM and 6 PM.", "area"], ["spoofed", "Fails the sender check (a fake courier mail)", "", "check"]] },
  slack: { verb: "Add a message", fields: [["where", "Channel", "#family"], ["sender", "From", "Daniel (brother)"], ["body", "Message", "I'm taking Mom to lunch on Sunday at 12:30.", "area"]] },
  zoom: { verb: "Add a meeting", fields: [["title", "Topic", "Call with Mom's doctor"], ["at", "When", "", "when"], ["minutes", "Minutes", "30", "number"], ["where", "With", "Mom, Daniel"], ["work", "A work meeting (she only hears \"busy\")", "", "check"]] },
  googlecalendar: { verb: "Add an event", fields: [["title", "Title", "Dinner with Mom"], ["at", "When", "", "when"], ["minutes", "Minutes", "90", "number"], ["where", "Where", "Mom's home"],
    ["kind", "What it is", "", "kind"]] },
};
const KINDS = [["family_events", "Family event (she can know)"], ["travel", "Travel (she can know)"], ["work", "Work (she only hears \"busy\")"]];

function addForm(app) {
  const spec = ADDABLE[app.id];
  // tomorrow at noon in the family's time zone (the times you add are read in it, like the rest of the demo week)
  const local = `${new Date(Date.now() + 86_400_000).toLocaleDateString("sv-SE", { timeZone: tz() })}T12:00`;
  const field = ([name, label, example, type]) => {
    if (type === "check") return `<label class="add-check"><input type="checkbox" name="${name}"> ${esc(label)}</label>`;
    if (type === "kind") return `<label><span>${esc(label)}</span><select name="kind">${KINDS.map(([v, l]) => `<option value="${v}">${esc(l)}</option>`).join("")}</select></label>`;
    if (type === "area") return `<label class="wide"><span>${esc(label)}</span><textarea name="${name}" rows="2" placeholder="${esc(example)}"></textarea></label>`;
    if (type === "when") return `<label><span>${esc(label)}</span><input type="datetime-local" name="at" value="${local}" required></label>`;
    return `<label><span>${esc(label)}</span><input name="${name}" ${type === "number" ? `type="number" min="5" max="1440" value="${esc(example)}"` : `placeholder="${esc(example)}"`}></label>`;
  };
  // a div, not a form: the apps panel sits inside the share box's form, and a form can't hold another one
  return `<div class="app-add" role="group" aria-label="${esc(spec.verb)}" hidden><b>${esc(spec.verb)}</b><div class="add-fields">${spec.fields.map(field).join("")}</div>
    <p class="add-error" hidden></p><div class="add-actions"><button type="button" class="btn ghost sm" data-add-cancel>Cancel</button><button type="button" class="btn sm" data-add-submit>Add</button></div></div>`;
}

async function addItem(app, form) {
  const data = Object.fromEntries([...form.querySelectorAll("[name]")].map((f) => [f.name, f.type === "checkbox" ? (f.checked ? "on" : "") : f.value]));
  const body = { title: data.title || "", sender: data.sender || "", where: data.where || "", body: data.body || "",
                 at: data.at || "", minutes: Number(data.minutes || 0), kind: data.work ? "work" : data.kind || "family_events", verified: !data.spoofed };
  const error = form.querySelector(".add-error");
  try {
    await api(`/api/circles/${state.circle.id}/apps/${app.id}/items`, { method: "POST", body });
    showApp(app.id);
  } catch (err) { error.textContent = err.message; error.hidden = false; }
}

function appItems(app, items) {
  const ref = (i) => `data-ref="${esc(app.id)}:${esc(i.id)}" data-title="${esc(i.title)}" data-app="${esc(app.id)}"${i.thumb ? ` data-thumb="${esc(i.thumb)}"` : ""}`;
  const tag = (i) => (i.badge ? `<span class="badge ${i.tone === "ok" ? "ok" : i.tone === "urgent" ? "danger" : ""}"><i></i>${esc(i.badge)}</span>` : "");
  if (app.id === "googlephotos") {
    return `<div class="photo-grid">${items.map((i) => `<button type="button" class="photo" ${ref(i)}><img src="${esc(i.thumb)}" alt="${esc(i.title)}" loading="lazy"><span>${esc(i.title)}</span></button>`).join("")}</div>`;
  }
  // what you added yourself can be removed (a separate button: a button can't sit inside the row's button)
  const row = (i, html) => (i.id.startsWith("add_") ? `<div class="app-added">${html}<button type="button" class="app-remove" data-remove="${esc(i.id)}" aria-label="Remove">${ICON.close}</button></div>` : html);
  const mine = (i) => (i.id.startsWith("add_") ? `<span class="badge info"><i></i>Added by you</span>` : "");
  if (app.id === "zoom" || app.id === "googlecalendar") {
    return `<div class="app-list">${items.map((i) => row(i, `<button type="button" class="app-row meet" ${ref(i)}><span class="cal"><small>${esc(fmt(i.edited, { weekday: "short" }))}</small><b>${esc(fmt(i.edited, { day: "numeric" }))}</b></span>
        <span class="main"><b>${esc(i.title)}</b><small>${esc(fmt(i.edited, { hour: "2-digit", minute: "2-digit" }))} · ${esc(i.snippet)}</small></span>${mine(i) || tag(i)}</button>`)).join("")}</div>`;
  }
  if (app.id === "gmail" || app.id === "slack") {
    const initials = (who) => esc((who.replace(/^[#@]/, "").split(/[·(]/).pop().trim() || who).slice(0, 1).toUpperCase());
    return `<div class="app-list">${items.map((i) => row(i, `<button type="button" class="app-row" ${ref(i)}>
      <span class="av">${initials(app.id === "slack" ? i.subtitle.split("·").pop() : i.subtitle)}</span><span class="main"><span class="who"><b>${esc(i.subtitle)}</b><small>${esc(when(i.edited))}</small></span>
      <span class="subj">${esc(app.id === "gmail" ? i.title : i.snippet)}</span>${app.id === "gmail" ? `<small class="snip">${esc(i.snippet)}</small>` : ""}</span>${mine(i)}${tag(i)}</button>`)).join("")}</div>`;
  }
  return `<div class="app-list">${items.map((i) => `<button type="button" class="app-row" ${ref(i)}><span class="main"><b>${esc(i.title)}</b><small>${esc((i.edited || "").slice(0, 10))}</small></span></button>`).join("")}</div>`;
}

function drawAttachments() {
  $("attachments").hidden = !state.files.length && !state.ref;
  const refApp = apps.find((a) => a.id === state.ref?.app);
  const ref = state.ref ? `<span class="att">${state.ref.thumb ? `<img src="${esc(state.ref.thumb)}" alt="">` : `<span class="att-icon">${brandMark(state.ref.app, 16) || icon("document", 18)}</span>`}<span>${esc(refApp?.label || state.ref.app)} · ${esc(state.ref.title)}</span>`
    + `<button type="button" class="icon-btn" data-drop-ref aria-label="Remove ${esc(state.ref.title)}">${ICON.close}</button></span>` : "";
  $("attachments").innerHTML = ref + state.files.map((f, k) => {
    const preview = f.type.startsWith("image/") ? `<img src="${thumb(f)}" alt="">`
      : `<span class="att-icon">${icon(f.type.startsWith("video/") ? "video" : "volume", 18)}</span>`;
    return `<span class="att">${preview}<span>${esc(f.name)}</span><button type="button" class="icon-btn" data-drop="${k}" aria-label="Remove ${esc(f.name)}">${ICON.close}</button></span>`;
  }).join("");
}

async function toggleRecording(button) {
  if (state.recorder) { state.recorder.stop(); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const chunks = [];
    const rec = new MediaRecorder(stream);
    rec.ondataavailable = (e) => chunks.push(e.data);
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      state.recorder = null;
      button.classList.remove("rec-on");
      button.setAttribute("aria-pressed", "false");
      button.innerHTML = `${icon("volume", 16)}Voice note`;
      if (chunks.length) addFiles([new File(chunks, "voice-note.webm", { type: rec.mimeType || "audio/webm" })]);
    };
    rec.start();
    state.recorder = rec;
    button.classList.add("rec-on");
    button.setAttribute("aria-pressed", "true");
    button.innerHTML = `${icon("pause", 16)}Stop recording`;
  } catch {
    notify("The microphone isn't available in this browser.");
  }
}

// ---------------------------------------------------------------- send

async function share(onShared) {
  const text = $("text").value.trim(), link = $("link").value.trim();
  if (!text && !link && !state.files.length && !state.ref) { $("text").focus(); return; }
  $("send").disabled = true;
  try {
    let item;
    if (state.mode === "quick" && !link && !state.files.length && !state.ref) {
      item = await api(`/api/circles/${state.circle.id}/compose`, { method: "POST", body: { text, voice: state.voice } });
    } else {
      const form = new FormData();
      form.append("text", text);
      form.append("link", link);
      form.append("to", state.to);
      form.append("ref", state.ref?.ref || "");
      form.append("ref_title", state.ref?.title || "");
      form.append("ref_thumb", state.ref?.thumb || "");
      for (const f of state.files) form.append("files", f, f.name);
      const res = await fetch(`/api/circles/${state.circle.id}/studio`, { method: "POST", body: form });
      item = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(item.detail || `Could not start the Studio (${res.status}).`);
    }
    $("text").value = ""; $("link").value = ""; $("link-row").hidden = true;
    state.files.forEach(forget);
    state.files = [];
    state.ref = null;
    drawAttachments();
    onShared(item);
  } catch (err) {
    notify(err.message);
  } finally {
    $("send").disabled = false;
  }
}
