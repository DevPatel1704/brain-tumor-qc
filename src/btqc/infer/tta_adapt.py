"""Mitigation 4: test-time adaptation for instance-normalized networks.

nnU-Net uses instance normalization, so batch-norm statistic adaptation does
not apply (instance norm already uses the statistics of the test image).
Instead we adapt only the affine parameters (weight, bias) of every
InstanceNorm layer by minimizing the mean binary entropy of the sigmoid
outputs on random patches of the test case (TENT-style objective, Wang et al.,
ICLR 2021), for a few steps, then predict with the adapted copy. The original
model is never modified, and each case starts from the trained weights.
"""

from __future__ import annotations

import copy
from collections.abc import Callable

import numpy as np
import torch
from torch import nn


def norm_affine_parameters(model: nn.Module) -> list[nn.Parameter]:
    params: list[nn.Parameter] = []
    for m in model.modules():
        if isinstance(m, nn.InstanceNorm1d | nn.InstanceNorm2d | nn.InstanceNorm3d) and m.affine:
            params += [m.weight, m.bias]
    return params


def configure_for_adaptation(model: nn.Module) -> tuple[nn.Module, list[nn.Parameter]]:
    adapted = copy.deepcopy(model)
    adapted.train()  # instance norm behaves the same in train/eval; dropout (if any) stays as configured below
    for m in adapted.modules():
        if isinstance(m, nn.Dropout | nn.Dropout2d | nn.Dropout3d):
            m.eval()
    for p in adapted.parameters():
        p.requires_grad_(False)
    params = norm_affine_parameters(adapted)
    for p in params:
        p.requires_grad_(True)
    return adapted, params


def entropy_loss(logits: torch.Tensor) -> torch.Tensor:
    p = torch.sigmoid(logits).clamp(1e-6, 1 - 1e-6)
    return -(p * torch.log(p) + (1 - p) * torch.log(1 - p)).mean()


def adapt(model: nn.Module, image: torch.Tensor, patch_size: tuple[int, ...], steps: int = 10, lr: float = 1e-3,
          batch: int = 2, seed: int = 0, output_transform: Callable[[object], torch.Tensor] | None = None,
          foreground_only: bool = True) -> nn.Module:
    """Return an adapted copy of ``model``. ``image`` is (C, *spatial). Patches are sampled
    from the nonzero (brain) region when ``foreground_only``."""
    adapted, params = configure_for_adaptation(model)
    if not params:
        return adapted
    opt = torch.optim.Adam(params, lr=lr)
    rng = np.random.default_rng(seed)
    spatial = image.shape[1:]
    ps = [min(p, s) for p, s in zip(patch_size, spatial)]
    fg = torch.nonzero(image.abs().sum(0) > 0) if foreground_only else None
    for _ in range(steps):
        xs = []
        for _ in range(batch):
            if fg is not None and len(fg):
                c = fg[int(rng.integers(0, len(fg)))].tolist()
                lo = [int(np.clip(ci - p // 2, 0, s - p)) for ci, p, s in zip(c, ps, spatial)]
            else:
                lo = [int(rng.integers(0, s - p + 1)) for p, s in zip(ps, spatial)]
            sl = tuple(slice(a, a + p) for a, p in zip(lo, ps))
            xs.append(image[(slice(None),) + sl])
        out = adapted(torch.stack(xs))
        logits = output_transform(out) if output_transform else (out[0] if isinstance(out, list | tuple) else out)
        loss = entropy_loss(logits)
        opt.zero_grad()
        loss.backward()
        opt.step()
    adapted.eval()
    for p in params:
        p.requires_grad_(False)
    return adapted
