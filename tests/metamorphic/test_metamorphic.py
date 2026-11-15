"""Metamorphic tests.

1. Rule-based example predictor (deterministic, always runs): translating the
   input translates the mask; global intensity scaling leaves it unchanged;
   flipping the input and un-flipping the output gives the same mask. This
   checks the geometry and intensity handling of the prediction path.
2. The nnU-Net model trained by the G3 smoke test (slow; skipped if the
   checkpoint does not exist). A 3-epoch toy model on synthetic data is far
   from converged, so its tolerances are loose and stated below.
"""

from pathlib import Path

import numpy as np
import pytest

from btqc.config import REPO_ROOT
from btqc.data.fixtures import make_case
from btqc.eval.metrics import dice
from btqc.infer.example_rules import predict_example

SHIFT = (3, -2, 1)
TOL_TRANSLATE = 0.95  # Dice between shift(pred(x)) and pred(shift(x)), rule predictor
TOL_SCALE = 0.99      # global x1.05 intensity scaling, rule predictor
TOL_FLIP = 0.99


def _vols(seed=0, shape=(48, 52, 40)):
    c = make_case("m", shape=shape, seed=seed)
    return {k: v.astype(np.float32) for k, v in c.images.items()}


def _shift(a, s):
    out = np.zeros_like(a)
    src = tuple(slice(max(0, -d), a.shape[i] - max(0, d)) for i, d in enumerate(s))
    dst = tuple(slice(max(0, d), a.shape[i] - max(0, -d)) for i, d in enumerate(s))
    out[dst] = a[src]
    return out


def _wt(vols):
    prob, _ = predict_example(vols)
    return prob[0] > 0.5


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_translation_translates_mask(seed):
    v = _vols(seed)
    a = _shift(_wt(v), SHIFT)
    b = _wt({k: _shift(x, SHIFT) for k, x in v.items()})
    assert a.any() and dice(a, b) >= TOL_TRANSLATE


@pytest.mark.parametrize("factor", [0.95, 1.05])
def test_global_intensity_scaling(factor):
    v = _vols(3)
    assert dice(_wt(v), _wt({k: x * factor for k, x in v.items()})) >= TOL_SCALE


@pytest.mark.parametrize("axis", [0, 1, 2])
def test_flip_consistency(axis):
    v = _vols(4)
    a = _wt(v)
    b = np.flip(_wt({k: np.ascontiguousarray(np.flip(x, axis)) for k, x in v.items()}), axis)
    assert dice(a, b) >= TOL_FLIP


SMOKE = REPO_ROOT / "data" / "nnUNet_results" / "Dataset990_BtqcFixture" / \
    "nnUNetTrainer_btqcSmoke__nnUNetPlans__3d_fullres" / "fold_0" / "checkpoint_final.pth"


@pytest.mark.slow
@pytest.mark.skipif(not SMOKE.exists(), reason="smoke model not trained (python scripts/train_smoke.py)")
def test_smoke_model_metamorphic():
    """Toy nnU-Net from gate G3. Tolerances: translation Dice >= 0.6, scaling >= 0.8, flip >= 0.6
    (the model saw 3 tiny epochs; these check the inference path, not model quality)."""
    from btqc.infer.predict import NnunetMember

    m = NnunetMember(Path(SMOKE).parents[1], 0, device="cpu")
    v = _vols(7, shape=(48, 48, 40))
    img = np.stack([v[s] for s in ("t1", "t1ce", "t2", "flair")])
    wt = lambda x: m(x, (1.0, 1.0, 1.0))[0] > 0.5  # noqa: E731
    base = wt(img)
    if not base.any():
        pytest.skip("toy model predicts no tumor on this case")
    sh = wt(np.stack([_shift(c, SHIFT) for c in img]))
    assert dice(_shift(base, SHIFT), sh) >= 0.6
    assert dice(base, wt(img * 1.05)) >= 0.8
    assert dice(base, np.flip(wt(np.ascontiguousarray(np.flip(img, 1))), 0)) >= 0.6
