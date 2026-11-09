"""End-to-end validation pipeline. Re-run after ANY parameter change:

    python validate.py config/game_v1.yaml

Steps
  1. Exact theory (analytic counting, rational arithmetic)
  2. Exact enumeration of all base-game stop combinations (independent C++ code)
     -> must equal theory EXACTLY; also gives exact hit rate and exact variance
  3. Per-window cross-check Python vs C++ on random stops (must match 100%)
  4. Sample-size plan from the exact sigma and a target precision
  5. Monte Carlo: Python (1 seed) + C++ (K seeds) -> CI / z-test / CI coverage
  6. RNG / stop uniformity chi-square
  7. Mutation test: inject known bugs, confirm the pipeline flags them
  8. Volatility / extreme-scenario / session analysis
Writes reports/<version>/report.md and results.json (with seeds, n, config hash, git-free metadata).
"""
from __future__ import annotations

import json
import math
import platform
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np

from slotmath import model, mutants, stats, theory
from slotmath.sim import Sim

ROOT = Path(__file__).parent
CPP = ROOT / "cpp" / "slot"

# ---- run settings (recorded in the report) ---------------------------------
TARGET_HALF_WIDTH = 0.001     # +-0.10% RTP
CONF = 0.95
PY_ROUNDS, PY_SEED = 5_000_000, 20261109
CPP_SEEDS = list(range(1, 21))  # 20 independent seeds
MUTANT_ROUNDS, MUTANT_SEED = 2_000_000, 7
CROSSCHECK_N, CROSSCHECK_SEED = 200_000, 99
SESSION_LEN, SESSION_BANKROLL = 200, 50  # spins, total-bet units


def build_cpp():
    subprocess.run(["g++", "-O2", "-std=c++17", "-o", str(CPP), str(ROOT / "cpp" / "slot.cpp")], check=True)


def cpp(*args, stdin=None) -> str:
    return subprocess.run([str(CPP), *map(str, args)], input=stdin, capture_output=True,
                          text=True, check=True).stdout


def exact_from_enum(g, enum, th):
    """Exact moments of the round win X = B + I*F using enumeration + branching process."""
    N = enum["combinations"]
    nl = g.n_lines
    hist = {int(k): v for k, v in enum["hist"].items()}
    hist_t = {int(k): v for k, v in enum["hist_trigger"].items()}
    EB = Fraction(sum(w * c for w, c in hist.items()), N * nl)
    EB2 = Fraction(sum(w * w * c for w, c in hist.items()), N * nl * nl)
    EBI = Fraction(sum(w * c for w, c in hist_t.items()), N * nl)
    p = Fraction(sum(hist_t.values()), N)
    M, A, R = g.fs_mult, g.fs_award, g.fs_retrigger
    # One FS spin pays Y = M*B and retriggers with indicator I (same strips).
    EY, EY2, EYI = M * EB, M * M * EB2, M * EBI
    # Z = Y + I * (sum of R iid Z): value of one FS spin incl. everything it spawns.
    EZ = EY / (1 - R * p)
    EZ2 = (EY2 + 2 * R * EYI * EZ + p * R * (R - 1) * EZ * EZ) / (1 - R * p)
    EF, EF2 = A * EZ, A * EZ2 + A * (A - 1) * EZ * EZ          # F = sum of A iid Z
    EX = EB + p * EF
    EX2 = EB2 + 2 * EBI * EF + p * EF2
    hit = Fraction(N - hist.get(0, 0) + hist_t.get(0, 0), N)   # pays OR triggers
    return {"base_rtp": EB, "p_trigger": p, "rtp": EX, "var": EX2 - EX * EX,
            "hit_rate": hit, "base_hit_rate": Fraction(N - hist.get(0, 0), N),
            "fs_session_mean": EF, "fs_session_std": math.sqrt(EF2 - EF * EF)}


def pct(x, d=4):
    return f"{100 * float(x):.{d}f}%"


def main(cfg_path: str):
    t0 = time.time()
    g = model.load(cfg_path)
    out_dir = ROOT / "reports" / f"v{g.version}"
    out_dir.mkdir(parents=True, exist_ok=True)
    spec = out_dir / "game.spec"
    model.export_flat(g, spec)
    build_cpp()
    R: dict = {"meta": {**model.meta(g), "config": cfg_path, "python": platform.python_version(),
                        "numpy": np.__version__, "run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "settings": {"target_half_width": TARGET_HALF_WIDTH, "conf": CONF,
                                     "py_rounds": PY_ROUNDS, "py_seed": PY_SEED, "cpp_seeds": CPP_SEEDS,
                                     "mutant_rounds": MUTANT_ROUNDS, "mutant_seed": MUTANT_SEED}}}
    checks: list[tuple[str, bool, str]] = []

    # 1. theory
    th = theory.theoretical(g)
    R["theory"] = theory.as_float(th)
    rtp = th["rtp"]

    # 2. enumeration
    enum = json.loads(cpp("enum", spec))
    ex = exact_from_enum(g, enum, th)
    base_theory = th["base_line"] + th["base_scatter"]
    checks.append(("Enumeration base RTP == analytic base RTP (exact rational)", ex["base_rtp"] == base_theory,
                   f"{ex['base_rtp']} vs {base_theory}"))
    checks.append(("Enumeration P(trigger) == analytic P(trigger) (exact rational)", ex["p_trigger"] == th["p_trigger"],
                   f"{ex['p_trigger']}"))
    checks.append(("Enumeration total RTP == analytic total RTP (exact rational)", ex["rtp"] == rtp, f"{float(rtp):.12f}"))
    sigma = math.sqrt(ex["var"])
    R["exact"] = {k: (float(v) if isinstance(v, Fraction) else v) for k, v in ex.items()}
    R["exact"]["sigma"] = sigma
    R["exact"]["rtp_fraction"] = f"{rtp.numerator}/{rtp.denominator}"
    R["exact"]["combinations"] = enum["combinations"]
    R["exact"]["max_base_win"] = max(int(k) for k in enum["hist"]) / g.n_lines

    # 3. per-window cross-check
    rng = np.random.default_rng(CROSSCHECK_SEED)
    sim = Sim(g)
    stops = sim.draw_stops(rng, CROSSCHECK_N)
    pw, pn = sim.evaluate(stops)
    cw = np.loadtxt(cpp("eval", spec, stdin="\n".join(" ".join(map(str, s)) for s in stops)).splitlines(), dtype=np.int64)
    mism = int(((cw[:, 0] != pw) | (cw[:, 1] != pn)).sum())
    checks.append((f"Python vs C++ per-window evaluation ({CROSSCHECK_N:,} random windows)", mism == 0, f"{mism} mismatches"))

    # 4. sample size
    n_req = stats.required_n(sigma, TARGET_HALF_WIDTH, CONF)
    R["plan"] = {"sigma": sigma, "half_width": TARGET_HALF_WIDTH, "conf": CONF, "n_required": n_req,
                 "n_for": {f"+-{h*100:.2f}%": stats.required_n(sigma, h, CONF) for h in (0.01, 0.005, 0.002, 0.001, 0.0005)}}

    # 5a. Python MC
    py = sim.run(PY_ROUNDS, PY_SEED)
    x = py["base"] + py["fs"]
    m, s, hw, _ = stats.mean_ci(x, CONF)
    z, pval = stats.z_test(m, float(rtp), sigma, x.size)
    R["python_mc"] = {"rounds": PY_ROUNDS, "seed": PY_SEED, "rtp": m, "std": s, "ci": [m - hw, m + hw], "z": z, "p": pval,
                      "base": float(py["base"].mean()), "fs": float(py["fs"].mean()),
                      "hit_rate": float(((py["base"] > 0) | (py["fs_spins"] > 0)).mean()),
                      "trigger_rate": float((py["fs_spins"] > 0).mean()),
                      "mean_fs_spins": float(py["fs_spins"][py["fs_spins"] > 0].mean())}
    checks.append((f"Python MC: theory RTP inside {CONF:.0%} CI", m - hw <= rtp <= m + hw, f"z={z:+.2f}"))

    # 5b. C++ MC, K seeds, each sized to n_req / K so the pooled run hits the target precision
    per = math.ceil(n_req / len(CPP_SEEDS))
    runs = [json.loads(cpp("mc", spec, per, sd)) for sd in CPP_SEEDS]
    zs, covered = [], 0
    for r in runs:
        se = sigma / math.sqrt(r["rounds"])
        r["z"] = (r["rtp"] - float(rtp)) / se
        r["covered"] = abs(r["z"]) <= 1.959964
        zs.append(r["z"]); covered += r["covered"]
    total_n = per * len(runs)
    pooled = sum(r["rtp"] * r["rounds"] for r in runs) / total_n
    pz = (pooled - float(rtp)) / (sigma / math.sqrt(total_n))
    phw = 1.959964 * sigma / math.sqrt(total_n)
    R["cpp_mc"] = {"per_seed_rounds": per, "seeds": len(runs), "total_rounds": total_n, "pooled_rtp": pooled,
                   "pooled_ci": [pooled - phw, pooled + phw], "pooled_z": pz, "coverage": covered,
                   "z_mean": float(np.mean(zs)), "z_std": float(np.std(zs, ddof=1)), "runs": runs}
    checks.append((f"C++ pooled MC ({total_n:,} rounds): theory inside 95% CI (+-{phw*100:.3f}%)", abs(pz) <= 1.959964, f"z={pz:+.2f}"))
    # Coverage: with 20 seeds, #covered ~ Binomial(20, .95); P(<=16) ~ 1.6%
    checks.append(("C++ per-seed CI coverage >= 17/20 (expected ~19)", covered >= 17, f"{covered}/20"))
    # z's across seeds should look standard normal
    checks.append(("z-scores across seeds have std in [0.6, 1.4]", 0.6 <= np.std(zs, ddof=1) <= 1.4, f"{np.std(zs, ddof=1):.2f}"))
    hit_cpp = sum(r["hit_rate"] * r["rounds"] for r in runs) / total_n
    hp, hl, hh = stats.proportion_ci(round(hit_cpp * total_n), total_n)
    checks.append(("Hit rate: exact value inside Wilson 95% CI of C++ MC", hl <= ex["hit_rate"] <= hh, f"{hit_cpp:.6f} vs {float(ex['hit_rate']):.6f}"))

    # 6. stop uniformity
    chi = [stats.chi2_uniform(c) for c in py["stop_counts"]]
    R["chi2_stops"] = [{"stat": a, "p": b} for a, b in chi]
    checks.append(("Chi-square: reel stops uniform (all 5 reels p > 0.001)", all(b > 0.001 for _, b in chi),
                   ", ".join(f"{b:.3f}" for _, b in chi)))

    # 7. mutation testing
    muts = []
    for mu in mutants.all_mutants(g):
        r = mu.run(MUTANT_ROUNDS, MUTANT_SEED)
        xm = r["base"] + r["fs"]
        zm, _ = stats.z_test(float(xm.mean()), float(rtp), sigma, xm.size)
        chis = [stats.chi2_uniform(c)[1] for c in r["stop_counts"]]
        caught_rtp = abs(zm) > 3.29  # 99.9% two-sided
        caught_chi = min(chis) < 0.001
        delta = float(xm.mean()) - float(rtp)
        muts.append({"name": mu.name, "rtp": float(xm.mean()), "delta": delta, "z": zm,
                     "min_chi2_p": min(chis), "caught_by_rtp_z": caught_rtp, "caught_by_chi2": caught_chi,
                     "rounds_needed_to_see_delta": stats.required_n(sigma, abs(delta) / 2, 0.999) if delta else None})
    R["mutants"] = muts
    checks.append(("Every injected bug detected (|z|>3.29 or chi2 p<0.001)",
                   all(m_["caught_by_rtp_z"] or m_["caught_by_chi2"] for m_ in muts), f"{sum(m_['caught_by_rtp_z'] or m_['caught_by_chi2'] for m_ in muts)}/{len(muts)}"))

    # 8. volatility & sessions (from Python MC, per-round wins)
    thresholds = [0, 1, 5, 10, 50, 100, 200]
    R["distribution"] = {
        "exceed_prob": {str(t): float((x > t).mean()) for t in thresholds},
        "quantiles": {str(q): float(np.quantile(x, q)) for q in (0.5, 0.9, 0.99, 0.999, 0.9999)},
        "max_observed_python": float(x.max()),
        "max_observed_cpp": max(r["max_win"] for r in runs),
        "fs_session_quantiles": {str(q): float(np.quantile(py["fs"][py["fs_spins"] > 0], q)) for q in (0.1, 0.5, 0.9, 0.99)},
        "rtp_share_of_wins_over_50x": float(x[x > 50].sum() / x.sum()),
    }
    n_sess = PY_ROUNDS // SESSION_LEN
    sess = x[: n_sess * SESSION_LEN].reshape(n_sess, SESSION_LEN)
    net = np.cumsum(sess - 1.0, axis=1)
    R["sessions"] = {"spins": SESSION_LEN, "count": n_sess,
                     "session_rtp_quantiles": {str(q): float(np.quantile(sess.mean(axis=1), q)) for q in (0.05, 0.25, 0.5, 0.75, 0.95)},
                     "p_end_ahead": float((net[:, -1] > 0).mean()),
                     "p_bust_bankroll": float((net.min(axis=1) <= -SESSION_BANKROLL).mean()),
                     "bankroll": SESSION_BANKROLL,
                     "theory_session_rtp_sd": sigma / math.sqrt(SESSION_LEN)}

    R["checks"] = [{"check": c, "pass": bool(p), "detail": d} for c, p, d in checks]
    R["all_pass"] = all(p for _, p, _ in checks)
    R["meta"]["elapsed_s"] = round(time.time() - t0, 1)
    (out_dir / "results.json").write_text(json.dumps(R, indent=2, default=float))
    from report import render
    (out_dir / "report.md").write_text(render(R, g))
    for c, p, d in checks:
        print(("PASS " if p else "FAIL ") + c + "  [" + d + "]")
    print("ALL PASS" if R["all_pass"] else "SOME CHECKS FAILED", f"({R['meta']['elapsed_s']}s)")
    return 0 if R["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "config/game_v1.yaml"))
