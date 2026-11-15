// Data sources: the FastAPI backend (ApiSource) or data embedded in the
// single-file export (EmbeddedSource). Both return canonical RAS uint8 volumes.
import { axisCodes, canonicalAffine, shiftAffine } from './geometry.js';
import { gunzip, makeOrienter, orienterFromPermFlip, parseNifti, rawToLabels, rawToU8, roleOf, isNiftiName, NiftiError } from './nifti.js';

const SEQS = ['t1', 't1ce', 't2', 'flair'];
const b64bytes = s => { const bin = atob(s), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; };

export async function getJSON(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) { let msg = r.status + ' ' + r.statusText; try { msg = (await r.json()).detail || msg; } catch (_) { /* not json */ } throw new Error(msg); }
  return r.json();
}

async function fetchBundle(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error('Could not load ' + url + ' (' + r.status + ')');
  const meta = JSON.parse(r.headers.get('X-Btqc-Meta') || '{}');
  const data = new Uint8Array(await gunzip(await r.arrayBuffer()));
  return { meta, data };
}

export function volumeFromBundles(caseId, seqs, metas, label) {
  const m = metas[Object.keys(metas)[0]], [nx, ny, nz] = m.dims, sp = m.spacing;
  const oo = m.original_orientation;
  const ori = orienterFromPermFlip(oo.shape, oo.perm, oo.flip, sp);
  const order = SEQS.filter(k => seqs[k]);
  // single-file export crops volumes to the brain box; the offset keeps file indices exact
  const off = m.crop_offset || [0, 0, 0];
  const windows = {};
  for (const [k, mm] of Object.entries(metas)) if (mm.kind === k && mm.window) windows[k] = mm.window;
  return {
    id: caseId, nx, ny, nz, sx: sp[0], sy: sp[1], sz: sp[2], seqs, order, labels: null, unc: null,
    rawDims: oo.shape, toOrig: (x, y, z) => ori.toOrig(x + off[0], y + off[1], z + off[2]),
    fromOrig: (i, j, k) => { const c = ori.fromOrig(i, j, k); return [c[0] - off[0], c[1] - off[1], c[2] - off[2]]; },
    label: label || caseId,
    affine: shiftAffine(m.affine, off), hasWorld: !!m.affine, origAxes: axisCodes(oo.perm, oo.flip),
    seqSource: 'dataset', windows, cropped: !!m.crop_offset,
  };
}

// BraTS 1/2/3 reference masks are shown with the 1/2/4 colors.
const normLabels = (data, conv) => { if (conv === 'brats_123') for (let i = 0; i < data.length; i++) if (data[i] === 3) data[i] = 4; return data; };

export class ApiSource {
  constructor(base = '') { this.base = base; this.kind = 'api'; }
  cases(limit) { return getJSON(this.base + '/api/cases' + (limit != null ? '?review_limit=' + limit : '')); }
  health() { return getJSON(this.base + '/api/health'); }
  thumbUrl(caseId) { return `${this.base}/api/cases/${encodeURIComponent(caseId)}/thumbnail`; }
  // Sequences load in parallel; onProgress(text, fraction).
  async volume(caseId, onProgress, list = SEQS) {
    const seqs = {}, metas = {}; let done = 0;
    if (onProgress) onProgress(`Loading ${list.length} sequences…`, 0);
    await Promise.all(list.map(async s => {
      const b = await fetchBundle(`${this.base}/api/cases/${encodeURIComponent(caseId)}/volume/${s}`);
      seqs[s] = b.data; metas[s] = b.meta; done++;
      if (onProgress) onProgress(`Loaded ${s.toUpperCase()} (${done} of ${list.length})`, done / list.length);
    }));
    return volumeFromBundles(caseId, seqs, metas);
  }
  // One sequence only (home page render).
  async single(caseId, seq) {
    const b = await fetchBundle(`${this.base}/api/cases/${encodeURIComponent(caseId)}/volume/${seq}`);
    return volumeFromBundles(caseId, { [seq]: b.data }, { [seq]: b.meta });
  }
  async reference(caseId) {
    try { const b = await fetchBundle(`${this.base}/api/cases/${encodeURIComponent(caseId)}/volume/seg`); return normLabels(b.data, b.meta.labels); } catch (_) { return null; }
  }
  async prediction(caseId, limit) {
    let info;
    try { info = await getJSON(`${this.base}/api/cases/${encodeURIComponent(caseId)}/prediction` + (limit != null ? '?review_limit=' + limit : '')); }
    catch (_) { return null; }
    const [lab, unc] = await Promise.all([fetchBundle(this.base + info.labels_url), fetchBundle(this.base + info.uncertainty_url)]);
    return { info, labels: lab.data, unc: unc.data };
  }
  evalSummary() { return getJSON(this.base + '/api/eval/summary'); }
  siteRisk() { return getJSON(this.base + '/api/site-risk'); }
  modelCard() { return getJSON(this.base + '/api/model-card'); }
  reviews() { return getJSON(this.base + '/api/review'); }
  addReview(body) { return getJSON(this.base + '/api/review', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); }
}

export class EmbeddedSource {
  constructor(embed) { this.embed = embed; this.kind = 'embedded'; this.local = []; }
  async cases(limit) {
    const { decide } = await import('./gate.js');
    const lim = limit != null ? limit : this.embed.review_limit;
    return {
      review_limit: lim, disclaimer: this.embed.disclaimer,
      cases: Object.entries(this.embed.cases).map(([id, c]) => {
        const s = c.prediction ? c.prediction.score : null, d = decide(s, lim);
        return { id, group: c.group || null, sequences: Object.keys(c.seqs), has_reference: !!c.reference, has_prediction: !!c.prediction,
          prediction_source: c.prediction ? c.prediction.source : null, score: s, flag: c.prediction ? d.flag : null,
          flag_label: c.prediction ? d.label : null, volumes_ml: c.prediction ? c.prediction.volumes_ml : null, review: null };
      }),
    };
  }
  async health() { return { status: 'ok', version: 'single-file demo', disclaimer: this.embed.disclaimer }; }
  thumbUrl() { return null; }
  async volume(caseId) {
    const c = this.embed.cases[caseId], seqs = {}, metas = {};
    for (const [s, b64] of Object.entries(c.seqs)) { seqs[s] = new Uint8Array(await gunzip(b64bytes(b64).buffer)); metas[s] = c.meta; }
    return volumeFromBundles(caseId, seqs, metas);
  }
  async single(caseId) { return this.volume(caseId); }
  async reference(caseId) { const c = this.embed.cases[caseId]; return c.reference ? new Uint8Array(await gunzip(b64bytes(c.reference).buffer)) : null; }
  async prediction(caseId, limit) {
    const c = this.embed.cases[caseId]; if (!c.prediction) return null;
    const { decide } = await import('./gate.js');
    const lim = limit != null ? limit : this.embed.review_limit, d = decide(c.prediction.score, lim);
    const info = { ...c.prediction, flag: d.flag, flag_label: d.label, reason: d.reason, review_limit: lim };
    return { info, labels: new Uint8Array(await gunzip(b64bytes(c.labels).buffer)), unc: new Uint8Array(await gunzip(b64bytes(c.unc).buffer)) };
  }
  async evalSummary() { return this.embed.eval || { status: 'not run' }; }
  async siteRisk() { return this.embed.site_risk || { status: 'not run' }; }
  async modelCard() { return this.embed.model_card || { status: 'not run' }; }
  async reviews() { return this.local; }
  async addReview(body) { const r = { id: this.local.length + 1, created_at: new Date().toISOString(), ...body }; this.local.push(r); return r; }
}

export function pickSource() {
  if (window.BTQC_EMBED) return new EmbeddedSource(window.BTQC_EMBED);
  return new ApiSource('');
}

// Local files dropped or opened by the user. Nothing is uploaded (R6). The sequence is
// taken from the file name; a name that does not identify one is shown as unknown.
export async function volumeFromFiles(files) {
  const list = [...files];
  for (const f of list) if (!isNiftiName(f.name)) throw new NiftiError(f.name + ' is not a NIfTI file. Use .nii or .nii.gz.');
  const parsed = [];
  for (const f of list) parsed.push({ role: roleOf(f.name), nii: await parseNifti(await f.arrayBuffer(), f.name) });
  const imgs = parsed.filter(p => p.role !== 'seg'), segs = parsed.filter(p => p.role === 'seg');
  if (!imgs.length) throw new NiftiError('Open at least one scan (T1, T1ce, T2 or FLAIR), not only a mask.');
  const d0 = imgs[0].nii.dims.join('×');
  for (const p of imgs) if (p.nii.dims.join('×') !== d0) throw new NiftiError(p.nii.name + ' is ' + p.nii.dims.join('×') + ' voxels but ' + imgs[0].nii.name + ' is ' + d0 + '.');
  const used = new Set(), seqs = {}; let ori = null, geom = null;
  for (const p of imgs) {
    let key = p.role || 'scan'; while (used.has(key)) key += '*'; used.add(key);
    const o = makeOrienter(p.nii.dims, p.nii.affine);
    if (!ori) { ori = o; geom = p; }
    seqs[key] = o.apply(rawToU8(p.nii.raw, p.nii.slope, p.nii.inter));
  }
  const order = [...SEQS.filter(k => seqs[k]), ...Object.keys(seqs).filter(k => !SEQS.includes(k))];
  const vol = {
    id: 'local', nx: ori.nd[0], ny: ori.nd[1], nz: ori.nd[2], sx: ori.sp[0], sy: ori.sp[1], sz: ori.sp[2], seqs, order,
    labels: null, unc: null, rawDims: geom.nii.dims, toOrig: ori.toOrig, fromOrig: ori.fromOrig,
    label: 'Local files: ' + imgs.length + (imgs.length > 1 ? ' sequences' : ' sequence') + ', ' + geom.nii.dims.join(' × ') + ' voxels',
    affine: canonicalAffine(geom.nii.affine, ori.toOrig), hasWorld: geom.nii.hasWorld, origAxes: axisCodes(ori.perm, ori.flip),
    seqSource: 'file name', windows: {}, cropped: false,
  };
  let seg = null;
  if (segs.length) {
    const s = segs[0].nii;
    if (s.dims.join('×') !== geom.nii.dims.join('×')) throw new NiftiError('The mask is ' + s.dims.join('×') + ' voxels but the scans are ' + d0 + '.');
    seg = makeOrienter(s.dims, s.affine).apply(rawToLabels(s.raw, s.slope, s.inter));
  }
  return { vol, seg };
}
