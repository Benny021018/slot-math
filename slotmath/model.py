"""Game model: load config, validate it, and evaluate one line (scalar reference version)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Game:
    version: str
    symbols: list[str]
    wild: str
    scatter: str
    paytable: dict[str, dict[int, int]]
    scatter_pay: dict[int, int]
    lines: list[list[int]]
    strips: list[list[str]]
    rows: int
    fs_trigger: int
    fs_award: int
    fs_retrigger: int
    fs_mult: int
    config_hash: str

    @property
    def n_lines(self) -> int:
        return len(self.lines)


def load(path: str | Path) -> Game:
    raw_text = Path(path).read_text(encoding="utf-8")
    c = yaml.safe_load(raw_text)
    fs = c["free_spins"]
    g = Game(
        version=c["model_version"],
        symbols=c["symbols"],
        wild=c["wild"],
        scatter=c["scatter"],
        paytable={s: {int(k): int(v) for k, v in p.items()} for s, p in c["paytable"].items()},
        scatter_pay={int(k): int(v) for k, v in c["scatter_pay"].items()},
        lines=c["lines"],
        strips=c["strips"],
        rows=c["rows"],
        fs_trigger=fs["trigger_min_scatter"],
        fs_award=fs["award"],
        fs_retrigger=fs["retrigger_award"],
        fs_mult=fs["multiplier"],
        config_hash=hashlib.sha256(raw_text.encode()).hexdigest()[:12],
    )
    validate(g)
    return g


def validate(g: Game) -> None:
    assert g.n_lines == 20, "spec says 20 lines"
    assert len({tuple(l) for l in g.lines}) == g.n_lines, "duplicate line pattern"
    assert all(len(l) == 5 and all(0 <= r < g.rows for r in l) for l in g.lines)
    for strip in g.strips:
        assert set(strip) <= set(g.symbols), "unknown symbol on strip"
        # Scatter formula in theory.py assumes at most one S visible per reel.
        idx = [i for i, s in enumerate(strip) if s == g.scatter]
        L = len(strip)
        for a in idx:
            for b in idx:
                if a != b:
                    assert min((a - b) % L, (b - a) % L) >= g.rows, "S too close on strip"


def line_pay(g: Game, syms: tuple[str, ...] | list[str]) -> int:
    """Pay of one line in LINE-bet multiples. Reference (slow, readable) implementation."""
    W = g.wild
    kw = 0
    while kw < 5 and syms[kw] == W:
        kw += 1
    wild_pay = g.paytable[W].get(kw, 0)
    if kw == 5:
        return wild_pay
    first = syms[kw]
    if first == g.scatter:  # wild does not substitute scatter
        return wild_pay
    k = kw
    while k < 5 and syms[k] in (W, first):
        k += 1
    return max(wild_pay, g.paytable[first].get(k, 0))


def export_flat(g: Game, path: str | Path) -> None:
    """Write a plain-text spec for the independent C++ implementation (no shared code)."""
    sym_id = {s: i for i, s in enumerate(g.symbols)}
    out = [f"{len(g.symbols)} {sym_id[g.wild]} {sym_id[g.scatter]}"]
    for s in g.symbols:
        p = g.paytable.get(s, {})
        out.append(" ".join(str(p.get(k, 0)) for k in range(6)))
    out.append(" ".join(str(g.scatter_pay.get(k, 0)) for k in range(6)))
    out.append(f"{g.fs_trigger} {g.fs_award} {g.fs_retrigger} {g.fs_mult}")
    out.append(str(g.n_lines))
    out += [" ".join(map(str, l)) for l in g.lines]
    for strip in g.strips:
        out.append(f"{len(strip)} " + " ".join(str(sym_id[s]) for s in strip))
    Path(path).write_text("\n".join(out) + "\n")


def meta(g: Game) -> dict:
    return {"model_version": g.version, "config_sha256_12": g.config_hash}


if __name__ == "__main__":
    import sys
    gm = load(sys.argv[1])
    print(json.dumps(meta(gm)))
