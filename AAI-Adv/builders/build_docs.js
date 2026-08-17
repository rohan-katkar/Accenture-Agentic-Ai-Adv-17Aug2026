/** build_docs.js — generates ALL documentation from docs_source.js.
 * Outputs: docs/STUDENT_GUIDE.docx, docs/FACILITATOR_GUIDE.docx,
 *          docs/LAB_STEPS.md, docs/ENVIRONMENT_SETUP.md,
 *          docs/VERIFICATION_REGISTER.md
 * Ocean Gradient palette, Cambria headers / Calibri body / Consolas mono,
 * US Letter.
 */
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow,
  TableCell, WidthType, AlignmentType, BorderStyle, ShadingType, LevelFormat,
  PageBreak,
} = require("docx");
const S = require("./docs_source.js");

const ROOT = path.resolve(__dirname, "..");
const DOCS = path.join(ROOT, "docs");
fs.mkdirSync(DOCS, { recursive: true });

const P = S.PALETTE;
const FONT_H = "Cambria", FONT_B = "Calibri", FONT_M = "Consolas";

// ---------- helpers ---------------------------------------------------------
const numbering = {
  config: [{
    reference: "bullets",
    levels: [{
      level: 0, format: LevelFormat.BULLET, text: "\u2022",
      style: { paragraph: { indent: { left: 360, hanging: 200 } } },
    }],
  }],
};

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 140 },
    children: [new TextRun({ text, font: FONT_H, color: P.NAVY, bold: true, size: 32 })],
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 110 },
    children: [new TextRun({ text, font: FONT_H, color: P.DEEP, bold: true, size: 26 })],
  });
}
function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3, spacing: { before: 180, after: 80 },
    children: [new TextRun({ text, font: FONT_H, color: P.TEAL, bold: true, size: 23 })],
  });
}
function body(text, opts = {}) {
  const runs = [];
  // Inline code: backtick segments render in Consolas.
  String(text).split(/(`[^`]+`)/).forEach((seg) => {
    if (seg.startsWith("`") && seg.endsWith("`")) {
      runs.push(new TextRun({ text: seg.slice(1, -1), font: FONT_M, size: 19,
                              color: P.DEEP }));
    } else if (seg) {
      runs.push(new TextRun({ text: seg, font: FONT_B, size: 21,
                              bold: !!opts.bold, italics: !!opts.italics,
                              color: opts.color }));
    }
  });
  return new Paragraph({ spacing: { after: opts.tight ? 40 : 100 },
                         numbering: opts.bullet ? { reference: "bullets", level: 0 } : undefined,
                         children: runs });
}
function labelValue(label, value) {
  return new Paragraph({
    spacing: { after: 60 },
    children: [
      new TextRun({ text: label + "  ", font: FONT_B, size: 21, bold: true, color: P.MINT }),
      new TextRun({ text: value, font: FONT_B, size: 21 }),
    ],
  });
}
function cell(text, { width, header = false, mono = false } = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: header ? { type: ShadingType.CLEAR, fill: P.NAVY } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({
      children: [new TextRun({ text, font: mono ? FONT_M : FONT_B,
                               size: header ? 20 : 19, bold: header,
                               color: header ? "FFFFFF" : undefined })],
    })],
  });
}
function table(headers, rows, widths) {
  return new Table({
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true,
        children: headers.map((t, i) => cell(t, { width: widths[i], header: true })) }),
      ...rows.map((r) => new TableRow({
        children: r.map((t, i) => cell(String(t), { width: widths[i], mono: i === 0 })) })),
    ],
  });
}
function titlePage(docTitle) {
  return [
    new Paragraph({ spacing: { before: 2600, after: 200 }, alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: S.PROGRAM.title, font: FONT_H, bold: true,
                               size: 52, color: P.NAVY })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 },
      children: [new TextRun({ text: S.PROGRAM.subtitle, font: FONT_B, size: 26,
                               color: P.TEAL })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 500 },
      border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: P.GOLD } },
      children: [new TextRun({ text: docTitle, font: FONT_H, bold: true, size: 36,
                               color: P.DEEP })] }),
    new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: `${S.PROGRAM.client} · v${S.PROGRAM.version} · ${S.PROGRAM.date}`,
                               font: FONT_B, size: 21, color: "666666" })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120 },
      children: [new TextRun({ text: S.PROGRAM.stack, font: FONT_B, italics: true,
                               size: 18, color: "888888" })] }),
    new Paragraph({ children: [new PageBreak()] }),
  ];
}
function pageProps() {
  return { page: { size: { width: 12240, height: 15840 },
                   margin: { top: 1080, bottom: 1080, left: 1180, right: 1180 } } };
}

// ---------- lab section (shared by both guides) ------------------------------
function labSection(lab, { facilitator }) {
  const out = [];
  out.push(h2(`Lab ${lab.id} — ${lab.title}`));
  out.push(labelValue("Duration", lab.duration));
  out.push(labelValue("Objective", lab.objective));
  out.push(labelValue("Concepts", lab.concepts));
  out.push(labelValue("Files",
    `labs/day${lab.day}/starters/${lab.file}.py (build here) · ` +
    `solutions/day${lab.day}/${lab.file}.py · ` +
    `labs/day${lab.day}/notebooks/${lab.file}.ipynb`));
  out.push(h3("Steps"));
  lab.steps.forEach(([t, d], i) => {
    out.push(body(`Step ${i + 1} — ${t}`, { bold: true, tight: true }));
    out.push(body(d));
  });
  out.push(h3("Named failure modes"));
  lab.failureModes.forEach((f) => out.push(body(f, { bullet: true })));
  out.push(h3("Stretch goal"));
  out.push(body(lab.stretch));
  out.push(h3("Completion checkpoint"));
  out.push(body(lab.checkpoint, { italics: true }));
  if (facilitator) {
    out.push(h3("Facilitation notes"));
    out.push(body(
      "Run the solution live once before learners start; keep the corrections " +
      "table visible. Circulate during the first failure-mode window (typically " +
      "10-15 minutes in). If a learner is blocked past the timebox, have them " +
      "diff their starter cell against the solution's matching Step cell — the " +
      "structure is identical by construction."));
  }
  return out;
}

// ---------- STUDENT GUIDE -----------------------------------------------------
function studentGuide() {
  const kids = [...titlePage("Student Guide")];
  kids.push(h1("Welcome & Scenario"));
  kids.push(body(
    "You are building an autonomous multi-agent pipeline for Northwind Global " +
    "Retail. The system ingests raw Amazon Seller Central settlement files, " +
    "extracts line-item fees, matches them against open invoices in Microsoft " +
    "Dynamics 365 ERP, posts verified reconciliation entries, and escalates " +
    "high variances to human reviewers. Every lab adds one production concern " +
    "to this same pipeline, and the Day 4 capstone assembles all of it."));
  kids.push(body(
    "The fixtures contain deliberately planted defects (D1-D6) — an overstated " +
    "FBA fee, a percent-rule breach, a duplicate settlement row, a missing " +
    "invoice, an accounting-negative promo field, and an unallocated promo. " +
    "They are the curriculum: each one is caught by a specific lab assertion."));
  kids.push(h1("Two Execution Modes"));
  kids.push(body(
    "Every lab runs in OFFLINE mode (deterministic stub model, zero cloud " +
    "dependencies) and in AZURE mode (live Azure AI Foundry models). The switch " +
    "is the .env file — lab code never changes. Get each lab green offline " +
    "first; then flip to Azure. Assertions are mode-independent by design."));
  kids.push(h1(S.ENV_SETUP.title));
  S.ENV_SETUP.steps.forEach(([t, d], i) => {
    kids.push(h3(`${i + 1}. ${t}`));
    kids.push(body(d));
  });
  kids.push(new Paragraph({ children: [new PageBreak()] }));
  [1, 2, 3].forEach((day) => {
    kids.push(h1(`Day ${day} Labs`));
    S.LABS.filter((l) => l.day === day).forEach((lab) =>
      kids.push(...labSection(lab, { facilitator: false })));
  });
  kids.push(new Paragraph({ children: [new PageBreak()] }));
  kids.push(h1(S.CAPSTONE.title));
  kids.push(labelValue("Duration", S.CAPSTONE.duration));
  kids.push(labelValue("Objective", S.CAPSTONE.objective));
  S.CAPSTONE.phases.forEach(([t, d]) => { kids.push(h3(t)); kids.push(body(d)); });
  kids.push(h1("Corrections Table (read this — you will hit these)"));
  kids.push(body(
    "Every defect below was found by EXECUTING this package against the live " +
    "SDKs during its build, then fixed and regression-tested. When your stack " +
    "trace matches a row, the fix is already written down."));
  kids.push(table(["#", "Defect", "Fix", "Where"],
                  S.CORRECTIONS, [700, 3800, 3800, 1500]));
  return new Document({ numbering, sections: [{ properties: pageProps(), children: kids }] });
}

// ---------- FACILITATOR GUIDE -------------------------------------------------
function facilitatorGuide() {
  const kids = [...titlePage("Facilitator Guide")];
  kids.push(h1("Audience & Prerequisites"));
  kids.push(body(S.FACILITATOR.audience));
  kids.push(h1("Cohort Preparation Checklist"));
  S.FACILITATOR.cohortPrep.forEach((c) => kids.push(body(c, { bullet: true })));
  kids.push(h1("Timing Plan"));
  kids.push(table(["Day", "Schedule"],
                  S.FACILITATOR.timing, [1100, 8700]));
  kids.push(h1("Teaching Notes"));
  S.FACILITATOR.teachingNotes.forEach((n) => kids.push(body(n, { bullet: true })));
  kids.push(h1("Assessment"));
  kids.push(body(S.FACILITATOR.assessment));
  kids.push(new Paragraph({ children: [new PageBreak()] }));
  [1, 2, 3].forEach((day) => {
    kids.push(h1(`Day ${day} Labs — Facilitation Detail`));
    S.LABS.filter((l) => l.day === day).forEach((lab) =>
      kids.push(...labSection(lab, { facilitator: true })));
  });
  kids.push(new Paragraph({ children: [new PageBreak()] }));
  kids.push(h1("Capstone Delivery & Demo Risk Register"));
  S.CAPSTONE.phases.forEach(([t, d]) => { kids.push(h3(t)); kids.push(body(d)); });
  kids.push(h2("Demo risk register"));
  kids.push(table(["Risk", "Named fallback"],
                  S.CAPSTONE.demoRisks, [4400, 5400]));
  kids.push(h1("Verification Register"));
  kids.push(body(
    "Claims below are classified by confidence. Re-check every VERSION-SENSITIVE " +
    "item against current Microsoft documentation before each delivery; the " +
    "Foundry preview surfaces move frequently."));
  kids.push(table(["Confidence", "Items"],
                  S.VERIFICATION_REGISTER, [2600, 7200]));
  kids.push(h1("Corrections Table"));
  kids.push(table(["#", "Defect", "Fix", "Where"],
                  S.CORRECTIONS, [700, 3800, 3800, 1500]));
  return new Document({ numbering, sections: [{ properties: pageProps(), children: kids }] });
}

// ---------- Markdown outputs ---------------------------------------------------
function labStepsMd() {
  let md = `# ${S.PROGRAM.title} — Lab Steps\n\n${S.PROGRAM.subtitle}\n\n` +
    `> Generated from builders/docs_source.js — do not edit by hand.\n\n`;
  [1, 2, 3].forEach((day) => {
    md += `\n## Day ${day}\n`;
    S.LABS.filter((l) => l.day === day).forEach((lab) => {
      md += `\n### Lab ${lab.id} — ${lab.title} (${lab.duration})\n\n` +
        `**Objective.** ${lab.objective}\n\n**Concepts.** ${lab.concepts}\n\n` +
        `**Files.** \`labs/day${lab.day}/starters/${lab.file}.py\` (build here) · ` +
        `\`solutions/day${lab.day}/${lab.file}.py\` · ` +
        `\`labs/day${lab.day}/notebooks/${lab.file}.ipynb\`\n\n`;
      lab.steps.forEach(([t, d], i) => { md += `${i + 1}. **${t}.** ${d}\n`; });
      md += `\n**Named failure modes.**\n`;
      lab.failureModes.forEach((f) => { md += `- ${f}\n`; });
      md += `\n**Stretch.** ${lab.stretch}\n\n**Checkpoint.** ${lab.checkpoint}\n`;
    });
  });
  md += `\n## Capstone — ${S.CAPSTONE.title} (${S.CAPSTONE.duration})\n\n${S.CAPSTONE.objective}\n\n`;
  S.CAPSTONE.phases.forEach(([t, d]) => { md += `**${t}.** ${d}\n\n`; });
  return md;
}
function envMd() {
  let md = `# ${S.ENV_SETUP.title}\n\n`;
  S.ENV_SETUP.steps.forEach(([t, d], i) => { md += `## ${i + 1}. ${t}\n\n${d}\n\n`; });
  return md;
}
function verifyMd() {
  let md = `# Verification Register\n\n| Confidence | Items |\n|---|---|\n`;
  S.VERIFICATION_REGISTER.forEach(([c, i]) => { md += `| ${c} | ${i} |\n`; });
  md += `\n# Corrections Table\n\n| # | Defect | Fix | Where |\n|---|---|---|---|\n`;
  S.CORRECTIONS.forEach((r) => { md += `| ${r.join(" | ")} |\n`; });
  return md;
}

// ---------- run ---------------------------------------------------------------
(async () => {
  fs.writeFileSync(path.join(DOCS, "LAB_STEPS.md"), labStepsMd());
  fs.writeFileSync(path.join(DOCS, "ENVIRONMENT_SETUP.md"), envMd());
  fs.writeFileSync(path.join(DOCS, "VERIFICATION_REGISTER.md"), verifyMd());
  fs.writeFileSync(path.join(DOCS, "STUDENT_GUIDE.docx"),
    await Packer.toBuffer(studentGuide()));
  fs.writeFileSync(path.join(DOCS, "FACILITATOR_GUIDE.docx"),
    await Packer.toBuffer(facilitatorGuide()));
  console.log("docs generated:", fs.readdirSync(DOCS).join(", "));
})();
