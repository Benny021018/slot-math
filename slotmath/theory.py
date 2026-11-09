"""Exact theoretical RTP by analytic counting (no randomness).

Key facts used:
1. For one fixed line, the symbol each reel puts on that line is uniformly one of the
   strip positions, independently across reels. So E[line pay] only depends on symbol
   counts per reel -> enumerate 9^5 symbol tuples weighted by probability.
   All 20 lines have the same marginal distribution, so by linearity of expectation
   line RTP = E[pay of ONE line in line-bet units] (20 lines * line_bet / total_bet = 1).
2. Scatter: because S are >= 3 apart on every strip, reel i shows an S with probability
   q_i = 3 * count_S / L_i, independently across reels -> Poisson-binomial count.
3. Free spins: each FS spin retriggers with prob p, adding 10 spins, so the expected
   number of FS spins per session satisfies T = A + p*R*T  ->  T = A / (1 - p*R).
   FS spins use the same strips, so E[FS spin pay] = M * (E_line + E_scatter).
"""
from __future__ import annotations

import itertools
from fractions import Fraction

from .model import Game, line_pay


def symbol_probs(g: Game) -> list[dict[str, Fraction]]:
    out = []
    for strip in g.strips:
        L = len(strip)
        out.append({s: Fraction(strip.count(s), L) for s in g.symbols})
    return out


def line_rtp(g: Game) -> Fraction:
    probs = symbol_probs(g)
    present = [[s for s in g.symbols if p[s] > 0] for p in probs]
    total = Fraction(0)
    for t in itertools.product(*present):
        pay = line_pay(g, t)
        if pay:
            pr = Fraction(1)
            for i, s in enumerate(t):
                pr *= probs[i][s]
            total += pr * pay
    return total


def line_contrib_by_symbol(g: Game) -> dict[str, Fraction]:
    """Split line RTP by which symbol the winning line pays as (for the RTP breakdown)."""
    probs = symbol_probs(g)
    present = [[s for s in g.symbols if p[s] > 0] for p in probs]
    out = {s: Fraction(0) for s in g.paytable}
    W = g.wild
    for t in itertools.product(*present):
        pay = line_pay(g, t)
        if not pay:
            continue
        pr = Fraction(1)
        for i, s in enumerate(t):
            pr *= probs[i][s]
        kw = 0
        while kw < 5 and t[kw] == W:
            kw += 1
        wild_pay = g.paytable[W].get(kw, 0)
        key = W if (kw == 5 or pay == wild_pay) else t[kw]
        out[key] += pr * pay
    return out


def scatter_count_dist(g: Game) -> list[Fraction]:
    dist = [Fraction(1)] + [Fraction(0)] * 5
    for strip in g.strips:
        q = Fraction(g.rows * strip.count(g.scatter), len(strip))
        new = [Fraction(0)] * 6
        for k in range(6):
            new[k] += dist[k] * (1 - q)
            if k < 5:
                new[k + 1] += dist[k] * q
        dist = new
    return dist


def theoretical(g: Game) -> dict:
    e_line = line_rtp(g)
    dist = scatter_count_dist(g)
    e_scat = sum(dist[k] * g.scatter_pay.get(k, 0) for k in range(6))
    p_trig = sum(dist[k] for k in range(g.fs_trigger, 6))
    assert p_trig * g.fs_retrigger < 1, "retrigger makes expected FS length infinite"
    T = Fraction(g.fs_award) / (1 - p_trig * g.fs_retrigger)
    e_fs_spin = g.fs_mult * (e_line + e_scat)
    fs_session = T * e_fs_spin
    fs_contrib = p_trig * fs_session
    rtp = e_line + e_scat + fs_contrib
    by_sym = line_contrib_by_symbol(g)
    assert sum(by_sym.values()) == e_line
    return {
        "rtp": rtp,
        "base_line": e_line,
        "base_scatter": e_scat,
        "free_spins": fs_contrib,
        "p_trigger": p_trig,
        "expected_fs_spins": T,
        "expected_fs_session_win": fs_session,
        "scatter_count_dist": dist,
        "line_by_symbol": by_sym,
    }


def as_float(d):
    if isinstance(d, Fraction):
        return float(d)
    if isinstance(d, dict):
        return {k: as_float(v) for k, v in d.items()}
    if isinstance(d, list):
        return [as_float(v) for v in d]
    return d
