// Every word on the page lives here. Change text here, not in the other files.
// COPY is the English page; LANG holds the few words shown on a family member's phone, in their language.

export const COPY = {
  brand: "CareCircle",
  nav: [["How it works", "#demo"], ["Safety", "#safety"], ["Families", "#demo"]],
  navCta: "Request a demo",
  eyebrow: "Family care, with an AI helper",
  headline: "Stay close to family, even on your busiest day.",
  lead: "Saathi turns what you share into something your parents and children understand at a glance, " +
    "holds back scams before they reach them, and calls to check in when you can't.",
  ctaWatch: "Watch it work", ctaSafety: "How we keep it safe",
  metrics: (m) => [
    [m ? `${(m.cost_per_item_usd * 100).toFixed(1)}¢` : "—", "model cost per shared item"],
    [m ? `${(m.cost_per_call_usd * 100).toFixed(1)}¢` : "—", "per daily check-in call"],
    ["3", "languages: Hindi, Japanese, English"],
    ["2", "countries: India and Japan"],
  ],
  metricsNote: "Measured in this demo on Azure OpenAI gpt-5-mini (text logic; voice not included).",
  glanceTitle: "Today at a glance", glanceFor: (who) => `Your chat with ${who}`,
  glance: {
    call: (who) => `Daily check-in with ${who}`, deadline: "Next deadline", scam: "Scams held back",
    scamCount: (n) => (n === 1 ? "1 message stopped this week" : `${n} messages stopped this week`),
  },

  demoEyebrow: "Product walkthrough", demoTitle: "See Saathi at work, with real outputs",
  demoLead: "Every screen below replays what the pipeline produced for two synthetic families: one in India, one in Japan.",
  controls: { play: "Play", pause: "Pause", replay: "Replay" },
  caregiverLabel: (caregiver) => `${caregiver}'s phone`,
  parentLabel: (who) => `${who}'s phone`,
  liveMirror: "Live mirror",
  saathiHelping: "Saathi is helping in this chat",
  stepCount: (i, n) => `Step ${i} of ${n}`,
  note: (missing) => (missing.length ? `Not generated yet: ${missing.join(", ")}. Run carecircle all to add them.` : ""),

  panel: { name: "Saathi", role: "AI helper", idle: "Ready", working: "Working", done: "Done", result: "Result" },
  preview: (who) => `Preview · what ${who} will see`, approve: "Approve and send", edit: "Edit", sent: "Sent",
  heldBack: (who) => `Held back from ${who}`,
  heldBackText: "This looks like a scam, so it wasn't forwarded. A short safety note was sent instead.",
  scamTitle: "Possible scam", scamAction: (who) => `Not forwarded to ${who}`,
  dateFound: "Deadline found", reminderSet: (days) => `Reminders ${days} day(s) before`,
  lockTitle: "Date waiting for your OK",
  lockText: (title, who) => `In ${who}'s chat, Saathi wasn't sure about the date for “${title}”, so it isn't in any calendar yet.`,
  checkin: (status) => `Today's check-in · ${status[0].toUpperCase()}${status.slice(1)}`,
  callNow: "Call now", fullReport: "Full report",
  liveView: (who) => `Live view · ${who}'s screen`,
  callStatus: {
    green: ["Green · all well", "Nothing needs your attention today."],
    amber: ["Amber · check in today", "Something needs attention, but it isn't urgent."],
    red: ["Red · call now", "Saathi has already alerted you by push and SMS."],
    rule: (n) => `Set by rules from ${n} recorded event${n === 1 ? "" : "s"}, not by the model's summary.`,
  },
  events: {
    record_checkin: (a) => ["checklist", "Check-in recorded", [a.mood && `Mood: ${a.mood}`, a.sleep && `Sleep: ${a.sleep}`].filter(Boolean).join(" · ")],
    flag_concern: (a) => ["shield-alert", `Concern flagged · ${cap(a.severity)}`, a.reason || ""],
    request_food_order: (a) => ["food", "Food order prepared", `${a.restaurant || "Saved restaurant"} · waiting for your approval`],
    end_call: () => ["phone", "Call ended", ""],
  },

  // The steps listed in Saathi's panel for each flow ({cg} caregiver, {who} recipient, {lang} their language).
  stages: {
    share: (n) => [`Received from ${n.cg}`, "Reading and simplifying", "Waiting for your approval", `Delivered to ${n.who}`, `Read aloud in ${n.lang}`],
    scam: (n) => [`Received from ${n.cg}`, "Checking for scam signs", "Held back", `Safety note sent to ${n.who}`],
    deadline: (n) => [`Received from ${n.cg}`, "Finding deadlines", `Added to ${n.who}'s calendar`, "Reminder set"],
    deadlineHeld: "Waiting for your OK",
    call: (n) => [`Calling ${n.who}`, "Talking together", "Recording what was learned", "Setting today's status", `Reporting to ${n.cg}`],
    mirror: (n) => [`${n.who} opens the card`, `Mirroring to ${n.cg}`, `${n.who} plays the voice note`],
  },

  // One line under the stage for each step.
  captions: {
    shareSent: ({ cg, who }) => `${cg} shares something with ${who}.`,
    shareRead: () => "Saathi reads it: the text, the pictures and the video frames, and checks the facts.",
    shareBuild: ({ lang }) => `It writes a short picture card in ${lang}.`,
    shareApprove: ({ cg }) => `${cg} checks the English preview and approves it.`,
    shareLand: ({ who }) => `The card reaches ${who}'s phone in large, simple type.`,
    shareVoice: ({ lang }) => `A voice note reads it aloud in ${lang}.`,
    scamSent: ({ cg }) => `${cg} forwards a message that came in.`,
    scamCheck: () => "Saathi finds the warning signs: urgency, secrecy and a request for money.",
    scamSafety: ({ who }) => `${who} gets a short safety note instead of the message.`,
    scamHeld: ({ cg }) => `${cg} sees why it was held back.`,
    dateSent: ({ cg }) => `${cg} shares a notice with a deadline.`,
    dateFind: () => "Saathi finds the deadline in the text.",
    dateCalendar: ({ who }) => `It goes into ${who}'s calendar.`,
    dateRemind: () => "A reminder rings before it's too late.",
    dateLock: ({ cg }) => `A date Saathi wasn't sure about waits for ${cg}. Dates are never changed automatically.`,
    callRing: ({ who, cg }) => `${cg} is busy, so Saathi calls ${who}.`,
    callTalk: () => "Saathi asks about medicines, meals, pain, and whether they've talked to anyone.",
    callRecord: () => "What Saathi learns is recorded as structured events, not just words.",
    callStatus: () => "Today's colour is worked out by code from those events, not by the model.",
    callReport: ({ cg }) => `${cg} gets the report, and an alert if something is wrong.`,
    mirrorOpen: ({ who }) => `${who} opens the card.`,
    mirrorSee: ({ cg }) => `${cg} sees exactly what they see, live.`,
    mirrorVoice: ({ who }) => `${who} plays the voice note, and the mirror follows.`,
  },

  safetyEyebrow: "Safety by design", safetyTitle: "Built so families can trust it",
  safetyLead: "The rules that matter most are enforced in code and tested, not left to the model.",
  safety: [
    ["lock", "Dates are never guessed", "If Saathi isn't sure about a date or time, it waits for your OK. It never moves one on its own."],
    ["activity", "Status is set by rules", "Red, amber or green comes from what was recorded on the call, worked out by code, not by a summary."],
    ["send", "You approve first", "Every card, voice note and reminder is previewed before it reaches your parents or children."],
    ["shield", "Scams are held back", "Messages asking for money, OTPs or secrecy never reach them. They get a short safety note instead."],
  ],
  foot: "Synthetic demo data. No real people, phone numbers or health records.",
};

const cap = (s) => (s ? `${String(s)[0].toUpperCase()}${String(s).slice(1).toLowerCase()}` : "");

export const FLOW_LABELS = {
  share: ["send", "Share and simplify"],
  scam: ["shield", "Scam held back"],
  deadline: ["calendar", "Deadline to reminder"],
  call: ["phone-call", "Daily check-in call"],
  mirror: ["eye", "See what they see"],
};

export const LANG = {
  Hindi: { helping: "Saathi आपकी मदद कर रही है", listen: "सुनिए", careful: "संभावित धोखा — ध्यान दें",
    remind: "याद दिलाऊँगी", calling: "Saathi का कॉल", ended: "कॉल समाप्त", by: (d) => `${d} तक`, label: "हिन्दी" },
  Japanese: { helping: "Saathiがお手伝いしています", listen: "聞く", careful: "詐欺に注意してください",
    remind: "前もってお知らせします", calling: "Saathiから電話", ended: "通話終了", by: (d) => `${d}まで`, label: "日本語" },
  English: { helping: "Saathi is helping", listen: "Listen", careful: "This could be a scam",
    remind: "I'll remind you", calling: "Saathi calling", ended: "Call ended", by: (d) => `by ${d}`, label: "English" },
};

export const lang = (language) => LANG[language] || LANG.English;

const HINDI_MONTHS = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"];
const EN_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
  "November", "December"];

/** "2026-11-20" -> "20 नवंबर" / "11月20日" / "20 November" (same rules as render/i18n.py); other text as written. */
export function formatDay(iso, language) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
  if (!match) return iso || "";
  const m = Number(match[2]), d = Number(match[3]);
  if (language === "Hindi") return `${d} ${HINDI_MONTHS[m - 1]}`;
  if (language === "Japanese") return `${m}月${d}日`;
  return `${d} ${EN_MONTHS[m - 1]}`;
}
