// Element lookups, done once. Modules load after the HTML is parsed, so the elements exist.

export const $ = (id) => document.getElementById(id);

export const els = {
  model: $("model"), effort: $("effort"), providerChip: $("providerChip"), speak: $("speak"),
  newChat: $("newChat"), log: $("log"), empty: $("empty"), system: $("system"), greeting: $("greeting"),
  composer: $("composer"), thumbs: $("thumbs"), attach: $("attach"), file: $("file"),
  mic: $("mic"), input: $("input"), send: $("send"), hint: $("hint"), toast: $("toast"),
  menu: $("menu"), scrim: $("scrim"),
};

/** Grow the message box with its content, up to a limit. */
export function autoGrow() {
  els.input.style.height = "auto";
  els.input.style.height = `${Math.min(els.input.scrollHeight, 220)}px`;
}
