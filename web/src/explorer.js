// Generalization explorer, built from /api/eval/summary (results/eval_summary.json).
// Real results, example data and the synthetic demo are always labeled as such;
// accuracy for unlabeled cases is shown as unavailable, never estimated.
import { barChart, lineChart, notRun } from './charts.js';
import { pickSource } from './data.js';
import { mountNav } from './nav.js';
import { countUp, icon, radioGroup, setRadio } from './ui.js';

mountNav('explorer.html');
const $ = s => document.querySelector(s);
const src = pickSource();
let real = null, synth = null, S = null;

function opt(sel, values) { sel.innerHTML = ''; for (const v of values) { const o = document.createElement('option'); o.value = o.textContent = v; sel.appendChild(o); } }
const kpi = (k, v, s = '', cls = '', ic = '') => `<div class="kpi ${cls}"><div class="k">${ic ? icon(ic, 13) : ''}${k}</div><div class="v" data-n="${typeof v === 'number' ? v : ''}">${typeof v === 'number' ? '0' : v}</div>${s ? `<div class="s">${s}</div>` : ''}</div>`;
function animateKpis(box) { for (const v of box.querySelectorAll('.v[data-n]')) if (v.dataset.n !== '') countUp(v, +v.dataset.n); }

function draw() {
  const ids = ['cHeld', 'cGap', 'cMethods', 'cRC', 'cRel', 'cFail'];
  if (!S) {
    const why = (real && real.message) || 'No site-held-out evaluation has been run.';
    const titles = ['Held-out Dice by site group', 'Generalization gap by group', 'Mitigation comparison', 'Risk-coverage', 'Reliability diagram', 'Failure detection'];
    ids.forEach((id, i) => notRun($('#' + id), titles[i], 'Not run. ' + why));
    $('#filters').hidden = true; $('#sumKpis').hidden = true; return;
  }
  $('#filters').hidden = false;
  const badge = S.source === 'model' ? null : S.source === 'synthetic' ? 'synthetic' : 'example';
  const m = $('#fMethod').value, r = $('#fRegion').value, met = $('#fMetric').value;
  const rows = S.gaps.filter(g => g.method === m && g.region === r && g.metric === met);
  const dom = met === 'dice' ? [0, 1] : [0, Math.max(10, ...rows.map(g => g.heldout_hi || g.heldout_mean || 0)) * 1.1];
  barChart($('#cHeld'), rows.map(g => ({ label: g.fold, value: g.heldout_mean, lo: g.heldout_lo, hi: g.heldout_hi, note: `n = ${g.n_heldout}${g.small_n ? ' (small n)' : ''}; in-site ${(+g.insite_mean).toFixed(3)}` })),
    { title: `Held-out ${met === 'dice' ? 'Dice' : 'HD95'} (${r}), ${m}`, xLabel: met === 'dice' ? 'Dice' : 'HD95 (mm)', domain: dom, badge });
  const gd = Math.max(0.05, ...rows.map(g => Math.abs(g.gap_hi ?? g.gap ?? 0)), ...rows.map(g => Math.abs(g.gap_lo ?? 0))) * 1.1;
  barChart($('#cGap'), rows.map(g => ({ label: g.fold, value: g.gap, lo: g.gap_lo, hi: g.gap_hi, note: 'in-site minus held-out' })),
    { title: `Gap (in-site minus held-out), ${r}`, xLabel: met === 'dice' ? 'Dice difference' : 'HD95 difference (mm)', domain: [met === 'dice' ? -gd : -gd * 10, met === 'dice' ? gd : gd * 10], badge, color: 1 });
  const byM = {};
  for (const g of S.gaps.filter(g => g.region === r && g.metric === met)) (byM[g.method] = byM[g.method] || []).push(g.gap);
  const mi = Object.entries(byM).map(([k, v]) => ({ label: k, value: v.reduce((a, b) => a + b, 0) / v.length, note: `mean over ${v.length} folds` }));
  const md = Math.max(0.05, ...mi.map(x => Math.abs(x.value))) * 1.2;
  barChart($('#cMethods'), mi, { title: `Mean gap per method (${r})`, xLabel: 'mean gap', domain: [-md, md], badge, color: 2 });
  const rc = (S.risk_coverage || []).filter(x => x.method === m).slice(0, 3);
  if (rc.length) lineChart($('#cRC'), rc.map(x => ({ name: x.fold, points: x.coverage.map((c, i) => [c, x.mean_dice[i]]) })), { title: `Risk-coverage (${m}), held-out cases`, xLabel: 'coverage (fraction retained)', yLabel: 'mean WT Dice of retained', yDomain: [0, 1], badge });
  else notRun($('#cRC'), 'Risk-coverage', 'No risk-coverage points for this method.');
  const rel = (S.reliability || []).filter(x => x.method === m && x.mode === 'band' && x.split === 'heldout');
  if (rel.length) lineChart($('#cRel'), ['WT', 'TC', 'ET'].map(reg => { const x = rel.find(z => z.region === reg); return { name: reg, points: x ? x.points.filter(p => p.count > 0).map(p => [p.confidence, p.accuracy]) : [] }; }), { title: `Reliability (${m}, held-out, tumor band)`, xLabel: 'predicted probability', yLabel: 'observed frequency', diagonal: true, badge });
  else notRun($('#cRel'), 'Reliability diagram', 'No calibration points for this method.');
  const fl = (S.failure || []).filter(x => x.method === m && x.score === 'boundary_band');
  if (fl.length) barChart($('#cFail'), fl.map(x => ({ label: x.fold, value: x.auroc, lo: x.lo, hi: x.hi,
    na: `not defined: ${x.n_failed} of ${x.n} cases failed`, note: `failures ${x.n_failed} of ${x.n}; review limit ${x.review_limit == null ? '–' : (+x.review_limit).toFixed(3)} (from in-site val)` })),
  { title: 'Failure-detection AUROC, boundary-band score (bootstrap 95% CI)', xLabel: 'AUROC (0.5 = chance)', domain: [0, 1], badge });
  else notRun($('#cFail'), 'Failure detection', 'No failure-detection results for this method.');
  const k = $('#sumKpis'); k.hidden = false;
  k.innerHTML = kpi('Cases in summary', S.n_cases ?? '–', badge ? 'synthetic fixtures' : '', 'accent') + kpi('Held-out folds', (S.folds || []).length) +
    kpi('Methods', (S.methods || []).length) + kpi('Failure threshold τ', S.tau != null ? 'Dice < ' + S.tau : '–', 'fixed before evaluation');
  animateKpis(k);
}

function useSummary(s) {
  S = s;
  if (S) opt($('#fMethod'), [...new Set(S.gaps.map(g => g.method))]);
  draw();
}

async function composition() {
  const res = await src.cases().catch(() => null), box = $('#composition');
  if (!res) { box.hidden = true; return; }
  const c = res.cases, n = c.length, ref = c.filter(x => x.has_reference).length, model = c.filter(x => x.prediction_source === 'model').length;
  const ex = c.filter(x => x.has_prediction && x.prediction_source !== 'model').length, grp = c.filter(x => x.group).length;
  box.innerHTML = kpi('Processed cases', n, 'in this installation', 'accent', 'folder') + kpi('With reference masks', ref, ref ? '' : 'accuracy cannot be measured', ref ? 'ok' : '', 'check') +
    kpi('Trained-model predictions', model, model ? '' : 'no model trained yet', '', 'cube') + kpi('Rule-based examples', ex, 'not model results', ex ? 'warm' : '', 'info') +
    kpi('Site group known', grp, grp ? '' : 'no site table available', '', 'globe') +
    (n - ref > 0 ? `<div class="kpi na"><div class="k">${icon('chart', 13)}Accuracy on the ${n - ref} unlabeled cases</div><div class="v">Unavailable</div><div class="s">No reference masks, so no Dice or HD95.</div></div>` : '');
  animateKpis(box);
}

async function init() {
  composition();
  real = await src.evalSummary().catch(e => ({ status: 'not run', message: e.message }));
  const st = $('#status');
  if (real.status === 'ok') {
    st.className = real.source === 'model' ? 'callout' : 'example';
    st.innerHTML = icon('info', 15) + '<span></span>';
    st.lastChild.textContent = real.source === 'model' ? `Results from ${real.run || 'the site-held-out harness'}.` : 'EXAMPLE data, not results.';
    useSummary(real);
  } else {
    st.innerHTML = icon('info', 15) + '<span><b>Not run on real data.</b> </span>';
    st.lastChild.append(real.message || 'No site-held-out evaluation exists yet.');
    synth = real.synthetic_demo || null;
    $('#synthWrap').hidden = !synth;
    useSummary(null);
  }
  window.__ready = true;
}
$('#synth').addEventListener('change', e => {
  const on = e.target.checked; $('#synthNote').hidden = !on;
  $('#synthNote').innerHTML = icon('info', 15) + '<span><b>Synthetic pipeline demo, not a result.</b> </span>';
  $('#synthNote').lastChild.append(synth ? synth.note : '');
  useSummary(on ? synth : null);
});
radioGroup($('#fRegionSeg'), v => { setRadio($('#fRegionSeg'), v); $('#fRegion').value = v; draw(); });
radioGroup($('#fMetricSeg'), v => { setRadio($('#fMetricSeg'), v); $('#fMetric').value = v; draw(); });
setRadio($('#fRegionSeg'), 'WT'); setRadio($('#fMetricSeg'), 'dice');
for (const id of ['fMethod', 'fRegion', 'fMetric']) $('#' + id).addEventListener('change', draw);
init();
