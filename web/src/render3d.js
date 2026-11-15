// WebGL 2 ray-casting volume renderer (refactored from the prototype).
// Front-to-back compositing, per-pixel random start offset, gradient shading
// with a head light, cut-away octant at the crosshair, glass-brain shell, and
// a softened RGBA tumor texture (R core, G edema, B enhancing). Optional color
// lookup table (pseudocolor display), per-region tumor visibility, and a lower
// resolution while the view is being dragged (full resolution once idle). Once idle,
// extra passes with a new ray offset and sub-pixel jitter are blended into the frame
// (progressive refinement), which removes the sampling grain and smooths edges.
// The "natural" brain and tumor tints are illustrative only: MRI has no color,
// so they map the windowed intensity (or the label) to tissue-like tones.
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
export const CAM_DEFAULT = { phi: -0.7, theta: 0.32, dist: 2.4 };

const VS = `#version 300 es
out vec2 vNdc;
void main(){ vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2)); vNdc = p * 2.0 - 1.0; gl_Position = vec4(vNdc, 0.0, 1.0); }`;
const FS = `#version 300 es
precision highp float; precision highp sampler3D;
uniform sampler3D uVol; uniform sampler3D uTum; uniform sampler2D uLut;
uniform vec3 uCam, uFwd, uRight, uUp, uExt, uTexel, uCutPos, uBMin, uBMax, uReg; uniform vec2 uJit;
uniform float uTanHalf, uAspect, uStep, uVox, uThresh, uDensity, uShade, uWinLo, uWinHi, uCutOn, uTumOn, uGlass, uLutOn, uNat, uTumNat, uSeed;
in vec2 vNdc; out vec4 outColor;
float hash(vec2 p){ vec3 q = fract(vec3(p.xyx) * 0.1031); q += dot(q, q.yzx + 33.33); return fract((q.x + q.y) * q.z); }
float solidAt(vec3 q){ vec4 v = texture(uTum, q); return max(v.r * uReg.x, v.b * uReg.z); }
vec3 lutAt(float s){ return texture(uLut, vec2(s * (255.0 / 256.0) + 0.5 / 256.0, 0.5)).rgb; }
float maskAt(vec3 q){ return smoothstep(uThresh, uThresh + 0.03, texture(uVol, q).r); }
// Illustrative tissue tint: darker rose-gray for low signal, pale cream for high.
vec3 tissue(float g){ return mix(vec3(0.86, 0.56, 0.50), vec3(1.0, 0.90, 0.84), smoothstep(0.2, 0.85, g)); }
void main(){
  vec2 ndc = vNdc + uJit;
  vec3 rd = normalize(uFwd + ndc.x * uAspect * uTanHalf * uRight + ndc.y * uTanHalf * uUp);
  vec3 sd = vec3(rd.x == 0.0 ? 1e-6 : rd.x, rd.y == 0.0 ? 1e-6 : rd.y, rd.z == 0.0 ? 1e-6 : rd.z);
  vec3 inv = 1.0 / sd, ta = (uBMin - uCam) * inv, tb = (uBMax - uCam) * inv;
  vec3 tmin = min(ta, tb), tmax = max(ta, tb);
  float tn = max(max(tmin.x, tmin.y), max(tmin.z, 0.0)), tf = min(min(tmax.x, tmax.y), tmax.z);
  vec3 col = vec3(0.0); float acc = 0.0;
  vec3 EDEMA = uTumNat > 0.5 ? vec3(1.0, 0.52, 0.12) * 1.4 : vec3(0.18, 0.74, 0.35);
  if (tf > tn) {
    float t = tn + uStep * fract(hash(gl_FragCoord.xy) + uSeed);
    vec3 side = sign(uCam - uCutPos);
    float stepK = uStep / uVox;
    bool afterCut = false;
    for (int i = 0; i < 1100; i++) {
      if (t > tf || acc > 0.985) break;
      vec3 p = uCam + rd * t;
      bool cut = false;
      if (uCutOn > 0.5) { vec3 d = (p - uCutPos) * side; cut = (d.x > 0.0 && d.y > 0.0 && d.z > 0.0); }
      if (cut) { afterCut = true; t += uStep; continue; }
      vec3 uvw = p / uExt + 0.5;
      float s = texture(uVol, uvw).r;
      float a = smoothstep(uThresh, uThresh + 0.03, s);
      vec3 cB = vec3(0.0); float aB = 0.0;
      if (a > 0.0) {
        float g = clamp((s - uWinLo) / max(uWinHi - uWinLo, 1e-4), 0.0, 1.0);
        if (afterCut) { cB = uLutOn > 0.5 ? lutAt(s) : vec3(g); aB = a > 0.15 ? 1.0 : a; }
        else {
          vec3 e = uTexel * 3.0;
          vec3 gr = vec3(
            texture(uVol, uvw + vec3(e.x, 0.0, 0.0)).r - texture(uVol, uvw - vec3(e.x, 0.0, 0.0)).r,
            texture(uVol, uvw + vec3(0.0, e.y, 0.0)).r - texture(uVol, uvw - vec3(0.0, e.y, 0.0)).r,
            texture(uVol, uvw + vec3(0.0, 0.0, e.z)).r - texture(uVol, uvw - vec3(0.0, 0.0, e.z)).r);
          float gm = length(gr), dif = 1.0, lit = 1.0, spec = 0.0;
          if (gm > 1e-4) {
            vec3 n = -gr / gm; float sw = uShade * smoothstep(0.0, 0.08, gm);
            dif = max(dot(n, -rd), 0.0); lit = mix(1.0, 0.3 + 0.9 * dif, sw); spec = pow(dif, 28.0) * 0.28 * sw;
          }
          if (uGlass > 0.5) {
            vec3 e3 = uTexel * 2.0;
            vec3 gk = vec3(maskAt(uvw + vec3(e3.x, 0.0, 0.0)) - maskAt(uvw - vec3(e3.x, 0.0, 0.0)),
                           maskAt(uvw + vec3(0.0, e3.y, 0.0)) - maskAt(uvw - vec3(0.0, e3.y, 0.0)),
                           maskAt(uvw + vec3(0.0, 0.0, e3.z)) - maskAt(uvw - vec3(0.0, 0.0, e3.z)));
            float gkm = length(gk), dk = 0.5;
            if (gkm > 1e-4) { dk = max(dot(-gk / gkm, -rd), 0.0); }
            if (uNat > 0.5) {
              // Translucent "illustration" look: glowing rim at grazing angles, folds from the
              // intensity gradient, bright signal glowing cream from inside.
              float edge = smoothstep(0.15, 0.7, gkm), rim = pow(1.0 - dk, 3.0) * edge;
              float fold = smoothstep(0.04, 0.2, gm) * (1.0 - dif), wm = smoothstep(0.55, 0.9, g);
              float sh = edge * 0.05 + rim * 0.09 + fold * 0.045 + a * 0.002 + wm * a * 0.012;
              aB = 1.0 - pow(1.0 - min(sh, 0.6), stepK);
              cB = tissue(g) * (0.62 + 0.55 * dk) * mix(1.0, lit, 0.5) + vec3(1.0, 0.30, 0.16) * rim * 1.2 + vec3(1.0, 0.86, 0.74) * wm * 0.45;
            } else {
              float sh = smoothstep(0.15, 0.7, gkm) * 0.05;
              aB = 1.0 - pow(1.0 - sh, stepK); cB = vec3(0.70, 0.78, 0.86) * (0.35 + 0.65 * dk);
            }
          } else {
            cB = (uLutOn > 0.5 ? max(lutAt(s), vec3(0.05)) : vec3(max(g, 0.55))) * lit + spec; aB = 1.0 - pow(1.0 - clamp(uDensity * a, 0.0, 0.999), stepK);
          }
        }
      }
      float aT = 0.0, aE = 0.0; vec3 cT = vec3(0.0);
      if (uTumOn > 0.5) {
        vec4 tm = texture(uTum, uvw) * vec4(uReg, 1.0);
        float ts = smoothstep(0.30, 0.60, max(tm.r, tm.b));
        float coreW = clamp(tm.r / (tm.r + tm.b + 1e-3), 0.0, 1.0);
        vec3 solidCol = uTumNat > 0.5 ? mix(vec3(1.0, 0.72, 0.22) * 1.5, vec3(1.0, 0.36, 0.08) * 1.3, coreW)
                                      : mix(vec3(0.96, 0.80, 0.22), vec3(0.90, 0.27, 0.30), coreW);
        if (uGlass > 0.5) {
          float shd = 1.0;
          if (ts > 0.02) {
            vec3 e2 = uTexel * 2.0;
            vec3 gt = vec3(solidAt(uvw + vec3(e2.x, 0.0, 0.0)) - solidAt(uvw - vec3(e2.x, 0.0, 0.0)),
                           solidAt(uvw + vec3(0.0, e2.y, 0.0)) - solidAt(uvw - vec3(0.0, e2.y, 0.0)),
                           solidAt(uvw + vec3(0.0, 0.0, e2.z)) - solidAt(uvw - vec3(0.0, 0.0, e2.z)));
            float gl2 = length(gt); if (gl2 > 1e-4) { vec3 n2 = -gt / gl2; shd = 0.4 + 0.6 * max(dot(n2, -rd), 0.0); }
          }
          cT = uTumNat > 0.5 ? solidCol * (0.75 + 0.75 * shd) : solidCol * shd;
          aT = 1.0 - pow(1.0 - ts * 0.6, stepK); aE = 1.0 - pow(1.0 - tm.g * (uTumNat > 0.5 ? 0.13 : 0.045), stepK);
        } else {
          cB = mix(cB, EDEMA, tm.g * 0.5 * (1.0 - ts)); cB = mix(cB, solidCol, ts * 0.9);
        }
      }
      if (aB > 0.0) { col += (1.0 - acc) * aB * cB; acc += (1.0 - acc) * aB; }
      if (aE > 0.0) { col += (1.0 - acc) * aE * EDEMA; acc += (1.0 - acc) * aE; }
      if (aT > 0.0) { col += (1.0 - acc) * aT * cT; acc += (1.0 - acc) * aT; }
      afterCut = false;
      t += uStep;
    }
  }
  if (uNat > 0.5) {
    // warm backdrop and a soft tone curve so the bright parts glow instead of clipping
    vec3 bg = mix(vec3(0.22, 0.07, 0.04), vec3(0.015, 0.008, 0.006), smoothstep(0.0, 1.2, length(vNdc * vec2(uAspect * 0.8, 1.0))));
    col = 1.0 - exp(-(col + (1.0 - acc) * bg) * 1.35);
  }
  outColor = vec4(col, 1.0);
}`;

const UNIFORMS = ['uVol', 'uTum', 'uLut', 'uLutOn', 'uReg', 'uCam', 'uFwd', 'uRight', 'uUp', 'uExt', 'uTexel', 'uCutPos', 'uBMin', 'uBMax', 'uTanHalf', 'uAspect', 'uStep', 'uVox', 'uThresh', 'uDensity', 'uShade', 'uWinLo', 'uWinHi', 'uCutOn', 'uTumOn', 'uGlass', 'uNat', 'uTumNat', 'uSeed', 'uJit'];
const cross3 = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const norm3 = a => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };

function boxBlur(a, w, h, d) {
  const tmp = new Float32Array(a.length);
  const pass = (src, dst, stride, len, outer1, s1, outer2, s2) => {
    for (let o2 = 0; o2 < outer2; o2++) for (let o1 = 0; o1 < outer1; o1++) {
      const base = o1 * s1 + o2 * s2;
      for (let i = 0; i < len; i++) {
        const p = base + i * stride, m = i > 0 ? src[p - stride] : 0, n = i < len - 1 ? src[p + stride] : 0;
        dst[p] = (m + src[p] + n) / 3;
      }
    }
  };
  pass(a, tmp, 1, w, h, w, d, w * h); pass(tmp, a, w, h, w, 1, d, w * h); pass(a, tmp, w * h, d, w, 1, h, w); a.set(tmp);
}

export class Renderer3D {
  constructor(canvas, errEl, getState, { maxDpr = 1.5, lowRes = 0.55 } = {}) {
    this.canvas = canvas; this.errEl = errEl; this.getState = getState; this.ok = false;
    this.opts = { cut: true, glass: false, natural: false, tumorNatural: false, thresh: 0.072, opacity: 0.55, shade: 0.7, tumor: true, stepScale: 1 };
    this.cam = { ...CAM_DEFAULT };
    this.tumBuilt = false; this.dims = null; this.lutOn = false;
    this.maxDpr = maxDpr; this.lowRes = lowRes; this.resScale = 1; this.idleT = 0;
    this.onCamera = null; this.onIdle = null;
    this.samples = 0; this.maxSamples = 10; this.tPass = 0;
    if (!canvas) return;
    const gl = canvas.getContext('webgl2', { antialias: false, alpha: false, powerPreference: 'high-performance', preserveDrawingBuffer: true });
    if (!gl) { this.fail(); return; }
    const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; };
    try {
      const pr = gl.createProgram();
      gl.attachShader(pr, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, FS)); gl.linkProgram(pr);
      if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(pr));
      this.pr = pr; this.u = {};
      for (const n of UNIFORMS) this.u[n] = gl.getUniformLocation(pr, n);
      this.vao = gl.createVertexArray(); this.tex = gl.createTexture(); this.tum = gl.createTexture(); this.lut = gl.createTexture();
      this.gl = gl; this.ok = true;
      gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
      this.emptyTumor(); this.setLut(null);
      canvas.addEventListener('webglcontextlost', e => { e.preventDefault(); this.fail(); });
    } catch (err) { console.warn('3D view disabled:', err.message); this.fail(); }
  }

  fail() { this.ok = false; if (this.errEl) this.errEl.style.display = 'flex'; }

  texParams() {
    const gl = this.gl;
    gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    for (const w of [gl.TEXTURE_WRAP_S, gl.TEXTURE_WRAP_T, gl.TEXTURE_WRAP_R]) gl.texParameteri(gl.TEXTURE_3D, w, gl.CLAMP_TO_EDGE);
  }

  emptyTumor() {
    const gl = this.gl; gl.bindTexture(gl.TEXTURE_3D, this.tum);
    gl.texImage3D(gl.TEXTURE_3D, 0, gl.RGBA8, 1, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(4)); this.texParams();
    this.tumBuilt = false;
  }

  // table: 256 x RGB uint8 indexed by the stored intensity (window, gamma and color map
  // already applied), or null for the original grayscale shading.
  setLut(table) {
    if (!this.ok) return;
    const gl = this.gl, rgba = new Uint8Array(1024);
    if (table) for (let i = 0; i < 256; i++) { rgba[i * 4] = table[i * 3]; rgba[i * 4 + 1] = table[i * 3 + 1]; rgba[i * 4 + 2] = table[i * 3 + 2]; rgba[i * 4 + 3] = 255; }
    gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D, this.lut);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, 256, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, rgba);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.activeTexture(gl.TEXTURE0);
    this.lutOn = !!table;
  }

  setVolume(vol, seq) { this.dims = null; if (this.ok) { this.emptyTumor(); this.uploadVolume(vol, seq); } }

  uploadVolume(vol, seq) {
    if (!this.ok || !vol) return;
    const gl = this.gl, { nx, ny, nz } = vol, data = vol.seqs[seq];
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1); gl.bindTexture(gl.TEXTURE_3D, this.tex);
    const key = nx + ',' + ny + ',' + nz;
    if (this.dims === key) gl.texSubImage3D(gl.TEXTURE_3D, 0, 0, 0, 0, nx, ny, nz, gl.RED, gl.UNSIGNED_BYTE, data);
    else { gl.texImage3D(gl.TEXTURE_3D, 0, gl.R8, nx, ny, nz, 0, gl.RED, gl.UNSIGNED_BYTE, data); this.texParams(); this.dims = key; }
  }

  setTumor(L) {
    if (!this.ok) return;
    const vol = this.getState().vol;
    if (!L) { this.emptyTumor(); return; }
    const { nx, ny, nz } = vol, pad = 5;
    let lo = [nx, ny, nz], hi = [-1, -1, -1], k = 0;
    for (let z = 0; z < nz; z++) for (let y = 0; y < ny; y++) for (let x = 0; x < nx; x++, k++) if (L[k]) {
      if (x < lo[0]) lo[0] = x; if (x > hi[0]) hi[0] = x; if (y < lo[1]) lo[1] = y; if (y > hi[1]) hi[1] = y; if (z < lo[2]) lo[2] = z; if (z > hi[2]) hi[2] = z;
    }
    if (hi[0] < 0) { this.emptyTumor(); return; }
    const N = [nx, ny, nz];
    lo = lo.map(v => Math.max(0, v - pad)); hi = hi.map((v, i) => Math.min(N[i] - 1, v + pad));
    const w = hi[0] - lo[0] + 1, h = hi[1] - lo[1] + 1, d = hi[2] - lo[2] + 1;
    const ch = [new Float32Array(w * h * d), new Float32Array(w * h * d), new Float32Array(w * h * d)], map = { 1: 0, 2: 1, 3: 2, 4: 2 };
    for (let z = 0; z < d; z++) for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const l = L[(x + lo[0]) + nx * ((y + lo[1]) + ny * (z + lo[2]))];
      if (l && map[l] !== undefined) ch[map[l]][x + w * (y + h * z)] = 1;
    }
    for (const c of ch) { boxBlur(c, w, h, d); boxBlur(c, w, h, d); }
    const rgba = new Uint8Array(nx * ny * nz * 4);
    for (let z = 0; z < d; z++) for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const s = x + w * (y + h * z), o = ((x + lo[0]) + nx * ((y + lo[1]) + ny * (z + lo[2]))) * 4;
      rgba[o] = Math.round(ch[0][s] * 255); rgba[o + 1] = Math.round(ch[1][s] * 255); rgba[o + 2] = Math.round(ch[2][s] * 255);
    }
    const gl = this.gl; gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1); gl.bindTexture(gl.TEXTURE_3D, this.tum);
    gl.texImage3D(gl.TEXTURE_3D, 0, gl.RGBA8, nx, ny, nz, 0, gl.RGBA, gl.UNSIGNED_BYTE, rgba); this.texParams();
    this.tumBuilt = true;
  }

  size() {
    if (!this.canvas) return;
    const g = this.canvas, d = Math.min(window.devicePixelRatio || 1, this.maxDpr) * this.resScale;
    const w = Math.max(1, Math.round(g.clientWidth * d)), h = Math.max(1, Math.round(g.clientHeight * d));
    if (g.width !== w || g.height !== h) { g.width = w; g.height = h; }
  }

  // Drop to a lower resolution while the user drags or zooms; restore when idle.
  interact() {
    if (this.resScale !== this.lowRes) { this.resScale = this.lowRes; this.size(); }
    clearTimeout(this.idleT);
    this.idleT = setTimeout(() => { this.resScale = 1; this.size(); if (this.onIdle) this.onIdle(); }, 180);
  }

  // Fresh frame: one pass, then refine() adds passes while nothing changes.
  render() { this.samples = 0; this.pass(); }

  // More passes are worth drawing only at full resolution (not while dragging).
  pending() { return this.ok && this.samples > 0 && this.samples < this.maxSamples && this.resScale === 1; }

  refine() { if (this.pending()) this.pass(); }

  pass() {
    const st = this.getState();
    if (!this.ok || !st.vol) return;
    const gl = this.gl, c = this.canvas, w = c.width, h = c.height, o = this.opts;
    if (!w || !h || !c.clientWidth) return;
    const { nx, ny, nz, sx, sy, sz } = st.vol;
    const mm = [nx * sx, ny * sy, nz * sz], mx = Math.max(...mm), ext = mm.map(v => v / mx);
    const n3 = [nx, ny, nz], bb = st.vol.bbox;
    const bmin = [0, 1, 2].map(i => (bb[2 * i] / n3[i] - 0.5) * ext[i]);
    const bmax = [0, 1, 2].map(i => ((bb[2 * i + 1] + 1) / n3[i] - 0.5) * ext[i]);
    const ctr = [0, 1, 2].map(i => (bmin[i] + bmax[i]) / 2), bs = Math.max(bmax[0] - bmin[0], bmax[1] - bmin[1], bmax[2] - bmin[2]);
    const vox = Math.min(sx, sy, sz) / mx, diag = Math.hypot(bmax[0] - bmin[0], bmax[1] - bmin[1], bmax[2] - bmin[2]);
    const step = Math.max(vox * 0.7, diag / 1000) * o.stepScale * (this.resScale < 1 ? 1.5 : 1);
    const { phi, theta, dist } = this.cam, D = dist * bs;
    const dir = [Math.cos(theta) * Math.sin(phi), Math.cos(theta) * Math.cos(phi), Math.sin(theta)];
    const pos = [ctr[0] + D * dir[0], ctr[1] + D * dir[1], ctr[2] + D * dir[2]];
    const fwd = norm3([-dir[0], -dir[1], -dir[2]]), right = norm3(cross3(fwd, [0, 0, 1])), up = cross3(right, fwd);
    const cp = [0, 1, 2].map(i => ((st.cursor[i] + 0.5) / n3[i] - 0.5) * ext[i]);
    const lo = st.center - st.width / 2, density = 0.05 + 0.95 * o.opacity * 0.8;
    const tumorOn = st.overlayOn && st.layTum && this.tumBuilt;
    const reg = st.regions || { 1: true, 2: true, 4: true };
    gl.viewport(0, 0, w, h); gl.useProgram(this.pr); gl.bindVertexArray(this.vao);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_3D, this.tex);
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_3D, this.tum);
    gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D, this.lut);
    const u = this.u;
    gl.uniform1i(u.uVol, 0); gl.uniform1i(u.uTum, 1); gl.uniform1i(u.uLut, 2);
    gl.uniform3fv(u.uCam, pos); gl.uniform3fv(u.uFwd, fwd); gl.uniform3fv(u.uRight, right); gl.uniform3fv(u.uUp, up);
    gl.uniform3fv(u.uExt, ext); gl.uniform3fv(u.uBMin, bmin); gl.uniform3fv(u.uBMax, bmax);
    gl.uniform3f(u.uTexel, 1 / nx, 1 / ny, 1 / nz); gl.uniform3fv(u.uCutPos, cp);
    gl.uniform1f(u.uTanHalf, Math.tan(15 * Math.PI / 180)); gl.uniform1f(u.uAspect, w / h);
    gl.uniform1f(u.uStep, step); gl.uniform1f(u.uVox, vox);
    gl.uniform1f(u.uThresh, o.thresh); gl.uniform1f(u.uDensity, density); gl.uniform1f(u.uShade, o.shade);
    gl.uniform1f(u.uWinLo, lo); gl.uniform1f(u.uWinHi, lo + st.width);
    const clear = o.glass || o.natural;
    gl.uniform1f(u.uCutOn, o.cut && !clear ? 1 : 0);
    gl.uniform1f(u.uTumOn, tumorOn ? 1 : 0); gl.uniform1f(u.uGlass, clear ? 1 : 0);
    gl.uniform1f(u.uNat, o.natural ? 1 : 0); gl.uniform1f(u.uTumNat, o.tumorNatural ? 1 : 0);
    gl.uniform1f(u.uLutOn, this.lutOn ? 1 : 0);
    gl.uniform3f(u.uReg, reg[1] ? 1 : 0, reg[2] ? 1 : 0, reg[4] ? 1 : 0);
    // Pass n is blended in with weight 1/(n+1), giving the running mean of all passes.
    const n = this.samples, R = [0.5, 0.25, 0.75, 0.125, 0.625, 0.375, 0.875, 0.0625, 0.5625, 0.3125];
    gl.uniform1f(u.uSeed, n ? (n * 0.618034) % 1 : 0);
    gl.uniform2f(u.uJit, n ? (R[n % 10] - 0.5) * 2 / w : 0, n ? (R[(n * 3 + 1) % 10] - 0.5) * 2 / h : 0);
    if (n) { gl.enable(gl.BLEND); gl.blendFunc(gl.CONSTANT_ALPHA, gl.ONE_MINUS_CONSTANT_ALPHA); gl.blendColor(0, 0, 0, 1 / (n + 1)); }
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    if (n) gl.disable(gl.BLEND);
    // Passes arriving slowly (software rendering, no GPU): stop early to stay responsive.
    const now = performance.now();
    if (!n) this.maxSamples = 10; else if (n >= 3 && now - this.tPass > 120) this.maxSamples = n + 1;
    this.tPass = now; this.samples = n + 1;
    gl.activeTexture(gl.TEXTURE0);
  }

  bind(invalidate) {
    const c = this.canvas; if (!c) return;
    this.onIdle = this.onIdle || invalidate;
    const ptrs = new Map(); let lastPinch = 0;
    const moved = () => { this.interact(); invalidate(); if (this.onCamera) this.onCamera(this.cam); };
    c.addEventListener('pointerdown', e => { c.setPointerCapture(e.pointerId); ptrs.set(e.pointerId, [e.clientX, e.clientY]); lastPinch = 0; c.classList.add('grabbing'); });
    c.addEventListener('pointermove', e => {
      if (!ptrs.has(e.pointerId)) return;
      const prev = ptrs.get(e.pointerId); ptrs.set(e.pointerId, [e.clientX, e.clientY]);
      if (ptrs.size === 1) { this.cam.phi += (e.clientX - prev[0]) * 0.008; this.cam.theta = clamp(this.cam.theta + (e.clientY - prev[1]) * 0.008, -1.5, 1.5); }
      else if (ptrs.size === 2) { const [a, b] = [...ptrs.values()], d = Math.hypot(a[0] - b[0], a[1] - b[1]); if (lastPinch) this.cam.dist = clamp(this.cam.dist * lastPinch / d, 1.3, 5); lastPinch = d; }
      moved();
    });
    const end = e => { ptrs.delete(e.pointerId); lastPinch = 0; if (!ptrs.size) c.classList.remove('grabbing'); };
    c.addEventListener('pointerup', end); c.addEventListener('pointercancel', end);
    c.addEventListener('wheel', e => { e.preventDefault(); this.cam.dist = clamp(this.cam.dist * Math.exp(e.deltaY * 0.0012), 1.3, 5); moved(); }, { passive: false });
  }

  presetCam(k) {
    if (k === 'front') return { phi: 0, theta: 0.1, dist: CAM_DEFAULT.dist };
    if (k === 'left') return { phi: -Math.PI / 2, theta: 0.1, dist: CAM_DEFAULT.dist };
    if (k === 'top') return { phi: 0, theta: 1.5, dist: CAM_DEFAULT.dist };
    return { ...CAM_DEFAULT };
  }

  preset(k) { Object.assign(this.cam, this.presetCam(k)); }
}
