"""Build the IEEE CS style technical report as a Word document (no LaTeX on
this machine): docs/report/btqc_report.docx.

Every number is read at build time from files produced by real runs
(data/phase0_summary.json, results/*.json, results/ui_junit.xml). Missing
inputs are printed as "not run". Synthetic figures carry their label.

    python scripts/build_report.py
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

from btqc.config import REPO_ROOT, load_config

R = REPO_ROOT / "results"


def workload_figure(out: Path) -> dict[str, Any] | None:
    """Fraction of the real validation cases flagged as a function of the review limit, from the rule-based
    EXAMPLE scores (not a model). Shows how the gate behaves on real scans; says nothing about accuracy."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    from btqc.uncertainty.gate import flag

    d = R / "predictions" / "example_rule_based" / "example"
    if not d.exists():
        return None
    scores = []
    for f in sorted(d.glob("*.json")):
        sc = json.loads(f.read_text(encoding="utf-8")).get("scores", {}).get("boundary_band")
        scores.append(float("nan") if sc is None else float(sc))
    if not scores:
        return None
    lim = np.linspace(0, 0.6, 121)
    frac = [np.mean([flag(x, float(t)) for x in scores]) for t in lim]
    default = float(load_config("uncertainty")["gate"]["default_review_limit"])
    at_default = float(np.mean([flag(x, default) for x in scores]))
    fig, ax = plt.subplots(figsize=(3.6, 2.6))
    ax.plot(lim, frac, color="#2a78d6", linewidth=2)
    ax.axvline(default, color="#9a9a95", linestyle="--", linewidth=1)
    ax.annotate(f"default limit {default:.2f}: {at_default:.0%} flagged", (default, at_default),
                xytext=(default + 0.03, at_default + 0.12), fontsize=7, arrowprops={"arrowstyle": "-", "lw": 0.6})
    ax.set_xlabel("review limit", fontsize=8)
    ax.set_ylabel("fraction of cases flagged", fontsize=8)
    ax.set_ylim(0, 1.02)
    ax.tick_params(labelsize=7)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(color="#e3e3e0", linewidth=0.6)
    ax.set_title(f"Review workload, {len(scores)} validation cases\n[EXAMPLE scores from brightness rules, not a model]",
                 fontsize=8)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=170)
    plt.close(fig)
    finite = np.array([x for x in scores if x == x])
    return {"n": len(scores), "at_default": at_default, "default": default, "median": float(np.median(finite)),
            "q10": float(np.quantile(finite, 0.1)), "q90": float(np.quantile(finite, 0.9)),
            "n_nan": int(sum(1 for x in scores if x != x))}
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI",
         "XVII", "XVIII", "XIX", "XX", "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI", "XXVII", "XXVIII", "XXIX",
         "XXX"]
# Repository link printed in the report (BTQC_REPO_URL overrides it).
REPO_URL = __import__("os").environ.get("BTQC_REPO_URL", "https://github.com/DevPatel1704/brain-tumor-qc")


def j(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def junit(path: Path) -> dict[str, int] | None:
    if not path.exists():
        return None
    root = ET.parse(path).getroot()
    s = root if root.tag == "testsuite" else root.find("testsuite")
    assert s is not None
    return {k: int(s.get(k, 0)) for k in ("tests", "failures", "errors", "skipped")}


class Report:
    def __init__(self) -> None:
        self.doc = Document()
        st = self.doc.styles["Normal"]
        st.font.name = "Times New Roman"
        st.font.size = Pt(10)
        st.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        pf = st.paragraph_format
        pf.space_after = Pt(3)
        pf.space_before = Pt(0)
        pf.line_spacing = 1.0
        for s in self.doc.sections:
            s.left_margin = s.right_margin = Inches(0.7)
            s.top_margin = s.bottom_margin = Inches(0.75)
        self.fig_n = 0
        self.tab_n = 0
        self.sec_n = 0
        self.sub_n = 0

    @staticmethod
    def _columns(section: Any, n: int) -> None:
        cols = section._sectPr.xpath("./w:cols")
        el = cols[0] if cols else OxmlElement("w:cols")
        el.set(qn("w:num"), str(n))
        el.set(qn("w:space"), "360")
        if not cols:
            section._sectPr.append(el)

    def title(self, title: str, author: str, affil: str) -> None:
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(title)
        r.font.size = Pt(22)
        for line, size in ((author, 11), (affil, 10)):
            q = self.doc.add_paragraph()
            q.alignment = WD_ALIGN_PARAGRAPH.CENTER
            q.add_run(line).font.size = Pt(size)

    def two_columns(self) -> None:
        sec = self.doc.add_section(WD_SECTION.CONTINUOUS)
        self._columns(sec, 2)

    def abstract(self, text: str, terms: str) -> None:
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        r = p.add_run("Abstract—")
        r.bold = r.italic = True
        p.add_run(text).bold = True
        q = self.doc.add_paragraph()
        r = q.add_run("Index Terms—")
        r.italic = r.bold = True
        q.add_run(terms).italic = True

    def h1(self, text: str) -> None:
        self.sec_n += 1
        self.sub_n = 0
        roman = ROMAN[self.sec_n - 1]
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(8)
        r = p.add_run(f"{roman}. {text.upper()}")
        r.font.size = Pt(10)

    def h2(self, text: str) -> None:
        self.sub_n += 1
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        r = p.add_run(f"{chr(64 + self.sub_n)}. {text}")
        r.italic = True

    def para(self, text: str) -> None:
        p = self.doc.add_paragraph(text)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.first_line_indent = Inches(0.15)

    def bullets(self, items: list[str]) -> None:
        for it in items:
            p = self.doc.add_paragraph(it, style="List Bullet")
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    def code(self, text: str) -> None:
        for line in text.strip("\n").splitlines():
            p = self.doc.add_paragraph()
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(line)
            r.font.name = "Consolas"
            r.font.size = Pt(7.5)

    def figure(self, path: Path, caption: str, width: float = 3.3) -> None:
        self.fig_n += 1
        if path.exists():
            self.doc.add_picture(str(path), width=Inches(width))
            self.doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        else:
            self.para(f"[figure not available: {path.name} — not run]")
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f"Fig. {self.fig_n}. {caption}")
        r.font.size = Pt(8)

    def figure_wide(self, path: Path, caption: str, width: float = 6.8) -> None:
        """A figure spanning both columns: one-column section for the figure, then back to two columns."""
        sec = self.doc.add_section(WD_SECTION.CONTINUOUS)
        self._columns(sec, 1)
        self.figure(path, caption, width)
        sec = self.doc.add_section(WD_SECTION.CONTINUOUS)
        self._columns(sec, 2)

    def table(self, caption: str, header: list[str], rows: list[list[Any]], widths: list[float] | None = None) -> None:
        self.tab_n += 1
        roman = ROMAN[self.tab_n - 1]
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f"TABLE {roman}\n{caption.upper()}")
        r.font.size = Pt(8)
        t = self.doc.add_table(rows=1, cols=len(header))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, h in enumerate(header):
            c = t.rows[0].cells[i]
            c.text = ""
            run = c.paragraphs[0].add_run(h)
            run.bold = True
            run.font.size = Pt(7.5)
        for row in rows:
            cells = t.add_row().cells
            for i, v in enumerate(row):
                cells[i].text = ""
                run = cells[i].paragraphs[0].add_run(str(v))
                run.font.size = Pt(7.5)
        if widths:
            for row in t.rows:
                for i, w in enumerate(widths):
                    row.cells[i].width = Inches(w)
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)


def fmt(v: Any, d: int = 3) -> str:
    if v is None:
        return "not run"
    if isinstance(v, float):
        return f"{v:.{d}f}"
    return str(v)


REFS = [
    "S. Amershi et al., “Software engineering for machine learning: A case study,” in Proc. IEEE/ACM ICSE-SEIP, 2019, pp. 291–300, doi: 10.1109/ICSE-SEIP.2019.00042.",
    "D. Sculley et al., “Hidden technical debt in machine learning systems,” in Adv. Neural Inf. Process. Syst., vol. 28, 2015, pp. 2503–2511.",
    "E. Breck, S. Cai, E. Nielsen, M. Salib, and D. Sculley, “The ML test score: A rubric for ML production readiness and technical debt reduction,” in Proc. IEEE Int. Conf. Big Data, 2017, pp. 1123–1132, doi: 10.1109/BigData.2017.8258038.",
    "B. H. Menze et al., “The multimodal brain tumor image segmentation benchmark (BRATS),” IEEE Trans. Med. Imag., vol. 34, no. 10, pp. 1993–2024, 2015, doi: 10.1109/TMI.2014.2377694.",
    "S. Bakas et al., “Advancing The Cancer Genome Atlas glioma MRI collections with expert segmentation labels and radiomic features,” Sci. Data, vol. 4, Art. no. 170117, 2017, doi: 10.1038/sdata.2017.117.",
    "U. Baid et al., “The RSNA-ASNR-MICCAI BraTS 2021 benchmark on brain tumor segmentation and radiogenomic classification,” arXiv:2107.02314, 2021.",
    "F. Isensee, P. F. Jaeger, S. A. A. Kohl, J. Petersen, and K. H. Maier-Hein, “nnU-Net: A self-configuring method for deep learning-based biomedical image segmentation,” Nat. Methods, vol. 18, no. 2, pp. 203–211, 2021, doi: 10.1038/s41592-020-01008-z.",
    "O. Ronneberger, P. Fischer, and T. Brox, “U-Net: Convolutional networks for biomedical image segmentation,” in Proc. MICCAI, 2015, pp. 234–241, doi: 10.1007/978-3-319-24574-4_28.",
    "S. Pati et al., “The Federated Tumor Segmentation (FeTS) challenge,” arXiv:2105.05874, 2021.",
    "S. Pati et al., “Federated learning enables big data for rare cancer boundary detection,” Nat. Commun., vol. 13, Art. no. 7346, 2022, doi: 10.1038/s41467-022-33407-5.",
    "S. Bakas et al., “Identifying the best machine learning algorithms for brain tumor segmentation, progression assessment, and overall survival prediction in the BRATS challenge,” arXiv:1811.02629, 2018.",
    "V. M. Campello et al., “Multi-centre, multi-vendor and multi-disease cardiac segmentation: The M&Ms challenge,” IEEE Trans. Med. Imag., vol. 40, no. 12, pp. 3543–3554, 2021, doi: 10.1109/TMI.2021.3090082.",
    "S. Ali et al., “A multi-centre polyp detection and segmentation dataset for generalisability assessment,” Sci. Data, vol. 10, Art. no. 75, 2023, doi: 10.1038/s41597-023-01981-y.",
    "M. Manthe, S. Duffner, and C. Lartizien, “Federated brain tumor segmentation: An extensive benchmark,” Med. Image Anal., 2024, arXiv:2410.17265.",
    "K. Zhou, Z. Liu, Y. Qiao, T. Xiang, and C. C. Loy, “Domain generalization: A survey,” IEEE Trans. Pattern Anal. Mach. Intell., vol. 45, no. 4, pp. 4396–4415, 2023, doi: 10.1109/TPAMI.2022.3195549.",
    "C. Chen et al., “MaxStyle: Adversarial style composition for robust medical image segmentation,” in Proc. MICCAI, 2022, pp. 151–161, doi: 10.1007/978-3-031-16443-9_15.",
    "B. Lakshminarayanan, A. Pritzel, and C. Blundell, “Simple and scalable predictive uncertainty estimation using deep ensembles,” in Adv. Neural Inf. Process. Syst., vol. 30, 2017, arXiv:1612.01474.",
    "Y. Gal and Z. Ghahramani, “Dropout as a Bayesian approximation: Representing model uncertainty in deep learning,” in Proc. ICML, 2016, pp. 1050–1059, arXiv:1506.02142.",
    "C. Guo, G. Pleiss, Y. Sun, and K. Q. Weinberger, “On calibration of modern neural networks,” in Proc. ICML, 2017, pp. 1321–1330, arXiv:1706.04599.",
    "A. Jungo and M. Reyes, “Assessing reliability and challenges of uncertainty estimations for medical image segmentation,” in Proc. MICCAI, 2019, pp. 48–56, doi: 10.1007/978-3-030-32245-8_6.",
    "D. Wang, E. Shelhamer, S. Liu, B. Olshausen, and T. Darrell, “Tent: Fully test-time adaptation by entropy minimization,” in Proc. ICLR, 2021, arXiv:2006.10726.",
    "F. Isensee, P. Kickingereder, W. Wick, M. Bendszus, and K. H. Maier-Hein, “No New-Net,” in Proc. BrainLes (MICCAI workshop), 2018, arXiv:1809.10483.",
    "A. Ferreira et al., “How we won BraTS 2023 adult glioma challenge? Just faking it! Enhanced synthetic data augmentation and model ensemble for brain tumour segmentation,” arXiv:2402.17317, 2024.",
    "FANCL: Feature-guided attention network with curriculum learning for brain metastases segmentation, arXiv:2410.22057, 2024.",
]


def test_inventory() -> dict[str, int]:
    """Number of collected tests per category (pytest --collect-only)."""
    import subprocess
    import sys

    out = {}
    for d in ("unit", "integration", "metamorphic", "regression", "perf", "ui"):
        r = subprocess.run([sys.executable, "-m", "pytest", f"tests/{d}", "--collect-only", "-q"], cwd=REPO_ROOT,
                           capture_output=True, text=True)
        out[d] = sum("::" in line for line in r.stdout.splitlines())
    return out


def real_results() -> dict[str, Any] | None:
    """Everything the report needs from the site-held-out run, or None when no model result exists."""
    import glob
    import re

    import pandas as pd

    ev = j(R / "eval_summary.json")
    if not ev or ev.get("source") != "model":
        return None
    tcfg = load_config("train")
    out: dict[str, Any] = {"ev": ev, "folds": ev.get("folds", []), "methods": ev.get("methods", [])}
    out["gaps"] = {(g["region"], g["metric"]): g for g in ev["gaps"]
                   if g.get("gap") is not None and g["method"] == "baseline"}
    fail = [f for f in ev["failure"] if f["method"] == "baseline"]
    out["fail"] = {f["score"]: f for f in fail}
    rc = [r for r in ev["risk_coverage"] if r["method"] == "baseline" and r["score"] == "score_boundary_band"]
    out["rc"] = rc[0] if rc else None
    out["ece"] = {(e["split"], e["region"], e["mode"]): e["ece"] for e in ev["ece"] if e["method"] == "baseline"}
    cases = pd.read_csv(R / "cases.csv")
    cases = cases[cases.method == "baseline"]
    ok = cases[cases.status == "ok"]
    out["n_split"] = ok.groupby("split").size().to_dict()
    out["n_total_split"] = cases.groupby("split").size().to_dict()
    held = ok[ok.split == "heldout"]
    out["inst"] = (held.groupby("institution")
                   .agg(n=("case_id", "size"), WT=("dice_WT", "mean"), TC=("dice_TC", "mean"), ET=("dice_ET", "mean"))
                   .reset_index().sort_values("institution"))
    out["split_dice"] = ok.groupby("split")[["dice_WT", "dice_TC", "dice_ET"]].mean().to_dict("index")
    # nnU-Net's own validation of the trained fold and the measured epoch time
    fold_dirs = sorted(glob.glob(str(REPO_ROOT / "data" / "nnUNet_results" / "Dataset501_FeTS2022" /
                                     f"nnUNetTrainer_btqc__{tcfg['plans']}__{tcfg['configuration']}" / "fold_*")))
    out["nnunet_val"] = None
    out["epoch_s"] = None
    for fd in fold_dirs:
        sj = j(Path(fd) / "validation" / "summary.json")
        if sj:
            m = sj["mean"]
            out["nnunet_val"] = {"WT": m.get("(1, 2, 3)", {}).get("Dice"), "TC": m.get("(2, 3)", {}).get("Dice"),
                                 "ET": m.get("(3,)", {}).get("Dice"), "mean": sj["foreground_mean"]["Dice"],
                                 "n": len(sj.get("metric_per_case", []))}
        times = []
        for logf in glob.glob(str(Path(fd) / "training_log_*.txt")):
            times += [float(x) for x in re.findall(r"Epoch time: ([0-9.]+) s", Path(logf).read_text(errors="replace"))]
        if times:
            out["epoch_s"] = sum(times) / len(times)
            out["n_epochs_run"] = len(times)
    secs = []
    for logf in glob.glob(str(R / "train_logs" / "infer_mid*.log")):
        secs += [float(x) for x in re.findall(r": ([0-9.]+)s, score", Path(logf).read_text(errors="replace"))]
    out["infer_s"] = sum(secs) / len(secs) if secs else None
    out["e2"] = j(R / "e2_shift.json")
    out["emb"] = j(R / "e2_embedding_shift.json")
    out["e3"] = j(R / "e3_mitigations.json")
    out["e4tta"] = j(R / "e4_tta_compare.json")
    out["r7r8"] = j(R / "r7_r8.json")
    out["all_gaps"] = [g for g in ev["gaps"] if g.get("gap") is not None]
    out["all_fail"] = [f for f in ev["failure"] if f["score"] == "boundary_band"]
    out["e5"] = j(R / "e5_failure.json")
    out["tcfg"] = tcfg
    return out


def main() -> int:
    s0 = j(REPO_ROOT / "data" / "phase0_summary.json") or {}
    rr = real_results()
    inv = test_inventory()
    files = None
    inv_p = REPO_ROOT / "data" / "file_inventory.csv"
    if inv_p.exists():
        import pandas as pd

        files = pd.read_csv(inv_p)
    smoke = j(R / "smoke_G3.json")
    perf = j(R / "perf.json")
    e6 = j(R / "e6_software.json")
    site = j(R / "site_risk.json")
    synth = j(R / "eval_summary_synthetic.json")
    ui = junit(R / "ui_junit.xml")
    conv = j(REPO_ROOT / "data" / "processed" / "convert_log.json")
    ucfg = load_config("uncertainty")
    n_cases, n_files = s0.get("n_cases", "?"), s0.get("n_nifti", "?")

    rp = Report()
    rp.title("Uncertainty-Gated Brain Tumor Segmentation Across Hospitals: Engineering a Trustworthy ML-Enabled "
             "Medical Imaging System",
             "Technical Report, Applied Track\n"
             "Dev Patel (101042729), Priyanka Gupta (101008820), Slesha Vora (101043167)",
             "Ontario Tech University, Oshawa, Canada")
    rp.two_columns()
    import re

    tests_line = re.sub(r" in [0-9.]+s.*$", "", e6["pytest_summary"]) if e6 else "not run"
    if rr:
        gd = {r: rr["gaps"].get((r, "dice")) for r in ("WT", "TC", "ET")}
        fb = rr["fail"].get("boundary_band")
        ns = rr["n_split"]
        rp.abstract(
            "Segmentation models for brain tumor MRI are usually validated on data from the hospitals that trained "
            "them, and they can lose accuracy at a new hospital without any visible warning. This applied-track "
            "project extends nnU-Net and the FeTS 2022 multi-institution data with software-engineering controls the "
            "base tools lack: a site-held-out evaluation harness, domain-generalization mitigations under a common "
            "budget, an uncertainty-based trust gate that flags scans for review, and a browser quality-control "
            "dashboard, specified by eight requirements traced to automated tests. On a 4 GB laptop GPU we trained a "
            f"baseline nnU-Net for {rr['tcfg']['epochs']} epochs with one site group of 7 institutions held out, and "
            f"evaluated it on seeded random samples of in-site ({ns.get('insite_test', 0)}) and held-out "
            f"({ns.get('heldout', 0)}) test cases. In-site and held-out Dice were "
            + ", ".join(f"{gd[r]['insite_mean']:.2f}/{gd[r]['heldout_mean']:.2f} ({r})" for r in gd if gd[r])
            + "; the drop is largest for "
            + {"WT": "whole tumor", "TC": "tumor core", "ET": "enhancing tumor"}[
                max((r for r in gd if gd[r]), key=lambda r: gd[r]["gap"])]
            + (", and its bootstrap interval excludes zero for "
               + ", ".join(r for r in gd if gd[r] and gd[r]["gap_lo"] > 0) + ". "
               if any(gd[r] and gd[r]["gap_lo"] > 0 for r in gd) else
               ", but every bootstrap interval of the gap includes zero. ")
            + (f"The boundary-band uncertainty score detected held-out failures with AUROC {fb['auroc']:.2f} "
               f"(95% CI {fb['lo']:.2f}–{fb['hi']:.2f}); flagged cases failed {fb['fail_rate_flagged']:.0%} of the "
               f"time versus {fb['fail_rate_unflagged']:.0%} for unflagged cases. " if fb else "")
            + "The mitigation comparison and the other four folds were not run within the compute budget; the "
            f"result is a pilot. The software is verified by a test suite ({tests_line}).",
            "ML-enabled systems, safety-critical software, domain shift, uncertainty estimation, medical image "
            "segmentation, software testing, human-in-the-loop")
    else:
        rp.abstract(
        "Segmentation models for brain tumor MRI are usually validated on data from the hospitals that trained them, "
        "and they can lose accuracy at a new hospital without any visible warning. This applied-track project "
        "extends nnU-Net and the FeTS 2022 multi-institution data with software-engineering controls the base tools "
        "lack: a site-held-out evaluation harness, a set of domain-generalization mitigations under a common budget, "
        "an uncertainty-based trust gate that flags scans for review, and a browser quality-control dashboard. The "
        "system is specified by eight requirements traced to automated tests. The data available for this work were "
        f"{n_cases} unlabeled FeTS 2022 validation cases and the machine had no usable GPU, so no model was trained "
        "on real data and no accuracy, calibration or failure-detection result is reported. We report what was "
        "built and verified: a geometry pipeline proven by planted-voxel round trips in Python and in the browser, "
        "an nnU-Net smoke training on synthetic fixtures, a leakage-checked harness, a trust gate whose flag depends "
        f"only on a score and a limit, and a test suite ({tests_line}). The experiments are scripted and "
        "ready to run once labeled data and a GPU are available.",
        "ML-enabled systems, safety-critical software, domain shift, uncertainty estimation, medical image "
        "segmentation, software testing, human-in-the-loop")

    # I. Introduction
    rp.h1("Introduction")
    rp.para("Software with learned components fails in ways conventional testing does not reveal: data "
            "dependencies, silent degradation and weak monitoring [1]–[3]. In medical imaging a wrong segmentation can "
            "look as trustworthy as a right one. We study glioma sub-region segmentation from four MRI sequences "
            "(T1, contrast-enhanced T1, T2, FLAIR), reported as whole tumor (WT), tumor core (TC) and enhancing tumor "
            "(ET) as in the BraTS benchmarks [4]–[6]. Hospitals differ in scanners and protocols, so a model trained "
            "at some institutions may degrade at another while producing confident-looking masks.")
    rp.para("Following the applied track, we take nnU-Net [7], a self-configuring U-Net framework [8], and the "
            "FeTS 2022 data with real institution labels [9], [10], and add four contributions: (C1) a harness that "
            "measures the generalization gap at held-out site groups, (C2) a comparison of mitigations under that "
            "harness, (C3) an uncertainty monitor validated as a failure detector, and (C4) a quality-control "
            "dashboard and test strategy that treat the monitor as a safety component with explicit requirements.")
    if rr:
        rp.para("This report is deliberately honest about scope. The components were first built and verified on "
                "the unlabeled FeTS 2022 validation scans and on synthetic fixtures, before the labeled training data "
                "and the institution partitioning became available. The model results then come from a single "
                f"laptop run on a 4 GB GPU, below the 8 GB tier the protocol assumes: one method (the baseline), one "
                f"held-out site group, one seed and {rr['tcfg']['epochs']} epochs instead of 100, evaluated on seeded "
                "random samples of each split rather than every case. They are a pilot that exercises the full chain "
                "on real labels; the comparisons the protocol was designed for (four mitigations, five folds, three "
                "seeds) remain to be run, and every table says which numbers exist and which do not. Outlines shown "
                "on the unlabeled validation scans are still rule-based examples and are labeled as such.")
    else:
        rp.para("This report is deliberately honest about scope. The labeled FeTS 2022 training data and the "
                "institution partitioning were not available in the project environment, which held only the "
                f"{n_cases} unlabeled validation cases ({n_files} NIfTI files). The machine had a 4 GB GPU, below the "
                "8 GB needed for 3D nnU-Net training. Every component was therefore built and verified on the real "
                "unlabeled scans (geometry, conversion, interface) and on synthetic fixtures (training, harness, "
                "uncertainty, statistics). Every model result is marked \"not run\". Rule-based outlines shown on "
                "real scans are labeled as examples wherever they appear.")

    rp.para("Table I analyzes the base system, nnU-Net v2 (2.8.1) with the FeTS 2022 data, as it ships: what each "
            "part does, the limitation that matters for deployment at a new hospital, and the enhancement this "
            "project adds. The limitations were confirmed against the nnU-Net documentation and source before the "
            "design was fixed.")
    rp.table("Base system, limitations and enhancements", ["Part", "nnU-Net / FeTS as is", "Limitation",
                                                           "Enhancement (this work)"], [
        ["Training, inference", "self-configuring 3D U-Net; 5-fold CV; ensembling of folds",
         "folds are random, not by hospital", "reused as the segmentation core; custom trainers"],
        ["Cross-site evaluation", "FeTS lists the institution of each case",
         "no protocol that holds out whole hospitals", "site-held-out harness with five site groups (C1)"],
        ["Robustness to shift", "default augmentation, z-score per image",
         "no comparison of shift mitigations", "augmentation, style, standardization, TTA variants (C2)"],
        ["Uncertainty, review", "softmax/sigmoid outputs, mirroring averaged inside the predictor",
         "no voxel uncertainty, no case score, no review decision", "member x flip uncertainty, case score, "
         "trust gate with a fixed review limit (C3)"],
        ["Clinician interface", "NIfTI files viewed in separate tools",
         "no view of mask, uncertainty and flag together", "browser QC dashboard, review queue, explorer (C4)"],
        ["Verification", "framework unit tests", "no requirement-linked tests around the model",
         "R1–R8 traced to unit, integration, metamorphic, UI tests; CI; Docker (C4)"],
    ], [0.62, 0.95, 0.85, 0.98])

    # II. Related work and gaps
    rp.h1("Background, Related Work and Gaps")
    rp.para("BraTS provides multi-institution MRI with expert labels [4], [5], [11]. FeTS 2022 builds on BraTS 2021 [6] "
            "and records the institution of origin of each case [9]; the same initiative trained federated models "
            "across 71 institutions [10]. Other fields built multi-site benchmarks to test generalization directly, "
            "such as M&Ms for cardiac MRI [12] and PolypGen for colonoscopy [13]. Manthe et al. benchmarked federated "
            "learning on FeTS 2022 with a 3D U-Net and report a centralized mean Dice of 0.903; they evaluated only "
            "institutions that took part in training and list unseen institutions as future work [14].")
    rp.para("Domain-generalization methods include alignment, meta-learning, augmentation and ensembles [15]; "
            "MaxStyle targets appearance shift in medical segmentation [16]. Deep ensembles [17] and Monte Carlo "
            "dropout [18] estimate predictive uncertainty, calibration is measured with expected calibration error "
            "[19], and the reliability of such estimates in segmentation has been questioned [20]. Test-time "
            "adaptation by entropy minimization of normalization parameters (Tent) adapts a model to a test "
            "distribution without labels [21].")
    rp.para("Four gaps motivate the work: (G1) no unseen-site protocol for FeTS 2022, and site imbalance makes naive "
            "leave-one-site-out unreliable (two institutions supply about 71% of cases); (G2) no evidence that a "
            "model can signal its own failures at a new site; (G3) little documented engineering (requirements, "
            "verification, monitoring) around model-centric studies; (G4) no reviewer interface for masks, "
            "uncertainty and flags.")

    # III. System and architecture
    rp.h1("System and Architecture")
    rp.para("Fig. 1 summarizes the architecture. A raw folder is read only. Phase 0 discovers files and writes a "
            "manifest; conversion writes canonical RAS NIfTI copies, compressed viewer bundles and montages; an "
            "nnU-Net raw dataset is created with region labels. Site groups and folds are computed from the "
            "manifest. Training uses custom nnU-Net trainers. Inference produces prediction records (labels, "
            "region probabilities, voxel uncertainty, member disagreement and case scores). The harness scores "
            "records against references; the trust gate turns a case score into a flag; a FastAPI service serves "
            "bundles, records, summaries and a review log to the dashboard.")
    rp.figure_wide(R / "figures" / "architecture.png",
                   "Architecture. Grey boxes are reused from nnU-Net and FeTS; blue boxes are added by this project; "
                   "the trust gate (outlined) is the safety component. Solid arrows: runtime flow; dashed: "
                   "evaluation.", 6.6)
    rp.table("Components", ["Package", "Responsibility"], [
        ["btqc.data", "file discovery, NIfTI I/O, RAS reorientation, conversion, manifest, labels, site groups, fixtures"],
        ["btqc.train", "nnU-Net dataset and splits, custom trainers, augmentations, CLI runner with MLflow"],
        ["btqc.infer", "nnU-Net member wrapper, flip TTA, leakage-safe ensembles, test-time adaptation, records"],
        ["btqc.uncertainty", "entropy, mutual information, case scores, calibration, failure detection, trust gate"],
        ["btqc.eval", "metrics, site-held-out harness, statistics, shift, summary, figures, experiments E1–E6"],
        ["btqc.serve / web", "FastAPI backend; vanilla-JS dashboard with WebGL 2 renderer, no runtime network"],
    ], [1.0, 2.3])
    rp.para("Table " + ROMAN[rp.tab_n] + " records the main design decisions, the alternatives that were "
            "considered and why they were rejected.")
    rp.table("Design decisions and alternatives", ["Decision", "Alternative considered", "Reason for the choice"], [
        ["Hold out five site groups, not single sites", "leave-one-institution-out",
         "two institutions hold 71% of cases and most others have < 15; single-site folds are tiny and unstable"],
        ["Uncertainty from members x explicit flips", "nnU-Net's built-in mirroring",
         "the built-in averages logits internally and hides the members, so no disagreement can be measured"],
        ["Case score = entropy in a band around the tumor", "mean entropy over the whole tumor or brain",
         "failures are boundary errors; whole-volume means are diluted by confident background"],
        ["Gate is a pure function of score and limit", "learned or rule-rich gate (metadata, LLM)",
         "a reviewer must be able to predict and audit the flag (R4); tested by an import check"],
        ["Review limit fixed on in-site validation", "tune the limit on held-out results",
         "tuning on the test group would overstate failure detection"],
        ["Vanilla JS + WebGL 2, no build step", "React/three.js frontend",
         "no runtime network or dependency drift; the same modules run in a single offline HTML export"],
        ["Smaller 80x112x80 patch on the laptop", "2D or low-resolution 3D configuration",
         "keeps the 3D full-resolution model the protocol specifies, within about 3 GB of usable GPU memory"],
    ], [1.05, 0.9, 1.45])

    # IV. Requirements
    rp.h1("Requirements and Traceability")
    rp.para("The monitor is treated as a verifiable component. Table " + ROMAN[rp.tab_n] + " lists requirements "
            "R1–R8 with their "
            "verification and status. \"Verified\" means an automated test runs in continuous integration on "
            "synthetic fixtures; rows that need labeled data or a GPU say \"not run\".")
    rp.table("Requirements and verification", ["ID", "Requirement", "Verified by", "Status"], [
        ["R1", "Segment WT, TC, ET", "metric tests; region remap test; smoke training (G3)",
         "software verified; held-out Dice measured (pilot, one fold)" if rr else
         "software verified; held-out Dice not run"],
        ["R2", "Per-group accuracy", "split/leakage tests; harness e2e test", "verified on fixtures"],
        ["R3", "Voxel uncertainty, case score", "uncertainty tests; API schema test", "verified on fixtures"],
        ["R4", "Flag from score and limit only", "gate unit tests incl. import check; UI flag test", "verified"],
        ["R5", "Correct display orientation", "48-orientation test; planted voxel in Python and browser", "verified"],
        ["R6", "No identifiers stored or shared", "log test; header-field policy; review", "verified"],
        ["R7", "Reproducible runs", "deterministic folds; regression baseline; lockfile; MLflow; inference re-run",
         (f"verified for inference (score difference ≤ {rr['r7r8']['r7_max_score_abs_diff']:.1e}); training "
          "re-run not measured") if rr and rr.get("r7r8") else "verified (deterministic parts)"],
        ["R8", "60 s per case on one GPU", "performance test (CPU stages); timed inference on the GPU",
         (f"measured: {rr['r7r8']['r8_mean_total_8_flips_s']:.0f} s with 8 flips (not met), "
          f"{rr['r7r8']['r8_mean_total_1_flip_s']:.0f} s with 1 flip"
          + (" (met)" if rr['r7r8']['r8_mean_total_1_flip_s'] <= 60 else " (not met)"))
         if rr and rr.get("r7r8") else
         (f"not met on a 4 GB GPU: {rr['infer_s']:.0f} s per case with 8 flip members"
          if rr and rr.get("infer_s") else "GPU latency not run")],
    ], [0.3, 1.0, 1.4, 0.7])
    rp.para("Three requirements carry the safety argument. R4 makes the flag auditable: if the flag could depend "
            "on anything beyond the score and the limit, for example metadata, a language model or a web service, "
            "a reviewer could not predict or reproduce it. The gate is therefore a pure function in a module "
            "whose imports a test restricts to the standard library, and the browser applies the same rule so "
            "the slider and the server agree. R5 addresses the failure mode most likely to harm a patient in a "
            "viewer, a left-right swap: it is verified by planting a voxel at a known file index and reading it "
            "back in Python and in the browser's status bar. R6 is verified by inspection of the request paths "
            "and by a test on the log content, and by design: local files are parsed in the browser and never "
            "uploaded, and header free-text fields are never copied.")

    # V. Methodology
    rp.h1("Methodology")
    rp.h2("Data")
    dr = s0
    if rr:
        rp.para(f"Phase 0 inspected every file read-only. The data folder holds {n_files} NIfTI files in "
                f"{n_cases} cases: the 1,251 labeled FeTS 2022 training cases from 23 institutions [14] and the 219 "
                "unlabeled validation cases, each with T1, T1ce, T2 and FLAIR of 240×240×155 voxels at 1 mm. The "
                "institution of each training case comes from the official partitioning CSV, so the data situation "
                f"is {dr.get('situation', '?')}: labels and site information. Files sit in wrapper directories "
                "carrying the official name, some with a different inner file name, so the wrapper name is used as "
                "the identity. Headers differ (qform-only files, float32 storage, a few negative voxels), and raw "
                "intensity scales differ by two orders of magnitude between cases, a form of heterogeneity that "
                "per-case z-scoring removes. Two institutions supply about 71% of the labeled cases.")
    else:
        rp.para(f"Phase 0 inspected every file read-only. The validation download contains {n_files} NIfTI files in "
                f"{n_cases} cases, each with T1, T1ce, T2 and FLAIR of 240×240×155 voxels at 1 mm, all with the same "
                "LPS affine diag(−1, −1, 1). None has a segmentation and no institution table exists, so the data "
                f"situation is {dr.get('situation', '?')}: unlabeled scans only. Every file sits in a wrapper "
                "directory carrying the official name; 36 cases have a different inner file name, and the wrapper "
                "name is used as the identity. 232 files store only a qform; 159 are float32; two contain a few "
                "negative voxels; and raw intensity scales differ by two orders of magnitude between cases (median "
                "99th percentile of T1 593, maximum about 25,000), a form of heterogeneity that per-case z-scoring "
                "removes. The expected labeled data, per the literature, are 1,251 cases from 23 institutions [14].")
    if files is not None:
        rows = []
        for sq in ("t1", "t1ce", "t2", "flair"):
            g = files[files.sequence == sq]
            rows.append([sq.upper(), f"{g.p1_nz.median():.0f}", f"{g.p99_nz.median():.0f}",
                         f"{g.p99_nz.min():.0f}–{g.p99_nz.max():.0f}", f"{(g.dtype == 'float32').sum()}",
                         f"{(g.sform_code == 0).sum()}"])
        rp.table("Per-sequence header and intensity facts of all FeTS 2022 files (Phase 0)" if rr else
                 "Per-sequence header and intensity facts of the validation download (Phase 0)",
                 ["Seq.", "median p1", "median p99", "p99 range", "float32", "no sform"], rows,
                 [0.45, 0.55, 0.6, 0.8, 0.5, 0.5])
        rp.para("Percentiles are over nonzero (brain) voxels of each file. The spread of the 99th percentile "
                "across cases is the most direct evidence of acquisition heterogeneity that needs no labels; "
                "it motivates the per-case standardization mitigation and the intensity-histogram shift metric, "
                "which is computed after z-scoring so that it measures differences in histogram shape rather than "
                "scale.")
    rp.h2("Site-held-out protocol")
    rp.figure(R / "figures" / "protocol.png",
              "Site-held-out protocol. Each fold withholds one site group entirely; the model never sees it.", 3.2)
    rp.para("Five site groups are computed from the manifest by rules in a configuration file: institution 1, "
            "institution 18, mid-size institutions, small institutions (fewer than 15 cases) merged, and the "
            "LGG-only institutions 12–15, which take precedence. Fold g holds out all cases of group g; the rest is "
            "split, stratified by institution, into train (80%), validation (10%) and an in-site test (10%). "
            "Stratification is systematic: within each institution cases are shuffled with the fold seed, "
            "institutions are concatenated, and position i receives a fixed slot pattern, so even institutions "
            "with a few cases contribute proportionally. The generalization gap is in-site minus held-out mean, "
            "per group and region, with case-level bootstrap intervals.")
    rp.para("Leakage is checked rather than assumed. Fold validation rejects overlap and any held-out-group case "
            "in train, validation or in-site test. nnU-Net fold indices are laid out as group position × "
            "n_members + member, so seed replicates of the same fold form the ensemble for that fold; an ensemble "
            "containing an index of another fold raises an error, and the harness refuses any record whose fold "
            "differs from the fold being scored. This reconciles the proposal's five-model ensemble with the rule "
            "that models from different folds are never ensembled for held-out evaluation.")
    rp.h2("Mitigations")
    rp.bullets([
        "Stronger augmentation: a smooth multiplicative polynomial bias field, stronger Gaussian noise and a wider gamma range, inserted into nnU-Net's transform pipeline by a custom trainer.",
        "Style augmentation: MaxStyle [16] needs an adversarial style generator with an auxiliary decoder inside the training loop and could not be integrated within budget; the documented fallback is a random monotone Bézier intensity curve per channel.",
        "Per-case standardization: percentile clipping (0.5–99.5) with brain z-scoring, and a mode/IQR variant, both per case so no statistics cross folds.",
        "Test-time adaptation: nnU-Net uses instance normalization, so batch-norm statistic adaptation does not apply. We adapt only the instance-norm affine parameters by minimizing the entropy of the sigmoid outputs on patches of the test case [21], starting from the trained weights for every case.",
    ])
    rp.h2("Uncertainty and the trust gate")
    rp.para("Members are seed replicates times flip test-time augmentation. nnU-Net's own mirroring averages logits "
            "inside the predictor, which hides the members, so mirroring is disabled and inputs are flipped "
            "explicitly. Running sums of member probabilities and member entropies give, in constant memory, the "
            "binary entropy of the mean (per region, in bits) and the mutual information. The case score is the "
            f"mean voxel uncertainty in a band of {ucfg['case_score']['band_width_voxels']} voxels on both sides of "
            "the predicted whole-tumor boundary. A case fails if WT or ET Dice is below τ = "
            f"{ucfg['failure']['tau']}, a value fixed in configuration and committed before any held-out evaluation. "
            "The gate is flag = score > review limit, with a NaN score (for example an empty prediction) flagged; "
            "the review limit is the 80th percentile of the fold's in-site validation scores and is applied "
            "unchanged to the held-out group.")
    rp.code("""
def flag(score, review_limit) -> bool:
    limit = _as_float(review_limit)
    if math.isnan(limit):
        raise ValueError("review_limit must be a number")
    s = _as_float(score)
    if math.isnan(s):
        return True          # fail-safe: no score -> review
    return s > limit         # equal to the limit -> not flagged
""")
    rp.para("Formally, with M members m = 1..M and region r in {WT, TC, ET}, the member-mean probability at voxel "
            "v is p̄_r(v) = (1/M) Σ_m p_{m,r}(v). Voxel uncertainty is u(v) = (1/3) Σ_r H(p̄_r(v)) with the "
            "binary entropy H(p) = −p log₂ p − (1−p) log₂(1−p), so u ∈ [0, 1]. Member disagreement is the mutual "
            "information I_r(v) = H(p̄_r(v)) − (1/M) Σ_m H(p_{m,r}(v)) ≥ 0. With the predicted whole tumor W and "
            "the 6-connected structuring element B, the band is D = (W ⊕ kB) minus (W ⊖ kB) for k = 3, and the "
            "case score is s = mean over v in D of u(v), undefined (NaN) when W is empty. Calibration bins the "
            "positive-class probability into 15 equal bins b and computes ECE = Σ_b (n_b/N)·|mean(p)_b − "
            "mean(y)_b|. Failure AUROC is the Mann-Whitney statistic of s between failed and non-failed cases. The "
            "risk-coverage curve sorts cases by s and reports, for coverage c = k/n, the mean Dice of the k most "
            "certain cases; AURC is the mean of 1 − Dice over all k, and the oracle AURC sorts by true Dice.")
    rp.para("The review limit is the only free parameter of the gate. It is chosen per fold on in-site validation "
            "cases, by the rule written in configs/uncertainty.yaml, so that the held-out group never informs it. "
            "The default rule flags roughly the 20% most uncertain in-site validation cases; a Youden rule on "
            "validation failures is implemented as an alternative and must be selected before evaluation, never "
            "after looking at held-out results.")
    rp.h2("Metrics and statistics")
    rp.para("Dice, HD95 (95th percentile of pooled symmetric surface distances in mm) and average surface distance "
            "are computed per region. If both masks are empty Dice is 1 and HD95 0; if exactly one is empty Dice "
            "is 0 and HD95 is 373.13 mm, the diagonal of the BraTS grid. This constant is used in published "
            "BraTS-family evaluations [24] while BraTS 2023 glioma reports use 374 [23]; we did not find it in an "
            "official BraTS 2021 document and therefore treat it as a documented, configurable choice and report "
            "the fraction of penalized cases. ECE uses 15 equal-width bins on the positive-class probability within "
            "a band around the tumor and over the whole brain. Failure detection uses AUROC with 2,000-sample "
            "bootstrap intervals and risk-coverage curves; methods are compared with paired Wilcoxon tests and "
            "shift is related to the gap with Spearman correlation. Hypotheses were stated in advance: H1 held-out "
            "Dice is lower than in-site, most for ET and the LGG-only group; H2 at least one mitigation narrows the "
            "gap; H3 uncertainty detects failures (AUROC interval above 0.5) and deferral raises retained Dice.")
    rp.para("Mitigations are compared with the baseline on the same held-out cases, so the tests are paired. "
            "Four mitigations times three regions give twelve comparisons; their p-values are reported both "
            "unadjusted and with the Holm-Bonferroni step-down adjustment, implemented and unit-tested, and H2 is "
            "accepted only if a bootstrap interval of the paired Dice difference excludes zero after adjustment. "
            "Effect sizes are reported as median paired differences with intervals, because with small held-out "
            "groups a significant p-value can coexist with a negligible effect.")

    # VI. Implementation
    rp.h1("Implementation")
    rp.h2("Tools and repository")
    rp.para("The system is written in Python 3.12 (PyTorch 2, nnU-Net v2.8.1, NiBabel, SciPy, pandas, FastAPI, "
            "MLflow with a SQLite store) and vanilla JavaScript with WebGL 2, without a frontend build step. Code "
            "quality is enforced by ruff and mypy; tests use pytest and Playwright with headless Chromium. Docker "
            "images exist for the CPU application and the GPU training stack, and a GitHub Actions workflow runs "
            "lint, tests, browser tests and the image build on synthetic fixtures. "
            + (f"The repository is available at {REPO_URL}. " if REPO_URL else
               "The repository (code, tests, configurations, Docker files) accompanies this report. ")
            + "Every number in this report is read at build time from result files by scripts/build_report.py, so "
              "the report cannot drift from the runs it describes.")
    rp.h2("Geometry")
    rp.para("Orientation errors are the most dangerous silent bug in an imaging viewer. One rule is used in "
            "Python and in the browser: for each voxel axis, choose the world axis with the permutation that "
            "maximizes the sum of absolute affine entries, and that entry's sign; the volume is reordered so that "
            "indices increase toward patient right, anterior and superior. The original orientation is stored, so "
            "the status bar reports the file's own voxel index. The Python implementation equals nibabel's "
            "closest-canonical result for all 48 axis permutations and signs.")
    rp.h2("nnU-Net integration")
    rp.para("The nnU-Net v2 (2.8.1) documentation and source were read before writing the dataset. Labels are "
            "remapped as in nnU-Net's own BraTS 2021 conversion (edema→1, necrotic core→2, enhancing→3); "
            "dataset.json declares the regions whole tumor [1, 2, 3], tumor core [2, 3] and enhancing tumor [3] "
            "with regions_class_order [1, 2, 3], keeping key order as the region-training guide requires; channels "
            "are T1, T1ce, T2, FLAIR in that order. A test reconstructs WT, TC and ET from the remapped labels with "
            "the dataset.json definitions and compares them with the original regions. Image files in the raw "
            "dataset are hard links to the canonical copies. Custom trainers are found through nnU-Net's "
            "external-trainer environment variable, so the installed package is not modified.")
    rp.h2("Challenges")
    rp.bullets([
        "Windows and 7.4 GB RAM: nnU-Net's fingerprint step started eight workers of about 1 GB each and exhausted memory; it now runs with one worker. With zero augmentation workers nnU-Net's planner called torch.set_num_threads(0); the runner now uses zero only for training.",
        "MLflow 3 no longer accepts the plain file store; runs are tracked in a local SQLite database.",
        "Inference must see each member, but nnU-Net averages mirrored logits internally; mirroring is disabled and flips are applied explicitly with streaming accumulation.",
        "ES modules cannot be inlined into a single HTML file directly; a small deterministic bundler wraps each module and resolves imports through a module table, so the export runs offline.",
    ] + ([
        "GPU memory: the planned 4 GB nnU-Net configuration ran out of memory at the first iteration, because Windows leaves about 3 GB usable. A standalone forward/backward probe of the planned network found that a 80×112×80 patch fits (about 1.7 GB peak), and disabling cuDNN's algorithm search, which allocates large temporary workspaces, removed the remaining spikes.",
        "System memory: preprocessing and the first training run failed with \"the paging file is too small\" because the system drive was full; the paging file was moved to the data drive.",
        "Two dashboard bugs appeared only with real model output. The viewer sent its built-in limit of 0.25 on its first request and so overrode the configured review limit, and a hidden EXAMPLE banner shifted the viewer's grid rows and collapsed the slice views. Both were invisible to the browser tests, which used example cases; both are fixed and now have regression tests.",
        "Long jobs were lost twice when the editor session or the laptop restarted; GPU jobs now run as detached processes with per-step logs, and the any-time case order lets a stopped run keep a valid random sample.",
    ] if rr else []))
    rp.h2("Dashboard")
    rp.para("The dashboard reuses and refactors two working single-file prototypes: three linked orthogonal views "
            "in radiological convention with a shared crosshair, window and level, sequence switching, WebGL 2 "
            "ray casting with cut-away and glass-brain modes, overlays for tumor regions and the uncertainty heat "
            "map, and a report panel with the flag, the review-limit slider, a jump to the most uncertain spot and "
            "region volumes. New pages add the review queue (decisions in SQLite), the generalization explorer, a "
            "site risk report and a model card; the disclaimer appears on every page. Charts use at most three "
            "validated categorical colors, a legend plus direct labels, hover tooltips and a table view.")
    rp.table("REST API of the dashboard backend", ["Endpoint", "Purpose"], [
        ["GET /api/cases", "id, group, flag, score and region volumes; review_limit query re-evaluates the gate"],
        ["GET /api/cases/{id}/volume/{seq}", "gzip uint8 RAS bundle; metadata in the X-Btqc-Meta header"],
        ["GET /api/cases/{id}/prediction", "scores, flag with reason, volumes, hemisphere, hot spot, source"],
        ["GET .../prediction/labels | uncertainty", "label and uncertainty volumes (uint8, RAS)"],
        ["GET /api/eval/summary", "per-group metrics, risk-coverage, reliability, failure detection"],
        ["POST/GET /api/review", "reviewer decisions (accept, reject, note) in SQLite"],
        ["POST /api/predict, GET /api/jobs/{id}", "upload four sequences; enabled only with a GPU and a model"],
        ["GET /api/site-risk, /api/model-card", "site risk report and model card data"],
    ], [1.5, 1.8])
    rp.para("Inputs are validated at the boundary: case identifiers must match a strict pattern, review notes are "
            "length-limited, review limits outside [0, 1] are rejected, and uploads are size-limited, decompressed "
            "and parsed as NIfTI-1 before anything else happens; file names are discarded. Logging middleware "
            "records only the method, the route template and the status code, which a test checks by requesting "
            "a case and asserting that its identifier never appears in the log.")
    rp.para("The frontend has no build step and no third-party libraries. A NIfTI-1 reader handles plain and "
            "gzip files, eight data types, scaling, and sform or qform orientation. The 3D view is a single "
            "fragment shader that marches rays front to back through an R8 texture with a random start offset "
            "per pixel to avoid banding, shades from the intensity gradient with a head light, removes the "
            "octant on the camera side of the crosshair for the cut-away, and draws a gradient-only shell in "
            "glass mode with the tumor as a softened RGBA texture inside. The same modules run against the API "
            "or against data embedded in the single-file export, which a small bundler produces; the export "
            "test checks that it makes no network request.")
    if rr:
        rp.figure(R / "screenshots" / "viewer_flagged_model.png",
                  "Viewer on a held-out case with the trained model's prediction: three linked views with tumor "
                  "regions, the uncertainty heat map and the glass-brain 3D view. The gate marks it \"Needs review\" "
                  "(boundary-band score above the review limit).", 3.4)
    else:
        rp.figure(R / "screenshots" / "viewer_real_example.png",
                  "Viewer on real validation case FeTS2022_00153 with a rule-based EXAMPLE outline (not a model), "
                  "showing the example banner, the report panel and the glass-brain 3D view.", 3.3)
        rp.figure(R / "screenshots" / "review_real_example.png",
                  "Review queue on the 219 unlabeled validation cases, sorted by boundary uncertainty; rows are marked "
                  "\"example\" because these scores come from the rule-based outlines"
                  + (" (screenshot taken before the model was trained)." if rr else ", as no model output exists."), 3.3)
    if not rr:
        rp.figure(R / "screenshots" / "explorer_synthetic.png",
                  "Generalization explorer: \"not run\" on real data, with the labeled synthetic pipeline demo "
                  "switched on (SYNTHETIC, not a result).", 3.3)
    if not rr:
        rp.figure(R / "screenshots" / "viewer_synthetic.png",
                  "Viewer on a synthetic fixture case with stub prediction and uncertainty overlay (SYNTHETIC data).")

    # VII. Evaluation and testing
    rp.h1("Evaluation and Testing Results")
    rp.h2("What was run")
    rows = [["Phase 0 inspection", f"{n_files} files, {n_cases} cases, situation {s0.get('situation', '?')}",
             f"{s0.get('elapsed_s', '?')} s"],
            ["Conversion", f"{conv['counts'].get('converted', 0)} cases converted, "
                           f"{conv['counts'].get('error', 0)} errors" if conv else "not run",
             f"{conv['elapsed_s']:.0f} s" if conv else ""]]
    if smoke:
        g, mm = smoke["gate_G3"], smoke["metrics"]
        rows.append(["nnU-Net smoke (G3, synthetic)",
                     f"loss {mm['train_loss_first']:.3f}→{mm['train_loss_last']:.3f}; {g['n_scored']} cases scored; "
                     f"passed={g['passed']}", f"run {smoke['mlflow_run_id'][:8]}"])
    if e6:
        rows.append(["Unit/integration/metamorphic/regression", e6["pytest_summary"],
                     f"coverage {fmt(e6['coverage_percent'], 1)}%"])
    if ui:
        rows.append(["Browser tests (Chromium, SwiftShader)",
                     f"{ui['tests'] - ui['failures'] - ui['errors'] - ui['skipped']} of {ui['tests']} passed", ""])
    if rr:
        nv = rr["nnunet_val"]
        rows.append([f"Baseline training, fold {', '.join(rr['folds'])} held out",
                     f"{rr.get('n_epochs_run', '?')} epochs on GTX 1650 Ti (4 GB)"
                     + (f"; nnU-Net validation Dice {nv['mean']:.3f} on {nv['n']} cases" if nv else ""),
                     f"{rr['epoch_s'] / 60:.0f} min/epoch" if rr.get("epoch_s") else ""])
        ns = rr["n_split"]
        rows.append(["Site-held-out evaluation (E1, E2, E4, E5)",
                     f"{sum(ns.values())} cases: val {ns.get('val', 0)}, in-site {ns.get('insite_test', 0)}, "
                     f"held-out {ns.get('heldout', 0)} (seeded samples)",
                     f"{rr['infer_s']:.0f} s/case, 8 flips" if rr.get("infer_s") else ""])
        rows.append(["Mitigations (E3), other folds and seeds", "not run (compute budget)", "docs/deviations.md"])
    else:
        rows.append(["Site-held-out training and evaluation (E1–E5)", "not run (no labeled data, no GPU)", ""])
    rp.table("Runs executed for this report", ["Run", "Outcome", "Notes"], rows, [1.2, 1.5, 0.6])
    rp.h2("Geometry and conversion")
    rp.para("The planted-voxel test places a marker at file index (95, 150, 82) of a 240×240×155 LPS volume and "
            "finds it at RAS index (144, 89, 82) with the same world coordinate; the inverse mapping returns the "
            "original index. The same check runs in headless Chromium on a NIfTI file opened in the viewer, where "
            "the status bar must show the file index and full signal. Montages of real cases with different "
            "header properties (qform only, float32 storage, negative voxels) were inspected and matched the "
            "expected anatomy; one showed a sagittally acquired T1, an acquisition difference rather than a "
            "geometry error.")
    rp.figure(REPO_ROOT / "data" / "processed" / "montage" / "FeTS2022_00153.png",
              "QA montage of a real validation case (qform-only header) in RAS, radiological display. Scan only; "
              "no outline.", 3.2)
    rp.h2("Smoke training on synthetic fixtures (gate G3)")
    if smoke:
        mm = smoke["metrics"]
        rp.para("nnU-Net planned and preprocessed 12 synthetic cases, trained the btqc smoke trainer for three tiny "
                f"epochs on CPU (training loss {mm['train_loss_first']:.4f}, then "
                f"{smoke['losses']['train_loss'][1]:.4f}, then {mm['train_loss_last']:.4f}), and the inference "
                "wrapper produced prediction records for the fold's in-site and held-out cases, which the harness "
                f"scored. Mean inference time was {mm['mean_infer_s']:.2f} s per 48×48×40 case with two flip members "
                f"on CPU. The mean WT Dice of {mm['mean_dice_WT']:.3f} describes a toy model on synthetic "
                "ellipsoids and is not a segmentation result.")
    if rr:
        tc = rr["tcfg"]
        ns, nt = rr["n_split"], rr["n_total_split"]
        nv = rr["nnunet_val"]
        rp.h2("Site-held-out pilot on real data")
        rp.para(f"The baseline trainer ran for {rr.get('n_epochs_run', tc['epochs'])} epochs of 250 iterations on "
                f"fold {', '.join(rr['folds'])}, whose held-out group holds 216 cases from 7 mid-size institutions; "
                "training used the remaining 828 cases of the other groups, 104 more served as in-site validation "
                "and 103 as the in-site test. The 4 GB plan ran out of GPU memory, so the plan was re-derived with a "
                f"patch of 80×112×80 voxels ({tc['plans']}) and cuDNN's algorithm search was disabled"
                + (f"; an epoch took {rr['epoch_s'] / 60:.0f} minutes" if rr.get("epoch_s") else "")
                + ". nnU-Net's poly learning-rate schedule is scaled to the shortened run."
                + (f" nnU-Net's own validation of the final checkpoint on all {nv['n']} in-site validation cases "
                   f"gave Dice {nv['WT']:.3f} (WT), {nv['TC']:.3f} (TC) and {nv['ET']:.3f} (ET)." if nv else ""))
        rp.para("Test inference used the uncertainty pipeline of Section V (eight flip members, streaming entropy). "
                "Because one case took about "
                + (f"{rr['infer_s'] / 60:.1f} minutes" if rr.get("infer_s") else "two minutes")
                + " on the laptop GPU, each split was evaluated on a seeded random sample: "
                f"{ns.get('val', 0)} of {nt.get('val', 0)} validation, {ns.get('insite_test', 0)} of "
                f"{nt.get('insite_test', 0)} in-site test and {ns.get('heldout', 0)} of {nt.get('heldout', 0)} "
                "held-out cases. Splits are sorted by case identifier, which clusters institutions, so the sample is "
                "drawn at random rather than taken from the top; the held-out sample covers all 7 institutions.")
        rows = []
        for r in ("WT", "TC", "ET"):
            for metric, d in (("dice", 3), ("hd95", 1)):
                g = rr["gaps"].get((r, metric))
                if g:
                    rows.append([r, "Dice" if metric == "dice" else "HD95 (mm)",
                                 f"{g['insite_mean']:.{d}f} [{g['insite_lo']:.{d}f}, {g['insite_hi']:.{d}f}]",
                                 f"{g['heldout_mean']:.{d}f} [{g['heldout_lo']:.{d}f}, {g['heldout_hi']:.{d}f}]",
                                 f"{g['gap']:.{d}f} [{g['gap_lo']:.{d}f}, {g['gap_hi']:.{d}f}]"])
        rp.table("In-site test versus held-out institutions (baseline; mean with 95% bootstrap CI; gap = in-site "
                 "minus held-out)", ["Region", "Metric", "In-site", "Held-out", "Gap"], rows,
                 [0.4, 0.55, 0.85, 0.85, 0.85])
        gd = {r: rr["gaps"][(r, "dice")] for r in ("WT", "TC", "ET") if (r, "dice") in rr["gaps"]}
        pos = [r for r in gd if gd[r]["gap"] > 0]
        sig = [r for r in gd if gd[r]["gap_lo"] > 0]
        big = max(gd, key=lambda r: gd[r]["gap"]) if gd else "?"
        rp.para(("Held-out Dice is below in-site Dice for every region" if len(pos) == len(gd) else
                 f"Held-out Dice is below in-site Dice for {', '.join(pos) or 'no region'}")
                + f", and the drop is largest for {big}"
                + (", the direction H1 predicted. " if big == "ET" else ". ")
                + (f"The interval of the gap excludes zero for {', '.join(sig)}; for the other regions the gap is a "
                   "trend, not a demonstrated effect. " if sig else
                   "With the sample sizes of this pilot every interval of the gap contains zero, so the gap is a "
                   "trend, not a demonstrated effect. ")
                + "HD95 is more sensitive than Dice to a few cases with distant false-positive islands, which "
                  "inflates its means and intervals.")
        rp.figure(R / "figures" / "gap_baseline.png",
                  "Dice gap (in-site minus held-out) per region for the held-out group, with bootstrap intervals "
                  "(baseline, real data, pilot sample).", 3.0)
        inst = rr["inst"]
        rp.table("Held-out Dice per institution (baseline)", ["Institution", "n", "WT", "TC", "ET"],
                 [[f"{int(x.institution)}", int(x.n), f"{x.WT:.3f}", f"{x.TC:.3f}", f"{x.ET:.3f}"]
                  for x in inst.itertuples()], [0.8, 0.4, 0.6, 0.6, 0.6])
        ins_wt = gd["WT"]["insite_mean"] if "WT" in gd else float("nan")
        worse = inst[inst.WT < ins_wt - 0.05]
        rp.para(f"Performance at unseen institutions is uneven: {len(inst) - len(worse)} of {len(inst)} held-out "
                "institutions reach a WT Dice within 0.05 of the in-site mean or above it, while "
                + (", ".join(f"institution {int(x.institution)} ({x.WT:.2f}, n = {int(x.n)})"
                             for x in worse.itertuples()) or "none")
                + " fall clearly below. Institutions with one or two sampled cases give per-institution means that "
                  "are anecdotes, not estimates.")
        fb = rr["fail"].get("boundary_band")
        if fb:
            rp.h2("Failure detection and the trust gate")
            names = {"boundary_band": "boundary-band entropy (gate score)", "wt_mean": "whole-tumor mean entropy",
                     "band_disagreement": "boundary-band member disagreement"}
            rp.table(f"Failure detection on held-out cases (failure: WT or ET Dice < {ucfg['failure']['tau']})",
                     ["Score", "n", "failed", "AUROC [95% CI]"],
                     [[names.get(k, k), f["n"], f["n_failed"], f"{f['auroc']:.2f} [{f['lo']:.2f}, {f['hi']:.2f}]"]
                      for k, f in rr["fail"].items()], [1.6, 0.35, 0.45, 0.9])
            rp.para(f"The review limit chosen on in-site validation by the committed rule is {fb['review_limit']:.3f}. "
                    f"Applied unchanged to the held-out cases it flags {fb['flagged_frac']:.0%} of them; "
                    f"{fb['fail_rate_flagged']:.0%} of flagged cases failed versus {fb['fail_rate_unflagged']:.0%} of "
                    "unflagged cases. With "
                    f"{fb['n_failed']} failures among {fb['n']} held-out cases the AUROC interval is wide"
                    + (", but its lower bound lies above 0.5, which is the H3 criterion." if fb["lo"] > 0.5 else
                       ", and it includes 0.5, so the H3 criterion is not met."))
            rc = rr["rc"]
            if rc:
                rp.para(f"Deferring the 20% most uncertain held-out cases raises the mean Dice of the retained cases "
                        f"from {rc['dice_full']:.3f} to {rc['dice_at_80']:.3f} (gain {rc['gain_at_80']:+.3f}). The "
                        f"area under the risk-coverage curve is {rc['aurc']:.3f}, against {rc['oracle_aurc']:.3f} for "
                        "an oracle that defers the truly worst cases first.")
            rp.figure(R / "figures" / "risk_coverage_baseline.png",
                      "Risk-coverage curve on the held-out cases: mean Dice of the retained cases as the most "
                      "uncertain cases are deferred (baseline, real data).", 3.0)
        ece = rr["ece"]
        if ece:
            rp.h2("Calibration")
            rows = []
            for split in ("insite_test", "heldout"):
                for r in ("WT", "TC", "ET"):
                    b, v = ece.get((split, r, "band")), ece.get((split, r, "volume"))
                    if b is not None:
                        rows.append(["in-site" if split == "insite_test" else "held-out", r, f"{b:.3f}",
                                     f"{v:.3f}" if v is not None else ""])
            rp.table("Expected calibration error (15 bins) near the tumor boundary and over the brain",
                     ["Split", "Region", "ECE band", "ECE brain"], rows, [0.7, 0.5, 0.7, 0.7])
            rp.para("Calibration over the whole brain is dominated by easy background voxels and is therefore small; "
                    "the boundary band is the informative number. Comparing estimators (E4) needs the seed "
                    "ensemble and the TTA variants, which were not trained.")
            rp.figure(R / "figures" / "reliability_baseline.png",
                      "Reliability diagram near the tumor boundary (baseline, real data).", 2.6)
        rp.para("E2 relates intensity shift to the gap across folds. With one trained fold there is a single "
                "point, so the correlation and the site-risk regression are undefined and reported as such; the "
                "per-fold shift statistics are computed for all five groups.")
        emb = rr.get("emb")
        e2 = rr.get("e2")
        if emb or e2:
            rp.h2("Shift between site groups (E2)")
            w1 = {x["fold"]: x for x in (e2 or {}).get("shift", [])}
            fd = {x["group"]: x for x in (emb or {}).get("rows", [])}
            rows = []
            for g in ("inst_1", "inst_18", "lgg_only", "mid", "small"):
                if g in w1 or g in fd:
                    rows.append([g + (" (held out)" if g in rr["folds"] else ""),
                                 f"{w1[g]['w1_mean']:.3f}" if g in w1 else "",
                                 f"{fd[g]['frechet']:.2f}" if g in fd else "",
                                 fd[g]["n"] if g in fd else ""])
            rp.table("Shift of each site group from the rest: intensity (mean Wasserstein-1 of z-scored histograms) "
                     "and model features (Fréchet distance of encoder embeddings)",
                     ["Group", "Intensity W1", "Embedding FD", "n (emb.)"], rows, [1.0, 0.75, 0.8, 0.5])
            if emb:
                order_fd = sorted(fd.values(), key=lambda x: -x["frechet"])
                rank = 1 + [x["group"] for x in order_fd].index(rr["folds"][0])
                rp.para("The embedding distance uses the trained baseline's encoder: each case is passed through the "
                        "encoder once on a centred patch, the bottleneck is averaged to a vector, and a Gaussian fit "
                        "of each group is compared with the rest of the training pool (Fréchet distance). By this "
                        f"measure the most distinct group is {order_fd[0]['group']} and the held-out group "
                        f"{rr['folds'][0]} ranks {rank} of {len(order_fd)}. With one trained fold this describes "
                        "shift but cannot test whether shift predicts the gap; that needs the other folds.")
        e3 = rr.get("e3")
        if e3 and e3.get("status") == "ok":
            rp.h2("Mitigation: test-time adaptation (E3)")
            rp.para("Test-time adaptation is the one mitigation that needs no training: for every held-out case it "
                    "starts from the trained baseline, minimizes the entropy of the sigmoid outputs on patches of "
                    "that case by updating only the instance-norm affine parameters (10 steps), and then predicts "
                    "with the same eight flip members [21]. Table " + ROMAN[rp.tab_n] + " compares it with the "
                    "baseline on the same held-out cases (paired).")
            rp.table("Test-time adaptation minus baseline, held-out Dice (paired; 95% bootstrap CI; Wilcoxon with "
                     "Holm adjustment)", ["Region", "n", "Mean diff. [CI]", "p (Holm)"],
                     [[c["region"], c["n"], f"{c['diff_mean']:+.3f} [{c['diff_lo']:+.3f}, {c['diff_hi']:+.3f}]",
                       f"{c['wilcoxon'].get('p_holm', float('nan')):.3f}"] for c in e3["comparisons"]],
                     [0.5, 0.35, 1.3, 0.7])
            better = [c["region"] for c in e3["comparisons"] if c["diff_lo"] > 0]
            worse = [c["region"] for c in e3["comparisons"] if c["diff_hi"] < 0]
            rp.para(("Test-time adaptation improves held-out Dice significantly for " + ", ".join(better) + ". "
                     if better else "No region improves significantly. ")
                    + ("It is significantly worse for " + ", ".join(worse) + ". " if worse else "")
                    + "H2 is therefore " + ("supported for this mitigation" if e3.get("H2") else "not supported")
                    + " on this fold; the three training-time mitigations were not trained.")
            tg = [g for g in rr["all_gaps"] if g["method"] == "tta_entropy" and g["metric"] == "dice"]
            if tg:
                rp.para("Generalization gap with test-time adaptation (in-site minus held-out Dice): "
                        + ", ".join(f"{g['region']} {g['gap']:+.3f}" for g in tg) + ", against "
                        + ", ".join(f"{r} {rr['gaps'][(r, 'dice')]['gap']:+.3f}" for r in ("WT", "TC", "ET")
                                    if (r, "dice") in rr["gaps"]) + " for the baseline on its (larger) sample.")
        e4 = rr.get("e4tta")
        if e4:
            rp.h2("Uncertainty estimator: eight flips versus one prediction (E4)")
            a8, a1 = e4["flips_8"], e4["flips_1"]

            def _ece(x: dict[str, Any], split: str, region: str) -> str:
                v = [e["ece"] for e in x["ece"] if e["split"] == split and e["region"] == region]
                return f"{v[0]:.3f}" if v else ""

            rows = [["Mean Dice WT / TC / ET (all cases)",
                     " / ".join(f"{a8['mean_dice'][r]:.3f}" for r in ("WT", "TC", "ET")),
                     " / ".join(f"{a1['mean_dice'][r]:.3f}" for r in ("WT", "TC", "ET"))]]
            for split in ("insite_test", "heldout"):
                rows.append([f"ECE band, WT ({'in-site' if split == 'insite_test' else 'held-out'})",
                             _ece(a8, split, "WT"), _ece(a1, split, "WT")])
            f8 = (a8["failure"] or [{}])[0]
            f1 = (a1["failure"] or [{}])[0]
            if f8 and f1:
                rows.append(["Failure AUROC, held-out [CI]", f"{f8['auroc']:.2f} [{f8['lo']:.2f}, {f8['hi']:.2f}]",
                             f"{f1['auroc']:.2f} [{f1['lo']:.2f}, {f1['hi']:.2f}]"])
            rp.table(f"Eight flip members versus a single prediction on the same {e4['n_cases']} cases",
                     ["Quantity", "8 flips", "1 prediction"], rows, [1.5, 0.95, 0.95])
            rp.para("A single prediction still yields a voxel entropy (the sigmoid's own uncertainty), so the gate "
                    "can run without test-time augmentation; the comparison shows what the eight-fold cost buys in "
                    "calibration and failure detection. Deep ensembles and Monte Carlo dropout, the other estimators "
                    "in the plan, need extra trained models and were not compared.")
        r78 = rr.get("r7r8")
        if r78:
            rp.h2("Reproducibility and latency (R7, R8)")
            rp.table("Inference re-run and latency on the GTX 1650 Ti (4 GB)",
                     ["Case", "Label agreement", "Score diff.", "8 flips (s)", "1 flip (s)"],
                     [[x["case"].replace("FeTS2022_", ""), f"{y['label_agreement']:.4f}",
                       f"{y['score_abs_diff']:.1e}", x["total_8_flips_s"], x["total_1_flip_s"]]
                      for x, y in zip(r78["r8"], r78["r7"], strict=True)], [0.6, 0.8, 0.7, 0.6, 0.55])
            rp.para("Re-running inference on stored cases with the same model, members and flips reproduces the "
                    f"labels with at least {r78['r7_min_label_agreement']:.2%} voxel agreement and the case score "
                    f"within {r78['r7_max_score_abs_diff']:.1e}, so the flag of a case does not change on a re-run. "
                    f"End-to-end latency (loading included) is {r78['r8_mean_total_8_flips_s']:.0f} s with eight "
                    f"flips and {r78['r8_mean_total_1_flip_s']:.0f} s with one, against the 60 s target of R8. A "
                    "larger GPU would shorten the eight-flip time, but that was not measured.")
        fb = rr["fail"].get("boundary_band")
        rc = rr["rc"]
        if fb and rc:
            rp.h2("Before versus after: what the enhancements change")
            rows = [
                ["Hospital-level evaluation", "random 5-fold CV; no unseen-site number",
                 "held-out group of 7 institutions; gap per region with CIs"],
                ["Knowing when the model fails", "none: every mask looks equally trustworthy",
                 f"gate flags {fb['flagged_frac']:.0%} of held-out cases; {fb['fail_rate_flagged']:.0%} of them "
                 f"failed vs {fb['fail_rate_unflagged']:.0%} of unflagged (AUROC {fb['auroc']:.2f})"],
                ["Accuracy of what is accepted", f"mean Dice of all held-out cases {rc['dice_full']:.3f}",
                 f"{rc['dice_at_80']:.3f} for the 80% accepted ({rc['gain_at_80']:+.3f}); flagged cases go to a "
                 "reviewer"],
                ["Reviewing a case", "open NIfTI files in separate tools",
                 "one page: slices, 3D, overlays, uncertainty heat map, flag, volumes, review log"],
                ["Evidence of quality", "framework tests only",
                 "R1–R8 traced to automated tests; CI; reproducible inference (R7)"],
            ]
            rp.table("Base nnU-Net workflow versus the extended system (held-out cases of the pilot)",
                     ["Aspect", "Before (nnU-Net as is)", "After (this work)"], rows, [0.85, 1.1, 1.45])
            rp.para("The enhancement does not make the segmentation itself more accurate; it changes what a user "
                    "can know about it. The base workflow reports one cross-validated Dice and hands out every mask "
                    "with the same apparent confidence. The extended system measures accuracy at hospitals the model "
                    "has never seen and, at run time, separates likely failures from likely successes, so that "
                    "accepting only unflagged cases raises the mean Dice of what is accepted from "
                    f"{rc['dice_full']:.3f} to {rc['dice_at_80']:.3f} at 80% coverage.")
    if rr:
        rp.para("Before labels were available, the same harness, calibration and plotting code were exercised end to "
                "end on synthetic fixtures with a stub predictor (scripts/synthetic_demo.py); those figures are kept "
                "in the repository, labeled SYNTHETIC, and are superseded here by the real pilot.")
    if not rr:
        rp.h2("Harness, uncertainty and explorer on synthetic data")
        rp.para("To exercise the evaluation chain end to end, a synthetic demonstration uses fixtures and a stub "
                "predictor that perturbs the reference mask, with stronger perturbation for held-out groups by "
                "construction. Figs. " f"{rp.fig_n + 1}–{rp.fig_n + 3}" " come from this demonstration; they show that the harness, calibration and "
                "plotting code work and say nothing about real model behavior.")
        rp.figure(R / "figures_synthetic" / "gap_stub_baseline.png",
                  "Generalization gap per held-out group from the synthetic demonstration (SYNTHETIC, not a result).")
        rp.figure(R / "figures_synthetic" / "reliability_stub_baseline.png",
                  "Reliability diagram from the synthetic demonstration (SYNTHETIC, not a result).", 2.6)
        rp.figure(R / "figures_synthetic" / "risk_coverage_stub_baseline.png",
                  "Risk-coverage curves of three held-out groups from the synthetic demonstration (SYNTHETIC).", 2.8)
        if synth:
            f = [r for r in synth["failure"] if r["score"] == "boundary_band" and r["method"] == "stub_baseline"]
            rp.table("Failure detection in the synthetic demonstration (not a result)",
                     ["Fold", "n", "failed", "AUROC", "95% CI"],
                     [[r["fold"], r["n"], r["n_failed"], fmt(r["auroc"]), f"{fmt(r['lo'])}–{fmt(r['hi'])}"] for r in f],
                     [0.8, 0.4, 0.5, 0.6, 0.9])
            rp.para("The intervals are wide because the synthetic groups hold 6 to 12 cases, which previews a real "
                    "limitation: with five site groups, and some small ones, per-group AUROC will be uncertain.")
        rp.figure(R / "figures_synthetic" / "auroc.png",
                  "Failure-detection AUROC with bootstrap intervals per method and fold from the synthetic demonstration "
                  "(SYNTHETIC, not a result).", 3.0)
    rp.h2("Software quality")
    if e6:
        rp.para(f"The CI suite reports {tests_line} with {fmt(e6['coverage_percent'], 1)}% statement "
                "coverage. Lint (ruff) and static types (mypy on src) pass. Metamorphic tests check that translating "
                "the input by (3, −2, 1) voxels translates the predicted mask, that ±5% global intensity scaling "
                "leaves it unchanged and that flipping is consistent; regression tests compare fixed-seed metrics "
                "with a stored baseline.")
    if ui:
        rp.para(f"Browser tests ({ui['tests']} tests) cover the planted-voxel readout, rejection of a non-NIfTI "
                "file with a message, overlay drawing, the flag flipping exactly when the review limit crosses the "
                "score, persistence of review decisions, WebGL 2 volume rendering under software rendering, "
                "absence of console errors, and no horizontal overflow at a 390 px viewport on all five pages.")
    rp.table("Test inventory by category", ["Category", "Tests", "What is checked"], [
        ["Unit", inv.get("unit"), "parsing, orientation (48 cases), labels, metrics, entropy, scores, ECE, AUROC, gate, splits, shift, stats, TTA"],
        ["Integration", inv.get("integration"), "conversion, nnU-Net dataset, end-to-end harness, API, leakage guard, logging"],
        ["Metamorphic", inv.get("metamorphic"), "translation, intensity scaling, flip consistency (rule predictor; smoke model when present)"],
        ["Regression", inv.get("regression"), "fixed-seed metrics against a stored baseline"],
        ["Performance", inv.get("perf"), "CPU latency, memory and bundle size on a full-size case"],
        ["Browser", inv.get("ui"), "orientation readout, overlays, flag flip, review, WebGL, mobile layout, export"],
    ], [0.7, 0.4, 2.2])
    if perf:
        rp.table("CPU performance on a synthetic 240×240×155 case", ["Stage", "Measured"], [
            ["Conversion of one case (4 sequences + mask)", f"{perf['convert_case_s']} s"],
            ["Members + uncertainty + scores (stub, 3 members)", f"{perf['stub_members_uncertainty_scores_s']} s"],
            ["Trust-gate decisions", f"{perf['gate_decisions_per_s']:,} per s"],
            ["Viewer bundles (4 sequences + mask)", f"{perf['viewer_bundle_mb_all_sequences_plus_seg']} MB"],
            ["GPU model latency (R8)", "not run"],
        ], [2.2, 1.1])
        rp.para("These timings were taken while another conversion job ran on the same CPU and are upper bounds.")
    wl = workload_figure(R / "figures_example" / "review_workload.png")
    if wl and not rr:
        rp.h2("Gate behavior on the real validation scans (example scores)")
        rp.para(f"The rule-based example predictor produced a boundary-band score for each of the {wl['n']} "
                f"validation cases ({wl['n_nan']} with an empty outline, which the gate flags). The scores span "
                f"{wl['q10']:.3f} to {wl['q90']:.3f} between the 10th and 90th percentiles (median "
                f"{wl['median']:.3f}), and the default review limit of {wl['default']:.2f} flags "
                f"{wl['at_default']:.0%} of the cases. Fig. {rp.fig_n + 1} shows the review workload as a function "
                "of the limit. These are example uncertainties from brightness rules, so the curve demonstrates the "
                "gate and the workload view a reviewer would use to choose a limit; it says nothing about how "
                "often a model fails. With a trained model, the same curve, combined with the in-site failure "
                "rate, is what turns the risk-coverage analysis into a staffing decision.")
        rp.figure(R / "figures_example" / "review_workload.png",
                  "Fraction of validation cases flagged versus review limit, from rule-based EXAMPLE scores "
                  "(not a model).", 3.0)
    rp.h2("Site risk report")
    if site:
        rp.para(f"For an example batch of {site['batch']['n_cases']} validation cases, the mean Wasserstein-1 "
                "distance between z-scored brain-intensity histograms and the remaining validation cases was "
                f"{site['shift']['w1_mean']:.3f} z-units (T1ce {site['shift']['w1_t1ce']:.3f}, T1 "
                f"{site['shift']['w1_t1']:.3f}). The reference here is an example, not the training pool, and the "
                "expected-performance estimate is reported as not available because it requires a shift-versus-gap "
                "relationship learned on held-out folds.")
    rp.h2("Hypotheses")
    if rr:
        gd = {r: rr["gaps"][(r, "dice")] for r in ("WT", "TC", "ET") if (r, "dice") in rr["gaps"]}
        big = max(gd, key=lambda r: gd[r]["gap"]) if gd else "?"
        allpos = all(g["gap"] > 0 for g in gd.values())
        anysig = any(g["gap_lo"] > 0 for g in gd.values())
        h1 = ("direction supported (" + ("all regions lower" if allpos else "not all regions lower")
               + f", largest for {big}); " + ("interval excludes 0 for some region" if anysig else
                                             "all gap intervals include 0")
               + "; LGG-only fold not run")
        fb = rr["fail"].get("boundary_band")
        rc = rr["rc"]
        h3 = ("not run" if not fb else
              (f"supported on one fold: AUROC {fb['auroc']:.2f} [{fb['lo']:.2f}, {fb['hi']:.2f}]"
               if fb["lo"] > 0.5 else f"not supported: AUROC interval [{fb['lo']:.2f}, {fb['hi']:.2f}] includes 0.5")
              + (f"; deferring 20% raises Dice by {rc['gain_at_80']:+.3f}" if rc else ""))
        rp.table("Hypotheses H1–H3 (pilot: one fold, sampled test cases)", ["Hypothesis", "Status"], [
            ["H1: held-out Dice < in-site, largest for ET and LGG-only", h1],
            ["H2: a mitigation reduces the mean gap",
             ("test-time adaptation only: " + ("supported" if rr["e3"].get("H2") else "not supported")
              + "; training-time mitigations not run")
             if rr.get("e3") and rr["e3"].get("status") == "ok" else "not run (mitigations not trained)"],
            ["H3: AUROC CI above 0.5 and deferral raises retained Dice", h3],
        ], [1.6, 1.7])
    else:
        rp.table("Hypotheses H1–H3", ["Hypothesis", "Status"], [
            ["H1: held-out Dice < in-site, largest for ET and LGG-only", "not run (no labeled data)"],
            ["H2: a mitigation reduces the mean gap", "not run"],
            ["H3: AUROC CI above 0.5 and deferral raises retained Dice", "not run"],
        ], [2.3, 1.0])
    from btqc.train.runner import estimate_hours

    tcfg = load_config("train")
    n_methods = sum(1 for v in tcfg["methods"].values() if not v.get("inference"))
    h8 = estimate_hours(5, tcfg["n_members"], n_methods, tcfg["epochs"], tcfg["seconds_per_epoch"]["gpu_8gb"])
    h24 = estimate_hours(5, tcfg["n_members"], n_methods, tcfg["epochs"], tcfg["seconds_per_epoch"]["gpu_24gb"])
    rp.h2("Experiment plan and compute budget")
    def st(done: str, why: str) -> str:
        return done if rr else why

    rp.table("Experiments, scripts and status", ["ID", "Question", "Script", "Status"], [
        ["E1", "Gap at held-out groups", "scripts/e1_gap.py", st("run: baseline, one fold (pilot)", "not run")],
        ["E2", "Does shift predict the gap?", "scripts/e2_shift.py, embedding_shift.py",
         st("intensity + embedding shift computed; correlation needs more folds", "not run")],
        ["E3", "Which mitigation narrows the gap?", "scripts/e3_mitigations.py",
         st("test-time adaptation vs baseline (paired); training-time mitigations not run"
            if rr and rr.get("e3") and rr["e3"].get("status") == "ok" else "not run (only the baseline trained)",
            "not run")],
        ["E4", "Which estimator is best calibrated?", "scripts/e4_calibration.py, e4_tta_compare.py",
         st("baseline ECE; 8 flips vs 1 prediction" if rr and rr.get("e4tta") else
            "baseline ECE only; no estimator comparison", "not run")],
        ["E5", "Does uncertainty detect failures?", "scripts/e5_failure.py", st("run: baseline, one fold", "not run")],
        ["E6", "Does the software meet R1–R8?", "scripts/e6_software.py", "run (this section)"],
    ], [0.3, 1.3, 1.1, 0.6])
    full_epochs = 100
    h8_full = estimate_hours(5, 3, n_methods, full_epochs, tcfg["seconds_per_epoch"]["gpu_8gb"])
    h24_full = estimate_hours(5, 3, n_methods, full_epochs, tcfg["seconds_per_epoch"]["gpu_24gb"])
    if rr and rr.get("epoch_s"):
        laptop_h = estimate_hours(5, 3, n_methods, full_epochs, rr["epoch_s"])
        rp.para(f"The full protocol is {n_methods} trained methods × five folds × three seeds × {full_epochs} "
                f"epochs. With the epoch time measured on the laptop ({rr['epoch_s'] / 60:.0f} minutes) that is "
                f"about {laptop_h:,.0f} GPU hours, against roughly {h8_full:.0f} hours on an 8–12 GB GPU and "
                f"{h24_full:.0f} hours on a 24 GB GPU with the planning estimates in configs/train.yaml. The pilot "
                f"used one method, one fold, one seed and {tcfg['epochs']} epochs, about "
                f"{rr['epoch_s'] * rr.get('n_epochs_run', tcfg['epochs']) / 3600:.1f} hours of training. "
                "scripts/train_loso.py prints an estimate before any run and requires confirmation for jobs longer "
                "than 30 minutes; checkpoints are written every five epochs so a laptop shutdown loses little work.")
    else:
        rp.para(f"With {tcfg['epochs']} epochs, {tcfg['n_members']} seed replicates, {n_methods} trained methods "
                f"and five folds, the configured per-epoch estimates give about {h8:.0f} GPU hours on an 8–12 GB GPU "
                f"and about {h24:.0f} hours on a 24 GB GPU (scripts/train_loso.py prints this estimate before any "
                "run and requires confirmation for jobs longer than 30 minutes). These per-epoch figures are "
                "planning assumptions in configs/train.yaml, to be replaced by the measured time of the first epoch. "
                "The Tier 1 fallback is one member per fold and a reduced configuration. The smoke run measured "
                "about 37 s per tiny epoch on CPU; a full-resolution epoch on CPU would take hours, which is why no "
                "real training was attempted on this machine.")

    rp.h1("Software Process and Reproducibility")
    rp.para("All behavior is driven by six configuration files; Table " + ROMAN[rp.tab_n] + " lists the parameters that matter for "
            "validity. The failure threshold and the review-limit rule were committed in the first commit of the "
            "repository, before any held-out evaluation, and the commit hash is stored with every MLflow run "
            "together with the configuration, seed, fold and group counts.")
    rp.table("Configuration files and key parameters", ["File", "Key parameters"], [
        ["data.yaml", "raw root (read-only), institution table, channel order T1/T1ce/T2/FLAIR, window percentiles"],
        ["sitegroups.yaml", "group rules (LGG-only first, small < 15 cases), split seed, 80/10/10 fractions"],
        ["train.yaml", "nnU-Net configuration, epochs, seed, seed replicates per fold, methods and trainers"],
        ["uncertainty.yaml", "tau, band width, review-limit rule, calibration bins, bootstrap resamples"],
        ["eval.yaml", "empty-mask convention and HD95 penalty, statistics, small-group threshold"],
        ["serve.yaml", "paths, prediction sets shown, upload limits, live inference switch"],
    ], [0.9, 2.4])
    rp.para("Continuous integration runs four jobs on synthetic fixtures only: lint and static types, the test "
            "suite with coverage, the browser tests in headless Chromium with SwiftShader, and a Docker build of "
            "the CPU application image followed by its unit tests. Dependencies are pinned in a lockfile; a second "
            "image contains the GPU training stack, and a compose file runs the application with the MLflow user "
            "interface. Data, checkpoints, prediction records and MLflow runs are never committed; the manifest "
            "stores SHA-256 checksums of every input file so that a re-run can prove it used the same data. "
            "Every Makefile target delegates to a Python task runner, because make is not available on the "
            "Windows machine used here, so the same commands run on Windows, Linux and in CI.")
    rp.para("Reproducibility is verified at two levels. Deterministic parts (folds, metrics, scores, the stub "
            "predictor) are checked for bit-identical re-runs and against a stored baseline with a tolerance of "
            "10⁻⁶. nnU-Net training is seeded per fold but not bit-exact because of multi-process augmentation "
            "and non-deterministic GPU kernels, so requirement R7 for trained models is a re-run within a stated "
            + ("tolerance; the pilot was trained once, so that tolerance is not yet measured." if rr else
               "tolerance, which cannot be measured until training is possible."))

    rp.h1("Lessons Learned")
    rp.para("The project also scoped three optional modules. The tumor profile (volume per region in "
            "millilitres, hemisphere relative to the brain midline, centroid) is implemented and shown in the "
            "report panel; tumor grade and stage are deliberately not predicted. Scan comparison between two "
            "time points needs registration and a follow-up dataset, which FeTS does not provide, so it is not "
            "supported. The literature-retrieval panel was not built, because the core evaluation took priority; "
            "if added, it would stay isolated from the gate and send no case data in queries.")
    rp.bullets([
        "Inspect before building. Phase 0 found that every file sits inside a directory carrying the official name while 36 cases use different inner names; a parser written from the brief's examples alone would have produced the wrong case identifiers.",
        "Geometry needs two independent checks. Comparing our reorientation with nibabel caught nothing, but the planted-voxel test in the browser is what proves that the status bar, the crosshair and the stored data agree.",
        "Resource limits shape the pipeline. Defaults that are harmless on a workstation (eight fingerprint workers) exhausted a 7.4 GB laptop; every heavy step now has an explicit worker count and the runner prints an estimate before long jobs.",
        "Honesty has to be designed in. A record-level source field that travels from the predictor to the API and the interface made it impossible to show a rule-based outline without its example banner, and the experiment scripts write \"not run\" instead of silently producing empty tables.",
        "Charts are code. The first version of the explorer anchored diverging bars at the axis edge and hid undefined AUROC values; looking at rendered screenshots, not only passing tests, found both.",
    ] + ([
        "Measure memory, not plans. The 4 GB nnU-Net plan ran out of GPU memory at the first iteration under Windows, where only about 3 GB is usable; a standalone forward/backward probe of the planned network at several patch sizes found a configuration that fits, and disabling cuDNN's algorithm search removed the remaining memory spikes.",
        "The operating system is part of the pipeline. Preprocessing and the first training attempt died because a nearly full system drive could not grow the paging file; moving the paging file to the data drive fixed both.",
        "Sample for the deadline, but sample honestly. Inference with eight flip members took about two minutes per case, so the test sets were sampled at random with a fixed seed, in an order that keeps every split a random sample wherever the run stops.",
    ] if rr else []))

    # VIII. Discussion
    rp.h1("Discussion")
    if rr:
        fb = rr["fail"].get("boundary_band")
        rp.para("The pilot answers the project's questions only partly. It shows the whole chain working on real "
                "labels: a model trained with one site group held out, scored by a leakage-checked harness, with a "
                "trust gate whose limit was fixed on in-site data before the held-out cases were scored. A baseline "
                f"trained for only {rr['tcfg']['epochs']} epochs already reaches in-site Dice close to published "
                "nnU-Net results on BraTS-style data, and its accuracy at seven unseen institutions is lower, most "
                "for enhancing tumor, though not by a margin this sample can confirm. "
                + (f"The most useful finding for a deployed system is that the uncertainty score separated failed "
                   f"from successful held-out segmentations (AUROC {fb['auroc']:.2f}), so a reviewer who checks the "
                   "flagged cases would see most of the failures. " if fb else "")
                + "Whether mitigations narrow the gap (H2), whether the result holds for the other four groups, "
                  "and in particular for the LGG-only group, remain open. Freezing τ and the review-limit rule in a "
                  "committed configuration before any held-out run is a small but real guard against tuning on the "
                  "test set, and it held here: neither was changed after the held-out cases were scored.")
    else:
        rp.para("The project did not answer its scientific questions, and we report that as the main negative "
                "outcome: without labeled multi-institution data there is no generalization gap to measure, no "
                "mitigation to compare and no failure to detect. What the work does show is that the engineering "
                "around such a study can be specified, built and verified before the data arrive, so that the "
                "expensive part, training about 5 folds × 3 seeds × 4 methods on a GPU, starts from a pipeline whose "
                "geometry, leakage rules, thresholds and statistics are already tested and frozen. Freezing τ and "
                "the review-limit rule in a committed configuration before any held-out run is a small but real "
                "guard against tuning on the test set.")
    rp.para("Two design choices deserve scrutiny once results exist. First, the case score averages entropy near "
            "the predicted boundary. This rewards a model that is uncertain where edema meets brain, which is "
            "where annotators disagree most, so a high score may signal label ambiguity rather than failure; the "
            "alternative scores (whole-tumor mean entropy, member disagreement) are computed for that comparison. "
            "Second, entropy can be confidently wrong under strong shift [20]; a fold whose AUROC interval includes "
            "0.5 would mean the gate gives false reassurance at that site, which is exactly why the gate is "
            "advisory and evaluated per group.")
    rp.h2("Threats to validity")
    rp.bullets([
        "Internal: the review limit and tau must be fixed before held-out evaluation; both are committed in configuration, and any change must be recorded as a deviation. nnU-Net planning sees all labeled cases, but for MRI it shares only spacing and shape statistics because normalization is per image.",
        "Construct: Dice below tau is a proxy for clinical failure; edema boundaries are ambiguous, so WT failures may reflect label noise. Cases without enhancing tumor make ET Dice binary under the empty-mask convention and are reported separately.",
        "External: institution is a proxy for scanner and protocol; five groups cannot represent all hospitals, and the LGG-only group confounds site with grade.",
        "Conclusion: small groups give wide bootstrap intervals; with five folds a Spearman correlation has very low power, and the site risk estimate should be read as a hypothesis.",
    ])

    # IX. Limitations
    rp.h1("Limitations")
    rp.bullets([
        (f"Pilot scale: one method, one held-out group, one seed, {load_config('train')['epochs']} epochs, and "
         "sampled test sets; confidence intervals are wide and the mitigation comparison was not run."
         if rr else "No model was trained or evaluated on real data; all model-dependent numbers are not run."),
        "Site is a proxy: scanner and protocol metadata are absent, and grade is confounded with site for the LGG-only group.",
        "Five site groups give very low power for shift-versus-gap correlation; the site risk estimate is an extrapolation from a handful of points.",
        ("MaxStyle was replaced by a simpler style augmentation, which, like the other training-time mitigations, "
         "was not trained; test-time adaptation and embedding shift were run on the one trained fold only."
         if rr else
         "MaxStyle was replaced by a simpler style augmentation; test-time adaptation and embedding shift are "
         "implemented and unit-tested but not run."),
        "nnU-Net training is seeded but not bit-exact; reproducibility holds for the deterministic parts and within tolerance otherwise.",
        "The rule-based example outlines on real scans are brightness rules and must not be read as segmentations.",
    ])

    # X. Ethics
    rp.h1("Ethics, Privacy and Safety")
    rp.para("The system is a research prototype, not a medical device, and the disclaimer is shown in the "
            "dashboard, the README and this report. Only public, de-identified challenge data were used; the raw "
            "folder is never modified; free-text NIfTI header fields are not copied; the API logs route templates "
            "only and makes no outbound calls; files opened in the viewer stay in the browser. Tumor grade and "
            "stage are deliberately not estimated, because grade is established from tissue and molecular "
            "findings and a wrong grade on a dashboard would look like a diagnosis. The flag cannot be influenced "
            "by any external service. Redistribution of scans, including the single-file demo, is governed by the "
            "FeTS data use agreement.")

    # XI. Conclusion
    rp.h1("Conclusion")
    if rr:
        fb = rr["fail"].get("boundary_band")
        rp.para("We engineered a site-held-out evaluation harness, mitigation trainers, an uncertainty monitor with "
                "a fail-safe trust gate, and a quality-control dashboard around nnU-Net and FeTS 2022, specified by "
                "eight requirements and verified by automated tests. A laptop-scale pilot on real labels showed a "
                "small, not yet significant accuracy drop at seven unseen institutions, largest for enhancing tumor"
                + (f", and an uncertainty score that detects failed segmentations with AUROC {fb['auroc']:.2f}" if fb
                   else "")
                + ". The same scripts, run on a larger GPU with the full protocol of four methods, five folds and "
                  "three seeds, produce the mitigation comparison and the per-site evidence this design was built "
                  "to measure.")
    else:
        rp.para("We engineered a site-held-out evaluation harness, mitigation trainers, an uncertainty monitor with "
                "a fail-safe trust gate, and a quality-control dashboard around nnU-Net and FeTS 2022, specified by "
                "eight requirements and verified by automated tests. The available data and hardware did not allow "
                "any model result, and none is claimed. With the FeTS 2022 training data, the partitioning CSV and "
                "one GPU, the scripted experiments E1–E6 produce the generalization gap, mitigation comparison, "
                "calibration and failure-detection results that this design was built to measure.")

    rp.h1("References")
    for i, ref in enumerate(REFS, 1):
        p = rp.doc.add_paragraph()
        r = p.add_run(f"[{i}] {ref}")
        r.font.size = Pt(8)
        p.paragraph_format.space_after = Pt(1)

    rp.h1("Appendix: Deviations and Reproduction")
    rp.table("Definition of done: status", ["Item", "Status"], [
        ["Data report and manifest describe the real files", "done (Phase 0, gate G0)"],
        ["Canonical NIfTI, bundles, montages, nnU-Net dataset; orientation round trip", "done (gate G1)"],
        ["CI passes on synthetic fixtures without a GPU", f"local run: {tests_line}; workflow file validated"],
        ["Site-held-out protocol, baseline, three or more mitigations, uncertainty, failure detection, "
         "risk-coverage, calibration",
         "implemented and tested; baseline run on one fold (pilot); mitigations not run" if rr else
         "implemented and tested on fixtures; real-data results not run"],
        ["Dashboard with API, all Phase 7 pages, single-file export", "done; browser tests pass"],
        ["R1–R8 traced to tests", "done (docs/requirements.md)"],
        ["Report and demo script from real results, references verified", "done; references checked"],
        ["No claim exceeds what was run",
         "pilot numbers with intervals; unrun parts marked not run; examples labeled" if rr else
         "every model result marked not run; examples labeled"],
    ], [2.1, 1.2])
    rp.table("Deviations from the proposal and the brief", ["Item", "Done instead", "Reason"], ([
        ["4 methods × 5 folds × 3 seeds × 100 epochs", f"baseline, fold mid, 1 seed, {load_config('train')['epochs']} epochs",
         "deadline; ~19 min/epoch on a 4 GB GPU"],
        ["nnUNetPlans_4GB (patch 96×128×96)", "patch 80×112×80, cuDNN search off", "GPU out of memory"],
        ["Every test case of the fold", "seeded random sample per split", "~2.5 min/case inference"],
        ["GPU training (Tier 1/2)", "Tier 0 laptop: GTX 1650 Ti 4 GB", "hardware available"],
    ] if rr else [
        ["Labeled data, 1,251 cases", "219 unlabeled validation cases", "training data and partition CSV unavailable"],
        ["GPU training (Tier 1/2)", "Tier 0: CPU and synthetic smoke training", "4 GB GPU, 7.4 GB RAM"],
    ]) + [
        ["Five-model ensemble", "seed replicates within each fold", "no cross-fold ensembles (leakage rule)"],
        ["Norm-statistics TTA", "entropy minimization of instance-norm affine", "nnU-Net uses instance norm"],
        ["MaxStyle", "random monotone intensity-curve augmentation", "integration not feasible within budget"],
        ["Embedding shift", "run with the one trained encoder" if rr and rr.get("emb") else "implemented, not run",
         "one fold only" if rr and rr.get("emb") else "needs trained encoders"],
        ["HD95 penalty from BraTS 2021", "373.13 mm, documented choice", "not found in an official 2021 document"],
        ["Model outlines in the dashboard",
         "model outlines on the tested labeled cases; EXAMPLE outlines on unlabeled cases" if rr else
         "rule-based EXAMPLE outlines", "unlabeled cases not predicted (time)" if rr else "no trained model"],
    ], [1.1, 1.3, 1.0])
    rp.para("Reproduction on a machine with the labeled data and a GPU (configs/data.yaml pointing at the data and "
            "the partitioning CSV):")
    rp.code("""
python scripts/tasks.py data-report && python scripts/tasks.py convert
python scripts/make_splits.py            # commit data/splits/ before training
python scripts/nnunet_prep.py --plan
python scripts/train_loso.py --dry-run   # prints the estimate
python scripts/train_loso.py --device cuda --yes
python scripts/infer.py --methods baseline strong_aug style_aug standardize_pct tta_entropy
python scripts/run_experiments.py && python scripts/tasks.py docs
""")
    if rr:
        rp.para("The pilot in this report was produced on the laptop with:")
        rp.code("""
python scripts/train_loso.py --methods baseline --groups mid --device cuda --yes   # 10 epochs, nnUNetPlans_3GB
python scripts/infer.py --methods baseline --groups mid --per-split 15 --rolling --stop-at 18:30
python scripts/run_experiments.py && python scripts/build_docs.py && python scripts/build_report.py
""")

    out = REPO_ROOT / "docs" / "report" / "btqc_report.docx"
    out.parent.mkdir(parents=True, exist_ok=True)
    rp.doc.save(str(out))
    print(f"wrote {out} ({rp.fig_n} figures, {rp.tab_n} tables, {len(REFS)} references)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
