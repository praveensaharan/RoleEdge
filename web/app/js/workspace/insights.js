// The two side tabs and the spend meter: how she's doing (the trend engine, against her own usual weeks) and
// activity (every step an agent or a check took, and the Meta spend estimate from the ledger).
import { api, esc } from "../common.js";
import { $, clock, state } from "./shared.js";

const LEVEL = {
  steady: ["Steady", "Her everyday life looks like her usual weeks."],
  small_change: ["A small change", "One part of her everyday life has changed over the last two weeks."],
  sustained_change: ["A sustained change", "Two parts of her everyday life have changed for two weeks."],
  worth_a_visit: ["Worth a visit", "Several parts of her everyday life have changed for two weeks."],
};

let usageTimer = null;
/** Refresh the top-bar meter, at most once per burst of live events. */
export function refreshUsage() {
  clearTimeout(usageTimer);
  usageTimer = setTimeout(async () => {
    const s = await api("/api/spend").catch(() => null);
    if (!s) return;
    const usedPct = Math.min(100, (s.meta_usd / s.meta_budget_usd) * 100);
    $("usage").innerHTML = `<span class="live-dot"></span><span class="lbl">Meta</span> <b class="dm">$${s.meta_usd.toFixed(4)}</b><span class="lbl"> / $${s.meta_budget_usd.toFixed(0)}</span>`
      + `<span class="bar" role="meter" aria-label="Meta credits used" aria-valuenow="${usedPct.toFixed(1)}" aria-valuemin="0" aria-valuemax="100"><b style="width:${Math.max(1.5, usedPct)}%"></b></span>`;
  }, 300);
}

export async function renderTrends() {
  const circleId = state.circle.id;
  let r;
  try { r = await api(`/api/circles/${circleId}/trends`); }
  catch (err) { $("tab-trends").innerHTML = `<div class="empty">The trends couldn't be loaded: ${esc(err.message)}</div>`; return; }
  if (state.circle.id !== circleId) return; // you switched circles while it loaded
  const [title, line] = LEVEL[r.level] || [r.level, ""];
  const flagged = r.lines.filter((l) => l.flagged).length;
  const lines = [...r.lines].sort((a, b) => b.flagged - a.flagged);
  const max = Math.max(1, ...r.lines.map((l) => Math.max(l.baseline, l.recent)));
  const row = (l) => `<div class="row${l.flagged ? " flag" : ""}"><div><b>${esc(l.label)}</b><small>${esc(l.unit)}${l.flagged ? " · changed" : ""}</small></div>
    <div class="bar2"><b style="width:${Math.round((l.recent / max) * 100)}%"></b></div><div class="num">${l.baseline} → ${l.recent}</div>
    ${l.evidence.length ? `<div class="ev">${l.evidence.slice(0, 2).map((ev) => `<div><span>${esc(ev.day)}</span>“${esc(ev.quote)}”</div>`).join("")}</div>` : ""}</div>`;
  $("tab-trends").innerHTML = `
    <div class="tiles"><div class="tile feature"><small>Overall</small><b>${esc(title)}</b><span>${esc(line)}</span></div>
      <div class="tile"><small>Signals changed</small><b>${flagged} of ${r.lines.length}</b><span>last two weeks vs her own usual</span></div>
      <div class="tile"><small>Compared with</small><b>${r.baseline_days} days</b><span>of her own history</span></div></div>
    <div class="steps-box"><h3>What the family can do</h3><ul>${r.family_steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ul></div>
    <div class="rows">${lines.map(row).join("")}</div>
    ${r.resources.length ? `<div class="note-box">${r.resources.map((x) => `<div><b class="ink">${esc(x.label)}</b>${x.detail ? ` · ${esc(x.detail)}` : ""}</div>`).join("")}</div>` : ""}
    <div class="note-box">Observations only: changes in what she told you and how she sounded, against her own usual weeks. RoleEdge doesn't diagnose or give medical advice. Computed by code from ${r.lines.length} signals, as of ${esc(r.as_of)}.</div>`;
}

let permissionLabels = null;

/** What the assistant may do for her without asking you, with a way to stop each. */
async function allowedList() {
  permissionLabels ||= await api("/api/permissions").catch(() => ({}));
  const keys = Object.keys(state.circle.permissions || {});
  const rows = keys.map((k) => `<div class="row"><div><b>${esc(permissionLabels[k] || k)}</b><small>allowed always</small></div>
    <div></div><button type="button" class="btn ghost sm" data-stop="${esc(k)}">Stop</button></div>`).join("");
  return `<div class="steps-box allowed"><h3>Allowed without asking</h3>${rows ? `<div class="rows">${rows}</div>`
    : `<p>Nothing yet. The first time she asks for something that needs your mail or your money, you're asked; choose Always allow and she's answered straight away after that.</p>`}
    <p class="small">Price checks are always on (the "watch prices" routine). Orders above your limit ask you every time.</p></div>`;
}

export async function renderActivity() {
  const s = await api("/api/spend").catch(() => null);
  const steps = state.items.flatMap((i) => i.trace.map((t) => ({ ...t, at: i.at }))).reverse();
  const tiles = s ? `<div class="tiles"><div class="tile feature"><small>Meta spend</small><b class="meter-num">$${s.meta_usd.toFixed(4)}</b><span>${s.meta_calls} model calls · estimate from tokens</span></div>
    <div class="tile"><small>Left this hackathon</small><b class="meter-num">$${s.meta_left_usd.toFixed(2)}</b><span>of $${s.meta_budget_usd.toFixed(0)} in credits</span></div>
    <div class="tile"><small>Per Studio share</small><b class="meter-num">${s.meta_by_task.studio ? "< 1¢" : "—"}</b><span>research, plan and the moments</span></div></div>` : "";
  const row = (t) => `<div class="row"><div><b>${esc(t.step)}</b><small>${clock(t.at)}${t.replayed ? " · replayed from cache" : ""}</small></div>
    <div class="num left">${esc(t.engine)}</div><div class="num">${t.latency_s ? `${t.latency_s}s` : ""}</div></div>`;
  $("tab-activity").innerHTML = tiles + await allowedList() + (steps.length ? `<div class="rows">${steps.slice(0, 60).map(row).join("")}</div>`
    : `<div class="empty">Every step an agent or a check takes is listed here, with the model that ran it.</div>`);
}
