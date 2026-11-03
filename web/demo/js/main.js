// Entry point: load icons and the story, draw the page, and wire the family switch, flow tabs and controls.
// URL options for screenshots and links: ?family=japan&flow=call&end=1 (jump to the end of a flow).

import { COPY, formatDay, lang } from "./copy.js";
import { el, setInstant } from "./dom.js";
import { FLOWS } from "./flows.js";
import { icon, loadIcons, logoMark } from "./icons.js";
import { createPlayer } from "./player.js";
import { createStage } from "./stage.js";
import { familyById, loadStory } from "./story.js";

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
let family = null, flowId = null, total = 0;

const stage = createStage({ caregiver: $("caregiverPhone"), parent: $("parentPhone"), panel: $("panel"),
  labels: { caregiver: $("caregiverLabel"), parent: $("parentLabel") } });
const player = createPlayer({ stage, onStep: showStep, onDone: finished });

function drawPage(story) {
  $("logo").replaceChildren(logoMark(30), COPY.brand);
  $("footLogo").replaceChildren(logoMark(24), COPY.brand);
  $("navLinks").replaceChildren(...COPY.nav.map(([text, href]) => { const a = el("a", "", text); a.href = href; return a; }));
  $("navCta").textContent = COPY.navCta;
  $("eyebrow").textContent = COPY.eyebrow;
  $("headline").textContent = COPY.headline;
  $("lead").textContent = COPY.lead;
  $("ctaWatch").replaceChildren(icon("play", 16, 2), COPY.ctaWatch);
  $("ctaSafety").textContent = COPY.ctaSafety;
  $("metrics").replaceChildren(...COPY.metrics(story.metrics).map(([value, text]) => el("div", "", el("dt", "", value), el("dd", "", text))),
    el("div", "metrics-note", COPY.metricsNote));
  for (const key of ["demoEyebrow", "demoTitle", "demoLead", "safetyEyebrow", "safetyTitle", "safetyLead"]) $(key).textContent = COPY[key];
  $("safetyCards").replaceChildren(...COPY.safety.map(([name, title, text]) =>
    el("div", "s-card", el("span", "ic", icon(name, 22)), el("h3", "", title), el("p", "", text))));
  $("footNote").textContent = COPY.foot;
  $("replay").replaceChildren(icon("replay", 16), COPY.controls.replay);
}

const RANK = { red: 0, amber: 1, green: 2 };

/** The hero's "today at a glance" card, built from the selected family's real outputs. */
function drawGlance() {
  const parent = family.parent, rows = [];
  const call = [...family.calls].sort((a, b) => RANK[a.status] - RANK[b.status])[0];
  if (call) rows.push(["phone-call", COPY.glance.call(parent.call_name), call.report.headline, call.status]);
  const parentKeys = family.recipients.filter((r) => r.role === "parent").map((r) => r.key);
  const due = family.items.filter((i) => !i.scam && parentKeys.includes(i.recipient)).flatMap((i) => i.digest.actions.filter((a, k) => a.add_to_calendar
    && /^\d{4}-\d{2}-\d{2}$/.test(a.due_date || "") && !i.held_actions.includes(k))).sort((a, b) => a.due_date.localeCompare(b.due_date))[0];
  if (due) rows.push(["calendar", COPY.glance.deadline, `${formatDay(due.due_date, "English")} · ${due.title}`]);
  const scams = family.items.filter((i) => i.scam).length;
  if (scams) rows.push(["shield", COPY.glance.scam, COPY.glance.scamCount(scams)]);
  $("glance").replaceChildren(el("div", "glance-head", el("b", "", COPY.glanceTitle), el("span", "", COPY.glanceFor(parent.call_name))),
    ...rows.map(([name, title, text, status]) => el("div", "glance-row", el("span", "ic", icon(name, 20)),
      el("div", "t", el("b", "", title), el("small", "", text)), status ? el("span", `dot ${status}`) : null)));
}

function showStep(index, step) {
  $("progressBar").style.width = `${((index + 1) / total) * 100}%`;
  $("stepCount").textContent = COPY.stepCount(index + 1, total);
  if (step.caption) $("caption").textContent = step.caption;
}

function finished() {
  stage.finish();
  setInstant(false);
  setPlayLabel();
}

function setPlayLabel() {
  const playing = player.isPlaying();
  $("play").replaceChildren(icon(playing ? "pause" : "play", 16, 2), playing ? COPY.controls.pause : COPY.controls.play);
}

function selectFamily(id) {
  family = familyById(id);
  [...$("familySwitch").children].forEach((b) => b.setAttribute("aria-selected", String(b.dataset.id === family.id)));
  const available = FLOWS.filter((flow) => flow.build(family));
  $("flowTabs").replaceChildren(...available.map((flow) => {
    const tab = el("button", "tab", icon(flow.icon, 16), flow.label);
    tab.dataset.id = flow.id;
    tab.addEventListener("click", () => selectFlow(flow.id));
    return tab;
  }));
  $("note").textContent = COPY.note(family.missing);
  drawGlance();
  const wanted = available.find((f) => f.id === (params.get("flow") || flowId)) || available[0];
  if (wanted) selectFlow(wanted.id);
}

function selectFlow(id) {
  flowId = id;
  [...$("flowTabs").children].forEach((t) => t.setAttribute("aria-pressed", String(t.dataset.id === id)));
  const built = FLOWS.find((f) => f.id === id).build(family);
  stage.reset(family, built.recipient, { live: built.live, stages: built.stages });
  total = built.steps.length;
  $("progressBar").style.width = "0";
  $("stepCount").textContent = COPY.stepCount(0, total);
  $("caption").textContent = "";
  player.load(built.steps);
  setInstant(params.get("end") === "1");
  player.play();
  setPlayLabel();
}

async function main() {
  let story;
  try {
    await loadIcons();
    story = await loadStory();
  } catch (error) {
    $("caption").textContent = error.message;
    return;
  }
  drawPage(story);
  $("familySwitch").replaceChildren(...story.families.map((f) => {
    const button = el("button", "", f.label, el("small", "", lang(f.parent.language).label));
    button.dataset.id = f.id;
    button.setAttribute("role", "tab");
    button.addEventListener("click", () => { params.delete("flow"); params.delete("end"); selectFamily(f.id); });
    return button;
  }));
  $("play").addEventListener("click", () => {
    if (player.isDone()) selectFlow(flowId);
    else if (player.isPlaying()) player.pause();
    else player.play();
    setPlayLabel();
  });
  $("replay").addEventListener("click", () => { params.delete("end"); selectFlow(flowId); });
  selectFamily(params.get("family") || story.families[0].id);
}

main();
