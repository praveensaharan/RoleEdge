// A small Markdown subset for replies: fenced code, inline code, bold, italics, headings,
// bullet and numbered lists, paragraphs. All text is escaped first.

import { escapeHtml } from "./format.js";

const PLACEHOLDER = /\u0000(\d+)\u0000/g;

const inline = (s) => escapeHtml(s)
  .replace(/`([^`]+)`/g, "<code>$1</code>")
  .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
  .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");

export function renderMarkdown(src) {
  // Pull code blocks out first so nothing inside them is formatted.
  const blocks = [];
  src = src.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, _lang, code) => {
    blocks.push(`<pre><code>${escapeHtml(code.replace(/\n$/, ""))}</code></pre>`);
    return `\u0000${blocks.length - 1}\u0000`;
  });

  const out = [];
  let list = null;
  const closeList = () => { if (list) { out.push(`</${list}>`); list = null; } };
  const openList = (tag) => { if (list !== tag) { closeList(); out.push(`<${tag}>`); list = tag; } };

  for (const para of src.split(/\n{2,}/)) {
    let lines = [];
    const flush = () => { if (lines.length) { out.push(`<p>${lines.join("<br>")}</p>`); lines = []; } };
    for (const line of para.split("\n")) {
      let m;
      if ((m = line.match(/^\u0000(\d+)\u0000$/))) { flush(); closeList(); out.push(blocks[+m[1]]); }
      else if ((m = line.match(/^(#{1,6})\s+(.*)/))) { flush(); closeList(); out.push(`<h3>${inline(m[2])}</h3>`); }
      else if ((m = line.match(/^\s*[-*]\s+(.*)/))) { flush(); openList("ul"); out.push(`<li>${inline(m[1])}</li>`); }
      else if ((m = line.match(/^\s*\d+[.)]\s+(.*)/))) { flush(); openList("ol"); out.push(`<li>${inline(m[1])}</li>`); }
      else { closeList(); lines.push(inline(line).replace(PLACEHOLDER, (_, i) => blocks[+i])); }
    }
    flush();
    closeList();
  }
  return out.join("");
}
