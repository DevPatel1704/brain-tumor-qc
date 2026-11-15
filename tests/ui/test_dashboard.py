"""Browser tests (R5 orientation, overlays, R4 flag behaviour, display modes, compare, layout, errors)."""

import json
import time

import pytest

from tests.ui.conftest import PLANTED

pytestmark = pytest.mark.ui
PAGES = ["index.html", "viewer.html", "compare.html", "review.html", "explorer.html", "site-risk.html",
         "model-card.html"]

# Counts pixels of the axial view whose channels differ (colored), and reads the corner pixel.
PIXELS_JS = """() => {
    const v = window.__btqc.viewer; v.frame();
    const cv = v.views[0].off, d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data;
    let n = 0;
    for (let i = 0; i < d.length; i += 4)
        if (Math.abs(d[i] - d[i + 1]) > 30 || Math.abs(d[i + 1] - d[i + 2]) > 30) n++;
    return {colored: n, corner: [d[0], d[1], d[2]]};
}"""


def _ready(page, timeout=30000):
    page.wait_for_function("window.__ready === true", timeout=timeout)


def _predicted(page, server):
    return [c for c in page.request.get(server + "/api/cases").json()["cases"] if c["has_prediction"]]


def _first_predicted(page, server):
    return _predicted(page, server)[0]


def test_planted_voxel_round_trip_in_readout(page, server, ui_data):
    page.goto(server + "/viewer.html")
    _ready(page)
    page.set_input_files("#fileIn", str(ui_data["files"] / "planted_t1.nii.gz"))
    page.wait_for_function("document.querySelector('#msg').textContent.startsWith('Opened')")
    res = page.evaluate("""([i, j, k]) => {
        const v = window.__btqc.viewer, vol = v.state.vol, c = vol.fromOrig(i, j, k);
        v.setCursor(c); v.frame();
        const idx = c[0] + vol.nx * (c[1] + vol.ny * c[2]);
        return {c, value: vol.seqs.t1[idx], vox: document.querySelector('#sVox').textContent,
                sig: document.querySelector('#sSig').textContent, dims: [vol.nx, vol.ny, vol.nz],
                src: vol.seqSource, world: vol.hasWorld};
    }""", list(PLANTED))
    # LPS file -> RAS canonical: x and y mirrored, z unchanged
    assert res["c"] == [res["dims"][0] - 1 - PLANTED[0], res["dims"][1] - 1 - PLANTED[1], PLANTED[2]]
    assert res["vox"] == ", ".join(map(str, PLANTED))
    assert res["value"] == 255 and res["sig"] == "100%"
    assert res["src"] == "file name" and res["world"] is True
    assert not page.errors


def test_non_nifti_rejected_with_message(page, server, ui_data):
    page.goto(server + "/viewer.html")
    _ready(page)
    page.set_input_files("#fileIn", str(ui_data["files"] / "notes.txt"))
    page.wait_for_function("document.querySelector('#msg').classList.contains('err')")
    assert "not a NIfTI" in page.text_content("#msg")
    assert not page.errors


def test_viewer_starts_at_server_review_limit(page, server):
    """Regression: the viewer sent its own 0.25 on the first request and overrode the configured default."""
    c = _first_predicted(page, server)
    server_limit = page.request.get(server + "/api/cases").json()["review_limit"]
    page.goto(server + f"/viewer.html?case={c['id']}")
    _ready(page)
    assert abs(page.evaluate("window.__btqc.app.reviewLimit") - server_limit) < 1e-9
    assert abs(page.evaluate("window.__btqc.app.defaultLimit") - server_limit) < 1e-9
    assert not page.errors


def test_views_keep_their_height_without_example_banner(page, server):
    """Regression: on model cases the hidden EXAMPLE banner shifted the grid and collapsed the slice views."""
    c = _first_predicted(page, server)
    page.goto(server + f"/viewer.html?case={c['id']}")
    _ready(page)
    page.evaluate("document.querySelector('#exampleNote').hidden = true")
    page.wait_for_timeout(300)
    assert page.evaluate("document.querySelector('#viewsHost').getBoundingClientRect().height") > 200
    assert not page.errors


def test_overlay_and_flag_flip(page, server):
    c = _first_predicted(page, server)
    page.goto(server + f"/viewer.html?show=1&case={c['id']}")
    _ready(page)
    page.wait_for_function("window.__btqc.viewer.state.overlayOn === true")
    # example banner is shown for a non-model prediction
    assert page.is_visible("#exampleNote")
    assert page.evaluate(PIXELS_JS)["colored"] > 0
    score = page.evaluate("window.__btqc.app.pred.info.score")
    for limit, expect in ((max(0, score - 0.02), "review"), (min(1, score + 0.02), "ok")):
        page.evaluate("""(v) => { const s = document.querySelector('#thrFlag'); s.value = Math.round(v * 100);
                                  s.dispatchEvent(new Event('input')); }""", limit)
        if abs(round(limit * 100) / 100 - score) < 1e-9:
            continue
        assert page.get_attribute("#flagBox", "data-flag") == expect
    assert not page.errors


def test_pseudocolor_changes_display_only(page, server):
    c = _first_predicted(page, server)
    page.goto(server + f"/viewer.html?case={c['id']}")
    _ready(page)
    checksum = """() => { const v = window.__btqc.viewer, d = v.state.vol.seqs[v.state.seq]; let s = 0;
        for (let i = 0; i < d.length; i++) s = (s * 31 + d[i]) % 1000000007; return s; }"""
    before = page.evaluate(checksum)
    sig = page.text_content("#sSig")
    gray = page.evaluate(PIXELS_JS)
    assert gray["colored"] == 0 and gray["corner"] == [0, 0, 0]
    page.click("#modeColor")
    page.wait_for_timeout(500)
    col = page.evaluate(PIXELS_JS)
    assert col["colored"] > 0, "pseudocolor did not color the slice"
    assert col["corner"] == [0, 0, 0], "background (zero) must stay black"
    assert page.is_visible("#pseudoNote") and "display transform" in page.text_content("#pseudoNote")
    assert "Pseudocolor" in page.text_content(".view[data-view=axial] .vbadge")
    for name in ("inferno", "turbo", "coolwarm"):
        page.click(f"#cmaps [data-value={name}]")
        page.wait_for_timeout(400)
        assert page.evaluate("window.__btqc.viewer.state.cmap") == name
    assert page.evaluate(checksum) == before, "voxel values changed"
    assert page.text_content("#sSig") == sig
    page.click("#modeGray")
    page.wait_for_timeout(500)
    assert page.evaluate(PIXELS_JS)["colored"] == 0
    assert not page.errors


def test_region_toggles_and_outline(page, server):
    c = _first_predicted(page, server)
    page.goto(server + f"/viewer.html?show=1&case={c['id']}")
    _ready(page)
    page.wait_for_function("window.__btqc.viewer.state.overlayOn === true")
    fill = page.evaluate(PIXELS_JS)["colored"]
    for lab in ("1", "2", "4"):
        page.uncheck(f"[data-reg='{lab}']")
    assert page.evaluate(PIXELS_JS)["colored"] == 0
    page.check("[data-reg='2']")
    page.click("#segStyle [data-value=outline]")
    outline = page.evaluate(PIXELS_JS)["colored"]
    assert 0 < outline < fill
    assert not page.errors


def test_zoom_pan_and_pick_stay_consistent(page, server):
    c = _first_predicted(page, server)
    page.goto(server + f"/viewer.html?case={c['id']}")
    _ready(page)
    w = page.evaluate("""() => { const v = window.__btqc.viewer, a = v.views[0]; v.frame(); const w0 = a.rect.dw;
        v.zoomView(a, 2); v.frame(); return [w0, a.rect.dw]; }""")
    assert abs(w[1] / w[0] - 2) < 1e-6
    # click on the screen position of a known voxel; the crosshair must land on it
    target = page.evaluate("""() => { const v = window.__btqc.viewer, a = v.views[0], vol = v.state.vol;
        const want = [Math.round(vol.nx * 0.4), Math.round(vol.ny * 0.55)], cr = a.cross([want[0], want[1], 0]);
        const r = a.rect, b = a.canvas.getBoundingClientRect(), d = a.canvas.width / b.width;
        return {want, x: b.left + (r.ox + (cr[0] + 0.5) / a.W * r.dw) / d,
                y: b.top + (r.oy + (cr[1] + 0.5) / a.H * r.dh) / d}; }""")
    page.mouse.click(target["x"], target["y"])
    got = page.evaluate("window.__btqc.viewer.state.cursor")
    assert got[:2] == target["want"]
    page.dblclick(".view[data-view=axial] canvas")
    assert page.evaluate("window.__btqc.viewer.views[0].zoom") == 1
    # maximize a panel and restore the grid
    page.hover(".view[data-view=coronal]")
    page.click(".view[data-view=coronal] [data-act=max]")
    assert page.get_attribute(".views", "data-layout") == "single"
    assert page.evaluate("document.querySelector('.view[data-view=axial]').offsetParent === null")
    page.click(".view[data-view=coronal] [data-act=max]")
    assert page.get_attribute(".views", "data-layout") == "grid"
    assert not page.errors


def test_compare_sync_flicker_and_difference(page, server):
    ids = [c["id"] for c in _predicted(page, server)][:2]
    page.goto(server + f"/compare.html?a={ids[0]}&b={ids[1]}")
    _ready(page)
    assert page.evaluate("window.__cmp.geom.level") == "identical"
    assert "Identical grid" in page.text_content("#geo")
    follow = """(c) => { const {A, B} = window.__cmp; A.viewer.setCursor(c); return B.viewer.state.cursor; }"""
    assert page.evaluate(follow, [10, 12, 8]) == [10, 12, 8]
    page.click("#syncBtn")
    page.uncheck("[data-sync=cross]")
    page.uncheck("[data-sync=slice]")
    assert page.evaluate(follow, [5, 6, 7]) == [10, 12, 8]
    page.check("[data-sync=cross]")
    page.click("#syncBtn")
    assert not page.is_disabled("#modeDiff")
    page.click("#cmpMode [data-value=diff]")
    page.wait_for_timeout(300)
    lit = page.evaluate("""() => { const cv = document.querySelector('#stageCv');
        const d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data;
        let n = 0; for (let i = 0; i < d.length; i += 4) if (d[i] + d[i + 1] + d[i + 2] > 60) n++; return n; }""")
    assert lit > 0
    page.click("#cmpMode [data-value=flicker]")
    seen = page.evaluate("""() => new Promise(res => { const s = new Set(), t0 = performance.now();
        const tick = () => { s.add(window.__cmp.stage.showB);
            if (s.size > 1 || performance.now() - t0 > 2500) res([...s]); else requestAnimationFrame(tick); };
        tick(); })""")
    assert sorted(seen) == [False, True]
    page.click("#cmpMode [data-value=split]")
    assert page.is_visible("#divider")
    page.click("#cmpMode [data-value=side]")
    assert page.is_hidden("#cmpStage")
    assert not page.errors


def test_compare_different_geometry_syncs_through_world(page, server, ui_data):
    c = _first_predicted(page, server)
    page.goto(server + f"/compare.html?a={c['id']}&b={c['id']}")
    _ready(page)
    page.set_input_files("#sideB input[type=file]", str(ui_data["files"] / "planted_t1.nii.gz"))
    page.wait_for_function("window.__cmp.B.vol() && window.__cmp.B.vol().id === 'local'")
    assert page.evaluate("window.__cmp.geom.level") == "world"
    assert page.is_disabled("#modeDiff")
    res = page.evaluate("""() => { const {A, B} = window.__cmp, a = A.vol(), b = B.vol();
        const w = (v, c) => [0, 1, 2].map(r =>
            v.affine[r][0] * c[0] + v.affine[r][1] * c[1] + v.affine[r][2] * c[2] + v.affine[r][3]);
        A.viewer.setCursor([Math.round(a.nx / 2), Math.round(a.ny / 2), Math.round(a.nz / 2)]);
        return {wa: w(a, A.viewer.state.cursor), wb: w(b, B.viewer.state.cursor)}; }""")
    assert all(abs(x - y) <= 0.5 + 1e-6 for x, y in zip(res["wa"], res["wb"], strict=True)), res
    page.click("#cmpMode [data-value=flicker]")
    page.wait_for_timeout(300)
    assert page.is_hidden("#stageCover")
    assert not page.errors


def test_review_queue_persists_decision(page, server):
    page.goto(server + "/review.html")
    _ready(page)
    first = page.locator("#queue tbody tr").first
    cid = first.get_attribute("data-case")
    first.locator("[data-action=accept]").click()
    page.wait_for_function("document.querySelector('#msg').textContent.startsWith('Saved')")
    rows = page.request.get(server + "/api/review").json()
    assert rows[-1]["case_id"] == cid and rows[-1]["decision"] == "accept"
    assert not page.errors


def test_review_queue_filters_search_and_thumbnails(page, server):
    page.goto(server + "/review.html")
    _ready(page)
    n_all = page.locator("#queue tbody tr[data-case]").count()
    page.wait_for_function("(() => { const i = document.querySelector('#queue img.thumb');"
                           " return i && i.complete && i.naturalWidth === 96; })()")
    page.click("#filter [data-value=above]")
    above = page.locator("#queue tbody tr[data-case]").count()
    flags = page.eval_on_selector_all("#queue tbody [data-flag]", "els => els.map(e => e.dataset.flag)")
    assert all(f == "review" for f in flags)
    page.click("#filter [data-value=below]")
    below = page.locator("#queue tbody tr[data-case]").count()
    assert above + below == n_all
    page.click("#filter [data-value=all]")
    cid = page.locator("#queue tbody tr[data-case]").first.get_attribute("data-case")
    page.fill("#q", cid)
    assert page.locator("#queue tbody tr[data-case]").count() == 1
    assert not page.errors


def test_explorer_not_run_and_synthetic_demo(page, server):
    page.goto(server + "/explorer.html")
    _ready(page)
    assert "Not run" in page.text_content("#status")
    if page.is_visible("#synthWrap"):
        page.check("#synth")
        page.wait_for_selector("#cHeld svg")
        assert page.is_visible("#synthNote")
        assert "Synthetic" in page.text_content("#cHeld .badge")
    assert not page.errors


def test_home_page_status_and_links(page, server):
    page.goto(server + "/index.html")
    _ready(page)
    assert page.get_attribute("#ctaWorkspace", "href") == "viewer.html"
    hrefs = page.eval_on_selector_all(".fcard", "els => els.map(e => e.getAttribute('href'))")
    assert len(hrefs) == 6 and "compare.html" in hrefs and "explorer.html" in hrefs
    assert "Processed cases" in page.text_content("#statlist")
    page.wait_for_selector("#stage3d.ready", timeout=30000)
    assert "EXAMPLE" in page.text_content("#heroCapT") or "model" in page.text_content("#heroCapT")
    assert not page.errors


def test_legacy_index_link_redirects_to_viewer(page, server):
    c = _first_predicted(page, server)
    page.goto(server + f"/index.html?show=1&case={c['id']}")
    page.wait_for_url("**/viewer.html**")
    _ready(page)
    page.wait_for_function("window.__btqc.viewer.state.overlayOn === true")
    assert page.evaluate("window.__btqc.app.caseId") == c["id"]


@pytest.mark.parametrize("path", PAGES)
def test_mobile_no_horizontal_overflow_and_disclaimer(browser, server, path):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(server + "/" + path)
    _ready(pg)
    time.sleep(0.3)
    sw = pg.evaluate("document.documentElement.scrollWidth")
    assert sw <= 390, f"{path}: scrollWidth {sw}"
    assert "Not a medical device" in pg.text_content("#disclaimer")
    assert not errs
    ctx.close()


def test_api_prediction_matches_ui_volumes(page, server):
    c = _first_predicted(page, server)
    info = page.request.get(server + f"/api/cases/{c['id']}/prediction").json()
    page.goto(server + f"/viewer.html?show=1&case={c['id']}")
    _ready(page)
    page.wait_for_function("window.__btqc.viewer.state.overlayOn === true")
    wt = page.text_content("#vWT")
    assert wt == f"{info['volumes_ml']['WT']:.1f} mL"
    json.dumps(info)


def test_webgl_volume_renders(page, server):
    c = _first_predicted(page, server)
    page.goto(server + f"/viewer.html?show=1&case={c['id']}")
    _ready(page)
    page.wait_for_function("window.__btqc.viewer.state.overlayOn === true")
    res = page.evaluate("""() => {
        const v = window.__btqc.viewer; v.frame();
        const r = v.r3d; if (!r.ok) return {ok: false};
        const gl = r.gl, w = gl.drawingBufferWidth, h = gl.drawingBufferHeight, px = new Uint8Array(w * h * 4);
        gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, px);
        let lit = 0; for (let i = 0; i < px.length; i += 4) if (px[i] + px[i + 1] + px[i + 2] > 30) lit++;
        return {ok: true, lit, total: w * h};
    }""")
    assert res["ok"], "WebGL 2 not available in headless Chromium"
    assert res["lit"] > 0.01 * res["total"]


def test_natural_3d_tint_is_labeled_and_kept_across_modes(page, server):
    c = _first_predicted(page, server)
    page.goto(server + f"/viewer.html?show=1&case={c['id']}")
    _ready(page)
    page.wait_for_function("window.__btqc.viewer.state.overlayOn === true")
    badge = "[data-view='3d'] .vbadge"
    page.click("[data-view='3d'] [data-r3=natural]")
    page.click("[data-r3t=natural]")
    assert "brain + tumor" in page.inner_text(badge)
    assert page.is_disabled("[data-r3=cut]")
    res = page.evaluate("""() => {
        const v = window.__btqc.viewer; v.frame();
        const r = v.r3d; if (!r.ok) return {ok: false};
        const gl = r.gl, w = gl.drawingBufferWidth, h = gl.drawingBufferHeight, px = new Uint8Array(w * h * 4);
        gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, px);
        let lit = 0, rs = 0, bs = 0;
        for (let i = 0; i < px.length; i += 4) {
            if (px[i] + px[i + 1] + px[i + 2] > 30) { lit++; rs += px[i]; bs += px[i + 2]; }
        }
        return {ok: true, lit, warm: rs > bs};
    }""")
    assert res["ok"], "WebGL 2 not available in headless Chromium"
    assert res["lit"] > 0 and res["warm"]
    page.click("#modeGray")
    assert page.evaluate("window.__btqc.viewer.style3d()") == "natural"
    assert page.is_hidden("[data-view='3d'] .tumcol")
    assert page.inner_text(badge).strip() == "Illustrative tint · brain"
    assert not page.errors


def test_screenshots(browser, server):
    """Saves screenshots for visual review (results/screenshots)."""
    from btqc.config import REPO_ROOT

    out = REPO_ROOT / "results" / "screenshots"
    out.mkdir(parents=True, exist_ok=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    ids = [c["id"] for c in _predicted(page, server)]
    page.goto(server + "/index.html")
    _ready(page)
    page.wait_for_selector("#stage3d.ready", timeout=30000)
    page.wait_for_timeout(1800)
    page.screenshot(path=str(out / "home_synthetic.png"))
    page.goto(server + f"/viewer.html?show=1&case={ids[0]}")
    _ready(page)
    page.wait_for_function("window.__btqc.viewer.state.overlayOn === true")
    page.check("#layUnc")
    page.wait_for_timeout(600)
    page.screenshot(path=str(out / "viewer_synthetic.png"))
    page.click("#modeColor")
    page.wait_for_timeout(600)
    page.screenshot(path=str(out / "viewer_pseudocolor_synthetic.png"))
    page.goto(server + f"/compare.html?a={ids[0]}&b={ids[1]}")
    _ready(page)
    page.wait_for_timeout(600)
    page.screenshot(path=str(out / "compare_synthetic.png"))
    page.goto(server + "/explorer.html")
    _ready(page)
    if page.is_visible("#synthWrap"):
        page.check("#synth")
        page.wait_for_selector("#cHeld svg")
    page.wait_for_timeout(1200)
    page.screenshot(path=str(out / "explorer_synthetic.png"), full_page=True)
    page.goto(server + "/review.html")
    _ready(page)
    page.wait_for_timeout(800)
    page.screenshot(path=str(out / "review_synthetic.png"), full_page=True)
    ctx.close()
