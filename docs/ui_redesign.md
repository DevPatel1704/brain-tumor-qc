# Frontend redesign: plan and design system

Scope: `web/` only, plus one additive read-only API route for review-queue thumbnails.
Backend routes, the gate rule, RAS handling, uncertainty scores, the review-limit
config, privacy rules and the synthetic fixtures are unchanged.

## Constraints found in the repository

- Vanilla ES modules, no build step, no runtime network access (R6). The redesign adds
  no dependencies: animation uses CSS transitions, the Web Animations API, cross-document
  View Transitions and `requestAnimationFrame`.
- `scripts/export_demo.py` bundles modules with regexes: imports stay one-line
  `import { a } from './x.js';`, exports stay `export function|class|const|let`.
- Browser tests address elements by id (`#fileIn`, `#msg`, `#thrFlag`, `#flagBox`, `#vWT`,
  `#layUnc`, `#exampleNote`, `#queue`, `#status`, `#synth`, `#disclaimer`) and use
  `window.__btqc.viewer.views[0].off` and `viewer.r3d.gl`; these are kept.
- Real data: 219 unlabeled FeTS 2022 validation cases, rule-based EXAMPLE predictions only,
  no trained model, real evaluation "not run". The UI must keep saying so.

## Pages

| Page | File | Notes |
|---|---|---|
| Home | `index.html`, `src/home.js` | Hero with a live WebGL render of a real case (labeled example outline), live project status from the API, six feature cards. Old `index.html?case=` links redirect to the viewer. |
| Viewer | `viewer.html`, `src/app.js` | Former `index.html`. Rail with Display / Report / Case tabs; stage with layout presets, per-panel zoom, pan, crosshair, smoothing and maximize. |
| Compare | `compare.html`, `src/compare.js` | Two independent viewers; side by side, flicker, split and difference (identical grid only); configurable sync through physical (world) coordinates. |
| Review queue | `review.html` | Thumbnails, search, filters, sort, per-row score-versus-limit meter, note dialog, animated reordering. |
| Generalization, Site risk, Model card | existing files | Same data, consistent visual language; synthetic and example data are badged; unavailable metrics say "unavailable". |

## Display modes (viewer and compare)

1. **Grayscale**: the original window/level mapping (unchanged).
2. **Pseudocolor**: the same windowed intensity passed through a color map (grayscale,
   viridis, inferno, plasma, turbo, cool-to-warm). Voxel values are never modified; zero
   (outside the brain) stays black; the UI labels it as a display transform.
3. **MRI + segmentation**: tumor regions toggled independently (necrotic core, edema,
   enhancing), uncertainty heat map, fill or outline, grayscale or pseudocolor base.

The sequence label comes from the dataset (API cases) or the file name (local files); a
local file whose name does not identify a sequence is shown as "Unknown sequence".

## Module map

`colormaps.js` (transfer functions), `geometry.js` (affines, world mapping, grid
compatibility), `ui.js` (icons, toasts, dialog, FLIP, reveal, reduced motion),
`viewer.js` (panels, display modes, zoom/pan, events), `render3d.js` (+ color LUT, region
mask, adaptive resolution), page controllers `home.js`, `app.js`, `compare.js`,
`review.js`, `explorer.js`, `siterisk.js`, `modelcard.js`.

## Design system

- Dark only. Charcoal background, near-black imaging panels, slate surfaces, a cool-blue
  accent, an amber accent reserved for the crosshair and "needs review", and a teal-green
  for "at or below the limit". Segmentation colors are unchanged.
- System fonts (no network): Segoe UI Variable / SF Pro / Inter for text, ui-monospace /
  Cascadia Mono / SF Mono for coordinates and metadata.
- 4 px spacing grid; radii 6/10/14/20; three shadow levels; hairline borders.
- Motion: 120 to 560 ms, ease-out curves. Entrances use opacity and translate only.
  Continuous motion is limited to the hero render, which pauses off screen and stops under
  `prefers-reduced-motion`. Image interpretation is never animated: slices, crosshair and
  overlays settle within 400 ms.

## Performance

- The 3D view renders at reduced resolution while it is being dragged and at full
  resolution when idle. Once idle it blends up to 10 extra passes, each with a new
  ray offset and sub-pixel jitter, into a running mean (progressive refinement). This
  removes sampling grain and anti-aliases edges. When passes arrive slowly
  (software rendering) it stops after 4 passes.
- 3D style Natural and 3D tumor color Natural use illustrative tissue-like colors; the
  panel shows an "Illustrative tint" badge whenever either is on.
- Slices use smooth (bilinear) interpolation by default; the per-panel toggle switches
  to nearest-neighbour to inspect individual voxels.
- Slice painting builds one 256-entry RGBA lookup table per display change.
- Volumes load their four sequences in parallel.
- The hero renders at 0.6x resolution and at most 30 fps.

## Verification

Existing unit, integration and browser tests, plus new browser tests for the home page,
pseudocolor (voxels unchanged, display colored, background black), region toggles,
zoom, compare sync, difference gating, the queue filters and the thumbnails.
