"""Deliberately buggy simulators ("mutants") — each mimics a mistake that AI-generated or
hand-written slot code really makes. The validation pipeline must catch every one of them."""
from __future__ import annotations

import dataclasses

import numpy as np

from .model import Game
from .sim import Sim


class OffByOneStop(Sim):
    """rng.integers(0, L - 1): the last strip position can never be drawn."""
    name = "RNG off-by-one (last stop never drawn)"

    def draw_stops(self, rng, n):
        return np.stack([rng.integers(0, L - 1, size=n) for L in self.lens], axis=1)


class WildPayIgnored(Sim):
    """Pays only the substituted symbol, forgets the 'max with wild-run pay' rule."""
    name = "Wild-run pay ignored (max rule missing)"

    def combine(self, wild_pay, sym_pay):
        return np.where(sym_pay > 0, sym_pay, wild_pay)


class ScatterMiddleRowOnly(Sim):
    """Counts scatters only on the middle row (treats S like a line symbol)."""
    name = "Scatter counted on middle row only"

    def count_scatter(self, window):
        return (window[:, :, 1] == self.S).sum(axis=1)


def no_retrigger(g: Game) -> Sim:
    s = Sim(dataclasses.replace(g, fs_retrigger=0))
    s.name = "Free-spin retrigger not implemented"
    return s


def all_mutants(g: Game) -> list[Sim]:
    return [OffByOneStop(g), WildPayIgnored(g), ScatterMiddleRowOnly(g), no_retrigger(g)]
