// Rendering of chat messages: user bubbles, Saathi replies with usage chips, thinking, errors.

import { els } from "./dom.js";
import { escapeHtml, fmt, percent } from "./format.js";
import { renderMarkdown } from "./markdown.js";
import { Pixel } from "./sprites.js";
import { toast } from "./toast.js";
import { speak } from "./voice.js";

function append(node) {
  els.empty.hidden = true;
  els.log.appendChild(node);
  els.log.scrollTop = els.log.scrollHeight;
  return node;
}

/** A Saathi row: cat avatar + body. Returns {wrap, body}. */
function assistantRow(cls, avatarSprite = "catHead", palette = "dark") {
  const wrap = document.createElement("div");
  wrap.className = `msg assistant ${cls}`.trim();
  wrap.innerHTML = `<div class="avatar">${Pixel.svg(avatarSprite, { palette })}</div><div class="assistant-body"></div>`;
  return { wrap, body: wrap.querySelector(".assistant-body") };
}

const header = (provider, model, effort) =>
  `<div class="who">Muse <span class="model">${[provider, model, effort].filter(Boolean).map(escapeHtml).join(" · ")}</span></div>`;

export function addUserMessage(text, images) {
  const wrap = document.createElement("div");
  wrap.className = "msg user";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (images.length) {
    const row = document.createElement("div");
    row.className = "imgs";
    for (const src of images) {
      const img = new Image();
      img.src = src;
      img.alt = "attached image";
      row.appendChild(img);
    }
    bubble.appendChild(row);
  }
  if (text) bubble.appendChild(document.createTextNode(text));
  wrap.appendChild(bubble);
  return append(wrap);
}

export function addThinking(providerLabel, model) {
  const { wrap, body } = assistantRow("thinking");
  body.innerHTML = `${header(providerLabel, model)}
    <div class="thinking-line">${Pixel.svg("sparkle", { cls: "spin" })}<span>Thinking</span>
      <span class="dots"><i></i><i></i><i></i></span></div>`;
  return append(wrap);
}

/** @param {{text, usage, model, note, latency_s, effort, providerLabel}} reply */
export function addAssistantMessage(reply) {
  const { wrap, body } = assistantRow("");
  const u = reply.usage;
  const cachedPct = percent(u.cached, u.input);
  body.innerHTML = `${header(reply.providerLabel, reply.model, reply.effort)}
    <div class="content">${renderMarkdown(reply.text || "(empty reply)")}</div>
    <div class="usage">
      <span class="chip" title="Input tokens sent this turn — the whole conversation is resent each turn">in ${fmt(u.input)}</span>
      <span class="chip cache" title="Input tokens served from the provider's prompt cache">cached ${fmt(u.cached)} · ${cachedPct}%
        <span class="mini-meter"><span style="width:${cachedPct}%"></span></span></span>
      <span class="chip" title="Output tokens, including hidden reasoning">out ${fmt(u.output)} · reasoning ${fmt(u.reasoning)}</span>
      <span class="chip" title="Round-trip time">${reply.latency_s}s</span>
      ${reply.note ? `<span class="chip note">${escapeHtml(reply.note)}</span>` : ""}
      <span class="spacer"></span>
      <button class="act" data-act="speak" title="Read aloud">Read aloud</button>
      <button class="act" data-act="copy" title="Copy reply">Copy</button>
    </div>`;
  body.querySelector('[data-act="speak"]').onclick = () => speak(reply.text);
  body.querySelector('[data-act="copy"]').onclick = async () => {
    try { await navigator.clipboard.writeText(reply.text); toast("Copied to clipboard"); }
    catch { toast("Copy isn't available here"); }
  };
  return append(wrap);
}

export function addError(message) {
  const { wrap, body } = assistantRow("error", "bang", "onRed");
  body.innerHTML = `<div class="who">Muse</div><div class="content"><b>Something went wrong.</b> Your message is back in the box — try again or switch models.\n\n${escapeHtml(message)}</div>`;
  return append(wrap);
}

export function clearMessages() {
  for (const el of [...els.log.querySelectorAll(".msg")]) el.remove();
  els.empty.hidden = false;
}
