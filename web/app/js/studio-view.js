// The Studio moments as a person experiences them. For the parent: a note in the caregiver's words, slides at her own
// pace, a mind map, a gentle quiz, an animated video, a picture and a fridge card to keep. For a child: a picture
// story, a quiz game, a mind map, an animated video, a picture and questions to ask their grandparent. Both screens use these viewers (the phone full screen, the caregiver's
// Studio panel). Every viewer reports what the person does through onEvent(format, event, value), which becomes
// engagement the caregiver sees. Text is always escaped (rule S9).
import { esc } from "./common.js";
import { hush, speakNaturally } from "./voice.js";

let ICONS = {};
export async function loadIcons() {
  if (Object.keys(ICONS).length) return;
  ICONS = await fetch("/api/icons").then((r) => (r.ok ? r.json() : {})).catch(() => ({}));
}
export const icon = (name, size = 22) =>
  `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ICONS.info || ""}</svg>`;

// What each moment is called on the person's own screen; {caregiver} and {grandparent} are what they call them.
export const FORMAT_INFO = {
  note: { icon: "volume", en: "{caregiver}'s note", ja: "{caregiver}からのお話" },
  steps: { icon: "checklist", en: "Slides", ja: "スライド" },
  card: { icon: "document", en: "Fridge card", ja: "とっておくメモ" },
  askme: { icon: "question", en: "Quiz", ja: "おさらい" },
  story: { icon: "book", en: "Picture story", ja: "えほん" },
  quiz: { icon: "star", en: "Quiz game", ja: "クイズ" },
  map: { icon: "map", en: "Mind map", ja: "マインドマップ" },
  relay: { icon: "family", en: "Ask {grandparent}", ja: "{grandparent}にきいてみよう" },
  video: { icon: "video", en: "Animated video", ja: "どうが" },
  picture: { icon: "eye", en: "Picture", ja: "え" },
};
/** A moment's name in `lang`, with the person's own words for their caregiver and grandparent filled in. */
export function formatName(format, lang, names = {}) {
  const info = FORMAT_INFO[format];
  if (!info) return format;
  return (info[lang] || info.en).replace("{caregiver}", names.caregiver || "").replace("{grandparent}", names.grandparent || "");
}

const WORDS = {
  en: { play: "Play", pause: "Pause", read: "Read it to me", done: "All done", next: "Next", back: "Back", of: "{i} of {n}",
        end: "The end", remember: "Remember", stars: "{k} of {n} stars", right: "That's right", tryAgain: "Try another one",
        thanks: "Thank you. {caregiver} will see your answers.", ask: "Tap a question to ask", own: "Or hold the microphone below and ask your own.",
        sent: "Sent", print: "Print it", replay: "Watch again", tapBranch: "Tap a part to hear about it" },
  ja: { play: "再生", pause: "一時停止", read: "読みあげる", done: "おわり", next: "次へ", back: "戻る", of: "{n}つのうち{i}つめ",
        end: "おしまい", remember: "おぼえておくこと", stars: "{n}こ中{k}こ", right: "せいかい", tryAgain: "ほかのを えらんでね",
        thanks: "ありがとうございます。{caregiver}にも伝わります。", ask: "ききたいことを タップしてね", own: "したの マイクを おして、じぶんで きいても いいよ。",
        sent: "おくりました", print: "印刷する", replay: "もういちど見る", tapBranch: "タップすると よみあげます" },
};

// ---------------------------------------------------------------- the device voice (allowed at runtime: no model)

let speaking = null;
const canSpeak = () => "speechSynthesis" in window; // the voice list may still be loading: the default voice speaks
if ("speechSynthesis" in window) speechSynthesis.getVoices(); // starts loading the voice list (Chrome fills it lazily)
export function stopSpeech() { speaking = null; hush(); }
/** Read ``text`` aloud in natural phrases (voice.js): pauses at commas and sentence ends, a rising question. */
export function speak(text, { lang = "en-US", rate = 0.9, gender = "", onBoundary = () => {} } = {}) {
  const token = {};
  speaking = token;
  if (!canSpeak()) { // no device voice (an old browser, a headless one): just pace the text
    return new Promise((resolve) => setTimeout(() => resolve(speaking === token), Math.min(6000, 60 * text.length)));
  }
  return speakNaturally(text, { lang, rate, gender, onBoundary }).then((said) => said && speaking === token);
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------- mount

/** Draw `format` into `el`. opts: lang, names ({caregiver, grandparent}), onEvent(format, event, value),
 *  onAsk(question, index) for the relay (absent in a preview), printable (the caregiver's panel). */
export function mountViewer(el, format, output, opts = {}) {
  const o = { lang: "en", names: {}, gender: "", onEvent: () => {}, onAsk: null, printable: false, ...opts }; // gender: the caregiver's, for the voice
  o.words = WORDS[o.lang] || WORDS.en;
  o.speechLang = o.lang === "ja" ? "ja-JP" : "en-US";
  el.innerHTML = "";
  el.className = [...el.classList].filter((c) => !c.startsWith("viewer")).concat("viewer", `viewer-${format}`).join(" "); // keeps the host's own classes
  o.onEvent(format, "opened", 0);
  const make = { note, steps: pages, story: pages, card, askme: quiz, quiz, map: mindmap, relay, video, picture }[format];
  return make ? make(el, output, o, format) : { stop() {} };
}

const say = (template, values) => Object.entries(values).reduce((t, [k, v]) => t.replace(`{${k}}`, v), template);

// ---------------------------------------------------------------- note: the caregiver's own words, read aloud

function note(el, out, o) {
  let playing = false;
  let at = 0;
  const who = o.names.caregiver || "";
  el.innerHTML = `<div class="note-head"><span class="av">${esc(who.slice(0, 1))}</span><div><b>${esc(out.title)}</b><small>${esc(formatName("note", o.lang, o.names))}</small></div></div>
    <ol class="note-lines">${out.lines.map((l, k) => `<li data-k="${k}">${esc(l)}</li>`).join("")}</ol>
    ${out.question ? `<div class="note-q">${icon("chat", 20)}<span>${esc(out.question)}</span></div>` : ""}
    <button type="button" class="big-play" aria-label="${esc(o.words.play)}">${icon("play", 30)}</button>`;
  const btn = el.querySelector(".big-play");
  const lines = [...out.lines, ...(out.question ? [out.question] : [])];
  const setUi = () => {
    el.classList.toggle("playing", playing);
    btn.innerHTML = icon(playing ? "pause" : "play", 30);
    btn.setAttribute("aria-label", playing ? o.words.pause : o.words.play);
    el.querySelectorAll(".note-lines li").forEach((li, k) => li.classList.toggle("now", playing && k === at));
    el.querySelector(".note-q")?.classList.toggle("now", playing && at === out.lines.length);
  };
  const run = async () => {
    while (playing && at < lines.length) {
      setUi();
      const finished = await speak(lines[at], { lang: o.speechLang, gender: o.gender });
      if (!playing || !finished) return;
      at += 1;
      o.onEvent("note", at >= lines.length ? "finished" : "progress", at / lines.length);
      await wait(200);
    }
    if (at >= lines.length) { playing = false; at = 0; setUi(); }
  };
  btn.onclick = () => { playing = !playing; if (playing) run(); else stopSpeech(); setUi(); };
  setUi();
  return { stop() { playing = false; stopSpeech(); } };
}

// ---------------------------------------------------------------- steps and story: one page at a time, at her pace

function pages(el, out, o, format) {
  let i = 0;
  const n = out.pages.length;
  const story = format === "story";
  el.innerHTML = `<div class="v-title">${esc(out.title)}</div><div class="v-page-track"></div>
    <div class="v-nav"><button type="button" class="v-btn" data-go="-1">${esc(o.words.back)}</button><div class="dots">${"<i></i>".repeat(n)}</div>
    <button type="button" class="v-btn primary" data-go="1">${esc(o.words.next)}</button></div>`;
  const track = el.querySelector(".v-page-track");
  const show = () => {
    const pg = out.pages[i];
    const label = story ? "" : `<span class="step-no">${esc(say(o.words.of, { i: i + 1, n }))}</span>`;
    track.innerHTML = `<div class="v-page${story ? " story" : ""}">${label}<span class="pic">${icon(pg.icon, story ? 72 : 52)}</span>
      <h3>${esc(pg.big_text)}</h3><p>${esc(pg.line)}</p>
      <button type="button" class="read">${icon("volume", 18)}${esc(o.words.read)}</button>${story && i === n - 1 ? `<span class="the-end">${esc(o.words.end)}</span>` : ""}</div>`;
    el.querySelectorAll(".dots i").forEach((d, k) => d.classList.toggle("on", k === i));
    el.querySelector('[data-go="-1"]').disabled = i === 0;
    el.querySelector('[data-go="1"]').textContent = i === n - 1 ? o.words.done : o.words.next;
    o.onEvent(format, i === n - 1 ? "finished" : "progress", (i + 1) / n);
    if (story) speak(pg.line, { lang: o.speechLang, gender: o.gender }); // a picture story reads itself; steps wait to be asked
  };
  el.onclick = (e) => {
    if (e.target.closest(".read")) { stopSpeech(); speak(out.pages[i].line, { lang: o.speechLang, gender: o.gender }); return; }
    const b = e.target.closest("[data-go]");
    if (!b) return;
    stopSpeech();
    i = Math.max(0, Math.min(n - 1, i + Number(b.dataset.go)));
    show();
  };
  swipe(track, (dir) => { stopSpeech(); i = Math.max(0, Math.min(n - 1, i + dir)); show(); });
  show();
  return { stop() { stopSpeech(); } };
}

// ---------------------------------------------------------------- card: one page to keep (printable from the Studio)

function card(el, out, o) {
  const body = `<div class="fridge"><h3>${esc(out.title)}</h3>
    <ul>${out.lines.map((l) => `<li>${icon(l.icon, 26)}<span>${esc(l.text)}</span></li>`).join("")}</ul>
    ${out.remember ? `<div class="remember"><small>${esc(o.words.remember)}</small><b>${esc(out.remember)}</b></div>` : ""}
    ${out.ask ? `<p class="ask-who">${esc(out.ask)}</p>` : ""}</div>`;
  el.innerHTML = body + `<div class="v-nav center"><button type="button" class="v-btn" data-read>${icon("volume", 18)} ${esc(o.words.read)}</button>
    ${o.printable ? `<button type="button" class="v-btn" data-print>${icon("printer", 18)} ${esc(o.words.print)}</button>` : ""}</div>`;
  const text = [out.title, ...out.lines.map((l) => l.text), out.remember].filter(Boolean).join("。 ");
  el.onclick = async (e) => {
    if (e.target.closest("[data-print]")) { printCard(body, o.lang); return; }
    if (!e.target.closest("[data-read]")) return;
    stopSpeech();
    if (await speak(text, { lang: o.speechLang, gender: o.gender })) o.onEvent("card", "finished", 1);
  };
  o.onEvent("card", "progress", 0.5); // seeing the page is most of the point
  return { stop() { stopSpeech(); } };
}

const FONTS = "https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&family=Noto+Sans+JP:wght@400;500;600&display=swap";
function printCard(body, lang) {
  const w = window.open("", "_blank", "width=720,height=900");
  if (!w) return;
  w.document.write(`<!doctype html><html lang="${esc(lang)}"><head><meta charset="utf-8"><title>RoleEdge</title>
    <link rel="stylesheet" href="${FONTS}"><link rel="stylesheet" href="/assets/css/tokens.css"><link rel="stylesheet" href="/assets/css/studio.css">
    <style>body{margin:32px;font-family:var(--font)}.fridge{font-size:26px}</style></head>
    <body>${body}<script>window.onload=()=>{window.print();}<\/script></body></html>`);
  w.document.close();
}

// ---------------------------------------------------------------- askme and quiz: gentle questions, no wrong buzzer

function quiz(el, out, o, format) {
  const qs = out.questions;
  const child = format === "quiz";
  let i = 0, firstTry = true, right = 0;
  el.innerHTML = `<div class="v-title">${esc(out.title)}</div><div class="quiz-stage" aria-live="polite"></div>`;
  const stage = el.querySelector(".quiz-stage");
  const stars = () => (child ? `<div class="stars" aria-label="${esc(say(o.words.stars, { k: right, n: qs.length }))}">${qs.map((_, k) => `<i class="${k < right ? "on" : ""}">${icon("star", 22)}</i>`).join("")}</div>` : "");
  const show = () => {
    if (i >= qs.length) {
      stage.innerHTML = `<div class="quiz-done">${child ? stars() : icon("check", 48)}
        <p>${esc(child ? say(o.words.stars, { k: right, n: qs.length }) : say(o.words.thanks, { caregiver: o.names.caregiver || "" }))}</p></div>`;
      o.onEvent(format, "finished", right / qs.length);
      return;
    }
    const q = qs[i];
    firstTry = true;
    stage.innerHTML = `${stars()}<div class="q">${icon(q.icon, 36)}<h3>${esc(q.question)}</h3><span class="v-count">${esc(say(o.words.of, { i: i + 1, n: qs.length }))}</span></div>
      <div class="choices">${q.choices.map((c, k) => `<button type="button" class="choice" data-k="${k}">${esc(c)}</button>`).join("")}</div>
      <div class="explain" hidden></div>`;
  };
  stage.onclick = (e) => {
    if (e.target.closest("[data-next]")) { i += 1; show(); return; }
    const b = e.target.closest(".choice");
    if (!b || b.disabled) return;
    const q = qs[i];
    const k = Number(b.dataset.k);
    if (k !== q.answer && child && firstTry) { // a child gets one more go; the wrong one just fades
      firstTry = false;
      b.disabled = true;
      b.classList.add("faded");
      stage.querySelector(".explain").hidden = false;
      stage.querySelector(".explain").textContent = o.words.tryAgain;
      return;
    }
    const correct = k === q.answer;
    const gotIt = correct && firstTry;
    if (gotIt) right += 1;
    o.onEvent(format, gotIt ? "answer_right" : "answer_missed", i);
    stage.querySelectorAll(".choice").forEach((c) => { c.disabled = true; c.classList.toggle("right", Number(c.dataset.k) === q.answer); });
    const box = stage.querySelector(".explain");
    box.hidden = false;
    box.innerHTML = `${correct ? `<b>${esc(o.words.right)}</b> ` : ""}${esc(q.explain)}
      <button type="button" class="v-btn primary" data-next>${esc(i === qs.length - 1 ? o.words.done : o.words.next)}</button>`;
    if (child) stage.querySelector(".stars")?.replaceWith(Object.assign(document.createElement("div"), { innerHTML: stars() }).firstElementChild);
  };
  show();
  return { stop() {} };
}

// ---------------------------------------------------------------- relay: questions a child can ask their grandparent

function relay(el, out, o) {
  el.innerHTML = `<div class="relay-intro">${icon("family", 40)}<h3>${esc(out.title)}</h3><p>${esc(out.intro)}</p></div>
    <div class="v-hint">${esc(o.words.ask)}</div>
    <div class="relay-qs">${out.questions.map((q, k) => `<button type="button" class="relay-q" data-k="${k}" ${o.onAsk ? "" : "disabled"}>
      <span>${esc(q)}</span>${icon("send", 20)}</button>`).join("")}</div>
    <p class="v-hint">${esc(o.words.own)}</p>`;
  el.onclick = (e) => {
    const b = e.target.closest(".relay-q");
    if (!b || !o.onAsk || b.disabled) return;
    b.disabled = true;
    b.classList.add("sent");
    b.querySelector("svg").outerHTML = `<small>${esc(o.words.sent)}</small>`;
    o.onEvent("relay", "asked", Number(b.dataset.k));
    o.onAsk(out.questions[Number(b.dataset.k)], Number(b.dataset.k));
  };
  return { stop() {} };
}

function swipe(target, go) {
  let x0 = null;
  target.addEventListener("pointerdown", (e) => { x0 = e.clientX; });
  target.addEventListener("pointerup", (e) => { if (x0 !== null && Math.abs(e.clientX - x0) > 40) go(e.clientX < x0 ? 1 : -1); x0 = null; });
}

// ---------------------------------------------------------------- map: a mind map, the key idea in the middle

function mindmap(el, map, o) {
  const n = map.branches.length;
  const W = 400, H = 330, cx = W / 2, cy = H / 2;
  const pos = map.branches.map((_, k) => {
    const a = -Math.PI / 2 + (2 * Math.PI * k) / n + (n % 2 ? 0 : Math.PI / n);
    return { x: cx + Math.cos(a) * 140, y: cy + Math.sin(a) * 124 };
  });
  const lines = pos.map((p, k) => `<path pathLength="1" style="animation-delay:${k * 80}ms" d="M${cx},${cy} C${(cx + p.x) / 2},${cy} ${(cx + p.x) / 2},${p.y} ${p.x},${p.y}"/>`).join("");
  el.innerHTML = `<div class="v-title">${esc(map.root)}</div>
    <div class="mm" role="group" aria-label="${esc(map.root)}"><svg viewBox="0 0 ${W} ${H}" class="mm-lines" aria-hidden="true">${lines}</svg>
      <div class="mm-root" style="left:50%;top:50%">${esc(map.root)}</div>
      ${map.branches.map((b, k) => `<button type="button" class="mm-node" data-k="${k}" style="left:${(pos[k].x / W) * 100}%;top:${(pos[k].y / H) * 100}%;animation-delay:${150 + k * 80}ms">
        ${icon(b.icon, 18)}<span>${esc(b.label)}</span></button>`).join("")}
    </div>
    <ol class="mm-list">${map.branches.map((b, k) => `<li data-k="${k}"><button type="button" class="mm-row" data-k="${k}">${icon(b.icon, 18)}<b>${esc(b.label)}</b></button>
      ${b.leaves.length ? `<div class="mm-leaves">${b.leaves.map((l) => `<span>${esc(l)}</span>`).join("")}</div>` : ""}</li>`).join("")}</ol>
    <p class="v-hint">${esc(o.words.tapBranch)}</p>`;
  const opened = new Set();
  el.onclick = (e) => {
    const b = e.target.closest("[data-k]");
    if (!b || !(b.classList.contains("mm-node") || b.classList.contains("mm-row"))) return;
    const k = Number(b.dataset.k);
    const branch = map.branches[k];
    el.querySelectorAll(".mm-node, .mm-list li").forEach((x) => x.classList.toggle("on", Number(x.dataset.k) === k));
    stopSpeech();
    speak([branch.label, ...branch.leaves].join("。 "), { lang: o.speechLang, gender: o.gender });
    opened.add(k);
    o.onEvent("map", opened.size === n ? "finished" : "progress", opened.size / n);
  };
  return { stop() { stopSpeech(); } };
}

// ---------------------------------------------------------------- video: narrated scenes that play by themselves

/** A soft ring around what to watch in a still (a box in the still's own pixels), wherever object-fit: cover put it. */
function ringOn(img, ring, [x1, y1, x2, y2, w, h]) {
  const place = () => {
    const W = img.clientWidth, H = img.clientHeight;
    if (!W || !H) return;
    const scale = Math.max(W / w, H / h), dw = w * scale, dh = h * scale;
    const [px, py] = getComputedStyle(img).objectPosition.split(" ").map((v) => parseFloat(v) / 100);
    const left = (W - dw) * px + x1 * scale, top = (H - dh) * py + y1 * scale;
    Object.assign(ring.style, { left: `${left - 8}px`, top: `${top - 8}px`, width: `${(x2 - x1) * scale + 16}px`, height: `${(y2 - y1) * scale + 16}px` });
    ring.hidden = false;
  };
  if (img.complete) place(); else img.addEventListener("load", place, { once: true });
}

function video(el, out, o) {
  const scenes = out.scenes;
  const n = scenes.length;
  let at = 0, playing = false, run = 0;
  const bg = o.picture ? `style="--pic:url('${esc(o.picture)}')"` : "";
  el.innerHTML = `<div class="v-title">${esc(out.title)}</div>
    <div class="vid${o.picture ? " has-pic" : ""}" ${bg}>
      <div class="vid-bars">${scenes.map(() => "<i><b></b></i>").join("")}</div>
      <div class="vid-scene" aria-live="polite"></div>
      <button type="button" class="vid-play" aria-label="${esc(o.words.play)}">${icon("play", 30)}</button>
    </div>
    <div class="v-nav center"><button type="button" class="v-btn" data-replay>${icon("replay", 18)} ${esc(o.words.replay)}</button></div>`;
  const stage = el.querySelector(".vid-scene");
  const bars = [...el.querySelectorAll(".vid-bars i")];
  const playBtn = el.querySelector(".vid-play");
  const frameOf = (sc) => (sc.frame >= 0 && out.frames?.[sc.frame]) || ""; // the shared video's own picture, if the maker chose one
  const focusOf = (sc) => { const f = out.focus?.[sc.frame]; return f?.length === 6 ? f : null; }; // [x1, y1, x2, y2, w, h] (SAM 3.1)
  const draw = (k, animate = true) => {
    const sc = scenes[k];
    const frame = frameOf(sc);
    const fb = frame ? focusOf(sc) : null;
    const centre = fb ? `style="object-position:${(((fb[0] + fb[2]) / 2 / fb[4]) * 100).toFixed(1)}% ${(((fb[1] + fb[3]) / 2 / fb[5]) * 100).toFixed(1)}%"` : "";
    el.querySelector(".vid").classList.toggle("has-frame", Boolean(frame));
    stage.innerHTML = (frame ? `<img class="vid-frame${animate ? " in" : ""}" src="${esc(frame)}" alt="" ${centre}>` : "") +
      (fb ? `<span class="vid-focus" hidden></span>` : "") +
      `<div class="vid-card${animate ? " in" : ""}"><span class="vid-pic">${icon(sc.icon, 64)}</span><h3>${esc(sc.big_text)}</h3><p>${esc(sc.narration)}</p></div>`;
    if (fb) ringOn(stage.querySelector(".vid-frame"), stage.querySelector(".vid-focus"), fb);
    bars.forEach((b, i) => { b.className = i < k ? "done" : i === k && playing ? "now" : ""; });
  };
  const setUi = () => { el.querySelector(".vid").classList.toggle("playing", playing); playBtn.hidden = playing; };
  const play = async () => {
    const token = ++run;
    playing = true; setUi();
    while (playing && token === run && at < n) {
      draw(at);
      const started = performance.now();
      const finished = await speak(scenes[at].narration, { lang: o.speechLang, gender: o.gender, rate: 0.92 });
      const left = 3200 - (performance.now() - started); // every scene stays up long enough to read
      if (left > 0) await wait(left);
      if (!playing || token !== run || !finished) return;
      at += 1;
      o.onEvent("video", at >= n ? "finished" : "progress", at / n);
    }
    if (at >= n) { playing = false; at = n - 1; setUi(); bars.forEach((b) => { b.className = "done"; }); }
  };
  playBtn.onclick = () => { if (at >= n - 1 && bars.every((b) => b.className === "done")) at = 0; play(); };
  el.querySelector(".vid").addEventListener("click", (e) => {
    if (e.target.closest(".vid-play") || !playing) return;
    playing = false; stopSpeech(); setUi(); draw(at, false);
  });
  el.querySelector("[data-replay]").onclick = () => { stopSpeech(); at = 0; play(); };
  draw(0, false);
  setUi();
  return { stop() { playing = false; run += 1; stopSpeech(); } };
}

// ---------------------------------------------------------------- picture: one illustration and what it means

function picture(el, out, o) {
  const art = out.image ? `<img src="${esc(out.image)}" alt="${esc(out.caption)}">` : `<span class="pic-none">${icon("eye", 56)}</span>`;
  el.innerHTML = `<div class="v-title">${esc(out.title)}</div><figure class="pic-frame">${art}<figcaption>${esc(out.caption)}</figcaption></figure>
    <div class="v-nav center"><button type="button" class="v-btn" data-read>${icon("volume", 18)} ${esc(o.words.read)}</button></div>`;
  el.onclick = async (e) => {
    if (!e.target.closest("[data-read]")) return;
    stopSpeech();
    if (await speak(out.caption, { lang: o.speechLang, gender: o.gender })) o.onEvent("picture", "finished", 1);
  };
  o.onEvent("picture", "progress", 0.5);
  return { stop() { stopSpeech(); } };
}
