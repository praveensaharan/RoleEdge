// The Lab page: how the agents were tested and tuned, in aggregate (GET /api/lab/summary: data/lab/summary.json,
// written by `python -m roleedge.lab report` and shipped with the app). Visitors can't run anything, so no text here
// names a command or a file path. No reel is shown or named: they are other people's content. Charts follow one
// system: marks in ink, an earlier round in grey (with labels and a table view, as it is light), status colour
// only on a change for better or worse, a tooltip on every mark and the same values in a table. The page's motion is
// the home page's (motion.js), and each chart draws its marks in as it scrolls into view.
import { ICON, esc } from "./common.js";
import { fades, field, fields, nav, pointer, reveals, splitHeadline } from "./motion.js";

const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const fmtN = (n) => Number(n).toLocaleString("en-US");
const usd = (n, d = 2) => `$${Number(n).toFixed(d)}`;
const pct = (r) => `${Math.round(r * 100)}%`;
const ROUND = (n) => `Round ${n}`;

const CRITERIA = { natural: "Sounds like family", engaging: "Engaging", clear: "Clear for her", format_fit: "Uses its format well",
  faithful: "Faithful to the reel", useful: "Useful to her" };
const FORMAT = { note: "Note in your words", steps: "Slides", map: "Mind map", askme: "Quiz", video: "Animated video",
  picture: "Picture", card: "Fridge card", story: "Picture story", quiz: "Quiz game", relay: "Ask Grandma" };
const CAUSE = { prompt: "Instructions (prompt)", workflow: "Workflow", tool: "A tool or agent", evaluation: "The judge", model: "Model use" };
const CAUSE_REST = { prompt: "changed the agents' instructions", workflow: "changed the workflow", tool: "added a tool",
  evaluation: "made the judge fairer", model: "changed how a model is used" };
const GAIN = { natural: "how natural it sounds", engaging: "how engaging it is", clear: "how clear it is", format_fit: "how well it uses its format",
  faithful: "how faithful it is", useful: "how useful it is" };
const KIND_SHORT = { exercise_or_howto: "how-tos", entertainment_list: "lists", motivation_or_opinion: "opinions", educational: "explainers",
  website_or_tool: "tool reels", story_or_steps: "stories", scam_or_warning: "warnings", news: "news", product: "products",
  unsuitable_or_too_little: "thin reels", other: "other reels" };
const lastOf = (a) => (a?.length ? a[a.length - 1] : null);
const maxOf = (a, f = (x) => x) => (a.length ? Math.max(...a.map(f)) : 0);
const cap = (t) => t.charAt(0).toUpperCase() + t.slice(1);
const andList = (xs) => (xs.length < 2 ? xs.join("") : `${xs.slice(0, -1).join(", ")} or ${xs[xs.length - 1]}`);
/** A headline from the data, so it stays true when the numbers change: the claim, and a softer second half. */
const headline = (el, claim, soft = "") => { if (el) el.innerHTML = `${esc(claim)}${soft ? ` <span class="soft">${esc(soft)}</span>` : ""}`; };

// ------------------------------------------------------------------ chart pieces (HTML; every text escaped)

const tipAttrs = (text) => `tabindex="0" role="img" data-tip="${esc(text)}" aria-label="${esc(text)}"`;

function chart(title, sub, body, table = "", extra = "") {
  return `<article class="chart spot" data-reveal><header><h3>${esc(title)}</h3>${sub ? `<p>${esc(sub)}</p>` : ""}</header>${body}${extra}${table}</article>`;
}

function tableView(caption, head, rows) {
  return `<details class="tview"><summary>Show as a table</summary><table><caption>${esc(caption)}</caption>
    <thead><tr>${head.map((h) => `<th scope="col">${esc(h)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((r) => `<tr>${r.map((c, k) => (k ? `<td>${esc(String(c))}</td>` : `<th scope="row">${esc(String(c))}</th>`)).join("")}</tr>`).join("")}</tbody></table></details>`;
}

const legend = (items) => `<div class="legend">${items.map(([cls, label]) => `<span><i class="key ${cls}"></i>${esc(label)}</span>`).join("")}</div>`;

function delta(d, digits = 2, better = "up") {
  if (Math.abs(d) < 10 ** -digits / 2) return `<em class="dl">same</em>`;
  const good = better === "up" ? d > 0 : d < 0;
  return `<em class="dl ${good ? "good" : "bad"}">${d > 0 ? "+" : "−"}${Math.abs(d).toFixed(digits)}</em>`;
}

/** Before -> after per item, on one scale: a grey dot (before), an ink dot (after), the value and the change. */
function dumbbell(rows, { lo, hi, step, digits = 2, from, to }) {
  const x = (v) => `${Math.min(100, Math.max(0, ((v - lo) / (hi - lo)) * 100)).toFixed(2)}%`;  // a value off the scale sits at its end
  const ticks = [];
  for (let v = lo; v <= hi + 1e-9; v += step) ticks.push(`<span style="left:${x(v)}">${v.toFixed(1)}</span>`);
  const body = rows.map((r, k) => `<div class="db-row" style="--i:${k}"><span class="db-label">${esc(r.label)}</span>
      <div class="db-track"><i class="db-line" style="left:${x(Math.min(r.from, r.to))};width:calc(${x(Math.max(r.from, r.to))} - ${x(Math.min(r.from, r.to))})"></i>
        <b class="db-dot before" style="left:${x(r.from)}" ${tipAttrs(`${r.label}, ${from}: ${r.from.toFixed(digits)}`)}></b>
        <b class="db-dot after" style="left:${x(r.to)}" ${tipAttrs(`${r.label}, ${to}: ${r.to.toFixed(digits)}`)}></b></div>
      <span class="db-val">${r.to.toFixed(digits)}${delta(r.to - r.from, digits)}</span></div>`).join("");
  return `${legend([["dot before", from], ["dot after", to]])}<div class="db">${body}<div class="db-row db-axis" aria-hidden="true"><span></span><div class="db-ticks">${ticks.join("")}</div><span></span></div></div>`;
}

/** Ranked horizontal bars, one hue, the value at the tip. */
function bars(rows, { max, digits = 2, unit = "", dark = false }) {
  const share = (v) => (max > 0 ? Math.min(1, Math.max(0, v / max)) : 0);
  return `<div class="hb${dark ? " on-dark" : ""}">${rows.map((r, k) => `<div class="hb-row" style="--i:${k}"><span class="hb-label">${esc(r.label)}${r.note ? `<small>${esc(r.note)}</small>` : ""}</span>
      <div class="hb-track"><b class="hb-bar" style="width:calc((100% - 56px) * ${share(r.v).toFixed(4)})" ${tipAttrs(`${r.label}: ${r.v.toFixed(digits)}${unit}${r.note ? ` · ${r.note}` : ""}`)}></b>
      <span class="hb-val">${r.v.toFixed(digits)}${esc(unit)}</span></div></div>`).join("")}</div>`;
}

/** Columns per round, one hue (the latest in ink); only the first and last carry their value, the rest are in the
 *  tooltip and the table. */
function columns(points, { max, format, label = ROUND }) {
  const n = points.length;
  const height = (v) => Math.max(1.5, max > 0 ? Math.min(1, v / max) * 86 : 0);
  return `<div class="cols" style="--n:${n}">${points.map((p, k) => {
    const shown = k === 0 || k === n - 1;
    return `<div class="col" style="--i:${k}"><div class="col-plot">${shown ? `<span class="col-val">${esc(format(p.v))}</span>` : ""}
        <b class="col-bar${k === n - 1 ? " last" : ""}" style="height:${height(p.v).toFixed(2)}%" ${tipAttrs(`${label(p.round)}: ${format(p.v)}${p.note ? ` · ${p.note}` : ""}`)}></b></div>
      <span class="col-x">${esc(`R${p.round}`)}</span></div>`;
  }).join("")}</div>`;
}

const tile = ({ value, label, from = "", note = "", tone = "" }) => `<div class="tile spot ${tone}" data-reveal>
    <b>${esc(value)}</b><span>${esc(label)}</span>${from ? `<em>${esc(from)}</em>` : ""}${note ? `<small>${esc(note)}</small>` : ""}</div>`;

// ------------------------------------------------------------------ the sections

/** A number in the strip, in the home page's dot-matrix type; it counts up when it scrolls into view. */
const stat = (n, label, note, unit = "") => `<div class="stat" data-reveal>
    <b><span data-count="${n}">${esc(fmtN(n))}</span>${esc(unit)}</b><span>${esc(label)}</span>${note ? `<small>${esc(note)}</small>` : ""}</div>`;

function hero(s) {
  const rounds = Math.max(s.rounds_linda || 0, s.rounds_leo || 0);
  $("#hero-pill").textContent = `${fmtN(s.usable)} real reels${rounds ? ` · ${rounds} rounds` : ""}`;
  const linda = s.robotic.filter((r) => r.who === "Linda");
  const stats = [];
  if (linda.length) {
    const last = lastOf(linda);
    const worst = linda.reduce((a, b) => (b.rate > a.rate ? b : a));
    stats.push(stat(Math.round(last.rate * 100), "of moments still sound robotic", `down from ${pct(worst.rate)} in round ${worst.round}`, "%"));
  }
  stats.push(stat(s.usable, `real reels, of ${fmtN(s.reels)} shared`, `${fmtN(s.reel_runs)} runs through the agents`),
    stat(s.moments, "moments made and scored", `${fmtN(s.model_calls)} model calls, each logged and priced`),
    stat(s.changes, "changes, each traced to a cause", `${fmtN(s.code_tests)} automated tests guard them`));
  $("#kpis").innerHTML = stats.join("");
}

function quality(s) {
  const parts = [];
  const [a, b] = [s.v4[0], lastOf(s.v4)];
  if (a && b) {
    const from = ROUND(a.round), to = ROUND(b.round);
    $("#quality-sub").textContent = `Judge v4, the strictest (it adds how natural a moment sounds), scored rounds ${a.round} to ${b.round} on the same ${b.judged} reels, every moment from 1 to 5. Earlier judges are not on the same scale, so they are left out of these charts.`;
    const crit = Object.keys(CRITERIA).filter((k) => k in b.criteria && k in a.criteria).map((k) => ({ key: k, label: CRITERIA[k], from: a.criteria[k], to: b.criteria[k] }))
      .sort((x, y) => (y.to - y.from) - (x.to - x.from));
    const per = [{ label: "Best moment per reel", from: a.mean_best, to: b.mean_best }, { label: "Every moment", from: a.pack_mean, to: b.pack_mean },
      { label: "Weakest moment per reel", from: a.weakest, to: b.weakest }];
    const up = [...crit, ...per].filter((r) => r.to > r.from).length, all = crit.length + per.length;
    if (a !== b) headline($("#quality-h"), up === all ? "Every score went up." : `${up} of ${all} scores went up.`,
      crit[0] && crit[0].to > crit[0].from ? `Most of all, ${GAIN[crit[0].key]}.` : "");
    parts.push(
      chart("For Linda (79): by criterion", `Mean score of every moment, ${from} → ${to}, sorted by the change.`,
        dumbbell(crit, { lo: 2, hi: 5, step: 0.5, from, to }),
        tableView("Mean score by criterion", ["Criterion", from, to], crit.map((r) => [r.label, r.from.toFixed(2), r.to.toFixed(2)]))),
      chart("For Linda (79): per reel", `${from} → ${to}. A reel is at the bar when one of its moments scores 4.2 or more.`,
        dumbbell(per, { lo: 2, hi: 5, step: 0.5, from, to }),
        tableView("Per reel", ["Measure", from, to], [...per.map((r) => [r.label, r.from.toFixed(2), r.to.toFixed(2)]),
          ["Reels at the bar", a.at_bar, b.at_bar], ["Problems the judge found", a.majors, b.majors]]),
        `<div class="mini">${tile({ value: `${b.at_bar} of ${b.judged}`, label: "reels at the bar", from: `from ${a.at_bar}`, tone: b.at_bar > a.at_bar ? "good" : "" })}${tile({ value: fmtN(b.majors), label: "problems the judge found", from: `from ${fmtN(a.majors)}`, tone: b.majors < a.majors ? "good" : "" })}</div>`));
  }
  const kid = lastOf(s.kids_v2);
  if (kid) {
    const kidCrit = Object.keys(CRITERIA).filter((k) => k in kid.criteria).map((k) => ({ label: CRITERIA[k], v: kid.criteria[k] })).sort((x, y) => y.v - x.v);
    parts.push(
      chart(`For Leo (9): the children's judge, round ${kid.round}`, "Safety first, then the same criteria for a 9-year-old. Mean of every moment.",
        bars(kidCrit, { max: 5 }),
        tableView("Leo, by criterion", ["Criterion", ROUND(kid.round)], kidCrit.map((r) => [r.label, r.v.toFixed(2)]))),
      chart("For Leo (9): per reel", `Round ${kid.round}: the same ${kid.judged} reels, made into a child's set.`,
        `<div class="mini">${tile({ value: kid.mean_best.toFixed(2), label: "best moment per reel, of 5" })}${tile({ value: `${kid.at_bar} of ${kid.judged}`, label: "reels at the bar" })}${tile({ value: kid.pack_mean.toFixed(2), label: "every moment, of 5" })}${tile({ value: kid.weakest.toFixed(2), label: "weakest moment per reel" })}</div>`));
  }
  $("#quality-charts").innerHTML = parts.join("");
}

function voice(s) {
  const part = (who, note) => {
    const rows = s.robotic.filter((r) => r.who === who);
    return rows.length ? chart(`${who === "Linda" ? "Linda (79)" : "Leo (9)"}: moments with a robotic habit`, note,
      columns(rows.map((r) => ({ round: r.round, v: r.rate, note: `${r.with_habit} of ${r.moments} moments, ${r.habits} habits` })), { max: 1, format: pct }),
      tableView(`${who}: robotic habits by round`, ["Round", "Moments", "With a habit", "Share"], rows.map((r) => [r.round, r.moments, r.with_habit, pct(r.rate)]))) : "";
  };
  const last = lastOf(s.robotic.filter((r) => r.who === "Linda"));
  if (last) headline($("#voice-h"), "From a report to a daughter talking.", `Robotic habits down to ${pct(last.rate)}.`);
  $("#voice-charts").innerHTML = part("Linda", "Round 4 made the full set of six moments per reel, so there was more to get wrong. Round 6 added the family-voice rules and a code check that gives the maker one rewrite.")
    + part("Leo", "Round 3 re-ran only the sets held for a child. Round 4 added the same voice rules and checks.");
}

function moments(s) {
  const parts = [];
  const [a, b] = [s.v4[0], lastOf(s.v4)];
  const kinds = (who) => Object.entries(s.by_kind?.[who] || {}).map(([key, k]) => ({ key, label: k.name, v: k.mean_best, reels: k.reels, natural: k.natural,
    note: `${k.reels} ${k.reels === 1 ? "reel" : "reels"} · sounds like family ${k.natural.toFixed(1)}` })).sort((x, y) => y.v - x.v);
  const lk = kinds("linda"), kk = kinds("leo");
  if (a && b) {
    const from = ROUND(a.round), to = ROUND(b.round);
    const fm = Object.keys(b.by_format).filter((f) => a.by_format[f]).map((f) => ({ label: FORMAT[f] || f, from: a.by_format[f].score, to: b.by_format[f].score }))
      .sort((x, y) => y.to - x.to);
    const up = fm.filter((r) => r.to > r.from).length;
    const best = lk.slice(0, 2).map((k) => KIND_SHORT[k.key] || k.label.toLowerCase());
    if (a !== b && fm.length) headline($("#moments-h"), up === fm.length ? "Every format improved." : `${up} of ${fm.length} formats improved.`,
      best.length ? `${cap(best.join(" and "))} explain best.` : "");
    parts.push(chart("For Linda: by moment format", `Mean score, ${from} → ${to}.`, dumbbell(fm, { lo: 2.5, hi: 4.5, step: 0.5, from, to }),
      tableView("Linda, by format", ["Format", from, to], fm.map((r) => [r.label, r.from.toFixed(2), r.to.toFixed(2)]))));
  }
  const kid = lastOf(s.kids_v2);
  if (kid) {
    const kf = Object.entries(kid.by_format).map(([f, x]) => ({ label: FORMAT[f] || f, v: x.score, note: `${x.count} moments` })).sort((x, y) => y.v - x.v);
    parts.push(chart(`For Leo: by moment format, round ${kid.round}`, "Mean score of each format in a child's set.", bars(kf, { max: 5 }),
      tableView("Leo, by format", ["Format", ROUND(kid.round)], kf.map((r) => [r.label, r.v.toFixed(2)]))));
  }
  $("#moment-charts").innerHTML = parts.join("");
  const kindChart = (title, sub, rows) => chart(title, sub, bars(rows, { max: 5 }),
    tableView(title, ["Kind of reel", "Reels", "Best moment", "Sounds like family"], rows.map((r) => [r.label, r.reels, r.v.toFixed(2), r.natural.toFixed(2)])));
  $("#kind-charts").innerHTML = (lk.length ? kindChart(`For Linda: by kind of reel${b ? `, round ${b.round}` : ""}`, "Best moment per reel, by what the reel was, as the profiler grouped it. A kind with one reel counts as other.", lk) : "")
    + (kk.length ? kindChart(`For Leo: by kind of reel${kid ? `, round ${kid.round}` : ""}`, "The same, for the child's set.", kk) : "");
}

function safety(s) {
  const lastL = lastOf(s.v4), lastK = lastOf(s.kids_v2);
  const latest = [lastL, lastK].filter(Boolean);
  const unsafe = latest.reduce((n, r) => n + r.unsafe_passed, 0);
  const earlier = maxOf([...s.v2, ...s.v3, ...s.v4.slice(0, -1), ...s.kids], (r) => r.unsafe_passed);
  const mostHeld = s.kids.reduce((m, k) => (!m || k.held_for_child > m.held_for_child ? k : m), null);
  const notion = s.notion.filter((n) => !n.label);
  const when = [lastL && `round ${lastL.round} for Linda`, lastK && `round ${lastK.round} for Leo`].filter(Boolean).join(" and ");
  if (latest.length) headline($("#safety-h"), unsafe === 0 ? "Nothing unsafe in the latest rounds." : `${unsafe} unsafe ${unsafe === 1 ? "finding" : "findings"} got past the checks in the latest rounds.`,
    "And every connection was tested.");
  const tiles = [
    latest.length ? { value: String(unsafe), label: "unsafe findings that got past the checks in the latest rounds", note: `${cap(when)}.${earlier ? ` Earlier rounds had up to ${earlier}.` : ""}`, tone: unsafe === 0 ? "good" : "" } : null,
    lastK ? { value: String(lastK.held_for_child), label: "of Leo's sets held as not right for a child",
      from: mostHeld && mostHeld.held_for_child > lastK.held_for_child ? `from ${mostHeld.held_for_child} in round ${mostHeld.round}` : "",
      note: "After the children's rule: nothing rated for teens, no stunt steps, no \"follow for more\".", tone: mostHeld && mostHeld.held_for_child > lastK.held_for_child ? "good" : "" } : null,
    lastL ? { value: `${lastL.gate_held} of ${lastL.judged}`, label: "packs the send gate held for a person to read", note: `Round ${lastL.round}. The gate is code: dates, money, codes, links, secrecy, pressure.` } : null,
    notion.length ? { value: `${lastOf(notion).passed}/${lastOf(notion).total}`, label: "questions answered right from a real Notion workspace", from: `from ${notion[0].passed}/${notion[0].total}`, tone: "good" } : null,
    s.links ? { value: `${s.links.passed}/${s.links.total}`, label: "shared reel and post links handled as expected" } : null,
    s.apps ? { value: `${s.apps.answered}/${s.apps.total}`, label: "questions answered from the demo mail, calendar and chat" } : null,
  ].filter(Boolean);
  $("#safety-tiles").innerHTML = tiles.map(tile).join("");
}

function changes(s) {
  const counts = {};
  for (const c of s.change_log) counts[c.cause] = (counts[c.cause] || 0) + 1;
  const rows = Object.entries(counts).map(([k, v]) => ({ key: k, label: CAUSE[k] || k, v })).sort((x, y) => y.v - x.v);
  const first = (t) => (t.match(/^.*?[.!?](\s|$)/)?.[0] || t).trim();
  const list = s.change_log.map((c) => `<li><span class="cid">${esc(c.id)}</span><span class="ccause">${esc(CAUSE[c.cause] || c.cause)}</span>
      <span class="ctext">${esc(first(c.change))}</span><code>${esc(c.where)}</code></li>`).join("");
  const waiting = s.change_log.filter((c) => /not yet measured/i.test(c.change)).length;
  headline($("#changes-h"), `${s.changes} weaknesses traced to their cause.`, waiting ? `Then fixed, and all but ${waiting} measured again.` : "Then fixed and measured again.");
  if (rows.length) {
    const [top, ...rest] = rows;
    $("#changes-sub").textContent = `Every change is logged with the weakness behind it and the round it was made in. The largest group, ${top.v} of ${s.changes}, ${CAUSE_REST[top.key] || top.label.toLowerCase()}`
      + (rest.length ? `; the others ${andList(rest.map((r) => CAUSE_REST[r.key] || r.label.toLowerCase()))}.` : ".");
  }
  $("#change-charts").innerHTML = (rows.length ? chart("Where the fixes were", `${s.changes} changes, by what was changed.`, bars(rows, { max: maxOf(rows, (r) => r.v), digits: 0 }),
    tableView("Changes by cause", ["Cause", "Changes"], rows.map((r) => [r.label, r.v]))) : "")
    + `<article class="chart" data-reveal><header><h3>Every change</h3><p>What changed, and where in the code. The full log, with the weakness behind each change and the round it was measured in, is in the <a href="https://github.com/praveensaharan/RoleEdge/blob/main/docs/REEL_LAB.md#log" target="_blank" rel="noopener noreferrer">Reel Lab notes</a>.</p></header>
      <ol class="clog">${list}</ol></article>`;
}

function tuning(s) {
  const ds = s.dataset || { examples: 0, by_format: {} };
  const rows = Object.entries(ds.by_format).map(([f, v]) => ({ label: FORMAT[f] || f, v })).sort((x, y) => y.v - x.v);
  const garvit = [["Unsafe lines caught", "52%", "99.6%"], ["Flags that were right", "92%", "98.7%"], ["Safe lines flagged", "2.0%", "0.6%"], ["Right category codes", "0%", "82%"]];
  $("#tuning-cards").innerHTML = `<article class="chart dark-card" data-reveal><header><span class="tag">Dataset</span><h3>${fmtN(ds.examples)} moments in the family's voice</h3>
      <p>Every moment the judge scored ${esc(String(ds.min_score ?? 4.3))} or more, with "sounds like family" at ${esc(String(ds.min_natural ?? 4))} or more, no robotic habit, and past the send gate. Each is a training pair: the maker's instructions, its brief and the approved moment. ${fmtN(ds.for_child || 0)} are for a child.</p></header>
      ${bars(rows, { max: Math.max(1, ...rows.map((r) => r.v)), digits: 0, dark: true })}
      <p class="fine">Ready for a LoRA on an open Meta model. Nothing is trained on it yet.</p></article>
    <article class="chart dark-card" data-reveal><header><span class="tag">Trained · research</span><h3><a href="https://huggingface.co/pra40109/Llama-Garvit-1.0" target="_blank" rel="noopener noreferrer">Llama-Garvit-1.0</a></h3>
      <p>A LoRA adapter for Llama Guard 3 1B that checks one line for children aged 4 to 12, on our own categories. 2,552 training lines, one pass, trained on Modal.</p></header>
      <div class="gtable" role="table" aria-label="727 held-out lines, before and after training"><div class="gr gh" role="row"><span role="columnheader">727 held-out lines</span><span role="columnheader">Untrained</span><span role="columnheader">Trained</span></div>
        ${garvit.map(([l, x, y]) => `<div class="gr" role="row"><span role="cell">${esc(l)}</span><span role="cell">${x}</span><b role="cell">${y}</b></div>`).join("")}</div></article>`;
}

function cost(s) {
  const linda = [...s.v2, ...s.v3, ...s.v4].reduce((m, r) => m.set(r.round, r), new Map());
  const lrows = [...linda.values()].sort((a, b) => a.round - b.round);
  const krows = [...s.kids, ...s.kids_v2];
  const per = (r) => r.cost / Math.max(1, r.judged);
  const sp = s.spend;
  const lastL = lastOf(lrows);
  $("#cost-h").innerHTML = `The whole lab, ${usd(sp.total_usd)}.${lastL ? ` <span class="soft">About ${usd(per(lastL))} a reel per round.</span>` : ""}`;
  const used = sp.limit_usd > 0 ? Math.min(100, (sp.total_usd / sp.limit_usd) * 100) : 0;
  const meter = `<div class="meter-row"><div class="spend-meter" role="img" aria-label="${esc(`${usd(sp.total_usd)} of ${usd(sp.limit_usd, 0)}`)}"><b style="width:${used.toFixed(1)}%"></b></div>
      <span>${usd(sp.total_usd)} of the ${usd(sp.limit_usd, 0)} limit · Meta models ${usd(sp.meta_usd)} · pictures ${usd(sp.images_usd)} · transcription ${usd(sp.transcribe_usd)}</span></div>`;
  const part = (title, rows) => (rows.length ? chart(title, "What a round cost per reel, the judge included.",
    columns(rows.map((r) => ({ round: r.round, v: per(r), note: `${usd(r.cost)} for ${r.judged} reels` })), { max: maxOf(rows, per), format: (v) => usd(v, 3) }),
    tableView(title, ["Round", "Reels", "Cost", "Per reel"], rows.map((r) => [r.round, r.judged, usd(r.cost), usd(per(r), 3)]))) : "");
  $("#cost-charts").innerHTML = part("Linda (79), per round", lrows) + part("Leo (9), per round", krows) + `<div class="span2" data-reveal>${meter}</div>`;
}

// ------------------------------------------------------------------ the page: icons, header, reveals, tooltip

async function hydrate() {
  const paths = await fetch("/api/icons").then((r) => r.json()).catch(() => ({}));
  $$("[data-i]").forEach((el) => {
    el.innerHTML = paths[el.dataset.i] ? `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[el.dataset.i]}</svg>` : "";
  });
  $$("[data-mark]").forEach((el) => { el.innerHTML = ICON.mark; });
}

/** One tooltip for every mark, on hover and on keyboard focus (the table view has the same values). */
function tooltips() {
  const tip = $("#tip");
  const show = (el) => {
    tip.textContent = el.dataset.tip;
    tip.hidden = false;
    const r = el.getBoundingClientRect(), t = tip.getBoundingClientRect();
    tip.style.left = `${Math.min(innerWidth - t.width - 8, Math.max(8, r.left + r.width / 2 - t.width / 2))}px`;
    tip.style.top = `${Math.max(8, r.top - t.height - 10)}px`;
  };
  const hide = () => { tip.hidden = true; };
  document.addEventListener("pointerover", (e) => { const el = e.target.closest("[data-tip]"); if (el) show(el); else hide(); });
  document.addEventListener("focusin", (e) => { const el = e.target.closest("[data-tip]"); if (el) show(el); else hide(); });
  addEventListener("scroll", hide, { passive: true });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hide(); });
}

async function start() {
  splitHeadline();
  await hydrate();
  tooltips();
  const s = await fetch("/api/lab/summary").then((r) => (r.ok ? r.json() : null)).catch(() => null);
  if (!s) {
    // no results: the hero says so and goes straight to the closing call (removed, not hidden, so the fades and the
    // header see only what is on the page)
    $("#hero-lead").textContent = "The lab results can't be shown right now. Please try again later.";
    $$('main > section:not(.hero):not(.cta), .nav-links, a[href="#quality"]').forEach((el) => el.remove());
  } else {
    for (const draw of [hero, quality, voice, moments, safety, changes, tuning, cost]) {
      try { draw(s); } catch (err) { console.error(`lab: ${draw.name}`, err); } // one section's gap never blanks the page
    }
  }
  reveals();
  fades(); fields(); nav(); pointer();
  field($("#hero-canvas"));
  field($("#cta-canvas"), { gap: 20, line: false });
  document.documentElement.classList.add("ready");
}
start();
