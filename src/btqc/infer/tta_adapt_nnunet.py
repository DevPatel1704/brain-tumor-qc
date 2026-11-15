"""Apply instance-norm entropy-minimization TTA (tta_adapt.py) to nnU-Net members.

Not run in this environment (no trained model). The adaptation itself is
unit-tested on a small instance-norm network in tests/unit/test_torch_parts.py.
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np
import torch

from btqc.infer.tta_adapt import adapt


def adapted_members(members: list[Any], image_cxyz: np.ndarray, spacing: tuple[float, ...], steps: int = 10,
                    lr: float = 1e-3) -> list[Any]:
    out = []
    for m in members:
        pred = m.predictor
        net = pred.network
        # nnU-Net normalizes inside its preprocessing; adapt on the z-scored brain image (same as ZScoreNormalization)
        x = image_cxyz.transpose(0, 3, 2, 1).astype(np.float32)
        for c in range(x.shape[0]):
            b = x[c] != 0
            if b.any():
                x[c][b] = (x[c][b] - x[c][b].mean()) / (x[c][b].std() or 1.0)
        dev = next(net.parameters()).device
        patch = tuple(pred.configuration_manager.patch_size)
        pred.network.load_state_dict(pred.list_of_parameters[0])
        adapted = adapt(net, torch.from_numpy(x).to(dev), patch, steps=steps, lr=lr)
        mm = copy.copy(m)
        mm.predictor = copy.copy(pred)
        mm.predictor.network = adapted
        mm.predictor.list_of_parameters = [adapted.state_dict()]
        out.append(mm)
    return out
