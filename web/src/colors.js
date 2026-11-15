// Display colors. Necrotic core red, enhancing tumor yellow, edema green (BraTS 1/2/4).
export const SEG_COLORS = { 1: [229, 72, 77], 2: [46, 189, 89], 3: [242, 204, 58], 4: [242, 204, 58] };
export const SEG_NAMES = { 1: 'Necrotic core', 2: 'Edema', 3: 'Enhancing tumor', 4: 'Enhancing tumor' };
// Regions the user can toggle; label 3 (BraTS 2021+ enhancing) is shown as 4.
export const SEG_REGIONS = [[1, 'Necrotic core', 'NCR', '#e5484d'], [2, 'Edema', 'ED', '#2ebd59'], [4, 'Enhancing tumor', 'ET', '#f2cc3a']];
export const SEQ_LABELS = { t1: 'T1', t1ce: 'T1ce', t2: 'T2', flair: 'FLAIR', scan: 'Unknown' };
export const SEQ_FULL = {
  t1: 'T1-weighted', t1ce: 'T1-weighted, contrast-enhanced', t2: 'T2-weighted', flair: 'T2-FLAIR', scan: 'Unknown sequence',
};

// Uncertainty colormap: dark purple -> magenta -> orange -> pale yellow (256 x RGB).
export const HEAT = (() => {
  const stops = [[0, 60, 20, 110], [0.35, 160, 35, 140], [0.6, 235, 70, 90], [0.8, 255, 150, 40], [1, 255, 235, 120]];
  const out = new Uint8Array(256 * 3);
  for (let i = 0; i < 256; i++) {
    const t = i / 255; let a = stops[0], b = stops[stops.length - 1];
    for (let s = 0; s < stops.length - 1; s++) if (t >= stops[s][0] && t <= stops[s + 1][0]) { a = stops[s]; b = stops[s + 1]; break; }
    const f = (t - a[0]) / Math.max(1e-6, b[0] - a[0]);
    for (let c = 0; c < 3; c++) out[i * 3 + c] = Math.round(a[c + 1] + (b[c + 1] - a[c + 1]) * f);
  }
  return out;
})();
