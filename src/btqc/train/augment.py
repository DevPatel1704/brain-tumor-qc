"""Extra intensity augmentations for the mitigation trainers (batchgeneratorsv2 API).

* ``BiasFieldTransform``: smooth multiplicative field exp(sum_k c_k * P_k(x, y, z)),
  polynomial basis up to ``order``, coefficients uniform in +-``max_coeff``.
* ``RandomCurveTransform``: per-channel random monotone cubic Bezier intensity
  curve (style randomization). Used as the documented fallback for MaxStyle,
  which needs an adversarial style generator and could not be integrated in
  nnU-Net's training loop within the compute budget (docs/deviations.md).

Both act on z-scored patches: intensities are mapped to [0, 1] with the
channel's min/max, transformed, and mapped back, so value ranges stay stable.
"""

from __future__ import annotations

import torch
from batchgeneratorsv2.transforms.base.basic_transform import ImageOnlyTransform


def _poly_basis(shape: tuple[int, ...], order: int, device: torch.device) -> torch.Tensor:
    axes = [torch.linspace(-1, 1, s, device=device) for s in shape]
    grids = torch.meshgrid(*axes, indexing="ij")
    terms = []
    if len(shape) == 3:
        x, y, z = grids
        for i in range(order + 1):
            for j in range(order + 1 - i):
                for k in range(order + 1 - i - j):
                    if i + j + k:
                        terms.append(x**i * y**j * z**k)
    else:
        x, y = grids
        for i in range(order + 1):
            for j in range(order + 1 - i):
                if i + j:
                    terms.append(x**i * y**j)
    return torch.stack(terms)


class BiasFieldTransform(ImageOnlyTransform):
    def __init__(self, order: int = 3, max_coeff: float = 0.3, p_per_channel: float = 1.0):
        super().__init__()
        self.order, self.max_coeff, self.p_per_channel = order, max_coeff, p_per_channel

    def get_parameters(self, **data_dict) -> dict:
        img = data_dict["image"]
        basis = _poly_basis(tuple(img.shape[1:]), self.order, img.device)
        coeffs = (torch.rand(img.shape[0], basis.shape[0], device=img.device) * 2 - 1) * self.max_coeff
        apply = torch.rand(img.shape[0], device=img.device) < self.p_per_channel
        return {"basis": basis, "coeffs": coeffs, "apply": apply}

    def _apply_to_image(self, img: torch.Tensor, **params) -> torch.Tensor:
        basis, coeffs, apply = params["basis"], params["coeffs"], params["apply"]
        for c in torch.nonzero(apply).flatten().tolist():
            field = torch.exp(torch.tensordot(coeffs[c], basis, dims=1)).to(img.dtype)
            lo = img[c].min()
            img[c] = (img[c] - lo) * field + lo
        return img


class RandomCurveTransform(ImageOnlyTransform):
    def __init__(self, p_per_channel: float = 1.0, n_points: int = 256):
        super().__init__()
        self.p_per_channel, self.n_points = p_per_channel, n_points

    def get_parameters(self, **data_dict) -> dict:
        img = data_dict["image"]
        c = img.shape[0]
        # control points p1, p2 in [0, 1]^2 with x sorted -> monotone curve from (0,0) to (1,1)
        pts = torch.rand(c, 2, 2)
        pts[:, :, 0] = torch.sort(pts[:, :, 0], dim=1).values
        invert = torch.rand(c) < 0.0  # no inversion: keep tumor contrast polarity
        apply = torch.rand(c) < self.p_per_channel
        return {"pts": pts, "apply": apply, "invert": invert}

    def _curve(self, p1: torch.Tensor, p2: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        t = torch.linspace(0, 1, self.n_points)
        x = 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t**2 * p2[0] + t**3
        y = 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t**2 * p2[1] + t**3
        x, idx = torch.sort(x)
        y = torch.cummax(y[idx], dim=0).values  # enforce monotone
        return x, y

    def _apply_to_image(self, img: torch.Tensor, **params) -> torch.Tensor:
        for c in torch.nonzero(params["apply"]).flatten().tolist():
            ch = img[c]
            lo, hi = ch.min(), ch.max()
            if hi <= lo:
                continue
            u = ((ch - lo) / (hi - lo)).clamp(0, 1)
            x, y = self._curve(params["pts"][c, 0], params["pts"][c, 1])
            x, y = x.to(img.device), y.to(img.device)
            i = torch.clamp(torch.searchsorted(x, u.reshape(-1)), 1, len(x) - 1)
            x0, x1, y0, y1 = x[i - 1], x[i], y[i - 1], y[i]
            w = ((u.reshape(-1) - x0) / (x1 - x0 + 1e-8)).clamp(0, 1)
            v = (y0 + w * (y1 - y0)).reshape(ch.shape)
            img[c] = (v * (hi - lo) + lo).to(img.dtype)
        return img
