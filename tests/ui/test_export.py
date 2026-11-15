"""The single-file export (dist/btqc_demo.html) opens offline from file:// and works."""

import pytest

from btqc.config import REPO_ROOT

pytestmark = pytest.mark.ui
DEMO = REPO_ROOT / "dist" / "btqc_demo.html"


@pytest.mark.skipif(not DEMO.exists(), reason="run scripts/export_demo.py first")
def test_export_opens_offline(page):
    requests = []
    page.on("request", lambda r: requests.append(r.url))
    page.goto(DEMO.as_uri())
    page.wait_for_function("window.__ready === true", timeout=60000)
    page.click("#modeSeg")
    page.wait_for_function("window.__btqc.viewer.state.overlayOn === true")
    info = page.evaluate("window.__btqc.app.pred && window.__btqc.app.pred.info")
    if info and info["is_example"]:
        assert page.is_visible("#exampleNote")
    # file indices still exact after cropping: canonical -> original -> canonical round trip
    ok = page.evaluate("""() => { const v = window.__btqc.viewer.state.vol, c = [10, 20, 30];
        const o = v.toOrig(...c), back = v.fromOrig(...o); return back.join() === c.join(); }""")
    assert ok
    assert not [u for u in requests if u.startswith("http")], "export made network requests"
    assert not page.errors
