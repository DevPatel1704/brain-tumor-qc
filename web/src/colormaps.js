// Intensity-to-color transfer functions for the pseudocolor display mode. They
// act on the windowed display intensity only; voxel values are never modified.
// viridis / inferno / plasma: degree-6 polynomial fits of the matplotlib maps
// (Matt Zucker); turbo: Google's polynomial approximation; cool-to-warm:
// Moreland's diverging map, piecewise-linear between its published key points.
const clamp01 = v => v < 0 ? 0 : v > 1 ? 1 : v;

const poly6 = C => t => [0, 1, 2].map(ch => {
  let v = C[6][ch];
  for (let i = 5; i >= 0; i--) v = C[i][ch] + t * v;
  return clamp01(v);
});

const viridis = poly6([
  [0.2777273272234177, 0.005407344544966578, 0.3340998053353061], [0.1050930431085774, 1.404613529898575, 1.384590162594685],
  [-0.3308618287255563, 0.214847559468213, 0.09509516302823659], [-4.634230498983486, -5.799100973351585, -19.33244095627987],
  [6.228269936347081, 14.17993336680509, 56.69055260068105], [4.776384997670288, -13.74514537774601, -65.35303263337234],
  [-5.435455855934631, 4.645852612178535, 26.3124352495832]]);
const plasma = poly6([
  [0.05873234392399702, 0.02333670892565664, 0.5433401826748754], [2.176514634195958, 0.2383834171260182, 0.7539604599784036],
  [-2.689460476458034, -7.455851135738909, 3.110799939717086], [6.130348345893603, 42.3461881477227, -28.51885465332158],
  [-11.10743619062271, -82.66631109428045, 60.13984767418263], [10.02306557647065, 71.41361770095349, -54.07218655560067],
  [-3.658713842777788, -22.93153465461149, 18.19190778539828]]);
const inferno = poly6([
  [0.0002189403691192265, 0.001651004631001012, -0.01948089843709184], [0.1065134194856116, 0.5639564367884091, 3.932712388889277],
  [11.60249308247187, -3.972853965665698, -15.9423941062914], [-41.70399613139459, 17.43639888205313, 44.35414519872813],
  [77.162935699427, -33.40235894210092, -81.80730925738993], [-71.31942824499214, 32.62606426397723, 73.20951985803202],
  [25.13112622477341, -12.24266895238567, -23.07032500287172]]);

function turbo(t) {
  const x = clamp01(t), x2 = x * x, x3 = x2 * x, x4 = x2 * x2, x5 = x4 * x;
  return [
    0.13572138 + 4.61539260 * x - 42.66032258 * x2 + 132.13108234 * x3 - 152.94239396 * x4 + 59.28637943 * x5,
    0.09140261 + 2.19418839 * x + 4.84296658 * x2 - 14.18503333 * x3 + 4.27729857 * x4 + 2.82956604 * x5,
    0.10667330 + 12.64194608 * x - 60.58204836 * x2 + 110.36276771 * x3 - 89.90310912 * x4 + 27.34824973 * x5,
  ].map(clamp01);
}

const COOLWARM = [[0, 59, 76, 192], [0.125, 98, 130, 234], [0.25, 141, 176, 254], [0.375, 184, 208, 249], [0.5, 221, 221, 221],
  [0.625, 245, 196, 173], [0.75, 244, 154, 123], [0.875, 222, 96, 77], [1, 180, 4, 38]];
function coolwarm(t) {
  const x = clamp01(t);
  for (let i = 0; i < COOLWARM.length - 1; i++) {
    const a = COOLWARM[i], b = COOLWARM[i + 1];
    if (x <= b[0]) { const f = (x - a[0]) / (b[0] - a[0]); return [1, 2, 3].map(c => (a[c] + (b[c] - a[c]) * f) / 255); }
  }
  return [180 / 255, 4 / 255, 38 / 255];
}

export const CMAPS = {
  gray: { label: 'Grayscale', fn: t => [t, t, t], note: 'Original intensity mapping' },
  viridis: { label: 'Viridis', fn: viridis, note: 'Perceptually uniform, colorblind-safe' },
  inferno: { label: 'Inferno', fn: inferno, note: 'Perceptually uniform, high dynamic range' },
  plasma: { label: 'Plasma', fn: plasma, note: 'Perceptually uniform, bright mid-tones' },
  turbo: { label: 'Turbo', fn: turbo, note: 'Rainbow-like; not perceptually uniform' },
  coolwarm: { label: 'Cool to warm', fn: coolwarm, note: 'Diverging around the window center' },
};
export const CMAP_ORDER = ['gray', 'viridis', 'inferno', 'plasma', 'turbo', 'coolwarm'];

const cache = {};
// 256 x RGB (uint8) table for one map.
export function cmapTable(name) {
  if (cache[name]) return cache[name];
  const fn = (CMAPS[name] || CMAPS.gray).fn, out = new Uint8Array(768);
  for (let i = 0; i < 256; i++) { const c = fn(i / 255); for (let k = 0; k < 3; k++) out[i * 3 + k] = Math.round(c[k] * 255); }
  return (cache[name] = out);
}

export function cmapGradient(name, stops = 12) {
  const t = cmapTable(name), parts = [];
  for (let i = 0; i <= stops; i++) { const j = Math.round(i / stops * 255) * 3; parts.push(`rgb(${t[j]},${t[j + 1]},${t[j + 2]}) ${(i / stops * 100).toFixed(1)}%`); }
  return `linear-gradient(90deg, ${parts.join(', ')})`;
}
