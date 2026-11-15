"""Screenshots of the dashboard on real model output for the report and slides (results/screenshots/*_model.png).
Needs the dashboard running (python scripts/tasks.py app) and Playwright with Chromium.

    python scripts/screenshots_real.py [--server http://127.0.0.1:8000]
"""

from __future__ import annotations

import argparse
import json
import urllib.request

from btqc.config import REPO_ROOT

ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--server", default="http://127.0.0.1:8000")
    a = ap.parse_args(argv)
    from playwright.sync_api import sync_playwright

    cases = json.load(urllib.request.urlopen(a.server + "/api/cases"))["cases"]
    model = [c for c in cases if c.get("prediction_source") == "model"]
    folds = json.loads((REPO_ROOT / "data" / "splits" / "folds.json").read_text())["folds"]
    held = {c for f in folds.values() for c in f["heldout"]} & set(folds["mid"]["heldout"])
    flagged = [c for c in model if c["id"] in held and c.get("flag")]
    reliable = [c for c in model if c["id"] in held and c.get("flag") is False]
    pick_flag = max(flagged, key=lambda c: c["score"] or 0) if flagged else model[0]
    pick_ok = min(reliable, key=lambda c: c["score"] or 1) if reliable else model[-1]
    out = REPO_ROOT / "results" / "screenshots"
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=ARGS)
        page = b.new_context(viewport={"width": 1280, "height": 860}, device_scale_factor=1.5).new_page()

        def ready() -> None:
            page.wait_for_function("window.__ready === true", timeout=60000)

        for name, c in (("viewer_flagged_model", pick_flag), ("viewer_reliable_model", pick_ok)):
            page.goto(a.server + f"/viewer.html?show=1&case={c['id']}")
            ready()
            page.wait_for_function("window.__btqc.viewer.state.overlayOn === true", timeout=60000)
            if page.is_visible("#layUnc"):
                page.check("#layUnc")
            page.wait_for_timeout(6000)
            page.screenshot(path=str(out / f"{name}.png"))
            print(name, c["id"], c["score"], c["flag_label"])
        page.goto(a.server + "/review.html")
        ready()
        page.wait_for_timeout(1500)
        page.screenshot(path=str(out / "review_model.png"))
        page.goto(a.server + "/explorer.html")
        ready()
        page.wait_for_timeout(2500)
        page.screenshot(path=str(out / "explorer_model.png"), full_page=True)
        page.goto(a.server + "/index.html")
        ready()
        page.wait_for_timeout(3000)
        page.screenshot(path=str(out / "home_model.png"))
        b.close()
    print("wrote screenshots to", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
