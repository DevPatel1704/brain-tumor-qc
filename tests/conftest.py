"""Shared fixtures. All data here is synthetic (btqc.data.fixtures)."""

from __future__ import annotations

from pathlib import Path

import pytest

from btqc.data.fixtures import make_dataset


@pytest.fixture(scope="session")
def synthetic_root(tmp_path_factory) -> Path:
    """12 labeled synthetic cases in the FeTS training layout plus a fake partition CSV."""
    root = tmp_path_factory.mktemp("synthetic_raw")
    make_dataset(root, n_cases=12)
    return root


@pytest.fixture(scope="session")
def synthetic_wrapped_root(tmp_path_factory) -> Path:
    """4 unlabeled synthetic cases in the wrapped validation layout."""
    root = tmp_path_factory.mktemp("synthetic_wrapped")
    make_dataset(root, n_cases=4, layout="wrapped", with_seg=False)
    return root
