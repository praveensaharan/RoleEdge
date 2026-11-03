// The five flows. Each turns one family's saved data into { recipient, stages, steps, live? } for player.js,
// or null when that family has nothing to show for it (its tab is then hidden).
//
// Editing guide
//   - A step is { do, stage, caption?, hold?, ...data }. `do` names a drawing function in stage.js (RENDER).
//   - `stage` is the index of the line in Saathi's panel that is active during the step (labels: COPY.stages).
//   - `hold` is how long to pause after the step (ms, default 1100). Words live in copy.js.

import { COPY, FLOW_LABELS, formatDay } from "./copy.js";
import { recipientOf } from "./story.js";

const C = COPY.captions;
const names = (family, who) => ({ cg: family.caregiver.name, who: who.call_name, lang: who.language });
const firstShareable = (family) => family.items.find((i) => !i.scam && i.media.card) || family.items.find((i) => !i.scam);
const label = (item) => item.input.split(" (")[0];
const short = (text, max) => (text.length > max ? `${text.slice(0, text.lastIndexOf(" ", max))}…` : text);
const kind = (item) => (/reel|video/i.test(item.input) ? "video" : /bill|photo/i.test(item.input) ? "bill"
  : /message|line/i.test(item.input) ? "chat" : "document");

function share(family) {
  const item = firstShareable(family);
  if (!item) return null;
  const who = recipientOf(family, item), n = names(family, who), d = item.digest;
  return { recipient: who, stages: COPY.stages.share(n), steps: [
    { do: "shared", stage: 0, kind: kind(item), label: label(item), text: d.one_line, caption: C.shareSent(n), hold: 700 },
    { do: "send", stage: 1, kind: kind(item), label: label(item), caption: C.shareRead(n), hold: 300 },
    { do: "build-card", stage: 1, digest: d, caption: C.shareBuild(n) },
    { do: "approve", stage: 2, text: short(d.simple_summary.join(" "), 220), caption: C.shareApprove(n) },
    { do: "deliver", stage: 3, src: item.media.card, digest: d, label: d.regional.title, caption: C.shareLand(n) },
    { do: "voice", stage: 4, text: item.voice_note, caption: C.shareVoice(n), hold: 1600 },
  ] };
}

function scam(family) {
  const item = family.items.find((i) => i.scam);
  if (!item) return null;
  const who = recipientOf(family, item), n = names(family, who), d = item.digest;
  return { recipient: who, stages: COPY.stages.scam(n), steps: [
    { do: "shared", stage: 0, kind: kind(item), label: label(item), text: d.one_line, caption: C.scamSent(n), hold: 700 },
    { do: "scam-check", stage: 1, kind: kind(item), label: label(item), reason: d.trust.reason, caption: C.scamCheck(n), hold: 1400 },
    { do: "held-note", stage: 2, caption: C.scamHeld(n), hold: 1100 },
    { do: "safety-note", stage: 3, advice: d.trust.advice_local, caption: C.scamSafety(n), hold: 1500 },
  ] };
}

function deadline(family) {
  const dated = family.items.flatMap((item) => item.digest.actions.map((action, index) => ({ item, action, index })))
    .filter(({ item, action }) => !item.scam && /^\d{4}-\d{2}-\d{2}$/.test(action.due_date || "") && action.add_to_calendar);
  const ok = dated.find(({ item, index }) => !item.held_actions.includes(index));
  const held = dated.find(({ item, index }) => item.held_actions.includes(index));
  const main = ok || held;
  if (!main) return null;
  const who = recipientOf(family, main.item), n = names(family, who), a = main.action;
  const when = formatDay(a.due_date, who.language) + (a.due_time ? ` · ${a.due_time}` : "");
  const stages = COPY.stages.deadline(n);
  const steps = [{ do: "shared", stage: 0, kind: kind(main.item), label: label(main.item), text: main.item.digest.one_line,
    caption: C.dateSent(n), hold: 700 }];
  if (ok) {
    steps.push(
      { do: "date-found", stage: 1, kind: kind(main.item), label: label(main.item), text: `${when} · ${a.title}`, caption: C.dateFind(n) },
      { do: "calendar", stage: 2, action: a, label: when, caption: C.dateCalendar(n) },
      { do: "reminder", stage: 3, caption: C.dateRemind(n), hold: 500 });
  }
  if (held) {
    stages.push(COPY.stages.deadlineHeld);
    steps.push({ do: "lock", stage: stages.length - 1, title: held.action.title, who: recipientOf(family, held.item).call_name,
      caption: C.dateLock(n), hold: 1800 });
  }
  return { recipient: who, stages, steps };
}

function call(family) {
  const order = { red: 0, amber: 1, green: 2 };
  const chosen = [...family.calls].sort((a, b) => order[a.status] - order[b.status])[0];
  if (!chosen) return null;
  const who = { call_name: family.parent.call_name, language: family.parent.language }, n = names(family, who);
  const lines = chosen.transcript.slice(1, 9).map(([speaker, text], i) => ({ do: "line", stage: 1, who: speaker, text,
    fromParent: speaker !== "Saathi", caption: i === 0 ? C.callTalk(n) : undefined, hold: 300 }));
  const events = chosen.events.filter((e) => e.tool !== "end_call").map((event, i) => ({ do: "event", stage: 2, event,
    caption: i === 0 ? C.callRecord(n) : undefined, hold: 400 }));
  return { recipient: who, stages: COPY.stages.call(n), steps: [
    { do: "ring", stage: 0, caption: C.callRing(n), hold: 200 },
    ...lines, ...events,
    { do: "status", stage: 3, status: chosen.status, caption: C.callStatus(n), hold: 1200 },
    { do: "report", stage: 4, call: chosen, caption: C.callReport(n), hold: 2000 },
  ] };
}

function mirror(family) {
  const item = firstShareable(family);
  if (!item) return null;
  const who = recipientOf(family, item), n = names(family, who), d = item.digest;
  return { recipient: who, live: true, stages: COPY.stages.mirror(n), steps: [
    { do: "deliver", stage: 0, src: item.media.card, digest: d, quick: true, caption: C.mirrorOpen(n), hold: 500 },
    { do: "tap", stage: 0, target: "card", hold: 200 },
    { do: "mirror", stage: 1, caption: C.mirrorSee(n), hold: 1400 },
    { do: "voice", stage: 2, text: item.voice_note, caption: C.mirrorVoice(n), hold: 300 },
    { do: "tap", stage: 2, target: "voice", hold: 200 },
    { do: "mirror", stage: 2, hold: 1800 },
  ] };
}

const BUILD = { share, scam, deadline, call, mirror };

export const FLOWS = Object.entries(FLOW_LABELS).map(([id, [icon, text]]) => ({ id, icon, label: text, build: BUILD[id] }));
