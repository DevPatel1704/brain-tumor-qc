// Review queue: cases sorted by uncertainty with accept / reject / note, persisted through
// the API. The flag is advisory: decide(score, limit) and nothing else.
import { pickSource } from './data.js';
import { decide } from './gate.js';
import { el, fmt, mountNav } from './nav.js';
import { countUp, flip, icon, paintRange, promptDialog, radioGroup, setRadio, toast } from './ui.js';

mountNav('review.html');
const $ = s => document.querySelector(s);
const src = pickSource();
let cases = [], limit = 0.25, defLimit = 0.25, filter = 'all', sort = 'score-desc', query = '';
const rows = new Map();
const viewerHref = id => (window.BTQC_EMBED ? '#index?case=' : 'viewer.html?show=1&case=') + encodeURIComponent(id);
const DEC = { accept: ['done', 'Accepted'], reject: ['rej', 'Rejected'] };

function decisionPill(c) { const d = DEC[c.review]; return el('span', { class: 'pill ' + (d ? d[0] : 'wait') }, d ? d[1] : 'Awaiting'); }

function makeRow(c) {
  const tr = document.createElement('tr'); tr.dataset.case = c.id;
  const thumb = src.thumbUrl(c.id);
  const tw = el('span', { class: 'thumbwrap' });
  if (thumb) { const img = el('img', { class: 'thumb', alt: '', loading: 'lazy', decoding: 'async', width: '46', height: '46', src: thumb }); img.addEventListener('load', () => img.classList.add('loaded')); tw.append(img); }
  const link = el('a', { href: viewerHref(c.id) }, c.id);
  tr.insertCell().append(el('div', { class: 'casecell' }, tw, el('div', {}, link, el('small', {}, c.group ? 'site group ' + c.group : 'site group unknown'))));
  const pr = tr.insertCell(); pr.className = 'num';
  tr.insertCell().append(el('div', { class: 'mini' }, el('div', { class: 'top' }, el('b'), el('span')), el('div', { class: 'track' }, el('span', { class: 'fill' }), el('span', { class: 'lim' }))));
  tr.insertCell();
  tr.insertCell().append(el('span', { class: 'pill ex' }, c.prediction_source === 'model' ? 'model' : 'example'));
  const v = tr.insertCell(); v.className = 'num'; v.textContent = c.volumes_ml ? fmt(c.volumes_ml.WT, 1) : '–';
  tr.insertCell();
  const act = el('div', { class: 'actions' });
  for (const [k, label, ic] of [['accept', 'Accept', 'check'], ['reject', 'Reject', 'x'], ['note', 'Note', 'note']]) {
    const b = el('button', { class: 'btn sm' + (k === 'note' ? ' ghost' : ''), type: 'button', 'data-action': k, html: icon(ic, 13) }, label);
    b.addEventListener('click', () => submit(c, k));
    act.append(b);
  }
  tr.insertCell().append(act);
  return tr;
}

function updateRow(tr, c, rank, n, dom) {
  const d = decide(c.score, limit), cells = tr.cells;
  tr.classList.toggle('row-flag', d.flag); tr.classList.toggle('row-ok', !d.flag);
  cells[1].innerHTML = ''; cells[1].append(el('span', { class: 'prio' }, '#' + rank), el('small', { style: 'display:block;color:var(--muted);font-size:11px' }, 'of ' + n));
  const mini = cells[2].firstChild, s = c.score;
  mini.querySelector('b').textContent = fmt(s);
  const delta = mini.querySelector('.top span');
  if (s == null) { delta.textContent = 'no score: flagged'; delta.className = 'up'; }
  else { const dd = s - limit; delta.textContent = (dd > 0 ? '+' : dd < 0 ? '−' : '±') + Math.abs(dd).toFixed(3) + (dd > 0 ? ' above limit' : ' within limit'); delta.className = dd > 0 ? 'up' : 'down'; }
  const fill = mini.querySelector('.fill'); fill.style.width = (s == null ? 100 : Math.min(1, s / dom) * 100) + '%'; fill.classList.toggle('hi', d.flag);
  mini.querySelector('.lim').style.left = Math.min(100, limit / dom * 100) + '%';
  cells[3].innerHTML = ''; cells[3].append(el('span', { class: 'pill ' + (d.flag ? 'review' : 'ok'), 'data-flag': d.flag ? 'review' : 'ok' }, d.label));
  cells[6].innerHTML = ''; cells[6].append(decisionPill(c));
}

function visibleList() {
  const withPred = cases.filter(c => c.has_prediction);
  const ranked = withPred.slice().sort((a, b) => (b.score ?? Infinity) - (a.score ?? Infinity));
  const rank = new Map(ranked.map((c, i) => [c.id, i + 1]));
  const q = query.trim().toLowerCase();
  let list = ranked.filter(c => {
    if (q && !(c.id.toLowerCase().includes(q) || (c.group || '').toLowerCase().includes(q))) return false;
    const f = decide(c.score, limit).flag;
    return filter === 'all' || (filter === 'above' && f) || (filter === 'below' && !f) || (filter === 'awaiting' && !c.review) || (filter === 'reviewed' && !!c.review);
  });
  if (sort === 'score-asc') list = list.slice().reverse();
  if (sort === 'id') list.sort((a, b) => a.id.localeCompare(b.id));
  if (sort === 'wt-desc') list.sort((a, b) => ((b.volumes_ml || {}).WT ?? -1) - ((a.volumes_ml || {}).WT ?? -1));
  return { withPred, list, rank };
}

function kpis(withPred) {
  const above = withPred.filter(c => decide(c.score, limit).flag).length, reviewed = withPred.filter(c => c.review).length;
  const box = $('#kpis'), first = !box.children.length;
  const data = [['Cases with predictions', withPred.length, 'accent', 'in the queue'], ['Above the limit', above, 'warm', 'flagged for review'],
    ['At or below the limit', withPred.length - above, 'ok', 'routine check'], ['Awaiting a decision', withPred.length - reviewed, '', 'no accept or reject yet'],
    ['Reviewed', reviewed, '', 'accepted or rejected']];
  if (first) box.innerHTML = data.map(([k, , cls, s]) => `<div class="kpi ${cls}"><div class="k">${k}</div><div class="v">0</div><div class="s">${s}</div></div>`).join('');
  data.forEach(([, v], i) => { const e = box.children[i].querySelector('.v'); if (first) countUp(e, v); else e.textContent = v; });
}

function render() {
  const { withPred, list, rank } = visibleList(), tb = $('#queue tbody');
  const anyExample = withPred.some(c => c.prediction_source !== 'model');
  $('#exNote').hidden = !anyExample;
  if (anyExample) $('#exNote').innerHTML = icon('info', 15) + '<span><b>Examples, not model results.</b> Rows marked "example" use a rule-based outline and a hand-designed uncertainty field. They only demonstrate the review workflow.</span>';
  kpis(withPred);
  if (!withPred.length) {
    tb.innerHTML = ''; const r = tb.insertRow(), td = r.insertCell(); td.colSpan = 8; td.className = 'empty';
    td.textContent = 'No predictions available. Run `make infer` (model) or `make example-predictions` (labeled examples).'; return;
  }
  const dom = Math.max(0.5, limit * 1.6, ...withPred.map(c => (c.score ?? 0) * 1.15));
  const before = [...tb.rows].filter(r => r.dataset.case);
  const view = innerHeight, inView = before.filter(r => { const b = r.getBoundingClientRect(); return b.bottom > -40 && b.top < view + 40; });
  const animate = inView.length < 80;
  const mutate = () => {
    const keep = new Set(list.map(c => c.id));
    for (const r of before) if (!keep.has(r.dataset.case)) r.remove();
    for (const r of [...tb.rows]) if (!r.dataset.case) r.remove();
    for (const c of list) {
      let tr = rows.get(c.id); const fresh = !tr;
      if (!tr) { tr = makeRow(c); rows.set(c.id, tr); }
      updateRow(tr, c, rank.get(c.id), withPred.length, dom);
      if (fresh || !tr.isConnected) { tr.classList.remove('fade-row'); void tr.offsetWidth; tr.classList.add('fade-row'); }
      tb.appendChild(tr);
    }
    if (!list.length) { const r = tb.insertRow(), td = r.insertCell(); td.colSpan = 8; td.className = 'empty'; td.textContent = 'No cases match this filter.'; }
  };
  if (animate) flip(inView, mutate, { duration: 380 }); else mutate();
  $('#countLine').textContent = `Showing ${list.length} of ${withPred.length} cases with predictions.`;
}

async function submit(c, decision) {
  let note = '';
  if (decision === 'note') {
    note = await promptDialog({ title: 'Note for ' + c.id, label: 'Note', hint: 'Do not type patient identifiers. Notes are stored locally.', okLabel: 'Save note' }) || '';
    if (!note) return;
  }
  try {
    await src.addReview({ case_id: c.id, decision, note, reviewer: 'reviewer' });
    $('#msg').textContent = `Saved: ${decision} for ${c.id}.`; $('#msg').classList.remove('err');
    toast(`Saved: ${decision} for ${c.id}`, 'ok');
    if (decision !== 'note') c.review = decision;
    render(); await loadLog();
  } catch (e) { $('#msg').textContent = 'Could not save: ' + e.message; $('#msg').classList.add('err'); toast('Could not save: ' + e.message, 'err', 5000); }
}

async function loadLog() {
  const list = await src.reviews(), tb = $('#log tbody'); tb.innerHTML = '';
  if (!list.length) { const r = tb.insertRow(), td = r.insertCell(); td.colSpan = 8; td.className = 'empty'; td.textContent = 'No decisions yet.'; return; }
  for (const r of list.slice().reverse()) {
    const tr = tb.insertRow();
    const cell = (v, cls) => { const td = tr.insertCell(); if (cls) td.className = cls; if (v instanceof Node) td.append(v); else td.textContent = v ?? '–'; };
    cell(r.id, 'num'); cell((r.created_at || '').replace('T', ' ').replace('+00:00', '')); cell(el('span', { class: 'mono' }, r.case_id));
    cell(el('span', { class: 'pill ' + (DEC[r.decision] ? DEC[r.decision][0] : 'ex') }, r.decision)); cell(r.reviewer);
    cell(fmt(r.score), 'num'); cell(fmt(r.review_limit, 2), 'num'); cell(r.note || '–');
  }
}

function setLimit(v) { limit = v; $('#lim').value = Math.round(v * 100); $('#limO').textContent = v.toFixed(2); paintRange($('#lim')); render(); }

async function init() {
  try {
    const res = await src.cases(); cases = res.cases; limit = defLimit = res.review_limit;
    $('#lim').value = Math.round(limit * 100); $('#limO').textContent = limit.toFixed(2);
    paintRange($('#lim'));
    render(); await loadLog();
  } catch (e) { $('#msg').textContent = 'Case list not available: ' + e.message; $('#msg').classList.add('err'); }
  window.__ready = true;
}
$('#qIcon').outerHTML = icon('search', 15);
$('#lim').addEventListener('input', e => { limit = +e.target.value / 100; $('#limO').textContent = limit.toFixed(2); render(); });
$('#limReset').addEventListener('click', () => setLimit(defLimit));
$('#q').addEventListener('input', e => { query = e.target.value; render(); });
$('#sort').addEventListener('change', e => { sort = e.target.value; render(); });
radioGroup($('#filter'), v => { filter = v; setRadio($('#filter'), v); render(); });
setRadio($('#filter'), 'all');
init();
