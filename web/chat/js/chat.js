// The conversation: send a turn, show the reply and its usage, roll back on failure.

import { postChat } from "./api.js";
import { renderThumbs } from "./attachments.js";
import { autoGrow, els } from "./dom.js";
import { addAssistantMessage, addError, addThinking, addUserMessage, clearMessages } from "./messages.js";
import { currentModel } from "./model-picker.js";
import { addUsage, resetConversation, state } from "./state.js";
import { updateUsagePanel } from "./usage-panel.js";
import { isListening, speak, stopListening, stopSpeaking } from "./voice.js";

function setBusy(busy) {
  state.busy = busy;
  els.send.disabled = busy;
}

export async function send() {
  if (state.busy) return;
  const text = els.input.value.trim();
  if (!text && !state.pending.length) return;
  if (isListening()) stopListening();

  const { provider, model } = currentModel();
  const providerLabel = state.providers[provider]?.label || provider;
  const effort = state.effort;
  const userMsg = { role: "user", text, images: state.pending };

  state.history.push(userMsg);
  const userEl = addUserMessage(text, state.pending);
  els.input.value = "";
  state.pending = [];
  renderThumbs();
  autoGrow();
  setBusy(true);
  const thinking = addThinking(providerLabel, model);

  try {
    const reply = await postChat({ provider, model, effort, system: els.system.value, messages: state.history });
    thinking.remove();
    state.history.push({ role: "assistant", text: reply.text, images: [] });
    addAssistantMessage({ ...reply, effort, providerLabel });
    addUsage(reply.usage);
    updateUsagePanel(reply.usage);
    if (els.speak.checked) speak(reply.text);
  } catch (err) {
    // Put the failed turn back in the composer so it can be retried, e.g. on another model.
    thinking.remove();
    state.history.pop();
    userEl.remove();
    els.input.value = userMsg.text;
    state.pending = userMsg.images;
    renderThumbs();
    autoGrow();
    addError(err.message);
  } finally {
    setBusy(false);
    els.input.focus();
  }
}

export function newChat() {
  if (state.busy) return;
  resetConversation();
  clearMessages();
  updateUsagePanel(null);
  stopSpeaking();
}
