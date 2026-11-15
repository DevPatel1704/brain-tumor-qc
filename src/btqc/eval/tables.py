"""Auto-generated Markdown and LaTeX tables for the report (from the eval summary)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def _fmt(v: Any, d: int = 3) -> str:
    if v is None or (isinstance(v, float) and v != v):
        return "–"
    if isinstance(v, bool):
        return "yes" if v else ""
    if isinstance(v, float):
        return f"{v:.{d}f}"
    return str(v)


def to_markdown(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(_fmt(r[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def to_latex(df: pd.DataFrame, caption: str, label: str) -> str:
    cols = list(df.columns)
    esc = lambda s: str(s).replace("_", r"\_").replace("%", r"\%")  # noqa: E731
    lines = [r"\begin{table}[t]", r"\centering", r"\caption{" + esc(caption) + "}", r"\label{" + label + "}",
             r"\begin{tabular}{" + "l" * 2 + "r" * (len(cols) - 2) + "}", r"\hline",
             " & ".join(esc(c) for c in cols) + r" \\", r"\hline"]
    for _, r in df.iterrows():
        lines.append(" & ".join(esc(_fmt(r[c])) for c in cols) + r" \\")
    lines += [r"\hline", r"\end{tabular}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def write_tables(summary: dict[str, Any], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    src = summary.get("source", "")
    note = "" if src == "model" else f" ({src.upper()} - NOT A RESULT)"
    gaps = pd.DataFrame(summary["gaps"])
    if not gaps.empty:
        d = gaps[gaps.metric == "dice"][["method", "fold", "region", "insite_mean", "heldout_mean", "gap", "gap_lo",
                                          "gap_hi", "n_heldout", "small_n"]]
        for ext, text in (("md", to_markdown(d)), ("tex", to_latex(d, "Dice gap per held-out group" + note,
                                                                     "tab:gap"))):
            p = out_dir / f"gap_dice.{ext}"
            p.write_text(text, encoding="utf-8")
            written.append(p)
    fail = pd.DataFrame(summary["failure"])
    if not fail.empty:
        cols = [c for c in ["method", "fold", "score", "n", "n_failed", "auroc", "lo", "hi", "review_limit",
                            "flagged_frac", "dice_mean_all", "dice_mean_unflagged"] if c in fail]
        d = fail[cols]
        for ext, text in (("md", to_markdown(d)), ("tex", to_latex(d, "Failure detection" + note, "tab:fail"))):
            p = out_dir / f"failure.{ext}"
            p.write_text(text, encoding="utf-8")
            written.append(p)
    rc = pd.DataFrame(summary["risk_coverage"])
    if not rc.empty:
        d = rc[["method", "fold", "aurc", "oracle_aurc", "auc_dice", "dice_full", "dice_at_80", "gain_at_80"]]
        for ext, text in (("md", to_markdown(d)), ("tex", to_latex(d, "Risk-coverage" + note, "tab:rc"))):
            p = out_dir / f"risk_coverage.{ext}"
            p.write_text(text, encoding="utf-8")
            written.append(p)
    return written
