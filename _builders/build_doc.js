/* =====================================================================
   build_doc.js — render a house-styled Word document from a Markdown file.

     node _builders/build_doc.js <input.md> <output.docx> "Document Title"

   Used for the documents a trainer prints or emails: the environment guide,
   the gap analysis, the version register. The Markdown stays the source of
   truth (it is what people read in the repo); the .docx is a derived artifact,
   so the two cannot drift.

   Supports the subset this package actually uses:
     # ## ### headings · paragraphs · - and 1. lists · > blockquotes
     ``` fenced code · | tables | · --- rules · **bold** `code` [links]
   ===================================================================== */

const fs = require("fs");
const path = require("path");
const {
  AlignmentType, BorderStyle, Document, Footer, HeadingLevel, PageNumber,
  Packer, Paragraph, ShadingType, Table, TableCell, TableRow, TextRun,
  WidthType,
} = require("docx");

const [, , inputPath, outputPath, docTitle = "Document"] = process.argv;
if (!inputPath || !outputPath) {
  console.error('usage: node build_doc.js <input.md> <output.docx> "Title"');
  process.exit(2);
}

const C = {
  NAVY: "21295C", DEEP: "065A82", TEAL: "1C7293", MINT: "16A0A0", GOLD: "E0A800",
  BODY: "3C4257", MUTED: "6B7280", WASH: "F2F6F9", LINE: "D7E1EA",
};
const HEAD = "Cambria", BODY = "Calibri", MONO = "Consolas";
const CONTENT_W = 9360; // 6.5" in DXA

/* ---------- inline markup: **bold**, `code`, [text](url) ---------------- */
function inline(text, base = {}) {
  const runs = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;
  let last = 0, m;
  const push = (t, opts) => { if (t) runs.push(new TextRun({ ...base, ...opts, text: t })); };

  while ((m = re.exec(text)) !== null) {
    push(text.slice(last, m.index), {});
    const tok = m[0];
    if (tok.startsWith("**")) push(tok.slice(2, -2), { bold: true });
    else if (tok.startsWith("`")) push(tok.slice(1, -1), { font: MONO, size: 19, color: C.DEEP });
    else push(tok.slice(1, tok.indexOf("]")), { color: C.DEEP, underline: {} });
    last = m.index + tok.length;
  }
  push(text.slice(last), {});
  return runs.length ? runs : [new TextRun({ ...base, text })];
}

const para = (text, opts = {}) =>
  new Paragraph({
    spacing: { after: opts.after ?? 130, line: 278 },
    indent: opts.indent,
    bullet: opts.bullet,
    children: inline(text, {
      font: opts.font ?? BODY, size: opts.size ?? 21,
      color: opts.color ?? C.BODY, italics: opts.italics,
    }),
  });

const heading = (text, level) => {
  const size = level === 1 ? 32 : level === 2 ? 26 : 23;
  return new Paragraph({
    heading: level === 1 ? HeadingLevel.HEADING_1
      : level === 2 ? HeadingLevel.HEADING_2 : HeadingLevel.HEADING_3,
    spacing: { before: level === 1 ? 340 : 250, after: 140 },
    pageBreakBefore: false,
    children: [new TextRun({
      text: text.replace(/[*`]/g, ""), font: HEAD, bold: true,
      color: level === 3 ? C.DEEP : C.NAVY, size,
    })],
  });
};

const codeBlock = (lines) =>
  new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [CONTENT_W],
    borders: ["top", "bottom", "left", "right"].reduce((acc, side) => {
      acc[side] = { style: BorderStyle.SINGLE, size: 2, color: "1B2340" };
      return acc;
    }, {}),
    rows: [new TableRow({
      children: [new TableCell({
        width: { size: CONTENT_W, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, fill: "1B2340" },
        margins: { top: 120, bottom: 120, left: 160, right: 160 },
        children: lines.map((l) => new Paragraph({
          spacing: { after: 0, line: 250 },
          children: [new TextRun({ text: l || " ", font: MONO, size: 17, color: "D8E4F0" })],
        })),
      })],
    })],
  });

const quoteBlock = (lines) =>
  new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [CONTENT_W],
    borders: ["top", "bottom", "left", "right"].reduce((acc, side) => {
      acc[side] = { style: BorderStyle.SINGLE, size: 2, color: "FDF6E3" };
      return acc;
    }, {}),
    rows: [new TableRow({
      children: [new TableCell({
        width: { size: CONTENT_W, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, fill: "FDF6E3" },
        margins: { top: 130, bottom: 130, left: 170, right: 170 },
        children: lines.map((l) => new Paragraph({
          spacing: { after: 70, line: 272 },
          children: inline(l, { font: BODY, size: 20, color: "6B4E00" }),
        })),
      })],
    })],
  });

function mdTable(rows) {
  const cells = rows.map((r) =>
    r.replace(/^\||\|$/g, "").split("|").map((c) => c.trim()));
  const header = cells[0];
  const body = cells.slice(2); // skip the --- separator row
  const n = header.length;
  const widths = new Array(n).fill(Math.floor(CONTENT_W / n));

  const mk = (text, i, isHeader, stripe) => new TableCell({
    width: { size: widths[i], type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, fill: isHeader ? C.NAVY : (stripe ? C.WASH : "FFFFFF") },
    margins: { top: 90, bottom: 90, left: 120, right: 120 },
    children: [new Paragraph({
      spacing: { after: 0, line: 264 },
      children: inline(text, {
        font: BODY, size: 19, bold: isHeader,
        color: isHeader ? "FFFFFF" : C.BODY,
      }),
    })],
  });

  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, children: header.map((t, i) => mk(t, i, true, false)) }),
      ...body.map((r, ri) => new TableRow({
        children: Array.from({ length: n }, (_, i) => mk(r[i] ?? "", i, false, ri % 2 === 1)),
      })),
    ],
  });
}

/* ------------------------------- parse -------------------------------- */
const src = fs.readFileSync(path.resolve(inputPath), "utf8").split("\n");
const children = [];
let i = 0;

while (i < src.length) {
  const line = src[i];

  if (line.trim().startsWith("```")) {                       // fenced code
    const buf = [];
    i++;
    while (i < src.length && !src[i].trim().startsWith("```")) buf.push(src[i++]);
    i++;
    children.push(codeBlock(buf), para("", { after: 90, size: 2 }));
    continue;
  }

  if (line.trim().startsWith("|")) {                          // table
    const buf = [];
    while (i < src.length && src[i].trim().startsWith("|")) buf.push(src[i++]);
    if (buf.length >= 2) children.push(mdTable(buf), para("", { after: 110, size: 2 }));
    continue;
  }

  if (line.trim().startsWith(">")) {                          // blockquote
    const buf = [];
    while (i < src.length && src[i].trim().startsWith(">")) {
      buf.push(src[i].replace(/^\s*>\s?/, ""));
      i++;
    }
    children.push(quoteBlock(buf.filter((l) => l.trim())), para("", { after: 90, size: 2 }));
    continue;
  }

  const h = line.match(/^(#{1,3})\s+(.*)$/);
  if (h) { children.push(heading(h[2], h[1].length)); i++; continue; }

  if (/^---+\s*$/.test(line.trim())) {
    children.push(new Paragraph({
      spacing: { before: 90, after: 170 },
      border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: C.LINE } },
      children: [new TextRun({ text: "", size: 2 })],
    }));
    i++; continue;
  }

  const bullet = line.match(/^(\s*)[-*]\s+(.*)$/);
  if (bullet) {
    children.push(para(bullet[2], {
      bullet: { level: Math.min(2, Math.floor(bullet[1].length / 2)) }, after: 70,
    }));
    i++; continue;
  }

  const numbered = line.match(/^(\s*)(\d+)\.\s+(.*)$/);
  if (numbered) {
    children.push(para(`${numbered[2]}.  ${numbered[3]}`, {
      indent: { left: 360 + numbered[1].length * 180 }, after: 70,
    }));
    i++; continue;
  }

  if (line.trim()) { children.push(para(line.trim())); i++; continue; }
  i++;
}

/* ------------------------------- cover -------------------------------- */
children.unshift(
  new Paragraph({
    spacing: { before: 1700, after: 100 },
    children: [new TextRun({
      text: "ACCENTURE BATCH 1 · AGENTIC AI FOUNDATION",
      font: BODY, size: 19, bold: true, color: C.DEEP, characterSpacing: 40,
    })],
  }),
  new Paragraph({
    spacing: { after: 200 },
    children: [new TextRun({ text: docTitle, font: HEAD, size: 50, bold: true, color: C.NAVY })],
  }),
  new Paragraph({
    spacing: { after: 400 },
    children: [new TextRun({
      text: `Derived from ${path.basename(inputPath)} — that file is the source of truth.`,
      font: BODY, size: 20, italics: true, color: C.MUTED,
    })],
  }),
  new Paragraph({ pageBreakBefore: true, children: [new TextRun({ text: "", size: 2 })] }),
);

const doc = new Document({
  creator: "Training Architecture",
  title: docTitle,
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1080, bottom: 1080, left: 1440, right: 1440 },
      },
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [
            new TextRun({ text: `${docTitle} · page `, font: BODY, size: 17, color: "9AA5B1" }),
            new TextRun({ children: [PageNumber.CURRENT], font: BODY, size: 17, color: "9AA5B1" }),
          ],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(outputPath, buf);
  console.log(`Wrote ${outputPath} from ${inputPath} (${children.length} blocks).`);
});
