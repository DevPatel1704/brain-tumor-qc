// Viewer page: case selection, local files, display modes (grayscale, pseudocolor,
// MRI + segmentation), report panel and the advisory review flag.
import { SEG_REGIONS, SEQ_FULL, SEQ_LABELS } from './colors.js';
import { CMAP_ORDER, CMAPS, cmapGradient } from './colormaps.js';
import { pickSource, volumeFromFiles } from './data.js';
import { decide } from './gate.js';
import { mountNav } from './nav.js';
import { icon, paintRanges, radioGroup, setRadio, toast } from './ui.js';
import { MODES, Viewer } from './viewer.js';

const $ = s => document.querySelector(s);
mountNav('viewer.html');
const src = pickSource();
const params = new URLSearchParams(location.search);
const app = { pred: null, ref: null, showRef: false, reviewLimit: 0.25, defaultLimit: 0.25, caseId: null, cases: {}, ids: [],
  seqTouched: false, segSeen: false, wantShow: params.get('show') === '1' };
const ml = v => v == null ? '–' : v.toFixed(1) + ' mL';

const viewer = new Viewer($('#stage'), {
  onCursor: r => {
    $('#sVox').textContent = r.original.join(', ');
    $('#sRas').textContent = r.canonical.join(', ');
    $('#sWorld').textContent = r.world ? r.world.map(v => v.toFixed(1)).join(', ') : 'n/a';
    $('#sSig').textContent = Math.round(r.signal / 255 * 100) + '%';
    const st = viewer.state, on = st.overlayOn && st.vol.labels;
    $('#sLabWrap').hidden = !on; $('#sUncWrap').hidden = !(st.overlayOn && st.vol.unc);
    if (on) $('#sLab').textContent = r.labelName;
    if (st.overlayOn && st.vol.unc) $('#sUnc').textContent = r.unc.toFixed(2);
  },
});
window.__btqc = { viewer, app, decide };

/* ---------------------------------------------------------------- status */
function cover(t, frac) {
  const c = $('#cover'), card = $('#coverCard');
  c.classList.toggle('on', !!t);
  if (!t) return;
  $('#coverT').textContent = t;
  card.classList.toggle('idle', frac == null);
  if (frac != null) $('#coverP').style.width = Math.round(frac * 100) + '%';
}
function msg(t, err) {
  const m = $('#msg'); m.textContent = t || ''; m.classList.toggle('err', !!err);
  if (t) toast(t, err ? 'err' : 'ok', err ? 5000 : 2600);
}

/* ---------------------------------------------------------------- tabs */
function showTab(k) {
  setRadio($('#railTabs'), k);
  for (const p of document.querySelectorAll('.rail-panel')) p.hidden = p.dataset.tab !== k;
}
radioGroup($('#railTabs'), showTab);

/* ---------------------------------------------------------------- sequence */
function buildSeqTabs() {
  const box = $('#seq'), st = viewer.state; box.innerHTML = '';
  for (const k of st.vol.order) {
    const b = document.createElement('button');
    b.type = 'button'; b.setAttribute('role', 'radio'); b.dataset.value = k; b.textContent = SEQ_LABELS[k] || k;
    box.appendChild(b);
  }
  setRadio(box, st.seq);
}
radioGroup($('#seq'), k => { app.seqTouched = true; selectSeq(k); });

function selectSeq(k) {
  const vol = viewer.state.vol; if (!vol) return;
  if (viewer.state.seq !== k) viewer.setSeq(k);
  setRadio($('#seq'), k);
  const base = k.replace(/\*+$/, ''), name = SEQ_FULL[base] || 'Unknown sequence';
  $('#seqChip').innerHTML = `<b>${SEQ_LABELS[base] || k}</b>`;
  $('#pcSeq').textContent = SEQ_LABELS[base] || k;
  const w = vol.windows && vol.windows[k];
  $('#seqFull').textContent = name + (vol.seqSource === 'file name' ? ' (identified from the file name)' : '') +
    (base === 'scan' ? '. The file name does not identify the sequence, so none is assumed.' : '') +
    (w ? `. Display range ${Math.round(w.lo)} to ${Math.round(w.hi)} (stored units, 1st to 99th percentile).` : '.');
  $('#cbLo').textContent = w ? 'p1 · ' + Math.round(w.lo) : '1st pct';
  $('#cbHi').textContent = w ? 'p99 · ' + Math.round(w.hi) : '99th pct';
}

/* ---------------------------------------------------------------- display modes */
function buildCmaps() {
  const box = $('#cmaps');
  for (const k of CMAP_ORDER) {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'cmap'; b.setAttribute('role', 'radio'); b.dataset.value = k;
    b.title = CMAPS[k].note;
    b.innerHTML = `<span class="bar" style="background:${cmapGradient(k)}"></span><span>${CMAPS[k].label}</span>`;
    box.appendChild(b);
  }
  radioGroup(box, k => { viewer.setColormap(k); syncDisplayUI(); });
  $('#swColor').style.background = cmapGradient('viridis');
}

function colorShown() { const s = viewer.state; return s.mode === 'color' || (s.mode === 'seg' && s.segBase === 'color'); }

function syncDisplayUI() {
  const s = viewer.state;
  setRadio($('#modes'), s.mode); setRadio($('#cmaps'), s.cmap); setRadio($('#segBase'), s.segBase); setRadio($('#segStyle'), s.segStyle);
  $('#secColor').hidden = !colorShown();
  $('#secSeg').hidden = s.mode !== 'seg';
  $('#swColor').style.background = cmapGradient(s.cmap);
  $('#cbar').style.background = cmapGradient(s.cmap, 24);
  $('#cmapNote').textContent = CMAPS[s.cmap].note + '.';
  $('#modeChip').innerHTML = s.mode === 'color' ? `<b>Pseudocolor</b> · ${CMAPS[s.cmap].label}` : `<b>${MODES[s.mode]}</b>`;
  const ex = app.pred && app.pred.info.is_example && !app.showRef;
  $('#modeHelp').textContent = s.mode === 'gray' ? 'Original grayscale display of the stored intensities.'
    : s.mode === 'color' ? 'The same intensities passed through a color map. A display transform only.'
      : ex ? 'MRI with the rule-based EXAMPLE outline and heat map (not a model result).'
        : app.showRef || !app.pred ? 'MRI with the reference mask.' : 'MRI with the predicted tumor regions and uncertainty.';
  $('#ovBadge').hidden = !ex;
}

function setMode(m, animate = true) {
  if (m === 'seg' && !(app.pred || app.ref)) return;
  const was = viewer.state.mode;
  viewer.setMode(m, { animate });
  if (m === 'seg' && !app.segSeen) {
    app.segSeen = true;
    const c = app.pred && app.pred.info.centroid;
    if (c) animate ? viewer.flyTo(c.map(Math.round)) : viewer.setCursor(c.map(Math.round));
    if (!app.seqTouched && viewer.state.vol.order.includes('t1ce')) selectSeq('t1ce');
    viewer.setGlass(viewer.r3d.ok);
  } else if (m !== 'seg' && was === 'seg') viewer.setGlass(false);
  syncDisplayUI();
}
radioGroup($('#modes'), m => setMode(m));
radioGroup($('#segBase'), b => { viewer.setSegBase(b); syncDisplayUI(); });
radioGroup($('#segStyle'), s => { viewer.setSegStyle(s); setRadio($('#segStyle'), s); });

function buildRegions() {
  const box = $('#regions');
  box.innerHTML = SEG_REGIONS.map(([l, name, ab, hex]) =>
    `<label class="region"><i style="background:${hex}"></i><span>${name}</span><span class="ml" id="rv${ab}">–</span><input type="checkbox" class="switch" data-reg="${l}" checked aria-label="${name}"></label>`).join('');
  box.addEventListener('change', e => { const l = e.target.dataset.reg; if (l) viewer.setRegion(+l, e.target.checked); });
}

// Labels stay loaded whatever the mode; the overlay is shown only in MRI + segmentation.
function applyOverlay() {
  if (app.showRef && app.ref) viewer.setOverlay(app.ref, null);
  else if (app.pred) viewer.setOverlay(app.pred.labels, app.pred.unc);
  else if (app.ref) viewer.setOverlay(app.ref, null);
  else viewer.setOverlay(null, null);
}

/* ---------------------------------------------------------------- report */
function updateFlag() {
  if (!app.pred) return;
  const s = app.pred.info.score, d = decide(s, app.reviewLimit);
  $('#flagBox').classList.toggle('ok', !d.flag);
  $('#flagBox').dataset.flag = d.flag ? 'review' : 'ok';
  $('#flagTitle').textContent = d.label;
  $('#flagWhy').textContent = d.reason;
  $('#scoreVal').textContent = s == null ? 'n/a' : s.toFixed(3);
  $('#tickScore').style.left = (s == null ? 100 : Math.min(1, s) * 100) + '%';
  $('#tickThr').style.left = (app.reviewLimit * 100) + '%';
  $('#thrFlagO').textContent = app.reviewLimit.toFixed(2);
  const chip = $('#flagChip'); chip.hidden = false; chip.classList.toggle('ok', !d.flag);
  $('#flagChipT').innerHTML = `${d.label} <b class="mono">${s == null ? 'n/a' : s.toFixed(3)}</b>`;
  $('#repDot').hidden = !d.flag;
}

function fillReport() {
  $('#rpEmpty').hidden = !!app.pred; $('#rpBody').hidden = !app.pred;
  $('#flagChip').hidden = !app.pred; $('#repDot').hidden = true;
  $('#rpEmpty').textContent = app.ref ? 'No prediction for this case. A reference mask is available in MRI + segmentation.' : 'No prediction for this case.';
  const ex = $('#exampleNote');
  ex.hidden = !(app.pred && app.pred.info.is_example);
  if (!app.pred) { for (const [, , ab] of SEG_REGIONS) $('#rv' + ab).textContent = '–'; return; }
  const i = app.pred.info, v = i.volumes_ml || {};
  $('#vWT').textContent = ml(v.WT); $('#vTC').textContent = ml(v.TC); $('#vET').textContent = ml(v.ET);
  $('#vED').textContent = ml(v.ED); $('#loc').textContent = i.hemisphere ? i.hemisphere[0].toUpperCase() + i.hemisphere.slice(1) : '–';
  $('#rvNCR').textContent = ml(v.NCR); $('#rvED').textContent = ml(v.ED); $('#rvET').textContent = ml(v.ET);
  $('#srcBadge').className = 'badge ' + (i.is_example ? 'example' : 'real');
  $('#srcBadge').textContent = i.is_example ? 'Example' : 'Model ' + i.method;
  if (i.is_example) ex.innerHTML = icon('info', 15) + '<span><b>Example, not a model result.</b> ' + (i.example_note || 'This outline comes from simple brightness rules.') + '</span>';
  $('#goHot').disabled = !i.hot_spot;
  updateFlag();
}

/* ---------------------------------------------------------------- case */
function metaRows(vol) {
  const info = app.cases[app.caseId] || {}, rows = [
    ['Case', app.caseId || 'local files'],
    ['Source', vol.seqSource === 'dataset' ? 'Processed dataset (API)' : 'Local files, in this browser only'],
    ['Grid', `${vol.nx} × ${vol.ny} × ${vol.nz} voxels`],
    ['Spacing', [vol.sx, vol.sy, vol.sz].map(x => +x.toFixed(3)).join(' × ') + ' mm'],
    ['Display orientation', 'RAS, radiological (patient right on screen left)'],
    ['On disk', vol.origAxes ? vol.origAxes + ' axis codes, ' + vol.rawDims.join(' × ') : vol.rawDims.join(' × ')],
    ['Physical coordinates', vol.hasWorld ? 'yes (affine)' : 'no qform or sform'],
    ['Sequences', vol.order.map(k => SEQ_LABELS[k.replace(/\*+$/, '')] || k).join(', ') + (vol.seqSource === 'file name' ? ' (from file names)' : '')],
  ];
  if (app.caseId) rows.push(['Site group', info.group || 'unknown (no site table)'], ['Reference mask', info.has_reference ? 'yes' : 'no'],
    ['Prediction', info.has_prediction ? (info.prediction_source === 'model' ? 'model' : 'rule-based example') : 'none']);
  $('#meta').innerHTML = '';
  for (const [k, v] of rows) { const dt = document.createElement('dt'), dd = document.createElement('dd'); dt.textContent = k; dd.textContent = v; $('#meta').append(dt, dd); }
}

function resetCaseUI(vol) {
  app.pred = null; app.ref = null; app.showRef = false; app.segSeen = false; $('#layRef').checked = false;
  if (viewer.state.mode === 'seg') viewer.setMode('gray', { animate: false });
  viewer.setVolume(vol); buildSeqTabs(); selectSeq(viewer.state.seq);
  $('#caseLine').textContent = vol.label;
  $('#seqSrc').textContent = vol.seqSource === 'dataset' ? 'from dataset' : 'from file names';
  $('#sDim').textContent = vol.rawDims.join(' × ');
  $('#sSp').textContent = [vol.sx, vol.sy, vol.sz].map(x => +x.toFixed(2)).join(' × ') + ' mm';
  $('#exampleNote').hidden = true;
  metaRows(vol);
}

function afterOverlayLoaded(keepSeg) {
  $('#modeSeg').disabled = !(app.pred || app.ref);
  $('#layRef').disabled = !(app.ref && app.pred);
  applyOverlay(); fillReport();
  if ((keepSeg || app.wantShow) && (app.pred || app.ref)) setMode('seg', !app.wantShow);
  else syncDisplayUI();
  app.wantShow = false;
}

async function loadCase(id) {
  if (!id) return;
  const keepSeg = viewer.state.mode === 'seg';
  cover('Loading ' + id + '…', 0); msg('');
  try {
    const info = app.cases[id] || {};
    const vol = await src.volume(id, (t, f) => cover(t, f), info.sequences && info.sequences.length ? info.sequences : undefined);
    resetCaseUI(vol); app.caseId = id; metaRows(vol);
    $('#casePick').value = id;
    // ask only for what exists (avoids 404s for unlabeled cases)
    const [ref, pred] = await Promise.all([info.has_reference ? src.reference(id) : null,
      info.has_prediction === false ? null : src.prediction(id, app.reviewLimit)]);
    app.ref = ref; app.pred = pred;
    cover('');
    afterOverlayLoaded(keepSeg);
    if (src.kind === 'api') history.replaceState(null, '', '?case=' + encodeURIComponent(id));
  } catch (e) { console.error(e); cover(viewer.state.vol ? '' : 'Choose a case or open local files.'); msg('Could not load the case. ' + e.message, true); }
}

async function loadFiles(list) {
  if (!list || !list.length) return;
  msg(''); cover('Reading ' + list.length + (list.length > 1 ? ' files…' : ' file…'));
  try {
    const { vol, seg } = await volumeFromFiles(list);
    app.caseId = null;
    resetCaseUI(vol);
    app.ref = seg; $('#casePick').value = '';
    cover(''); afterOverlayLoaded(false);
    msg('Opened ' + list.length + (list.length > 1 ? ' files' : ' file') + ' locally.');
  } catch (e) {
    console.warn(e.message); cover(viewer.state.vol ? '' : 'Choose a case or open local files.'); msg(e.message, true);
  }
}

function stepCase(d) {
  const i = app.ids.indexOf(app.caseId), j = i < 0 ? 0 : (i + d + app.ids.length) % app.ids.length;
  if (app.ids[j]) loadCase(app.ids[j]);
}

async function init() {
  buildCmaps(); buildRegions(); syncDisplayUI();
  try {
    // no limit on the first request: the server's configured default (serve.yaml) is the starting value
    const res = await src.cases();
    app.reviewLimit = app.defaultLimit = res.review_limit;
    $('#thrFlag').value = Math.round(app.reviewLimit * 100); $('#thrFlagO').textContent = app.reviewLimit.toFixed(2); $('#thrDefault').textContent = app.defaultLimit.toFixed(2);
    const sel = $('#casePick'); sel.innerHTML = '<option value="">Choose a case…</option>';
    for (const c of res.cases) {
      app.cases[c.id] = c; app.ids.push(c.id);
      const o = document.createElement('option'); o.value = c.id;
      o.textContent = c.id + (c.has_prediction ? (c.prediction_source === 'model' ? ' · prediction' : ' · example') : '') + (c.has_reference ? ' · reference' : '');
      sel.appendChild(o);
    }
    const want = params.get('case') || (res.cases.find(c => c.has_prediction) || res.cases[0] || {}).id;
    if (want) { sel.value = want; await loadCase(want); }
    else cover('No processed cases. Open local files from the Case tab.');
  } catch (e) {
    $('#casePick').innerHTML = '<option value="">No case server</option>';
    msg('Case list not available (' + e.message + '). You can still open local files.');
    cover('Open local files from the Case tab.');
  }
  paintRanges();
  window.__ready = true;
}

/* ---------------------------------------------------------------- wiring */
function slider(id, fn, out = v => v) { const el = $('#' + id), o = $('#' + id + 'O'); el.addEventListener('input', () => { o.textContent = out(+el.value); fn(+el.value); }); }
slider('lvl', v => viewer.setWindow(v / 100, viewer.state.width));
slider('win', v => viewer.setWindow(viewer.state.center, v / 100));
slider('gam', v => viewer.setGamma(v / 100), v => (v / 100).toFixed(2));
slider('ovA', v => viewer.setOpacity(v / 100));
$('#thrFlag').addEventListener('input', e => { app.reviewLimit = +e.target.value / 100; updateFlag(); });
$('#winReset').addEventListener('click', () => {
  for (const [id, v, t] of [['lvl', 50, '50'], ['win', 100, '100'], ['gam', 100, '1.00']]) { $('#' + id).value = v; $('#' + id + 'O').textContent = t; }
  paintRanges(); viewer.state.gamma = 1; viewer.setWindow(0.5, 1);
});
$('#layTum').addEventListener('change', e => { viewer.setLayer('tum', e.target.checked); for (const r of document.querySelectorAll('[data-reg]')) r.disabled = !e.target.checked; });
$('#layUnc').addEventListener('change', e => viewer.setLayer('unc', e.target.checked));
$('#layRef').addEventListener('change', e => { app.showRef = e.target.checked; applyOverlay(); syncDisplayUI(); });
$('#goHot').innerHTML = icon('target', 15) + 'Go to the most uncertain spot';
$('#goHot').addEventListener('click', () => {
  if (!app.pred || !app.pred.info.hot_spot) return;
  if (viewer.state.mode !== 'seg') setMode('seg');
  viewer.flyTo(app.pred.info.hot_spot); $('#layUnc').checked = true; viewer.setLayer('unc', true);
});
$('#flagChip').addEventListener('click', () => showTab('report'));
$('#casePick').addEventListener('change', e => loadCase(e.target.value));
$('#casePrev').innerHTML = icon('chev-left'); $('#caseNext').innerHTML = icon('chev-right');
$('#casePrev').addEventListener('click', () => stepCase(-1)); $('#caseNext').addEventListener('click', () => stepCase(1));
$('#fileIn').addEventListener('change', e => loadFiles(e.target.files));

const LAYOUT_ICONS = { grid: 'grid', focus: 'focus', row: 'queue', single: 'single' };
for (const b of $('#layout').children) b.innerHTML = icon(LAYOUT_ICONS[b.dataset.value]);
$('#layout').querySelector('[data-value=row]').innerHTML = '<svg class="ic" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><rect x="1.5" y="4" width="2.6" height="8" rx=".8"/><rect x="5.1" y="4" width="2.6" height="8" rx=".8"/><rect x="8.7" y="4" width="2.6" height="8" rx=".8"/><rect x="12.3" y="4" width="2.2" height="8" rx=".8"/></svg>';
radioGroup($('#layout'), v => viewer.setLayout(v, viewer.main));
viewer.on('layout', ({ layout }) => setRadio($('#layout'), layout));
setRadio($('#layout'), 'grid');
$('#crossAll').innerHTML = icon('cross'); $('#resetView').innerHTML = icon('reset'); $('#keysBtn').innerHTML = icon('keyboard'); $('#fsBtn').innerHTML = icon('fullscreen');
$('#crossAll').addEventListener('click', e => { const on = !viewer.state.showCross; viewer.setCrosshairs(on); e.currentTarget.setAttribute('aria-pressed', String(on)); });
$('#resetView').addEventListener('click', () => { viewer.resetViews(); viewer.flyCam('reset'); });
$('#keysBtn').addEventListener('click', () => $('#keysDlg').showModal());
$('#fsBtn').addEventListener('click', () => { if (document.fullscreenElement) document.exitFullscreen(); else $('#stage').requestFullscreen && $('#stage').requestFullscreen().catch(() => {}); });
for (const v of viewer.views) v.canvas.addEventListener('focus', () => { viewer.main = v.key; });

const drop = $('#drop');
for (const t of ['dragenter', 'dragover']) drop.addEventListener(t, e => { e.preventDefault(); drop.classList.add('over'); });
for (const t of ['dragleave', 'drop']) drop.addEventListener(t, e => { e.preventDefault(); drop.classList.remove('over'); });
drop.addEventListener('drop', e => loadFiles(e.dataTransfer.files));
document.body.addEventListener('dragover', e => e.preventDefault());
document.body.addEventListener('drop', e => { e.preventDefault(); if (!drop.contains(e.target)) loadFiles(e.dataTransfer.files); });

init();
