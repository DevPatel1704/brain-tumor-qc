"""btqc nnU-Net trainers. Found by nnU-Net through ``nnUNet_extTrainer``
(set by scripts/tasks.py and btqc.train.nnunet_setup.nnunet_env).

All methods use the same budget: ``BTQC_EPOCHS`` epochs (default 100, from
configs/train.yaml), 250 iterations per epoch, and a fixed seed ``BTQC_SEED``.
Seeds are set for Python, NumPy and torch before the network is built.
"""

from __future__ import annotations

import os
import random

import numpy as np
import torch
from batchgeneratorsv2.transforms.intensity.gamma import GammaTransform
from batchgeneratorsv2.transforms.intensity.gaussian_noise import GaussianNoiseTransform
from batchgeneratorsv2.transforms.utils.random import RandomTransform
from batchgeneratorsv2.transforms.utils.remove_label import RemoveLabelTansform
from nnunetv2.training.nnUNetTrainer.nnUNetTrainer import nnUNetTrainer

from btqc.train.augment import BiasFieldTransform, RandomCurveTransform


def _seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _insert_before_label_cleanup(compose, extra):  # type: ignore[no-untyped-def]
    ts = compose.transforms
    idx = next((i for i, t in enumerate(ts) if isinstance(t, RemoveLabelTansform)), len(ts))
    compose.transforms = ts[:idx] + list(extra) + ts[idx:]
    return compose


class nnUNetTrainer_btqc(nnUNetTrainer):
    def __init__(self, plans: dict, configuration: str, fold: int, dataset_json: dict,
                 device: torch.device = torch.device("cuda")):
        self.btqc_seed = int(os.environ.get("BTQC_SEED", "12345")) + int(fold)
        _seed(self.btqc_seed)
        super().__init__(plans, configuration, fold, dataset_json, device)
        self.num_epochs = int(os.environ.get("BTQC_EPOCHS", "100"))
        # nnU-Net writes checkpoint_latest every 50 epochs; save more often so a laptop
        # shutdown loses at most a few epochs (resume with nnUNetv2_train --c).
        self.save_every = int(os.environ.get("BTQC_SAVE_EVERY", "5"))
        if os.environ.get("BTQC_ITERS"):
            self.num_iterations_per_epoch = int(os.environ["BTQC_ITERS"])
        if os.environ.get("BTQC_VAL_ITERS"):
            self.num_val_iterations_per_epoch = int(os.environ["BTQC_VAL_ITERS"])

    def on_train_start(self) -> None:
        super().on_train_start()
        # nnU-Net turns on cudnn.benchmark; its algorithm search allocates large conv
        # workspaces that run a 4 GB laptop GPU out of memory. BTQC_CUDNN_BENCHMARK=0 turns it off.
        if os.environ.get("BTQC_CUDNN_BENCHMARK", "1") == "0":
            torch.backends.cudnn.benchmark = False
            self.print_to_log_file("cudnn.benchmark disabled (BTQC_CUDNN_BENCHMARK=0)")


class nnUNetTrainer_btqcSmoke(nnUNetTrainer_btqc):
    """Gate G3 smoke test: a few tiny epochs, CPU friendly."""

    def __init__(self, plans: dict, configuration: str, fold: int, dataset_json: dict,
                 device: torch.device = torch.device("cuda")):
        super().__init__(plans, configuration, fold, dataset_json, device)
        self.num_epochs = int(os.environ.get("BTQC_EPOCHS", "3"))
        self.num_iterations_per_epoch = int(os.environ.get("BTQC_ITERS", "8"))
        self.num_val_iterations_per_epoch = int(os.environ.get("BTQC_VAL_ITERS", "2"))
        self.save_every = 1


class nnUNetTrainer_btqcStrongAug(nnUNetTrainer_btqc):
    """Mitigation 1: stronger intensity, bias-field and noise augmentation."""

    @staticmethod
    def get_training_transforms(*args, **kwargs):  # type: ignore[no-untyped-def]
        t = nnUNetTrainer.get_training_transforms(*args, **kwargs)
        return _insert_before_label_cleanup(t, [
            RandomTransform(BiasFieldTransform(order=3, max_coeff=0.3), apply_probability=0.3),
            RandomTransform(GaussianNoiseTransform(noise_variance=(0, 0.2), p_per_channel=1,
                                                   synchronize_channels=False), apply_probability=0.3),
            RandomTransform(GammaTransform(gamma=(0.5, 2.0), p_invert_image=0, synchronize_channels=False,
                                           p_per_channel=1, p_retain_stats=1), apply_probability=0.3),
        ])


class nnUNetTrainer_btqcStyle(nnUNetTrainer_btqc):
    """Mitigation 2 (MaxStyle fallback): random monotone intensity-curve style augmentation."""

    @staticmethod
    def get_training_transforms(*args, **kwargs):  # type: ignore[no-untyped-def]
        t = nnUNetTrainer.get_training_transforms(*args, **kwargs)
        return _insert_before_label_cleanup(t, [RandomTransform(RandomCurveTransform(), apply_probability=0.5)])
