// NIfTI-1 reader and RAS reorientation (refactored from the prototype viewer).
// The reorientation rule matches src/btqc/data/orient.py exactly: for each voxel
// axis pick the world axis it is most aligned with (permutation maximizing the
// sum of absolute affine entries) and that entry's sign.

const DTYPES = { 2: ['u8', 1], 4: ['i16', 2], 8: ['i32', 4], 16: ['f32', 4], 64: ['f64', 8], 256: ['i8', 1], 512: ['u16', 2], 768: ['u32', 4] };
const CTORS = { u8: Uint8Array, i8: Int8Array, i16: Int16Array, u16: Uint16Array, i32: Int32Array, u32: Uint32Array, f32: Float32Array, f64: Float64Array };

export class NiftiError extends Error {}

export async function gunzip(buf) {
  if (typeof DecompressionStream === 'undefined') {
    throw new NiftiError('This browser cannot open .gz files. Unzip the file first, or use a current version of Chrome, Edge, Firefox or Safari.');
  }
  const stream = new Blob([buf]).stream().pipeThrough(new DecompressionStream('gzip'));
  return await new Response(stream).arrayBuffer();
}

export const isGzip = buf => { const h = new Uint8Array(buf, 0, Math.min(2, buf.byteLength)); return h[0] === 0x1f && h[1] === 0x8b; };

export async function parseNifti(buf, name = 'file') {
  if (isGzip(buf)) buf = await gunzip(buf);
  if (buf.byteLength < 352) throw new NiftiError(name + ' is too small to be a NIfTI file.');
  const dv = new DataView(buf);
  let le = true, hdr = dv.getInt32(0, true);
  if (hdr !== 348) { hdr = dv.getInt32(0, false); le = false; }
  if (hdr !== 348) {
    if (dv.getInt32(0, true) === 540 || dv.getInt32(0, false) === 540) throw new NiftiError(name + ' is NIfTI-2, which this viewer cannot read yet.');
    throw new NiftiError(name + ' is not a NIfTI file. Use .nii or .nii.gz.');
  }
  const i16 = o => dv.getInt16(o, le), f32 = o => dv.getFloat32(o, le);
  const ndim = i16(40), nx = i16(42), ny = i16(44), nz = i16(46);
  if (ndim < 3 || nx < 1 || ny < 1 || nz < 2) throw new NiftiError(name + ' is not a 3D volume.');
  const dt = DTYPES[i16(70)];
  if (!dt) throw new NiftiError(name + ' uses a data type this viewer does not support (code ' + i16(70) + ').');
  const px = []; for (let i = 0; i < 8; i++) px.push(f32(76 + 4 * i));
  const voff = Math.round(f32(108));
  let slope = f32(112), inter = f32(116);
  if (!isFinite(slope) || slope === 0) { slope = 1; inter = 0; }
  if (!isFinite(inter)) inter = 0;
  const n = nx * ny * nz, bytes = dt[1];
  if (voff < 352 || voff + n * bytes > buf.byteLength) throw new NiftiError(name + ' looks truncated or damaged.');
  let raw;
  const part = buf.slice(voff, voff + n * bytes);
  if (le || bytes === 1) raw = new CTORS[dt[0]](part);
  else {
    const d2 = new DataView(part); raw = new Float64Array(n);
    const get = { i16: 'getInt16', u16: 'getUint16', i32: 'getInt32', u32: 'getUint32', f32: 'getFloat32', f64: 'getFloat64' }[dt[0]];
    for (let i = 0; i < n; i++) raw[i] = d2[get](i * bytes, false);
  }
  const qcode = i16(252), scode = i16(254);
  let A;
  if (scode > 0) {
    A = [[f32(280), f32(284), f32(288), f32(292)], [f32(296), f32(300), f32(304), f32(308)], [f32(312), f32(316), f32(320), f32(324)]];
  } else if (qcode > 0) {
    let b = f32(256), c = f32(260), d = f32(264), a = 1 - (b * b + c * c + d * d);
    if (a < 1e-7) { const s = 1 / (Math.hypot(b, c, d) || 1); b *= s; c *= s; d *= s; a = 0; } else a = Math.sqrt(a);
    const qf = px[0] < 0 ? -1 : 1;
    const R = [
      [a * a + b * b - c * c - d * d, 2 * (b * c - a * d), 2 * (b * d + a * c)],
      [2 * (b * c + a * d), a * a + c * c - b * b - d * d, 2 * (c * d - a * b)],
      [2 * (b * d - a * c), 2 * (c * d + a * b), a * a + d * d - b * b - c * c],
    ];
    A = R.map((r, i) => [r[0] * px[1], r[1] * px[2], r[2] * px[3] * qf, f32(268 + 4 * i)]);
  } else {
    A = [[px[1] || 1, 0, 0, 0], [0, px[2] || 1, 0, 0], [0, 0, px[3] || 1, 0]];
  }
  return { name, dims: [nx, ny, nz], raw, slope, inter, affine: A, hasWorld: scode > 0 || qcode > 0 };
}

// 1st-99th percentile of nonzero voxels -> 1..255, exact zero stays 0 (same as the Python bundles).
export function rawToU8(raw, slope, inter) {
  const n = raw.length, step = Math.max(1, Math.floor(n / 250000)), s = [];
  for (let i = 0; i < n; i += step) { const v = raw[i] * slope + inter; if (v !== 0 && isFinite(v)) s.push(v); }
  if (s.length < 50) for (let i = 0; i < n; i += step) { const v = raw[i] * slope + inter; if (isFinite(v)) s.push(v); }
  const arr = Float32Array.from(s).sort();
  let lo = arr[Math.floor(arr.length * 0.01)] || 0, hi = arr[Math.floor(arr.length * 0.99)] || 1;
  if (!(hi > lo)) hi = lo + 1;
  const out = new Uint8Array(n), k = 254 / (hi - lo);
  for (let i = 0; i < n; i++) {
    const v = raw[i] * slope + inter;
    out[i] = v === 0 || !isFinite(v) ? 0 : v <= lo ? 1 : v >= hi ? 255 : (1 + (v - lo) * k + 0.5) | 0;
  }
  return out;
}

export function rawToLabels(raw, slope, inter) {
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) { const v = Math.round(raw[i] * slope + inter); out[i] = v > 0 && v < 256 ? v : 0; }
  return out;
}

// Reorder voxels so index = x + nx*(y + ny*z): x to the patient's right, y anterior, z superior.
export function makeOrienter(dims, A) {
  const cols = [0, 1, 2].map(j => [A[0][j], A[1][j], A[2][j]]);
  const perms = [[0, 1, 2], [0, 2, 1], [1, 0, 2], [1, 2, 0], [2, 0, 1], [2, 1, 0]];
  let best = perms[0], bs = -1;
  for (const p of perms) { let s = 0; for (let a = 0; a < 3; a++) s += Math.abs(cols[a][p[a]]); if (s > bs + 1e-12) { bs = s; best = p; } }
  const flip = [0, 1, 2].map(a => cols[a][best[a]] < 0);
  const sp = [1, 1, 1];
  for (let a = 0; a < 3; a++) sp[best[a]] = Math.hypot(cols[a][0], cols[a][1], cols[a][2]) || 1;
  return orienterFromPermFlip(dims, best, flip, sp);
}

// perm[a] = world axis of original voxel axis a; flip[a] = axis runs against it. Mirrors orient.py.
export function orienterFromPermFlip(dims, perm, flip, sp = [1, 1, 1]) {
  const inv = [0, 0, 0], nd = [1, 1, 1];
  for (let a = 0; a < 3; a++) { inv[perm[a]] = a; nd[perm[a]] = dims[a]; }
  const stride = [1, dims[0], dims[0] * dims[1]];
  const offs = [0, 1, 2].map(w => {
    const a = inv[w], arr = new Int32Array(nd[w]);
    for (let o = 0; o < nd[w]; o++) arr[o] = (flip[a] ? dims[a] - 1 - o : o) * stride[a];
    return arr;
  });
  const apply = src => {
    const out = new src.constructor(nd[0] * nd[1] * nd[2]), [ox, oy, oz] = offs; let k = 0;
    for (let z = 0; z < nd[2]; z++) { const bz = oz[z]; for (let y = 0; y < nd[1]; y++) { const b = bz + oy[y]; for (let x = 0; x < nd[0]; x++) out[k++] = src[b + ox[x]]; } }
    return out;
  };
  const toOrig = (x, y, z) => { const c = [x, y, z], r = [0, 0, 0]; for (let a = 0; a < 3; a++) { const w = perm[a]; r[a] = flip[a] ? dims[a] - 1 - c[w] : c[w]; } return r; };
  const fromOrig = (i, j, k) => { const v = [i, j, k], r = [0, 0, 0]; for (let a = 0; a < 3; a++) { const w = perm[a]; r[w] = flip[a] ? dims[a] - 1 - v[a] : v[a]; } return r; };
  return { apply, nd, sp, toOrig, fromOrig, perm, flip, dims };
}

// Guess the sequence of a file from its name (prototype rule).
export function roleOf(name) {
  const n = name.toLowerCase().replace(/\.gz$/, '').replace(/\.nii$/, '');
  if (/seg|mask|label|(^|[_\-. ])gt([_\-. ]|$)/.test(n)) return 'seg';
  if (/flair/.test(n)) return 'flair';
  if (/t1ce|t1c|t1gd|t1[_\-. ]?(ce|gd|post|contrast)|gad/.test(n)) return 't1ce';
  if (/t2/.test(n)) return 't2';
  if (/t1/.test(n)) return 't1';
  return null;
}

export const isNiftiName = name => /\.nii(\.gz)?$/i.test(name);
