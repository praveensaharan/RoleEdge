// The stage: the caregiver's phone, Saathi's panel and the recipient's phone. run(step) draws one step and resolves
// when its animation is done. To add a new kind of step, add one entry to RENDER (and a builder in pieces.js).
// Each reset() makes fresh containers (a "scene"), so a step still finishing from the previous flow only draws
// into the old, detached scene.

import { COPY, lang } from "./copy.js";
import { animate, el, enter, tap, travel, typeText, wait } from "./dom.js";
import { icon } from "./icons.js";
import * as P from "./pieces.js";

export function createStage({ caregiver, parent, panel, labels }) {
  let scene = null;

  function reset(family, who, { live = false, stages = [] } = {}) {
    const frame = P.panelFrame();
    scene = { family, who, frame, labels: stages, items: stages.map(P.stepItem), overlay: el("div"),
      feeds: { caregiver: el("div", "feed"), parent: el("div", "feed") }, call: null, mirror: null, events: 0 };
    frame.steps.replaceChildren(...scene.items);
    panel.replaceChildren(...frame.nodes);
    caregiver.replaceChildren(P.statusBar(), P.chatHead({ name: who.call_name, sub: COPY.saathiHelping,
      actions: live ? ["eye"] : ["phone", "video"] }), scene.feeds.caregiver);
    parent.replaceChildren(P.statusBar(), P.chatHead({ name: family.caregiver.name, sub: lang(who.language).helping,
      actions: ["phone", "video"] }), scene.feeds.parent, scene.overlay);
    labels.caregiver.textContent = COPY.caregiverLabel(family.caregiver.name);
    labels.parent.replaceChildren(COPY.parentLabel(who.call_name), live ? el("span", "live", COPY.liveMirror) : "");
  }

  function progress(c, stage) {
    c.frame.state.className = "state working";
    c.frame.state.textContent = COPY.panel.working;
    c.frame.status.textContent = `${c.labels[stage]}…`;
    c.items.forEach((item, i) => {
      const state = i < stage ? "done" : i === stage ? "active" : "";
      if (item.className !== state) item.firstElementChild.replaceChildren(state === "done" ? icon("tick", 12, 2.6) : "");
      item.className = state;
    });
    c.frame.bar.style.width = `${(stage / Math.max(1, c.items.length)) * 100}%`;
  }

  function finish() {
    const c = scene;
    c.items.forEach((item) => { if (item.className !== "done") item.firstElementChild.replaceChildren(icon("tick", 12, 2.6)); item.className = "done"; });
    c.frame.bar.style.width = "100%";
    c.frame.state.className = "state done";
    c.frame.state.textContent = COPY.panel.done;
    c.frame.status.textContent = c.labels[c.labels.length - 1];
  }

  const RENDER = { // each entry: (step, c) where c is the scene it belongs to
    shared: (s, c) => enter(c.feeds.caregiver, P.shared(s.kind, s.label, s.text), 4),
    send: (s, c) => travel(P.travelPill(s.kind, s.label), c.feeds.caregiver.lastElementChild, panel),
    "build-card": async (s, c) => {
      const card = P.miniCard(s.digest);
      await enter(c.frame.result, card, 3);
      for (const row of card.rows) { await enter(card, row, 9); await wait(220); }
    },
    approve: async (s, c) => {
      const { box, approve } = P.preview(c.who.call_name, s.text);
      await enter(c.feeds.caregiver, box, 3);
      await wait(700);
      await tap(approve);
      box.append(P.sent());
    },
    deliver: async (s, c) => {
      if (!s.quick) await travel(P.travelPill("send", s.label), panel, c.feeds.parent);
      await enter(c.feeds.parent, s.src ? P.cardImage(s.src, s.digest.regional.title) : P.miniCard(s.digest), 2);
    },
    voice: async (s, c) => {
      const bar = P.voiceNote(c.who.language), text = P.voiceText();
      await enter(c.feeds.parent, bar, 3);
      bar.classList.add("playing");
      await enter(c.feeds.parent, text, 3);
      await typeText(text, s.text.length > 160 ? `${s.text.slice(0, 160)}…` : s.text, 16);
    },
    "scam-check": async (s, c) => {
      await travel(P.travelPill(s.kind, s.label), c.feeds.caregiver.lastElementChild, panel);
      await enter(c.frame.result, P.notice("danger", "shield-alert", COPY.scamTitle, s.reason), 4);
      await enter(c.frame.result, P.notice("", "cross", COPY.scamAction(c.who.call_name), ""), 4);
    },
    "safety-note": (s, c) => enter(c.feeds.parent, P.safetyNote(c.who.language, s.advice), 3),
    "held-note": (s, c) => enter(c.feeds.caregiver, P.heldBack(c.who.call_name), 3),
    "date-found": async (s, c) => {
      await travel(P.travelPill(s.kind, s.label), c.feeds.caregiver.lastElementChild, panel);
      await enter(c.frame.result, P.notice("date", "calendar", COPY.dateFound, s.text), 4);
    },
    calendar: async (s, c) => {
      await travel(P.travelPill("calendar", s.label), panel, c.feeds.parent);
      await enter(c.feeds.parent, P.calendarCard(s.action, c.who.language), 3);
    },
    reminder: async (s, c) => {
      [...c.feeds.parent.querySelectorAll(".cal")].pop()?.classList.add("ringing");
      await wait(1400);
    },
    lock: (s, c) => enter(c.feeds.caregiver, P.lockNote(s.title, s.who), 3),
    ring: async (s, c) => {
      c.call = P.callScreen(c.who.language);
      c.overlay.append(c.call.screen);
      await animate(c.call.screen, [{ transform: "translateY(100%)" }, { transform: "none" }], { duration: 520 });
      await wait(1500);
      c.call.screen.classList.add("answered");
    },
    line: async (s, c) => {
      const { node, body } = P.callLine(s.who, s.text, s.fromParent);
      await enter(c.call.lines, node, 6);
      await typeText(body, s.text, 9);
    },
    event: (s, c) => { c.events += 1; const row = P.eventRow(s.event); return row ? enter(c.frame.result, row, 7) : null; },
    status: (s, c) => enter(c.frame.result, P.statusBadge(s.status, c.events), 8),
    report: async (s, c) => {
      if (c.call) { c.call.screen.classList.add("ended"); c.call.sub.textContent = lang(c.who.language).ended; }
      await enter(c.feeds.caregiver, P.statusCard(s.call), 3);
    },
    tap: (s, c) => tap(c.feeds.parent.querySelector(s.target === "voice" ? ".voice" : ".card-img, .mini-card")),
    mirror: async (s, c) => {
      if (!c.mirror) { c.mirror = P.mirrorBox(c.who.call_name); await enter(c.feeds.caregiver, c.mirror.node, 2); }
      c.mirror.view.replaceChildren(parent.cloneNode(true));
    },
  };

  async function run(step) {
    const c = scene;
    if (step.stage != null) progress(c, step.stage);
    await (RENDER[step.do] || (() => {}))(step, c);
  }

  return { reset, run, finish };
}
