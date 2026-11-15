// Three linked orthogonal views (radiological display) plus the 3D view.
// Volumes are canonical RAS, x-fastest. Display modes: grayscale, pseudocolor (a
// color map applied to the windowed intensity) and MRI + segmentation. Voxel values
// are never modified; only the 256-entry display lookup table changes.
// The viewer builds its own panels, so a page can host more than one (Compare).
import { HEAT, SEG_COLORS, SEG_NAMES } from './colors.js';
import { CMAPS, cmapTable } from './colormaps.js';
import { toWorld } from './geometry.js';
import { Renderer3D } from './render3d.js';
import { flip, icon, paintRange, reducedMotion } from './ui.js';

const $ = (s, r = document) => r.querySelector(s);
export const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const ease = t => 1 - Math.pow(1 - t, 3);
const PANEL_BG = '#030405';
const ZMIN = 0.5, ZMAX = 12;

const VIEWS = [
  { key: 'axial', name: 'Axial', axis: 2, letters: ['R', 'L', 'A', 'P'] },
  { key: 'coronal', name: 'Coronal', axis: 1, letters: ['R', 'L', 'S', 'I'] },
  { key: 'sagittal', name: 'Sagittal', axis: 0, letters: ['A', 'P', 'S', 'I'] },
];
export const MODES = { gray: 'Grayscale', color: 'Pseudocolor', seg: 'MRI + segmentation' };

const tool = (act, ic, label, pressed) =>
  `<button class="ibtn" type="button" data-act="${act}" aria-label="${label}" data-tip="${label}"${pressed == null ? '' : ` aria-pressed="${pressed}"`}>${icon(ic)}</button>`;

export function panelsHTML() {
  const slice = v => `<section class="view" data-view="${v.key}">
  <canvas class="slice" role="img" aria-label="${v.name} slice"></canvas>
  <header class="vhead"><div class="vtitle"><span class="vname">${v.name}</span><span class="pos"></span><span class="vbadge" hidden></span></div>
  <div class="vtools">${tool('zoom-out', 'zoom-out', 'Zoom out (−)')}${tool('zoom-in', 'zoom-in', 'Zoom in (+)')}${tool('fit', 'fit', 'Fit to panel (0)')}${tool('cross', 'cross', 'Crosshair (C)', true)}${tool('smooth', 'smooth', 'Smooth interpolation', true)}${tool('max', 'max', 'Maximize (F)', false)}</div></header>
  <footer class="vfoot"><input type="range" class="scrub" aria-label="${v.name} slice number" min="0" max="0" value="0"><span class="zlab">100%</span></footer>
</section>`;
  return `<div class="views" data-layout="grid">${VIEWS.map(slice).join('')}
<section class="view v3d" data-view="3d">
  <canvas class="gl" role="img" aria-label="3D volume rendering, drag to rotate"></canvas>
  <div class="glerr">The 3D view needs WebGL 2, which this browser or device does not provide. The slice views still work.</div>
  <header class="vhead"><div class="vtitle"><span class="vname">3D volume</span><span class="vbadge" hidden></span></div>
  <div class="vtools">
    <div class="seg xs" role="group" aria-label="3D rendering style"><button type="button" data-r3="solid" aria-pressed="true">Solid</button><button type="button" data-r3="glass" aria-pressed="false">Glass</button><button type="button" data-r3="natural" aria-pressed="false" data-tip="Translucent glowing look (illustrative colors)">Natural</button></div>
    <button class="ibtn txt" type="button" data-cam="left" aria-label="View from the left" data-tip="Left">L</button><button class="ibtn txt" type="button" data-cam="front" aria-label="View from the front" data-tip="Front">F</button><button class="ibtn txt" type="button" data-cam="top" aria-label="View from the top" data-tip="Top">T</button>${tool('cam-reset', 'reset', 'Reset camera')}
    ${tool('r3set', 'sliders', '3D settings', false)}${tool('max', 'max', 'Maximize (F)', false)}
  </div></header>
  <div class="pop r3pop" hidden>
    <div class="prow"><label>Threshold</label><input type="range" data-r3s="thr" min="1" max="60" value="12" aria-label="3D threshold"><output>12</output></div>
    <div class="prow"><label>Opacity</label><input type="range" data-r3s="opa" min="5" max="100" value="55" aria-label="3D opacity"><output>55</output></div>
    <div class="prow"><label>Shading</label><input type="range" data-r3s="shd" min="0" max="100" value="70" aria-label="3D shading"><output>70</output></div>
  </div>
  <footer class="vfoot"><label class="check sm"><input type="checkbox" class="switch" data-r3="cut" checked><span>Cut away at crosshair</span></label>
  <div class="tumcol" hidden><span>Tumor</span><div class="seg xs" role="group" aria-label="3D tumor color"><button type="button" data-r3t="labels" aria-pressed="true">Labels</button><button type="button" data-r3t="natural" aria-pressed="false" data-tip="Glowing orange (illustrative colors)">Natural</button></div></div><span class="hint">Drag to rotate · scroll to zoom</span></footer>
</section></div>`;
}

export class Viewer {
  constructor(root, { onCursor, keys = true } = {}) {
    this.root = root;
    if (!$('.views', root)) ($('[data-views-host]', root) || root).insertAdjacentHTML('beforeend', panelsHTML());
    this.grid = $('.views', root);
    this.onCursor = onCursor || (() => {});
    this.ls = {};
    this.state = {
      vol: null, seq: 't1', cursor: [0, 0, 0], home: [0, 0, 0], center: 0.5, width: 1.0, gamma: 1, lut: new Uint8Array(256),
      mode: 'gray', cmap: 'viridis', segBase: 'gray', segStyle: 'fill', regions: { 1: true, 2: true, 4: true },
      overlayOn: false, layTum: true, layUnc: false, ovA: 0.55, showCross: true,
    };
    this.rgb = new Uint32Array(256); this.rgbT = new Uint8Array(768);
    this.fade = { tum: 1, unc: 1 }; this.anims = new Map();
    this.layout = 'grid'; this.main = 'axial'; this.prevLayout = 'grid';
    this.views = VIEWS.map(v => ({ ...v, zoom: 1, pan: [0, 0], showX: true, smooth: true }));
    for (const v of this.views) {
      const el = $(`[data-view="${v.key}"]`, root);
      Object.assign(v, { el, canvas: $('canvas', el), pos: $('.pos', el), slider: $('input[type=range]', el), zlab: $('.zlab', el), badge: $('.vbadge', el) });
      v.ctx = v.canvas.getContext('2d');
      v.off = document.createElement('canvas'); v.offCtx = v.off.getContext('2d'); v.rect = null; v.drag = null;
      this.bindSliceView(v);
    }
    this.el3d = $('[data-view="3d"]', root);
    this.r3d = new Renderer3D($('canvas.gl', root), $('.glerr', root), () => this.state);
    this.r3d.bind(() => this.invalidate(false));
    this.r3d.onCamera = cam => this.emit('camera', cam);
    this.bind3dTools();
    this.raf = 0; this.needSlices = true; this.need3d = true; this.spaceDown = false;
    if (keys) this.bindKeys();
    const ro = new ResizeObserver(() => this.sizeCanvases());
    for (const el of root.querySelectorAll('.view')) ro.observe(el);
    this.buildLut();
  }

  on(ev, fn) { (this.ls[ev] = this.ls[ev] || []).push(fn); return this; }
  emit(ev, d) { for (const f of this.ls[ev] || []) f(d); }

  /* ------------------------------------------------------------ volume */
  setVolume(vol) {
    const st = this.state;
    st.vol = vol; st.seq = vol.order.includes(st.seq) ? st.seq : vol.order.includes('t1') ? 't1' : vol.order[0];
    const d = vol.seqs[vol.order.includes('flair') ? 'flair' : st.seq], { nx, ny, nz } = vol;
    let sxs = 0, sys = 0, szs = 0, n = 0, k = 0;
    const lo = [nx, ny, nz], hi = [-1, -1, -1];
    for (let z = 0; z < nz; z++) for (let y = 0; y < ny; y++) for (let x = 0; x < nx; x++, k++) if (d[k] > 0) {
      if (d[k] > 25) { sxs += x; sys += y; szs += z; n++; }
      if (x < lo[0]) lo[0] = x; if (x > hi[0]) hi[0] = x; if (y < lo[1]) lo[1] = y; if (y > hi[1]) hi[1] = y; if (z < lo[2]) lo[2] = z; if (z > hi[2]) hi[2] = z;
    }
    st.home = n ? [Math.round(sxs / n), Math.round(sys / n), Math.round(szs / n)] : [nx >> 1, ny >> 1, nz >> 1];
    st.cursor = st.home.slice();
    const m = 3, N = [nx, ny, nz];
    vol.bbox = hi[0] < 0 ? [0, nx - 1, 0, ny - 1, 0, nz - 1] : [0, 1, 2].flatMap(i => [Math.max(0, lo[i] - m), Math.min(N[i] - 1, hi[i] + m)]);
    for (const v of this.views) { v.zoom = 1; v.pan = [0, 0]; }
    this.setupGeometry(); this.buildLut();
    this.r3d.setVolume(vol, st.seq);
    this.sizeCanvases();
    this.updateBadges();
  }

  setOverlay(labels, unc) {
    const vol = this.state.vol; if (!vol) return;
    vol.labels = labels || null; vol.unc = unc || null;
    this.r3d.setTumor(vol.labels);
    this.updateBadges(); this.invalidate(true);
  }

  setSeq(k, { emit = true } = {}) {
    const st = this.state; if (!st.vol || !st.vol.seqs[k]) return;
    st.seq = k; this.r3d.uploadVolume(st.vol, k); this.invalidate(true);
    if (emit) this.emit('display', this.display());
  }

  setCursor(c, { emit = true, axis = null } = {}) {
    const v = this.state.vol; if (!v) return;
    this.state.cursor = [clamp(Math.round(c[0]), 0, v.nx - 1), clamp(Math.round(c[1]), 0, v.ny - 1), clamp(Math.round(c[2]), 0, v.nz - 1)];
    this.invalidate(true);
    if (emit) this.emit('cursor', { cursor: this.state.cursor.slice(), axis });
  }

  // Glide the crosshair to a target (programmatic jumps only; user input is immediate).
  flyTo(c, ms = 420) {
    const st = this.state; if (!st.vol) return;
    if (reducedMotion()) { this.setCursor(c); return; }
    const from = st.cursor.slice();
    this.tween('cursor', ms, k => this.setCursor(from.map((f, i) => f + (c[i] - f) * k), { emit: k >= 1 }));
  }

  setupGeometry() {
    const { nx, ny, nz, sx, sy, sz } = this.state.vol;
    const mk = (n, f) => Int32Array.from({ length: n }, (_, i) => f(i));
    const G = {
      axial: { W: nx, H: ny, mmW: nx * sx, mmH: ny * sy, n: nz,
        colOff: mk(nx, c => nx - 1 - c), rowOff: mk(ny, r => nx * (ny - 1 - r)), sliceOff: c => nx * ny * c[2],
        cross: c => [nx - 1 - c[0], ny - 1 - c[1]], pick: (col, row, c) => { c[0] = nx - 1 - col; c[1] = ny - 1 - row; } },
      coronal: { W: nx, H: nz, mmW: nx * sx, mmH: nz * sz, n: ny,
        colOff: mk(nx, c => nx - 1 - c), rowOff: mk(nz, r => nx * ny * (nz - 1 - r)), sliceOff: c => nx * c[1],
        cross: c => [nx - 1 - c[0], nz - 1 - c[2]], pick: (col, row, c) => { c[0] = nx - 1 - col; c[2] = nz - 1 - row; } },
      sagittal: { W: ny, H: nz, mmW: ny * sy, mmH: nz * sz, n: nx,
        colOff: mk(ny, c => nx * (ny - 1 - c)), rowOff: mk(nz, r => nx * ny * (nz - 1 - r)), sliceOff: c => c[0],
        cross: c => [ny - 1 - c[1], nz - 1 - c[2]], pick: (col, row, c) => { c[1] = ny - 1 - col; c[2] = nz - 1 - row; } },
    };
    for (const v of this.views) {
      Object.assign(v, G[v.key]);
      v.off.width = v.W; v.off.height = v.H;
      v.img = v.offCtx.createImageData(v.W, v.H); v.px = new Uint32Array(v.img.data.buffer);
      v.slider.max = v.n - 1;
    }
  }

  /* ------------------------------------------------------------ display */
  colorOn() { const st = this.state; return st.mode === 'color' || (st.mode === 'seg' && st.segBase === 'color'); }

  // Window/level and gamma give the display intensity of each stored value; the color
  // map (grayscale outside pseudocolor) turns it into RGB. Stored value 0 stays black.
  buildLut() {
    const st = this.state, lo = st.center - st.width / 2, g = st.gamma, T = this.rgbT;
    for (let i = 0; i < 256; i++) {
      let t = clamp((i / 255 - lo) / st.width, 0, 1);
      if (g !== 1) t = Math.pow(t, g);
      st.lut[i] = i === 0 ? 0 : Math.round(255 * t);
    }
    const table = cmapTable(this.colorOn() ? st.cmap : 'gray');
    for (let i = 0; i < 256; i++) { const j = st.lut[i] * 3; T[i * 3] = table[j]; T[i * 3 + 1] = table[j + 1]; T[i * 3 + 2] = table[j + 2]; }
    T[0] = T[1] = T[2] = 0;
    this.packRgb(T);
    this.r3d.setLut(this.colorOn() ? T : null);
  }

  packRgb(T) { const o = this.rgb; for (let i = 0; i < 256; i++) o[i] = 0xFF000000 | (T[i * 3 + 2] << 16) | (T[i * 3 + 1] << 8) | T[i * 3]; }

  // Rebuild the lookup table, cross-fading the slice colors when animate is set.
  retint(animate) {
    const prev = animate && !reducedMotion() && this.state.vol ? this.rgbT.slice() : null;
    this.buildLut();
    this.invalidate(true, true);
    if (!prev) return;
    const next = this.rgbT.slice(), mix = new Uint8Array(768);
    this.tween('lut', 300, k => { for (let i = 0; i < 768; i++) mix[i] = prev[i] + (next[i] - prev[i]) * k; this.packRgb(mix); this.invalidate(true, false); },
      () => { this.packRgb(next); this.invalidate(true, false); });
  }

  setMode(mode, { animate = true, emit = true } = {}) {
    const st = this.state, wasOn = st.overlayOn;
    st.mode = mode; st.overlayOn = mode === 'seg';
    if (st.overlayOn && !wasOn && animate && !reducedMotion()) {
      this.fade.tum = 0; this.fade.unc = 0;
      this.tween('fov', 260, k => { this.fade.tum = k; this.fade.unc = k; this.invalidate(true, false); });
    } else { this.fade.tum = 1; this.fade.unc = 1; }
    this.retint(animate);
    this.updateBadges();
    if (emit) this.emit('display', this.display());
  }

  setColormap(name, { animate = true, emit = true } = {}) { if (!CMAPS[name]) return; this.state.cmap = name; this.retint(animate); this.updateBadges(); if (emit) this.emit('display', this.display()); }
  setWindow(center, width, { emit = true } = {}) { this.state.center = center; this.state.width = width; this.buildLut(); this.invalidate(true); if (emit) this.emit('display', this.display()); }
  setGamma(g, { emit = true } = {}) { this.state.gamma = g; this.buildLut(); this.invalidate(true); if (emit) this.emit('display', this.display()); }
  setSegBase(b, { animate = true } = {}) { this.state.segBase = b; this.retint(animate); this.updateBadges(); this.emit('display', this.display()); }
  setSegStyle(s) { this.state.segStyle = s; this.invalidate(true, false); }
  setOpacity(a) { this.state.ovA = a; this.invalidate(true, false); }
  setRegion(label, on) { this.state.regions[label] = on; this.invalidate(true, true); }

  // Fade a layer ('tum' or 'unc') in or out.
  setLayer(name, on, { animate = true } = {}) {
    const st = this.state, key = name === 'tum' ? 'layTum' : 'layUnc';
    if (!animate || reducedMotion()) { st[key] = on; this.fade[name] = 1; this.invalidate(true, name === 'tum'); return; }
    if (on) {
      st[key] = true; this.fade[name] = 0; this.invalidate(false, true);
      this.tween('f' + name, 220, k => { this.fade[name] = k; this.invalidate(true, false); });
    } else {
      this.tween('f' + name, 180, k => { this.fade[name] = 1 - k; this.invalidate(true, false); }, () => { st[key] = false; this.fade[name] = 1; this.invalidate(true, true); });
    }
  }

  display() { const s = this.state; return { mode: s.mode, cmap: s.cmap, center: s.center, width: s.width, gamma: s.gamma, seq: s.seq, segBase: s.segBase }; }

  applyDisplay(d) {
    const s = this.state, modeChanged = d.mode !== s.mode;
    Object.assign(s, { cmap: d.cmap, center: d.center, width: d.width, gamma: d.gamma, segBase: d.segBase });
    if (d.seq && s.vol && s.vol.seqs[d.seq] && d.seq !== s.seq) this.setSeq(d.seq, { emit: false });
    if (modeChanged) this.setMode(d.mode, { emit: false }); else { this.retint(false); this.updateBadges(); }
  }

  updateBadges() {
    const s = this.state, txt = this.colorOn() ? 'Pseudocolor · ' + CMAPS[s.cmap].label : '';
    for (const b of this.root.querySelectorAll('.vbadge')) { b.textContent = txt; b.hidden = !txt; }
    if (!this.el3d || !this.r3d) return;
    const o = this.r3d.opts, tumShown = s.overlayOn && !!(s.vol && s.vol.labels);
    $('.tumcol', this.el3d).hidden = !tumShown;
    const tint = [o.natural && 'brain', o.tumorNatural && tumShown && 'tumor'].filter(Boolean);
    if (tint.length) {
      const b = $('.vbadge', this.el3d);
      b.textContent = 'Illustrative tint · ' + tint.join(' + '); b.hidden = false;
      b.title = 'MRI has no color. These tissue-like tones are a display choice, not measured from the scan.';
    }
  }

  /* ------------------------------------------------------------ painting */
  // Returns idx -> packed RGBA for the current display state. Outlines use the in-plane
  // neighbours of the view's axis, so the same shader works for any slice orientation.
  shader(axis) {
    const st = this.state, vol = st.vol, data = vol.seqs[st.seq], rgb = this.rgb;
    const lab = st.overlayOn && st.layTum && vol.labels && this.fade.tum > 0.002 ? vol.labels : null;
    const unc = st.overlayOn && st.layUnc && vol.unc && this.fade.unc > 0.002 ? vol.unc : null;
    if (!lab && !unc) return idx => rgb[data[idx]];
    const reg = st.regions, al = st.ovA * this.fade.tum, ua = Math.min(1, st.ovA * 1.5) * this.fade.unc;
    const outline = st.segStyle === 'outline', N = data.length, nx = vol.nx, nxy = vol.nx * vol.ny;
    const s1 = axis === 0 ? nx : 1, s2 = axis === 2 ? nx : nxy;
    const oa = Math.min(1, 0.45 + st.ovA) * this.fade.tum;
    const vis = l => (l && reg[l === 3 ? 4 : l] ? l : 0);
    return idx => {
      const p = rgb[data[idx]];
      let R = p & 255, G = (p >>> 8) & 255, B = (p >>> 16) & 255;
      if (lab) {
        const l = vis(lab[idx]);
        if (l) {
          let a = al;
          if (outline) {
            const edge = idx < s1 || vis(lab[idx - s1]) !== l || idx + s1 >= N || vis(lab[idx + s1]) !== l ||
              idx < s2 || vis(lab[idx - s2]) !== l || idx + s2 >= N || vis(lab[idx + s2]) !== l;
            a = edge ? oa : 0;
          }
          if (a > 0) { const c = SEG_COLORS[l]; R += (c[0] - R) * a; G += (c[1] - G) * a; B += (c[2] - B) * a; }
        }
      }
      if (unc) {
        const u = unc[idx];
        if (u > 8) { const a = Math.min(0.92, (u / 255) * 1.3) * ua, h = u * 3; R += (HEAT[h] - R) * a; G += (HEAT[h + 1] - G) * a; B += (HEAT[h + 2] - B) * a; }
      }
      return 0xFF000000 | ((B | 0) << 16) | ((G | 0) << 8) | (R | 0);
    };
  }

  paintSlice(v) {
    const so = v.sliceOff(this.state.cursor), px = v.px, f = this.shader(v.axis), W = v.W, H = v.H, co = v.colOff, ro = v.rowOff;
    let k = 0;
    for (let r = 0; r < H; r++) { const b = ro[r] + so; for (let c = 0; c < W; c++) px[k++] = f(b + co[c]); }
    v.offCtx.putImageData(v.img, 0, 0);
  }

  // Image placement inside the canvas for a view (fit * zoom, plus pan in mm).
  placement(v) {
    const c = v.canvas, cw = c.width, ch = c.height, dpr = cw / Math.max(1, c.clientWidth);
    const padT = 40 * dpr, padB = 38 * dpr, padX = 14 * dpr, aw = cw - 2 * padX, ah = ch - padT - padB;
    if (aw <= 0 || ah <= 0 || !v.W) return null;
    const fit = Math.min(aw / v.mmW, ah / v.mmH), scale = fit * v.zoom, dw = v.mmW * scale, dh = v.mmH * scale;
    const cx = cw / 2, cy = padT + ah / 2;
    return { ox: cx - dw / 2 + v.pan[0] * scale, oy: cy - dh / 2 + v.pan[1] * scale, dw, dh, scale, fit, dpr, cx, cy, padT, padB, padX, cw, ch };
  }

  drawView(v) {
    const c = v.canvas, ctx = v.ctx, cw = c.width, ch = c.height, st = this.state;
    ctx.fillStyle = PANEL_BG; ctx.fillRect(0, 0, cw, ch);
    if (!st.vol || !v.W || !cw) return;
    this.paintSlice(v);
    const P = this.placement(v); v.rect = P; if (!P) return;
    ctx.imageSmoothingEnabled = v.smooth; ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(v.off, 0, 0, v.W, v.H, P.ox, P.oy, P.dw, P.dh);
    drawOverlayMarks(ctx, v, P, v.cross(st.cursor), v.showX && st.showCross);
    if (v.zlab) v.zlab.textContent = Math.round(v.zoom * 100) + '%';
  }

  /* ------------------------------------------------------------ view transforms */
  emitView(v) { if (v.rect) this.emit('view', { key: v.key, zoom: v.zoom, pan: v.pan.slice(), pxPerMm: v.rect.fit * v.zoom / v.rect.dpr }); }

  zoomView(v, f, ax, ay) {
    const r = v.rect || this.placement(v); if (!r) return;
    const nz = clamp(v.zoom * f, ZMIN, ZMAX); if (nz === v.zoom) return;
    if (ax != null) {
      const mx = (ax - r.ox) / r.scale, my = (ay - r.oy) / r.scale, s2 = r.fit * nz;
      v.pan = [(ax - mx * s2 - r.cx + v.mmW * s2 / 2) / s2, (ay - my * s2 - r.cy + v.mmH * s2 / 2) / s2];
    }
    v.zoom = nz; v.rect = this.placement(v); this.invalidate(true, false); this.emitView(v);
  }

  fitView(v, { emit = true } = {}) { v.zoom = 1; v.pan = [0, 0]; v.rect = this.placement(v); this.invalidate(true, false); if (emit) this.emitView(v); }

  // Apply a transform from another viewer; pxPerMm keeps the physical scale equal.
  setViewTransform(key, { zoom, pan, pxPerMm }, { useZoom = true, usePan = true } = {}) {
    const v = this.views.find(w => w.key === key); if (!v) return;
    if (useZoom) {
      const r = v.rect || this.placement(v);
      v.zoom = clamp(pxPerMm && r ? pxPerMm / (r.fit / r.dpr) : zoom, ZMIN, ZMAX);
    }
    if (usePan) v.pan = pan.slice();
    v.rect = this.placement(v); this.invalidate(true, false);
  }

  setCrosshairs(on) { this.state.showCross = on; for (const v of this.views) { v.showX = on; v.el.querySelector('[data-act=cross]').setAttribute('aria-pressed', String(on)); } this.invalidate(true, false); }

  resetViews() {
    for (const v of this.views) this.fitView(v, { emit: false });
    if (this.state.vol) this.flyTo(this.state.home);
  }

  setLayout(layout, main = this.main) {
    if (layout !== 'single') this.prevLayout = layout;
    const views = [...this.grid.querySelectorAll('.view')];
    flip(views, () => {
      this.layout = layout; this.main = main;
      this.grid.dataset.layout = layout;
      for (const el of views) el.classList.toggle('is-main', el.dataset.view === main);
    });
    for (const el of views) {
      const b = el.querySelector('[data-act=max]'), on = layout === 'single' && el.dataset.view === main;
      b.setAttribute('aria-pressed', String(on)); b.innerHTML = icon(on ? 'min' : 'max');
      b.setAttribute('aria-label', on ? 'Restore layout' : 'Maximize (F)'); b.dataset.tip = on ? 'Restore layout' : 'Maximize (F)';
    }
    this.sizeCanvases();
    this.emit('layout', { layout, main });
  }

  toggleMax(key) {
    if (this.layout === 'single' && this.main === key) this.setLayout(this.prevLayout === 'single' ? 'grid' : this.prevLayout, key);
    else this.setLayout('single', key);
  }

  /* ------------------------------------------------------------ interaction */
  bindSliceView(v) {
    const c = v.canvas;
    const at = e => { const r = c.getBoundingClientRect(), d = c.width / r.width; return [(e.clientX - r.left) * d, (e.clientY - r.top) * d]; };
    const set = e => {
      if (!this.state.vol || !v.rect) return;
      const [x, y] = at(e), { ox, oy, dw, dh } = v.rect;
      v.pick(clamp(Math.floor((x - ox) / dw * v.W), 0, v.W - 1), clamp(Math.floor((y - oy) / dh * v.H), 0, v.H - 1), this.state.cursor);
      this.invalidate(true);
      this.emit('cursor', { cursor: this.state.cursor.slice(), axis: null });
    };
    c.addEventListener('pointerdown', e => {
      if (!this.state.vol) return;
      const pan = e.button === 1 || e.button === 2 || e.shiftKey || this.spaceDown;
      if (e.button > 2) return;
      c.setPointerCapture(e.pointerId); v.drag = pan ? 'pan' : 'cross'; v.last = at(e);
      c.classList.toggle('panning', pan);
      if (!pan) set(e);
      c.focus({ preventScroll: true });
      e.preventDefault();
    });
    c.addEventListener('pointermove', e => {
      if (v.drag === 'cross') set(e);
      else if (v.drag === 'pan' && v.rect) {
        const p = at(e); v.pan[0] += (p[0] - v.last[0]) / v.rect.scale; v.pan[1] += (p[1] - v.last[1]) / v.rect.scale; v.last = p;
        v.rect = this.placement(v); this.invalidate(true, false); this.emitView(v);
      }
    });
    const end = () => { v.drag = null; c.classList.remove('panning'); };
    c.addEventListener('pointerup', end); c.addEventListener('pointercancel', end);
    c.addEventListener('contextmenu', e => e.preventDefault());
    c.addEventListener('dblclick', () => this.fitView(v));
    let acc = 0;
    c.addEventListener('wheel', e => {
      e.preventDefault(); if (!this.state.vol) return;
      if (e.ctrlKey || e.metaKey) { const [x, y] = at(e); this.zoomView(v, Math.exp(-e.deltaY * 0.0022), x, y); return; }
      const dy = e.deltaMode === 1 ? e.deltaY * 40 : e.deltaY;
      if (Math.abs(dy) >= 50) { this.step(v, dy < 0 ? 1 : -1); acc = 0; return; }
      acc += dy; if (Math.abs(acc) >= 50) { this.step(v, acc < 0 ? 1 : -1); acc = 0; }
    }, { passive: false });
    v.slider.addEventListener('input', () => { this.state.cursor[v.axis] = +v.slider.value; this.invalidate(true); this.emit('cursor', { cursor: this.state.cursor.slice(), axis: v.axis }); });
    c.tabIndex = 0;
    c.addEventListener('keydown', e => {
      const k = e.key;
      if (k === 'ArrowUp' || k === 'PageUp') { this.step(v, 1); e.preventDefault(); }
      else if (k === 'ArrowDown' || k === 'PageDown') { this.step(v, -1); e.preventDefault(); }
      else if (k === '+' || k === '=') { this.zoomView(v, 1.25); e.preventDefault(); }
      else if (k === '-' || k === '_') { this.zoomView(v, 0.8); e.preventDefault(); }
      else if (k === '0') { this.fitView(v); e.preventDefault(); }
      else if (k === 'c' || k === 'C') { this.toggleCross(v); e.preventDefault(); }
      else if (k === 'f' || k === 'F') { this.toggleMax(v.key); e.preventDefault(); }
    });
    v.el.querySelector('.vtools').addEventListener('click', e => {
      const b = e.target.closest('[data-act]'); if (!b) return;
      const a = b.dataset.act;
      if (a === 'zoom-in') this.zoomView(v, 1.25);
      if (a === 'zoom-out') this.zoomView(v, 0.8);
      if (a === 'fit') this.fitView(v);
      if (a === 'cross') this.toggleCross(v);
      if (a === 'smooth') { v.smooth = !v.smooth; b.setAttribute('aria-pressed', String(v.smooth)); this.invalidate(true, false); }
      if (a === 'max') this.toggleMax(v.key);
    });
  }

  toggleCross(v) { v.showX = !v.showX; v.el.querySelector('[data-act=cross]').setAttribute('aria-pressed', String(v.showX)); this.invalidate(true, false); }

  step(v, d) {
    this.state.cursor[v.axis] = clamp(this.state.cursor[v.axis] + d, 0, v.n - 1);
    this.invalidate(true);
    this.emit('cursor', { cursor: this.state.cursor.slice(), axis: v.axis });
  }

  bind3dTools() {
    const el = this.el3d, r = this.r3d, pop = $('.r3pop', el);
    el.querySelector('.vtools').addEventListener('click', e => {
      const b = e.target.closest('button'); if (!b) return;
      if (b.dataset.r3 === 'solid' || b.dataset.r3 === 'glass' || b.dataset.r3 === 'natural') this.setStyle3d(b.dataset.r3);
      if (b.dataset.cam) this.flyCam(b.dataset.cam);
      if (b.dataset.act === 'cam-reset') this.flyCam('reset');
      if (b.dataset.act === 'max') this.toggleMax('3d');
      if (b.dataset.act === 'r3set') { pop.hidden = !pop.hidden; b.setAttribute('aria-pressed', String(!pop.hidden)); }
    });
    const opts = r.opts, out = {
      thr: v => { opts.thresh = v / 100 * 0.6; }, opa: v => { opts.opacity = v / 100; }, shd: v => { opts.shade = v / 100; },
    };
    for (const inp of el.querySelectorAll('[data-r3s]')) {
      inp.addEventListener('input', () => { inp.nextElementSibling.textContent = inp.value; out[inp.dataset.r3s](+inp.value); r.interact(); this.invalidate(false); });
    }
    $('[data-r3=cut]', el).addEventListener('change', e => { opts.cut = e.target.checked; this.invalidate(false); });
    $('.tumcol', el).addEventListener('click', e => { const b = e.target.closest('[data-r3t]'); if (b) this.setTumorColor3d(b.dataset.r3t); });
  }

  style3d() { const o = this.r3d.opts; return o.natural ? 'natural' : o.glass ? 'glass' : 'solid'; }

  // 3D brain style: 'solid', 'glass' (edge shell) or 'natural' (translucent glow, illustrative tissue tint).
  setStyle3d(k) {
    const o = this.r3d.opts, el = this.el3d;
    o.glass = k === 'glass'; o.natural = k === 'natural';
    for (const b of el.querySelectorAll('.vtools [data-r3]')) b.setAttribute('aria-pressed', String(b.dataset.r3 === k));
    $('[data-r3=cut]', el).disabled = k !== 'solid'; this.updateBadges(); this.invalidate(false);
  }

  // 3D tumor color: 'labels' (region colors, as in the slices) or 'natural' (illustrative orange glow).
  setTumorColor3d(k) {
    this.r3d.opts.tumorNatural = k === 'natural';
    for (const b of this.el3d.querySelectorAll('[data-r3t]')) b.setAttribute('aria-pressed', String(b.dataset.r3t === k));
    this.updateBadges(); this.invalidate(false);
  }

  // Mode switches call this: keep a chosen Natural style, otherwise toggle Solid/Glass.
  setGlass(g) { if (this.style3d() !== 'natural') this.setStyle3d(g ? 'glass' : 'solid'); }

  flyCam(k) {
    const r = this.r3d, to = r.presetCam(k);
    if (reducedMotion()) { Object.assign(r.cam, to); this.invalidate(false); this.emit('camera', r.cam); return; }
    const from = { ...r.cam }, tau = 2 * Math.PI;
    const dphi = ((to.phi - from.phi) % tau + tau + Math.PI) % tau - Math.PI;
    this.tween('cam', 560, k2 => {
      r.cam.phi = from.phi + dphi * k2; r.cam.theta = from.theta + (to.theta - from.theta) * k2; r.cam.dist = from.dist + (to.dist - from.dist) * k2;
      r.interact(); this.invalidate(false); this.emit('camera', r.cam);
    });
  }

  setCamera(cam) { Object.assign(this.r3d.cam, cam); this.r3d.interact(); this.invalidate(false); }

  bindKeys() {
    // Keyboard: 1/2/3 focus axial/coronal/sagittal; Space + drag pans.
    window.addEventListener('keydown', e => {
      if (e.key === ' ' && e.target && e.target.classList && e.target.classList.contains('slice')) { this.spaceDown = true; e.preventDefault(); return; }
      if (e.target && /INPUT|TEXTAREA|SELECT|BUTTON/.test(e.target.tagName)) return;
      const i = ['1', '2', '3'].indexOf(e.key);
      if (i >= 0 && !e.ctrlKey && !e.metaKey && !e.altKey) this.views[i].canvas.focus();
    });
    window.addEventListener('keyup', e => { if (e.key === ' ') this.spaceDown = false; });
  }

  /* ------------------------------------------------------------ loop */
  tween(key, ms, step, done) {
    const prev = this.anims.get(key); if (prev) cancelAnimationFrame(prev);
    const t0 = performance.now();
    const tick = now => {
      const k = Math.min(1, (now - t0) / ms); step(ease(k));
      if (k < 1) this.anims.set(key, requestAnimationFrame(tick)); else { this.anims.delete(key); if (done) done(); }
    };
    this.anims.set(key, requestAnimationFrame(tick));
  }

  invalidate(slices = true, three = true) {
    if (slices) this.needSlices = true;
    if (three) this.need3d = true;
    if (!this.raf) this.raf = requestAnimationFrame(() => this.frame(false));
  }

  // frame() draws everything; the animation loop calls frame(false) to draw only what changed.
  frame(force = true) {
    this.raf = 0; if (!this.state.vol) return;
    const changed = force || this.needSlices || this.need3d;
    if (force || this.needSlices) { for (const v of this.views) if (force || v.el.offsetParent !== null) this.drawView(v); this.needSlices = false; }
    if (force || this.need3d) { this.r3d.render(); this.need3d = false; } else this.r3d.refine();
    if (this.r3d.pending() && !this.raf) this.raf = requestAnimationFrame(() => this.frame(false));
    if (changed) this.updateReadouts();
  }

  readout() {
    const st = this.state, v = st.vol, c = st.cursor, idx = c[0] + v.nx * (c[1] + v.ny * c[2]);
    return {
      canonical: c.slice(), original: v.toOrig(c[0], c[1], c[2]), signal: v.seqs[st.seq][idx], world: v.hasWorld ? toWorld(v, c) : null,
      label: v.labels ? v.labels[idx] : null, labelName: v.labels ? (v.labels[idx] ? SEG_NAMES[v.labels[idx]] : 'No tumor') : null,
      unc: v.unc ? v.unc[idx] / 255 : null,
    };
  }

  updateReadouts() {
    const st = this.state;
    for (const w of this.views) { w.slider.value = st.cursor[w.axis]; paintRange(w.slider); w.pos.textContent = (st.cursor[w.axis] + 1) + ' / ' + w.n; }
    this.onCursor(this.readout());
  }

  sizeCanvases() {
    for (const v of this.views) {
      const d = Math.min(window.devicePixelRatio || 1, 2), w = Math.round(v.canvas.clientWidth * d), h = Math.round(v.canvas.clientHeight * d);
      if (v.canvas.width !== w || v.canvas.height !== h) { v.canvas.width = w; v.canvas.height = h; }
      if (v.W) v.rect = this.placement(v);
    }
    this.r3d.size();
    this.invalidate(true);
  }
}

// Crosshair, orientation letters and a physical scale bar, drawn over a slice image.
export function drawOverlayMarks(ctx, v, P, cr, showCross) {
  const { ox, oy, dw, dh, dpr, padT, padB, padX, cw, ch, scale } = P;
  if (showCross && cr) {
    const x = ox + (cr[0] + 0.5) / v.W * dw, y = oy + (cr[1] + 0.5) / v.H * dh, gap = 8 * dpr;
    ctx.save(); ctx.beginPath(); ctx.rect(Math.max(ox, 0), Math.max(oy, 0), Math.min(dw, cw), Math.min(dh, ch)); ctx.clip();
    ctx.strokeStyle = 'rgba(240,179,79,.82)'; ctx.lineWidth = Math.max(1, dpr); ctx.beginPath();
    ctx.moveTo(x, oy); ctx.lineTo(x, y - gap); ctx.moveTo(x, y + gap); ctx.lineTo(x, oy + dh);
    ctx.moveTo(ox, y); ctx.lineTo(x - gap, y); ctx.moveTo(x + gap, y); ctx.lineTo(ox + dw, y);
    ctx.stroke(); ctx.restore();
  }
  ctx.fillStyle = 'rgba(214,224,234,.62)';
  ctx.font = '600 ' + 11 * dpr + 'px "Segoe UI Variable Text","Segoe UI",system-ui,-apple-system,Roboto,sans-serif';
  ctx.textBaseline = 'middle'; ctx.textAlign = 'left'; ctx.fillText(v.letters[0], padX, padT + (ch - padT - padB) / 2);
  ctx.textAlign = 'right'; ctx.fillText(v.letters[1], cw - padX, padT + (ch - padT - padB) / 2);
  ctx.textAlign = 'center'; ctx.fillText(v.letters[2], cw / 2, padT + 2 * dpr); ctx.fillText(v.letters[3], cw / 2, ch - padB - 2 * dpr);
  // scale bar, bottom left: the largest round length that fits in 80 CSS pixels
  const mmPx = scale, opts = [1, 2, 5, 10, 20, 50, 100];
  let len = opts[0]; for (const o of opts) if (o * mmPx <= 80 * dpr) len = o;
  const L = len * mmPx; if (L < 20 * dpr || cw < 220 * dpr) return;
  const bx = padX + 2 * dpr, by = ch - padB - 4 * dpr;
  ctx.strokeStyle = 'rgba(214,224,234,.55)'; ctx.lineWidth = Math.max(1, dpr); ctx.beginPath();
  ctx.moveTo(bx, by - 3 * dpr); ctx.lineTo(bx, by); ctx.lineTo(bx + L, by); ctx.lineTo(bx + L, by - 3 * dpr); ctx.stroke();
  ctx.font = '500 ' + 10 * dpr + 'px ui-monospace,"Cascadia Mono","SF Mono",Consolas,monospace';
  ctx.textAlign = 'left'; ctx.fillStyle = 'rgba(214,224,234,.6)'; ctx.fillText(len + ' mm', bx + L + 6 * dpr, by - 1 * dpr);
}
