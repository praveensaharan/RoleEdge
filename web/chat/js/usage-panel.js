// Sidebar token-usage panel: session totals, cache-hit meter, last turn.

import { $ } from "./dom.js";
import { compact, fmt, percent } from "./format.js";
import { state } from "./state.js";

function setStat(id, n) {
  $(id).textContent = compact(n);
  $(id).title = fmt(n);  // exact number on hover
}

/** @param {{input: number, cached: number, output: number}|null} last  usage of the latest turn */
export function updateUsagePanel(last) {
  const t = state.totals;
  const hit = percent(t.cached, t.input);
  setStat("sIn", t.input);
  setStat("sOut", t.output);
  setStat("sReason", t.reasoning);
  setStat("sCached", t.cached);
  setStat("sReq", t.requests);

  $("sHit").textContent = t.input ? `${hit}%` : "–";
  $("sHitBar").style.width = `${hit}%`;
  $("sHitMeter").setAttribute("aria-valuenow", String(hit));
  $("sCachedLine").textContent = t.cached
    ? `${fmt(t.cached)} of ${fmt(t.input)} input tokens cached`
    : t.input ? "Nothing cached yet — caching kicks in on long, repeated prompts" : "No cached tokens yet";
  $("sLast").textContent = last
    ? `Last turn: in ${fmt(last.input)} · cached ${fmt(last.cached)} · out ${fmt(last.output)}`
    : "Last turn: –";
}
