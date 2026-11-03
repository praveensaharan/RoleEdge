// Entry point: wire the page together. Each feature lives in its own module:
//   model-picker  chat  messages  usage-panel  attachments  voice  markdown  sprites  toast

import { initAttachments, openFilePicker } from "./attachments.js";
import { newChat, send } from "./chat.js";
import { autoGrow, els } from "./dom.js";
import { addError } from "./messages.js";
import { initModelPicker, loadModels } from "./model-picker.js";
import { Pixel } from "./sprites.js";
import { prefs } from "./state.js";
import { toast } from "./toast.js";
import { updateUsagePanel } from "./usage-panel.js";
import { initVoice, startListening } from "./voice.js";

function greet() {
  const h = new Date().getHours();
  els.greeting.textContent = h < 5 ? "Up late?" : h < 12 ? "Good morning." : h < 18 ? "Good afternoon." : "Good evening.";
}

function initSettings() {
  els.speak.checked = prefs.get("speak") === "1";
  els.speak.addEventListener("change", () => prefs.set("speak", els.speak.checked ? "1" : "0"));
  els.system.value = prefs.get("system");
  els.system.addEventListener("input", () => prefs.set("system", els.system.value));
}

function initComposer() {
  els.send.addEventListener("click", send);
  els.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); }
  });
  els.input.addEventListener("input", autoGrow);
}

function initSidebar() {
  els.menu.addEventListener("click", () => document.body.classList.add("sidebar-open"));
  els.scrim.addEventListener("click", () => document.body.classList.remove("sidebar-open"));
  els.newChat.addEventListener("click", () => {
    newChat();
    document.body.classList.remove("sidebar-open");
    greet();
    els.input.focus();
  });
}

/** Welcome-screen cards either fill in a prompt or start an action. */
function initSuggestions() {
  for (const card of document.querySelectorAll(".suggestions .card")) {
    card.addEventListener("click", () => {
      if (card.dataset.action === "attach") return openFilePicker();
      if (card.dataset.action === "mic") return els.mic.disabled ? toast(els.mic.title) : startListening();
      els.input.value = card.dataset.prompt;
      autoGrow();
      els.input.focus();
    });
  }
}

Pixel.hydrate();
greet();
initSettings();
initComposer();
initSidebar();
initSuggestions();
initAttachments();
initVoice();
initModelPicker();
updateUsagePanel(null);
loadModels().catch((e) => addError(`Could not load models: ${e.message}`));
els.input.focus();
