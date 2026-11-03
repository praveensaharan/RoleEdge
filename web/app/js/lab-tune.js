// "How we tuned the agents": the lab's numbers from /api/lab/summary. Every round is a dot on its row's own scale
// (earlier rounds lighter, the latest in ink, each labelled on hover and in the table view), so a reader sees what
// moved and what didn't. No model is called; the numbers come from the stored rounds.
import { esc } from "./common.js";

const SHADES = ["#d4d4d8", "#a1a1aa", "#52525b", "#0a0a0a"]; // one neutral ramp, light -> dark; the latest is ink
const FORMAT = { card: "Fridge card", map: "Mind map", steps: "Slides", askme: "Quiz", video: "Animated video", picture: "Picture",
  note: "Maya's note", story: "Picture story", quiz: "Quiz game", relay: "Ask Grandma" };
const CRIT = { faithful: "Faithful to the reel", clear: "Clear for her", engaging: "Engaging", useful: "Useful", format_fit: "Format fit" };
const CAUSE = { prompt: "Prompt", model: "Model", tool: "Tool", workflow: "Workflow", evaluation: "Evaluation", data: "Data" };
const fmtN = (n) => n.toLocaleString("en-US");
const shade = (k, n) => SHADES[Math.max(0, SHADES.length - n + k)]; // the last of n points is always ink

/** One row: a label, its points on [lo, hi], the latest value written out, and the change from the first. */
function dotRow(label, points, { lo, hi, digits = 2, better = "up", note = "" }) {
  const x = (v) => `${(((v - lo) / (hi - lo)) * 100).toFixed(2)}%`;
  const first = points[0], last = points[points.length - 1];
  const delta = last.v - first.v;
  const good = better === "up" ? delta > 0 : delta < 0;
  const span = points.length > 1 ? `<i class="dr-line" style="left:${x(Math.min(...points.map((p) => p.v)))};right:calc(100% - ${x(Math.max(...points.map((p) => p.v)))})"></i>` : "";
  const dots = points.map((p, k) => `<button type="button" class="dr-dot${k === points.length - 1 ? " last" : ""}" style="left:${x(p.v)};--c:${shade(k, points.length)}"
      data-tip="${esc(`${p.label}: ${p.v.toFixed(digits)}${p.extra ? ` · ${p.extra}` : ""}`)}" aria-label="${esc(`${label}, ${p.label}: ${p.v.toFixed(digits)}`)}"></button>`).join("");
  const change = points.length > 1 && Math.abs(delta) >= 10 ** -digits / 2
    ? `<em class="${good ? "up" : "down"}">${delta > 0 ? "+" : "−"}${Math.abs(delta).toFixed(digits)}</em>` : `<em>same</em>`;
  return `<div class="dr"><div class="dr-label"><b>${esc(label)}</b>${note ? `<small>${esc(note)}</small>` : ""}</div>
    <div class="dr-track" data-lo="${lo}" data-hi="${hi}">${span}${dots}</div>
    <div class="dr-value"><b>${last.v.toFixed(digits)}</b>${change}</div></div>`;
}

function axis(lo, hi, step, digits = 1) {
  const ticks = [];
  for (let v = lo; v <= hi + 1e-9; v += step) ticks.push(`<span style="left:${(((v - lo) / (hi - lo)) * 100).toFixed(2)}%">${v.toFixed(digits)}</span>`);
  return `<div class="dr dr-ax" aria-hidden="true"><div class="dr-label"></div><div class="dr-axis">${ticks.join("")}</div><div></div></div>`;
}

function legend(labels) {
  return `<div class="dr-legend">${labels.map((l, k) => `<span><i style="--c:${shade(k, labels.length)}"></i>${esc(l)}</span>`).join("")}</div>`;
}

function table(caption, head, rows) {
  return `<details class="dr-table"><summary>Show as a table</summary><table><caption>${esc(caption)}</caption>
    <thead><tr>${head.map((h) => `<th scope="col">${esc(h)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((r) => `<tr>${r.map((c, k) => (k ? `<td>${esc(String(c))}</td>` : `<th scope="row">${esc(String(c))}</th>`)).join("")}</tr>`).join("")}</tbody></table></details>`;
}

const stat = (value, label, sub = "") => `<div class="tstat"><b>${value}</b><span>${esc(label)}</span>${sub ? `<small>${esc(sub)}</small>` : ""}</div>`;

export function drawTuning(el, s) {
  const v2 = s.v2, v3 = s.v3, kids = s.kids.filter((k) => k.judged === s.usable);
  const leoFix = s.kids.find((k) => k.judged < s.usable);
  const notion = s.notion.filter((n) => !n.label);
  const r = (rows, n) => rows.find((x) => x.round === n);
  const pts = (rows, key, label = (x) => `Round ${x.round}`, extra = () => "") => rows.map((x) => ({ v: x[key], label: label(x), extra: extra(x) }));

  // 1. what was done
  const head = `<div class="tune-head"><div class="eyebrow">Evaluation and tuning</div>
      <h2 id="tune-h">Tested on ${s.usable} real reels, ${fmtN(s.reel_runs)} times. Changed ${s.changes} times, each change measured.</h2>
      <p class="lead">We didn't accept a first result. Every reel went through the Studio's own agents, round after round. A Muse Wonder judge scored every moment, and code checked the rest. Each weakness was traced to its cause (prompt, model, tool or workflow), fixed, and the reels were run again.</p></div>
    <div class="tstats">
      ${stat(fmtN(s.reel_runs), "reel runs through the agents", `${s.rounds_linda} rounds for Linda (79), ${s.rounds_leo} for Leo (9)`)}
      ${stat(fmtN(s.moments), "moments made and judged", `${fmtN(s.judgements)} judge reviews`)}
      ${stat(fmtN(s.model_calls), "model calls", "Muse Spark, Wonder, Image, SAM 3.1, Voice Transcribe")}
      ${stat(String(s.changes), "changes, each one measured", "prompts, agents, tools, workflow, the judge")}
      ${stat(String(s.code_tests), "automated tests pass", "code checks on every agent")}
      ${stat(`$${s.spend.total_usd.toFixed(2)}`, "spent on the whole lab", `of a $${s.spend.limit_usd.toFixed(0)} limit`)}
    </div>`;

  // 2. the headline moves, each row on its own scale
  const headline = [];
  if (v3.length >= 2) {
    headline.push(dotRow("Best moment per reel, Linda", pts(v3, "mean_best"), { lo: 3.5, hi: 4.5, note: "Mean of each reel's best moment (judge v3)" }));
    headline.push(dotRow("Reels with a moment at 4.2 or more", pts(v3, "at_bar", undefined, (x) => `of ${x.judged}`), { lo: 0, hi: s.usable, digits: 0, note: `Of ${s.usable} reels` }));
    const full = v3.filter((x) => x.round >= 4);  // like for like: both with the full set of six moments per reel
    if (full.length >= 2) headline.push(dotRow("Weakest moment per reel", pts(full, "weakest"), { lo: 2.5, hi: 3.5, note: "Rounds 4-5, both with six moments per reel" }));
  }
  if (v2.length >= 2) headline.push(dotRow("Major problems the judge found", pts(v2, "majors"), { lo: 0, hi: 120, digits: 0, better: "down", note: "Rounds 1-3, judge v2" }));
  if (kids.length >= 2) {
    headline.push(dotRow("Leo: best moment per reel", pts(kids, "mean_best", (x) => `Leo round ${x.round}`), { lo: 3.5, hi: 4.5, note: "The children's set, children's judge" }));
    headline.push(dotRow("Leo: reels with a moment at 4.2 or more", pts(kids, "at_bar", (x) => `Leo round ${x.round}`), { lo: 0, hi: s.usable, digits: 0 }));
  }
  if (notion.length >= 2) headline.push(dotRow("Notion: retrieval scenarios passed", notion.map((n, k) => ({ v: n.passed, label: k ? "After the fixes" : "Baseline", extra: `of ${n.total}` })), { lo: 0, hi: 10, digits: 0, note: "Facts, summaries, two pages combined, answers that aren't there" }));
  const moves = `<div class="tune-block"><h3>What moved</h3><p class="sub">Each row has its own scale. A dot is a round: lighter is earlier, ink is the latest. Hover a dot for its value.</p>
    ${headline.join("")}
    ${table("What moved, round by round", ["Measure", "Rounds", "Values"], [
      ["Best moment per reel, Linda (judge v3)", v3.map((x) => x.round).join(", "), v3.map((x) => x.mean_best).join(", ")],
      ["Reels at the bar, Linda", v3.map((x) => x.round).join(", "), v3.map((x) => x.at_bar).join(", ")],
      ["Every moment, Linda", v3.map((x) => x.round).join(", "), v3.map((x) => x.pack_mean).join(", ")],
      ["Weakest moment per reel", v3.map((x) => x.round).join(", "), v3.map((x) => x.weakest).join(", ")],
      ["Major problems (judge v2)", v2.map((x) => x.round).join(", "), v2.map((x) => x.majors).join(", ")],
      ["Unsafe advice that passed the gate (judge v2, then v3)", [...v2, ...v3.slice(1)].map((x) => x.round).join(", "), [...v2, ...v3.slice(1)].map((x) => x.unsafe_passed).join(", ")],
      ["Leo: best moment per reel", kids.map((x) => x.round).join(", "), kids.map((x) => x.mean_best).join(", ")],
      ["Leo: reels at the bar", kids.map((x) => x.round).join(", "), kids.map((x) => x.at_bar).join(", ")],
      ["Notion scenarios passed", "baseline, after", notion.map((n) => `${n.passed}/${n.total}`).join(", ")],
    ])}</div>`;

  // 3. by format and by criterion, on one 1-5 scale, rounds 3-5 (judge v3)
  const formats = [...new Set(v3.flatMap((x) => Object.keys(x.by_format)))].filter((f) => FORMAT[f])
    .sort((a, b) => (r(v3, 5)?.by_format[b]?.score || 0) - (r(v3, 5)?.by_format[a]?.score || 0));
  const fmtRows = formats.map((f) => dotRow(FORMAT[f], v3.filter((x) => x.by_format[f]).map((x) => ({ v: x.by_format[f].score, label: `Round ${x.round}`, extra: `${x.by_format[f].count} moments` })), { lo: 2.5, hi: 4.5 }));
  const critRows = Object.keys(CRIT).map((k) => dotRow(CRIT[k], v3.map((x) => ({ v: x.criteria[k], label: `Round ${x.round}` })), { lo: 2.5, hi: 4.5 }));
  const byFormat = `<div class="tune-grid">
    <div class="tune-block"><h3>Every format, round by round</h3><p class="sub">Mean of the judge's five scores, 1 to 5 (judge v3). Round 3 made one to three moments per reel; from round 4, the full set.</p>
      ${legend(v3.map((x) => `Round ${x.round}`))}${fmtRows.join("")}${axis(2.5, 4.5, 0.5)}
      ${table("Every format, round by round", ["Format", ...v3.map((x) => `Round ${x.round}`)], formats.map((f) => [FORMAT[f], ...v3.map((x) => (x.by_format[f] ? `${x.by_format[f].score} (${x.by_format[f].count})` : "-"))]))}</div>
    <div class="tune-block"><h3>Every criterion, round by round</h3><p class="sub">What the judge scores in every moment, 1 to 5.</p>
      ${legend(v3.map((x) => `Round ${x.round}`))}${critRows.join("")}${axis(2.5, 4.5, 0.5)}
      ${table("Every criterion, round by round", ["Criterion", ...v3.map((x) => `Round ${x.round}`)], Object.keys(CRIT).map((k) => [CRIT[k], ...v3.map((x) => x.criteria[k])]))}</div>
  </div>`;

  // 4. Leo's set and the safety review
  const kidFormats = kids.length ? Object.keys(kids[kids.length - 1].by_format).filter((f) => FORMAT[f]) : [];
  const leo = kids.length ? `<div class="tune-block"><h3>The same reels for a child: Leo, 9</h3>
      <p class="sub">A picture story, a quiz game, an animated video, a mind map and a picture from every reel. Every set also went through the child-safety review, which holds anything unsuitable for Maya to see first.
      In round 2 it held ${kids[kids.length - 1].held_for_child} sets (films rated for teens, handstand steps, "follow for part two"). We tightened the children's rule and ran those reels again${leoFix ? `: ${leoFix.judged - leoFix.held_for_child} of ${leoFix.judged} now pass, and the ${leoFix.held_for_child} still held are about dating and stock trading, which stay with Maya` : ""}.</p>
      ${legend(kids.map((x) => `Leo round ${x.round}`))}
      ${kidFormats.map((f) => dotRow(FORMAT[f], kids.filter((x) => x.by_format[f]).map((x) => ({ v: x.by_format[f].score, label: `Leo round ${x.round}`, extra: `${x.by_format[f].count} moments` })), { lo: 2.5, hi: 4.5 })).join("")}
      ${axis(2.5, 4.5, 0.5)}</div>` : "";

  // 5. every change, by round
  const groups = [];
  for (const c of s.change_log) {
    const key = c.round.startsWith("Notion") ? "Notion" : c.round.startsWith("Leo") ? "Leo" : c.round;
    let g = groups.find((x) => x.key === key);
    if (!g) groups.push((g = { key, items: [] }));
    g.items.push(c);
  }
  const groupName = (k) => (k === "-" ? "Product, outside the rounds" : k === "Notion" ? "Notion" : k === "Leo" ? "Leo's rounds" : /rescored/.test(k) ? `The judge (${k})` : `Round ${k}`);
  const changes = `<div class="tune-block" id="changes"><h3>Every change, and why</h3>
      <p class="sub">${s.changes} changes. Each one names the weakness it fixes, with the judge's own words as evidence, where the fix belongs, and the round that measured it.</p>
      ${groups.map((g, gi) => `<details class="tg"${gi < 2 ? " open" : ""}><summary><b>${esc(groupName(g.key))}</b><span>${g.items.length} change${g.items.length > 1 ? "s" : ""}</span></summary>
        <ol>${g.items.map((c) => `<li><div class="tc-top"><code>${esc(c.id)}</code><span class="cause">${esc(CAUSE[c.cause] || c.cause)}</span><small>${esc(c.where)}</small></div>
          <p><span class="k">Found</span>${esc(c.weakness)}</p><p><span class="k">Changed</span>${esc(c.change)}</p></li>`).join("")}</ol></details>`).join("")}
    </div>`;

  const limits = `<div class="tune-block tune-limits"><h3>What still falls short</h3><ul>
      <li>${v3.length ? `${v3[v3.length - 1].at_bar} of ${s.usable}` : ""} reels reach the 4.2 bar. Most of the rest are only music or an opinion, so there is little to teach, and the quiz and the mind map suffer most on them.</li>
      <li>No real Google Calendar, Gmail, Slack or Zoom connection yet: the demo apps stand in, and the sign-in plan and its tests are written.</li>
      <li>A photo post shared as a link isn't downloaded: the caregiver attaches the pictures.</li>
      <li>The rounds ran in English, for Linda and Leo. The Japanese family uses the same agents but wasn't scored.</li></ul></div>`;

  // the family's voice: the user's own review of the moments, measured by code in every round and by judge v4
  const rob = (who) => (s.robotic || []).filter((x) => x.who === who && x.moments);
  const v4 = s.v4 || [];
  const voiceRows = [];
  if (rob("Linda").length) voiceRows.push(dotRow("Moments with a robotic habit, Linda", rob("Linda").map((x) => ({ v: x.rate * 100, label: `Round ${x.round}`, extra: `${x.with_habit} of ${x.moments} moments` })),
    { lo: 0, hi: 60, digits: 0, better: "down", note: "Code: \"the reel says\", \"I am Maya\", disclaimers, labels (%)" }));
  if (rob("Leo").length) voiceRows.push(dotRow("Moments with a robotic habit, Leo", rob("Leo").map((x) => ({ v: x.rate * 100, label: `Leo round ${x.round}`, extra: `${x.with_habit} of ${x.moments} moments` })),
    { lo: 0, hi: 60, digits: 0, better: "down", note: "The same check (%)" }));
  if (v4.length >= 1 && v4[0].criteria?.natural) voiceRows.push(dotRow("Natural, the judge's sixth score", v4.map((x) => ({ v: x.criteria.natural, label: `Round ${x.round}` })), { lo: 1, hi: 5, note: "Sounds like the family talking (judge v4)" }));
  if (v4.length >= 1) voiceRows.push(dotRow("Every moment, with natural (judge v4)", v4.map((x) => ({ v: x.pack_mean, label: `Round ${x.round}` })), { lo: 2.5, hi: 4.5 }));
  const voice = voiceRows.length ? `<div class="tune-block"><h3>The family's voice</h3><p class="sub">After reading the moments, the family asked for warmth instead of a report: no "Mom, I am Maya", no "the reel says", no disclaimers nobody needs, a scam told as kind news, products with what they're good for and an offer to get one. Code counts the robotic habits in every moment of every round; judge v4 adds a sixth score, natural (round 5 was scored again with it).</p>
      ${voiceRows.join("")}</div>` : "";
  el.innerHTML = head + moves + voice + byFormat + leo + changes + limits;
  tips(el);
}

/** One tooltip for every dot: on hover and on keyboard focus. */
function tips(root) {
  const tip = document.createElement("div");
  tip.className = "dr-tip";
  tip.hidden = true;
  document.body.append(tip);
  const show = (e) => {
    const dot = e.target.closest(".dr-dot");
    if (!dot) return;
    tip.textContent = dot.dataset.tip;
    tip.hidden = false;
    const b = dot.getBoundingClientRect();
    tip.style.left = `${b.left + b.width / 2 + window.scrollX}px`;
    tip.style.top = `${b.top + window.scrollY - 8}px`;
  };
  const hide = () => { tip.hidden = true; };
  root.addEventListener("mouseover", show);
  root.addEventListener("focusin", show);
  root.addEventListener("mouseout", (e) => { if (e.target.closest(".dr-dot")) hide(); });
  root.addEventListener("focusout", hide);
}
