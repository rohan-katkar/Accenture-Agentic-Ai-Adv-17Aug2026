/* =====================================================================
   build_deck.js — renders a deck from a content module.
   Usage:  node _builders/build_deck.js content_day1.js Day1_Foundations/Day1_Deck.pptx
   ===================================================================== */

const path = require("path");
const pptxgen = require("pptxgenjs");

const contentFile = process.argv[2] || "content_day1.js";
const outPath = process.argv[3] || "Day1_Deck.pptx";
const { PALETTE: C, FONT: F, slides } = require(path.resolve(__dirname, contentFile));

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5 inches — set BEFORE adding slides
pres.author = "Training Architecture";
pres.title = "Accenture Batch 1 — Agentic AI Foundation";

const W = 13.33, H = 7.5, M = 0.7;

/* ---------- helpers (fresh option objects every call — pptxgenjs mutates) --- */
// Auto-shrink long titles. A 2-line title at 32pt overruns its 0.8" box and
// collides with the subtitle at y=1.22 on table/flow/code layouts. Rather than
// hand-tuning every string, scale the size to the length.
const titleSize = (text) => (text.length > 62 ? 24 : text.length > 44 ? 27 : 32);

const title = (s, text, colour = C.NAVY) =>
  s.addText(text, {
    x: M, y: 0.42, w: W - 2 * M, h: 0.78,
    fontFace: F.HEAD, fontSize: titleSize(text), bold: true,
    color: colour, valign: "top", margin: 0,
  });

const subtitle = (s, text, y = 1.22) =>
  s.addText(text, {
    x: M, y, w: W - 2 * M, h: 0.5,
    fontFace: F.BODY, fontSize: 14, color: C.MUTED, italic: true, margin: 0,
  });

const pageNum = (s, n) =>
  s.addText(String(n), {
    x: W - 1.0, y: H - 0.55, w: 0.5, h: 0.3,
    fontFace: F.BODY, fontSize: 10, color: C.LINE, align: "right", margin: 0,
  });

const circleIcon = (s, glyph, x, y, d, fill, txtColour = "FFFFFF", size = 16) => {
  s.addShape(pres.ShapeType.ellipse, { x, y, w: d, h: d, fill: { color: fill } });
  s.addText(glyph, {
    x, y, w: d, h: d, align: "center", valign: "middle",
    fontFace: F.HEAD, fontSize: size, bold: true, color: txtColour, margin: 0,
  });
};

const card = (s, x, y, w, h, fill) =>
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.08,
    fill: { color: fill },
    shadow: { type: "outer", angle: 90, blur: 8, offset: 1, opacity: 0.10, color: "000000" },
  });

/* ======================= layout renderers ================================= */
const render = {
  title(s, d) {
    s.background = { color: C.NAVY };
    s.addShape(pres.ShapeType.ellipse, {
      x: W - 3.4, y: -1.9, w: 5.6, h: 5.6, fill: { color: C.DEEP, transparency: 55 },
    });
    s.addShape(pres.ShapeType.ellipse, {
      x: W - 2.1, y: 3.5, w: 3.4, h: 3.4, fill: { color: C.TEAL, transparency: 62 },
    });
    s.addText(d.kicker, {
      x: M, y: 1.75, w: 8.4, h: 0.35, fontFace: F.BODY, fontSize: 12,
      bold: true, color: C.GOLD, charSpacing: 2, margin: 0,
    });
    s.addText(d.title, {
      x: M, y: 2.25, w: 8.6, h: 2.2, fontFace: F.HEAD, fontSize: 38,
      bold: true, color: "FFFFFF", lineSpacing: 44, margin: 0,
    });
    s.addText(d.subtitle, {
      x: M, y: 4.62, w: 8.4, h: 0.6, fontFace: F.BODY, fontSize: 16,
      color: "CFE0EC", margin: 0,
    });
    s.addText(d.footer, {
      x: M, y: H - 0.95, w: 8.4, h: 0.35, fontFace: F.MONO, fontSize: 11,
      color: C.MINT, margin: 0,
    });
  },

  statement(s, d) {
    s.background = { color: C.NAVY };
    circleIcon(s, "▲", M, 1.55, 0.5, C.GOLD, C.NAVY, 15);
    s.addText(d.kicker, {
      x: M + 0.75, y: 1.6, w: 8, h: 0.4, fontFace: F.BODY, fontSize: 12,
      bold: true, color: C.GOLD, charSpacing: 2, valign: "middle", margin: 0,
    });
    s.addText(d.headline, {
      x: M, y: 2.35, w: W - 2 * M - 1.2, h: 1.9, fontFace: F.HEAD, fontSize: 34,
      bold: true, color: "FFFFFF", lineSpacing: 42, margin: 0,
    });
    s.addText(d.support, {
      x: M, y: 4.5, w: W - 2 * M - 2.2, h: 1.6, fontFace: F.BODY, fontSize: 15,
      color: "C9D8E4", lineSpacing: 24, margin: 0,
    });
  },

  flow(s, d) {
    title(s, d.title);
    if (d.subtitle) subtitle(s, d.subtitle);
    const n = d.steps.length;
    const top = 2.0, gap = 0.16;
    const h = (H - top - 0.85 - gap * (n - 1)) / n;
    const tints = [C.NAVY, C.DEEP, C.TEAL, C.MINT, C.GOLD];
    d.steps.forEach((st, i) => {
      const y = top + i * (h + gap);
      card(s, M, y, W - 2 * M, h, C.WASH);
      circleIcon(s, st.n, M + 0.28, y + (h - 0.52) / 2, 0.52, tints[i % tints.length],
        i === 4 ? C.NAVY : "FFFFFF", 17);
      s.addText(st.h, {
        x: M + 1.0, y: y + 0.10, w: W - 2 * M - 1.35, h: 0.34,
        fontFace: F.HEAD, fontSize: 15, bold: true, color: C.NAVY, margin: 0,
      });
      s.addText(st.b, {
        x: M + 1.0, y: y + 0.44, w: W - 2 * M - 1.35, h: h - 0.52,
        fontFace: F.BODY, fontSize: 12, color: C.BODY, lineSpacing: 16, margin: 0,
      });
    });
  },

  cards3(s, d) {
    title(s, d.title);
    const y = d.footnote ? 1.85 : 2.0;
    const h = d.footnote ? 3.6 : 3.9;
    const w = (W - 2 * M - 0.7) / 3;
    const tints = [C.DEEP, C.TEAL, C.MINT];
    d.cards.forEach((c, i) => {
      const x = M + i * (w + 0.35);
      card(s, x, y, w, h, C.WASH);
      circleIcon(s, c.icon, x + 0.32, y + 0.34, 0.62, tints[i], "FFFFFF", 20);
      s.addText(c.tag, {
        x: x + 0.32, y: y + 1.12, w: w - 0.64, h: 0.26,
        fontFace: F.BODY, fontSize: 9, bold: true, color: tints[i], charSpacing: 1.4, margin: 0,
      });
      s.addText(c.h, {
        x: x + 0.32, y: y + 1.40, w: w - 0.64, h: 0.5,
        fontFace: F.HEAD, fontSize: 17, bold: true, color: C.NAVY, margin: 0,
      });
      s.addText(c.b, {
        x: x + 0.32, y: y + 1.98, w: w - 0.64, h: h - 2.3,
        fontFace: F.BODY, fontSize: 12, color: C.BODY, lineSpacing: 17, margin: 0,
      });
    });
    if (d.footnote) {
      s.addText(d.footnote, {
        x: M, y: y + h + 0.3, w: W - 2 * M, h: 0.45,
        fontFace: F.BODY, fontSize: 13, italic: true, color: C.DEEP, margin: 0,
      });
    }
  },

  cards4(s, d) {
    title(s, d.title);
    if (d.subtitle) subtitle(s, d.subtitle);
    const y = d.subtitle ? 2.05 : 1.9;
    const h = d.subtitle ? 3.75 : 4.05;
    const w = (W - 2 * M - 0.75) / 4;
    const tints = [C.NAVY, C.DEEP, C.TEAL, C.MINT];
    d.cards.forEach((c, i) => {
      const x = M + i * (w + 0.25);
      card(s, x, y, w, h, C.WASH);
      circleIcon(s, c.icon, x + 0.26, y + 0.3, 0.54, tints[i], "FFFFFF", 18);
      s.addText(c.tag, {
        x: x + 0.26, y: y + 1.0, w: w - 0.52, h: 0.24,
        fontFace: F.BODY, fontSize: 8, bold: true, color: tints[i], charSpacing: 1.2, margin: 0,
      });
      s.addText(c.h, {
        x: x + 0.26, y: y + 1.26, w: w - 0.52, h: 0.62,
        fontFace: F.HEAD, fontSize: 15, bold: true, color: C.NAVY, lineSpacing: 19, margin: 0,
      });
      s.addText(c.b, {
        x: x + 0.26, y: y + 1.92, w: w - 0.52, h: h - 2.2,
        fontFace: F.BODY, fontSize: 11.5, color: C.BODY, lineSpacing: 16, margin: 0,
      });
    });
  },

  compare(s, d) {
    title(s, d.title);
    subtitle(s, d.subtitle);
    const y = 1.95, h = 4.5;
    const w = (W - 2 * M - 0.6) / 3;
    d.columns.forEach((col, i) => {
      const x = M + i * (w + 0.3);
      const accent = C[col.tint];
      const dark = i === 2;
      card(s, x, y, w, h, dark ? C.NAVY : C.WASH);
      s.addText(col.h, {
        x: x + 0.3, y: y + 0.28, w: w - 0.6, h: 0.5,
        fontFace: F.HEAD, fontSize: 19, bold: true,
        color: dark ? "FFFFFF" : accent, margin: 0,
      });
      s.addText(
        col.rows.map((r, k) => {
          const [k1, ...rest] = r.split(": ");
          return {
            text: `${k1}: `, options: {
              bold: true, breakLine: false,
              color: dark ? C.MINT : C.MUTED, fontSize: 11.5,
            },
          };
        }).flatMap((lead, k) => [lead, {
          text: col.rows[k].split(": ").slice(1).join(": "),
          options: {
            breakLine: true, color: dark ? "E4EDF4" : C.BODY,
            fontSize: 11.5, paraSpaceAfter: 9,
          },
        }]),
        { x: x + 0.3, y: y + 0.92, w: w - 0.6, h: h - 1.2, fontFace: F.BODY, margin: 0 }
      );
    });
  },

  table(s, d) {
    title(s, d.title);
    subtitle(s, d.subtitle);
    const rows = [
      d.head.map((t) => ({
        text: t,
        options: {
          bold: true, color: "FFFFFF", fill: { color: C.NAVY },
          fontFace: F.BODY, fontSize: 12, margin: [6, 8, 6, 8],
        },
      })),
      ...d.rows.map((r, i) =>
        r.map((cell, j) => ({
          text: cell,
          options: {
            color: j === 1 ? C.DEEP : C.BODY,
            bold: j <= 1,
            fill: { color: i % 2 ? C.WASH : "FFFFFF" },
            fontFace: j === 1 ? F.MONO : F.BODY,
            fontSize: 11.5, margin: [5, 8, 5, 8],
          },
        }))
      ),
    ];
    s.addTable(rows, {
      x: M, y: 1.85, w: W - 2 * M, colW: d.colW,
      border: { type: "solid", color: C.LINE, pt: 0.5 },
      valign: "middle",
    });
    if (d.callout) {
      const cy = H - 1.5;
      card(s, M, cy, W - 2 * M, 0.92, "FDF6E3");
      circleIcon(s, "!", M + 0.22, cy + 0.22, 0.48, C.GOLD, C.NAVY, 17);
      s.addText(d.callout, {
        x: M + 0.85, y: cy + 0.1, w: W - 2 * M - 1.1, h: 0.72,
        fontFace: F.BODY, fontSize: 11.5, color: "6B4E00",
        valign: "middle", lineSpacing: 15, margin: 0,
      });
    }
  },

  worked(s, d) {
    title(s, d.title);
    subtitle(s, d.subtitle);
    const top = 1.95, n = d.steps.length;
    const h = (H - top - 0.7) / n - 0.06;
    d.steps.forEach((st, i) => {
      const y = top + i * (h + 0.06);
      const last = i === n - 1;
      card(s, M, y, W - 2 * M, h, last ? "E8F4F1" : (i % 2 ? C.WASH : "FFFFFF"));
      s.addText(st.k, {
        x: M + 0.28, y, w: 2.5, h,
        fontFace: F.BODY, fontSize: 12, bold: true,
        color: last ? "0F6B4F" : C.DEEP, valign: "middle", margin: 0,
      });
      s.addText(st.v, {
        x: M + 2.9, y, w: W - 2 * M - 3.2, h,
        fontFace: F.MONO, fontSize: 11.5,
        color: last ? "0F6B4F" : C.BODY, valign: "middle", margin: 0,
      });
    });
  },

  code(s, d) {
    title(s, d.title);
    subtitle(s, d.subtitle);
    const boxH = 3.5;
    s.addShape(pres.ShapeType.roundRect, {
      x: M, y: 1.95, w: 7.55, h: boxH, rectRadius: 0.06, fill: { color: "1B2340" },
    });
    s.addText(d.code, {
      x: M + 0.22, y: 2.08, w: 7.15, h: boxH - 0.26,
      fontFace: F.MONO, fontSize: 10, color: "D8E4F0", lineSpacing: 14.5, margin: 0,
    });
    s.addText(
      d.bullets.map((b, i) => ({
        text: b,
        options: {
          bullet: true, breakLine: i !== d.bullets.length - 1,
          fontSize: 12, color: C.BODY, paraSpaceAfter: 11,
        },
      })),
      { x: 8.55, y: 2.0, w: W - 8.55 - M, h: boxH, fontFace: F.BODY, margin: 0 }
    );
  },

  stats(s, d) {
    title(s, d.title);
    const y = 2.0, h = 2.35;
    const w = (W - 2 * M - 0.4) / 2;
    const tints = [C.DEEP, C.MINT];
    d.stats.forEach((st, i) => {
      const x = M + i * (w + 0.4);
      card(s, x, y, w, h, i ? "E8F5F3" : C.WASH);
      s.addText(st.big, {
        x: x + 0.35, y: y + 0.35, w: w - 0.7, h: 0.85,
        fontFace: F.HEAD, fontSize: 34, bold: true, color: tints[i], margin: 0,
      });
      s.addText(st.small, {
        x: x + 0.35, y: y + 1.25, w: w - 0.7, h: 0.95,
        fontFace: F.BODY, fontSize: 12.5, color: C.BODY, lineSpacing: 17, margin: 0,
      });
    });
    card(s, M, y + h + 0.35, W - 2 * M, 1.5, C.NAVY);
    s.addText(d.body, {
      x: M + 0.45, y: y + h + 0.5, w: W - 2 * M - 0.9, h: 1.2,
      fontFace: F.BODY, fontSize: 14, color: "E4EDF4",
      lineSpacing: 21, valign: "middle", margin: 0,
    });
  },

  closing(s, d) {
    s.background = { color: C.NAVY };
    s.addShape(pres.ShapeType.ellipse, {
      x: -1.6, y: H - 3.0, w: 4.6, h: 4.6, fill: { color: C.DEEP, transparency: 60 },
    });
    s.addText(d.kicker, {
      x: M, y: 0.85, w: 8, h: 0.35, fontFace: F.BODY, fontSize: 12,
      bold: true, color: C.GOLD, charSpacing: 2, margin: 0,
    });
    s.addText(d.headline, {
      x: M, y: 1.3, w: 8.6, h: 0.95,
      fontFace: F.HEAD, fontSize: 32, bold: true, color: "FFFFFF", margin: 0,
    });
    s.addText(
      d.points.map((p, i) => ({
        text: p,
        options: {
          bullet: true, breakLine: i !== d.points.length - 1,
          fontSize: 14, color: "DCE7F0", paraSpaceAfter: 12,
        },
      })),
      { x: M + 0.15, y: 2.5, w: 7.4, h: 2.4, fontFace: F.BODY, margin: 0 }
    );
    card(s, M, 5.2, W - 2 * M, 1.42, "0E1730");
    circleIcon(s, "→", M + 0.3, 5.55, 0.55, C.MINT, C.NAVY, 18);
    s.addText(d.next, {
      x: M + 1.05, y: 5.35, w: W - 2 * M - 1.4, h: 1.1,
      fontFace: F.BODY, fontSize: 13, color: "C9D8E4",
      lineSpacing: 19, valign: "middle", margin: 0,
    });
  },
};

/* ============================ build ====================================== */
slides.forEach((d, i) => {
  const s = pres.addSlide();
  const fn = render[d.layout];
  if (!fn) throw new Error(`Unknown layout "${d.layout}" on slide ${i + 1}`);
  fn(s, d);
  if (!["title", "statement", "closing"].includes(d.layout)) pageNum(s, i + 1);
  s.addNotes(d.notes);
});

pres.writeFile({ fileName: outPath }).then(() =>
  console.log(`Wrote ${outPath} — ${slides.length} slides, all with speaker notes.`)
);
