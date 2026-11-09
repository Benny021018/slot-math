"""Regression tests. Run: pytest -q
Golden values are tied to config/game_v1.yaml. If you change parameters on purpose,
bump model_version, re-run validate.py, review the report, then update the goldens."""
import json
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from slotmath import model, mutants, theory
from slotmath.sim import Sim

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "game_v1.yaml"
CPP = ROOT / "cpp" / "slot"


@pytest.fixture(scope="module")
def g():
    return model.load(CFG)


@pytest.fixture(scope="module")
def spec(g, tmp_path_factory):
    subprocess.run(["g++", "-O2", "-std=c++17", "-o", str(CPP), str(ROOT / "cpp" / "slot.cpp")], check=True)
    p = tmp_path_factory.mktemp("spec") / "game.spec"
    model.export_flat(g, p)
    return p


# ---------- rule unit tests (hand-checked windows) ----------
@pytest.mark.parametrize("line,expected", [
    (["W", "W", "W", "W", "W"], 1000),          # all wild
    (["W", "W", "W", "L4", "L4"], 50),           # WWW (50) beats L4 x5 (40)
    (["W", "H1", "H1", "H1", "H1"], 500),        # wild substitutes -> H1 x5
    (["W", "W", "S", "H1", "H1"], 0),            # wild does not substitute scatter; WW pays nothing
    (["W", "W", "W", "S", "H1"], 50),            # WWW then scatter: wild-run pay only
    (["L1", "L1", "W", "L2", "L2"], 5),          # L1 L1 W -> L1 x3
    (["L1", "L2", "L1", "L1", "L1"], 0),         # broken at reel 2
    (["H2", "H2", "H2", "H2", "W"], 300),        # trailing wild extends run
    (["S", "S", "S", "S", "S"], 0),              # scatter never pays on a line
])
def test_line_pay(g, line, expected):
    assert model.line_pay(g, line) == expected


# ---------- golden theory ----------
def test_theory_golden(g):
    th = theory.theoretical(g)
    assert th["rtp"] == Fraction(3223228345, 3334927869)
    assert th["p_trigger"] == Fraction(173, 9464)
    assert th["base_line"] + th["base_scatter"] == Fraction(575885, 862407)


def test_enumeration_equals_theory(g, spec):
    enum = json.loads(subprocess.run([str(CPP), "enum", str(spec)], capture_output=True, text=True, check=True).stdout)
    N = enum["combinations"]
    base = Fraction(sum(int(w) * c for w, c in enum["hist"].items()), N * g.n_lines)
    th = theory.theoretical(g)
    assert base == th["base_line"] + th["base_scatter"]


# ---------- cross-implementation ----------
def test_python_vs_cpp_windows(g, spec):
    s = Sim(g)
    stops = s.draw_stops(np.random.default_rng(2024), 20_000)
    pw, pn = s.evaluate(stops)
    out = subprocess.run([str(CPP), "eval", str(spec)], input="\n".join(" ".join(map(str, r)) for r in stops),
                         capture_output=True, text=True, check=True).stdout
    cw = np.loadtxt(out.splitlines(), dtype=np.int64)
    assert (cw[:, 0] == pw).all() and (cw[:, 1] == pn).all()


@pytest.mark.parametrize("mutant_cls", [mutants.WildPayIgnored, mutants.ScatterMiddleRowOnly])
def test_window_check_catches_logic_bugs(g, mutant_cls):
    """Small RTP bugs can hide in noisy MC, but an exact per-window diff exposes them immediately."""
    ok, bad = Sim(g), mutant_cls(g)
    stops = ok.draw_stops(np.random.default_rng(5), 20_000)
    assert (ok.evaluate(stops)[0] != bad.evaluate(stops)[0]).any()


# ---------- reproducibility (same seed -> same numbers) ----------
def test_python_sim_seed_golden(g):
    r = Sim(g).run(100_000, 42)
    assert float((r["base"] + r["fs"]).mean()) == pytest.approx(0.9694425, abs=1e-12)


def test_cpp_mc_seed_golden(spec):
    out = json.loads(subprocess.run([str(CPP), "mc", str(spec), "100000", "1"], capture_output=True, text=True, check=True).stdout)
    assert out["rtp"] == pytest.approx(0.9517365, abs=1e-10)
    assert out["trigger_rate"] == pytest.approx(0.01793, abs=1e-12)
