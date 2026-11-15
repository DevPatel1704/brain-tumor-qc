// Compare page: two independent viewers with configurable synchronization through
// physical coordinates, plus flicker, split and difference views drawn on scan A's
// grid. Scan B is resampled into that grid by nearest neighbour through the
// world (scanner mm) coordinates; difference is offered only for identical grids.
import { SEQ_LABELS } from './colors.js';
import { CMAP_ORDER, CMAPS, cmapGradient, cmapTable } from './colormaps.js';
import { pickSource, volumeFromFiles } from './data.js';
import { decide } from './gate.js';
import { compareGeometry, toVoxel, toWorld } from './geometry.js';
import { fmt, mountNav } from './nav.js';
import { icon, paintRanges, radioGroup, setRadio, toast } from './ui.js';
import { drawOverlayMarks, Viewer } from './viewer.js';

const $ = (s, r = document) => r.querySelector(s);
mountNav('compare.html');
const src = pickSource();
const params = new URLSearchParams(location.search);
const sync = { cross: true, slice: true, zoom: true, pan: true, display: false, cam: true };
let cases = [], limit = 0.25, geom = { level: 'none', notes: [] }, lock = false, mode = 'side', view = 'all';

const sideHTML = k => `<header class="side-head">
  <span class="side-tag">${k}</span>
  <select data-k="case" aria-label="Scan ${k} case"><option value="">Loading…</option></select>
  <label class="btn sm ghost" title="Open local NIfTI files (stay in this browser)">${icon('upload', 14)}<span>Files</span><input type="file" multiple accept=".nii,.gz" hidden data-k="files"></label>
  <div class="seg" role="radiogroup" data-k="seq" aria-label="Scan ${k} sequence"></div>
  <span class="grow"></span>
  <div class="seg" role="radiogroup" data-k="mode" aria-label="Scan ${k} display mode">
    <button type="button" role="radio" data-value="gray" aria-checked="true">Gray</button><button type="button" role="radio" data-value="color" aria-checked="false">Color</button><button type="button" role="radio" data-value="seg" aria-checked="false">Seg</button></div>
  <select data-k="cmap" aria-label="Scan ${k} color map" hidden>${CMAP_ORDER.map(c => `<option value="${c}">${CMAPS[c].label}</option>`).join('')}</select>
  <label class="check sm" data-k="uncWrap" hidden><input type="checkbox" class="switch warm" data-k="unc"><span>Uncertainty</span></label>
  <span class="badge example" data-k="ex" hidden>Example outline</span>
</header>
<div class="side-body" data-views-host><div class="cover on" data-k="cover"><div class="cover-card idle"><div class="ring"></div><p data-k="coverT">Choose a case</p><div class="prog"><i data-k="coverP"></i></div></div></div>
  <div class="side-note example" data-k="note" hidden></div></div>
<div class="status" data-k="status"><span>RAS<b data-k="sRas">–</b></span><span>World mm<b data-k="sWorld">–</b></span><span>Signal<b data-k="sSig">–</b></span></div>`;

class Side {
  constructor(k) {
    this.k = k; this.el = $('#side' + k); this.el.innerHTML = sideHTML(k);
    this.q = n => this.el.querySelector(`[data-k="${n}"]`);
    this.viewer = new Viewer(this.el, { keys: false, onCursor: r => this.readout(r) });
    this.pred = null; this.ref = null; this.caseId = null; this.info = null;
    radioGroup(this.q('seq'), s => { this.viewer.setSeq(s); this.syncHeader(); });
    radioGroup(this.q('mode'), m => this.setMode(m));
    this.q('cmap').addEventListener('change', e => { this.viewer.setColormap(e.target.value); this.syncHeader(); });
    this.q('unc').addEventListener('change', e => this.viewer.setLayer('unc', e.target.checked));
    this.q('case').addEventListener('change', e => this.loadCase(e.target.value));
    this.q('files').addEventListener('change', e => this.loadFiles(e.target.files));
  }
  vol() { return this.viewer.state.vol; }
  cover(t, f) {
    const c = this.q('cover'); c.classList.toggle('on', !!t); if (!t) return;
    this.q('coverT').textContent = t; c.firstElementChild.classList.toggle('idle', f == null);
    if (f != null) this.q('coverP').style.width = Math.round(f * 100) + '%';
  }
  readout(r) {
    this.q('sRas').textContent = r.canonical.join(', ');
    this.q('sWorld').textContent = r.world ? r.world.map(v => v.toFixed(1)).join(', ') : 'n/a';
    this.q('sSig').textContent = Math.round(r.signal / 255 * 100) + '%';
    stage.invalidate();
  }
  setMode(m) {
    if (m === 'seg' && !(this.pred || this.ref)) return;
    this.viewer.setMode(m);
    if (m === 'seg') this.viewer.setGlass(this.viewer.r3d.ok); else this.viewer.setGlass(false);
    this.syncHeader();
  }
  syncHeader() {
    const s = this.viewer.state, v = s.vol;
    setRadio(this.q('mode'), s.mode);
    this.q('mode').querySelector('[data-value=seg]').disabled = !(this.pred || this.ref);
    const cm = this.q('cmap'); cm.hidden = !(s.mode === 'color'); cm.value = s.cmap;
    this.q('uncWrap').hidden = !(s.mode === 'seg' && this.pred);
    this.q('ex').hidden = !(s.mode === 'seg' && this.pred && this.pred.info.is_example);
    if (v) setRadio(this.q('seq'), s.seq);
    stage.invalidate();
  }
  buildSeq() {
    const box = this.q('seq'), v = this.vol(); box.innerHTML = '';
    for (const s of v.order) box.insertAdjacentHTML('beforeend', `<button type="button" role="radio" data-value="${s}">${SEQ_LABELS[s.replace(/\*+$/, '')] || s}</button>`);
    setRadio(box, this.viewer.state.seq);
  }
  afterLoad(label) {
    if (this.viewer.state.mode === 'seg' && !(this.pred || this.ref)) this.viewer.setMode('gray', { animate: false });
    if (this.pred) this.viewer.setOverlay(this.pred.labels, this.pred.unc); else this.viewer.setOverlay(this.ref, null);
    this.buildSeq(); this.syncHeader(); this.cover('');
    $(`#tag${this.k}T`).textContent = label;
    onGeometry();
  }
  async loadCase(id) {
    if (!id) return;
    this.cover('Loading ' + id + '…', 0);
    try {
      const info = cases.find(c => c.id === id) || {};
      const vol = await src.volume(id, (t, f) => this.cover(t, f), info.sequences && info.sequences.length ? info.sequences : undefined);
      this.viewer.setVolume(vol); this.caseId = id; this.info = info;
      const [ref, pred] = await Promise.all([info.has_reference ? src.reference(id) : null, info.has_prediction === false ? null : src.prediction(id, limit)]);
      this.ref = ref; this.pred = pred;
      this.q('case').value = id;
      this.afterLoad(id);
      updateUrl();
    } catch (e) { console.error(e); this.cover('Could not load ' + id); toast('Scan ' + this.k + ': ' + e.message, 'err', 5000); }
  }
  async loadFiles(list) {
    if (!list || !list.length) return;
    this.cover('Reading files…');
    try {
      const { vol, seg } = await volumeFromFiles(list);
      this.viewer.setVolume(vol); this.caseId = null; this.info = null; this.pred = null; this.ref = seg;
      this.q('case').value = '';
      this.afterLoad('Local files');
      toast(`Scan ${this.k}: opened ${list.length} local file${list.length > 1 ? 's' : ''}`, 'ok');
    } catch (e) { this.cover(this.vol() ? '' : 'Choose a case'); toast('Scan ' + this.k + ': ' + e.message, 'err', 5000); }
  }
  setNote(t) { const n = this.q('note'); n.hidden = !t; if (t) n.innerHTML = icon('info', 14) + '<span>' + t + '</span>'; }
}

/* ------------------------------------------------------------------ geometry */
// Voxel of `to` at the physical position of voxel c of `from`, unrounded; null without world coordinates.
function mapRaw(from, to, c) { if (!from.hasWorld || !to.hasWorld) return null; const w = toWorld(from, c); return w && toVoxel(to, w); }
const inside = (v, p) => p[0] >= -0.5 && p[1] >= -0.5 && p[2] >= -0.5 && p[0] < v.nx - 0.5 && p[1] < v.ny - 0.5 && p[2] < v.nz - 0.5;

function onGeometry() {
  const a = A.vol(), b = B.vol(), g = $('#geo');
  if (!a || !b) { geom = { level: 'none', notes: [] }; return; }
  geom = compareGeometry(a, b);
  g.className = 'geo ' + geom.level;
  $('#geoT').textContent = geom.level === 'identical' ? 'Identical grid · voxel-wise comparison available'
    : geom.level === 'world' ? 'Different geometry · synced through physical coordinates' : 'No physical coordinates · sync unavailable';
  g.title = geom.notes.join(' ') || 'Same dimensions, spacing and affine.';
  $('#modeDiff').disabled = geom.level !== 'identical';
  $('#modeDiff').title = geom.level === 'identical' ? '' : 'Difference needs two scans on an identical grid. ' + geom.notes.join(' ');
  for (const b2 of $('#cmpMode').querySelectorAll('[data-value=flicker],[data-value=split]')) b2.disabled = geom.level === 'none';
  for (const i of document.querySelectorAll('[data-sync]')) i.disabled = geom.level === 'none';
  $('#syncHelp').textContent = geom.level === 'none' ? 'Synchronization is unavailable: ' + geom.notes.join(' ')
    : 'Positions are matched through physical (scanner) coordinates, never by voxel index alone.';
  if ((mode === 'diff' && geom.level !== 'identical') || (mode !== 'side' && geom.level === 'none')) setMode('side');
  renderMeta();
  // bring B to A's position once both are loaded
  if (geom.level !== 'none' && sync.cross) pushCursor(A, null);
  stage.invalidate();
}

function pushCursor(from, axis) {
  const to = from === A ? B : A, a = from.vol(), b = to.vol();
  if (!a || !b || geom.level === 'none' || (!sync.cross && !(sync.slice && axis != null))) return;
  const c = from.viewer.state.cursor, p = geom.level === 'identical' ? c.slice() : mapRaw(a, b, c);
  if (!p) return;
  const r = p.map(Math.round);
  lock = true;
  if (sync.cross) {
    const ok = inside(b, p); to.setNote(ok ? '' : 'The synchronized position is outside this scan’s field of view.');
    if (ok) to.viewer.setCursor(r, { emit: false });
  } else {
    const n = [b.nx, b.ny, b.nz][axis], ok = r[axis] >= 0 && r[axis] < n;
    to.setNote(ok ? '' : 'The synchronized slice is outside this scan’s field of view.');
    if (ok) { const c2 = to.viewer.state.cursor.slice(); c2[axis] = r[axis]; to.viewer.setCursor(c2, { emit: false }); }
  }
  lock = false;
}

function bindSync(s) {
  const o = () => (s === A ? B : A), v = s.viewer;
  v.on('cursor', ({ axis }) => { if (!lock) pushCursor(s, axis); });
  v.on('view', d => {
    if (lock || !(sync.zoom || sync.pan) || geom.level === 'none' || !o().vol()) return;
    lock = true; o().viewer.setViewTransform(d.key, d, { useZoom: sync.zoom, usePan: sync.pan }); lock = false;
  });
  v.on('display', d => {
    if (lock || !sync.display || !o().vol()) return;
    lock = true;
    const tgt = o();
    if (d.mode === 'seg' && !(tgt.pred || tgt.ref)) d = { ...d, mode: 'gray' };
    tgt.viewer.applyDisplay(d); tgt.syncHeader(); lock = false;
  });
  v.on('camera', cam => { if (lock || !sync.cam || !o().vol()) return; lock = true; o().viewer.setCamera(cam); lock = false; });
}

/* ------------------------------------------------------------------ composite stage */
const stage = {
  cv: $('#stageCv'), zoom: 1, pan: [0, 0], split: 0.5, showB: false, timer: 0, raf: 0, gain: 2, cacheKey: '', mapB: null,
  invalidate() { if (mode === 'side' || this.raf) return; this.raf = requestAnimationFrame(() => { this.raf = 0; this.draw(); }); },
  key() { return view === 'all' || view === '3d' ? 'axial' : view; },
  pseudo() {
    const vA = A.viewer.views.find(w => w.key === this.key());
    return { canvas: this.cv, W: vA.W, H: vA.H, mmW: vA.mmW, mmH: vA.mmH, zoom: this.zoom, pan: this.pan, letters: vA.letters, vA };
  },
  size() { const d = Math.min(window.devicePixelRatio || 1, 2), c = this.cv, w = Math.round(c.clientWidth * d), h = Math.round(c.clientHeight * d); if (c.width !== w || c.height !== h) { c.width = w; c.height = h; } },
  // Linear index in B for every pixel of A's current slice (-1 outside B).
  mapping(vA) {
    const a = A.vol(), b = B.vol(), so = vA.sliceOff(A.viewer.state.cursor), W = vA.W, H = vA.H;
    const key = [this.key(), so, a.id, b.id, a.nx, b.nx, geom.level].join('|');
    if (key === this.cacheKey) return this.mapB;
    const out = new Int32Array(W * H);
    if (geom.level === 'identical') { let k = 0; for (let r = 0; r < H; r++) { const ro = vA.rowOff[r] + so; for (let c = 0; c < W; c++) out[k++] = ro + vA.colOff[c]; } }
    else {
      const at = (col, row) => { const c = A.viewer.state.cursor.slice(); vA.pick(col, row, c); return mapRaw(a, b, c); };
      const p0 = at(0, 0), p1 = at(1, 0), p2 = at(0, 1), dc = p1.map((v, i) => v - p0[i]), dr = p2.map((v, i) => v - p0[i]);
      let k = 0;
      for (let r = 0; r < H; r++) for (let c = 0; c < W; c++) {
        const x = Math.round(p0[0] + c * dc[0] + r * dr[0]), y = Math.round(p0[1] + c * dc[1] + r * dr[1]), z = Math.round(p0[2] + c * dc[2] + r * dr[2]);
        out[k++] = x < 0 || y < 0 || z < 0 || x >= b.nx || y >= b.ny || z >= b.nz ? -1 : x + b.nx * (y + b.ny * z);
      }
    }
    this.cacheKey = key; this.mapB = out; return out;
  },
  image(W, H, fill) {
    if (!this.offs || this.offs.W !== W || this.offs.H !== H) {
      const mk = () => { const c = document.createElement('canvas'); c.width = W; c.height = H; const x = c.getContext('2d'), img = x.createImageData(W, H); return { c, x, img, px: new Uint32Array(img.data.buffer) }; };
      this.offs = { W, H, a: mk(), b: mk(), d: mk() };
    }
    const o = this.offs[fill]; return o;
  },
  draw() {
    const ctx = this.cv.getContext('2d'); this.size();
    const cw = this.cv.width, ch = this.cv.height; ctx.fillStyle = '#030405'; ctx.fillRect(0, 0, cw, ch);
    const a = A.vol(), b = B.vol();
    const why = !a || !b ? 'Load scan A and scan B.' : geom.level === 'none' ? 'These scans have no shared physical coordinates, so they cannot be overlaid.' : '';
    $('#stageCover').classList.toggle('on', !!why); $('#stageCoverT').textContent = why;
    if (why) return;
    const pv = this.pseudo(), vA = pv.vA, W = vA.W, H = vA.H, so = vA.sliceOff(A.viewer.state.cursor), map = this.mapping(vA);
    const P = A.viewer.placement(pv); if (!P) return;
    this.P = P;
    const draw = (which) => {
      const o = this.image(W, H, which), px = o.px;
      if (which === 'a') { const f = A.viewer.shader(vA.axis); let k = 0; for (let r = 0; r < H; r++) { const ro = vA.rowOff[r] + so; for (let c = 0; c < W; c++) px[k++] = f(ro + vA.colOff[c]); } }
      else if (which === 'b') { const f = B.viewer.shader(vA.axis); for (let k = 0; k < px.length; k++) px[k] = map[k] < 0 ? 0xFF141210 : f(map[k]); }
      else {
        const da = a.seqs[A.viewer.state.seq], db = b.seqs[B.viewer.state.seq], T = cmapTable('coolwarm'), g = this.gain;
        let k = 0;
        for (let r = 0; r < H; r++) { const ro = vA.rowOff[r] + so; for (let c = 0; c < W; c++, k++) {
          const ia = ro + vA.colOff[c], x = da[ia], y = db[map[k]];
          if (!x && !y) { px[k] = 0xFF000000; continue; }
          const t = Math.max(0, Math.min(255, Math.round(127.5 + (x - y) * g / 2))) * 3;
          px[k] = 0xFF000000 | (T[t + 2] << 16) | (T[t + 1] << 8) | T[t];
        } }
      }
      o.x.putImageData(o.img, 0, 0); return o.c;
    };
    ctx.imageSmoothingEnabled = vA.smooth; ctx.imageSmoothingQuality = 'high';
    if (mode === 'flicker') ctx.drawImage(draw(this.showB ? 'b' : 'a'), 0, 0, W, H, P.ox, P.oy, P.dw, P.dh);
    else if (mode === 'diff') ctx.drawImage(draw('d'), 0, 0, W, H, P.ox, P.oy, P.dw, P.dh);
    else {
      const x = cw * this.split;
      ctx.drawImage(draw('a'), 0, 0, W, H, P.ox, P.oy, P.dw, P.dh);
      ctx.save(); ctx.beginPath(); ctx.rect(x, 0, cw - x, ch); ctx.clip();
      ctx.drawImage(draw('b'), 0, 0, W, H, P.ox, P.oy, P.dw, P.dh); ctx.restore();
    }
    drawOverlayMarks(ctx, pv, P, vA.cross(A.viewer.state.cursor), true);
    const c = A.viewer.state.cursor, ia = c[0] + a.nx * (c[1] + a.ny * c[2]);
    const cr = vA.cross(c), kb = map[cr[1] * W + cr[0]];
    $('#stA').textContent = Math.round(a.seqs[A.viewer.state.seq][ia] / 255 * 100) + '%';
    $('#stB').textContent = kb >= 0 ? Math.round(b.seqs[B.viewer.state.seq][kb] / 255 * 100) + '%' : 'outside';
    const sc = $('#stScrub'); sc.max = vA.n - 1; sc.value = c[vA.axis]; paintRanges($('#cmpStage'));
    $('#stPos').textContent = (c[vA.axis] + 1) + ' / ' + vA.n;
    $('#tagA').classList.toggle('dim', mode === 'flicker' && this.showB); $('#tagB').classList.toggle('dim', mode === 'flicker' && !this.showB);
    if (mode === 'split') { const d = $('#divider'); d.style.left = (this.split * 100) + '%'; d.setAttribute('aria-valuenow', Math.round(this.split * 100)); }
  },
  startFlicker() {
    clearInterval(this.timer);
    if (mode !== 'flicker' || $('#flkPlay').getAttribute('aria-pressed') !== 'true') return;
    this.timer = setInterval(() => { this.showB = !this.showB; this.draw(); }, +$('#flkRate').value);
  },
};

function bindStage() {
  const cv = stage.cv;
  const at = e => { const r = cv.getBoundingClientRect(), d = cv.width / r.width; return [(e.clientX - r.left) * d, (e.clientY - r.top) * d]; };
  let drag = null, last = null;
  const pick = e => {
    const P = stage.P; if (!P) return;
    const [x, y] = at(e), vA = stage.pseudo().vA, c = A.viewer.state.cursor.slice();
    vA.pick(Math.max(0, Math.min(vA.W - 1, Math.floor((x - P.ox) / P.dw * vA.W))), Math.max(0, Math.min(vA.H - 1, Math.floor((y - P.oy) / P.dh * vA.H))), c);
    A.viewer.setCursor(c);
  };
  cv.addEventListener('pointerdown', e => {
    cv.setPointerCapture(e.pointerId); drag = e.button === 2 || e.shiftKey ? 'pan' : 'cross'; last = at(e);
    if (drag === 'cross') pick(e);
  });
  cv.addEventListener('pointermove', e => {
    if (drag === 'cross') pick(e);
    if (drag === 'pan' && stage.P) { const p = at(e); stage.pan[0] += (p[0] - last[0]) / stage.P.scale; stage.pan[1] += (p[1] - last[1]) / stage.P.scale; last = p; stage.invalidate(); }
  });
  cv.addEventListener('pointerup', () => { drag = null; });
  cv.addEventListener('contextmenu', e => e.preventDefault());
  cv.addEventListener('dblclick', () => { stage.zoom = 1; stage.pan = [0, 0]; stage.invalidate(); });
  cv.addEventListener('wheel', e => {
    e.preventDefault(); if (!A.vol()) return;
    if (e.ctrlKey || e.metaKey) { stage.zoom = Math.max(0.5, Math.min(12, stage.zoom * Math.exp(-e.deltaY * 0.0022))); stage.invalidate(); return; }
    const vA = A.viewer.views.find(w => w.key === stage.key()); A.viewer.step(vA, e.deltaY < 0 ? 1 : -1);
  }, { passive: false });
  $('#stScrub').addEventListener('input', e => { const vA = A.viewer.views.find(w => w.key === stage.key()), c = A.viewer.state.cursor.slice(); c[vA.axis] = +e.target.value; A.viewer.setCursor(c, { axis: vA.axis }); });
  const dv = $('#divider');
  dv.addEventListener('pointerdown', e => { dv.setPointerCapture(e.pointerId); dv.dragging = true; });
  dv.addEventListener('pointermove', e => { if (!dv.dragging) return; const r = $('#cmpStage').getBoundingClientRect(); stage.split = Math.max(0.02, Math.min(0.98, (e.clientX - r.left) / r.width)); stage.invalidate(); });
  dv.addEventListener('pointerup', () => { dv.dragging = false; });
  dv.addEventListener('keydown', e => { if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { stage.split = Math.max(0.02, Math.min(0.98, stage.split + (e.key === 'ArrowLeft' ? -0.02 : 0.02))); stage.invalidate(); e.preventDefault(); } });
  $('#flkPlay').innerHTML = icon('pause');
  $('#flkPlay').addEventListener('click', e => {
    const on = e.currentTarget.getAttribute('aria-pressed') !== 'true';
    e.currentTarget.setAttribute('aria-pressed', String(on)); e.currentTarget.innerHTML = icon(on ? 'pause' : 'play');
    e.currentTarget.setAttribute('aria-label', on ? 'Pause flicker' : 'Play flicker');
    if (!on) { stage.showB = !stage.showB; stage.draw(); }
    stage.startFlicker();
  });
  $('#flkRate').addEventListener('input', e => { $('#flkRateO').textContent = e.target.value + ' ms'; stage.startFlicker(); });
  $('#diffGain').addEventListener('input', e => { stage.gain = +e.target.value / 100; $('#diffGainO').textContent = stage.gain.toFixed(1) + '×'; stage.invalidate(); });
  $('#diffCb').style.background = cmapGradient('coolwarm');
  new ResizeObserver(() => stage.invalidate()).observe($('#cmpStage'));
}

/* ------------------------------------------------------------------ modes, views */
function setMode(m) {
  mode = m; setRadio($('#cmpMode'), m);
  $('#cmp').dataset.mode = m;
  $('#cmpStage').hidden = m === 'side';
  $('#divider').hidden = m !== 'split';
  $('#flkCtl').hidden = m !== 'flicker'; $('#diffCtl').hidden = m !== 'diff';
  $('#tagB').hidden = m === 'diff'; $('#tagAT').textContent = m === 'diff' ? `A − B · ${A.caseId || 'local'} − ${B.caseId || 'local'}` : (A.caseId || 'Local files');
  for (const b of $('#cmpView').querySelectorAll('[data-value=all],[data-value="3d"]')) b.disabled = m !== 'side';
  if (m !== 'side' && (view === 'all' || view === '3d')) setView('axial');
  stage.cacheKey = ''; stage.showB = false;
  stage.startFlicker();
  if (m !== 'side') requestAnimationFrame(() => stage.draw());
  else { for (const s of [A, B]) s.viewer.sizeCanvases(); }
}

function setView(v) {
  view = v; setRadio($('#cmpView'), v);
  for (const s of [A, B]) s.viewer.setLayout(v === 'all' ? 'grid' : 'single', v === 'all' ? s.viewer.main : v);
  stage.cacheKey = ''; stage.invalidate();
}

function renderMeta() {
  const tb = $('#metaTbl tbody'), a = A.vol(), b = B.vol(); tb.innerHTML = '';
  const row = s => {
    const v = s.vol(); if (!v) return {};
    const p = s.pred && s.pred.info, i = s.info || {}, o = v.hasWorld ? toWorld(v, [0, 0, 0]) : null;
    return {
      Case: s.caseId || 'local files', Source: v.seqSource === 'dataset' ? 'dataset' : 'local files', Sequences: v.order.map(k => SEQ_LABELS[k.replace(/\*+$/, '')] || k).join(', '),
      Grid: `${v.nx} × ${v.ny} × ${v.nz}`, 'Spacing (mm)': [v.sx, v.sy, v.sz].map(x => +x.toFixed(3)).join(' × '), 'On disk': v.origAxes || '–',
      'Physical coordinates': v.hasWorld ? 'yes' : 'no', 'Origin of voxel 0,0,0 (mm)': o ? o.map(x => x.toFixed(1)).join(', ') : '–',
      'Site group': i.group || (s.caseId ? 'unknown' : '–'), 'Reference mask': s.ref ? 'yes' : 'no',
      Prediction: p ? (p.is_example ? 'rule-based example' : 'model · ' + p.method) : 'none',
      'Boundary uncertainty': p ? fmt(p.score) : '–', [`Flag at limit ${limit.toFixed(2)}`]: p ? decide(p.score, limit).label : '–',
      'WT volume (mL)': p && p.volumes_ml ? fmt(p.volumes_ml.WT, 1) : '–',
    };
  };
  const ra = row(A), rb = row(B);
  for (const k of new Set([...Object.keys(ra), ...Object.keys(rb)])) {
    const tr = tb.insertRow(), d = a && b && ra[k] !== rb[k] && !['Case'].includes(k);
    tr.insertCell().textContent = k;
    for (const v of [ra[k], rb[k]]) { const td = tr.insertCell(); td.textContent = v ?? '–'; if (d) td.className = 'diff'; }
  }
}

function updateUrl() { if (src.kind !== 'api') return; const q = new URLSearchParams(); if (A.caseId) q.set('a', A.caseId); if (B.caseId) q.set('b', B.caseId); history.replaceState(null, '', '?' + q); }

/* ------------------------------------------------------------------ init */
const A = new Side('A'), B = new Side('B');
window.__cmp = { A, B, sync, stage, get geom() { return geom; }, setMode, setView };
bindSync(A); bindSync(B); bindStage();
radioGroup($('#cmpMode'), setMode);
radioGroup($('#cmpView'), setView);
setRadio($('#cmpMode'), 'side'); setRadio($('#cmpView'), 'all');
$('#syncBtn').innerHTML = icon('link', 14) + 'Sync';
$('#resetBoth').innerHTML = icon('reset', 14) + 'Reset both';
$('#syncBtn').addEventListener('click', e => { const p = $('#syncPop'); p.hidden = !p.hidden; e.currentTarget.setAttribute('aria-expanded', String(!p.hidden)); });
document.addEventListener('pointerdown', e => { const p = $('#syncPop'); if (!p.hidden && !p.contains(e.target) && !$('#syncBtn').contains(e.target)) { p.hidden = true; $('#syncBtn').setAttribute('aria-expanded', 'false'); } });
for (const i of document.querySelectorAll('[data-sync]')) i.addEventListener('change', () => { sync[i.dataset.sync] = i.checked; if (i.checked && i.dataset.sync === 'cross') pushCursor(A, null); });
$('#resetBoth').addEventListener('click', () => { for (const s of [A, B]) { s.viewer.resetViews(); s.viewer.flyCam('reset'); } stage.zoom = 1; stage.pan = [0, 0]; stage.invalidate(); });

async function init() {
  try {
    const res = await src.cases(); cases = res.cases; limit = res.review_limit;
    for (const s of [A, B]) {
      const sel = s.q('case'); sel.innerHTML = '<option value="">Choose a case…</option>';
      for (const c of cases) { const o = document.createElement('option'); o.value = c.id; o.textContent = c.id + (c.has_prediction ? (c.prediction_source === 'model' ? ' · prediction' : ' · example') : ''); sel.appendChild(o); }
    }
    const withPred = cases.filter(c => c.has_prediction), pool = withPred.length >= 2 ? withPred : cases;
    const a = params.get('a') || (pool[0] || {}).id, b = params.get('b') || (pool[1] || pool[0] || {}).id;
    await Promise.all([a ? A.loadCase(a) : null, b ? B.loadCase(b) : null]);
  } catch (e) {
    for (const s of [A, B]) { s.q('case').innerHTML = '<option value="">No case server</option>'; s.cover('Open local files'); }
    toast('Case list not available: ' + e.message + '. You can still open local files.', 'err', 6000);
  }
  paintRanges();
  window.__ready = true;
}
init();
