// The Reel Lab page: the reels, their rounds and scores, and the moments made, drawn with the phone's own viewers.
// Read only (GET /api/lab, /api/lab/{id}); nothing here calls a model.
import { api, esc, ICON } from "./common.js";
import { drawTuning } from "./lab-tune.js";
import { formatName, loadIcons, mountViewer, stopSpeech } from "./studio-view.js";

const $ = (id) => document.getElementById(id);
const CRITERIA = [["faithful", "Faithful"], ["clear", "Clear"], ["engaging", "Engaging"], ["useful", "Useful"], ["format_fit", "Format fit"]];
const BAR = 4.2;
const TYPES = { educational: "Educational", story_or_steps: "Story or steps", exercise_or_howto: "Exercise or how-to",
  interesting_idea: "An idea", website_or_tool: "Websites and tools", entertainment_list: "Films and lists",
  motivation_or_opinion: "Advice or opinion", unsuitable_or_too_little: "Little to explain" };
const NAMES = { caregiver: "Maya", grandparent: "Grandma" };
const KID_NAMES = { caregiver: "Mom", grandparent: "Grandma" };
const state = { index: null, reel: null, round: 0, format: "", viewer: null, type: "all", who: "parent" };

const score = (x) => (x ? x.toFixed(1) : "–");
const tone = (x) => (x >= BAR ? "ok" : x >= 3.5 ? "" : "low");
const short = (t, n = 64) => { const s = (t || "").replace(/\s+/g, " ").trim(); return s.length > n ? `${s.slice(0, n - 1)}…` : s; };

async function init() {
  $("mark").innerHTML = ICON.mark;
  await loadIcons();
  const [index, summary] = await Promise.all([api("/api/lab"), api("/api/lab/summary").catch(() => null)]);
  state.index = index;
  if (summary) { drawTuning($("tune"), summary); $("stats").hidden = true; } else { $("tune").hidden = true; drawStats(); }
  drawFilter();
  drawList();
  const first = location.hash.slice(1) || state.index.reels.find((r) => !r.skipped && r.rounds.length)?.id;
  if (first) openReel(first);
}

function roundsSeen() {
  return [...new Set(state.index.reels.flatMap((r) => r.rounds.map((x) => x.round)))].sort((a, b) => a - b);
}

function drawStats() {
  const reels = state.index.reels;
  const usable = reels.filter((r) => !r.skipped);
  const avg = (xs) => xs.reduce((a, b) => a + b, 0) / (xs.length || 1);
  const at = (list, n) => usable.map((r) => (r[list] || []).find((x) => x.round === n)).filter(Boolean);
  const tile = (value, label) => `<div class="stat"><b>${value}</b><span>${esc(label)}</span></div>`;
  // rounds 1-3 on the same judge (v2): the best moment per reel; the full set (round 4) and Leo's set: every moment
  const r1 = at("rounds", 1), r3 = at("rounds", 3), r4 = at("rounds", 4), k1 = at("kids", 1);
  const notion = state.index.notion[state.index.notion.length - 1];
  const tiles = [tile(`${usable.length}<small>/${reels.length}</small>`, "reels with a video")];
  if (r1.length && r3.length) tiles.push(tile(`${score(avg(r1.map((x) => x.best_v2)))}<small> → </small>${score(avg(r3.map((x) => x.best_v2)))}`, `best moment per reel, round 1 → 3 (${r3.length} reels)`));
  if (r4.length) tiles.push(tile(`${score(avg(r4.map((x) => x.every)))}`, `every moment of the full set, round 4 (${r4.length} of ${usable.length} reels)`));
  if (k1.length) tiles.push(tile(`${score(avg(k1.map((x) => x.every)))}`, `every moment of Leo's set (${k1.length} of ${usable.length} reels)`));
  if (notion) tiles.push(tile(`${notion.passed}<small>/${notion.total}</small>`, "Notion retrieval scenarios"));
  $("stats").innerHTML = tiles.join("");
  $("stats").style.setProperty("--tiles", tiles.length);
}

function drawFilter() {
  const types = [...new Set(state.index.reels.map((r) => r.type).filter(Boolean))];
  $("filter").innerHTML = `<label class="sr" for="type">Type</label><select id="type"><option value="all">All types</option>${types.map((t) => `<option value="${esc(t)}">${esc(TYPES[t] || t)}</option>`).join("")}</select>`;
  $("type").onchange = (e) => { state.type = e.target.value; drawList(); };
}

function drawList() {
  const reels = state.index.reels.filter((r) => state.type === "all" || r.type === state.type);
  $("reels").innerHTML = reels.map((r) => {
    const trail = r.rounds.map((x) => `<span class="sc ${tone(x.best)}">${score(x.best)}</span>`).join(`<i>→</i>`);
    return `<li><button type="button" data-reel="${esc(r.id)}" aria-current="${state.reel?.id === r.id}" ${r.skipped ? "disabled" : ""}>
      <span class="t">${esc(short(r.title, 58))}</span>
      <span class="m">${esc(r.skipped ? "No video: skipped" : TYPES[r.type] || "")}${r.duration_s ? ` · ${Math.round(r.duration_s)} s` : ""}</span>
      ${r.rounds.length ? `<span class="trail">${trail}${r.kids?.length ? `<b class="kid">Leo <span class="sc ${tone(r.kids[r.kids.length - 1].best)}">${score(r.kids[r.kids.length - 1].best)}</span></b>` : ""}</span>` : ""}</button></li>`;
  }).join("");
  $("reels").onclick = (e) => { const b = e.target.closest("[data-reel]"); if (b) openReel(b.dataset.reel); };
}

async function openReel(id) {
  stop();
  state.reel = await api(`/api/lab/${encodeURIComponent(id)}`);
  history.replaceState(null, "", `#${id}`);
  if (state.who === "kids" && !state.reel.kids?.length) state.who = "parent";
  const rounds = runs();
  state.round = rounds.length ? rounds[rounds.length - 1].round : 0;
  state.format = "";
  document.querySelectorAll("[data-reel]").forEach((b) => b.setAttribute("aria-current", String(b.dataset.reel === id)));
  drawDetail();
}

const runs = () => (state.who === "kids" ? state.reel.kids : state.reel.rounds) || [];

function stop() { state.viewer?.stop?.(); state.viewer = null; stopSpeech(); }

function drawDetail() {
  const r = state.reel;
  const p = r.probe || {};
  const t = r.transcript || {};
  const round = runs().find((x) => x.round === state.round);
  const stills = round?.stills?.length ? round.stills : r.frames;
  const names = state.who === "kids" ? KID_NAMES : NAMES;
  const issues = Object.entries(p.bands || {}).filter(([, v]) => v !== "pass");
  const bands = issues.length ? issues.map(([k, v]) => `<span class="badge ${v === "weak" ? "warn" : "danger"}"><i></i>${esc(k.replace("_", " "))}: ${esc(v)}</span>`).join("")
    : `<span class="badge ok"><i></i>All ${Object.keys(p.bands || {}).length} video and audio checks pass</span>`;
  const agree = t.agreement != null ? `agrees ${Math.round(t.agreement * 100)}% with the earlier transcript`
    : t.scripts?.[1] && t.scripts[0] !== t.scripts[1] ? `earlier transcript in another script (${esc(t.scripts[1])})` : "no earlier transcript";
  const outputs = round?.outputs || {};
  const formats = Object.keys(outputs);
  if (!state.format || !outputs[state.format]) state.format = formats[0] || "";
  const tabs = formats.map((f) => {
    const j = round.judged[f];
    return `<button type="button" role="tab" data-format="${esc(f)}" aria-selected="${f === state.format}">${esc(formatName(f, "en", names))}${j ? `<span class="sc ${tone(j.score)}">${score(j.score)}</span>` : ""}</button>`;
  }).join("");
  $("detail").innerHTML = `
    <header class="rd-head">
      <div><div class="eyebrow">${esc(r.id)} · ${esc(TYPES[round?.profile?.content_type] || "")}</div><h2>${esc(short(r.title, 110))}</h2>
      <p class="rd-meta">${Math.round(p.duration_s || 0)} s · ${p.width}×${p.height} · ${p.fps} fps · ${t.words || 0} words spoken${t.words ? ` (${t.wpm}/min), ${agree}` : ""}</p></div>
    </header>
    <div class="rd-bands">${bands}</div>
    ${stills.length ? `<div class="rd-frames">${stills.map((f, k) => `<figure><img src="${esc(f)}" alt="Still ${k + 1}" loading="lazy"><figcaption>${esc(short(round?.reading?.pictures_en?.[k] || "", 60))}</figcaption></figure>`).join("")}</div>` : ""}
    ${round?.timeline?.segments?.length ? `<details class="rd-caption"><summary>Watched whole: ${round.timeline.segments.length} steps (Muse Spark, with its sound)</summary><ol class="rd-timeline">${round.timeline.segments.map((g) => `<li><b>${g.start_s.toFixed(0)}–${g.end_s.toFixed(0)} s</b> ${esc(g.shows_en)}${g.said_en ? ` <em>“${esc(short(g.said_en, 120))}”</em>` : ""}${g.focus_en ? ` <span class="sc">${esc(g.focus_en)}</span>` : ""}</li>`).join("")}</ol></details>` : ""}
    ${round?.items?.length ? `<details class="rd-caption"><summary>Looked up one by one: ${round.items.length} ${round.items.length === 1 ? "item" : "items"}</summary><ul class="rd-timeline">${round.items.map((i) => `<li><b>${esc(i.name)}</b> (${esc(i.kind)}): ${esc(i.what_en)} ${esc(i.detail_en)}${i.suitable_en ? ` · ${esc(i.suitable_en)}` : ""}</li>`).join("")}</ul></details>` : ""}
    ${r.caption ? `<details class="rd-caption"><summary>Caption and transcript</summary><p>${esc(r.caption)}</p>${t.text ? `<p class="tx">${esc(t.text.slice(0, 1200))}</p>` : ""}</details>` : ""}
    <div class="rd-rounds">${r.kids?.length ? `<div class="seg small" data-who-seg><button type="button" data-who="parent" aria-pressed="${state.who === "parent"}">For Linda, 79</button><button type="button" data-who="kids" aria-pressed="${state.who === "kids"}">For Leo, 9</button></div>` : ""}
      <span class="eyebrow">Round</span><div class="seg small" data-round-seg>${runs().map((x) => `<button type="button" data-round="${x.round}" aria-pressed="${x.round === state.round}">${x.round}</button>`).join("")}</div>
      ${round ? `<span class="rd-verdict">Fact check: <b>${esc((round.fact_check?.verdict || "").replaceAll("_", " "))}</b> · Shape: <b>${esc((round.plan?.content_shape || "–").replace("_", " "))}</b> · Judge's best format: <b>${esc(formatName(round.best_format, "en", names) || "–")}</b></span>` : ""}</div>
    ${round ? `<div class="rd-work">
      <div class="rd-moment"><div class="rd-tabs" role="tablist">${tabs}</div><div class="rd-viewer" id="viewer"></div></div>
      <aside class="rd-judge" id="judge"></aside></div>` : `<p class="app-note">No round has run on this reel.</p>`}`;
  $("detail").querySelector("[data-round-seg]").onclick = (e) => { const b = e.target.closest("[data-round]"); if (b) { stop(); state.round = Number(b.dataset.round); state.format = ""; drawDetail(); } };
  const whoSeg = $("detail").querySelector("[data-who-seg]");
  if (whoSeg) whoSeg.onclick = (e) => {
    const b = e.target.closest("[data-who]");
    if (!b || b.dataset.who === state.who) return;
    stop(); state.who = b.dataset.who; const list = runs(); state.round = list.length ? list[list.length - 1].round : 0; state.format = ""; drawDetail();
  };
  const tablist = $("detail").querySelector(".rd-tabs");
  if (tablist) tablist.onclick = (e) => { const b = e.target.closest("[data-format]"); if (b) { stop(); state.format = b.dataset.format; drawDetail(); } };
  if (round && state.format) {
    state.viewer = mountViewer($("viewer"), state.format, outputs[state.format], { lang: "en", names });
    drawJudge(round);
  }
}

function drawJudge(round) {
  const j = round.judged[state.format];
  if (!j) { $("judge").innerHTML = `<p class="app-note">Not judged.</p>`; return; }
  const crits = j.natural ? [...CRITERIA, ["natural", "Natural"]] : CRITERIA; // judge v4 adds natural
  const bars = crits.map(([k, label]) => `<div class="crit"><span>${label}</span><i><b style="width:${(j[k] / 5) * 100}%"></b></i><em>${j[k]}</em></div>`).join("");
  const problems = j.problems.map((p) => `<li class="${p.severity}"><span class="badge ${p.severity === "major" ? "danger" : ""}"><i></i>${esc(p.severity)} · ${esc(p.cause)}</span>${esc(p.problem_en)}</li>`).join("");
  $("judge").innerHTML = `<div class="jd-score"><b class="${tone(j.score)}">${score(j.score)}</b><span>of 5 · Muse Wonder judge</span></div>
    <div class="crits">${bars}</div>
    <p class="jd-verdict">${esc(j.verdict_en)}</p>
    ${problems ? `<h3>What still falls short</h3><ul class="jd-problems">${problems}</ul>` : `<p class="app-note">No problems found.</p>`}
    ${round.missing?.length ? `<h3>Not carried by any moment</h3><ul class="jd-missing">${round.missing.map((m) => `<li>${esc(m)}</li>`).join("")}</ul>` : ""}
    ${round.guardian ? `<h3>Child-safety review</h3><p class="jd-verdict">${round.guardian.safe_for_child ? "Safe for Leo." : `Held for Maya: ${esc(round.guardian.concerns_en.join(" "))}`}</p>` : ""}
    <p class="jd-cost">This round on this reel: $${((round.cost?.usd || 0) + (round.cost?.image_usd || 0)).toFixed(3)} · ${Math.round(round.seconds || 0)} s</p>`;
}

init().catch((err) => { $("detail").innerHTML = `<p class="app-note">${esc(err.message)}</p>`; });
