import numpy as np
import pytest

from btqc.eval.shift import (
    CENTERS,
    case_histogram,
    estimate_performance,
    fit_gap_model,
    frechet_distance,
    ks_hist,
    profile_distances,
    wasserstein_hist,
)
from btqc.eval.stats import bootstrap_ci, bootstrap_diff_ci, paired_wilcoxon, spearman


def test_histogram_normalized_and_scale_invariant():
    rng = np.random.default_rng(0)
    v = np.zeros((20, 20, 20))
    v[5:15, 5:15, 5:15] = rng.normal(500, 50, (10, 10, 10))
    h1 = case_histogram(v)
    h2 = case_histogram(v * 3.0 + (v != 0) * 100)  # affine intensity change inside brain
    assert h1.sum() == pytest.approx(1.0)
    np.testing.assert_allclose(h1, h2, atol=1e-12)


def test_wasserstein_hist_matches_shift():
    p = np.zeros(len(CENTERS))
    q = np.zeros(len(CENTERS))
    p[40] = 1
    q[45] = 1
    assert wasserstein_hist(p, q) == pytest.approx(5 * (CENTERS[1] - CENTERS[0]))
    assert ks_hist(p, q) == 1.0
    assert wasserstein_hist(p, p) == 0.0
    d = profile_distances({"t1": p, "t2": p}, {"t1": q, "t2": p})
    assert d["w1_t2"] == 0 and d["w1_mean"] == pytest.approx(d["w1_t1"] / 2)


def test_frechet_distance():
    rng = np.random.default_rng(0)
    a = rng.normal(0, 1, (500, 4))
    b = rng.normal(0, 1, (500, 4))
    c = rng.normal(2, 1, (500, 4))
    assert frechet_distance(a, b) < 0.2
    assert frechet_distance(a, c) == pytest.approx(16, rel=0.15)


def test_gap_model_and_estimate():
    x = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
    y = 0.02 + 0.5 * x
    m = fit_gap_model(x, y)
    assert m["b"] == pytest.approx(0.5) and m["loo_rmse"] == pytest.approx(0, abs=1e-9)
    e = estimate_performance(m, 0.6, 0.9)
    assert e["estimate"] == pytest.approx(0.9 - 0.32)
    assert np.isnan(fit_gap_model(x[:2], y[:2])["a"])


def test_bootstrap_ci_and_diff():
    rng = np.random.default_rng(0)
    a = rng.normal(0.9, 0.05, 200)
    b = rng.normal(0.8, 0.05, 200)
    ci = bootstrap_ci(a, n_boot=500)
    assert ci["lo"] < 0.9 < ci["hi"] and ci["n"] == 200
    d = bootstrap_diff_ci(a, b, n_boot=500)
    assert d["lo"] > 0.05 and d["diff"] == pytest.approx(a.mean() - b.mean())
    assert np.isnan(bootstrap_ci(np.array([np.nan]))["mean"])


def test_paired_wilcoxon_and_spearman():
    rng = np.random.default_rng(0)
    a = rng.normal(0.8, 0.05, 40)
    w = paired_wilcoxon(a + 0.03, a)
    assert w["p"] < 1e-6 and w["n"] == 40
    assert np.isnan(paired_wilcoxon(a, a)["p"])
    s = spearman(np.arange(10), np.arange(10) ** 2)
    assert s["rho"] == pytest.approx(1.0)


def test_holm_adjustment():
    from btqc.eval.stats import holm

    adj = holm([0.01, 0.04, 0.03, float("nan")])
    assert adj[0] == pytest.approx(0.03) and adj[2] == pytest.approx(0.06) and adj[1] == pytest.approx(0.06)
    assert np.isnan(adj[3])
    assert holm([]) == []
