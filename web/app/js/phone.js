// Her screen (or a child's, with ?member=<id>): one calm app. Your talking avatar, messages, Studio packs (one row per
// moment), big replies and hold-to-talk. Something new slides in as a banner; a pack opens full screen, one moment at
// a time. Everything she does there is reported back as engagement. The family relay runs between the two screens: a
// child asks their grandparent something (typed, or held to talk), the grandparent answers by voice, and each hears
// the other's own voice. The real phone also reports what is on screen; the caregiver's mirror
// (?mirror=1) follows it (F8, "see what they see").
import { loadAvatar, TalkingHead } from "./avatar.js";
import { loadAvatar3D } from "./avatar3d.js";
import { genderOf, mute } from "./voice.js";
import { api, esc, ICON, live, morph } from "./common.js";
import { FORMAT_INFO, formatName, icon, loadIcons, mountViewer, speak, stopSpeech } from "./studio-view.js";

const circleId = location.pathname.split("/").pop();
const params = new URLSearchParams(location.search);
const mirror = params.get("mirror") === "1";
if (mirror) mute(); // the caregiver's copy of her screen stays quiet: only her phone speaks
const memberId = params.get("member") || ""; // a child's screen; empty = the parent's
const subs = params.get("subs") === "1";
const me = Math.random().toString(36).slice(2, 10); // tells this screen's own reports from the real phone's
const WORDS = {
  en: { placeholder: "Type a reply", empty: "Messages from {name} appear here.", assistant: "{name}'s assistant",
        sub: "{relation} · online", sending: "Sending…", wantOne: "I'd like one", listening: "Listening… let go to send", next: "Next", back: "Back", done: "Done",
        step: "Step {i} of {n}", micDenied: "The microphone is not available.", idle: "Tap a message to hear it.",
        now: "now", fromYou: "{name} sent you something", listen: "Listen", newPack: "New", son: "Your son", daughter: "Your daughter",
        dad: "Your dad", mom: "Your mom", order: "Order it", ask: "Ask {name} something", answering: "Answering {name}",
        answer: "Answer {name}", listenTo: "Listen to {name}", checking: "{caregiver} is checking it first", sentTo: "Sent to {name}",
        heard: "{name} heard it", askNext: "Ask: {q}", cancel: "Cancel",
        arriving: "On its way", shipped: "Shipped", transit: "On the way", delivered: "Delivered", fromMail: "From the {who} email · checked" },
  ja: { placeholder: "返事を入力", empty: "{name}さんからのメッセージがここに届きます。", assistant: "{name}さんのアシスタント",
        sub: "{relation} · オンライン", sending: "送信中…", wantOne: "ほしい", listening: "聞いています… 指を離すと送ります", next: "次へ", back: "戻る", done: "閉じる",
        step: "{n}つのうち{i}つめ", micDenied: "マイクが使えません。", idle: "メッセージをタップすると聞けます。",
        now: "今", fromYou: "{name}さんからお知らせ", listen: "聞く", newPack: "新着", son: "息子", daughter: "娘",
        dad: "お父さん", mom: "お母さん", order: "注文する", ask: "{name}にききたいこと", answering: "{name}へのお返事",
        answer: "{name}にお返事する", listenTo: "{name}の声を聞く", checking: "{caregiver}が確認しています", sentTo: "{name}に送りました",
        heard: "{name}が聞きました", askNext: "きいてみる：{q}", cancel: "やめる",
        arriving: "お届け予定", shipped: "発送", transit: "輸送中", delivered: "お届け", fromMail: "{who}のメールから · 確認済み" },
};
const CHILD_WORDS = { // simpler words on a child's screen
  en: {},
  ja: { placeholder: "かいてね", ask: "{name}に きいてみよう", listenTo: "{name}の こえを きく", checking: "{caregiver}が たしかめているよ",
        sentTo: "{name}に おくったよ", heard: "{name}が きいたよ", askNext: "きいてみる：{q}", listen: "きく", sending: "おくっています…" },
};

let circle;
let person; // whose screen this is: the parent, or one of the children
let isChild = false;
let items = [];
let words = WORDS.en;
let avatar = null;
let head = null;
let stage = null; // { item, index } - the talking stage for messages
let threeD = false;
let sheet = null; // { item, format, viewer }
let link = null;
let answering = null; // the relay being answered from the talk bar, if any

const $ = (id) => document.getElementById(id);

async function start() {
  document.body.classList.toggle("mirror", mirror);
  const [data] = await Promise.all([api(`/api/circles/${circleId}`), loadIcons()]);
  circle = data.circle;
  items = data.items;
  person = (memberId && circle.children?.find((c) => c.id === memberId)) || circle.parent;
  isChild = person.role === "child";
  words = { ...(WORDS[person.language] || WORDS.en), ...(isChild ? CHILD_WORDS[person.language] || {} : {}) };
  document.documentElement.lang = person.language;
  await setUpAvatar();
  const relation = isChild ? (/^his\b/i.test(person.relation) ? words.dad : words.mom)
    : /daughter/i.test(circle.caregiver.relation) ? words.daughter : words.son;
  $("who").textContent = callName();
  $("who-sub").textContent = words.sub.replace("{relation}", relation);
  $("brand").innerHTML = ICON.mark;
  setTalkTarget();
  $("reply-send").innerHTML = icon("send", 22);
  $("mic").innerHTML = ICON.mic;
  $("stage-close").innerHTML = ICON.close;
  $("sheet-done").innerHTML = ICON.close;
  $("sheet-done").setAttribute("aria-label", words.done);
  render();
  link = live(circleId, onLive);
  setInterval(tick, 15000);
  tick();
}

const callName = () => person.calls_caregiver || circle.caregiver.call_name_local || circle.caregiver.call_name;
const lang = () => (person.language === "ja" ? "ja-JP" : "en-US");
const received = (item) => ["sent", "played"].includes(item.status);
const shown = (item) => mine(item) || (isChild
  ? item.to === "child" && item.payload.recipient === person.id && received(item)
  : (item.to === "parent" && received(item)) || item.kind === "reply");
const grandparentName = () => person.calls_grandparent || circle.parent.call_name_local || circle.parent.call_name;
/** What this screen's person calls a family member. */
const nameOf = (memberId) => (memberId === circle.parent.id ? grandparentName()
  : (circle.children || []).find((c) => c.id === memberId)?.call_name_local || "");
const names = () => ({ caregiver: callName(), grandparent: grandparentName() });
const fmtName = (f) => formatName(f, person.language, names());
const fill = (template, values) => Object.entries(values).reduce((t, [k, v]) => t.replace(`{${k}}`, v), template);
const mine = (item) => item.kind === "relay" && item.payload.from === person.id;

async function resync() {
  const data = await api(`/api/circles/${circleId}`).catch(() => null);
  if (!data) return;
  const wasShown = new Set(items.filter(shown).map((i) => i.id));
  items = data.items;
  render();
  const fresh = items.filter((i) => shown(i) && i.kind !== "reply" && !mine(i) && !wasShown.has(i.id)); // arrived while offline
  if (fresh.length) arrived(fresh[fresh.length - 1]);
}

function onLive(event) {
  if (event.type === "resync") { resync(); return; }
  if (event.type === "screen") { if (mirror && event.from !== me) follow(event.screen); return; }
  if (event.type !== "item") return;
  const i = items.findIndex((x) => x.id === event.item.id);
  const wasShown = i >= 0 && shown(items[i]);
  if (i < 0) items.push(event.item); else items[i] = event.item;
  render();
  if (!wasShown && shown(event.item) && event.item.kind !== "reply" && !mine(event.item)) arrived(event.item);
}

function tick() {
  $("clock").textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false }); // the visitor's own time
}

// ---------------------------------------------------------------- arrival, and what the mirror follows

function arrived(item) {
  const title = item.kind === "studio" ? packTitle(item) : item.payload.message?.screen_title || "";
  const from = item.kind === "relay" ? title : words.fromYou.replace("{name}", callName());
  const line = item.kind === "relay" ? item.payload.message?.spoken_text || "" : title;
  $("banner").innerHTML = `<span class="bi">${ICON.mark}</span><div><small>RoleEdge · ${esc(words.now)}</small><b>${esc(from)}</b><span>${esc(line)}</span></div>`;
  // It stays until she opens it (or something newer replaces it): no timer, an older reader may need longer (WCAG 2.2.1).
  $("banner").dataset.item = item.id;
  $("banner").hidden = false;
  $("banner").onclick = () => openItem(item);
  if (item.kind === "alert") openItem(item);
}

function openItem(item) {
  if (item.kind === "studio") openSheet(item, firstFormat(item));
  else if (item.kind === "relay") { seen(item); listenRelay(item); }
  else openStage(item, true);
}

/** Tell the caregiver's mirror what is on screen (only the real phone reports; the mirror only follows). */
function tell() {
  if (mirror || !link) return;
  link.send({ type: "screen", from: me, screen: { view: sheet ? "sheet" : "app", item: sheet?.item.id || stage?.item.id || "",
                                                  format: sheet?.format || "", member: person.id } });
}

function follow(screen) {
  if ((screen.member || circle.parent.id) !== person.id) return; // another device in the family
  if (screen.view === "sheet") {
    if (sheet && sheet.item.id === screen.item && sheet.format === screen.format) return; // already showing it: don't restart it
    const item = items.find((i) => i.id === screen.item);
    if (item) { openSheet(item, screen.format, false); return; }
  }
  closeSheet(false);
}

// ---------------------------------------------------------------- feed

let drawn = -1; // how many cards the feed showed last time
/** Redraw the feed in place (pictures don't flash, the scroll stays), and go to the newest only when one arrived. */
function render() {
  const visible = items.filter(shown);
  morph($("feed"), visible.length ? visible.map((i) => card(i).replace(/^(\s*)<div /, `$1<div data-card="${i.id}" `)).join("") :
    `<p class="empty">${esc(words.empty.replace("{name}", callName()))}</p>`);
  if (visible.length > drawn) $("feed").scrollTop = $("feed").scrollHeight; // something new: show it
  drawn = visible.length;
}

function fromTag(item, extra = "") {
  return item.speaker === "assistant"
    ? `<div class="from"><span class="tag assistant"><i></i>${esc(words.assistant.replace("{name}", callName()))}</span>${extra}</div>`
    : `<div class="from"><span class="tag"><i></i>${esc(callName())}</span>${extra}</div>`;
}

function packTitle(item) {
  const first = (item.payload.outputs || {})[firstFormat(item)] || {};
  return first.title || first.root || "";
}
/** The pack's moments this screen can show (packs made with the earlier formats have none). */
const packFormats = (item) => (item.payload.formats || []).filter((f) => item.payload.outputs?.[f] && FORMAT_INFO[f]);
function firstFormat(item) { return packFormats(item)[0]; }
function finished(item, format) { return (item.payload.engagement || []).some((e) => e.format === format && e.event === "finished"); }

/** A price the assistant found: she can order it with one tap (her caregiver is asked the first time). */
const canOrder = (item) => item.payload.errand?.kind === "price" && !item.payload.order_requested;

function card(item) {
  if (item.kind === "reply") return `<div class="card mine">${esc(item.payload.text)}</div>`;
  if (item.kind === "relay") return relayCard(item);
  if (item.kind === "studio") {
    const formats = packFormats(item);
    if (!formats.length) return "";
    const ask = item.payload.plan?.conversation_starter;
    const isNew = !(item.payload.engagement || []).length;
    return `<div class="card pack">${fromTag(item, isNew ? `<span>${esc(words.newPack)}</span>` : "")}
      <div class="title">${esc(packTitle(item))}</div>${ask ? `<div class="ask">${esc(ask)}</div>` : ""}
      <div class="fmts">${formats.map((f) => `<button class="fmt" type="button" data-pack="${item.id}" data-format="${f}"><span class="fi ${f}">${icon(FORMAT_INFO[f].icon, 22)}</span>${esc(fmtName(f))}
        <span class="end${finished(item, f) ? " done" : ""}">${icon(finished(item, f) ? "check" : "arrow-right", 22)}</span></button>`).join("")}</div></div>`;
  }
  const m = item.payload.message;
  const own = item.payload.own_voice; // the caregiver recorded it: her captions are what they said
  const steps = m.steps.length ? `<ol class="steps">${m.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>` : "";
  const gloss = subs && m.english_gloss && !(own && own.caption !== m.spoken_text) ? `<div class="gloss">${esc(m.english_gloss)}</div>` : "";
  const replies = item.kind === "alert"
    ? `<a class="call" href="tel:${esc(item.payload.emergency)}">${esc(m.quick_replies[0] || item.payload.emergency)}</a>`
    : canOrder(item) ? `<div class="replies"><button type="button" class="order" data-order="${item.id}">${icon("cart", 20)}${esc(words.order)}</button></div>`
    : m.quick_replies.length ? `<div class="replies">${m.quick_replies.map((q) => `<button type="button" data-reply="${esc(q)}">${esc(q)}</button>`).join("")}</div>` : "";
  return `<div class="card${item.kind === "alert" ? " alert" : ""}">${fromTag(item)}
    <div class="title">${esc(m.screen_title)}</div>${product(item)}<div class="spoken">${esc(own?.caption || m.spoken_text)}</div>${gloss}${steps}${delivery(item)}
    <button class="listen" type="button" data-play="${item.id}"><span class="pb">${ICON.play}</span>${esc(own ? fill(words.listenTo, { name: callName() }) : words.listen)}<span class="wv">${"<i></i>".repeat(16)}</span></button>
    ${replies}</div>`;
}

/** A price she asked for, or an order placed: the product's photo above the words. */
function product(item) {
  const o = item.payload.errand?.offer;
  return o?.image ? `<div class="prod-row"><img src="${esc(o.image)}" alt=""><span>${esc(o.name)}<small>${esc(o.store)}</small></span></div>` : "";
}

/** A delivery answer, drawn: when it comes, a truck on its way along the route, and which checked mail it came from. */
const TRUCK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h11v9H3zM14 9h4l3 3v3h-7z"/><circle cx="7" cy="17.5" r="1.8"/><circle cx="17.5" cy="17.5" r="1.8"/></svg>';
function delivery(item) {
  const e = item.payload.errand;
  if (e?.kind !== "delivery" || !e.found || !e.eta) return "";
  const who = (e.used?.[0]?.sender || "").split("<")[0].trim();
  return `<div class="deliv"><div class="dl-head"><span class="dl-ic">${TRUCK}</span><div><small>${esc(words.arriving)}</small><b>${esc(e.eta)}</b></div></div>
    <div class="dl-track"><i class="dl-fill"></i><span class="dl-truck">${TRUCK}</span></div>
    <div class="dl-steps"><span>${esc(words.shipped)}</span><span>${esc(words.transit)}</span><span>${esc(words.delivered)}</span></div>
    ${who ? `<div class="dl-src">${icon("mail", 16)}<span>${esc(fill(words.fromMail, { who }))}</span></div>` : ""}</div>`;
}

// ---------------------------------------------------------------- the family relay

function relayCard(item) {
  const p = item.payload;
  if (mine(item)) {
    const to = nameOf(p.recipient);
    const state = p.stage === "writing" ? words.sending : item.status === "held" ? fill(words.checking, { caregiver: callName() })
      : item.status === "played" ? fill(words.heard, { name: to }) : fill(words.sentTo, { name: to });
    return `<div class="card mine">${esc(p.text)}<small class="relay-state">${esc(state)}</small></div>`;
  }
  const m = p.message, from = nameOf(p.from);
  const action = isChild
    ? (p.follow_up ? `<div class="replies"><button type="button" data-ask="${item.id}">${esc(fill(words.askNext, { q: p.follow_up }))}</button></div>` : "")
    : `<div class="replies"><button type="button" class="answer" data-answer="${item.id}">${icon("mic", 20)}${esc(fill(words.answer, { name: from }))}</button></div>`;
  return `<div class="card relay"><div class="from"><span class="tag family"><i></i>${esc(from)}</span></div>
    <div class="title">${esc(m.screen_title)}</div>${p.picture ? `<img class="relay-pic" src="${esc(p.picture)}" alt="">` : ""}
    <div class="spoken">${esc(m.spoken_text)}</div>${subs && m.english_gloss ? `<div class="gloss">${esc(m.english_gloss)}</div>` : ""}
    <button class="listen" type="button" data-relay="${item.id}"><span class="pb">${ICON.play}</span>${esc(p.audio ? fill(words.listenTo, { name: from }) : words.listen)}<span class="wv">${"<i></i>".repeat(16)}</span></button>
    ${action}</div>`;
}

let voice = null;
/** Play the speaker's own recording (or read the words aloud when it was typed), and tell the speaker it was heard. */
function listenRelay(item) {
  voice?.pause();
  stopSpeech();
  if (item.payload.audio) { voice = new Audio(item.payload.audio); voice.play().catch(() => {}); }
  else speak(item.payload.message.spoken_text, { lang: lang() });
  if (item.status === "sent" && !mirror) api(`/api/items/${item.id}/played`, { method: "POST" }).catch(() => {});
}

/** Who the talk bar sends to: a child always asks their grandparent; the grandparent while answering a relay. */
function setTalkTarget(item = null) {
  answering = item;
  const chip = $("relay-chip");
  if (isChild || answering) {
    const name = answering ? nameOf(answering.payload.from) : grandparentName();
    chip.innerHTML = `${icon("family", 16)}<span>${esc(fill(answering && !isChild ? words.answering : words.ask, { name }))}</span>`
      + (answering && !isChild ? `<button type="button" data-cancel>${esc(words.cancel)}</button>` : "");
    chip.hidden = false;
    $("reply").placeholder = isChild ? words.placeholder : fill(words.answering, { name });
  } else {
    chip.hidden = true;
    $("reply").placeholder = words.placeholder;
  }
}
$("relay-chip").onclick = (e) => { if (e.target.closest("[data-cancel]")) setTalkTarget(); };

/** Send a relay (typed text, a recording, or a question from a pack), as this screen's person. */
async function sendRelay({ text = "", audio = null, about = "", replyTo = answering?.id || "" } = {}) {
  if (mirror) return [];
  const form = new FormData();
  form.append("from", person.id);
  if (text) form.append("text", text);
  if (audio) form.append("audio", audio, "voice.webm");
  if (about) form.append("about", about);
  if (replyTo) form.append("reply_to", replyTo);
  const res = await fetch(`/api/circles/${circleId}/relay`, { method: "POST", body: form });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Could not send it.");
  answering = isChild ? answering : null; // the answer is sent: back to talking with the caregiver
  return [data];
}

$("feed").onclick = (e) => {
  const relayBtn = e.target.closest("button[data-relay]");
  if (relayBtn) { listenRelay(items.find((i) => i.id === relayBtn.dataset.relay)); return; }
  const answerBtn = e.target.closest("button[data-answer]");
  if (answerBtn) { setTalkTarget(items.find((i) => i.id === answerBtn.dataset.answer)); $("mic").focus(); return; }
  const askBtn = e.target.closest("button[data-ask]");
  if (askBtn) {
    const item = items.find((i) => i.id === askBtn.dataset.ask);
    askBtn.disabled = true;
    submit(() => sendRelay({ text: item.payload.follow_up, replyTo: item.id }));
    return;
  }
  const fmt = e.target.closest("button[data-pack]");
  if (fmt) { openSheet(items.find((i) => i.id === fmt.dataset.pack), fmt.dataset.format); return; }
  const orderBtn = e.target.closest("button[data-order]");
  if (orderBtn) {
    if (mirror) return; // the caregiver's mirror only watches
    orderBtn.disabled = true;
    api(`/api/items/${orderBtn.dataset.order}/order`, { method: "POST" }).catch(() => { orderBtn.disabled = false; });
    return;
  }
  const playBtn = e.target.closest("button[data-play]");
  if (playBtn) { openStage(items.find((i) => i.id === playBtn.dataset.play), true); return; }
  const replyBtn = e.target.closest("button[data-reply]");
  if (replyBtn) sendReply(replyBtn.dataset.reply);
};

// ---------------------------------------------------------------- the Studio sheet

function seen(item) {
  if ($("banner").dataset.item === item.id) $("banner").hidden = true;
}

function openSheet(item, format, report = true) {
  if (!item?.payload.outputs?.[format]) return; // e.g. a stale or forged screen report for a format it doesn't have
  seen(item);
  closeStage();
  sheet?.viewer?.stop();
  const formats = packFormats(item);
  sheet = { item, format, viewer: null };
  $("sheet-title").textContent = packTitle(item);
  $("sheet-tabs").innerHTML = formats.map((f) => `<button type="button" data-format="${f}" aria-selected="${f === format}">${icon(FORMAT_INFO[f].icon, 18)}${esc(fmtName(f))}</button>`).join("");
  const onEvent = report ? (fmt, event, value) => engage(item, fmt, event, value) : () => {};
  sheet.viewer = mountViewer($("viewer"), format, item.payload.outputs[format], {
    lang: person.language, onEvent, names: names(), picture: item.payload.outputs.picture?.image || "",
    gender: genderOf(circle.caregiver.relation), // read in a voice like the caregiver's
    onAsk: report && !mirror ? (question) => submit(() => sendRelay({ text: question, about: item.id, replyTo: "" })) : null,
  });
  drawExtras(item, report);
  const wasOpen = !$("sheet").hidden;
  $("sheet").hidden = false;
  if (!wasOpen) $("sheet-done").focus(); // keyboard and screen-reader users land inside the sheet
  if (report) tell();
}
/** Under every moment: the products it recommends (with their pictures, and "I'd like one") and the links the app
 *  checked for a genuine item. Nothing here was written by a model: names and pictures come from the research. */
function drawExtras(item, report) {
  const research = item.payload.research || {};
  const products = research.products || [];
  const links = research.links || [];
  const ask = words.wantOne || "I'd like one";
  $("sheet-extras").innerHTML = (products.length ? `<div class="x-products">${products.map((p, k) => `<div class="x-product">
      ${p.image ? `<img src="${esc(p.image)}" alt="" loading="lazy">` : `<span class="x-noimg">${icon("cart", 22)}</span>`}
      <div><b>${esc(p.name)}</b><small>${esc(p.good_for_en || "")}</small></div>
      ${report && !mirror && !isChild ? `<button type="button" class="x-want" data-want="${k}">${esc(ask)}</button>` : ""}</div>`).join("")}</div>` : "")
    + (links.length && !isChild ? `<div class="x-links">${links.map((l) => `<a class="x-link" href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">${icon("link", 16)}<span><b>${esc(l.title)}</b><small>${esc(l.host)}</small></span></a>`).join("")}</div>` : "");
  $("sheet-extras").onclick = (e) => {
    const want = e.target.closest("[data-want]");
    if (!want) return;
    const product = products[Number(want.dataset.want)];
    want.disabled = true;
    sendReply(person.language === "ja" ? `${product.name}がほしいです。買ってもらえる？` : `Could you get me the ${product.name}, please?`);
  };
}

function closeSheet(report = true) {
  sheet?.viewer?.stop();
  sheet = null;
  $("sheet").hidden = true;
  render();
  if (report) tell();
}
$("sheet-tabs").onclick = (e) => { const b = e.target.closest("[data-format]"); if (b && sheet) openSheet(sheet.item, b.dataset.format); };
$("sheet-done").onclick = () => closeSheet();

const sentEvents = new Set();
function engage(item, format, event, value) {
  if (mirror) return; // the caregiver clicking around the mirror is not her engagement
  const key = `${item.id}:${format}:${event}:${event === "progress" ? Math.round(value * 4) : value}`;
  if (sentEvents.has(key)) return; // one report per milestone is enough
  sentEvents.add(key);
  api(`/api/items/${item.id}/engagement`, { method: "POST", body: { format, event, value } }).catch(() => {});
}

// ---------------------------------------------------------------- the talking stage (messages)

async function setUpAvatar() {
  avatar = await loadAvatar(circle.caregiver.id);
  // Headless test browsers render WebGL in software, which stalls screenshots; they get the 2D avatar.
  if (!isChild && (circle.avatar_mode || "3d") === "3d" && !navigator.webdriver) {
    $("stage").hidden = false;
    $("stage").classList.add("idle");
    $("stage-img").hidden = true;
    $("stage-3d").hidden = false;
    head = await loadAvatar3D($("stage-3d"), `/assets/avatars/vrm/${circle.caregiver.id}.vrm`);
    threeD = Boolean(head);
    if (threeD) {
      await new Promise((r) => setTimeout(r, 400));
      avatar = { ...(avatar || {}), urls: { ...(avatar?.urls || {}), base: head.snapshot() } };
    } else { $("stage-img").hidden = false; $("stage-3d").hidden = true; $("stage").hidden = true; }
  }
  if (!threeD) head = new TalkingHead($("stage-img"), avatar);
  $("stage-badge").innerHTML = esc(callName());
  $("caption").textContent = words.idle;
  $("face").innerHTML = avatar ? `<img src="${avatar.urls.base}" alt="">` : esc(callName()[0]);
}

function openStage(item, autoplay = false) {
  if (!item || item.kind === "studio") return;
  seen(item);
  stage = { item, index: -1 };
  $("stage").hidden = false;
  $("stage").classList.remove("idle");
  $("stage-badge").innerHTML = item.speaker === "assistant" ? `<span class="mark">${ICON.assistant}</span>${esc(words.assistant.replace("{name}", callName()))}` : esc(callName());
  showStage();
  if (autoplay) playStage();
}

function closeStage() {
  head?.stop();
  stage = null;
  if (threeD) {
    $("stage").classList.add("idle");
    $("stage-badge").innerHTML = esc(callName());
    $("caption").textContent = words.idle;
  } else {
    $("stage").hidden = true;
  }
}

function stageText() {
  const m = stage.item.payload.message;
  return stage.index < 0 ? stage.item.payload.own_voice?.caption || m.spoken_text : m.steps[stage.index];
}

function showStage(progress = 0) {
  const m = stage.item.payload.message;
  const text = stageText();
  $("caption").innerHTML = `<span class="said">${esc(text.slice(0, progress))}</span>${esc(text.slice(progress))}` +
    (subs && stage.index < 0 && m.english_gloss && text === m.spoken_text ? `<div class="gloss">${esc(m.english_gloss)}</div>` : "");
  followCaption(progress);
  const n = m.steps.length;
  $("stage-step").textContent = stage.index >= 0 ? words.step.replace("{i}", stage.index + 1).replace("{n}", n) : "";
  $("stage-back").textContent = words.back;
  $("stage-back").disabled = stage.index < 0;
  $("stage-next").textContent = stage.index < n - 1 ? words.next : words.done;
  $("stage-play").innerHTML = head?.speaking ? ICON.stop : ICON.play;
  $("stage-play").classList.toggle("playing", Boolean(head?.speaking));
}

/** The caption is a few lines tall: keep the words being said in view (and start at the top). */
function followCaption(progress) {
  const box = $("caption");
  if (!progress) { box.scrollTop = 0; return; }
  const rects = box.querySelector(".said")?.getClientRects();
  if (!rects?.length) return;
  const bottom = rects[rects.length - 1].bottom - box.getBoundingClientRect().top + box.scrollTop;
  if (bottom > box.scrollTop + box.clientHeight) box.scrollTop = bottom - box.clientHeight + 4;
}

async function playStage() {
  if (!stage) return;
  if (head.speaking) { head.stop(); showStage(); return; }
  const item = stage.item;
  const own = stage.index < 0 ? item.payload.own_voice : null; // the caregiver recorded it: she hears them, not a device voice
  const text = stageText();
  const playing = own ? head.speakAudio(own.audio, { onProgress: (f) => { if (stage?.item === item) showStage(Math.round(f * text.length)); } })
    : head.speak(text, {
      lang: lang(), voiceIndex: item.speaker === "assistant" ? 1 : 0,
      gender: item.speaker === "assistant" ? "" : genderOf(circle.caregiver.relation), // her son's voice is a man's
      onProgress: (i) => { if (stage?.item === item) showStage(i); },
    });
  showStage();
  if (item.status === "sent" && !mirror) api(`/api/items/${item.id}/played`, { method: "POST" }).catch(() => {});
  await playing;
  if (stage?.item === item) showStage(stageText().length);
}

function moveStage(step) {
  if (!stage) return;
  const n = stage.item.payload.message.steps.length;
  const next = stage.index + step;
  if (next >= n) { closeStage(); return; }
  stage.index = Math.max(-1, next);
  head.stop();
  showStage();
  playStage();
}

$("stage-play").onclick = playStage;
$("stage-next").onclick = () => moveStage(1);
$("stage-back").onclick = () => moveStage(-1);
$("stage-close").onclick = closeStage;

// ---------------------------------------------------------------- replying

async function sendReply(text) {
  if (!text.trim()) return;
  closeStage();
  $("reply").value = "";
  if (isChild || answering) await submit(() => sendRelay({ text }));
  else await submit(() => api(`/api/circles/${circleId}/reply`, { method: "POST", body: { text } }));
}

async function submit(call) {
  $("reply-send").disabled = true;
  $("reply").placeholder = words.sending;
  try {
    for (const item of await call()) if (!items.some((x) => x.id === item.id)) items.push(item);
    render();
  } catch (err) { alert(err.message); }
  $("reply-send").disabled = false;
  setTalkTarget(answering);
}

let recorder = null;
async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const chunks = [];
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (e) => chunks.push(e.data);
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(chunks, { type: recorder.mimeType });
      recorder = null;
      if (blob.size < 2000) return;
      if (isChild || answering) { submit(() => sendRelay({ audio: blob })); return; }
      const form = new FormData();
      form.append("audio", blob, "reply.webm");
      submit(async () => {
        const res = await fetch(`/api/circles/${circleId}/reply-audio`, { method: "POST", body: form });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Could not send the recording.");
        return data;
      });
    };
    recorder.start();
    $("mic").classList.add("rec");
    $("reply").placeholder = words.listening;
  } catch { alert(words.micDenied); }
}
function stopRecording() {
  $("mic").classList.remove("rec");
  if (recorder?.state === "recording") recorder.stop();
}
$("mic").addEventListener("pointerdown", (e) => { e.preventDefault(); closeStage(); startRecording(); });
for (const ev of ["pointerup", "pointerleave", "pointercancel"]) $("mic").addEventListener(ev, stopRecording);
$("talk").onsubmit = (e) => { e.preventDefault(); sendReply($("reply").value); };
$("reply").onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("talk").requestSubmit(); } };

start();
