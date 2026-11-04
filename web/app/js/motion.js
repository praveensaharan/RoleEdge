// The motion the home page and the Lab share, so the two read as one site: scroll reveals and count-ups, the split
// headline and its rotating word, the header that takes the colour of the section under it, pointer effects, the
// dot-matrix fields behind the hero and every section, and the dark sections' fades into their neighbours. Each part
// starts only on screen and stops when it leaves; with reduced motion every part is shown at its final state.
import { esc } from "./common.js";

const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
export const reduce = matchMedia("(prefers-reduced-motion: reduce)");
export const fine = matchMedia("(hover: hover) and (pointer: fine)");
/** Run `fn(visible)` whenever `el` enters or leaves the screen. */
export function whenVisible(el, fn, margin = "0px") {
  if (!el) return;
  new IntersectionObserver(([e]) => fn(e.isIntersecting), { rootMargin: margin }).observe(el);
}

// ------------------------------------------------------------------ reveals, headline, counters
export function splitHeadline() {
  const h = $("[data-split]");
  if (!h) return;
  if (!h.hasAttribute("aria-label")) h.setAttribute("aria-label", h.textContent.replace(/\s+/g, " ").trim());
  let k = 0;
  const wrap = (text) => { // by spaces, so punctuation stays with its word ("Mom." never breaks before the dot)
    const parts = text.split(/(\s+)/);
    return parts.map((p) => (/^\s+$/.test(p) || !p ? p : `<span class="split-w" aria-hidden="true" style="--d:${(k++ * 0.045).toFixed(3)}s">${esc(p)}</span>`)).join("");
  };
  h.innerHTML = [...h.childNodes].map((n) => {
    if (n.nodeType === 3) return wrap(n.textContent);
    if (n.classList.contains("rot")) { // the word that changes: one revealed word, rotated afterwards
      return `<span class="split-w rot" aria-hidden="true" data-words="${esc(n.dataset.words)}" style="--d:${(k++ * 0.045).toFixed(3)}s"><span class="rot-w">${esc(n.textContent)}</span></span>`;
    }
    return `<span class="${n.className}">${wrap(n.textContent)}</span>`;
  }).join("");
  requestAnimationFrame(() => requestAnimationFrame(() => h.classList.add("split-in")));
  rotate($(".rot", h));
  $$("h2 .rot").forEach(rotate); // "Your work apps, working for Mom. / Dad. / your kids. ..."
}

/** Mom. → Dad. → your kids. → Grandma. → Grandpa.: the word slides out and the next slides in, and the box
 *  eases to the new word's width so the line re-centres smoothly. Off with reduced motion. */
function rotate(box) {
  if (!box || reduce.matches) return;
  const words = box.dataset.words.split("|");
  let i = 0;
  const measure = (text) => {
    const probe = Object.assign(document.createElement("span"), { className: "rot-w", textContent: text });
    probe.style.cssText = "position:absolute;visibility:hidden;white-space:nowrap";
    box.append(probe);
    const w = probe.getBoundingClientRect().width;
    probe.remove();
    return w;
  };
  const fit = () => { box.style.width = `${measure(words[i])}px`; };
  fit();
  document.fonts?.ready.then(fit); // measured again once Geist has loaded, and when the size changes
  addEventListener("resize", fit);
  setInterval(() => {
    if (document.hidden || box.getBoundingClientRect().bottom < 0) return;
    const old = $(".rot-w", box);
    i = (i + 1) % words.length;
    const next = Object.assign(document.createElement("span"), { className: "rot-w in", textContent: words[i] });
    box.style.width = `${measure(words[i])}px`;
    old.classList.add("out");
    box.append(next);
    setTimeout(() => old.remove(), 700);
  }, 1800);
}

export function countUp(el) {
  const to = parseFloat(el.dataset.count), dec = +(el.dataset.dec || 0);
  const fmt = new Intl.NumberFormat("en", { minimumFractionDigits: dec, maximumFractionDigits: dec });
  if (reduce.matches) { el.textContent = fmt.format(to); return; }
  const t0 = performance.now(), d = 1400;
  const f = (t) => {
    const p = Math.min((t - t0) / d, 1), e = p === 1 ? 1 : 1 - 2 ** (-10 * p);
    el.textContent = fmt.format(to * e);
    if (p < 1) requestAnimationFrame(f);
  };
  requestAnimationFrame(f);
}

/** Reveal `[data-reveal]` (and `extra`, a selector) as it scrolls into view, counting up any `[data-count]` inside. */
export function reveals(extra = "") {
  $$("[data-count]").forEach((el) => { if (!reduce.matches) el.textContent = "0"; });
  $$("[data-stagger]").forEach((g) => [...g.children].forEach((c, i) => c.style.setProperty("--d", `${i * 0.06}s`)));
  const io = new IntersectionObserver((entries) => entries.forEach((e) => {
    if (!e.isIntersecting) return;
    e.target.classList.add("in");
    $$("[data-count]", e.target).forEach(countUp);
    io.unobserve(e.target);
  }), { rootMargin: "0px 0px -10% 0px" });
  $$(`[data-reveal]${extra ? `, ${extra}` : ""}`).forEach((el) => (el.closest(".hero") ? requestAnimationFrame(() => el.classList.add("in")) : io.observe(el)));
}

// ------------------------------------------------------------------ nav: the section under the header decides its colour
export function nav() {
  const bar = $("#nav"), prog = $("#progress");
  const links = new Map($$(".nav-links a").map((a) => [a.getAttribute("href").slice(1), a]));
  const themed = $$("[data-theme]");
  let ticking = false;
  const onScroll = () => {
    ticking = false;
    const y = scrollY, max = document.documentElement.scrollHeight - innerHeight;
    prog.style.transform = `scaleX(${max > 0 ? y / max : 0})`;
    const probe = bar.offsetHeight / 2; // the header's middle line
    const under = themed.find((s) => { const r = s.getBoundingClientRect(); return r.top <= probe && r.bottom > probe; });
    const light = under?.dataset.theme === "light";
    bar.classList.toggle("light", light);
    bar.classList.toggle("scrolled", !light && y > 40);
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", light ? "#ffffff" : "#0a0a0a");
  };
  addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(onScroll); } }, { passive: true });
  addEventListener("resize", onScroll);
  onScroll();
  const io = new IntersectionObserver((entries) => entries.forEach((e) => {
    if (e.isIntersecting) links.forEach((a, id) => a.classList.toggle("on", id === e.target.id));
  }), { rootMargin: "-45% 0px -50% 0px" });
  document.querySelectorAll("main > section, footer").forEach((s) => io.observe(s)); // a section not in the nav clears it
}

// ------------------------------------------------------------------ pointer effects (fine pointers only)
export function pointer() {
  if (!fine.matches || reduce.matches) return;
  let raf = 0, last = null;
  document.addEventListener("pointermove", (e) => {
    last = e;
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0;
      const card = last.target.closest?.(".spot");
      if (card) {
        const r = card.getBoundingClientRect();
        card.style.setProperty("--mx", `${last.clientX - r.left}px`);
        card.style.setProperty("--my", `${last.clientY - r.top}px`);
      }
    });
  }, { passive: true });

  $$("[data-magnetic]").forEach((b) => { // the primary buttons lean towards the pointer, at most 6px
    b.addEventListener("pointermove", (e) => {
      const r = b.getBoundingClientRect();
      b.style.transform = `translate(${(((e.clientX - r.left) / r.width - 0.5) * 12).toFixed(1)}px, ${(((e.clientY - r.top) / r.height - 0.5) * 10).toFixed(1)}px)`;
    });
    b.addEventListener("pointerleave", () => { b.style.transform = ""; });
  });

  const stage = $("[data-tilt]"); // the hero stage settles flat as you scroll and tilts a little with the pointer
  if (stage && innerWidth > 720) {
    let rx = 10, ry = 0;
    const apply = () => { stage.style.setProperty("--rx", `${rx.toFixed(2)}deg`); stage.style.setProperty("--ry", `${ry.toFixed(2)}deg`); };
    addEventListener("scroll", () => { rx = Math.max(0, 10 - scrollY / 40); apply(); }, { passive: true });
    $(".hero").addEventListener("pointermove", (e) => { ry = (e.clientX / innerWidth - 0.5) * 6; apply(); });
    $(".hero").addEventListener("pointerleave", () => { ry = 0; apply(); });
  }
}

// ------------------------------------------------------------------ the dot-matrix field: a trend line drawn in dots
export function field(canvas, { gap = 22, line = true, rgb = "255,255,255", base = 0.07, wave = false } = {}) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  let w = 0, h = 0, on = false, seen = false, px = -999, py = -999;
  const t0 = performance.now();
  const still = !fine.matches; // a phone or tablet: draw once, no animation on every frame
  const resize = () => {
    w = canvas.clientWidth; h = canvas.clientHeight;
    const dpr = h > 1800 ? 1 : Math.min(2, devicePixelRatio || 1); // a tall section stays light on memory
    canvas.width = w * dpr; canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (!on) paint(t0 + 6000);
  };
  const host = canvas.parentElement;
  host.addEventListener("pointermove", (e) => { const r = canvas.getBoundingClientRect(); px = e.clientX - r.left; py = e.clientY - r.top; });
  host.addEventListener("pointerleave", () => { px = py = -999; });
  const signal = (x, t) => { // her usual weeks, then a drift: the same shape as the trend card further down
    const u = x / w;
    const drift = u > 0.62 ? Math.pow((u - 0.62) / 0.38, 1.6) * 0.16 : 0;
    return h * (0.5 + drift + 0.018 * Math.sin(u * 19 + t * 0.6) + 0.012 * Math.sin(u * 41 - t * 0.9));
  };
  const BUCKETS = 10;
  const paint = (now) => {
    const t = (now - t0) / 1000;
    const r0 = canvas.getBoundingClientRect();
    const top = Math.max(0, -r0.top - gap), bottom = Math.min(h, innerHeight - r0.top + gap); // only the part on screen
    ctx.clearRect(0, 0, w, h);
    if (bottom <= top) return;
    const phase = (t % 11) / 11; // the line draws, holds, then fades
    const head = Math.min(1, phase / 0.55) * w, fade = phase > 0.85 ? 1 - (phase - 0.85) / 0.15 : 1;
    const paths = Array.from({ length: BUCKETS }, () => new Path2D());
    const amber = new Path2D();
    const off = (gap / 2) | 0;
    const y0 = off + Math.ceil(Math.max(0, top - off) / gap) * gap;
    for (let y = y0; y < bottom; y += gap) {
      for (let x = off; x < w; x += gap) {
        let a = base, r = 1;
        const dx = x - px, dy = y - py, d2 = dx * dx + dy * dy;
        if (d2 < 48400) { const f = 1 - Math.sqrt(d2) / 220; a += 0.42 * f * f; r += 0.5 * f; }
        if (wave) { const k = Math.sin((x + y * 0.6) * 0.011 - t * 0.7); if (k > 0.6) a += 0.12 * (k - 0.6) / 0.4; }
        if (line && x < head) {
          const dv = Math.abs(y - signal(x, t));
          if (dv < gap * 1.6) {
            const f = (1 - dv / (gap * 1.6)) * fade;
            if (x / w > 0.62 && f > 0.55) { amber.moveTo(x + 1.6, y); amber.arc(x, y, 1.6, 0, 6.283); continue; }
            a += 0.55 * f; r += 0.6 * f;
          }
        }
        const b = Math.min(BUCKETS - 1, (a * BUCKETS) | 0);
        paths[b].moveTo(x + r, y); paths[b].arc(x, y, r, 0, 6.283);
      }
    }
    paths.forEach((p, i) => { ctx.fillStyle = `rgba(${rgb},${((i + 0.5) / BUCKETS).toFixed(3)})`; ctx.fill(p); });
    ctx.fillStyle = `rgba(220,104,3,${(0.85 * fade).toFixed(3)})`; ctx.fill(amber); // the drift is "needs you" amber
  };
  const draw = (now) => { if (!on) return; paint(now); requestAnimationFrame(draw); };
  resize();
  addEventListener("resize", resize);
  if (reduce.matches || still) { // drawn once, and again when it scrolls into view
    addEventListener("scroll", () => requestAnimationFrame(() => paint(t0 + 6000)), { passive: true });
    return;
  }
  const update = () => { const was = on; on = seen && !document.hidden; if (on && !was) requestAnimationFrame(draw); };
  whenVisible(canvas, (v) => { seen = v; update(); });
  document.addEventListener("visibilitychange", update);
}

/** The dot matrix behind every section, not just the hero: white dots on the dark sections, black on the light. */
export function fields() {
  document.querySelectorAll("main > section, body > footer").forEach((sec) => {
    if (sec.querySelector(":scope > canvas")) return; // the hero and the closing call already have theirs
    const c = Object.assign(document.createElement("canvas"), { className: "sec-field" });
    c.setAttribute("aria-hidden", "true");
    sec.prepend(c);
    const dark = sec.dataset.theme === "dark";
    field(c, { gap: 24, line: false, wave: true, rgb: dark ? "255,255,255" : "10,10,10", base: 0.1 }); // a visible grid, like the hero's
  });
}

// ------------------------------------------------------------------ dark to light and back: each dark section fades in from,
// and out to, the colour of the section beside it, so the page dims and brightens instead of cutting
export function fades() {
  const all = [...document.querySelectorAll("main > section, body > footer")];
  const bg = (el) => getComputedStyle(el).backgroundColor;
  const isDark = (el) => el.dataset.theme === "dark";
  all.forEach((el, k) => {
    if (!isDark(el)) return;
    const prev = all[k - 1], next = all[k + 1];
    const add = (side, color) => {
      const f = Object.assign(document.createElement("div"), { className: `fade fade-${side}` });
      f.setAttribute("aria-hidden", "true");
      f.style.setProperty("--edge", color === "rgba(0, 0, 0, 0)" ? "#fff" : color);
      el.prepend(f);
    };
    if (prev && !isDark(prev)) add("top", bg(prev));
    if (next && !isDark(next)) add("bottom", bg(next));
  });
}
