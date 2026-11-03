// The stream's cards, as HTML. A Studio share shows its whole pipeline the way RoleSpace shows a decision: agent
// checks that tick off, the plan with its sources, the formats to pick, the outputs, the code checks, your decision
// and what she did with it. Everything from a model or a person goes through esc() (rule S9).
import { esc } from "../common.js";
import { FORMAT_INFO, icon } from "../studio-view.js";
import { clock, FORMAT_TEXT, formatsFor, formatText, her, herLang, isChild, parent, recipientOf, recipients, state } from "./shared.js";

const SOFT_RULES = new Set(["phone", "pressure", "date_not_in_source", "child_guardian", "verifier", "scam_named"]);
const STATUS = {
  draft: ["warn", "Waiting for your approval"], held: ["danger", "Held by the safety check"], sent: ["info", "Sent"],
  played: ["ok", "She opened it"], done: ["", "Done"],
};
const STAGE = { researching: ["info", "Researching"], planned: ["warn", "Plan ready"], making: ["info", "Making"], failed: ["danger", "Couldn't finish"] };
const VERDICT = { looks_genuine: ["ok", "Checked against the web"], personal: ["ok", "Family news"], unverified: ["warn", "Not confirmed"],
  likely_scam_or_misleading: ["danger", "Likely a scam"] };
// The pipeline in the order it runs. Agents in the same stage run in parallel, so they may finish in any order.
// A fourth value marks an agent that only runs for some shares (a video, a list of named things): shown once it has run.
const STAGES = [
  ["Read", [["download", "Opened the link and saved the video", "The video and its caption", true],
    ["watcher", "Watched the whole video", "With its sound, step by step", true], ["reader", "Read what you shared", "Facts, dates and claims"],
    ["web_search", "Searched the web for its claims", "Meta web search"], ["focus", "Marked what to watch in each still", "SAM 3.1", true]]],
  ["Understand", [["fact_checker", "Decided if it can be trusted", "Verdict and sources"],
    ["item_researcher", "Looked up each thing it names", "Web search, one by one", true],
    ["audience", "Thought about how {name} takes things in", "Reading, attention, best moments"],
    ["context", "Connected it to {name}'s week", "Why it matters now"]]],
  ["Plan", [["planner", "Planned the best way to explain it", "Key message, outline, moments"]]],
];
const ENGINE_NAME = { "muse-wonder-1.0": "Muse Wonder", "muse-image-1.0": "Muse Image", "sam-3.1": "SAM 3.1" };
const engineChip = (e) => { const m = (e?.engine || "").split("/").pop(); return ENGINE_NAME[m] ? `<span class="eng">${ENGINE_NAME[m]}</span>` : ""; };
const LANE = { tonight: "Tonight", staples: "Staples", medicine: "Medicine" };
const APP_LABEL = { gmail: "Gmail", slack: "Slack", googlephotos: "Google Photos", zoom: "Zoom", notion: "Notion" };
const APP_ICON = { gmail: "mail", slack: "chat", googlephotos: "eye", zoom: "video", notion: "document" };

export function card(item) {
  if (item.kind === "studio") return studioCard(item);
  if (item.kind === "relay") return relayCard(item);
  if (item.kind === "approval") return approvalCard(item);
  if (item.kind === "answer") return answerCard(item);
  if (item.kind === "order") return orderCard(item);
  if (item.kind === "reply") return replyCard(item);
  if (item.kind === "summary") return summaryCard(item);
  if (item.kind === "alert") return alertCard(item);
  return messageCard(item);
}

const badge = ([tone, text]) => `<span class="badge ${tone}"><i></i>${esc(text)}</span>`;
const head = (iconName, title, meta, right) => `<header class="card-head"><span class="src">${icon(iconName, 18)}</span>
  <div class="t"><b>${esc(title)}</b><small>${esc(meta)}</small></div>${right}</header>`;
const plural = (n, word, many = `${word}s`) => `${n} ${n === 1 ? word : many}`;
const who = (item) => recipientOf(item).call_name;
const langOf = (item) => recipientOf(item).language;

// ---------------------------------------------------------------- a Studio share

function sourceKind(p, files) {
  if (p.source?.kind) return p.source.kind;
  if (p.ref) return p.ref.app;
  if (files.some((f) => f.type.startsWith("video/"))) return "video";
  if (files.some((f) => f.type.startsWith("audio/"))) return "voice";
  if (files.length) return "image";
  return p.link ? "link" : "text";
}

function studioCard(item) {
  const p = item.payload;
  const files = p.files || [];
  const kind = sourceKind(p, files);
  const kindIcon = { video: "video", image: "book", link: "link", voice: "volume", text: "chat", notion: "document", gmail: "mail",
    slack: "chat", googlephotos: "eye", zoom: "video" }[kind] || "chat";
  const status = p.stage === "ready" ? STATUS[item.status] : STAGE[p.stage] || ["", p.stage];
  const title = p.plan?.key_message_en || p.request || (p.link ? "A link" : "Something you shared");
  const person = recipientOf(item);
  const meta = `for ${person.call_name}${isChild(person) ? ` (${person.age})` : ""} · ${kind}${files.length ? ` · ${plural(files.length, "file")}` : ""} · ${clock(item.at)}`;
  let html = `<article class="card" data-card="${item.id}">${head(kindIcon, title, meta, badge(status))}${sharedMedia(p, files)}`;
  if (p.request) html += `<div class="said${p.request.length < 260 ? " short" : ""}">${esc(p.request)}</div>`;
  html += `<div class="pipeline"><section>${researchChecks(item)}</section><section>${planBlock(item)}</section></div>`;
  if (p.error) html += `<div class="error">${esc(p.error)}</div>`;
  if (p.plan) html += formatsBlock(item);
  if (p.outputs && p.stage === "ready") html += outputsBlock(item) + reviewBlock(item) + gateBlock(item) + decideBlock(item) + engagementBlock(item);
  if (p.outputs && !Object.keys(p.outputs).some((f) => f in FORMAT_TEXT)) html += `<div class="note-box">Made with the earlier formats. Share it again for the new moments.</div>`;
  return `${html}${footer(item)}</article>`;
}

function sharedMedia(p, files) {
  if (!files.length && !p.link && !p.ref) return "";
  const shown = files.map((f) => (f.type.startsWith("image/") ? `<img src="${esc(f.url)}" alt="">`
    : f.type.startsWith("video/") ? `<video src="${esc(f.url)}" muted playsinline></video>`
    : `<span class="linkcard">${icon("volume", 14)}voice note</span>`)).join("");
  const ref = p.ref ? `${p.ref.thumb ? `<img src="${esc(p.ref.thumb)}" alt="">` : ""}<span class="linkcard">${icon(APP_ICON[p.ref.app] || "document", 14)}${esc(APP_LABEL[p.ref.app] || p.ref.app)} · ${esc(p.ref.title || "an item")}</span>` : "";
  return `<div class="media">${shown}${p.link ? `<span class="linkcard">${icon("link", 14)}${esc(p.link)}</span>` : ""}${ref}</div>`;
}

/** The latest event per agent (events arrive live and again in the saved item, so later ones win). */
function agentStates(item) {
  const last = new Map();
  for (const e of item.payload.agents || []) last.set(e.agent, e);
  return last;
}

function checkRow(st, title, detail, chip = "") {
  const mark = st === "done" ? icon("tick", 14) : st === "failed" ? icon("cross", 14) : "";
  return `<div class="check ${st}"><span class="st">${mark}</span><div><b>${esc(title)}${chip}</b><small>${esc(detail)}</small></div></div>`;
}

const settled = (e) => ["done", "skipped", "failed"].includes(e?.state);

/** One stage: its name, how many of its agents are finished, and a row per agent. */
function stageBlock(name, rows, parallel = true) {
  const all = rows.length && rows.every(([, st]) => ["done", "skipped"].includes(st));
  const working = rows.some(([, st]) => st === "working");
  const tone = all ? "done" : working ? "working" : rows.some(([, st]) => st === "failed") ? "failed" : "";
  const finished = rows.filter(([, st]) => ["done", "skipped"].includes(st)).length;
  return `<div class="stage ${tone}"><div class="stage-h"><span class="sd"></span><b>${esc(name)}</b>${rows.length > 1 ? `<small>${finished} of ${rows.length}${parallel ? " · in parallel" : ""}</small>` : ""}</div>
    <div class="checks">${rows.map(([html]) => html).join("")}</div></div>`;
}

function researchChecks(item) {
  const states = agentStates(item);
  const name = who(item);
  const p = item.payload;
  const row = (agent, template, sub) => {
    const e = states.get(agent);
    const st = e?.state || (p.stage === "failed" ? "skipped" : "pending");
    const detail = e?.state === "done" ? `${sub} · ${e.latency_s.toFixed(1)}s` : ["failed", "skipped"].includes(e?.state) ? (e.detail || e.state) : sub;
    return [checkRow(st, template.replace("{name}", name), detail, engineChip(e)), st];
  };
  const shown = STAGES.map(([stage, rows]) => [stage, rows.filter(([agent, , , optional]) => !optional || states.has(agent))]);
  const researchSteps = shown.flatMap(([, rows]) => rows);
  const blocks = shown.map(([stage, rows]) => stageBlock(stage, rows.map(([a, t, s]) => row(a, t, s))));
  // Make: one maker per moment (and the picture drawn), once she has picked them
  const picked = p.formats && ["making", "ready"].includes(p.stage) ? p.formats : [];
  const makeRows = picked.map((f) => row(`maker_${f}`, formatText(f, recipientOf(item))[0], `Its own maker · ${formatText(f, recipientOf(item))[1]}`));
  if (states.has("illustrator")) makeRows.push(row("illustrator", "Drew the picture", "Muse Image"));
  if (makeRows.length) blocks.push(stageBlock("Make", makeRows));
  // Verify: the child guardian, the verifier on Muse Wonder, then code
  const verify = [];
  if (isChild(recipientOf(item)) && picked.length) verify.push(row("child_guardian", `Checked it is right for ${name}`, "Child-safety review, every line"));
  if (picked.length) verify.push(row("verifier", "Verified the whole pack", "Against the research and the source"));
  if (picked.length) {
    const st = item.gate ? "done" : "pending";
    verify.push([checkRow(st, "Checked dates and ran the send gate", item.gate ? (item.gate.passed ? "Code · passed" : "Code · held for you") : "Code"), st]);
  }
  if (verify.length) blocks.push(stageBlock("Verify", verify, false));
  const total = researchSteps.length + makeRows.length + verify.length;
  const done = [...researchSteps.map(([a]) => states.get(a)), ...picked.map((f) => states.get(`maker_${f}`))].filter((e) => settled(e) && e.state !== "failed").length
    + verify.filter(([, st]) => st === "done").length + (states.get("illustrator")?.state === "done" ? 1 : 0);
  return `<div class="label">Agents <span class="dm">${done}/${total}</span></div><div class="stages">${blocks.join("")}</div>`;
}

function sourceHosts(checked) {
  const host = (url) => { try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return ""; } };
  return [...new Set(checked.filter((c) => c.source_url).map((c) => host(c.source_url)).filter(Boolean))].slice(0, 3);
}

function planBlock(item) {
  const { plan, research, stage } = item.payload;
  if (!plan) {
    if (stage === "failed") return `<div class="label">The plan</div><p class="lead plan-wait">No plan: the agents couldn't finish.</p>`;
    return `<div class="label">The plan</div><p class="lead plan-wait">Working: the agents are reading it and checking the claims. The plan for ${esc(who(item))} appears here in about a minute.</p>
      <button class="btn ghost sm stop" data-act="discard" data-id="${item.id}">Stop and discard</button>`;
  }
  const fc = research.fact_check;
  const [tone, verdict] = VERDICT[fc.verdict] || ["", fc.verdict];
  const hosts = sourceHosts(fc.checked);
  const verifyIcon = tone === "ok" ? "shield" : tone === "danger" ? "shield-alert" : "info";
  const translated = plan.conversation_starter_en !== plan.conversation_starter;
  return `<div class="label">The plan</div>
    <div class="key">${esc(plan.key_message_en)}</div>
    <ol class="plan-outline">${plan.outline_en.map((o) => `<li>${esc(o.replace(/^\s*\d+[.)]\s*/, ""))}</li>`).join("")}</ol>
    <div class="verify ${tone}">${icon(verifyIcon, 18)}<div><b>${esc(verdict)}.</b> ${esc(fc.note_en)}
      ${hosts.length ? `<div class="chips">${hosts.map((h) => `<span class="chip">${icon("tick", 12)}${esc(h)}</span>`).join("")}</div>` : ""}</div></div>
    <div class="starter" lang="${langOf(item)}">${esc(plan.conversation_starter)}${translated ? `<small lang="en">${esc(plan.conversation_starter_en)}</small>` : ""}</div>`;
}

function formatsBlock(item) {
  const { plan, stage } = item.payload;
  const editable = stage === "planned";
  const picks = state.picks[item.id] || item.payload.formats || [];
  const person = recipientOf(item);
  const rows = formatsFor(person).map((f) => {
    const choice = plan.formats.find((x) => x.format === f) || {};
    const [name, sub] = formatText(f, person);
    const reason = (choice.reason_en || sub).replace(/^(not )?recommended[:.\s-]*/i, "");
    return `<button type="button" class="pick" data-pick="${f}" data-id="${item.id}" aria-pressed="${picks.includes(f)}" ${editable ? "" : "disabled"}>
      <span class="fi ${f}">${icon(FORMAT_INFO[f].icon, 17)}</span><span><b>${esc(name)}</b><small>${esc(reason)}</small></span>
      <span class="hint${choice.recommended ? " best" : ""}">${choice.recommended ? "best fit" : ""}</span></button>`;
  }).join("");
  let action = "";
  if (editable) {
    action = `<div class="decide inline"><button class="btn primary" data-make="${item.id}" ${picks.length ? "" : "disabled"}>${icon("activity", 16)}Make ${plural(picks.length, "moment")}</button>
      <button class="btn outline" data-act="discard" data-id="${item.id}">Discard</button><span class="note">The best fits are picked for you. Change them if you like.</span></div>`;
  } else if (stage === "making") {
    action = `<div class="decide inline"><span class="note making">Working: one agent per moment, in parallel.</span>
      <button class="btn ghost sm" data-act="discard" data-id="${item.id}">Stop and discard</button></div>`;
  }
  return `<section class="formats"><div class="label">Moments for ${esc(who(item))}</div><div class="picks">${rows}</div>${action}</section>`;
}

function describe(f, o) {
  if (f === "note") return `${plural(o.lines.length, "line")} · read aloud`;
  if (f === "steps") return plural(o.pages.length, "slide");
  if (f === "video") return `${plural(o.scenes.length, "scene")} · narrated`;
  if (f === "picture") return o.image ? "drawn by Muse Image" : "caption only";
  if (f === "story") return plural(o.pages.length, "page");
  if (f === "card") return `${plural(o.lines.length, "line")}${o.remember ? " · one thing to remember" : ""}`;
  if (f === "askme" || f === "quiz") return plural(o.questions.length, "question");
  if (f === "map") return plural(o.branches.length, "branch", "branches");
  if (f === "relay") return plural(o.questions.length, "question");
  return "";
}

const known = (outputs) => Object.entries(outputs || {}).filter(([f]) => f in FORMAT_TEXT);

function outputsBlock(item) {
  const person = recipientOf(item);
  const outs = known(item.payload.outputs).map(([f, o]) => `
    <button type="button" class="out ${f}" data-view="${item.id}" data-format="${f}">
      <span class="out-kind">${icon(FORMAT_INFO[f].icon, 14)}${esc(formatText(f, person)[0])}</span>${outThumb(f, o, item)}
      <b lang="${langOf(item)}">${esc(o.title || o.root || "")}</b><p>${esc(o.summary_en || "")}</p><span class="of">${esc(describe(f, o))} · preview</span></button>`).join("");
  const research = item.payload.research || {};
  const extras = [...(research.products || []).map((p) => `<span class="x-chip">${p.image ? `<img src="${esc(p.image)}" alt="">` : icon("cart", 14)}${esc(p.name)}</span>`),
    ...(research.links || []).map((l) => `<span class="x-chip">${icon("link", 14)}${esc(l.host)}</span>`)].join("");
  return outs ? `<div class="label pad">What ${esc(who(item))} gets</div><div class="outs">${outs}</div>${extras ? `<div class="x-chips"><small>Added by the app, from the research:</small>${extras}</div>` : ""}<div class="preview-slot" id="slot-${item.id}" hidden></div>` : "";
}

/** A glance at the moment itself: the picture, the mind map's parts, the video's first scene. */
function outThumb(f, o, item) {
  if (f === "picture" && o.image) return `<img class="out-img" src="${esc(o.image)}" alt="">`;
  if (f === "map") return `<span class="out-map" lang="${langOf(item)}"><i>${esc(o.root)}</i>${o.branches.slice(0, 5).map((b) => `<em>${esc(b.label)}</em>`).join("")}</span>`;
  if (f === "video" && o.scenes[0]) return `<span class="out-vid" lang="${langOf(item)}">${icon("play", 16)}${esc(o.scenes[0].big_text)}</span>`;
  return "";
}

/** What the verifier (Muse Wonder) made of the whole pack. */
function reviewBlock(item) {
  const r = item.payload.review;
  if (!r) return "";
  const approved = r.faithful && r.safe && !r.issues.some((i) => i.severity === "fix");
  const checks = [["Faithful to the source", r.faithful], ["Right for " + who(item), r.right_for_reader], ["Safe", r.safe]];
  const engine = (agentStates(item).get("verifier")?.engine || "").includes("wonder") ? "Muse Wonder" : "Muse Spark";
  return `<div class="review ${approved ? "ok" : "watch"}"><div class="review-h">${icon("shield", 18)}<b>Verified by ${engine}</b><span>${esc(r.verdict_en)}</span></div>
    <div class="review-checks">${checks.map(([t, ok]) => `<span class="${ok ? "ok" : "no"}">${icon(ok ? "tick" : "cross", 12)}${esc(t)}</span>`).join("")}</div>
    ${r.issues.length ? `<ul>${r.issues.map((i) => `<li class="${i.severity}"><b>${esc(i.severity === "fix" ? "Look at" : "Note")}</b> ${esc(i.problem_en)}</li>`).join("")}</ul>` : ""}</div>`;
}

function gateBlock(item) {
  if (!item.gate) return "";
  const guardian = item.payload.guardian?.safe_for_child ? " A child-safety review read every line." : "";
  const source = item.payload.errand ? "the verified mail" : item.kind === "relay" ? "what was said" : "what you shared";
  if (item.gate.passed) return `<div class="gate ok">${icon("shield", 18)}<div><b>Checked by code.</b> Every date and time is in ${source}, and the final send gate found nothing to stop.${guardian}</div></div>`;
  const soft = item.gate.rules.every((r) => SOFT_RULES.has(r));
  return `<div class="gate ${soft ? "soft" : "held"}">${icon("shield-alert", 18)}<div><b>${soft ? "Waiting for you to read it." : "Held."}</b> ${esc(item.gate.reasons.join(" "))}</div></div>`;
}

function decideBlock(item) {
  const discard = `<button class="btn outline" data-act="discard" data-id="${item.id}">Discard</button>`;
  if (item.status === "draft") {
    return `<div class="decide"><button class="btn primary" data-act="approve" data-id="${item.id}">${icon("send", 16)}Approve and send to ${esc(who(item))}</button>
      ${discard}<span class="note">A gentle notification; it opens when ${esc(who(item))} likes.</span></div>`;
  }
  if (item.status === "held") {
    const soft = item.gate.rules.every((r) => SOFT_RULES.has(r)); // only soft holds can be overridden; hard ones never
    return `<div class="decide">${soft ? `<button class="btn primary" data-act="anyway" data-id="${item.id}">${icon("send", 16)}I checked it, send anyway</button>` : ""}${discard}</div>`;
  }
  return "";
}

function engagementBlock(item) {
  if (!["sent", "played"].includes(item.status)) return "";
  const events = item.payload.engagement || [];
  const person = recipientOf(item);
  const rows = known(item.payload.outputs).map(([f, out]) => {
    const list = events.filter((e) => e.format === f);
    const finished = list.some((e) => e.event === "finished");
    const progress = finished ? 1 : Math.max(0, ...list.map((e) => (e.event === "progress" ? e.value : 0)));
    let value = finished ? "finished" : progress ? `${Math.round(progress * 100)}%` : list.length ? "opened" : "not yet";
    let detail = "";
    if (f === "askme" || f === "quiz") { // what she got, and what to talk about together
      const right = new Set(list.filter((e) => e.event === "answer_right").map((e) => e.value));
      const missed = [...new Set(list.filter((e) => e.event === "answer_missed").map((e) => e.value))].filter((k) => !right.has(k));
      if (right.size || missed.length) value = `${right.size} of ${out.questions.length} first time`;
      if (missed.length) detail = `<div class="talk-about">Talk about: ${missed.map((k) => `<span lang="${langOf(item)}">${esc(out.questions[k]?.question || "")}</span>`).join(" · ")}</div>`;
    }
    if (f === "relay") {
      const asked = list.filter((e) => e.event === "asked").length;
      if (asked) value = `asked ${plural(asked, "question")}`;
    }
    return `<div class="erow"><span class="fi ${f}">${icon(FORMAT_INFO[f].icon, 15)}</span><span>${esc(formatText(f, person)[0])}</span>
      <span class="emeter"><span class="meter"><b style="width:${Math.round(progress * 100)}%"></b></span><span class="v">${esc(value)}</span></span></div>${detail}`;
  }).join("");
  return rows ? `<div class="engaged"><div class="label">What ${esc(who(item))} did</div><div class="rows-plain">${rows}</div></div>` : "";
}

// ---------------------------------------------------------------- the family relay: grandchild and grandparent

const memberById = (id) => recipients().find((m) => m.id === id);

function relayCard(item) {
  const p = item.payload, m = p.message;
  const from = memberById(p.from), to = memberById(p.recipient);
  const fromName = from?.call_name || "Someone", toName = to?.call_name || "";
  const answering = Boolean(p.reply_to);
  const title = `${fromName} ${answering ? "answered" : isChild(from || {}) ? "asked" : "said to"} ${toName}`;
  const status = p.stage === "writing" ? ["info", "Passing it on"] : item.status === "sent" ? ["info", "Delivered"]
    : item.status === "played" ? ["ok", "Heard"] : STATUS[item.status] || ["", item.status];
  const meta = `family relay · ${p.audio ? `voice ${Math.round(p.seconds || 0)}s` : "typed"} · ${clock(item.at)}`;
  const voice = p.audio ? `<audio controls preload="none" src="${esc(p.audio)}"></audio>` : "";
  const gloss = m?.english_gloss && (from?.language || "en") !== "en" ? `<div class="gloss" lang="en">${esc(m.english_gloss)}</div>` : "";
  const retold = m && isChild(to || {}) ? `<div class="label pad">What ${esc(toName)} hears</div><div class="hear" lang="${to.language}"><div class="big">${esc(m.spoken_text)}</div>
    ${p.follow_up ? `<div class="starter">Next question for ${esc(toName)}: ${esc(p.follow_up)}</div>` : ""}</div>` : "";
  const picture = p.picture ? `<div class="media"><img src="${esc(p.picture)}" alt="${esc(p.picture_en || "")}"></div>` : "";
  return `<article class="card relay" data-card="${item.id}">${head("family", title, meta, badge(status))}
    <div class="quote"><div class="q" lang="${from?.language || "en"}">${esc(p.text)}</div>${gloss}${voice}</div>${retold}${picture}
    ${p.stage === "ready" ? gateBlock(item) + decideBlock(item) : ""}</article>`;
}

function footer(item) {
  const done = [...agentStates(item).values()].filter((e) => e.state === "done");
  const secs = done.reduce((s, e) => s + (e.latency_s || 0), 0);
  const engines = [...new Set(item.trace.map((t) => t.engine))].filter((e) => e !== "code" && e !== "you");
  const model = (engines.find((e) => !e.includes("web_search")) || state.engine || "").replace(/^meta\//, "");
  const checks = item.gate ? (item.gate.passed ? "passed" : "held") : "pending";
  return `<footer class="card-foot"><span>model <b>${esc(model)}</b></span><span class="sep">·</span>
    <span><b>${done.length}</b> agent runs</span><span class="sep">·</span><span><b>${secs.toFixed(0)}s</b> model time</span>
    ${engines.some((e) => e.includes("web_search")) ? `<span class="sep">·</span><span>web search</span>` : ""}<span class="sep">·</span><span>code checks <b>${checks}</b></span></footer>`;
}

// ---------------------------------------------------------------- errands: she asks, the assistant finds out or orders

const money = (amount, currency) => (currency === "JPY" ? `¥${amount.toLocaleString()}` : `$${(amount / 100).toFixed(2)}`);
const productPic = (offer, size = "") => (offer?.image ? `<img class="prod-pic ${size}" src="${esc(offer.image)}" alt="">` : icon("cart", 16));
const TRUCK = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h11v9H3zM14 9h4l3 3v3h-7z"/><circle cx="7" cy="17.5" r="1.8"/><circle cx="17.5" cy="17.5" r="1.8"/></svg>';
/** The delivery answer as her phone draws it: when, a truck on its way, and which checked mail it came from. */
function deliveryVisual(e) {
  if (e.kind !== "delivery" || !e.found || !e.eta) return "";
  const who = (e.used?.[0]?.sender || "").split("<")[0].trim();
  return `<div class="deliv"><span class="dl-ic">${TRUCK}</span><div class="dl-main"><small>Arriving</small><b lang="${herLang()}">${esc(e.eta)}</b>
    <span class="dl-track"><i></i><em>${TRUCK}</em></span></div>${who ? `<span class="dl-src">${icon("mail", 14)}From the ${esc(who)} email · checked</span>` : ""}</div>`;
}
const domainOf = (sender) => (sender.match(/@([^>\s]+)/) || [])[1] || sender;

function approvalCard(item) {
  const p = item.payload, quote = p.request?.quote || "";
  const offer = p.offer ? `<div class="offer">${productPic(p.offer, "lg")}<span><b>${esc(p.offer.name)}</b><small>${esc(money(p.offer.price, p.offer.currency))} · ${esc(p.offer.store)}</small></span><span class="sim">simulated</span></div>` : "";
  const over = p.over_limit ? `<p class="over">${icon("warning", 14)}Above your spending limit, so this one asks you every time.</p>` : "";
  let decide = "";
  if (item.status === "draft") {
    decide = p.over_limit
      ? `<button class="btn primary" data-allow="once" data-id="${item.id}">${icon("check", 16)}Approve this order</button>
         <button class="btn outline" data-allow="deny" data-id="${item.id}">Decline</button>`
      : `<button class="btn primary" data-allow="always" data-id="${item.id}">${icon("check", 16)}Always allow</button>
         <button class="btn outline" data-allow="once" data-id="${item.id}">Allow once</button>
         <button class="btn ghost" data-allow="deny" data-id="${item.id}">Not now</button>
         <span class="note">With Always allow, ${esc(her())} gets answers even when you're busy. You can stop it any time.</span>`;
  } else {
    const said = { always: "You allowed it always.", once: "You allowed it once.", deny: "You said not now." }[p.decision] || "";
    decide = `<span class="note">${esc(said)}</span>`;
  }
  const tone = item.status === "draft" ? ["warn", "Needs your OK"] : p.decision === "deny" ? ["", "Not now"] : ["ok", "Allowed"];
  return `<article class="card ask" data-card="${item.id}">${head("key", `${her()} asked: “${quote}”`, `the assistant asks first · ${clock(item.at)}`, badge(tone))}
    <div class="card-body"><div class="label">To answer, the assistant needs to</div><div class="permission"><b>${esc(p.title)}</b><p>${esc(p.detail)}</p>${offer}${over}</div></div>
    <div class="decide">${decide}</div></article>`;
}

function answerCard(item) {
  const p = item.payload, e = p.errand || {}, m = p.message;
  const titles = { delivery: `Answered ${her()} from your mail`, price: `Checked a price for ${her()}`, ordered: `Told ${her()} the order is placed`,
                   waiting: `Told ${her()} you'll check first`, declined: `Told ${her()} you'll get back to her`, order: `Looked for it for ${her()}` };
  const meta = e.kind === "delivery" ? `demo mailbox · ${e.permission === "always" ? "allowed always" : "allowed once"}`
    : e.offer ? `${e.offer.store} · simulated` : "assistant";
  const gloss = m.english_gloss && parent().language !== "en" ? `<div class="gloss" lang="en">${esc(m.english_gloss)}</div>` : "";
  const asked = e.question ? `<div class="asked">She asked: <span lang="${herLang()}">“${esc(e.question)}”</span></div>` : "";
  const used = (e.used || []).map((u) => `<span class="chip">${icon("tick", 12)}verified ${esc(domainOf(u.sender))}</span>`).join("");
  const blocked = (e.blocked || []).map((b) => `<div class="blocked">${icon("shield-alert", 15)}<span><b>Blocked</b> ${esc(b.sender)}: ${esc(b.reason)}</span></div>`).join("");
  const sources = used || blocked ? `<div class="sources">${used ? `<div class="chips">${used}</div>` : ""}${blocked}</div>` : "";
  const status = STATUS[item.status] || ["", item.status];
  return `<article class="card" data-card="${item.id}">${head(e.kind === "delivery" ? "mail" : e.offer ? "cart" : "chat", titles[e.kind] || "The assistant answered her", `${meta} · ${clock(item.at)}`, badge(status))}
    <div class="card-body tight">${asked}<div class="label">What ${esc(her())} hears</div></div>
    <div class="hear" lang="${herLang()}">${e.offer?.image ? `<div class="prod-line">${productPic(e.offer, "lg")}<span>${esc(e.offer.name)}<small>${esc(money(e.offer.price, e.offer.currency))} · ${esc(e.offer.store)}</small></span></div>` : ""}<div class="big">${esc(m.spoken_text)}</div>${gloss}${deliveryVisual(e)}</div>${sources}${gateBlock(item)}${decideBlock(item)}</article>`;
}

function orderCard(item) {
  const { offer, order, spent_month: spent, per_month: limit } = item.payload;
  const pct = Math.min(100, Math.round((spent / limit) * 100));
  return `<article class="card" data-card="${item.id}">${head("cart", `Ordered for ${her()}: ${offer.name_en}`, `${offer.store} · simulated checkout · ${clock(item.at)}`, badge(["ok", "Ordered"]))}
    <div class="card-body"><div class="prod-line">${productPic(offer, "lg")}<span>${esc(offer.name)}<small>${esc(offer.name_en)}</small></span></div><div class="order-row"><span>${esc(money(order.total, order.currency))}</span><span>arrives ${esc(new Date(`${order.arrives}T12:00`).toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" }))}</span><span class="mono">${esc(order.order_id)}</span></div>
    <div class="month">This month <span class="meter"><b style="width:${pct}%"></b></span>${esc(money(spent, order.currency))} of ${esc(money(limit, order.currency))}</div></div></article>`;
}

// ---------------------------------------------------------------- quick message, her reply, the summary for you, alerts

function messageCard(item) {
  const m = item.payload.message;
  if (!m) return "";
  const title = item.payload.ack ? "Your assistant answered her" : item.payload.source_text;
  const meta = `quick message · ${item.voice === "mine" ? "your voice" : "assistant voice"} · ${clock(item.at)}`;
  const gloss = m.english_gloss && parent().language !== "en" ? `<div class="gloss" lang="en">${esc(m.english_gloss)}</div>` : "";
  const steps = m.steps.length ? `<ol>${m.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>` : "";
  const replies = m.quick_replies.length ? `<div class="qr">${m.quick_replies.map((q) => `<span class="badge">${esc(q)}</span>`).join("")}</div>` : "";
  return `<article class="card" data-card="${item.id}">${head("chat", title, meta, badge(STATUS[item.status] || ["", item.status]))}
    <div class="card-body tight"><div class="label">What ${esc(her())} hears</div></div>
    <div class="hear" lang="${herLang()}"><div class="big">${esc(m.spoken_text)}</div>${gloss}${steps}${replies}</div>${ownVoiceBlock(item)}${gateBlock(item)}${decideBlock(item)}</article>`;
}

const minutes = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;

/** Your own recording of a quick message: record it or pick a file; she then hears you, not the device voice.
 *  Code makes it clearer (no voice model); both versions can be played here. */
function ownVoiceBlock(item) {
  if (item.payload.ack) return "";
  const v = item.payload.own_voice;
  const open = ["draft", "held", "sent"].includes(item.status);
  if (v) {
    return `<div class="own-voice has">${icon("volume", 18)}<div class="ov-text"><b>${esc(her())} hears your own voice</b>
      <span>${minutes(v.seconds)} · made clearer by code, not a voice model: ${Math.round(v.before_lufs)} to ${Math.round(v.after_lufs)} LUFS, less noise, shorter pauses${v.match < 0.85 ? ` · you said it your way, so her captions show your words` : ""}</span>
      <div class="ov-players"><label>As recorded<audio controls preload="none" src="${esc(v.original)}"></audio></label><label>Made clearer<audio controls preload="none" src="${esc(v.audio)}"></audio></label></div></div>
      ${open ? `<button type="button" class="btn ghost sm" data-own-voice="remove" data-id="${item.id}">Remove</button>` : ""}</div>`;
  }
  if (!open) return "";
  const recording = state.ownVoice?.id === item.id;
  return `<div class="own-voice">${icon("mic", 18)}<div class="ov-text"><b>Say it in your own voice</b>
    <span>Read the words above, or say them your way. ${esc(her())} hears you instead of the device voice; code only makes it clearer.</span></div>
    <button type="button" class="btn ${recording ? "primary" : "outline"} sm" data-own-voice="record" data-id="${item.id}">${icon(recording ? "pause" : "mic", 16)}${recording ? "Stop and attach" : "Record"}</button>
    ${recording ? "" : `<label class="btn ghost sm">Choose a file<input type="file" accept="audio/*,video/*" data-own-voice-file="${item.id}" hidden></label>`}</div>`;
}

function replyCard(item) {
  return `<article class="card" data-card="${item.id}">${head("chat", `${her()} replied`, `from her phone · ${clock(item.at)}`, `<span class="avatar">${esc(her()[0])}</span>`)}
    <div class="quote"><div class="q" lang="${herLang()}">${esc(item.payload.text)}</div></div></article>`;
}

function summaryCard(item) {
  const p = item.payload;
  const tone = p.alert === "urgent" ? ["danger", "Urgent"] : p.alert === "watch" ? ["warn", "Worth a look"] : ["", "Summary"];
  const signals = [...p.signals.map((s) => `<span class="badge warn" title="${esc(s.quote)}"><i></i>${esc(s.observation)}</span>`),
    ...p.needs.map((n) => `<span class="badge">${esc(LANE[n.lane])} · ${esc(n.item)}${n.quantity ? ` · ${esc(n.quantity)}` : ""}</span>`)].join("");
  return `<article class="card" data-card="${item.id}">${head("activity", "What she said, for you", `reply reader · ${clock(item.at)}`, badge(tone))}
    <div class="card-body">${esc(p.summary)}${p.question ? `<div class="starter">She asked: ${esc(p.question)}</div>` : ""}</div>${signals ? `<div class="signals">${signals}</div>` : ""}</article>`;
}

function alertCard(item) {
  if (item.to !== "caregiver") {
    return `<article class="card" data-card="${item.id}">${head("phone", "Shown on her screen", clock(item.at), badge(["danger", "Urgent"]))}
      <div class="card-body">${esc(item.payload.emergency)} in large type, with a call button.</div></article>`;
  }
  return `<article class="card alert" data-card="${item.id}">${head("warning", "Urgent", clock(item.at), badge(["danger", "Urgent"]))}<div class="card-body">${esc(item.payload.text)}</div></article>`;
}
