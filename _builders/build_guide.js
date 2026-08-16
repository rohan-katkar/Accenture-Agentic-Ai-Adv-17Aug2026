/* =====================================================================
   build_guide.js — renders a Word facilitation guide from a content module.

   Usage:
     node _builders/build_guide.js content_day1.js Day1_Foundations/Day1_Facilitation_Guide.docx "Day 1"

   WHY THIS EXISTS
   ---------------
   A deck and its facilitation guide are the classic drift pair: someone fixes a
   figure on a slide and the guide keeps the old one. Here the guide is DERIVED
   from the same content module the deck is rendered from, so the two cannot
   disagree. Speaker notes are parsed out of the WHY / SAY / ASK / WATCH / TIME
   convention and laid out as a delivery script.
   ===================================================================== */

const path = require("path");
const {
  AlignmentType, BorderStyle, Document, HeadingLevel, PageBreak, Packer,
  Paragraph, ShadingType, Table, TableCell, TableRow, TextRun, WidthType,
  Footer, PageNumber, LevelFormat,
} = require("docx");
const fs = require("fs");

const contentFile = process.argv[2] || "content_day1.js";
const outPath = process.argv[3] || "Facilitation_Guide.docx";
const dayLabel = process.argv[4] || "Day";
const { PALETTE: C, slides } = require(path.resolve(__dirname, contentFile));

const HEAD = "Cambria", BODY = "Calibri", MONO = "Consolas";
const LETTER = { width: 12240, height: 15840 };   // DXA, US Letter
const CONTENT_W = 9360;                            // 6.5" usable

/* ---------------------------------------------------------------- helpers */
const P = (text, opts = {}) =>
  new Paragraph({
    spacing: { after: opts.after ?? 120, line: opts.line ?? 276 },
    indent: opts.indent,
    alignment: opts.alignment,
    children: [new TextRun({
      text, font: opts.font ?? BODY, size: opts.size ?? 21,
      bold: opts.bold, italics: opts.italics, color: opts.color ?? "3C4257",
    })],
  });

const H = (text, level, colour = C.NAVY) =>
  new Paragraph({
    heading: level,
    spacing: { before: 260, after: 130 },
    children: [new TextRun({
      text, font: HEAD, bold: true, color: colour,
      size: level === HeadingLevel.HEADING_1 ? 32 : level === HeadingLevel.HEADING_2 ? 26 : 23,
    })],
  });

const rule = () =>
  new Paragraph({
    spacing: { before: 60, after: 160 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: C.LINE } },
    children: [new TextRun({ text: "", size: 2 })],
  });

const cell = (text, { w, bold, fill, font, colour, size } = {}) =>
  new TableCell({
    width: { size: w, type: WidthType.DXA },
    shading: fill ? { type: ShadingType.CLEAR, fill } : undefined,
    margins: { top: 90, bottom: 90, left: 130, right: 130 },
    children: [new Paragraph({
      spacing: { after: 0, line: 264 },
      children: [new TextRun({
        text, font: font ?? BODY, size: size ?? 20, bold,
        color: colour ?? "3C4257",
      })],
    })],
  });

/** Callout block: tinted single-cell table. Avoids edge-stripe styling. */
const callout = (label, text, fill, colour) =>
  new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [CONTENT_W],
    borders: {
      top: { style: BorderStyle.SINGLE, size: 2, color: fill },
      bottom: { style: BorderStyle.SINGLE, size: 2, color: fill },
      left: { style: BorderStyle.SINGLE, size: 2, color: fill },
      right: { style: BorderStyle.SINGLE, size: 2, color: fill },
    },
    rows: [new TableRow({
      children: [new TableCell({
        width: { size: CONTENT_W, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, fill },
        margins: { top: 130, bottom: 130, left: 160, right: 160 },
        children: [
          new Paragraph({
            spacing: { after: 60 },
            children: [new TextRun({
              text: label, font: BODY, size: 17, bold: true,
              color: colour, characterSpacing: 20,
            })],
          }),
          ...text.split("\n").filter(Boolean).map((line) => new Paragraph({
            spacing: { after: 70, line: 272 },
            children: [new TextRun({ text: line, font: BODY, size: 20, color: colour })],
          })),
        ],
      })],
    })],
  });

/* ------------------------------------------------- speaker-note parsing -- */
/** Split notes into labelled blocks on the WHY/SAY/ASK/WATCH/TIME convention. */
function parseNotes(notes) {
  const blocks = [];
  const re = /^(WHY|SAY|ASK|WATCH|TIME|DEMO|FLAG|BE HONEST|TRAINER|DEMO IF TIME|DEMO IF POSSIBLE|SAY FIRST|ASK FIRST)\b([^:]*):\s*/;
  let current = null;
  for (const raw of notes.split("\n")) {
    const line = raw.trim();
    if (!line) continue;
    const m = line.match(re);
    if (m) {
      if (current) blocks.push(current);
      current = { tag: (m[1] + (m[2] || "")).trim(), text: line.slice(m[0].length) };
    } else if (current) {
      current.text += " " + line;
    } else {
      current = { tag: "NOTE", text: line };
    }
  }
  if (current) blocks.push(current);
  return blocks;
}

const TAG_STYLE = {
  WHY: { fill: "F2F6F9", colour: "3C4257", label: "WHY THIS SLIDE EXISTS" },
  SAY: { fill: "EAF2F7", colour: "10405C", label: "SAY" },
  ASK: { fill: "E8F5F3", colour: "0F5A50", label: "ASK THE ROOM" },
  WATCH: { fill: "FDF6E3", colour: "6B4E00", label: "WATCH FOR" },
  TIME: { fill: "FFFFFF", colour: "6B7280", label: "TIME" },
  DEMO: { fill: "E8F5F3", colour: "0F5A50", label: "DEMO" },
  FLAG: { fill: "FDF6E3", colour: "6B4E00", label: "FLAG HONESTLY" },
};

function styleFor(tag) {
  const key = Object.keys(TAG_STYLE).find((k) => tag.startsWith(k));
  const base = TAG_STYLE[key] || TAG_STYLE.WHY;
  return { ...base, label: tag.length > (key || "").length ? tag : base.label };
}

/* ---------------------------------------------------- slide body summary - */
function bodyLines(d) {
  const out = [];
  const push = (s) => { if (s) out.push(s); };
  push(d.subtitle);
  push(d.headline);
  push(d.support);
  (d.steps || []).forEach((s) => push(`${s.n ?? s.k} · ${s.h ?? ""} ${s.b ?? s.v ?? ""}`.trim()));
  (d.cards || []).forEach((c) => push(`${c.h} — ${c.b}`));
  (d.columns || []).forEach((c) => push(`${c.h}: ${c.rows.join(" · ")}`));
  (d.stats || []).forEach((s) => push(`${s.big} — ${s.small}`));
  (d.points || []).forEach(push);
  (d.bullets || []).forEach(push);
  if (d.head && d.rows) {
    push(d.head.join(" | "));
    d.rows.forEach((r) => push(r.join(" | ")));
  }
  push(d.body);
  push(d.footnote);
  push(d.callout);
  push(d.next);
  return out;
}

/* =============================================================== document */
const totalMin = slides.reduce((acc, d) => {
  const m = (d.notes || "").match(/TIME:\s*(\d+)/);
  return acc + (m ? parseInt(m[1], 10) : 0);
}, 0);

const children = [];

/* --- cover --- */
children.push(
  new Paragraph({ spacing: { before: 1900, after: 100 }, children: [
    new TextRun({ text: "ACCENTURE BATCH 1 · AGENTIC AI FOUNDATION",
      font: BODY, size: 19, bold: true, color: C.DEEP, characterSpacing: 40 })] }),
  new Paragraph({ spacing: { after: 160 }, children: [
    new TextRun({ text: `${dayLabel} — Facilitation Guide`,
      font: HEAD, size: 52, bold: true, color: C.NAVY })] }),
  new Paragraph({ spacing: { after: 460 }, children: [
    new TextRun({ text: slides[0].title, font: BODY, size: 24, color: "6B7280", italics: true })] }),
);

children.push(callout("HOW TO USE THIS GUIDE",
  `This guide is generated from ${contentFile}, the same source the deck is rendered from. Slide text and speaker notes here cannot drift from the deck — if a figure changes, it changes in one place and both artifacts follow.\n` +
  `Each slide gives you: what is on it, why it is there, the spoken line, the question to put to the room, and the misconception to catch.\n` +
  `${slides.length} slides · ${totalMin} minutes of speaking time, excluding labs and breaks.\n` +
  `Read the two registers in 00_Program/ before you deliver: VERSION_RISK_REGISTER.md and CURRICULUM_GAP_ANALYSIS.md.`,
  "F2F6F9", "21295C"));

children.push(new Paragraph({ children: [new PageBreak()] }));

/* --- at a glance --- */
children.push(H("At a glance", HeadingLevel.HEADING_1));
children.push(P("Speaking time only. Labs, breaks and discussion overruns are additional.", { italics: true, color: "6B7280" }));

const glanceW = [700, 5400, 1200, 2060];
children.push(new Table({
  width: { size: CONTENT_W, type: WidthType.DXA },
  columnWidths: glanceW,
  rows: [
    new TableRow({ tableHeader: true, children: [
      cell("#", { w: glanceW[0], bold: true, fill: C.NAVY, colour: "FFFFFF" }),
      cell("Slide", { w: glanceW[1], bold: true, fill: C.NAVY, colour: "FFFFFF" }),
      cell("Minutes", { w: glanceW[2], bold: true, fill: C.NAVY, colour: "FFFFFF" }),
      cell("Layout", { w: glanceW[3], bold: true, fill: C.NAVY, colour: "FFFFFF" }),
    ] }),
    ...slides.map((d, i) => {
      const m = (d.notes || "").match(/TIME:\s*(\d+)/);
      return new TableRow({ children: [
        cell(String(i + 1), { w: glanceW[0], bold: true, fill: i % 2 ? "F2F6F9" : "FFFFFF" }),
        cell(d.title || d.headline || d.kicker || "—", { w: glanceW[1], fill: i % 2 ? "F2F6F9" : "FFFFFF" }),
        cell(m ? `${m[1]} min` : "—", { w: glanceW[2], fill: i % 2 ? "F2F6F9" : "FFFFFF" }),
        cell(d.layout, { w: glanceW[3], font: MONO, size: 18, colour: "6B7280", fill: i % 2 ? "F2F6F9" : "FFFFFF" }),
      ] });
    }),
    new TableRow({ children: [
      cell("", { w: glanceW[0], fill: "EAF2F7" }),
      cell("Total speaking time", { w: glanceW[1], bold: true, fill: "EAF2F7", colour: C.DEEP }),
      cell(`${totalMin} min`, { w: glanceW[2], bold: true, fill: "EAF2F7", colour: C.DEEP }),
      cell("", { w: glanceW[3], fill: "EAF2F7" }),
    ] }),
  ],
}));

children.push(new Paragraph({ children: [new PageBreak()] }));

/* --- per-slide --- */
slides.forEach((d, i) => {
  const minutes = (d.notes || "").match(/TIME:\s*(\d+)/);
  children.push(H(`Slide ${i + 1} — ${d.title || d.headline || d.kicker}`, HeadingLevel.HEADING_1));
  children.push(P(`${d.layout} layout${minutes ? ` · ${minutes[1]} minutes` : ""}`,
    { font: MONO, size: 18, color: "6B7280", after: 60 }));
  children.push(rule());

  children.push(H("On the slide", HeadingLevel.HEADING_3, C.DEEP));
  bodyLines(d).forEach((line) =>
    children.push(P(line, { indent: { left: 260 }, after: 80, size: 20 })));

  children.push(H("Delivery", HeadingLevel.HEADING_3, C.DEEP));
  parseNotes(d.notes || "").forEach((block) => {
    if (block.tag.startsWith("TIME")) return;      // already in the header line
    const st = styleFor(block.tag);
    children.push(callout(st.label, block.text, st.fill, st.colour));
    children.push(P("", { after: 90, size: 2 }));
  });

  if (i < slides.length - 1) children.push(new Paragraph({ children: [new PageBreak()] }));
});

const doc = new Document({
  creator: "Training Architecture",
  title: `${dayLabel} — Facilitation Guide`,
  sections: [{
    properties: { page: { size: LETTER, margin: { top: 1080, bottom: 1080, left: 1440, right: 1440 } } },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.RIGHT,
        children: [new TextRun({
          text: `${dayLabel} Facilitation Guide · page `,
          font: BODY, size: 17, color: "9AA5B1",
        }), new TextRun({ children: [PageNumber.CURRENT], font: BODY, size: 17, color: "9AA5B1" })],
      })] }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(outPath, buf);
  console.log(`Wrote ${outPath} — ${slides.length} slides, ${totalMin} min speaking time.`);
});
