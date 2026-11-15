"""Ensemble membership and the leakage rule.

nnU-Net fold indices in our ``splits_final.json`` are laid out as
``index = group_position * n_members + member``: every site group's split is
repeated ``n_members`` times so that independently initialized models
(different random seeds) can be trained on the same fold. An ensemble that
predicts group g may only use indices of g (never models from other folds,
which have seen g during training).
"""

from __future__ import annotations


def member_indices(fold_order: list[str], group: str, n_members: int) -> list[int]:
    g = fold_order.index(group)
    return [g * n_members + k for k in range(n_members)]


def group_of_index(fold_order: list[str], index: int, n_members: int) -> str:
    return fold_order[index // n_members]


def check_ensemble(fold_order: list[str], group: str, indices: list[int], n_members: int) -> None:
    bad = [i for i in indices if group_of_index(fold_order, i, n_members) != group]
    if bad:
        raise ValueError(f"leakage: ensemble for {group!r} contains models of other folds: {bad}")
