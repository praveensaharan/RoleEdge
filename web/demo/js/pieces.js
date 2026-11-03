// Builders for everything drawn on the phones and in Saathi's panel. Each returns a DOM node; timing lives in stage.js.
// Story text always goes in through el() / textContent, never as HTML (rule S9).

import { COPY, formatDay, lang } from "./copy.js";
import { el } from "./dom.js";
import { icon, logoMark } from "./icons.js";

const initial = (name) => [...(name || "?")][0];

// ---- phone chrome
export function statusBar(time = "9:41") {
  const signal = el("span", "sig", ...[4, 6, 8, 10].map((h) => { const bar = el("i"); bar.style.height = `${h}px`; return bar; }));
  return el("div", "sbar", time, el("span", "island"), el("span", "right", signal, el("span", "bat", el("i"))));
}

export function chatHead({ name, sub, actions = [] }) {
  return el("div", "chat-head", el("div", "av", initial(name)), el("div", "", el("div", "n", name), el("div", "s", sub)),
    el("div", "acts", ...actions.map((a) => icon(a, 18))));
}

// ---- caregiver side
export const shared = (kind, label, text) =>
  el("div", "b me", el("div", "attach", el("span", "thumb", icon(kind, 18)), el("b", "", label)), text);

export function preview(who, text) {
  const approve = el("button", "mini-btn p", COPY.approve);
  const box = el("div", "box", el("div", "h", icon("eye", 14), COPY.preview(who)), el("div", "", text),
    el("div", "row-btns", approve, el("button", "mini-btn", COPY.edit)));
  return { box, approve };
}

export const sent = () => el("div", "sent", icon("tick", 14, 2.4), COPY.sent);
export const heldBack = (who) => el("div", "box alert", el("div", "h", icon("shield-alert", 14), COPY.heldBack(who)), COPY.heldBackText);
export const lockNote = (title, who) => el("div", "box dashed", el("div", "h", icon("lock", 14), COPY.lockTitle), COPY.lockText(title, who));

export function statusCard(call) {
  const { report } = call;
  return el("div", "status-card", el("div", "h", el("span", `dot ${call.status}`), COPY.checkin(call.status)),
    el("div", "", report.headline),
    report.social_contact ? el("div", "soc", icon("family", 16), el("span", "", report.social_contact)) : null,
    el("div", "row-btns", el("button", "mini-btn p", COPY.callNow), el("button", "mini-btn", COPY.fullReport)));
}

export function mirrorBox(who) {
  const view = el("div", "view");
  return { node: el("div", "mirror", el("div", "h", icon("eye", 14), COPY.liveView(who)), view), view };
}

// ---- recipient side
export function cardImage(src, alt) {
  const img = el("img", "card-img");
  img.src = src;
  img.alt = alt;
  return img;
}

export function voiceNote(language) {
  const wave = el("div", "wave");
  for (let i = 0; i < 28; i += 1) { const bar = el("i"); bar.style.animationDelay = `${(i * 137) % 900}ms`; wave.append(bar); }
  return el("div", "voice", el("span", "play", icon("play", 14, 2)), el("span", "lbl", lang(language).listen), wave, el("span", "len", "0:25"));
}

export const voiceText = () => el("div", "voice-text");
export const safetyNote = (language, advice) => el("div", "safety-note", icon("warning", 20), el("div", "", el("b", "", lang(language).careful), advice));

export function calendarCard(action, language) {
  const when = formatDay(action.due_date, language) + (action.due_time ? ` · ${action.due_time}` : "");
  return el("div", "cal", el("span", "ic", icon("calendar", 18)),
    el("div", "", el("b", "", action.title_local), el("small", "", `${lang(language).by(when)} · ${lang(language).remind}`)),
    el("span", "bell", icon("bell", 18)));
}

export function callScreen(language) {
  const ring = el("div", "ring", logoMark(40)), sub = el("div", "sub", lang(language).calling), lines = el("div", "lines");
  return { screen: el("div", "call", ring, el("div", "who", "Saathi"), sub, lines), sub, lines };
}

export function callLine(who, text, fromParent) {
  const body = el("span", "", text);
  return { node: el("div", fromParent ? "line parent" : "line", el("span", "k", who), body), body };
}

// ---- Saathi's panel
export function panelFrame() {
  const state = el("span", "state", COPY.panel.idle), status = el("p", "panel-status"), bar = el("span");
  const steps = el("ol", "steps"), result = el("div", "result", el("div", "result-label", COPY.panel.result));
  const head = el("div", "panel-head", el("span", "mark", logoMark(26)),
    el("div", "", el("b", "", COPY.panel.name), el("small", "", COPY.panel.role)), state);
  return { nodes: [head, status, el("div", "panel-bar", bar), steps, result], state, status, bar, steps, result };
}

export const stepItem = (label) => el("li", "", el("span", "ind"), label);
export const travelPill = (kind, text) => el("div", "", icon(kind, 16), text);

export function miniCard(digest) {
  const card = el("div", digest.trust.verdict === "likely_scam_or_misleading" ? "mini-card warn" : "mini-card",
    el("div", "top", digest.illustration.headline));
  card.rows = digest.illustration.panels.slice(0, 4)
    .map((p) => el("div", "row", el("span", "ic", icon(p.icon, 16)), el("div", "", el("b", "", p.heading), p.caption)));
  return card;
}

export const notice = (kind, iconName, title, text) =>
  el("div", `notice ${kind}`, el("span", "ic", icon(iconName, 18)), el("div", "", el("b", "", title), text));

export function eventRow(event) {
  const describe = COPY.events[event.tool];
  if (!describe) return null;
  const [iconName, title, detail] = describe(event.args || {});
  const severity = event.tool === "flag_concern" ? String(event.args?.severity || "").toLowerCase() : "";
  return el("div", `event ${severity}`, el("span", "ic", icon(iconName, 16)), el("div", "", el("b", "", title), detail ? el("small", "", detail) : null));
}

export function statusBadge(status, eventCount) {
  const [title, text] = COPY.callStatus[status];
  return el("div", `badge ${status}`, el("span", `dot ${status}`), el("div", "", title, el("small", "", `${text} ${COPY.callStatus.rule(eventCount)}`)));
}
