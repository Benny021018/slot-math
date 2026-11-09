"""Vectorised Monte Carlo simulator (numpy). Independent of theory.py's line_pay.

Each "round" = one paid base spin plus the full free-spin session it may trigger.
Round win (in total-bet units) is the unit of analysis for RTP, hit rate and variance.
"""
from __future__ import annotations

import numpy as np

from .model import Game


class Sim:
    def __init__(self, g: Game):
        self.g = g
        self.sym_id = {s: i for i, s in enumerate(g.symbols)}
        self.W = self.sym_id[g.wild]
        self.S = self.sym_id[g.scatter]
        self.strips = [np.array([self.sym_id[s] for s in st], dtype=np.int8) for st in g.strips]
        self.lens = np.array([len(s) for s in g.strips])
        self.lines = np.array(g.lines, dtype=np.int64)  # (20, 5)
        n_sym = len(g.symbols)
        self.pt = np.zeros((n_sym, 6), dtype=np.int64)  # pay[sym, count]
        for s, p in g.paytable.items():
            for k, v in p.items():
                self.pt[self.sym_id[s], k] = v
        self.sp = np.zeros(6, dtype=np.int64)
        for k, v in g.scatter_pay.items():
            self.sp[k] = v

    def spin(self, rng: np.random.Generator, n: int):
        """Return (win_in_line_bets[int64], scatter_count[int], stops[n,5]) for n spins."""
        stops = self.draw_stops(rng, n)
        return self.evaluate(stops) + (stops,)

    def draw_stops(self, rng: np.random.Generator, n: int) -> np.ndarray:
        return np.stack([rng.integers(0, L, size=n) for L in self.lens], axis=1)

    def evaluate(self, stops: np.ndarray):
        """Return (win_in_line_bets, scatter_count) for given stop positions (n, 5)."""
        n = stops.shape[0]
        window = np.empty((n, 5, 3), dtype=np.int8)
        for r in range(5):
            for row in range(3):
                window[:, r, row] = self.strips[r][(stops[:, r] + row) % self.lens[r]]
        # line symbols: (n, 20, 5)
        ls = window[:, np.arange(5)[None, :], self.lines]
        is_w = ls == self.W
        # leading wild run length
        lead_w = np.cumprod(is_w, axis=2).sum(axis=2)  # (n,20)
        wild_pay = self.pt[self.W][lead_w]
        idx = np.minimum(lead_w, 4)
        first = np.take_along_axis(ls, idx[..., None], axis=2)[..., 0]
        match = is_w | (ls == first[..., None])
        run = np.cumprod(match, axis=2).sum(axis=2)
        sym_pay = self.pt[first.astype(np.int64), run]
        sym_pay = np.where((lead_w == 5) | (first == self.S), 0, sym_pay)
        line_win = self.combine(wild_pay, sym_pay).sum(axis=1)  # line-bet units
        n_s = self.count_scatter(window)
        total_line_bets = line_win + self.sp[n_s] * self.g.n_lines  # everything in line bets
        return total_line_bets, n_s

    # Small hooks so tests/mutants.py can inject realistic bugs.
    def combine(self, wild_pay, sym_pay):
        return np.maximum(wild_pay, sym_pay)

    def count_scatter(self, window):
        return (window == self.S).sum(axis=(1, 2))

    def run(self, n_rounds: int, seed: int, batch: int = 500_000):
        """Simulate n_rounds paid rounds. Returns dict of arrays (total-bet units)."""
        g = self.g
        rng = np.random.default_rng(seed)
        nl = g.n_lines
        base = np.empty(n_rounds)
        fsw = np.zeros(n_rounds)
        fs_spins = np.zeros(n_rounds, dtype=np.int64)
        stop_counts = [np.zeros(L, dtype=np.int64) for L in self.lens]
        done = 0
        while done < n_rounds:
            m = min(batch, n_rounds - done)
            w, ns, stops = self.spin(rng, m)
            for r in range(5):
                stop_counts[r] += np.bincount(stops[:, r], minlength=self.lens[r])
            base[done:done + m] = w / nl
            trig = np.flatnonzero(ns >= g.fs_trigger)
            remaining = np.full(trig.size, g.fs_award, dtype=np.int64)
            acc = np.zeros(trig.size)
            cnt = np.zeros(trig.size, dtype=np.int64)
            active = remaining > 0
            while active.any():
                a = np.flatnonzero(active)
                fw, fns, _ = self.spin(rng, a.size)
                acc[a] += g.fs_mult * fw / nl
                cnt[a] += 1
                remaining[a] -= 1
                remaining[a] += np.where(fns >= g.fs_trigger, g.fs_retrigger, 0)
                active = remaining > 0
            fsw[done + trig] = acc
            fs_spins[done + trig] = cnt
            done += m
        return {"base": base, "fs": fsw, "fs_spins": fs_spins, "stop_counts": stop_counts}
