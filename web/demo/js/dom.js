// Small DOM and timing helpers. Story text always goes in with textContent (rule S9: model text is escaped).

const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
let instant = false; // true while jumping straight to the end of a flow

export const setInstant = (value) => { instant = value; };
export const fast = () => instant || reducedMotion.matches;

/** el("div", "b me", "text", node) -> <div class="b me">text…</div>. */
export function el(tag, cls = "", ...children) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  for (const child of children) if (child != null && child !== false) node.append(child);
  return node;
}

export const wait = (ms) => (fast() ? Promise.resolve() : new Promise((done) => setTimeout(done, ms)));

/** Web Animations API with a reduced-motion path: skip straight to the end state. */
export function animate(node, keyframes, options = {}) {
  if (fast()) return Promise.resolve();
  return node.animate(keyframes, { duration: 360, easing: "cubic-bezier(.2,.8,.2,1)", fill: "both", ...options })
    .finished.catch(() => {});
}

/** Append with a short fade-up, keep at most `keep` children, resolve when it has landed. */
export function enter(parent, node, keep = 6) {
  parent.append(node);
  while (parent.children.length > keep) parent.firstElementChild.remove();
  return animate(node, [{ opacity: 0, transform: "translateY(8px)" }, { opacity: 1, transform: "none" }]);
}

/** Type text into a node letter by letter (instant when motion is off). */
export async function typeText(node, text, perChar = 14) {
  if (fast()) { node.textContent = text; return; }
  node.textContent = "";
  node.classList.add("typing");
  for (const char of text) { node.textContent += char; await wait(perChar); }
  node.classList.remove("typing");
}

/** Move a small labelled pill (e.g. "Instagram reel") from one element to another, then remove it. */
export async function travel(pill, from, to, duration = 850) {
  if (fast() || !from || !to) return;
  const a = from.getBoundingClientRect(), b = to.getBoundingClientRect();
  pill.classList.add("travel");
  document.body.append(pill);
  const start = { x: a.left + a.width / 2, y: a.top + a.height / 2 }, end = { x: b.left + b.width / 2, y: b.top + Math.min(b.height / 2, 120) };
  Object.assign(pill.style, { left: `${start.x}px`, top: `${start.y}px` });
  await animate(pill, [
    { transform: "translate(-50%, -50%) scale(.9)", opacity: 0 },
    { transform: "translate(-50%, -50%) scale(1)", opacity: 1, offset: .15 },
    { transform: `translate(calc(-50% + ${end.x - start.x}px), calc(-50% + ${end.y - start.y}px)) scale(1)`, opacity: 1, offset: .85 },
    { transform: `translate(calc(-50% + ${end.x - start.x}px), calc(-50% + ${end.y - start.y}px)) scale(.9)`, opacity: 0 },
  ], { duration, easing: "cubic-bezier(.4,0,.2,1)" });
  pill.remove();
}

/** A tap ring over `target`, inside its phone screen. */
export async function tap(target) {
  const screen = target?.closest(".screen");
  if (!screen) return;
  const s = screen.getBoundingClientRect(), t = target.getBoundingClientRect();
  const ring = el("span", "tap");
  Object.assign(ring.style, { left: `${t.left - s.left + t.width / 2}px`, top: `${t.top - s.top + t.height / 2}px` });
  screen.append(ring);
  await animate(ring, [{ transform: "scale(.5)", opacity: 1 }, { transform: "scale(1.5)", opacity: 0 }], { duration: 600 });
  ring.remove();
}
