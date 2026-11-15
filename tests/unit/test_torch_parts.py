"""Unit tests for torch-based parts: test-time adaptation, augmentation transforms, TTA accumulation."""

import numpy as np
import pytest

torch = pytest.importorskip("torch")
from torch import nn  # noqa: E402

from btqc.infer.tta import MemberAccumulator, flip_sets, predict_with_flips  # noqa: E402
from btqc.infer.tta_adapt import adapt, entropy_loss, norm_affine_parameters  # noqa: E402

pytestmark = pytest.mark.torch


class Tiny(nn.Module):
    def __init__(self):
        super().__init__()
        self.c1 = nn.Conv3d(2, 4, 3, padding=1)
        self.n1 = nn.InstanceNorm3d(4, affine=True)
        self.c2 = nn.Conv3d(4, 3, 1)

    def forward(self, x):
        return self.c2(torch.relu(self.n1(self.c1(x))))


def test_adapt_changes_only_norm_affine_and_reduces_entropy():
    torch.manual_seed(0)
    m = Tiny()
    before = {k: v.clone() for k, v in m.state_dict().items()}
    img = torch.randn(2, 12, 12, 12)
    with torch.no_grad():
        e0 = entropy_loss(m(img[None])).item()
    a = adapt(m, img, (8, 8, 8), steps=30, lr=0.05, foreground_only=False)
    with torch.no_grad():
        e1 = entropy_loss(a(img[None])).item()
    assert e1 < e0
    for k, v in m.state_dict().items():  # original untouched
        assert torch.equal(v, before[k])
    sa = a.state_dict()
    assert torch.equal(sa["c1.weight"], before["c1.weight"]) and torch.equal(sa["c2.weight"], before["c2.weight"])
    assert not torch.equal(sa["n1.weight"], before["n1.weight"])
    assert len(norm_affine_parameters(m)) == 2


def test_flip_tta_identity_model_is_consistent():
    """Metamorphic: a flip-equivariant predictor gives identical members, so MI is zero."""
    rng = np.random.default_rng(0)
    img = rng.random((4, 6, 5, 4)).astype(np.float32)
    pred = lambda x: 1 / (1 + np.exp(-x[:3]))  # noqa: E731 - voxel-wise, hence flip-equivariant
    acc = MemberAccumulator()
    predict_with_flips(pred, img, flip_sets(), acc)
    assert acc.n == 8
    np.testing.assert_allclose(acc.mean(), pred(img), atol=1e-6)
    assert acc.mutual_information().max() < 1e-5


def test_bias_and_curve_transforms_shape_and_range():
    pytest.importorskip("batchgeneratorsv2")
    from btqc.train.augment import BiasFieldTransform, RandomCurveTransform

    torch.manual_seed(0)
    img = torch.randn(4, 10, 9, 8)
    out = BiasFieldTransform(order=2, max_coeff=0.3)(image=img.clone())["image"]
    assert out.shape == img.shape and torch.isfinite(out).all() and not torch.allclose(out, img)
    out2 = RandomCurveTransform()(image=img.clone())["image"]
    assert out2.shape == img.shape
    for c in range(4):  # range preserved and monotone mapping keeps the order of voxels
        assert out2[c].min() >= img[c].min() - 1e-4 and out2[c].max() <= img[c].max() + 1e-4
        o = torch.argsort(img[c].reshape(-1))
        assert (torch.diff(out2[c].reshape(-1)[o]) >= -1e-4).all()
