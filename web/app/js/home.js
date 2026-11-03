// The home page's motion and data: icons and app marks, reveals, a header that matches the section under it, the
// dot-matrix field, the hero loop, the "see it in action" pipeline and its moments (mind map, slides, quiz, animated
// video, picture, her phone), the child model's line-by-line check, the apps browser, the comparison and the
// roadmap line. Everything starts only when it is on screen and stops when it leaves; with reduced motion every part
// is shown at its final state.
import { ICON, esc } from "./common.js";

const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const reduce = matchMedia("(prefers-reduced-motion: reduce)");
const fine = matchMedia("(hover: hover) and (pointer: fine)");
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

let PATHS = {}, BRANDS = {};
const icon = (name, size = 18) => PATHS[name]
  ? `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${PATHS[name]}</svg>` : "";
const brand = (slug, size = 18) => BRANDS[slug]
  ? `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="${esc(BRANDS[slug].path)}"/></svg>` : "";

/** Run `fn(visible)` whenever `el` enters or leaves the screen. */
function whenVisible(el, fn, margin = "0px") {
  if (!el) return;
  new IntersectionObserver(([e]) => fn(e.isIntersecting), { rootMargin: margin }).observe(el);
}

// ------------------------------------------------------------------ icons, marks and app logos
async function hydrate() {
  const [paths, brands] = await Promise.all([
    fetch("/api/icons").then((r) => r.json()).catch(() => ({})),
    fetch("/assets/brands.json").then((r) => r.json()).catch(() => ({ icons: {} })),
  ]);
  PATHS = paths; BRANDS = brands.icons || {};
  $$("[data-i]").forEach((el) => { el.innerHTML = icon(el.dataset.i); });
  $$("[data-mark]").forEach((el) => { el.innerHTML = ICON.mark; });
  $$("[data-brand]").forEach((el) => { el.innerHTML = brand(el.dataset.brand, 14); });
}

// ------------------------------------------------------------------ reveals, headline, counters
function splitHeadline() {
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

function countUp(el) {
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

function reveals() {
  $$("[data-count]").forEach((el) => { if (!reduce.matches) el.textContent = "0"; });
  $$("[data-stagger]").forEach((g) => [...g.children].forEach((c, i) => c.style.setProperty("--d", `${i * 0.06}s`)));
  const io = new IntersectionObserver((entries) => entries.forEach((e) => {
    if (!e.isIntersecting) return;
    e.target.classList.add("in");
    $$("[data-count]", e.target).forEach(countUp);
    io.unobserve(e.target);
  }), { rootMargin: "0px 0px -10% 0px" });
  $$("[data-reveal], #cmp, .trend-card").forEach((el) => (el.closest(".hero") ? requestAnimationFrame(() => el.classList.add("in")) : io.observe(el)));
}

// ------------------------------------------------------------------ nav: the section under the header decides its colour
function nav() {
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
function pointer() {
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
function field(canvas, { gap = 22, line = true, rgb = "255,255,255", base = 0.07, wave = false } = {}) {
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
function fields() {
  document.querySelectorAll("main > section, body > footer").forEach((sec) => {
    if (sec.querySelector(":scope > canvas")) return; // the hero and the closing call already have theirs
    const c = Object.assign(document.createElement("canvas"), { className: "sec-field" });
    c.setAttribute("aria-hidden", "true");
    sec.prepend(c);
    const dark = sec.dataset.theme === "dark";
    field(c, { gap: 24, line: false, wave: true, rgb: dark ? "255,255,255" : "10,10,10", base: 0.1 }); // a visible grid, like the hero's
  });
}

// ------------------------------------------------------------------ the hero loop: share → agents → checks → her phone
function heroLoop() {
  const typed = $("#hero-type"), att = $("#hero-att"), send = $("#hero-send");
  const agents = $$("#hero-agents .agent"), banner = $("#hero-banner"), card = $("#hero-card");
  const f1 = $("#hero-f1"), f2 = $("#hero-f2"), listen = $(".ip-listen", card);
  const scenes = new Map($$(".win-main .hscene").map((el) => [el.dataset.scene, el]));
  const navs = $$(".scenes-nav [data-go]");
  const slots = { pcMe: $("#pc-me"), pcCard: $("#pc-card"), odMe: $("#od-me"), odCard: $("#od-card") };
  const text = "Mom got a text saying she has a tax refund waiting. Explain kindly why it's a scam.";
  const FLOATS = {
    share: [["Muse Wonder: verified", "every claim matches the research"], ["Okaasan listened to all of it", 'and asked: "What should I do with the text?"']],
    parcel: [["Gmail: read with your OK", "only verified senders; the fake one was blocked"], ["Answered in 6 seconds", "while Kenji was in his meeting"]],
    order: [["Within your limit: ¥2,980 of ¥3,000", "you approve every order"], ["Ordered on Rakuten", "size M, like her last order"]],
  };
  const setFloats = (name) => [f1, f2].forEach((f, k) => { $("b", f).textContent = FLOATS[name][k][0]; $("small", f).textContent = FLOATS[name][k][1]; });
  const show = (name) => {
    scenes.forEach((el, k) => { el.classList.toggle("on", k === name); el.setAttribute("aria-hidden", String(k !== name)); });
    navs.forEach((b) => b.setAttribute("aria-selected", String(b.dataset.go === name)));
    setFloats(name);
  };
  const clear = () => {
    typed.textContent = ""; att.classList.remove("on");
    $$(".win-main .agent").forEach((a) => a.classList.remove("on", "done"));
    [banner, card, f1, f2, ...Object.values(slots)].forEach((x) => x.classList.remove("on"));
    $$("#pc-mails .mail-mock, #od-shop .prod, #od-confirm, #pc-ask, #od-ask").forEach((x) => x.classList.remove("on"));
    $("#od-approve").classList.remove("press", "done"); $("#od-approve").innerHTML = `${icon("cart", 14)}Approve order`;
    $(".dl-fill").style.transform = ""; $(".dl-truck").style.left = ""; $$(".od-steps span").forEach((x, i) => x.classList.toggle("on", i === 0));
    listen.classList.remove("play");
  };
  if (reduce.matches) { // the first scene at its end, nothing moves
    typed.textContent = text; att.classList.add("on");
    agents.forEach((a) => a.classList.add("on", "done"));
    [card, f1, f2].forEach((x) => x.classList.add("on"));
    navs.forEach((b) => b.addEventListener("click", () => { clear(); show(b.dataset.go); finalOf(b.dataset.go); }));
    return;
  }
  let running = false, gen = 0, next = null;
  const step = async (alive, list, gap, done) => { for (const a of list) { if (!alive()) return; a.classList.add("on"); await wait(gap); } for (const a of list) { if (!alive()) return; await wait(380); a.classList.add(done); } };
  const SCENES = {
    async share(alive) {
      await wait(500);
      for (const ch of text) { if (!alive()) return; typed.textContent += ch; await wait(ch === " " ? 28 : 18); }
      await wait(200); att.classList.add("on");
      await wait(500); send.classList.add("press"); await wait(220); send.classList.remove("press");
      await step(alive, agents, 140, "done");
      await wait(250); f1.classList.add("on");
      await wait(600); banner.classList.add("on");
      await wait(1200); card.classList.add("on"); banner.classList.remove("on");
      await wait(600); listen.classList.add("play");
      await wait(1600); f2.classList.add("on");
      await wait(3200);
    },
    async parcel(alive) {
      await wait(400); slots.pcMe.classList.add("on");
      await wait(500); $("#pc-ask").classList.add("on");
      await wait(700); await step(alive, $$("#pc-agents .agent"), 160, "done");
      for (const m of $$("#pc-mails .mail-mock")) { if (!alive()) return; await wait(420); m.classList.add("on"); }
      await wait(300); f1.classList.add("on");
      await wait(700); slots.pcCard.classList.add("on");
      await wait(700); $(".dl-fill").style.transform = "scaleX(.62)"; $(".dl-truck").style.left = "62%"; // on its way: "in transit"
      await wait(1400); f2.classList.add("on");
      await wait(3600);
    },
    async order(alive) {
      await wait(400); slots.odMe.classList.add("on");
      await wait(500); $("#od-ask").classList.add("on");
      for (const pr of $$("#od-shop .prod")) { if (!alive()) return; await wait(380); pr.classList.add("on"); }
      await wait(500); f1.classList.add("on");
      await wait(600); $("#od-confirm").classList.add("on");
      await wait(1300); const ok = $("#od-approve"); ok.classList.add("press"); await wait(240); ok.classList.remove("press");
      ok.classList.add("done"); ok.innerHTML = `${icon("check", 14)}Approved`;
      await wait(700); slots.odCard.classList.add("on");
      await wait(900); $$(".od-steps span")[1].classList.add("on");
      await wait(900); f2.classList.add("on");
      await wait(3400);
    },
  };
  const ORDER = ["share", "parcel", "order"];
  const run = async (g, from = "share") => {
    const alive = () => running && g === gen;
    let k = ORDER.indexOf(from);
    while (alive()) {
      const name = ORDER[k % ORDER.length];
      clear(); show(name);
      await SCENES[name](alive);
      if (!alive()) return;
      [f1, f2].forEach((x) => x.classList.remove("on"));
      await wait(500);
      k += 1;
    }
  };
  navs.forEach((b) => b.addEventListener("click", () => { running = true; run(++gen, b.dataset.go); }));
  whenVisible($(".stage"), (v) => { if (v && !running) { running = true; run(++gen); } else if (!v) running = false; });
}

/** A scene at its end, for reduced motion. */
function finalOf(name) {
  if (name === "parcel") { ["#pc-me", "#pc-card"].forEach((id) => $(id).classList.add("on")); $$("#pc-mails .mail-mock, #pc-agents .agent, #pc-ask").forEach((x) => x.classList.add("on", "done")); }
  if (name === "order") { ["#od-me", "#od-card"].forEach((id) => $(id).classList.add("on")); $$("#od-shop .prod, #od-confirm, #od-ask").forEach((x) => x.classList.add("on")); }
  if (name === "share") { $("#hero-card").classList.add("on"); $$("#hero-agents .agent").forEach((a) => a.classList.add("on", "done")); }
}

// ------------------------------------------------------------------ see it in action: the agents, in stages
function stages() {
  const rows = $$("#stages .stage-row");
  if (reduce.matches) { rows.forEach((r) => r.classList.add("done")); return; }
  let started = false;
  whenVisible($("#stages"), async (v) => {
    if (!v || started) return;
    started = true;
    for (const r of rows) { r.classList.add("run"); await wait(r.dataset.stage === "3" ? 1100 : 720); r.classList.remove("run"); r.classList.add("done"); }
  }, "0px 0px -20% 0px");
}

// ------------------------------------------------------------------ what Mom gets: the moments, as tabs
const MAP = { root: "The gift card text", branches: [
  { icon: "warning", label: "It's a trick", leaves: ["No real prize", "Not from Walmart"] },
  { icon: "money", label: "What they want", leaves: ["Your card number", "A $4.99 fee"] },
  { icon: "shield", label: "What to do", leaves: ["Don't tap the link", "Delete the text"] },
  { icon: "phone", label: "Who to ask", leaves: ["Call Maya", "Any time"] },
  { icon: "eye", label: "How to spot one", leaves: ["\"Tonight only\"", "A strange link"] },
] };
const SLIDES = [
  { icon: "heart", big: "Mom, you're safe", line: "That text is a trick, not a real prize." },
  { icon: "info", big: "Real prizes are free", line: "A real prize never asks you to pay first." },
  { icon: "warning", big: "Don't tap the link", line: "Links in surprise texts are there to take your card number." },
  { icon: "chat", big: "Delete it, tell Maya", line: "Delete the text. Maya is happy to check anything for you." },
];
const QUIZ = [
  { q: "A text says you won a prize, but you must pay first. What is it?", choices: ["A trick", "A real prize"], answer: 0, explain: "It's a trick. Real prizes never ask you to pay." },
  { q: "What do you do with the link in the text?", choices: ["Tap it to check", "Don't tap it, delete the text"], answer: 1, explain: "Don't tap it. Delete the text, and tell Maya." },
];
const SCENES = [
  { icon: "mobile", kick: "A text arrives", big: "\"You won $500!\"", sub: "A surprise prize, from a number you don't know." },
  { icon: "money", kick: "Then it asks", big: "Pay <span class=\"warn\">$4.99</span> tonight", sub: "Real prizes never ask you to pay." },
  { icon: "warning", kick: "That's the trick", big: "No prize. Just your card.", sub: "The link is there to take your card number." },
  { icon: "shield", kick: "What to do", big: "<span class=\"hl\">Don't tap.</span> Delete it.", sub: "Then tell Maya. You did the right thing." },
  { icon: "chat", kick: "Any time", big: "Maya is one tap away", sub: "Hold the mic on your phone and ask her." },
];

function mindMap(el) {
  const W = 640, H = 470, cx = W / 2, cy = H / 2, n = MAP.branches.length;
  const clampX = (x) => Math.max(78, Math.min(W - 78, x)), clampY = (y) => Math.max(26, Math.min(H - 26, y));
  const nodes = [], lines = [];
  MAP.branches.forEach((b, k) => {
    const a = -Math.PI / 2 + (2 * Math.PI * k) / n;
    const bx = cx + Math.cos(a) * 150, by = cy + Math.sin(a) * 118;
    lines.push({ d: `M${cx},${cy} Q${cx + Math.cos(a) * 80},${cy + Math.sin(a) * 40} ${bx},${by}`, k, leaf: false });
    nodes.push(`<button type="button" class="mn br" data-k="${k}" style="left:${(bx / W) * 100}%;top:${(by / H) * 100}%;transition-delay:${0.25 + k * 0.08}s">${icon(b.icon, 15)}<span>${esc(b.label)}</span></button>`);
    b.leaves.forEach((leaf, j) => {
      const la = a + (j - (b.leaves.length - 1) / 2) * 0.6;
      const lx = clampX(cx + Math.cos(la) * 262), ly = clampY(cy + Math.sin(la) * 206);
      lines.push({ d: `M${bx},${by} Q${(bx + lx) / 2 + Math.cos(a) * 12},${(by + ly) / 2 + Math.sin(a) * 12} ${lx},${ly}`, k, leaf: true });
      nodes.push(`<span class="mn lf" data-k="${k}" style="left:${(lx / W) * 100}%;top:${(ly / H) * 100}%;transition-delay:${0.6 + k * 0.08 + j * 0.05}s">${esc(leaf)}</span>`);
    });
  });
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">${lines.map((l, i) =>
    `<path class="ln${l.leaf ? " leaf" : ""}" data-k="${l.k}" pathLength="1" d="${l.d}" style="transition-delay:${(l.leaf ? 0.5 : 0.1) + i * 0.02}s"/>`).join("")}</svg>
    <span class="mn root" style="left:50%;top:50%">${esc(MAP.root)}</span>${nodes.join("")}
    <p class="sr">Mind map: ${esc(MAP.root)}. ${esc(MAP.branches.map((b) => `${b.label}: ${b.leaves.join(", ")}`).join(". "))}.</p>`;
  el.onclick = (e) => {
    const b = e.target.closest(".mn.br");
    const k = b && !b.classList.contains("on") ? b.dataset.k : null;
    el.classList.toggle("focus", k !== null);
    $$(".mn.br", el).forEach((x) => x.classList.toggle("on", x.dataset.k === k));
    $$(".mn.lf, .ln", el).forEach((x) => x.classList.toggle("hot", x.dataset.k === k));
  };
  return { show() { el.classList.remove("drawn"); requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add("drawn"))); } };
}

function slides(el) {
  let i = 0, timer = 0, playing = false;
  el.innerHTML = `<div class="slide-frame">${SLIDES.map((s, k) => `<div class="slide${k === 0 ? " on" : ""}"><span class="s-no">${k + 1} of ${SLIDES.length}</span>
    <span class="s-ic">${icon(s.icon, 32)}</span><h4>${esc(s.big)}</h4><p>${esc(s.line)}</p></div>`).join("")}</div>
    <div class="deck-nav"><button type="button" class="dbtn" data-go="-1">Back</button><span class="ddots">${SLIDES.map((_, k) => `<i class="${k === 0 ? "on" : ""}"></i>`).join("")}</span><button type="button" class="dbtn primary" data-go="1">Next</button></div>`;
  const go = (n) => {
    const all = $$(".slide", el);
    all[i].classList.remove("on"); all[i].classList.add("out");
    setTimeout(() => all.forEach((s) => s.classList.remove("out")), 600);
    i = (n + SLIDES.length) % SLIDES.length;
    all[i].classList.add("on");
    $$(".ddots i", el).forEach((d, k) => d.classList.toggle("on", k === i));
    $('[data-go="-1"]', el).disabled = i === 0;
  };
  const tick = () => { clearTimeout(timer); if (playing) timer = setTimeout(() => { go(i + 1); tick(); }, 3600); };
  el.onclick = (e) => { const b = e.target.closest("[data-go]"); if (b) { go(i + Number(b.dataset.go)); tick(); } };
  $('[data-go="-1"]', el).disabled = true;
  return { show() { playing = !reduce.matches; tick(); }, hide() { playing = false; clearTimeout(timer); } };
}

function quiz(el) {
  let i = 0, right = 0;
  const show = () => {
    if (i >= QUIZ.length) {
      el.innerHTML = `<div class="qz-done">${icon("check", 40)}<b>${right} of ${QUIZ.length} first time</b><span>Thank you. Maya will see your answers, and what to talk about.</span>
        <div style="margin-top:14px"><button type="button" class="dbtn" data-again>Try it again</button></div></div>`;
      return;
    }
    const q = QUIZ[i];
    el.innerHTML = `<div class="qz-q"><small>Question ${i + 1} of ${QUIZ.length}</small><b>${esc(q.q)}</b></div>
      ${q.choices.map((c, k) => `<button type="button" class="qz-c" data-k="${k}">${esc(c)}</button>`).join("")}`;
  };
  el.onclick = (e) => {
    if (e.target.closest("[data-again]")) { i = 0; right = 0; show(); return; }
    if (e.target.closest("[data-next]")) { i += 1; show(); return; }
    const b = e.target.closest(".qz-c");
    if (!b || b.disabled) return;
    const q = QUIZ[i], k = Number(b.dataset.k);
    if (k === q.answer) right += 1;
    $$(".qz-c", el).forEach((c) => { c.disabled = true; const r = Number(c.dataset.k) === q.answer; c.classList.toggle("right", r); c.classList.toggle("faded", !r); });
    el.insertAdjacentHTML("beforeend", `<div class="qz-x"><span>${k === q.answer ? "<b>That's right.</b> " : ""}${esc(q.explain)}</span>
      <button type="button" class="dbtn primary" data-next>${i === QUIZ.length - 1 ? "Done" : "Next"}</button></div>`);
  };
  show();
  return {};
}

function video(el) {
  const DUR = 4000;
  el.innerHTML = `${SCENES.map((s, k) => `<div class="scene${k === 0 ? " on" : ""}"><div class="bgfx">${icon(s.icon, 200)}</div>
      <div class="cap"><small>${esc(s.kick)}</small><b>${s.big}</b></div></div>`).join("")}
    <div class="p-bars">${SCENES.map(() => "<i><b></b></i>").join("")}</div>
    <div class="p-sub">${esc(SCENES[0].sub)}</div>
    <div class="p-ctl"><button type="button" aria-label="Pause">${icon("pause", 13)}</button><span class="p-time">0:00 / 0:20</span></div>
    <p class="sr">Animated video: ${esc(SCENES.map((s) => `${s.kick}. ${s.big.replace(/<[^>]+>/g, "")}. ${s.sub}`).join(" "))}</p>`;
  const scenes = $$(".scene", el), bars = $$(".p-bars i b", el), sub = $(".p-sub", el), btn = $(".p-ctl button", el), time = $(".p-time", el);
  let at = 0, t0 = 0, raf = 0, playing = false, held = 0;
  const fmt = (ms) => `0:${String(Math.floor(ms / 1000)).padStart(2, "0")}`;
  const scene = (k) => {
    scenes.forEach((s, j) => { s.classList.toggle("on", j === k); if (j === k) { const fx = $(".bgfx", s); fx.style.animation = "none"; void fx.offsetWidth; fx.style.animation = ""; } });
    sub.textContent = SCENES[k].sub;
  };
  const frame = (now) => {
    raf = 0;
    if (!playing) return;
    const p = Math.min(1, (now - t0) / DUR);
    bars.forEach((b, j) => { b.style.transform = `scaleX(${j < at ? 1 : j === at ? p : 0})`; });
    time.textContent = `${fmt(at * DUR + p * DUR)} / ${fmt(SCENES.length * DUR)}`;
    if (p >= 1) {
      at = (at + 1) % SCENES.length; t0 = now; scene(at);
      if (at === 0) bars.forEach((b) => { b.style.transform = "scaleX(0)"; });
    }
    raf = requestAnimationFrame(frame);
  };
  const play = () => { if (playing) return; playing = true; t0 = performance.now() - held; btn.innerHTML = icon("pause", 13); btn.setAttribute("aria-label", "Pause"); raf = requestAnimationFrame(frame); };
  const pause = () => { if (!playing) return; playing = false; held = performance.now() - t0; cancelAnimationFrame(raf); raf = 0; btn.innerHTML = icon("play", 13); btn.setAttribute("aria-label", "Play"); };
  btn.onclick = () => (playing ? pause() : play());
  return {
    show() { if (reduce.matches) { bars.forEach((b) => { b.style.transform = "scaleX(1)"; }); return; } at = 0; held = 0; scene(0); play(); },
    hide() { pause(); },
  };
}

function outputs() {
  const tabs = $$(".vtabs [data-out]"), panels = new Map($$(".vpanel").map((p) => [p.dataset.panel, p]));
  const parts = { map: mindMap($("#mind")), slides: slides($("#deck")), quiz: quiz($("#qz")), video: video($("#player")) };
  let current = "map", visible = false;
  const activate = (name) => {
    parts[current]?.hide?.();
    current = name;
    tabs.forEach((t) => t.setAttribute("aria-selected", String(t.dataset.out === name)));
    panels.forEach((p, k) => { p.hidden = k !== name; p.classList.toggle("live", k === name); });
    if (visible) parts[name]?.show?.();
  };
  tabs.forEach((t) => t.addEventListener("click", () => activate(t.dataset.out)));
  $(".vtabs").addEventListener("keydown", (e) => {
    if (!["ArrowRight", "ArrowLeft"].includes(e.key)) return;
    const k = tabs.findIndex((t) => t.dataset.out === current);
    const n = tabs[(k + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
    activate(n.dataset.out); n.focus();
  });
  whenVisible($(".outs-panel"), (v) => {
    const was = visible; visible = v;
    if (v && !was) parts[current]?.show?.();
    if (!v && was) parts[current]?.hide?.();
  }, "0px 0px -15% 0px");
  // scrolling down the chapters turns the panel to each moment in turn (the panel is pinned beside them)
  const chapters = $$(".chapter");
  const io = new IntersectionObserver((entries) => entries.forEach((e) => {
    if (!e.isIntersecting) return;
    chapters.forEach((c) => c.classList.toggle("on", c === e.target));
    if (e.target.dataset.chapter !== current) activate(e.target.dataset.chapter);
  }), { rootMargin: "-45% 0px -45% 0px" });
  chapters.forEach((c) => io.observe(c));
  chapters.forEach((c) => c.addEventListener("click", () => c.scrollIntoView({ behavior: reduce.matches ? "auto" : "smooth", block: "center" })));
}

// ------------------------------------------------------------------ the child model: every line, one at a time
function scan() {
  const box = $("#scan"), picks = $$("#ts-picks [data-line]");
  const verdict = (l) => { const why = l.dataset.held; l.classList.add(why ? "held" : "pass"); $("small", l).textContent = why ? `held · ${why}` : "passed"; };
  if (reduce.matches) { $$(".sc-line", box).forEach(verdict); }
  let busy = Promise.resolve();
  const check = (l) => { busy = busy.then(async () => { l.classList.add("scan-on"); await wait(reduce.matches ? 0 : 700); l.classList.remove("scan-on"); verdict(l); }); return busy; };
  // the first pass runs by itself when it comes into view; after that, the visitor's lines join the list
  let started = false;
  whenVisible(box, (v) => { if (v && !started) { started = true; $$(".sc-line", box).forEach((l) => { if (!reduce.matches) check(l); }); } });
  picks.forEach((b) => b.addEventListener("click", () => {
    const held = b.dataset.verdict === "pass" ? "" : b.dataset.verdict;
    const l = Object.assign(document.createElement("div"), { className: "sc-line new" });
    l.dataset.held = held;
    l.innerHTML = `<span class="dot"></span><span lang="ja">${esc(b.dataset.line)}<em>${esc(b.dataset.en)}</em></span><small></small>`;
    box.prepend(l);
    while (box.children.length > 4) box.lastElementChild.remove();
    $$(".km-cats span").forEach((c) => c.classList.toggle("hit", Boolean(held) && c.textContent.split(/[,\s]+/)[0].toLowerCase() === held.split(/[,\s]+/)[0].toLowerCase()));
    check(l);
  }));
}

// ------------------------------------------------------------------ a child's moments, on Hana's screen
const KID = {
  story: { name: "Picture story", pages: [
    ["globe", "つきは まるいよ", "つきは いつも まあるい ボールの かたち。", "The moon is always a round ball."],
    ["eye", "ひかりが あたる ところ", "たいようの ひかりが あたった ところだけ みえるんだ。", "We only see the part the sun lights up."],
    ["star", "こんやの つきは？", "パパと いっしょに そらを みてみよう。", "Let's look at the sky with Papa tonight."]] },
  quiz: { name: "Quiz game", q: "つきは ほんとうは どんな かたち？", en: "What shape is the moon really?", choices: ["まるい", "みかづき"], answer: 0 },
  map: { name: "Mind map", root: "つきの ひみつ", branches: [["かたち", "いつも まるい"], ["ひかり", "たいようの ひかり"], ["みえかた", "まいにち かわる"], ["みてみよう", "パパと そらを"]] },
  video: { name: "Animated video", scenes: [["globe", "つきは まるい", "The moon is round"], ["eye", "ひかりで かわる", "Sunlight changes what we see"], ["star", "そらを みよう", "Let's look up"]] },
  picture: { name: "Picture" },
  relay: { name: "Ask Grandma" },
};
let kidTimer = 0;
function kids() {
  const tabs = $$(".kmoments [data-kid]"), body = $("#kp-body");
  const show = (k) => {
    clearInterval(kidTimer);
    tabs.forEach((t) => t.setAttribute("aria-selected", String(t.dataset.kid === k)));
    $("#kp-name").textContent = KID[k].name;
    body.className = `kp-body kp-${k}`;
    body.innerHTML = RENDER[k]();
    WIRE[k]?.(body);
  };
  const RENDER = {
    story: () => `<div class="ks-page"></div><div class="ks-nav"><button type="button" data-go="-1" lang="ja">まえ</button><span class="ks-dots">${KID.story.pages.map(() => "<i></i>").join("")}</span><button type="button" data-go="1" class="next" lang="ja">つぎ</button></div>`,
    quiz: () => `<div class="kq"><div class="kq-stars"><i>${ic("star", 22)}</i><i>${ic("star", 22)}</i><i>${ic("star", 22)}</i></div><b lang="ja">${esc(KID.quiz.q)}</b><small>${esc(KID.quiz.en)}</small>
      <div class="kq-ch">${KID.quiz.choices.map((c, i) => `<button type="button" data-k="${i}" lang="ja">${esc(c)}</button>`).join("")}</div><p class="kq-say" aria-live="polite"></p></div>`,
    map: () => `<div class="kmap"><span class="kmap-root" lang="ja">${esc(KID.map.root)}</span>${KID.map.branches.map(([b, leaf], i) => `<button type="button" class="kmap-b b${i}" lang="ja"><b>${esc(b)}</b><span>${esc(leaf)}</span></button>`).join("")}<svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><path d="M50 50 L18 22 M50 50 L82 22 M50 50 L18 78 M50 50 L82 78"/></svg></div><p class="kp-hint">Tap a part to open it</p>`,
    video: () => `<div class="kv"><div class="kv-bars">${KID.video.scenes.map(() => "<i><b></b></i>").join("")}</div><div class="kv-scene"></div></div>`,
    picture: () => `<figure class="kpic"><img src="/assets/home/relay-dagashi.jpg" alt=""><figcaption lang="ja">おばあちゃんの だがしやさん<small>Grandma's sweet shop, drawn from her own words</small></figcaption></figure>`,
    relay: () => `<div class="kr"><button type="button" class="kr-ask" lang="ja">${ic("send", 14)}おばあちゃんが ちいさいころ、おかいものは どんな おみせだったの？</button>
      <div class="kr-feed"></div></div>`,
  };
  const WIRE = {
    story(el) {
      let i = 0;
      const draw = () => {
        const [ico, big, line, en] = KID.story.pages[i];
        $(".ks-page", el).innerHTML = `<span class="ks-pic">${ic(ico, 40)}</span><b lang="ja">${esc(big)}</b><p lang="ja">${esc(line)}</p><small>${esc(en)}</small>`;
        $$(".ks-dots i", el).forEach((d, k) => d.classList.toggle("on", k === i));
      };
      el.addEventListener("click", (e) => { const b = e.target.closest("[data-go]"); if (b) { i = (i + Number(b.dataset.go) + 3) % 3; draw(); } });
      draw();
    },
    quiz(el) {
      let tries = 0;
      el.addEventListener("click", (e) => {
        const b = e.target.closest("[data-k]");
        if (!b || b.disabled) return;
        if (Number(b.dataset.k) === KID.quiz.answer) {
          b.classList.add("right"); $$(".kq-ch button", el).forEach((x) => { x.disabled = true; });
          $$(".kq-stars i", el).forEach((s, k) => setTimeout(() => s.classList.add("on"), k * 160 + (tries ? 0 : 0)));
          $(".kq-say", el).innerHTML = `<span lang="ja">せいかい！</span> That's right: the moon is always round.`;
        } else {
          tries += 1; b.classList.add("faded"); b.disabled = true;
          $(".kq-say", el).innerHTML = `<span lang="ja">ほかのを えらんでね</span> One more try, never a buzzer.`;
        }
      });
    },
    map(el) { el.addEventListener("click", (e) => { const b = e.target.closest(".kmap-b"); if (b) b.classList.toggle("open"); }); },
    video(el) {
      let i = 0;
      const draw = () => {
        const [ico, big, en] = KID.video.scenes[i];
        $(".kv-scene", el).innerHTML = `<div class="kv-card"><span>${ic(ico, 44)}</span><b lang="ja">${esc(big)}</b><small>${esc(en)}</small></div>`;
        $$(".kv-bars i", el).forEach((b, k) => { b.className = k < i ? "done" : k === i ? "now" : ""; });
      };
      draw();
      if (!reduce.matches) kidTimer = setInterval(() => { i = (i + 1) % KID.video.scenes.length; draw(); }, 2600);
    },
    relay(el) {
      const feed = $(".kr-feed", el), ask = $(".kr-ask", el);
      const add = (html, cls) => { const d = Object.assign(document.createElement("div"), { className: cls, innerHTML: html }); feed.append(d); return d; };
      const go = async () => {
        ask.disabled = true; ask.classList.add("sent");
        add(`<small>はなちゃんから</small><span lang="ja">おばあちゃんが ちいさいころ、おかいものは どんな おみせだったの？</span>`, "kr-msg kid");
        await wait(reduce.matches ? 0 : 900);
        const typing = add("<i></i><i></i><i></i>", "kr-typing");
        await wait(reduce.matches ? 0 : 1300); typing.remove();
        add(`<small>おばあちゃん · こえ</small><span lang="ja">駄菓子屋さんで 10円の あめを 買うのが 楽しみだったのよ。</span><em>"I loved buying 10-yen sweets at the dagashi shop."</em>`, "kr-msg gran");
        await wait(reduce.matches ? 0 : 700);
        add(`<img src="/assets/home/relay-dagashi.jpg" alt=""><span>Drawn by Muse Image, after the checks passed</span>`, "kr-pic");
        await wait(reduce.matches ? 0 : 500);
        const next = add(`${ic("star", 13)}<span lang="ja">つぎは：どんな あじの あめだったの？</span>`, "kr-next");
        next.addEventListener("click", () => { feed.innerHTML = ""; ask.disabled = false; ask.classList.remove("sent"); });
      };
      ask.addEventListener("click", go);
    },
  };
  tabs.forEach((t) => t.addEventListener("click", () => show(t.dataset.kid)));
  show("relay");
  whenVisible($("#kprev"), (v) => { if (v && !$(".kr-feed")?.children.length && $(".kr-ask") && !$(".kr-ask").disabled) setTimeout(() => $(".kr-ask")?.click(), 600); }, "0px 0px -25% 0px");
}

// ------------------------------------------------------------------ the apps browser (demo accounts; nothing is sent)
// Each demo account drawn the way the real app looks on the web (layout, not their colours or logos), with
// Maya's family's synthetic data. "Share" sends nothing from here: it shows what the Studio does with it.
const ic = (n, z = 15) => icon(n, z);
const GMAIL = [
  { from: "Uber Eats", subj: "Your order is on the way", body: "Delivering to Linda Chen. Golden Bowl Noodles: chicken noodle soup. Arriving 12:25 to 12:35", t: "12:02 PM", ok: true, unread: true, label: "Deliveries", tell: "Tells Mom" },
  { from: "Priya Shah", subj: "Re: Q4 design review moved to 3 PM", body: "Thanks Maya, I've moved the review to 3 PM. Can you bring the onboarding mocks? We'll run until about 4.", t: "11:48 AM", ok: true, unread: true, label: "Work", tell: "Busy until 4" },
  { from: "Amazon.com", subj: "Your package has shipped", body: "Delivering to Linda Chen. Paper towels, 6 rolls. Arriving Thursday, Nov 5 by 9 PM", t: "10:15 AM", ok: true, label: "Deliveries", tell: "Tells Mom" },
  { from: "Alaska Airlines", subj: "Your trip to Seattle: Tue, Nov 10", body: "Confirmation ZX4K2Q. Departs LAX 7:05 AM, arrives SEA 9:52 AM. Return Wed, Nov 11, 6:40 PM.", t: "9:30 AM", ok: true, label: "Travel", tell: "City and days only" },
  { from: "USPS", addr: "alerts@usps-redelivery.top", subj: "Your package is on hold", body: "We tried to deliver your package. Pay the $1.99 redelivery fee within 24 hours", t: "7:40 AM", ok: false, unread: true },
  { from: "Workday", subj: "Your expense report was approved", body: "Expense report ER-20931 ($412.80) was approved by Priya Shah.", t: "Nov 2", ok: true, label: "Work", tell: "Private" },
];
const gmail = () => `<div class="app gm">
  <aside class="gm-side"><span class="gm-compose">${ic("edit")}Compose</span>
    <a class="on">${ic("mail")}<span>Inbox</span><b>4</b></a><a>${ic("star")}<span>Starred</span></a><a>${ic("clock")}<span>Snoozed</span></a><a>${ic("send")}<span>Sent</span></a><a>${ic("document")}<span>Drafts</span><b>1</b></a>
    <span class="gm-lbl">Labels</span><a><i class="sq"></i><span>Work</span></a><a><i class="sq"></i><span>Travel</span></a><a><i class="sq"></i><span>Deliveries</span></a></aside>
  <div class="gm-main">
    <div class="gm-search">${ic("eye")}<span>Search mail</span><span class="grow"></span><small class="gm-who">maya.chen@northwind.example</small></div>
    <div class="gm-tools"><span class="cb"></span>${ic("replay", 14)}<span class="grow"></span><small>1–6 of 48</small></div>
    <div class="gm-tabs"><span class="on">${ic("mail", 14)}Primary</span><span>${ic("bill", 14)}Promotions</span><span>${ic("info", 14)}Updates<em>6 new</em></span></div>
    <div class="gm-rows">${GMAIL.map((m) => `<div class="gm-row${m.unread ? " unread" : ""}${m.ok ? "" : " bad"}"><span class="cb"></span><span class="star">${ic("star", 14)}</span>
      <span class="from" title="${esc(m.addr || m.from)}">${esc(m.from)}</span>
      <span class="msg">${m.label ? `<i class="lb">${esc(m.label)}</i>` : ""}<b>${esc(m.subj)}</b><span> – ${esc(m.body)}</span></span>
      <span class="chk ${m.ok ? (m.tell === "Private" ? "" : "ok") : "bad"}">${m.ok ? esc(m.tell) : "Fake: blocked"}</span>
      <time>${m.t}</time><button type="button" class="share-btn" data-share>${m.ok ? "Share" : "Explain it"}</button></div>`).join("")}</div>
  </div></div>`;

const slack = () => `<div class="app sk">
  <aside class="sk-side"><div class="sk-ws"><span class="sk-ws-ic">N</span><b>Northwind</b>${ic("edit", 14)}</div>
    <div class="sk-status"><span class="av">M</span><span><b>Maya Chen</b><small><i class="pr busy"></i>In a meeting · until 4:00 PM</small></span></div>
    <span class="sk-sec">Channels</span><a class="on"><i>#</i>design-team</a><a><i>#</i>q4-launch</a><a><i>#</i>general</a>
    <span class="sk-sec">Direct messages</span><a><i class="pr on"></i>Priya Shah</a><a><i class="pr"></i>Daniel (brother)</a><a class="bot"><i class="pr on"></i>RoleEdge<small>APP</small></a></aside>
  <div class="sk-main">
    <div class="sk-head"><b><i>#</i>design-team</b><span class="sk-mem">${ic("family", 14)}14</span><span class="grow"></span><small>Onboarding redesign · Q4</small></div>
    <div class="sk-feed">
      <div class="sk-day"><span>Today</span></div>
      <div class="sk-msg"><span class="av">P</span><div class="bd"><b>Priya Shah</b><time>11:52 AM</time><p>Design review moved to <b>3 PM</b> in the Orca room. Bring the onboarding mocks, we'll go until about 4.</p>
        <div class="sk-re"><span>${ic("check", 12)}6</span><a>3 replies</a></div></div><button type="button" class="share-btn" data-share>Share</button></div>
      <div class="sk-msg"><span class="av">J</span><div class="bd"><b>Jordan Lee</b><time>12:10 PM</time><p>Launch checklist is in the doc. Maya, can you sign off the empty states by Friday?</p></div><button type="button" class="share-btn" data-share>Share</button></div>
      <div class="sk-msg app-msg"><span class="av bot"><span class="mark" data-mark></span></span><div class="bd"><b>RoleEdge</b><em>APP</em><time>2:14 PM</time><small class="only">Only visible to you</small>
        <div class="sk-card"><p><b>Mom asks:</b> "Are you coming for dinner on Sunday?"</p><span>You're in Design review until 4:00 PM, so I told her: "Maya is in a meeting until 4. She'll answer you after." Work details stay private.</span>
          <div class="sk-acts"><button type="button" class="share-btn primary" data-share>Yes, at 6 PM</button><button type="button" class="share-btn" data-share>I'll call her at 4</button><button type="button" class="share-btn" data-share>Not this week</button></div></div></div></div>
    </div>
    <div class="sk-box"><span>Message #design-team</span><span class="grow"></span>${ic("send", 14)}</div>
  </div></div>`;

const PHOTOS = [["flyer", "Leo's science fair flyer", "This week"], ["itinerary", "Seattle trip confirmation", "This week"], ["office", "Maya's team room", "This week"],
  ["train", "The train along the coast", "Sun, Nov 1"], ["skyline", "LA at golden hour", "Sun, Nov 1"], ["garden", "Tomatoes from Mom's garden", "Sun, Nov 1"]];
const photos = () => {
  const days = [...new Set(PHOTOS.map((p) => p[2]))];
  return `<div class="app gp"><div class="gp-top"><div class="gp-search">${ic("eye")}<span>Search your photos</span></div><span class="gp-sel" data-count>2 selected</span><button type="button" class="share-btn primary" data-share data-photos>Share 2 to the Studio</button></div>
    <div class="gp-feed">${days.map((d) => `<div class="gp-day"><b>${d}</b><div class="gp-grid">${PHOTOS.filter((p) => p[2] === d).map(([f, title], i) =>
      `<button type="button" class="photo${i < 2 && d === days[0] ? " on" : ""}" aria-pressed="${i < 2 && d === days[0]}" aria-label="${esc(title)}"><img src="/assets/demo/photos/chen/${f}.jpg" alt="" loading="lazy"><span class="ck">${ic("check", 12)}</span></button>`).join("")}</div></div>`).join("")}</div></div>`;
};

const ZOOM = [
  ["Today", [["1:00 PM", "1:30 PM", "1:1 with Priya", "Priya Shah", "812 •••• 4417", "work"], ["3:00 PM", "4:00 PM", "Q4 design review", "Design team (14)", "905 •••• 2260", "work"],
             ["6:30 PM", "7:00 PM", "Weekly call with Mom", "Maya, Linda, Leo", "771 •••• 0938", "family"]]],
  ["Tue, Nov 10", [["10:00 AM", "11:30 AM", "Seattle offsite: kickoff", "Northwind leads", "640 •••• 1182", "work"]]],
];
const zoom = () => `<div class="app zm"><div class="zm-top"><b>Meetings</b><span class="zm-tabs"><span class="on">Upcoming</span><span>Previous</span><span>Personal room</span></span><span class="grow"></span><span class="zm-busy"><i class="pr busy"></i>Busy until 4:00 PM</span><span class="zm-new">${ic("calendar", 14)}Schedule</span></div>
  <div class="zm-feed">${ZOOM.map(([day, list]) => `<div class="zm-day">${esc(day)}</div>${list.map(([a, b, topic, who, id, kind]) => `<div class="zm-row${kind === "work" ? " work" : ""}">
    <span class="zm-time"><b>${a}</b><small>${b}</small></span><span class="zm-info"><b>${esc(topic)}</b><small>Meeting ID ${id} · ${esc(who)}</small></span>
    ${kind === "family" ? `<button type="button" class="share-btn" data-share>Make a Join button for Mom</button>` : `<span class="chk">Work · Mom hears "in a meeting"</span>`}<span class="zm-start">Start</span></div>`).join("")}`).join("")}</div>
  <p class="zm-note">${ic("lock", 13)}Mom never sees a work meeting's name or link: only that you're busy, and until when.</p></div>`;

const notion = () => `<div class="app nt"><aside class="nt-side"><div class="nt-ws"><span>C</span><b>Chen family</b></div>
    <span class="nt-sec">Shared with RoleEdge</span><a class="on">${ic("document", 14)}Trip to Big Sur</a><a>${ic("document", 14)}Mom's weekly routine</a><a>${ic("food", 14)}Grandma's chicken soup</a><a>${ic("medicine", 14)}Pharmacy and refills</a></aside>
  <div class="nt-main"><div class="nt-bar"><small>Chen family / Trip to Big Sur</small><span class="grow"></span><small>Edited 2 days ago</small><button type="button" class="share-btn primary" data-share>Share this page</button></div>
    <h4>Trip to Big Sur</h4>
    <div class="nt-props"><span>${ic("calendar", 13)}Date</span><b>Saturday, November 14</b><span>${ic("person", 13)}Who</span><b>Maya, Mom, Leo</b></div>
    <ul><li>Maya picks Mom up at 9:00</li><li>Bring a warm jacket, her medicine and her walking stick</li><li>Lunch at the bakery in Carmel</li><li>Back home by 6:00</li></ul></div></div>`;

const later = (id, name, line) => `<div class="app empty"><span class="em">${brand(id, 24)}</span><b>${name} is coming next</b><p>${line}</p><button type="button" class="share-btn" disabled>Connect ${name}</button></div>`;

const APPS = [
  { id: "gmail", name: "Gmail", status: "live", tag: "Live · demo account", line: "Your work inbox: deliveries and trips Mom can hear about, work that stays yours",
    hint: "Mom's delivery questions are answered only from verified senders; work mail never reaches her.", list: gmail },
  { id: "slack", name: "Slack", status: "live", tag: "Live · demo account", line: "Your work Slack: your status tells Mom you're busy; her questions reach you here",
    hint: "One tap from a meeting, and she hears your answer in your voice.", list: slack },
  { id: "googlephotos", name: "Google Photos", status: "live", tag: "Live · demo account", line: "This week's album, ready to become a story in your words",
    hint: "Pick a few photos; Grandma gets a story read in your voice.", list: photos },
  { id: "zoom", name: "Zoom", status: "live", tag: "Live · demo account", line: "Your meetings tell RoleEdge when you're busy; a family call becomes one big Join button",
    hint: "Codes, links and work meeting names never reach Mom.", list: zoom },
  { id: "notion", name: "Notion", status: "live", tag: "Live", line: "Pages shared with the RoleEdge integration",
    hint: "A page becomes a fridge card, slides or a mind map.", list: notion },
  { id: "spotify", name: "Spotify", status: "next", tag: "Coming next", line: "Share a song from her life, with a note in your voice",
    hint: "Not connected yet.", list: () => later("spotify", "Spotify", "Share a song or a podcast, and she plays it with one big button after your note.") },
  { id: "line", name: "LINE", status: "next", tag: "Coming next", line: "The family group, explained, with scams flagged",
    hint: "Not connected yet.", list: () => later("line", "LINE", "Forward a message from the family group, or a suspicious one, and RoleEdge explains it.") },
];

function apps() {
  const rail = $(".br-rail"), list = $("#br-list"), bar = $("#br-bar"), box = $("#browser");
  rail.innerHTML = APPS.map((a, i) => `<button class="app-btn" role="tab" aria-selected="${i === 0}" data-app="${i}"><span class="am">${brand(a.id, 15)}</span><span class="nm">${esc(a.name)}</span><span class="st ${a.status}" title="${esc(a.tag)}"></span></button>`).join("");
  let cur = -1, paused = false, visible = false, raf = 0;
  const show = (i) => {
    cur = i;
    const a = APPS[i];
    $$(".app-btn", rail).forEach((b, k) => b.setAttribute("aria-selected", String(k === i)));
    $("#br-mark").innerHTML = brand(a.id, 20);
    $("#br-name").textContent = a.name;
    $("#br-line").textContent = a.line;
    const tag = $("#br-tag"); tag.className = `tag ${a.status === "next" ? "next" : "live"}`; tag.textContent = a.tag;
    $("#br-hint").textContent = a.hint;
    list.innerHTML = a.list();
    $$("[data-mark]", list).forEach((el) => { el.innerHTML = ICON.mark; });
  };
  // On a wide screen the browser is pinned and scrolling past it opens each connected app in turn (not the two that
  // are coming next); the bar shows how far along. Narrow screens just use the tabs.
  const track = $("#apps-track");
  const SCROLLED = APPS.filter((a) => a.status !== "next").length;
  const pinned = () => matchMedia("(min-width: 1101px)").matches && !reduce.matches;
  const progress = () => {
    const r = track.getBoundingClientRect(), room = r.height - box.offsetHeight;
    return room > 0 ? Math.min(1, Math.max(0, -r.top / room + 0.06)) : 0;
  };
  const loop = () => {
    raf = 0;
    if (!visible) return;
    if (pinned()) {
      const p = progress();
      bar.style.transform = `scaleX(${p})`;
      const k = Math.min(SCROLLED - 1, Math.floor(p * SCROLLED));
      if (k !== cur && !paused) show(k);
    }
    raf = requestAnimationFrame(loop);
  };
  rail.addEventListener("click", (e) => {
    const b = e.target.closest("[data-app]");
    if (!b) return;
    const k = +b.dataset.app;
    show(k);
    if (pinned() && k < SCROLLED) { // move the page to where scrolling would have opened it
      const r = track.getBoundingClientRect(), room = r.height - box.offsetHeight;
      scrollTo({ top: scrollY + r.top + ((k + 0.5) / SCROLLED - 0.06) * room, behavior: "smooth" });
    }
  });
  rail.addEventListener("keydown", (e) => {
    if (!["ArrowDown", "ArrowUp", "ArrowRight", "ArrowLeft"].includes(e.key)) return;
    e.preventDefault();
    const n = (cur + (e.key === "ArrowDown" || e.key === "ArrowRight" ? 1 : -1) + APPS.length) % APPS.length;
    show(n); $$(".app-btn", rail)[n].focus();
  });
  list.addEventListener("click", (e) => {
    const ph = e.target.closest(".photo");
    if (ph) {
      ph.classList.toggle("on"); ph.setAttribute("aria-pressed", String(ph.classList.contains("on")));
      const n = $$(".photo.on", list).length, b = $("[data-photos]", list);
      $("[data-count]", list).textContent = `${n} selected`;
      b.textContent = n ? `Share ${n} to the Studio` : "Pick photos"; b.disabled = !n; b.classList.remove("done");
      return;
    }
    const b = e.target.closest("[data-share]");
    if (!b || b.disabled) return;
    b.classList.add("done"); b.textContent = "Shared to the Studio";
  });
  box.addEventListener("focusin", () => { paused = true; }); box.addEventListener("focusout", () => { paused = false; });
  show(0);
  if (reduce.matches) return;
  whenVisible(track, (v) => { visible = v; if (v && !raf) raf = requestAnimationFrame(loop); });
}

// ------------------------------------------------------------------ the comparison, by category (no company names)
const COLS = ["us", "watch", "wear", "robot", "tablet", "chat"];
const ROWS = [
  ["Notices change over weeks, against her own usual", "meals, sleep, going out, voice pace and more", "y p n p n n"],
  ["Turns what you share into something she can follow", "mind maps, slides, a quiz, a short video", "y n n n n n"],
  ["Speaks with your face and in your words", "only inside the app, with consent", "y n n n p p"],
  ["Answers her while you're busy, by your rules", "from your mail and apps, with what you allow", "y n n p n n"],
  ["Blocks scams, money requests and fake courier mail", "in code, before she sees them", "y n n n n p"],
  ["Brings the grandchildren in, with a child model", "the family relay and a line-by-line check", "y n n n p p"],
  ["Alerts you at once to an emergency", "red flags in what she says; not a sensor", "p p y p p n"],
  ["Needs no new device in her home", "works on the phone she has", "y p n n n y"],
];
function compare() {
  const label = { y: "Does this", p: "Partly", n: "Doesn't" };
  $("#cmp tbody").innerHTML = ROWS.map(([what, detail, marks], r) => `<tr><td>${esc(what)}<small>${esc(detail)}</small></td>${marks.split(" ").map((m, c) =>
    `<td class="${COLS[c] === "us" ? "us" : ""}"><span class="v ${m}" role="img" aria-label="${label[m]}" style="--d:${(r * 0.05 + c * 0.04).toFixed(2)}s"></span></td>`).join("")}</tr>`).join("");
}

// ------------------------------------------------------------------ the roadmap line fills as you scroll past
function roadmap() {
  const road = $("#road"), line = $(".road-line b", road);
  if (reduce.matches) { line.style.setProperty("--p", 1); return; }
  let on = false;
  const tick = () => {
    if (!on) return;
    const r = road.getBoundingClientRect();
    line.style.setProperty("--p", Math.min(1, Math.max(0, (innerHeight * 0.8 - r.top) / (r.height * 0.9))).toFixed(3));
    requestAnimationFrame(tick);
  };
  whenVisible(road, (v) => { on = v; if (v) requestAnimationFrame(tick); });
}

// ------------------------------------------------------------------ dark to light and back: each dark section fades in from,
// and out to, the colour of the section beside it, so the page dims and brightens instead of cutting
function fades() {
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

// ------------------------------------------------------------------ the phones' status bars: the visitor's own time
function clocks() {
  const set = () => {
    const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
    $$(".ip-status > b").forEach((b) => { b.textContent = now; });
  };
  set();
  setInterval(set, 15000);
}

// ------------------------------------------------------------------ start
async function start() {
  splitHeadline();
  await hydrate();
  compare();
  reveals();
  fades(); fields(); clocks(); nav(); pointer(); heroLoop(); stages(); outputs(); scan(); kids(); apps(); roadmap();
  field($("#hero-canvas"));
  field($("#cta-canvas"), { gap: 20, line: false });
  document.documentElement.classList.add("ready");
}
start();
