// Home page: hero with a live render of a real case, capability cards and live project
// status. Everything shown is read from the API; nothing is invented when data is missing.
import { SEG_COLORS } from './colors.js';
import { pickSource } from './data.js';
import { mountNav } from './nav.js';
import { Renderer3D } from './render3d.js';
import { countUp, icon, logo, reducedMotion, reveal } from './ui.js';

// Old bookmarks (index.html?case=...&show=1) pointed at the viewer.
if (/[?&](case|show)=/.test(location.search)) location.replace('viewer.html' + location.search);

const $ = s => document.querySelector(s);
mountNav('index.html');
const src = pickSource();
$('#heroLogo').innerHTML = logo(30);
$('#ctaArrow').innerHTML = icon('arrow-right', 16);

/* ---------------------------------------------------------------- features */
const BRAIN = (cx, cy, rx, ry, extra = '') => `<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="url(#gB)" stroke="rgba(200,215,230,.35)" stroke-width="1"/>
  <path d="M${cx} ${cy - ry + 4}v${2 * ry - 8}" stroke="rgba(0,0,0,.5)" stroke-width="1.5"/>${extra}`;
const DEFS = `<defs><radialGradient id="gB" cx="50%" cy="45%" r="60%"><stop offset="0" stop-color="#8b96a3"/><stop offset=".7" stop-color="#3b434d"/><stop offset="1" stop-color="#1a1f25"/></radialGradient>
  <linearGradient id="gH" x1="0" x2="1"><stop offset="0" stop-color="#3c146e"/><stop offset=".35" stop-color="#a0238c"/><stop offset=".6" stop-color="#eb465a"/><stop offset=".8" stop-color="#ff9628"/><stop offset="1" stop-color="#ffeb78"/></linearGradient>
  <linearGradient id="gV" x1="0" x2="1"><stop offset="0" stop-color="#440154"/><stop offset=".5" stop-color="#21918c"/><stop offset="1" stop-color="#fde725"/></linearGradient></defs>`;
const TUMOR = (x, y, r) => `<circle cx="${x}" cy="${y}" r="${r + 5}" fill="rgba(46,189,89,.45)"/><circle cx="${x}" cy="${y}" r="${r + 1.5}" fill="#f2cc3a"/><circle cx="${x}" cy="${y}" r="${r - 2}" fill="#e5484d"/>`;
const ART = {
  viewer: `<svg viewBox="0 0 300 118" preserveAspectRatio="xMidYMid slice">${DEFS}
    <g>${[[0, 0], [1, 0], [0, 1], [1, 1]].map(([i, j]) => `<rect x="${78 + i * 73}" y="${4 + j * 56}" width="71" height="54" rx="4" fill="#020304" stroke="rgba(170,190,210,.12)"/>`).join('')}
    ${BRAIN(113, 31, 22, 19, TUMOR(121, 26, 5))}${BRAIN(187, 31, 25, 17, TUMOR(196, 27, 5))}${BRAIN(113, 87, 26, 16, TUMOR(121, 84, 5))}
    <ellipse cx="187" cy="87" rx="24" ry="19" fill="none" stroke="rgba(180,200,220,.4)" stroke-dasharray="2 3"/>${TUMOR(194, 83, 6)}
    <path d="M121 6v54M80 26h69M196 6v54M153 27h69" stroke="#f0b34f" stroke-width="1" opacity=".75"/></g></svg>`,
  compare: `<svg viewBox="0 0 300 118" preserveAspectRatio="xMidYMid slice">${DEFS}
    <rect x="60" y="8" width="180" height="102" rx="6" fill="#020304" stroke="rgba(170,190,210,.12)"/>
    <clipPath id="cL"><rect x="60" y="8" width="94" height="102"/></clipPath><clipPath id="cR"><rect x="154" y="8" width="86" height="102"/></clipPath>
    <g clip-path="url(#cL)">${BRAIN(150, 59, 46, 40, TUMOR(166, 48, 9))}</g>
    <g clip-path="url(#cR)"><ellipse cx="150" cy="59" rx="46" ry="40" fill="url(#gV)" opacity=".85" stroke="rgba(200,215,230,.35)"/>${TUMOR(134, 66, 7)}</g>
    <path d="M154 8v102" stroke="#e8edf1" stroke-width="2"/><circle cx="154" cy="59" r="8" fill="#e8edf1"/>
    <text x="70" y="22" fill="#7aabff" font-size="10" font-weight="700" font-family="system-ui">A</text><text x="226" y="22" fill="#f0b34f" font-size="10" font-weight="700" font-family="system-ui">B</text></svg>`,
  uncertainty: `<svg viewBox="0 0 300 118" preserveAspectRatio="xMidYMid slice">${DEFS}
    ${BRAIN(150, 59, 58, 48, '')}
    <ellipse cx="166" cy="50" rx="24" ry="20" fill="none" stroke="url(#gH)" stroke-width="9" opacity=".9"/>
    <ellipse cx="166" cy="50" rx="18" ry="14" fill="#e5484d" opacity=".55"/>
    <rect x="230" y="20" width="8" height="78" rx="4" fill="url(#gH)" transform="rotate(180 234 59)"/><text x="244" y="26" fill="#8490a0" font-size="8" font-family="system-ui">high</text><text x="244" y="98" fill="#8490a0" font-size="8" font-family="system-ui">low</text></svg>`,
  generalization: `<svg viewBox="0 0 300 118" preserveAspectRatio="xMidYMid slice">
    <path d="M40 98h220" stroke="rgba(170,190,210,.25)"/>${[0, 1, 2, 3, 4].map(i => {
      const x = 56 + i * 42, a = [72, 66, 70, 61, 68][i], b = [62, 41, 55, 30, 50][i];
      return `<rect x="${x}" y="${98 - a}" width="13" height="${a}" rx="2.5" fill="#3987e5" opacity=".9"/><rect x="${x + 15}" y="${98 - b}" width="13" height="${b}" rx="2.5" fill="#d95926" opacity=".9"/><path d="M${x + 21.5} ${98 - b - 9}v18" stroke="#e7ecf1" stroke-width="1.4"/>`;
    }).join('')}<text x="56" y="16" fill="#8490a0" font-size="8.5" font-family="system-ui">in-site</text><rect x="46" y="10" width="7" height="7" rx="1.5" fill="#3987e5"/><text x="106" y="16" fill="#8490a0" font-size="8.5" font-family="system-ui">held-out site</text><rect x="96" y="10" width="7" height="7" rx="1.5" fill="#d95926"/></svg>`,
  siterisk: `<svg viewBox="0 0 300 118" preserveAspectRatio="xMidYMid slice">
    <path d="M30 100h240" stroke="rgba(170,190,210,.25)"/>
    <path d="M30 100C80 100 92 22 128 22S176 100 226 100" fill="rgba(57,135,229,.18)" stroke="#3987e5" stroke-width="2"/>
    <path d="M60 100C112 100 126 36 160 36S206 100 262 100" fill="rgba(217,89,38,.14)" stroke="#d95926" stroke-width="2" stroke-dasharray="5 4"/>
    <path d="M128 14v90M160 28v76" stroke="rgba(231,236,241,.35)" stroke-dasharray="2 3"/><path d="M130 58h28" stroke="#f0b34f" stroke-width="2" marker-end="url(#ar)"/>
    <defs><marker id="ar" viewBox="0 0 8 8" refX="6" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 8 4 0 8z" fill="#f0b34f"/></marker></defs>
    <text x="134" y="52" fill="#f6c97a" font-size="8.5" font-family="ui-monospace,monospace">shift</text></svg>`,
  modelcard: `<svg viewBox="0 0 300 118" preserveAspectRatio="xMidYMid slice">
    <rect x="96" y="10" width="108" height="98" rx="8" fill="#151a20" stroke="rgba(170,190,210,.18)"/>
    ${[0, 1, 2, 3].map(i => `<circle cx="113" cy="${32 + i * 20}" r="5" fill="none" stroke="${i === 3 ? '#f0b34f' : '#5ccf9e'}" stroke-width="1.5"/>${i === 3 ? '<path d="M113 70v5" stroke="#f0b34f" stroke-width="1.5"/>' : `<path d="m110.5 ${32 + i * 20}l2 2 3.5-3.5" stroke="#5ccf9e" stroke-width="1.4" fill="none"/>`}<rect x="124" y="${29 + i * 20}" width="${[60, 48, 54, 40][i]}" height="5" rx="2.5" fill="rgba(170,190,210,.22)"/>`).join('')}
    <rect x="108" y="16" width="40" height="5" rx="2.5" fill="#7aabff" opacity=".8"/></svg>`,
};
const FEATURES = [
  ['viewer', 'viewer.html', 'viewer', 'MRI Viewer', 'Explore individual brain scans with linked axial, coronal, sagittal and 3D views, in grayscale or pseudocolor.'],
  ['compare', 'compare.html', 'split', 'Scan Comparison', 'Compare two MRI scans side by side, by flicker or split screen, with navigation synchronized through physical coordinates.'],
  ['uncertainty', 'viewer.html?show=1', 'pulse', 'Uncertainty Analysis', 'See where a segmentation is unsure with a voxel heat map, and jump straight to the region that most needs a second look.'],
  ['generalization', 'explorer.html', 'chart', 'Generalization Explorer', 'Investigate model behavior across held-out institutions: accuracy gaps, risk-coverage and calibration.'],
  ['siterisk', 'site-risk.html', 'globe', 'Site Risk Analysis', 'Measure intensity distribution shift for a batch of scans from a new site, against a reference pool.'],
  ['modelcard', 'model-card.html', 'doc', 'Research Model Card', 'Methodology, evaluation status, intended use and limitations, generated from the results on disk.'],
];
$('#features').innerHTML = FEATURES.map(([k, href, ic, title, body], i) =>
  `<a class="fcard" href="${href}" data-reveal style="--i:${i % 3}"><span class="num">0${i + 1}</span><div class="art">${ART[k]}</div>
   <h3>${icon(ic, 16)}${title}</h3><p>${body}</p><span class="go">Open ${icon('arrow-right', 14)}</span></a>`).join('');
for (const c of document.querySelectorAll('.fcard')) {
  c.addEventListener('pointermove', e => { const r = c.getBoundingClientRect(); c.style.setProperty('--mx', (e.clientX - r.left) + 'px'); c.style.setProperty('--my', (e.clientY - r.top) + 'px'); });
}
$('#ctaResearch').addEventListener('click', e => {
  e.preventDefault();
  $('#research').scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'start' });
});
reveal();

/* ---------------------------------------------------------------- live status */
function statRow(label, value, cls = '') { return `<div><span>${label}</span><b class="${cls}">${value}</b></div>`; }

async function loadStatus() {
  const [cases, ev, sr, mc, h] = await Promise.all([
    src.cases().catch(() => null), src.evalSummary().catch(() => null), src.siteRisk().catch(() => null),
    src.modelCard().catch(() => null), src.health().catch(() => null)]);
  const rows = [];
  if (cases) {
    const c = cases.cases, n = c.length, model = c.filter(x => x.prediction_source === 'model').length;
    const ex = c.filter(x => x.has_prediction && x.prediction_source !== 'model').length, ref = c.filter(x => x.has_reference).length;
    countUp($('#fCases'), n);
    $('#fModel').textContent = model ? String(model) : 'none yet';
    rows.push(statRow('Processed cases', n), statRow('With reference masks', ref), statRow('Trained-model predictions', model || 'none'),
      statRow('Rule-based example outlines', ex, ex ? 'warm' : ''), statRow('Default review limit', cases.review_limit.toFixed(2)));
  } else { $('#fCases').textContent = 'n/a'; $('#fModel').textContent = 'n/a'; rows.push(statRow('Case server', 'not reachable')); }
  rows.push(statRow('Site-held-out evaluation', ev && ev.status === 'ok' ? (ev.source === 'model' ? 'available' : 'example data') : ev && ev.synthetic_demo ? 'not run (synthetic demo only)' : 'not run'));
  if (ev && ev.status === 'ok' && ev.source === 'model') {
    // read the numbers from the evaluation summary, never hard-coded
    const dice = r => (ev.gaps || []).find(g => g.method === 'baseline' && g.metric === 'dice' && g.region === r);
    const f2 = v => (v == null || Number.isNaN(v) ? 'n/a' : Number(v).toFixed(2));
    const reg = ['WT', 'TC', 'ET'].map(dice).filter(Boolean);
    if (reg.length) {
      const n = reg[0].n_heldout;
      rows.push(statRow(`Held-out Dice WT / TC / ET (n = ${n})`, reg.map(g => f2(g.heldout_mean)).join(' / ')));
      rows.push(statRow(`In-site Dice WT / TC / ET (n = ${reg[0].n_insite})`, reg.map(g => f2(g.insite_mean)).join(' / ')));
    }
    const fl = (ev.failure || []).find(f => f.score === 'boundary_band');
    if (fl) rows.push(statRow('Failure detection AUROC (held-out)', `${f2(fl.auroc)} [${f2(fl.lo)}, ${f2(fl.hi)}]`));
  }
  rows.push(statRow('Site risk report', sr && sr.status === 'ok' ? (sr.reference && sr.reference.kind !== 'training_pool' ? 'example reference' : 'available') : 'not run'));
  const trained = mc && mc.sections ? (mc.sections.find(s => s.title === 'Model') || {}).body : null;
  rows.push(statRow('Model trained', trained && trained.Trained ? trained.Trained : 'unknown'));
  $('#statlist').innerHTML = rows.join('');
  for (const b of $('#statlist').querySelectorAll('b.warm')) b.style.color = 'var(--warm)';
  if (h) $('#ver').textContent = 'v' + h.version;
  return cases;
}

/* ---------------------------------------------------------------- hero render */
function brainBox(vol, d) {
  const { nx, ny, nz } = vol, lo = [nx, ny, nz], hi = [-1, -1, -1];
  let k = 0;
  for (let z = 0; z < nz; z++) for (let y = 0; y < ny; y++) for (let x = 0; x < nx; x++, k++) if (d[k] > 0) {
    if (x < lo[0]) lo[0] = x; if (x > hi[0]) hi[0] = x; if (y < lo[1]) lo[1] = y; if (y > hi[1]) hi[1] = y; if (z < lo[2]) lo[2] = z; if (z > hi[2]) hi[2] = z;
  }
  return hi[0] < 0 ? [0, nx - 1, 0, ny - 1, 0, nz - 1] : [0, 1, 2].flatMap(i => [Math.max(0, lo[i] - 3), Math.min([nx, ny, nz][i] - 1, hi[i] + 3)]);
}

// A 2D slice (radiological display) with the tumor outline, cropped to the brain box.
function paintChip(cv, vol, data, labels, axis, idx) {
  const ctx = cv.getContext('2d'), W = cv.width, H = cv.height, { nx, ny } = vol, b = vol.bbox;
  const [u0, u1, v0, v1] = axis === 2 ? [b[0], b[1], b[2], b[3]] : [b[0], b[1], b[4], b[5]];
  const su = u1 - u0 + 1, sv = v1 - v0 + 1, s = Math.max(su, sv), img = ctx.createImageData(W, H), px = new Uint32Array(img.data.buffer);
  const ou = u0 - (s - su) / 2, ov = v0 - (s - sv) / 2;
  for (let r = 0; r < H; r++) for (let c = 0; c < W; c++) {
    const u = Math.floor(ou + (1 - (c + 0.5) / W) * s), v = Math.floor(ov + (1 - (r + 0.5) / H) * s);
    let p = 0xFF000000;
    if (u >= 0 && v >= 0 && u < nx && v < (axis === 2 ? ny : vol.nz)) {
      const i = axis === 2 ? u + nx * (v + ny * idx) : u + nx * (idx + ny * v);
      let g = data[i], R = g, G = g, B = g;
      const l = labels && labels[i];
      if (l) { const col = SEG_COLORS[l] || SEG_COLORS[4]; R = g * 0.5 + col[0] * 0.5; G = g * 0.5 + col[1] * 0.5; B = g * 0.5 + col[2] * 0.5; }
      p = 0xFF000000 | ((B | 0) << 16) | ((G | 0) << 8) | (R | 0);
    }
    px[r * W + c] = p;
  }
  ctx.putImageData(img, 0, 0);
}

async function hero(cases) {
  const fb = $('#heroFallback'), cap = $('#heroCapT');
  const list = cases ? cases.cases : [];
  const pick = list.find(c => c.prediction_source === 'model') || list.find(c => c.has_prediction) || list[0];
  if (!pick) { fb.hidden = false; fb.textContent = 'No processed cases yet. Run the conversion step to see a live render here.'; cap.textContent = 'No data loaded'; return; }
  let vol, pred = null;
  try {
    vol = await src.single(pick.id, 'flair');
    if (pick.has_prediction) pred = await src.prediction(pick.id);
  } catch (e) { fb.hidden = false; fb.textContent = 'The volume could not be loaded.'; cap.textContent = 'Live render unavailable'; return; }
  const data = vol.seqs.flair || vol.seqs[vol.order[0]];
  vol.bbox = brainBox(vol, data);
  const labels = pred ? pred.labels : null;
  const cz = Math.round((vol.bbox[4] + vol.bbox[5]) / 2), cy = Math.round((vol.bbox[2] + vol.bbox[3]) / 2);
  const centroid = pred && pred.info.centroid ? pred.info.centroid.map(Math.round) : [vol.nx >> 1, cy, cz];
  const state = { vol, seq: vol.order[0], cursor: centroid.slice(), center: 0.5, width: 1, overlayOn: !!labels, layTum: true, regions: { 1: true, 2: true, 4: true } };
  const r = new Renderer3D($('#heroGl'), null, () => state, { maxDpr: 1, lowRes: 0.6 });
  const src3 = pred ? (pred.info.is_example ? 'tumor outline: rule-based EXAMPLE, not a model' : 'model prediction (' + pred.info.method + ')') : 'no outline';
  cap.textContent = `Live render · ${pick.id} · FLAIR · ${src3}`;
  $('#sliceALab').textContent = 'Axial · FLAIR'; $('#sliceBLab').textContent = 'Coronal · FLAIR';
  const vis = $('#heroVis'), stage = $('#stage3d');
  if (r.ok) {
    Object.assign(r.opts, { glass: true, cut: false, stepScale: 1.35 });
    r.cam.dist = 2.15; r.cam.theta = 0.28;
    r.setVolume(vol, state.seq); if (labels) r.setTumor(labels);
    r.size();
  } else { fb.hidden = false; fb.textContent = 'This browser has no WebGL 2, so the 3D render is off. The slice views still work.'; }

  const reduce = reducedMotion();
  let running = true, last = 0, lastChip = 0, t = 0, dragging = false;
  const amp = [Math.max(6, (vol.bbox[5] - vol.bbox[4]) * 0.32), Math.max(6, (vol.bbox[3] - vol.bbox[2]) * 0.3)];
  const chips = time => {
    const za = Math.round(centroid[2] + Math.sin(time * 0.35) * amp[0] * 0.5), yb = Math.round(centroid[1] + Math.sin(time * 0.28 + 1.2) * amp[1] * 0.5);
    const z = Math.max(0, Math.min(vol.nz - 1, za)), y = Math.max(0, Math.min(vol.ny - 1, yb));
    paintChip($('#sliceA'), vol, data, labels, 2, z); paintChip($('#sliceB'), vol, data, labels, 1, y);
    $('#sliceAPos').textContent = 'z ' + (z + 1); $('#sliceBPos').textContent = 'y ' + (y + 1);
  };
  chips(0);
  if (r.ok) r.render();
  requestAnimationFrame(() => { vis.classList.add('ready'); stage.classList.add('ready'); });
  r.onCamera = () => { dragging = true; clearTimeout(r.dragT); r.dragT = setTimeout(() => { dragging = false; }, 1200); };
  r.bind(() => { if (r.ok) r.render(); });
  if (reduce) return;
  const loop = now => {
    if (!running) return;
    const dt = last ? Math.min(0.1, (now - last) / 1000) : 0;
    if (now - last >= 33) {
      last = now; t += dt;
      if (r.ok && !dragging) { r.cam.phi += dt * 0.16; r.render(); }
      if (now - lastChip > 66) { lastChip = now; chips(t); }
    }
    requestAnimationFrame(loop);
  };
  const start = () => { if (!running) { running = true; last = 0; requestAnimationFrame(loop); } };
  const stop = () => { running = false; };
  requestAnimationFrame(loop);
  new IntersectionObserver(es => { for (const e of es) e.isIntersecting ? start() : stop(); }, { threshold: 0.05 }).observe(vis);
  document.addEventListener('visibilitychange', () => (document.hidden ? stop() : start()));
  // gentle depth: the slice chips drift against the pointer
  vis.addEventListener('pointermove', e => {
    const b = vis.getBoundingClientRect(), dx = (e.clientX - b.left) / b.width - 0.5, dy = (e.clientY - b.top) / b.height - 0.5;
    vis.querySelector('.c1').style.translate = `${dx * -10}px ${dy * -10}px`;
    vis.querySelector('.c2').style.translate = `${dx * 14}px ${dy * 14}px`;
  });
}

async function init() {
  const cases = await loadStatus();
  window.__ready = true;
  hero(cases);
}
init();
