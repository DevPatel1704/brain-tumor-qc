// Small dependency-free SVG charts. At most three colored series per chart
// (validated palette slots 1-3, see styles.css); identity is never color-alone:
// a legend plus direct labels, a hover tooltip on every mark, and a table view.
// opts.badge ('synthetic' | 'example') marks charts whose data are not real results.
const NS = 'http://www.w3.org/2000/svg';
const SERIES = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)'];
const svgEl = (tag, attrs = {}) => { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); return e; };
const f3 = v => (v == null || Number.isNaN(v)) ? '–' : (+v).toFixed(3);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function tooltip(host) {
  let tip = host.querySelector(':scope > .ctip');
  if (!tip) { tip = document.createElement('div'); tip.className = 'ctip'; tip.setAttribute('role', 'status'); host.style.position = 'relative'; host.appendChild(tip); }
  return {
    show(html, x, y) { tip.innerHTML = html; tip.style.display = 'block'; const w = host.clientWidth; tip.style.left = Math.max(4, Math.min(x + 14, w - tip.offsetWidth - 4)) + 'px'; tip.style.top = Math.max(4, y - tip.offsetHeight - 10) + 'px'; },
    hide() { tip.style.display = 'none'; },
  };
}

function header(host, title, badge) {
  host.innerHTML = '';
  if (!title && !badge) return;
  const h = document.createElement('h2'); h.textContent = title || ''; host.appendChild(h);
  if (badge) { const b = document.createElement('span'); b.className = 'badge ribbon ' + (badge === 'synthetic' ? 'synth' : 'example'); b.textContent = badge === 'synthetic' ? 'Synthetic' : 'Example'; host.appendChild(b); }
}

function tableView(host, columns, rows, caption) {
  const d = document.createElement('details'); d.style.marginTop = '8px';
  d.innerHTML = '<summary>Table view</summary>';
  const wrap = document.createElement('div'); wrap.className = 'table-wrap';
  const t = document.createElement('table'); t.className = 'data';
  if (caption) { const c = t.createCaption(); c.textContent = caption; c.className = 'vh'; }
  const tr = t.createTHead().insertRow(); for (const c of columns) { const th = document.createElement('th'); th.textContent = c; tr.appendChild(th); }
  const tb = t.createTBody();
  for (const r of rows) { const row = tb.insertRow(); for (const v of r) { const td = row.insertCell(); td.textContent = typeof v === 'number' ? f3(v) : v; if (typeof v === 'number') td.className = 'num'; } }
  wrap.appendChild(t); d.appendChild(wrap); host.appendChild(d);
}

function legend(host, names) {
  if (names.length < 2) return;
  const l = document.createElement('div'); l.className = 'chart-legend';
  names.forEach((n, i) => { const s = document.createElement('span'); s.innerHTML = `<i style="background:${SERIES[i]}"></i>`; s.append(n); l.appendChild(s); });
  host.appendChild(l);
}

// Horizontal bars with optional CI whiskers. items: [{label, value, lo, hi, note, na}]
export function barChart(host, items, { title, xLabel = '', domain = [0, 1], unit = '', badge = null, color = 0 } = {}) {
  header(host, title, badge);
  const W = 560, rowH = 30, padL = 150, padR = 66, padT = 6, padB = 32, H = padT + padB + rowH * Math.max(1, items.length);
  const svg = svgEl('svg', { viewBox: `0 0 ${W} ${H}`, class: 'chart', role: 'img', 'aria-label': title || 'bar chart' });
  const x = v => padL + (W - padL - padR) * (v - domain[0]) / (domain[1] - domain[0]);
  for (let t = 0; t <= 4; t++) {
    const v = domain[0] + (domain[1] - domain[0]) * t / 4, gx = x(v);
    svg.appendChild(svgEl('line', { x1: gx, x2: gx, y1: padT, y2: H - padB, class: Math.abs(v) < 1e-12 ? 'zero' : 'axis' }));
    const tx = svgEl('text', { x: gx, y: H - padB + 15, 'text-anchor': 'middle' }); tx.textContent = +v.toFixed(2); svg.appendChild(tx);
  }
  const xl = svgEl('text', { x: (padL + W - padR) / 2, y: H - 3, 'text-anchor': 'middle' }); xl.textContent = xLabel; svg.appendChild(xl);
  const tip = tooltip(host);
  items.forEach((it, i) => {
    const y = padT + i * rowH + 7, h = rowH - 14;
    const lab = svgEl('text', { x: padL - 10, y: y + h / 2 + 4, 'text-anchor': 'end', style: 'fill:var(--ink-2)' }); lab.textContent = it.label; svg.appendChild(lab);
    const base = Math.min(Math.max(0, domain[0]), domain[1]);
    if (it.value == null || Number.isNaN(it.value)) {
      const na = svgEl('text', { x: x(base) + 8, y: y + h / 2 + 4, style: 'fill:var(--muted);font-style:italic' }); na.textContent = it.na || 'not defined'; svg.appendChild(na);
    } else {
      const x0 = Math.min(x(base), x(it.value)), w = Math.abs(x(it.value) - x(base));
      svg.appendChild(svgEl('rect', { x: x0, y, width: Math.max(w, 1), height: h, rx: 3, fill: SERIES[color], class: 'bar' + (it.value < base ? ' neg' : ''), style: `--i:${i}` }));
    }
    if (it.lo != null && it.hi != null) {
      const g = svgEl('g', { class: 'dot' });
      g.appendChild(svgEl('line', { x1: x(it.lo), x2: x(it.hi), y1: y + h / 2, y2: y + h / 2, stroke: 'var(--ink)', 'stroke-width': 1.5 }));
      for (const v of [it.lo, it.hi]) g.appendChild(svgEl('line', { x1: x(v), x2: x(v), y1: y + 2, y2: y + h - 2, stroke: 'var(--ink)', 'stroke-width': 1.5 }));
      svg.appendChild(g);
    }
    if (it.value != null && !Number.isNaN(it.value)) {
      const val = svgEl('text', { x: x(Math.max(it.value, it.hi ?? it.value, base)) + 7, y: y + h / 2 + 4, style: 'fill:var(--ink);font-family:var(--mono)' }); val.textContent = f3(it.value) + unit; svg.appendChild(val);
    }
    const hit = svgEl('rect', { x: 0, y: y - 6, width: W, height: rowH, fill: 'transparent' });
    hit.addEventListener('pointermove', e => { const r = host.getBoundingClientRect(); tip.show(`<b>${esc(it.label)}</b><br>${f3(it.value)}${unit}${it.lo != null ? ` (95% CI ${f3(it.lo)} to ${f3(it.hi)})` : ''}${it.note ? '<br><span style="color:var(--muted)">' + esc(it.note) + '</span>' : ''}`, e.clientX - r.left, e.clientY - r.top); });
    hit.addEventListener('pointerleave', () => tip.hide());
    svg.appendChild(hit);
  });
  host.appendChild(svg);
  tableView(host, ['Item', 'Value', 'CI low', 'CI high', 'Note'], items.map(it => [it.label, it.value ?? (it.na || 'not defined'), it.lo ?? '–', it.hi ?? '–', it.note || '']), title);
}

// Lines (<= 3 series): series = [{name, points: [[x, y], ...]}]; crosshair tooltip.
export function lineChart(host, series, { title, xLabel = '', yLabel = '', xDomain = [0, 1], yDomain = [0, 1], diagonal = false, badge = null } = {}) {
  header(host, title, badge);
  series = series.slice(0, 3);
  legend(host, series.map(s => s.name));
  const W = 560, H = 320, padL = 50, padR = 92, padT = 10, padB = 38;
  const svg = svgEl('svg', { viewBox: `0 0 ${W} ${H}`, class: 'chart', role: 'img', 'aria-label': title || 'line chart' });
  const x = v => padL + (W - padL - padR) * (v - xDomain[0]) / (xDomain[1] - xDomain[0]);
  const y = v => H - padB - (H - padT - padB) * (v - yDomain[0]) / (yDomain[1] - yDomain[0]);
  for (let t = 0; t <= 4; t++) {
    const vy = yDomain[0] + (yDomain[1] - yDomain[0]) * t / 4, vx = xDomain[0] + (xDomain[1] - xDomain[0]) * t / 4;
    svg.appendChild(svgEl('line', { x1: padL, x2: W - padR, y1: y(vy), y2: y(vy), class: t === 0 ? 'zero' : 'axis' }));
    const ty = svgEl('text', { x: padL - 8, y: y(vy) + 4, 'text-anchor': 'end' }); ty.textContent = +vy.toFixed(2); svg.appendChild(ty);
    const tx = svgEl('text', { x: x(vx), y: H - padB + 15, 'text-anchor': 'middle' }); tx.textContent = +vx.toFixed(2); svg.appendChild(tx);
  }
  const xl = svgEl('text', { x: (padL + W - padR) / 2, y: H - 3, 'text-anchor': 'middle' }); xl.textContent = xLabel; svg.appendChild(xl);
  const yl = svgEl('text', { x: 12, y: (padT + H - padB) / 2, 'text-anchor': 'middle', transform: `rotate(-90 12 ${(padT + H - padB) / 2})` }); yl.textContent = yLabel; svg.appendChild(yl);
  if (diagonal) svg.appendChild(svgEl('line', { x1: x(xDomain[0]), y1: y(yDomain[0]), x2: x(xDomain[1]), y2: y(yDomain[1]), stroke: 'var(--muted)', 'stroke-dasharray': '4 4', opacity: 0.6 }));
  const ends = [];
  series.forEach((s, i) => {
    const pts = s.points.filter(p => p[1] != null && !Number.isNaN(p[1]));
    if (!pts.length) return;
    let len = 0; for (let k = 1; k < pts.length; k++) len += Math.hypot(x(pts[k][0]) - x(pts[k - 1][0]), y(pts[k][1]) - y(pts[k - 1][1]));
    svg.appendChild(svgEl('polyline', { points: pts.map(p => `${x(p[0])},${y(p[1])}`).join(' '), fill: 'none', stroke: SERIES[i], 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round', class: 'line', style: `--len:${Math.ceil(len) + 2}` }));
    for (const p of pts.length <= 20 ? pts : []) svg.appendChild(svgEl('circle', { cx: x(p[0]), cy: y(p[1]), r: 3.5, fill: SERIES[i], stroke: 'var(--surface)', 'stroke-width': 2, class: 'dot' }));
    const last = pts[pts.length - 1];
    ends.push({ name: s.name, x: x(last[0]) + 7, y: y(last[1]) + 4 });
  });
  ends.sort((a, b) => a.y - b.y);
  for (let k = 1; k < ends.length; k++) if (ends[k].y - ends[k - 1].y < 13) ends[k].y = ends[k - 1].y + 13;
  for (const e of ends) { const dl = svgEl('text', { x: e.x, y: e.y, style: 'fill:var(--ink-2)' }); dl.textContent = e.name; svg.appendChild(dl); }
  const cross = svgEl('line', { y1: padT, y2: H - padB, stroke: 'var(--muted)', 'stroke-width': 1, visibility: 'hidden' }); svg.appendChild(cross);
  const tip = tooltip(host);
  const hit = svgEl('rect', { x: padL, y: padT, width: W - padL - padR, height: H - padT - padB, fill: 'transparent' });
  hit.addEventListener('pointermove', e => {
    const b = svg.getBoundingClientRect(), sx = (e.clientX - b.left) * W / b.width, xv = xDomain[0] + (sx - padL) / (W - padL - padR) * (xDomain[1] - xDomain[0]);
    cross.setAttribute('x1', sx); cross.setAttribute('x2', sx); cross.setAttribute('visibility', 'visible');
    const lines = series.map((s, i) => { let best = null; for (const p of s.points) if (best == null || Math.abs(p[0] - xv) < Math.abs(best[0] - xv)) best = p; return best ? `<span style="color:${SERIES[i]}">●</span> ${esc(s.name)}: <b>${f3(best[1])}</b> at ${f3(best[0])}` : ''; });
    const r = host.getBoundingClientRect(); tip.show(lines.join('<br>'), e.clientX - r.left, e.clientY - r.top);
  });
  hit.addEventListener('pointerleave', () => { tip.hide(); cross.setAttribute('visibility', 'hidden'); });
  svg.appendChild(hit);
  host.appendChild(svg);
  const rows = []; for (const s of series) for (const p of s.points) rows.push([s.name, p[0], p[1]]);
  tableView(host, ['Series', xLabel || 'x', yLabel || 'y'], rows, title);
}

export function notRun(host, title, message) {
  header(host, title, null);
  const p = document.createElement('p'); p.className = 'notrun';
  p.innerHTML = '<svg class="ic" width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true"><circle cx="8" cy="8" r="6.2"/><path d="M5.5 8h5"/></svg>';
  const s = document.createElement('span'); s.textContent = message || 'Not run.'; p.appendChild(s);
  host.appendChild(p);
}
