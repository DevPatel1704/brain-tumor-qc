// Site risk report, built from /api/site-risk (results/site_risk.json, written by `make site-risk`).
// Shift metrics are computed from images only; an accuracy estimate is shown only when the
// shift-versus-gap model exists, and is labeled as an estimate.
import { barChart, notRun } from './charts.js';
import { pickSource } from './data.js';
import { el, fmt, mountNav } from './nav.js';
import { countUp, icon } from './ui.js';

mountNav('site-risk.html');
const $ = s => document.querySelector(s);
const SEQ = { t1: 'T1', t1ce: 'T1ce', t2: 'T2', flair: 'FLAIR' };

function kpi(k, v, s, cls = '', digits = 0) {
  const d = el('div', { class: 'kpi ' + cls }, el('div', { class: 'k' }, k)), vv = el('div', { class: 'v' });
  d.append(vv); if (s) d.append(el('div', { class: 's' }, s));
  if (typeof v === 'number') countUp(vv, v, digits); else vv.textContent = v;
  return d;
}

async function init() {
  const r = await pickSource().siteRisk().catch(e => ({ status: 'not run', message: e.message }));
  const st = $('#status');
  if (r.status === 'not run') {
    st.innerHTML = icon('info', 15) + '<span></span>'; st.lastChild.textContent = 'Not run: ' + (r.message || '');
    notRun($('#cShift'), 'Intensity shift per sequence', 'Not run.'); notRun($('#cKs'), 'KS statistic per sequence', 'Not run.');
    notRun($('#cCases'), 'Per-case shift', 'Not run.'); notRun($('#cEst'), 'Estimated accuracy', 'Not run.');
    window.__ready = true; return;
  }
  const exampleRef = r.reference.kind !== 'training_pool';
  st.className = 'sub'; st.style.marginTop = '0';
  st.textContent = `Batch of ${r.batch.n_cases} cases (${r.batch.description}). Shift is the Wasserstein-1 distance between z-scored brain intensity histograms; KS is the Kolmogorov-Smirnov statistic.`;
  if (exampleRef) { $('#refNote').hidden = false; $('#refNote').innerHTML = icon('info', 15) + '<span><b>Example reference.</b> </span>'; $('#refNote').lastChild.append(r.reference.note); }
  const est = r.estimate, hasEst = est && est.estimate != null && !Number.isNaN(est.estimate);
  const k = $('#kpis'); k.hidden = false;
  k.append(kpi('Batch size', r.batch.n_cases, 'cases'), kpi('Reference pool', r.reference.n_cases, exampleRef ? 'example reference' : 'training pool', exampleRef ? 'warm' : ''),
    kpi('Mean W1 shift', r.shift.w1_mean, 'z-units, over sequences', 'accent', 3), kpi('Mean KS', r.shift.ks_mean, 'over sequences', '', 3),
    kpi('Estimated held-out Dice', hasEst ? fmt(est.estimate) : 'Unavailable', hasEst ? `range ${fmt(est.lo)} to ${fmt(est.hi)}` : 'no shift-versus-gap model', hasEst ? '' : 'na'));
  const badge = exampleRef ? 'example' : null;
  const bySeq = p => Object.entries(r.shift).filter(([kk]) => kk.startsWith(p) && !kk.endsWith('_mean')).map(([kk, v]) => ({ label: SEQ[kk.slice(p.length)] || kk.slice(p.length).toUpperCase(), value: v }));
  const w = bySeq('w1_'), ks = bySeq('ks_');
  barChart($('#cShift'), w, { title: 'Intensity shift per sequence (W1, z-units)', xLabel: 'Wasserstein-1', domain: [0, Math.max(0.2, ...w.map(x => x.value)) * 1.2], badge });
  barChart($('#cKs'), ks, { title: 'Distribution difference per sequence (KS)', xLabel: 'KS statistic', domain: [0, Math.max(0.1, ...ks.map(x => x.value)) * 1.2], badge, color: 1 });
  const all = r.cases.slice().sort((a, b) => b.w1_mean - a.w1_mean), TOP = 30, cs = all.slice(0, TOP);
  barChart($('#cCases'), cs.map(c => ({ label: c.case_id, value: c.w1_mean, note: `KS mean ${fmt(c.ks_mean)}` })),
    { title: all.length > TOP ? `Per-case shift: the ${TOP} most shifted of ${all.length} cases (mean W1)` : 'Per-case shift (mean W1 over sequences)',
      xLabel: 'mean W1 (z-units)', domain: [0, Math.max(0.1, ...cs.map(c => c.w1_mean)) * 1.15], badge });
  const c = $('#cEst');
  if (!hasEst) notRun(c, 'Estimated accuracy', est && est.reason ? est.reason : 'No shift-versus-gap model is available: it needs results from the site-held-out folds.');
  else {
    c.innerHTML = '<h2>Estimated held-out Dice <span class="badge example">Estimate</span></h2>';
    c.append(el('p', { class: 'sub' }, `${fmt(est.estimate)} (range ${fmt(est.lo)} to ${fmt(est.hi)}), from a line fitted on ${est.n_folds} folds. This is an estimate, not a measurement.`));
  }
  c.append(el('p', { class: 'help', style: 'margin-top:14px' }, r.note || ''));
  window.__ready = true;
}
init();
