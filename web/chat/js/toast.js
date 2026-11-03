// Short, self-dismissing status message at the bottom of the screen.

import { els } from "./dom.js";

let timer = null;

export function toast(message, ms = 2200) {
  els.toast.textContent = message;
  els.toast.hidden = false;
  clearTimeout(timer);
  timer = setTimeout(() => { els.toast.hidden = true; }, ms);
}
