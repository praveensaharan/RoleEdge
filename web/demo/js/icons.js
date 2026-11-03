// Line icons, loaded once from /api/demo/icons: the same table the cards and videos use
// (src/carecircle/render/icons.py), so there is one icon set for the whole product.

const SVG = "http://www.w3.org/2000/svg";
let ICONS = {};

export async function loadIcons() {
  const response = await fetch("/api/demo/icons");
  if (response.ok) ICONS = await response.json();
}

/** An <svg> for the named icon (stroke = currentColor). Icon markup comes from our server, never from model text. */
export function icon(name, size = 18, stroke = 1.75) {
  const svg = document.createElementNS(SVG, "svg");
  for (const [key, value] of Object.entries({ width: size, height: size, viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", "stroke-width": stroke, "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" })) {
    svg.setAttribute(key, value);
  }
  svg.innerHTML = ICONS[name] || ICONS.info || "";
  return svg;
}

/** The CareCircle mark: two linked circles, an older and a younger generation. */
export function logoMark(size = 28) {
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("width", size);
  svg.setAttribute("height", Math.round(size * .75));
  svg.setAttribute("viewBox", "0 0 32 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("aria-hidden", "true");
  svg.innerHTML = '<circle cx="11" cy="12" r="8" stroke="var(--brand)" stroke-width="3"/>' +
    '<circle cx="21" cy="12" r="8" stroke="currentColor" stroke-width="3"/>';
  return svg;
}
