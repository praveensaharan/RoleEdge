import { hush, speakNaturally } from "./voice.js";
// The talking avatar on the parent's phone: frames drawn by Muse Image and aligned with SAM 3.1 (see
// src/roleedge/avatar), switched in time with the speech by plain code. Speech is the browser's built-in voice
// (not an AI model call), or an audio file when the server provides one.

const FRAMES = ["base", "open", "half", "blink"];
const OPEN_SOUNDS = /[aoAOあいかがさざただなはばぱまやらわおこごそぞとどのほぼぽもよろをアカガサザタダナハバパマヤラワオコゴソゾトドノホボポモヨロヲ]/;
const PAUSES = /[、。,.!?！？\n]/;

/** Load an avatar's frames; resolves to null if this person has no avatar. */
export async function loadAvatar(personId) {
  try {
    const res = await fetch(`/assets/avatars/${personId}/avatar.json`);
    if (!res.ok) return null;
    const meta = await res.json();
    const urls = Object.fromEntries(FRAMES.map((f) => [f, `/assets/avatars/${personId}/${f}.jpg`]));
    await Promise.all(Object.values(urls).map((src) => new Promise((ok) => { const i = new Image(); i.onload = i.onerror = ok; i.src = src; })));
    return { meta, urls };
  } catch { return null; }
}

/** Animates one <img>: idle blinking, and a moving mouth while it speaks. */
export class TalkingHead {
  constructor(img, avatar) {
    this.img = img;
    this.avatar = avatar;
    this.speaking = false;
    this.pointer = 0;
    this.text = "";
    this.show("base");
    this.blinkLoop();
  }

  show(frame) { if (this.avatar) this.img.src = this.avatar.urls[frame]; }

  blinkLoop() {
    clearTimeout(this.blinkTimer);
    this.blinkTimer = setTimeout(() => {
      if (!this.speaking || Math.random() < 0.5) {
        const before = this.img.src;
        this.show("blink");
        setTimeout(() => { if (this.img.src.endsWith("blink.jpg")) this.img.src = before.endsWith("blink.jpg") ? this.avatar.urls.base : before; }, 140);
      }
      this.blinkLoop();
    }, 2400 + Math.random() * 3600);
  }

  /** Speak ``text``; calls onProgress(charIndex) as it goes and resolves when done (or stopped). */
  speak(text, { lang, voiceIndex = 0, rate = 0.92, gender = "", onProgress = () => {} } = {}) {
    this.stop();
    this.text = text;
    this.pointer = 0;
    const cps = (lang.startsWith("ja") ? 7.5 : 14) * rate; // characters a second, to move the mouth between word marks
    let phrase = null; // the phrase being said, or null in a pause (the mouth rests)
    this.speaking = true;
    this.img.classList.add("talking");
    const timer = setInterval(() => {
      if (phrase) this.pointer = Math.max(this.pointer, Math.min(phrase.end, phrase.start + Math.floor((performance.now() - phrase.at) / 1000 * cps * (phrase.rate / rate))));
      onProgress(this.pointer);
      this.show(phrase ? this.mouthFor(this.pointer) : "base");
    }, 95);
    this.mouthTimer = timer;
    const said = speakNaturally(text, { lang, rate, gender, pick: voiceIndex,
      onState: (s) => { this.pointer = Math.max(this.pointer, s.index); phrase = s.talking ? { start: s.phraseStart, end: s.phraseStart + s.phraseLength, at: s.startedAt, rate: s.rate } : null; },
      onBoundary: (i) => { this.pointer = Math.max(this.pointer, i); if (phrase) phrase.at = performance.now() - (i - phrase.start) / cps * 1000; } });
    const finish = () => { // only this speech's own timer: a newer speech may already be running
      clearInterval(timer);
      if (this.mouthTimer !== timer) return;
      this.speaking = false; this.img.classList.remove("talking"); this.show("base"); onProgress(text.length);
    };
    this.finish = () => { hush(); finish(); };
    return said.then(() => finish());
  }

  /** Play an audio file and switch mouth frames with its loudness. */
  speakAudio(url, { onProgress = () => {} } = {}) {
    this.stop();
    return new Promise((resolve) => {
      const audio = new Audio(url);
      const ctx = new AudioContext();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      ctx.createMediaElementSource(audio).connect(analyser);
      analyser.connect(ctx.destination);
      const data = new Uint8Array(analyser.fftSize);
      let done = false; // ended, failed or stopped: whichever comes first
      const finish = () => { if (done) return; done = true; this.speaking = false; this.img.classList.remove("talking"); clearInterval(this.mouthTimer); this.show("base"); ctx.close().catch(() => {}); onProgress(1); resolve(); };
      audio.onended = finish;
      audio.onerror = finish;
      this.finish = () => { audio.pause(); finish(); };
      this.speaking = true;
      this.img.classList.add("talking");
      this.mouthTimer = setInterval(() => {
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (const v of data) sum += ((v - 128) / 128) ** 2;
        const loud = Math.sqrt(sum / data.length) * 6;
        this.show(loud > 0.45 ? "open" : loud > 0.12 ? "half" : "base");
        onProgress(audio.duration ? audio.currentTime / audio.duration : 0);
      }, 80);
      audio.play().catch(finish); // the browser refused (no tap yet): don't hang
    });
  }

  mouthFor(index) {
    const ch = this.text[index] || "";
    if (!ch || PAUSES.test(ch)) return "base";
    const r = Math.random();
    if (OPEN_SOUNDS.test(ch)) return r < 0.65 ? "open" : "half";
    return r < 0.35 ? "base" : r < 0.75 ? "half" : "open";
  }

  stop() {
    if (this.speaking) { hush(); this.finish?.(); }
    clearInterval(this.mouthTimer);
    this.speaking = false;
    this.img.classList.remove("talking");
    this.show("base");
  }
}
