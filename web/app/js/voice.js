// A more natural browser voice: the best voice the device has, speaking whole sentences with real pauses between
// them, instead of one flat utterance. Used by the read-aloud moments and by both avatars on her phone.
//
// * Voice: the device's neural/natural voices first (Edge "… Online (Natural)", Google, Apple "Premium/Enhanced"),
//   matching the speaker when it can (Maya and Okaasan's family voices are women's, Kenji's a man's).
// * Sentences, not fragments: a voice gives a sentence its own melody (a comma rises and runs on, the end falls), so
//   each sentence is said whole. Cutting at every comma, as before, made each piece end like a full stop: choppy.
//   Only the opening "Mom," stands alone, and a very long sentence is split at a comma near its middle (Chrome's
//   online voices can stop partway through a long one).
// * Pauses: a beat after "Mom,", a breath between sentences, a longer one after a question (time to think) and
//   between paragraphs; Japanese 。！？ the same way (、 stays inside, like a comma).
// * Expression: the words carry it (the makers write how people talk); the voice adds a little: an exclamation a
//   touch quicker, the last sentence a touch slower so it settles. Pitch is left alone on neural voices, which
//   already rise for a question and sound strained when shifted; a basic voice gets a small lift for a question.

const NATURAL = /natural|neural|online|premium|enhanced|siri|google|wavenet|studio/i;
const FEMALE = /female|woman|samantha|aria|jenny|ava|allison|susan|zira|karen|moira|tessa|serena|kyoko|nanami|haruka|ayumi|o-ren|google.*(us|uk) english/i;
const MALE = /male|man\b|guy|davis|tony|daniel|alex|fred|aaron|keita|ichiro|otoya|ryan|eric|christopher|brian/i;
const PAUSE = { address: 260, sentence: 380, exclaim: 380, question: 560, dash: 330, soft: 140, paragraph: 700 }; // ms
const LONGEST = 220; // characters: a longer sentence is split at a comma near its middle

let cache = null;
const voices = () => (cache && cache.length ? cache : (cache = "speechSynthesis" in window ? speechSynthesis.getVoices() : []));
if ("speechSynthesis" in window) speechSynthesis.addEventListener?.("voiceschanged", () => { cache = null; });

/** The most natural voice for ``lang``; ``gender`` ("female" | "male" | "") is a preference, not a rule; ``pick`` 1
 *  takes the next best one (the assistant's voice, so it never sounds like the family member). */
export function bestVoice(lang = "en-US", gender = "", pick = 0) {
  const base = lang.slice(0, 2).toLowerCase();
  const list = voices().filter((v) => v.lang.toLowerCase().replace("_", "-").startsWith(base));
  if (!list.length) return null;
  const score = (v) => (NATURAL.test(v.name) ? 4 : 0) + (v.lang.toLowerCase() === lang.toLowerCase() ? 2 : 0)
    + (gender === "female" && FEMALE.test(v.name) ? 3 : 0) + (gender === "male" && MALE.test(v.name) && !FEMALE.test(v.name) ? 3 : 0)
    + (v.localService ? 0.5 : 0);
  const ranked = [...list].sort((a, b) => score(b) - score(a));
  return ranked[Math.min(pick, ranked.length - 1)];
}

/** "female" or "male" from how a family member is described ("her daughter", "his son"), else "". */
export function genderOf(relation = "") {
  return /daughter|mother|wife|sister|grandmother|aunt/i.test(relation) ? "female" : /\bson\b|father|husband|brother|grandfather|uncle/i.test(relation) ? "male" : "";
}

const ADDRESS = /^(mom|mum|mommy|mama|dad|papa|grandma|grandpa|granny|nana|お母さん|おかあさん|おばあちゃん|おじいちゃん|お父さん)[,、]/i;

/** The text as phrases: {text, start (its offset in the whole text), pause (ms after it), kind}. Phrases are whole
 *  sentences; a break between digits ("10:30", "3.5") or after "e.g." / "Dr." is not a sentence end. */
export function phrases(text) {
  const END = /[.!?。！？…\n]/; // not a dash: a voice reads "the tea — hot — is ready" as one sentence, better than three
  const out = [];
  let from = 0;
  const push = (to) => {
    const raw = text.slice(from, to);
    const piece = raw.trim();
    if (piece) {
      const at = from + raw.indexOf(piece);
      const paragraph = (raw.slice(at - from + piece.length) + text.slice(to).match(/^\s*/)[0]).includes("\n");
      const address = !out.length && piece.match(ADDRESS);
      if (address && piece.length > address[0].length + 1) { // "Mom, the soup is ready." -> "Mom," + the sentence
        out.push({ text: address[0], start: at, pause: PAUSE.address, kind: "address" });
        const rest = piece.slice(address[0].length);
        const trimmed = rest.trimStart();
        split(trimmed, at + address[0].length + (rest.length - trimmed.length), paragraph);
      } else split(piece, at, paragraph);
    }
    from = to;
  };
  const split = (piece, at, paragraph) => { // a very long sentence: at the comma nearest its middle, recursively
    if (piece.length > LONGEST) {
      const commas = [...piece.matchAll(/[,，、;；:：]\s*/g)].map((m) => m.index + 1).filter((i) => i > 20 && i < piece.length - 20);
      if (commas.length) {
        const cut = commas.reduce((a, b) => (Math.abs(b - piece.length / 2) < Math.abs(a - piece.length / 2) ? b : a));
        const head = piece.slice(0, cut).trimEnd();
        out.push({ text: head, start: at, pause: PAUSE.soft, kind: "soft" });
        const rest = piece.slice(cut);
        const trimmed = rest.trimStart();
        return split(trimmed, at + cut + (rest.length - trimmed.length), paragraph);
      }
    }
    const end = piece.replace(/["'”’)」』]+$/, "").slice(-1);
    const kind = /[?？]/.test(end) ? "question" : /[!！]/.test(end) ? "exclaim" : end === "—" || end === "…" ? "dash" : "sentence";
    out.push({ text: piece, start: at, pause: paragraph ? PAUSE.paragraph : PAUSE[kind], kind });
  };
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (!END.test(ch)) continue;
    const between = /\d/.test(text[i - 1] || "") && /\d/.test(text[i + 1] || "") && ch === ".";
    const abbreviation = ch === "." && (/(^|[\s.])[a-z]$/i.test(text.slice(Math.max(0, i - 2), i)) // "e.g." "i.e." "U.S."
      || /\b(dr|mr|mrs|ms|st|jr|sr|no|vs|approx|etc)$/i.test(text.slice(Math.max(0, i - 7), i))); // "Dr. Patel"
    const midSentence = ch === "." && /^\.?\s*[a-z]/.test(text.slice(i + 1, i + 4)) && text[i + 1] !== "."; // "3 p.m. today"
    if (between || abbreviation || midSentence) continue;
    let j = i + 1;
    while (j < text.length && /[.!?。！？…"'”’)」』]/.test(text[j])) j++; // "?!", "...", a closing quote stay with it
    push(j);
    i = j - 1;
  }
  push(text.length);
  if (out.length) out[out.length - 1].pause = 0;
  return out;
}

let run = 0;
let muted = false; // the caregiver's mirror of her screen: it shows everything, but only her phone speaks
/** Show speech without sound (the mirror): timing, captions and the avatar's mouth still follow the words. */
export function mute(on = true) { muted = on; }
let failing = new Set(); // voices that failed this session (a network voice offline): the default voice speaks instead
const alive = new Set(); // Chrome drops an utterance it can't see referenced, and then its "end" never comes

/** Stop whatever is being said. */
export function hush() {
  run += 1;
  if (!("speechSynthesis" in window)) return;
  if (speechSynthesis.speaking || speechSynthesis.pending) speechSynthesis.cancel();
}

/**
 * Speak ``text`` phrase by phrase. ``onState({index, phraseStart, phraseLength, startedAt, rate, talking})`` lets an
 * avatar move its mouth with the words and rest it in the pauses; ``onBoundary(index)`` reports word starts.
 * Resolves true when everything was said, false if it was stopped or the browser can't speak.
 *
 * Browser quirks handled: speaking right after cancel() is dropped in Chrome (a short wait first); an utterance must
 * stay referenced or its end never fires; a network voice can fail ("synthesis-failed"), so that phrase is said again
 * with the default voice and the failing voice isn't used again; speech can get stuck paused (resume()); and a phrase
 * whose end never comes is moved past after a generous time, so the rest is still said.
 */
export function speakNaturally(text, { lang = "en-US", rate = 0.92, gender = "", pick = 0, onState = () => {}, onBoundary = () => {} } = {}) {
  if (!text?.trim()) return Promise.resolve(false);
  if (muted || !("speechSynthesis" in window)) return silently(text, { lang, rate, onState });
  const wasBusy = speechSynthesis.speaking || speechSynthesis.pending;
  hush();
  const token = ++run;
  const first = bestVoice(lang, gender, pick);
  let parts = phrases(text);
  const ja = lang.startsWith("ja");
  if (first && !first.localService) {
    // An online voice fetches each phrase, which adds its own gap: keep "Mom," with its sentence (the voice pauses
    // at the comma) and shorten our pauses by that much.
    const merged = [];
    for (let k = 0; k < parts.length; k++) {
      const p = parts[k], q = parts[k + 1];
      if (p.kind === "address" && q) { merged.push({ ...q, text: text.slice(p.start, q.start + q.text.length), start: p.start }); k++; }
      else merged.push(p);
    }
    parts = merged.map((p) => ({ ...p, pause: p.pause ? Math.max(80, p.pause - 200) : 0 }));
  }
  return new Promise((resolve) => {
    const say = (k, voice) => {
      if (token !== run) return resolve(false);
      if (k >= parts.length) { onState({ index: text.length, talking: false }); return resolve(true); }
      const p = parts[k];
      const last = k === parts.length - 1;
      const utter = new SpeechSynthesisUtterance(p.text);
      alive.add(utter);
      utter.lang = lang;
      if (voice && !failing.has(voice.name)) utter.voice = voice;
      utter.rate = Math.max(0.6, rate + (p.kind === "exclaim" ? 0.04 : 0) - (last && parts.length > 2 ? 0.04 : 0));
      const neural = NATURAL.test(utter.voice?.name || "");
      utter.pitch = neural || ja ? 1 : p.kind === "question" ? 1.08 : p.kind === "exclaim" ? 1.04 : 1;
      let settled = false;
      const watchdog = setTimeout(() => finish(), 4000 + p.text.length * 140 / utter.rate); // its end never came
      const finish = () => {
        if (settled) return;
        settled = true;
        clearTimeout(watchdog);
        alive.delete(utter);
        if (token !== run) return resolve(false);
        onState({ index: p.start + p.text.length, talking: false });
        setTimeout(() => say(k + 1, voice), p.pause);
      };
      utter.onstart = () => onState({ index: p.start, phraseStart: p.start, phraseLength: p.text.length, startedAt: performance.now(), rate: utter.rate, talking: true });
      utter.onboundary = (e) => { if (typeof e.charIndex === "number") onBoundary(p.start + e.charIndex); };
      utter.onend = finish;
      utter.onerror = (e) => {
        if (settled) return;
        if (e.error === "interrupted" || e.error === "canceled") { settled = true; clearTimeout(watchdog); alive.delete(utter); return resolve(false); }
        if (e.error === "not-allowed") { settled = true; clearTimeout(watchdog); alive.delete(utter); console.warn("speech needs a tap first"); return resolve(false); }
        if (utter.voice) { // this voice can't speak right now: say the phrase again with the default voice
          failing.add(utter.voice.name);
          settled = true; clearTimeout(watchdog); alive.delete(utter);
          return say(k, null);
        }
        finish();
      };
      if (speechSynthesis.paused) speechSynthesis.resume();
      speechSynthesis.speak(utter);
    };
    // Chrome drops a speak() that comes right after cancel(): wait a moment when something was being said
    setTimeout(() => say(0, first), wasBusy ? 120 : 0);
  });
}

/** The same rhythm with no sound: each phrase "said" at a reading pace, then its pause. */
function silently(text, { lang, rate, onState }) {
  hush();
  const token = ++run;
  const parts = phrases(text);
  const cps = (lang.startsWith("ja") ? 7.5 : 14) * rate;
  return new Promise((resolve) => {
    const next = (k) => {
      if (token !== run) return resolve(false);
      if (k >= parts.length) { onState({ index: text.length, talking: false }); return resolve(true); }
      const p = parts[k];
      onState({ index: p.start, phraseStart: p.start, phraseLength: p.text.length, startedAt: performance.now(), rate, talking: true });
      setTimeout(() => { if (token !== run) return resolve(false); onState({ index: p.start + p.text.length, talking: false }); setTimeout(() => next(k + 1), p.pause); },
        (p.text.length / cps) * 1000);
    };
    next(0);
  });
}
