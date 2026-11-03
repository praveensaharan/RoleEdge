// Voice: dictation (browser speech-to-text) and reading replies aloud (browser text-to-speech).
// Neither model API offers a transcription endpoint we can call yet, so this runs in the browser
// (Chrome/Edge/Safari). Chrome sends dictated audio to Google for recognition.

import { autoGrow, els } from "./dom.js";
import { toast } from "./toast.js";

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const DEFAULT_HINT = "Enter to send · Shift+Enter for a new line";

let recognizer = null;
let listening = false;

export const isListening = () => listening;

export function stopListening() {
  if (listening) recognizer.stop();
}

export function startListening() {
  if (!Recognition) return toast("Speech recognition isn't supported in this browser — try Chrome or Edge");
  if (listening) return;
  recognizer = new Recognition();
  recognizer.lang = navigator.language || "en-US";
  recognizer.interimResults = true;
  recognizer.continuous = true;

  const before = els.input.value ? `${els.input.value.trimEnd()} ` : "";
  let finalText = "";
  recognizer.onresult = (e) => {
    let interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const result = e.results[i];
      if (result.isFinal) finalText += result[0].transcript;
      else interim += result[0].transcript;
    }
    els.input.value = before + finalText + interim;
    autoGrow();
  };
  recognizer.onerror = (e) => {
    if (e.error === "not-allowed") toast("Microphone permission was denied");
    else if (e.error !== "no-speech" && e.error !== "aborted") toast(`Speech error: ${e.error}`);
  };
  recognizer.onend = () => {
    listening = false;
    els.mic.classList.remove("on");
    els.hint.textContent = DEFAULT_HINT;
  };
  recognizer.start();
  listening = true;
  els.mic.classList.add("on");
  els.hint.textContent = "Listening… click the mic again to stop";
}

/** Read text aloud with the browser's voice (code blocks are skipped). */
export function speak(text) {
  if (!("speechSynthesis" in window) || !text) return;
  speechSynthesis.cancel();
  const plain = text.replace(/```[\s\S]*?```/g, " code block. ").replace(/[*_#`>]/g, "");
  const utterance = new SpeechSynthesisUtterance(plain);
  utterance.lang = navigator.language || "en-US";
  speechSynthesis.speak(utterance);
}

export function stopSpeaking() {
  if ("speechSynthesis" in window) speechSynthesis.cancel();
}

export function initVoice() {
  if (!Recognition) {
    els.mic.disabled = true;
    els.mic.title = "Speech recognition isn't supported in this browser — try Chrome or Edge";
    return;
  }
  els.mic.addEventListener("click", () => (listening ? stopListening() : startListening()));
}
