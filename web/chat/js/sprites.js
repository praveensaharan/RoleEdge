// ES module: import { Pixel } from "./sprites.js";

// Pixel-art sprites, drawn as crisp SVG from character grids ('.' = transparent).
// Render at integer multiples of the grid width (cat: 16 cols -> 32px, 64px, 160px) so
// every pixel stays sharp.

export const Pixel = (() => {
  const INK = "#25282b", RED = "#e60000", WHITE = "#ffffff", PINK = "#ff8a80", GREY = "#bebebe";

  // Sitting cat, front view. Base layer has closed eyes (lids 'G'); the "eyes" layer
  // draws them open on top, and CSS hides that layer for a moment to blink.
  const CAT_ROWS = [
    "...B........B...",
    "..BIB......BIB..",
    "..BIIB....BIIB..",
    "..BBBBBBBBBBBB..",
    ".BBBBBBBBBBBBBB.",
    ".BBBBBBBBBBBBBB.",
    ".BBGGBBBBBBGGBB.",
    ".BBBBBBNNBBBBBB.",
    ".BCCBBBBBBBBCCB.",
    "..BBBBBBBBBBBB.B",
    "...LLLLLLLLLL..B",
    "...BBBBTTBBBB..B",
    "..BBBBBBBBBBBB.B",
    "..BBBBBBBBBBBBBB",
    "..BFFBBBBBBFFBB.",
  ];
  const CAT_EYES = { cls: "px-eyes", y: 5, rows: ["...EE......EE...", "...EO......EO..."] };

  const DEFS = {
    cat: { rows: CAT_ROWS, layers: [CAT_EYES] },
    catHead: { rows: CAT_ROWS.slice(0, 9).map((r) => r.slice(0, 16)), layers: [CAT_EYES] },
    logo: {
      rows: [
        "W.......W",
        "WW.....WW",
        "WWWWWWWWW",
        "WW.WWW.WW",
        "WWWW.WWWW",
        "WWWWWWWWW",
        ".WWWWWWW.",
      ],
    },
    sparkle: {
      rows: ["...R...", "...R...", "..RWR..", "RRWWWRR", "..RWR..", "...R...", "...R..."],
    },
    diamond: {
      rows: ["...R...", "..RRR..", ".RRRRR.", "RRRRRRR", ".RRRRR.", "..RRR..", "...R..."],
    },
    bulb: {
      rows: [
        "....KKKK....",
        "..KKRRRRKK..",
        ".KRRWWRRRRK.",
        ".KRWRRRRRRK.",
        "KRWRRRRRRRRK",
        "KRRRRRRRRRRK",
        ".KRRRRRRRRK.",
        "..KRRRRRRK..",
        "...KKKKKK...",
        "...KGGGGK...",
        "...KKKKKK...",
        "....KGGK....",
      ],
    },
    image: {
      rows: [
        "............",
        "KKKKKKKKKKKK",
        "KWWWWWWWWWWK",
        "KWWWWWWWRRWK",
        "KWWWWWWWRRWK",
        "KWWWWWWWWWWK",
        "KWWWGWWWWWWK",
        "KWWGGGWWWGWK",
        "KWGGGGGWGGGK",
        "KKKKKKKKKKKK",
        "............",
        "............",
      ],
    },
    mic: {
      rows: [
        "....KKKK....",
        "...KRRRRK...",
        "...KRRRRK...",
        "...KRRRRK...",
        ".K.KRRRRK.K.",
        ".K.KRRRRK.K.",
        ".K..KKKK..K.",
        "..K......K..",
        "...KKKKKK...",
        ".....KK.....",
        ".....KK.....",
        "...KKKKKK...",
      ],
    },
    chart: {
      rows: [
        "............",
        "K...........",
        "K........RR.",
        "K........RR.",
        "K....KK..RR.",
        "K....KK..RR.",
        "K.GG.KK..RR.",
        "K.GG.KK..RR.",
        "K.GG.KK..RR.",
        "KKKKKKKKKKKK",
        "............",
        "............",
      ],
    },
    arrow: {
      rows: [
        "....W....",
        "...WWW...",
        "..WWWWW..",
        ".WW.W.WW.",
        "....W....",
        "....W....",
        "....W....",
        "....W....",
        "....W....",
      ],
    },
    bang: { rows: ["WW", "WW", "WW", "WW", "..", "WW"] },
  };

  const PALETTES = {
    // ink cat for light surfaces
    dark: { B: INK, I: RED, G: GREY, E: WHITE, O: INK, N: RED, C: PINK, L: RED, T: GREY, F: WHITE },
    // white cat for the ink sidebar
    light: { B: WHITE, I: PINK, G: INK, E: INK, O: WHITE, N: RED, C: PINK, L: RED, T: WHITE, F: GREY },
    icon: { K: INK, R: RED, W: WHITE, G: GREY },
    onRed: { W: WHITE, R: WHITE },
  };

  function rects(rows, palette, dy = 0) {
    let out = "";
    rows.forEach((row, y) => {
      for (let x = 0; x < row.length;) {
        const ch = row[x];
        if (!(ch in palette)) { x++; continue; }
        let w = 1;
        while (row[x + w] === ch) w++;
        out += `<rect x="${x}" y="${y + dy}" width="${w}" height="1.02" fill="${palette[ch]}"/>`;
        x += w;
      }
    });
    return out;
  }

  /** Return an <svg> string for sprite `name`. opts: {palette, cls, label}. */
  function svg(name, { palette = "icon", cls = "", label = "" } = {}) {
    const def = DEFS[name];
    const pal = { W: WHITE, R: RED, K: INK, G: GREY, ...(PALETTES[palette] || palette) };
    const w = Math.max(...def.rows.map((r) => r.length));
    const h = def.rows.length;
    let body = rects(def.rows, pal);
    for (const layer of def.layers || []) body += `<g class="${layer.cls}">${rects(layer.rows, pal, layer.y)}</g>`;
    const a11y = label ? `role="img" aria-label="${label}"` : `aria-hidden="true"`;
    return `<svg class="px px-${name} ${cls}" viewBox="0 0 ${w} ${h}" shape-rendering="crispEdges" ${a11y}>${body}</svg>`;
  }

  /** Replace every <i data-px="name" data-palette=".." data-cls=".."> placeholder in root. */
  function hydrate(root = document) {
    for (const el of root.querySelectorAll("i[data-px]")) {
      el.outerHTML = svg(el.dataset.px, { palette: el.dataset.palette || "icon", cls: el.dataset.cls || "",
                                          label: el.dataset.label || "" });
    }
  }

  return { svg, hydrate };
})();
