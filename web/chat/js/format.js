// Number and text formatting helpers.

/** 1284 -> "1,284" */
export const fmt = (n) => Number(n || 0).toLocaleString();

/** 12873 -> "12.9K" (for big stat tiles; the exact value goes in a tooltip) */
export const compact = (n) =>
  new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(n || 0);

const HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

/** Escape text before putting it into innerHTML. */
export const escapeHtml = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);

/** Share of a total as a whole percentage (0 when the total is 0). */
export const percent = (part, total) => (total ? Math.round((part / total) * 100) : 0);
