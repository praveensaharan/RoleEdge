// Model dropdown (grouped by provider) and the reasoning-effort chips.

import { fetchModels } from "./api.js";
import { els } from "./dom.js";
import { prefs, state } from "./state.js";

const CONTRIBUTOR_NOTE = " · trains on your data";

/** {provider, model} for the current selection. Option values look like "azure|gpt5mini". */
export function currentModel() {
  const [provider, ...rest] = els.model.value.split("|");
  return { provider, model: rest.join("|") };
}

export async function loadModels() {
  const data = await fetchModels();
  els.model.innerHTML = "";
  for (const p of data.providers) {
    state.providers[p.id] = p;
    if (!p.models.length) continue;  // provider not configured
    const group = document.createElement("optgroup");
    group.label = p.label;
    for (const m of p.models) {
      const label = m.endsWith("-contributor") ? m + CONTRIBUTOR_NOTE : m;
      group.appendChild(new Option(label, `${p.id}|${m}`));
    }
    els.model.appendChild(group);
  }
  const saved = prefs.get("model");
  const options = [...els.model.options].map((o) => o.value);
  els.model.value = options.includes(saved) ? saved : `meta|${data.defaults.meta}`;
  if (!els.model.value && options.length) els.model.selectedIndex = 0;
  refreshModelUi();
}

/** Update the provider chip and the effort chips for the selected provider. */
export function refreshModelUi() {
  const { provider } = currentModel();
  const info = state.providers[provider];
  els.providerChip.textContent = info?.label || provider;
  els.providerChip.classList.toggle("azure", provider === "azure");

  const efforts = info?.efforts || ["low"];
  if (!efforts.includes(state.effort)) state.effort = "low";
  els.effort.innerHTML = "";
  for (const effort of efforts) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.textContent = effort;
    chip.setAttribute("role", "radio");
    chip.setAttribute("aria-checked", String(effort === state.effort));
    chip.onclick = () => {
      state.effort = effort;
      prefs.set("effort", effort);
      for (const other of els.effort.children) other.setAttribute("aria-checked", String(other === chip));
    };
    els.effort.appendChild(chip);
  }
}

export function initModelPicker() {
  els.model.addEventListener("change", () => {
    prefs.set("model", els.model.value);
    refreshModelUi();
  });
}
