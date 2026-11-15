// Voxel <-> world (scanner millimetres) mapping for canonical RAS volumes, and the
// checks that decide whether two scans can be synchronized or compared voxel by voxel.
// vol.affine is the 4x4 canonical-index -> world matrix (rows), as written by
// btqc.data.convert.bundle_meta; vol.hasWorld is false when a local file has no
// qform or sform, in which case there are no physical coordinates to sync through.

export function axisCodes(perm, flip) {
  return [0, 1, 2].map(a => (flip[a] ? 'LPI' : 'RAS')[perm[a]]).join('');
}

// Affine of the canonical grid, from the file affine A (3x4) and the orienter's toOrig.
export function canonicalAffine(A, toOrig) {
  const w = c => { const o = toOrig(c[0], c[1], c[2]); return [0, 1, 2].map(r => A[r][0] * o[0] + A[r][1] * o[1] + A[r][2] * o[2] + A[r][3]); };
  const o = w([0, 0, 0]), e = [w([1, 0, 0]), w([0, 1, 0]), w([0, 0, 1])];
  return [0, 1, 2].map(r => [e[0][r] - o[r], e[1][r] - o[r], e[2][r] - o[r], o[r]]).concat([[0, 0, 0, 1]]);
}

// The single-file export crops volumes; index c in the crop is c + off in the full grid.
export function shiftAffine(A, off) {
  if (!A) return null;
  return A.map((r, i) => i === 3 ? r.slice() : [r[0], r[1], r[2], r[3] + r[0] * off[0] + r[1] * off[1] + r[2] * off[2]]);
}

function invert(A) {
  const [a, b, c] = [A[0], A[1], A[2]];
  const m = [
    [b[1] * c[2] - b[2] * c[1], a[2] * c[1] - a[1] * c[2], a[1] * b[2] - a[2] * b[1]],
    [b[2] * c[0] - b[0] * c[2], a[0] * c[2] - a[2] * c[0], a[2] * b[0] - a[0] * b[2]],
    [b[0] * c[1] - b[1] * c[0], a[1] * c[0] - a[0] * c[1], a[0] * b[1] - a[1] * b[0]],
  ];
  const det = a[0] * m[0][0] + a[1] * m[1][0] + a[2] * m[2][0];
  if (Math.abs(det) < 1e-12) return null;
  const R = m.map(r => r.map(v => v / det)), t = [a[3], b[3], c[3]];
  return R.map(r => [r[0], r[1], r[2], -(r[0] * t[0] + r[1] * t[1] + r[2] * t[2])]);
}

export function toWorld(vol, c) {
  const A = vol.affine; if (!A) return null;
  return [0, 1, 2].map(r => A[r][0] * c[0] + A[r][1] * c[1] + A[r][2] * c[2] + A[r][3]);
}

export function toVoxel(vol, w) {
  if (!vol.affine) return null;
  if (!vol.invAffine) vol.invAffine = invert(vol.affine);
  const I = vol.invAffine; if (!I) return null;
  return [0, 1, 2].map(r => I[r][0] * w[0] + I[r][1] * w[1] + I[r][2] * w[2] + I[r][3]);
}

// Nearest voxel of b at the physical position of voxel c of a; null when outside b or no world coordinates.
export function mapVoxel(a, b, c) {
  if (!a.hasWorld || !b.hasWorld) return null;
  const w = toWorld(a, c), v = w && toVoxel(b, w);
  if (!v) return null;
  const r = v.map(Math.round);
  if (r[0] < 0 || r[1] < 0 || r[2] < 0 || r[0] >= b.nx || r[1] >= b.ny || r[2] >= b.nz) return null;
  return r;
}

const near = (x, y, tol) => Math.abs(x - y) <= tol;

// level: 'identical' (same grid, voxel-by-voxel comparison allowed), 'world' (sync through
// physical coordinates), 'none' (no physical coordinates on at least one side).
export function compareGeometry(a, b) {
  const sameDims = a.nx === b.nx && a.ny === b.ny && a.nz === b.nz;
  const sameSpacing = near(a.sx, b.sx, 1e-3) && near(a.sy, b.sy, 1e-3) && near(a.sz, b.sz, 1e-3);
  const world = !!(a.hasWorld && b.hasWorld && a.affine && b.affine);
  const sameAffine = world && a.affine.every((r, i) => r.every((v, j) => near(v, b.affine[i][j], 1e-3)));
  const notes = [];
  if (!sameDims) notes.push(`Dimensions differ (${a.nx}×${a.ny}×${a.nz} vs ${b.nx}×${b.ny}×${b.nz}).`);
  if (!sameSpacing) notes.push('Voxel spacing differs.');
  if (world && !sameAffine && sameDims && sameSpacing) notes.push('Same grid size but a different position in space.');
  if (!world) notes.push('At least one scan has no physical coordinates (no qform or sform), so synchronization is unavailable.');
  const level = sameDims && sameSpacing && sameAffine ? 'identical' : world ? 'world' : 'none';
  return { level, sameDims, sameSpacing, sameAffine, world, notes };
}
