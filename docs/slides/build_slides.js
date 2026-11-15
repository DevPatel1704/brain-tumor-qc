// Build the final presentation (docs/slides/btqc_presentation.pptx) from results/slide_data.json.
//   python scripts/slide_data.py && node docs/slides/build_slides.js
// Needs pptxgenjs, react, react-dom, react-icons and sharp on NODE_PATH.
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const md = require("react-icons/md");

const ROOT = path.resolve(__dirname, "..", "..");
const R = path.join(ROOT, "results");
const D = JSON.parse(fs.readFileSync(path.join(R, "slide_data.json"), "utf8"));
const OUT = path.join(__dirname, "btqc_presentation.pptx");

const THEME = {
  name: "BTQC Clinical",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1F2328", lt1: "FFFFFF", dk2: "16324F", lt2: "EEF3F8",
    accent1: "16324F", accent2: "2F7FB8", accent3: "E09A2D", accent4: "2E8B57",
    accent5: "C0504D", accent6: "8C959F", hlink: "2F7FB8", folHlink: "6B4FA0",
  },
};
const HEX = THEME.colors;
const MUTED = "57606A";

// ---------- helpers ----------
const f2 = (x) => (x == null ? "–" : x.toFixed(2));
const f3 = (x) => (x == null ? "–" : x.toFixed(3));
const pct = (x) => (x == null ? "–" : Math.round(x * 100) + "%");
const REG = { WT: "Whole tumor", TC: "Tumor core", ET: "Enhancing tumor" };

async function icon(name, color, size = 256) {
  const Comp = md[name];
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(size) }));
  const buf = await sharp(Buffer.from(svg)).resize(size, size).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

async function main() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5 in
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  pres.title = "Uncertainty-Gated Brain Tumor Segmentation Across Hospitals";
  pres.author = "Dev Patel, Priyanka Gupta, Slesha Vora";
  pres.company = "Ontario Tech University";
  const C = pres.SchemeColor;

  // ---------- layouts ----------
  pres.defineSlideMaster({
    title: "COVER",
    background: { color: "FFFFFF" },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 1.2, w: 6.5, h: 2.6, fontSize: 36,
        bold: true, color: C.text2, fontFace: THEME.headFontFace, valign: "bottom", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 3.95, w: 6.5, h: 1.0, fontSize: 18,
        color: C.accent2, valign: "top", margin: 0 }, text: "" } },
    ],
  });
  pres.defineSlideMaster({
    title: "CONTENT",
    background: { color: "FFFFFF" },
    margin: [0.5, 0.6, 0.7, 0.6],
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.85, fontSize: 32,
        bold: true, color: C.text2, fontFace: THEME.headFontFace, valign: "middle", margin: 0 }, text: "" } },
      { text: { text: "Ontario Tech University · Applied Track · Research prototype, not a medical device",
        options: { x: 0.6, y: 7.0, w: 9.5, h: 0.3, fontSize: 10, color: C.accent6, margin: 0 } } },
    ],
    slideNumber: { x: 12.2, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: C.accent6, align: "right" },
  });

  const ic = {
    hospital: await icon("MdLocalHospital", HEX.accent2), warn: await icon("MdWarningAmber", HEX.accent3),
    check: await icon("MdCheckCircleOutline", HEX.accent4), eval: await icon("MdInsights", HEX.accent2),
    tune: await icon("MdTune", HEX.accent2), shield: await icon("MdVerifiedUser", HEX.accent2),
    dash: await icon("MdDashboard", HEX.accent2), bug: await icon("MdBugReport", HEX.accent5),
    memory: await icon("MdMemory", HEX.accent2), timer: await icon("MdTimer", HEX.accent2),
    replay: await icon("MdReplay", HEX.accent4), science: await icon("MdScience", HEX.accent2),
  };

  function card(slide, x, y, w, h, opts = {}) {
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: opts.fill || HEX.lt2 },
      line: { color: opts.fill || HEX.lt2, width: 0.75 }, objectName: opts.name || "card" });
  }
  function iconCircle(slide, x, y, img, d = 0.62) {
    slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: "FFFFFF" }, line: { color: "D0D7DE", width: 0.75 } });
    slide.addImage({ data: img, x: x + d * 0.18, y: y + d * 0.18, w: d * 0.64, h: d * 0.64 });
  }
  function text(slide, t, o) { slide.addText(t, { isTextBox: true, margin: 0, fontSize: 16, color: HEX.dk1, ...o }); }
  const sections = new Set(["Introduction"]);
  function newSlide(title, section) {
    if (!sections.has(section)) { pres.addSection({ title: section }); sections.add(section); }
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
    s.addText(title, { placeholder: "title" });
    return s;
  }
  const chartText = { catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt",
    legendFontFace: "+mn-lt", titleFontFace: "+mn-lt", catAxisLabelColor: MUTED, valAxisLabelColor: MUTED,
    catAxisLabelFontSize: 12, valAxisLabelFontSize: 11, dataLabelFontSize: 11, legendFontSize: 12,
    valGridLine: { color: "E3E6EA", size: 0.75 }, catGridLine: { style: "none" } };

  const g = D.gaps, fb = D.fail.boundary_band, rc = D.rc, ns = D.n_split;

  // ---------- 1. cover ----------
  pres.addSection({ title: "Introduction" });
  let s = pres.addSlide({ masterName: "COVER", sectionTitle: "Introduction" });
  s.addText("Uncertainty-Gated Brain Tumor Segmentation Across Hospitals", { placeholder: "title" });
  s.addText("Engineering a Trustworthy ML-Enabled Medical Imaging System · Final Presentation, Applied Track",
    { placeholder: "body" });
  text(s, [{ text: "Dev Patel (101042729)", options: { breakLine: true } }, { text: "Priyanka Gupta (101008820)", options: { breakLine: true } },
    { text: "Slesha Vora (101043167)" }], { x: 0.8, y: 5.05, w: 6.5, h: 1.0, fontSize: 15, color: HEX.dk1 });
  text(s, "Ontario Tech University, Oshawa, Canada", { x: 0.8, y: 6.1, w: 6.5, h: 0.4, fontSize: 14, color: MUTED });
  s.addImage({ path: path.join(R, "screenshots", "viewer_flagged_model.png"), x: 7.65, y: 1.5, w: 5.1, h: 3.43,
    altText: "Dashboard viewer on a held-out case flagged Needs review" });
  text(s, "Held-out case flagged “Needs review” by the trust gate", { x: 7.65, y: 5.0, w: 5.1, h: 0.4, fontSize: 12, color: MUTED });
  s.addNotes("Introduce the team and the one-sentence pitch: we took nnU-Net, the standard open-source tumor " +
    "segmentation framework, and added the engineering that tells you when it is safe to trust it at a new hospital.");

  // ---------- 2. problem ----------
  s = newSlide("The problem: silent failure at a new hospital", "Introduction");
  text(s, "A segmentation model trained at some hospitals can lose accuracy at another one, and its masks look just as " +
    "confident either way. Standard validation never tests this.", { x: 0.6, y: 1.35, w: 12.1, h: 0.8, fontSize: 18 });
  const stats = [["1,251", "labeled MRI cases\n(FeTS 2022)"], ["23", "institutions"], ["71%", "of cases from just\n2 institutions"],
    ["> 61%", "of institutions have\nfewer than 15 cases"]];
  stats.forEach(([big, lab], i) => {
    const x = 0.6 + i * 3.08;
    card(s, x, 2.5, 2.8, 2.3);
    text(s, big, { x: x + 0.25, y: 2.7, w: 2.3, h: 1.0, fontSize: 48, bold: true, color: HEX.dk2, fontFace: THEME.headFontFace });
    text(s, lab, { x: x + 0.25, y: 3.75, w: 2.3, h: 0.9, fontSize: 15, color: MUTED });
  });
  iconCircle(s, 0.6, 5.3, ic.warn);
  text(s, [{ text: "Engineering question: ", options: { bold: true } },
    { text: "can the software measure accuracy at unseen hospitals, and say “check this one” when it is likely wrong?" }],
    { x: 1.4, y: 5.25, w: 11.3, h: 0.75, fontSize: 18, valign: "middle" });
  s.addNotes("FeTS 2022 records which hospital each case came from, which makes this measurable. The imbalance is why a " +
    "naive leave-one-hospital-out split does not work.");

  // ---------- 3. base system ----------
  s = newSlide("Base system: nnU-Net as it ships", "Introduction");
  const rowsBase = [
    ["Part", "nnU-Net / FeTS as is", "Limitation", "Our enhancement"],
    ["Evaluation", "random 5-fold cross-validation", "never tests an unseen hospital", "site-held-out harness (C1)"],
    ["Robustness", "default augmentation", "no shift mitigations compared", "mitigation variants + TTA (C2)"],
    ["Uncertainty", "probabilities only; mirroring averaged inside", "no case score, no review decision", "uncertainty monitor + trust gate (C3)"],
    ["Interface", "NIfTI files in separate tools", "no view of mask + uncertainty + flag", "QC dashboard (C4)"],
    ["Verification", "framework unit tests", "nothing tied to requirements", "R1–R8 traced to tests, CI, Docker (C4)"],
  ];
  s.addTable(rowsBase.map((r, i) => r.map((c) => ({ text: c, options: {
    bold: i === 0, color: i === 0 ? "FFFFFF" : HEX.dk1, fill: { color: i === 0 ? HEX.dk2 : (i % 2 ? "FFFFFF" : HEX.lt2) },
    fontSize: 14, valign: "middle" } }))), { x: 0.6, y: 1.45, w: 12.1, colW: [1.9, 3.4, 3.4, 3.4], rowH: 0.62,
    border: { type: "solid", pt: 0.5, color: "D0D7DE" }, margin: 0.08 });
  s.addNotes("This is the current-state analysis the applied track asks for. Each row is a gap we confirmed in the " +
    "nnU-Net documentation and source before designing.");

  // ---------- 4. contributions ----------
  s = newSlide("Four contributions", "Design");
  const contrib = [[ic.eval, "C1 · Site-held-out harness", "Five site groups; each fold holds one group out entirely. Leakage checked, not assumed."],
    [ic.tune, "C2 · Shift mitigations", "Stronger augmentation, style augmentation, standardization and test-time adaptation under one budget."],
    [ic.shield, "C3 · Uncertainty monitor", "Voxel entropy from members × flips, a boundary-band case score and a trust gate: flag = score > limit."],
    [ic.dash, "C4 · QC dashboard + tests", "Viewer, review queue, explorer, model card; requirements R1–R8 traced to automated tests."]];
  contrib.forEach(([img, h, b], i) => {
    const x = 0.6 + (i % 2) * 6.15, y = 1.45 + Math.floor(i / 2) * 2.65;
    card(s, x, y, 5.95, 2.4);
    iconCircle(s, x + 0.3, y + 0.3, img, 0.75);
    text(s, h, { x: x + 1.25, y: y + 0.3, w: 4.5, h: 0.6, fontSize: 20, bold: true, color: HEX.dk2 });
    text(s, b, { x: x + 1.25, y: y + 0.95, w: 4.45, h: 1.3, fontSize: 15, color: HEX.dk1, valign: "top" });
  });
  s.addNotes("The model itself is not the contribution; the engineering around it is.");

  // ---------- 5. architecture ----------
  s = newSlide("Architecture", "Design");
  s.addImage({ path: path.join(R, "figures", "architecture.png"), x: 1.1, y: 1.3, w: 11.1, h: 5.4 });
  s.addNotes("Grey boxes are reused from nnU-Net and FeTS, blue boxes are ours. The trust gate is the safety component: " +
    "a pure function of the score and a limit, so a reviewer can always predict and audit it.");

  // ---------- 6. protocol + gate ----------
  s = newSlide("Protocol and trust gate", "Design");
  s.addImage({ path: path.join(R, "figures", "protocol.png"), x: 0.6, y: 1.4, w: 6.0, h: 3.86 });
  text(s, "Each fold withholds one site group; the model never sees it. In-site performance comes from a within-site split.",
    { x: 0.6, y: 5.45, w: 6.0, h: 0.9, fontSize: 15, color: MUTED });
  card(s, 7.0, 1.4, 5.7, 4.95, { fill: "F6F8FA" });
  text(s, "The gate (src/btqc/uncertainty/gate.py)", { x: 7.3, y: 1.6, w: 5.2, h: 0.4, fontSize: 16, bold: true, color: HEX.dk2 });
  text(s, "def flag(score, review_limit) -> bool:\n    if isnan(score):\n        return True      # fail-safe\n" +
    "    return score > review_limit", { x: 7.3, y: 2.1, w: 5.2, h: 1.5, fontSize: 15, fontFace: "Courier New", color: HEX.dk1 });
  text(s, [{ text: "Score: ", options: { bold: true } }, { text: "mean voxel entropy in a 3-voxel band around the predicted tumor boundary.", options: { breakLine: true } },
    { text: "Limit: ", options: { bold: true } }, { text: `fixed on in-site validation (80th percentile) = ${f3(fb && fb.review_limit)}, never tuned on held-out cases.`, options: { breakLine: true } },
    { text: "Failure: ", options: { bold: true } }, { text: "WT or ET Dice < 0.7, fixed before evaluation." }],
  { x: 7.3, y: 3.75, w: 5.2, h: 2.4, fontSize: 15, valign: "top", paraSpaceAfter: 6 });
  s.addNotes("Freezing the threshold and the limit before scoring held-out cases is a small but real guard against tuning on the test set.");

  // ---------- 7. what we ran ----------
  s = newSlide("What we ran on a 4 GB laptop GPU", "Results");
  const ran = [[`${D.n_epochs_run || D.epochs}`, "epochs, baseline nnU-Net\n(full protocol: 100)"],
    [D.epoch_min ? `${Math.round(D.epoch_min)} min` : "–", "per epoch on a\nGTX 1650 Ti (4 GB)"],
    ["7", "unseen institutions\nin the held-out group"],
    [`${(ns.val || 0) + (ns.insite_test || 0) + (ns.heldout || 0)}`, `test cases (${ns.insite_test || 0} in-site,\n${ns.heldout || 0} held-out, ${ns.val || 0} val)`]];
  ran.forEach(([big, lab], i) => {
    const x = 0.6 + i * 3.08;
    card(s, x, 1.5, 2.8, 2.2);
    text(s, big, { x: x + 0.25, y: 1.65, w: 2.3, h: 0.95, fontSize: 40, bold: true, color: HEX.dk2, fontFace: THEME.headFontFace });
    text(s, lab, { x: x + 0.25, y: 2.65, w: 2.4, h: 0.95, fontSize: 14, color: MUTED });
  });
  const nv = D.nnunet_val;
  text(s, [{ text: "Scope, honestly: ", options: { bold: true } },
    { text: "one method, one held-out fold, one seed, sampled test sets. The other 3 mitigations, 4 folds and the seed ensemble need ~31 h per training run on this GPU and are future work." + (nv ? ` nnU-Net's own validation of the trained model: Dice ${f3(nv.WT)} / ${f3(nv.TC)} / ${f3(nv.ET)} (WT/TC/ET) on ${nv.n} cases.` : "") }],
  { x: 0.6, y: 4.05, w: 12.1, h: 1.3, fontSize: 16, valign: "top" });
  iconCircle(s, 0.6, 5.55, ic.memory);
  text(s, "The planned 4 GB configuration ran out of memory; a measured 80×112×80 patch with cuDNN search off fits in ~3 GB usable.",
    { x: 1.4, y: 5.5, w: 11.3, h: 0.75, fontSize: 15, color: MUTED, valign: "middle" });

  // ---------- 8. accuracy ----------
  s = newSlide("Accuracy at seen vs unseen hospitals", "Results");
  const regs = ["WT", "TC", "ET"].filter((r) => g[r + "_dice"]);
  s.addChart(pres.charts.BAR, [
    { name: "In-site (seen hospitals)", labels: regs.map((r) => REG[r]), values: regs.map((r) => +g[r + "_dice"].insite_mean.toFixed(3)) },
    { name: "Held-out (7 unseen hospitals)", labels: regs.map((r) => REG[r]), values: regs.map((r) => +g[r + "_dice"].heldout_mean.toFixed(3)) },
  ], { x: 0.6, y: 1.35, w: 7.4, h: 5.3, barDir: "col", barGrouping: "clustered", chartColors: [HEX.accent2, HEX.accent3],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", valAxisMinVal: 0, valAxisMaxVal: 1,
    valAxisLabelFormatCode: "0.0", showLegend: true, legendPos: "b", showTitle: true, title: "Mean Dice (higher is better)",
    titleFontSize: 14, titleColor: HEX.dk1, ...chartText });
  const topGap = Math.max(...regs.map((r) => g[r + "_dice"].gap));
  const bigRegs = regs.filter((r) => g[r + "_dice"].gap >= topGap - 0.005);  // near-ties are named together
  card(s, 8.4, 1.45, 4.3, 5.1);
  text(s, "Gap (in-site − held-out)", { x: 8.7, y: 1.65, w: 3.8, h: 0.4, fontSize: 16, bold: true, color: HEX.dk2 });
  regs.forEach((r, i) => {
    const x = g[r + "_dice"];
    text(s, [{ text: `${REG[r]}: `, options: { bold: true } }, { text: `${x.gap >= 0 ? "+" : ""}${f3(x.gap)}`, options: { breakLine: true } },
      { text: `95% CI [${f3(x.gap_lo)}, ${f3(x.gap_hi)}]`, options: { color: MUTED, fontSize: 13 } }],
    { x: 8.7, y: 2.2 + i * 0.95, w: 3.8, h: 0.85, fontSize: 16, valign: "top" });
  });
  const anySig = regs.some((r) => g[r + "_dice"].gap_lo > 0);
  text(s, `Largest drop: ${bigRegs.map((r) => REG[r].toLowerCase()).join(" and ")}` +
    (bigRegs.includes("ET") ? ", as H1 predicted for ET. " : ". ") + (anySig ? "Some intervals exclude 0." :
    "Every interval includes 0: a trend, not yet a proven effect."), { x: 8.7, y: 5.1, w: 3.8, h: 1.3, fontSize: 14, color: MUTED, valign: "top" });
  s.addNotes("Read this as a pilot: the direction matches the hypothesis, but with this sample size the gap is not significant.");

  // ---------- 9. per institution ----------
  s = newSlide("Unseen hospitals are uneven", "Results");
  const inst = D.inst.filter((x) => x.n > 0);
  s.addChart(pres.charts.BAR, [{ name: "Held-out WT Dice", labels: inst.map((x) => `Inst. ${x.institution} (n=${x.n})`),
    values: inst.map((x) => +x.WT.toFixed(3)) }], { x: 0.6, y: 1.35, w: 8.0, h: 5.3, barDir: "bar", chartColors: [HEX.accent2],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", valAxisMinVal: 0, valAxisMaxVal: 1,
    showLegend: false, showTitle: true, title: "Whole-tumor Dice per held-out institution", titleFontSize: 14, titleColor: HEX.dk1, ...chartText });
  card(s, 9.0, 1.45, 3.7, 3.3);
  iconCircle(s, 9.3, 1.7, ic.hospital);
  text(s, "Most unseen hospitals are segmented about as well as seen ones; the average drop comes from a few. Bars from one or two cases are anecdotes, not estimates.",
    { x: 9.3, y: 2.55, w: 3.15, h: 2.0, fontSize: 15, valign: "top" });

  // ---------- 10. failure detection ----------
  s = newSlide("The gate catches the failures", "Results");
  if (fb) {
    const st2 = [[f2(fb.auroc), `failure-detection AUROC\n95% CI ${f2(fb.lo)}–${f2(fb.hi)} (target ≥ 0.75)`],
      [pct(fb.fail_rate_flagged), "of flagged cases\nhad failed"], [pct(fb.fail_rate_unflagged), "of unflagged cases\nhad failed"]];
    st2.forEach(([b, l], i) => {
      card(s, 0.6, 1.45 + i * 1.75, 4.2, 1.55, { fill: i === 1 ? "FBF1E0" : i === 2 ? "E7F4EC" : HEX.lt2 });
      text(s, b, { x: 0.85, y: 1.55 + i * 1.75, w: 1.8, h: 1.35, fontSize: 40, bold: true, fontFace: THEME.headFontFace,
        color: i === 1 ? HEX.accent3 : i === 2 ? HEX.accent4 : HEX.dk2, valign: "middle" });
      text(s, l, { x: 2.7, y: 1.55 + i * 1.75, w: 2.0, h: 1.35, fontSize: 13, color: MUTED, valign: "middle" });
    });
  }
  if (rc && rc.coverage) {
    s.addChart(pres.charts.LINE, [{ name: "Mean Dice of accepted cases", labels: rc.coverage.map((c) => Math.round(c * 100) + "%"),
      values: rc.mean_dice.map((v) => +v.toFixed(3)) }], { x: 5.2, y: 1.35, w: 7.5, h: 4.2, chartColors: [HEX.accent2],
      lineSize: 2.5, lineDataSymbol: "circle", lineDataSymbolSize: 6, valAxisMinVal: 0.6, valAxisMaxVal: 1, showLegend: false,
      showTitle: true, title: "Risk-coverage: defer the most uncertain cases first", titleFontSize: 14, titleColor: HEX.dk1,
      catAxisTitle: "coverage (share of cases accepted)", showCatAxisTitle: true, catAxisTitleFontSize: 12, catAxisTitleColor: MUTED,
      valAxisLabelFormatCode: "0.00", ...chartText });
    text(s, `Accepting the 80% most certain held-out cases raises mean Dice from ${f3(rc.dice_full)} to ${f3(rc.dice_at_80)}.`,
      { x: 5.2, y: 5.7, w: 7.5, h: 0.7, fontSize: 16, bold: true, color: HEX.dk2 });
  }
  s.addNotes(fb ? `${fb.n_failed} of ${fb.n} held-out cases failed. The gate flagged ${pct(fb.flagged_frac)} of cases. ` +
    "H3 asks for an AUROC interval above 0.5 and a Dice gain from deferral; both hold on this fold." : "");

  // ---------- 11. shift + E3/E4 ----------
  s = newSlide("Shift, mitigation and uncertainty estimator", "Results");
  if (D.emb) {
    const rows = D.emb.rows;
    s.addChart(pres.charts.BAR, [{ name: "Embedding distance", labels: rows.map((x) => x.group + (x.role === "held-out" ? " (held out)" : "")),
      values: rows.map((x) => +x.frechet.toFixed(3)) }], { x: 0.6, y: 1.35, w: 5.9, h: 4.0, barDir: "bar", chartColors: [HEX.accent2],
      showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000", showLegend: false, showTitle: true,
      title: "E2 · How different each group looks to the model", titleFontSize: 14, titleColor: HEX.dk1, ...chartText });
    const top = [...rows].sort((a, b) => b.frechet - a.frechet)[0];
    text(s, `Most distinct: ${top.group}. The held-out group is among the least shifted, consistent with its small gap; LGG-only is the fold to run next.`,
      { x: 0.6, y: 5.45, w: 5.9, h: 1.0, fontSize: 14, color: MUTED, valign: "top" });
  }
  card(s, 6.9, 1.45, 5.8, 2.35);
  text(s, "E3 · Test-time adaptation vs baseline (held-out)", { x: 7.15, y: 1.6, w: 5.3, h: 0.4, fontSize: 16, bold: true, color: HEX.dk2 });
  if (D.e3 && D.e3.status === "ok") {
    text(s, D.e3.comparisons.map((c, i) => ({ text: `${REG[c.region]}: ${c.diff_mean >= 0 ? "+" : ""}${f3(c.diff_mean)} [${f3(c.diff_lo)}, ${f3(c.diff_hi)}]`,
      options: { breakLine: i < D.e3.comparisons.length - 1 } })), { x: 7.15, y: 2.05, w: 5.3, h: 1.1, fontSize: 15, valign: "top" });
    const e3sig = D.e3.comparisons.some((c) => c.wilcoxon && c.wilcoxon.p_holm < 0.05);
    text(s, e3sig ? "Significant after Holm correction: H2 supported for this mitigation."
      : "Small gains, none significant after Holm correction: H2 not shown on this fold.",
      { x: 7.15, y: 3.2, w: 5.3, h: 0.45, fontSize: 14, color: MUTED });
  } else {
    text(s, "Pending: results are added when the run finishes.", { x: 7.15, y: 2.1, w: 5.3, h: 0.5, fontSize: 15, color: MUTED });
  }
  card(s, 6.9, 4.05, 5.8, 2.4);
  text(s, "E4 · 8 flip members vs 1 prediction", { x: 7.15, y: 4.2, w: 5.3, h: 0.4, fontSize: 16, bold: true, color: HEX.dk2 });
  if (D.e4) {
    const a8 = (D.e4.flips_8.failure || [])[0], a1 = (D.e4.flips_1.failure || [])[0];
    const d8 = D.e4.flips_8.mean_dice, d1 = D.e4.flips_1.mean_dice;
    text(s, [{ text: `Failure AUROC: ${a8 ? f2(a8.auroc) : "–"} vs ${a1 ? f2(a1.auroc) : "–"}`, options: { breakLine: true } },
      { text: `Mean WT Dice: ${f3(d8.WT)} vs ${f3(d1.WT)}`, options: { breakLine: true } },
      { text: `Latency: ~${D.r7r8 ? Math.round(D.r7r8.r8_mean_total_8_flips_s) : "–"} s vs ~${D.r7r8 ? Math.round(D.r7r8.r8_mean_total_1_flip_s) : "–"} s per case` }],
    { x: 7.15, y: 4.7, w: 5.3, h: 1.6, fontSize: 15, valign: "top", paraSpaceAfter: 4 });
  } else {
    text(s, "Pending: results are added when the run finishes.", { x: 7.15, y: 4.7, w: 5.3, h: 0.5, fontSize: 15, color: MUTED });
  }

  // ---------- 12. quality ----------
  s = newSlide("Verification: requirements, tests, reproducibility", "Results");
  const r78 = D.r7r8;
  const q = [[ic.check, D.tests_line || "–", `automated tests (unit, integration, metamorphic, regression, performance)${D.coverage ? `, ${Math.round(D.coverage)}% coverage` : ""}`],
    [ic.dash, D.ui_tests ? `${D.ui_tests.tests - D.ui_tests.failures - D.ui_tests.errors} / ${D.ui_tests.tests}` : "–", "browser tests pass in headless Chromium (orientation, flag flip, review, WebGL, mobile)"],
    [ic.replay, r78 ? "identical" : "–", r78 ? `R7: re-running inference gives 100% label agreement; score differs by < ${r78.r7_max_score_abs_diff.toExponential(0)}` : "R7 re-run"],
    [ic.timer, r78 ? `${Math.round(r78.r8_mean_total_8_flips_s)} s / ${Math.round(r78.r8_mean_total_1_flip_s)} s` : "–", "R8 latency per case, 8 flips / 1 flip, vs a 60 s target: met only without TTA on this GPU"],
    [ic.bug, "2 bugs", "found only on real model output (wrong review limit in the viewer, collapsed views); fixed with regression tests"]];
  q.forEach(([img, b, l], i) => {
    const y = 1.4 + i * 1.07;
    iconCircle(s, 0.6, y + 0.1, img, 0.7);
    text(s, b, { x: 1.55, y, w: 3.6, h: 0.9, fontSize: 22, bold: true, color: HEX.dk2, valign: "middle" });
    text(s, l, { x: 5.2, y, w: 7.5, h: 0.9, fontSize: 15, color: HEX.dk1, valign: "middle" });
  });

  // ---------- 13. before / after ----------
  s = newSlide("Before vs after", "Results");
  card(s, 0.6, 1.4, 5.95, 4.0, { fill: "F6F8FA" });
  card(s, 6.75, 1.4, 5.95, 4.0, { fill: "E8F1FA" });
  text(s, "Before: nnU-Net as is", { x: 0.9, y: 1.6, w: 5.4, h: 0.5, fontSize: 22, bold: true, color: MUTED });
  text(s, "After: this work", { x: 7.05, y: 1.6, w: 5.4, h: 0.5, fontSize: 22, bold: true, color: HEX.dk2 });
  const before = ["One cross-validated Dice; no number for unseen hospitals", "Every mask looks equally trustworthy",
    rc ? `Accept everything: mean held-out Dice ${f3(rc.dice_full)}` : "Accept everything", "Open NIfTI files in separate tools", "Framework tests only"];
  const after = ["Held-out group of 7 hospitals; gap per region with intervals",
    fb ? `Gate flags ${pct(fb.flagged_frac)} of cases; ${pct(fb.fail_rate_flagged)} of them failed (vs ${pct(fb.fail_rate_unflagged)})` : "Gate flags uncertain cases",
    rc ? `Accept unflagged 80%: mean Dice ${f3(rc.dice_at_80)} (${rc.gain_at_80 >= 0 ? "+" : ""}${f3(rc.gain_at_80)})` : "Defer uncertain cases",
    "One page: slices, 3D, uncertainty, flag, review log", "R1–R8 traced to tests; CI; reproducible inference"];
  text(s, before.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < before.length - 1 } })),
    { x: 0.9, y: 2.3, w: 5.4, h: 2.9, fontSize: 16, color: HEX.dk1, valign: "top", paraSpaceAfter: 10 });
  text(s, after.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < after.length - 1 } })),
    { x: 7.05, y: 2.3, w: 5.4, h: 2.9, fontSize: 16, color: HEX.dk1, valign: "top", paraSpaceAfter: 10 });
  iconCircle(s, 0.6, 5.75, ic.science);
  text(s, "The segmentation is not more accurate; what changes is what a user can know about it, and which cases a person checks.",
    { x: 1.4, y: 5.7, w: 11.3, h: 0.75, fontSize: 17, bold: true, color: HEX.dk2, valign: "middle" });
  s.addNotes("The segmentation is not more accurate. What changes is what a user can know about it.");

  // ---------- 14. demo ----------
  s = newSlide("Demo: the QC dashboard on a flagged case", "Demo");
  s.addImage({ path: path.join(R, "screenshots", "viewer_flagged_model.png"), x: 0.6, y: 1.3, w: 8.3, h: 5.58 });
  card(s, 9.2, 1.3, 3.5, 5.58);
  text(s, [{ text: "Walkthrough", options: { bold: true, color: HEX.dk2, fontSize: 18, breakLine: true } },
    { text: "Home → Viewer: a held-out case", options: { bullet: true, breakLine: true } },
    { text: "Regions + uncertainty heat map", options: { bullet: true, breakLine: true } },
    { text: "“Needs review”: drag the limit across the score", options: { bullet: true, breakLine: true } },
    { text: "Review queue: accept / reject, logged", options: { bullet: true, breakLine: true } },
    { text: "Generalization explorer + model card", options: { bullet: true } }],
  { x: 9.45, y: 1.5, w: 3.1, h: 5.2, fontSize: 15, valign: "top", paraSpaceAfter: 8 });
  s.addNotes("Live demo at http://127.0.0.1:8000 (python scripts/tasks.py app). Fallback: dist/btqc_demo.html works offline.");

  // ---------- 15. limitations ----------
  s = newSlide("Limitations and future work", "Conclusion");
  const lim = [["Pilot scale", "1 method, 1 fold, 1 seed, 10 epochs, sampled test cases → wide intervals"],
    ["Not run", "3 training-time mitigations (H2), the LGG-only and other folds (H1), deep ensembles / MC dropout (E4), shift → gap correlation (E2)"],
    ["Hardware", "4 GB GPU: 8-flip inference misses the 60 s target; a larger GPU runs the same scripts unchanged"],
    ["Validity", "site is a proxy for scanner/protocol; Dice < 0.7 is a proxy for clinical failure"],
    ["Optional", "literature-retrieval panel not built (scoped “only if time allows”)"]];
  lim.forEach(([h, b], i) => {
    const y = 1.4 + i * 1.07;
    card(s, 0.6, y, 12.1, 0.9);
    text(s, h, { x: 0.85, y, w: 2.3, h: 0.9, fontSize: 17, bold: true, color: HEX.dk2, valign: "middle" });
    text(s, b, { x: 3.2, y, w: 9.3, h: 0.9, fontSize: 15, valign: "middle" });
  });

  // ---------- 16. conclusion ----------
  s = newSlide("Takeaways", "Conclusion");
  const take = [[ic.eval, "We can now measure it", "Accuracy at hospitals the model never saw, per region, with intervals."],
    [ic.shield, "The software can say “check this one”", fb ? `Uncertainty flags failures with AUROC ${f2(fb.auroc)}; accepted cases score higher.` : "Uncertainty flags likely failures."],
    [ic.science, "Engineered, not just trained", "Requirements traced to tests, frozen thresholds, reproducible runs, honest scope."]];
  take.forEach(([img, h, b], i) => {
    const x = 0.6 + i * 4.1;
    card(s, x, 1.5, 3.9, 3.6);
    iconCircle(s, x + 0.3, 1.8, img, 0.8);
    text(s, h, { x: x + 0.3, y: 2.8, w: 3.3, h: 0.9, fontSize: 19, bold: true, color: HEX.dk2, valign: "top" });
    text(s, b, { x: x + 0.3, y: 3.7, w: 3.3, h: 1.3, fontSize: 15, valign: "top" });
  });
  text(s, "Thank you. Questions?", { x: 0.6, y: 5.35, w: 12.1, h: 0.75, fontSize: 28, bold: true, color: HEX.dk2,
    fontFace: THEME.headFontFace, align: "center" });
  text(s, [{ text: "Code: github.com/DevPatel1704/brain-tumor-qc",
    options: { hyperlink: { url: "https://github.com/DevPatel1704/brain-tumor-qc" } } }],
    { x: 0.6, y: 6.1, w: 12.1, h: 0.4, fontSize: 15, color: HEX.accent2, align: "center" });

  await pres.writeFile({ fileName: OUT });
  const { applyTheme } = require(process.env.PPTX_SKILL + "/scripts/apply_theme.js");
  await applyTheme(OUT, THEME);
  console.log("wrote " + OUT);
}

main().catch((e) => { console.error(e); process.exit(1); });
