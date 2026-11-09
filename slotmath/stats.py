"""Statistics helpers: confidence intervals, sample-size planning, acceptance tests."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats


def mean_ci(x: np.ndarray, conf: float = 0.95) -> tuple[float, float, float, float]:
    """Return (mean, std, half_width, z) for a normal-approximation CI (CLT)."""
    n = x.size
    m = float(x.mean())
    s = float(x.std(ddof=1))
    z = stats.norm.ppf(0.5 + conf / 2)
    return m, s, z * s / math.sqrt(n), z


def required_n(sigma: float, half_width: float, conf: float = 0.95) -> int:
    """n such that a conf-level CI of the mean has the requested half-width."""
    z = stats.norm.ppf(0.5 + conf / 2)
    return math.ceil((z * sigma / half_width) ** 2)


def z_test(sim_mean: float, theory: float, sigma: float, n: int) -> tuple[float, float]:
    """Two-sided z test of H0: true mean == theory. Returns (z, p_value)."""
    se = sigma / math.sqrt(n)
    z = (sim_mean - theory) / se
    return z, 2 * (1 - stats.norm.cdf(abs(z)))


def chi2_uniform(counts: np.ndarray) -> tuple[float, float]:
    """Chi-square goodness-of-fit of reel-stop counts against a uniform distribution."""
    res = stats.chisquare(counts)
    return float(res.statistic), float(res.pvalue)


def proportion_ci(k: int, n: int, conf: float = 0.95) -> tuple[float, float, float]:
    """Wilson score interval for a probability (e.g. hit rate)."""
    z = stats.norm.ppf(0.5 + conf / 2)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, c - h, c + h
