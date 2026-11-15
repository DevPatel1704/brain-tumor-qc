// App shell: top navigation and the research-prototype disclaimer on every page,
// plus small DOM helpers shared by the page controllers.
import { logo } from './ui.js';

const PAGES = [
  ['index.html', 'Home'],
  ['viewer.html', 'Viewer'],
  ['compare.html', 'Compare'],
  ['review.html', 'Review queue'],
  ['explorer.html', 'Generalization'],
  ['site-risk.html', 'Site risk'],
  ['model-card.html', 'Model card'],
];

export const DISCLAIMER = 'Research prototype only. Not a medical device and not for diagnosis.';

export function mountNav(current) {
  const embed = !!window.BTQC_EMBED;
  let bar = document.getElementById('topbar');
  if (!bar) { bar = document.createElement('header'); bar.id = 'topbar'; document.body.prepend(bar); }
  bar.className = 'topbar';
  bar.innerHTML = `<a class="brand" href="${embed ? '#' : 'index.html'}" aria-label="BTQC home">${logo(24)}<span class="wordmark">BTQC</span><span class="brand-sub">Brain Tumor Quantification &amp; Confidence</span></a>
<nav class="nav" aria-label="Pages"></nav>
<p class="disclaimer" id="disclaimer"><span class="ddot" aria-hidden="true"></span><b>Research prototype only.</b> <span>Not a medical device and not for diagnosis.</span></p>`;
  const nav = bar.querySelector('nav');
  // the single-file export contains only the viewer page
  for (const [href, label] of embed ? [['viewer.html', 'Viewer (single-file demo)']] : PAGES) {
    const a = document.createElement('a');
    a.href = embed ? '#' : href; a.className = 'nav-link';
    a.textContent = label;
    if (href === current) { a.setAttribute('aria-current', 'page'); a.insertAdjacentHTML('afterbegin', '<span class="nav-pill" aria-hidden="true"></span>'); }
    nav.appendChild(a);
  }
  const cur = nav.querySelector('[aria-current]');
  if (cur && nav.scrollWidth > nav.clientWidth) cur.scrollIntoView({ block: 'nearest', inline: 'center' });
  return bar;
}

export function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') e.className = v; else if (k === 'text') e.textContent = v; else if (k === 'html') e.innerHTML = v; else e.setAttribute(k, v);
  }
  for (const k of kids) e.append(k instanceof Node ? k : document.createTextNode(String(k)));
  return e;
}

export const fmt = (v, d = 3) => (v === null || v === undefined || Number.isNaN(v)) ? '–' : Number(v).toFixed(d);
