// Shared UI primitives: icons, logo, toasts, a prompt dialog, radio groups with a
// sliding indicator, FLIP layout animation and scroll reveal. No dependencies.
export const reducedMotion = () => !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

const ICONS = {
  'zoom-in': '<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5 14 14M7 5v4M5 7h4"/>',
  'zoom-out': '<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5 14 14M5 7h4"/>',
  fit: '<path d="M2 5.5V3a1 1 0 0 1 1-1h2.5M10.5 2H13a1 1 0 0 1 1 1v2.5M14 10.5V13a1 1 0 0 1-1 1h-2.5M5.5 14H3a1 1 0 0 1-1-1v-2.5"/>',
  cross: '<path d="M8 1.5v4.2M8 10.3v4.2M1.5 8h4.2M10.3 8h4.2"/><circle cx="8" cy="8" r=".8"/>',
  smooth: '<path d="M1.8 10.5c2.1-6.5 4.1-6.5 6.2 0s4.1 6.5 6.2 0"/>',
  max: '<path d="M9.5 2H14v4.5M6.5 14H2V9.5M14 2 9.2 6.8M2 14l4.8-4.8"/>',
  min: '<path d="M14 2 9.6 6.4M9.6 3v3.4H13M2 14l4.4-4.4M6.4 13V9.6H3"/>',
  grid: '<rect x="2" y="2" width="5" height="5" rx="1"/><rect x="9" y="2" width="5" height="5" rx="1"/><rect x="2" y="9" width="5" height="5" rx="1"/><rect x="9" y="9" width="5" height="5" rx="1"/>',
  focus: '<rect x="2" y="2" width="8" height="12" rx="1"/><path d="M12 2.5h2M12 8h2M12 13.5h2"/>',
  single: '<rect x="2" y="2" width="12" height="12" rx="1.5"/>',
  reset: '<path d="M2.6 8a5.4 5.4 0 1 0 1.6-3.8L2.6 5.8"/><path d="M2.6 2.4v3.4H6"/>',
  fullscreen: '<path d="M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4"/>',
  sliders: '<path d="M2.5 4h6M12 4h1.5M2.5 12h1.5M7.5 12h6M2.5 8h2M8 8h5.5"/><circle cx="10.2" cy="4" r="1.6"/><circle cx="5.8" cy="12" r="1.6"/><circle cx="6.2" cy="8" r="1.6"/>',
  info: '<circle cx="8" cy="8" r="6.2"/><path d="M8 7.2v3.8M8 5h.01"/>',
  search: '<circle cx="7" cy="7" r="4.5"/><path d="m10.5 10.5 3.5 3.5"/>',
  check: '<path d="m3 8.5 3 3 7-7"/>',
  x: '<path d="m4 4 8 8M12 4l-8 8"/>',
  note: '<path d="M10.5 2.5 13.5 5.5 6 13H3v-3z"/>',
  'arrow-right': '<path d="M3 8h10M9 4l4 4-4 4"/>',
  'chev-left': '<path d="M10 3 5 8l5 5"/>',
  'chev-right': '<path d="m6 3 5 5-5 5"/>',
  upload: '<path d="M8 10.5V2.5M4.5 6 8 2.5 11.5 6M2.5 10.5v2a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1v-2"/>',
  play: '<path d="M5 3.2v9.6L12.5 8z" fill="currentColor"/>',
  pause: '<path d="M5.5 3v10M10.5 3v10"/>',
  swap: '<path d="M3 5.5h10M10 2.5l3 3-3 3M13 10.5H3M6 7.5l-3 3 3 3"/>',
  keyboard: '<rect x="1.5" y="4" width="13" height="8" rx="1.5"/><path d="M4 6.5h.01M6.5 6.5h.01M9 6.5h.01M11.5 6.5h.01M5 9.5h6"/>',
  layers: '<path d="m8 2 6 3-6 3-6-3z"/><path d="m2 8 6 3 6-3M2 11l6 3 6-3"/>',
  cube: '<path d="m8 1.8 5.5 3.1v6.2L8 14.2l-5.5-3.1V4.9z"/><path d="M8 8v6.2M8 8l5.5-3.1M8 8 2.5 4.9"/>',
  split: '<rect x="2" y="2.5" width="12" height="11" rx="1.5"/><path d="M8 1v14"/>',
  pulse: '<path d="M1.5 8h3l1.5-4 3 8 1.5-4h4"/>',
  chart: '<path d="M2.5 13.5h11M4.5 11V8M8 11V4.5M11.5 11V6.5"/>',
  globe: '<circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c1.8 2 1.8 10 0 12M8 2c-1.8 2-1.8 10 0 12"/>',
  doc: '<path d="M4 1.8h5l3 3v9.4H4z"/><path d="M9 1.8v3h3M6 8h4M6 10.5h4"/>',
  queue: '<path d="M2.5 4h11M2.5 8h11M2.5 12h7"/>',
  viewer: '<rect x="2" y="2" width="5.2" height="5.2" rx="1"/><rect x="8.8" y="2" width="5.2" height="5.2" rx="1"/><rect x="2" y="8.8" width="5.2" height="5.2" rx="1"/><circle cx="11.4" cy="11.4" r="2.6"/>',
  shield: '<path d="M8 1.8 13 3.6v4.1c0 3-2.2 5.4-5 6.5-2.8-1.1-5-3.5-5-6.5V3.6z"/>',
  folder: '<path d="M2 4.5a1 1 0 0 1 1-1h3l1.5 1.5H13a1 1 0 0 1 1 1V12a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1z"/>',
  target: '<circle cx="8" cy="8" r="5.5"/><circle cx="8" cy="8" r="2"/>',
  link: '<path d="M6.5 9.5 9.5 6.5M7 4.5l1-1a2.8 2.8 0 0 1 4 4l-1 1M9 11.5l-1 1a2.8 2.8 0 0 1-4-4l1-1"/>',
};

export function icon(name, size = 16, cls = '') {
  return `<svg class="ic${cls ? ' ' + cls : ''}" width="${size}" height="${size}" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ''}</svg>`;
}

// Mark: three orthogonal planes through a sphere, with the region of interest.
export function logo(size = 24) {
  return `<svg class="logo" width="${size}" height="${size}" viewBox="0 0 32 32" fill="none" aria-hidden="true">
<defs><linearGradient id="btqcLg" x1="4" y1="4" x2="28" y2="28" gradientUnits="userSpaceOnUse"><stop stop-color="#a9c8ff"/><stop offset="1" stop-color="#5b8fe8"/></linearGradient></defs>
<circle cx="16" cy="16" r="12.5" stroke="url(#btqcLg)" stroke-width="1.7"/>
<ellipse cx="16" cy="16" rx="12.5" ry="4.6" stroke="url(#btqcLg)" stroke-width="1.2" opacity=".55"/>
<ellipse cx="16" cy="16" rx="4.6" ry="12.5" stroke="url(#btqcLg)" stroke-width="1.2" opacity=".55"/>
<circle cx="20.2" cy="12.4" r="3" fill="#f0b34f"/><circle cx="20.2" cy="12.4" r="5.2" stroke="#f0b34f" stroke-opacity=".35"/></svg>`;
}

let toastBox = null;
export function toast(text, kind = 'info', ms = 3200) {
  if (!toastBox) {
    toastBox = document.createElement('div'); toastBox.className = 'toasts'; toastBox.setAttribute('role', 'status'); toastBox.setAttribute('aria-live', 'polite');
    document.body.appendChild(toastBox);
  }
  const t = document.createElement('div');
  t.className = 'toast ' + kind;
  t.innerHTML = icon(kind === 'err' ? 'x' : kind === 'ok' ? 'check' : 'info', 15);
  const s = document.createElement('span'); s.textContent = text; t.appendChild(s);
  toastBox.appendChild(t);
  requestAnimationFrame(() => t.classList.add('in'));
  setTimeout(() => { t.classList.remove('in'); t.classList.add('out'); setTimeout(() => t.remove(), 260); }, ms);
}

// Modal text prompt. Resolves to the text, or null when cancelled.
export function promptDialog({ title, label, hint = '', okLabel = 'Save', maxLength = 2000 }) {
  return new Promise(resolve => {
    const d = document.createElement('dialog');
    d.className = 'dlg';
    d.innerHTML = `<form method="dialog"><h2></h2><label class="field"><span class="flabel"></span><textarea rows="4" maxlength="${maxLength}"></textarea></label><p class="help"></p>
      <div class="dlg-actions"><button class="btn ghost" value="cancel" type="submit">Cancel</button><button class="btn primary" value="ok" type="submit"></button></div></form>`;
    d.querySelector('h2').textContent = title; d.querySelector('.flabel').textContent = label;
    d.querySelector('.help').textContent = hint; d.querySelector('.primary').textContent = okLabel;
    document.body.appendChild(d);
    const ta = d.querySelector('textarea');
    d.addEventListener('close', () => { const v = d.returnValue === 'ok' ? ta.value.trim() : null; d.remove(); resolve(v || null); });
    d.showModal(); ta.focus();
  });
}

// Radio group of buttons ([role=radio][data-value]) with arrow-key navigation and,
// for .seg containers, a sliding indicator under the checked button.
export function radioGroup(box, onSelect) {
  const items = () => [...box.querySelectorAll('[role=radio]')].filter(b => !b.disabled);
  box.addEventListener('click', e => { const b = e.target.closest('[role=radio]'); if (b && box.contains(b) && !b.disabled) onSelect(b.dataset.value, b); });
  box.addEventListener('keydown', e => {
    const list = items(), i = list.indexOf(document.activeElement); if (i < 0) return;
    let j = -1;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') j = (i + 1) % list.length;
    if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') j = (i + list.length - 1) % list.length;
    if (j >= 0) { e.preventDefault(); list[j].focus(); onSelect(list[j].dataset.value, list[j]); }
  });
  if (box.classList.contains('seg') && 'ResizeObserver' in window) new ResizeObserver(() => placeThumb(box)).observe(box);
}

function placeThumb(box) {
  let th = box.querySelector(':scope > .seg-thumb');
  const on = box.querySelector('[role=radio][aria-checked="true"]');
  if (!th) { th = document.createElement('span'); th.className = 'seg-thumb'; th.setAttribute('aria-hidden', 'true'); box.prepend(th); }
  if (!on || !on.offsetWidth) { th.style.opacity = '0'; return; }
  th.style.opacity = '1';
  th.style.transform = `translate(${on.offsetLeft}px, ${on.offsetTop}px)`;
  th.style.width = on.offsetWidth + 'px'; th.style.height = on.offsetHeight + 'px';
}

export function setRadio(box, value) {
  for (const b of box.querySelectorAll('[role=radio]')) {
    const on = b.dataset.value === String(value);
    b.setAttribute('aria-checked', String(on)); b.tabIndex = on ? 0 : -1;
  }
  if (box.classList.contains('seg')) placeThumb(box);
}

// FLIP: animate elements from their old box to the new one after mutate() changes layout.
export function flip(els, mutate, { duration = 340, easing = 'cubic-bezier(.2,.75,.2,1)' } = {}) {
  const list = [...els], before = new Map(list.map(e => [e, e.getBoundingClientRect()]));
  mutate();
  if (reducedMotion() || !Element.prototype.animate) return;
  for (const e of list) {
    const a = before.get(e), b = e.getBoundingClientRect();
    if (!b.width || !b.height) continue;
    if (!a.width || !a.height) { e.animate([{ opacity: 0, transform: 'scale(.97)' }, { opacity: 1, transform: 'none' }], { duration, easing }); continue; }
    const dx = a.left - b.left, dy = a.top - b.top, sx = a.width / b.width, sy = a.height / b.height;
    if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5 && Math.abs(sx - 1) < 0.005 && Math.abs(sy - 1) < 0.005) continue;
    e.animate([{ transformOrigin: '0 0', transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})` }, { transformOrigin: '0 0', transform: 'none' }], { duration, easing });
  }
}

// Adds .in to [data-reveal] elements as they scroll into view (immediately under reduced motion).
export function reveal(root = document) {
  const els = [...root.querySelectorAll('[data-reveal]:not(.in)')];
  if (reducedMotion() || !('IntersectionObserver' in window)) { for (const e of els) e.classList.add('in'); return; }
  const io = new IntersectionObserver(entries => {
    for (const en of entries) if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); }
  }, { rootMargin: '0px 0px -6% 0px', threshold: 0.06 });
  for (const e of els) io.observe(e);
}

// Counts a number up to its value (static under reduced motion).
export function countUp(el, to, digits = 0, ms = 900) {
  const f = v => Number(v).toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  if (reducedMotion() || !isFinite(to)) { el.textContent = isFinite(to) ? f(to) : '–'; return; }
  const t0 = performance.now();
  const tick = now => { const k = Math.min(1, (now - t0) / ms), e = 1 - Math.pow(1 - k, 3); el.textContent = f(to * e); if (k < 1) requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
}

export function debounce(fn, ms) { let t = 0; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

// Filled track for range inputs (CSS reads --p).
export function paintRange(el) {
  const min = +el.min || 0, max = el.max === '' ? 100 : +el.max, v = +el.value;
  el.style.setProperty('--p', (max > min ? (v - min) / (max - min) * 100 : 0) + '%');
}
export function paintRanges(root = document) { for (const r of root.querySelectorAll('input[type=range]')) paintRange(r); }
document.addEventListener('input', e => { if (e.target && e.target.type === 'range') paintRange(e.target); });
