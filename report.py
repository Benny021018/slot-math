"""Render results.json into a human-readable Markdown validation report."""
from __future__ import annotations


def p(x, d=3):
    return f"{100 * x:.{d}f}%"


def render(R: dict, g) -> str:
    th, ex, pl, py, cp = R["theory"], R["exact"], R["plan"], R["python_mc"], R["cpp_mc"]
    d, se = R["distribution"], R["sessions"]
    L = []
    a = L.append
    a(f"# Validation report — Jade Dragon (synthetic slot) v{R['meta']['model_version']}\n")
    a(f"- Config: `{R['meta']['config']}` · SHA-256 (first 12): `{R['meta']['config_sha256_12']}`")
    a(f"- Run (UTC): {R['meta']['run_utc']} · Python {R['meta']['python']} · numpy {R['meta']['numpy']} · elapsed {R['meta']['elapsed_s']} s")
    a(f"- Result: **{'ALL CHECKS PASS' if R['all_pass'] else 'CHECKS FAILED'}**\n")

    a("## 1. Rules (summary)\n")
    a("5 reels × 3 rows, 20 fixed lines, total bet = 20 × line bet. Line wins pay left to right, 3+ in a row, "
      "in line-bet multiples. **W** substitutes for everything except **S** and also pays itself; "
      "a line pays the larger of the wild-run pay and the substituted-symbol pay. **S** pays anywhere "
      "(3/4/5 → 2/10/100 × total bet). 3+ S trigger 10 free spins, all wins ×2, retrigger +10, same reel strips. "
      "Free-spin wins are attributed to the paid spin that triggered them.\n")

    a("## 2. Theoretical RTP and breakdown (exact)\n")
    a(f"Exact RTP = `{ex['rtp_fraction']}` = **{p(th['rtp'], 4)}**\n")
    a("| Source | RTP contribution | Share |")
    a("|---|---:|---:|")
    for name, v in [("Base game — line wins", th["base_line"]), ("Base game — scatter pays", th["base_scatter"]),
                    ("Free spins (incl. retriggers)", th["free_spins"])]:
        a(f"| {name} | {p(v)} | {100*v/th['rtp']:.1f}% |")
    a(f"| **Total** | **{p(th['rtp'])}** | 100% |\n")
    a("Line-win RTP by paying symbol: " + ", ".join(f"{k} {p(v, 2)}" for k, v in th["line_by_symbol"].items()) + "\n")
    a("| Quantity | Value | How derived |")
    a("|---|---:|---|")
    a(f"| P(trigger free spins) per spin | {th['p_trigger']:.6f} (1 in {1/th['p_trigger']:.1f}) | Poisson-binomial over reels, q_i = 3·#S/L_i |")
    a(f"| Expected free spins per trigger | {th['expected_fs_spins']:.4f} | T = 10 / (1 − 10p) |")
    a(f"| Expected free-spin session win | {th['expected_fs_session_win']:.4f} × bet | T × 2 × (base line + scatter RTP) |")
    a(f"| Free-spin session win std | {ex['fs_session_std']:.4f} × bet | branching-process second moment |")
    a(f"| Hit rate (spin pays or triggers) | {p(ex['hit_rate'])} (1 in {1/ex['hit_rate']:.2f}) | exact enumeration |")
    a(f"| Std dev of round win σ | **{ex['sigma']:.4f}** × bet | exact: enumeration + branching process |")
    a(f"| Max base-spin win | {ex['max_base_win']:.2f} × bet | exact enumeration |\n")

    a("## 3. Verification design\n")
    a("Three independent routes to the same numbers, so that one implementation's mistake cannot hide:\n")
    a(f"1. **Analytic counting** (Python, rational arithmetic): per-line expectation over symbol tuples, scatter Poisson-binomial, free-spin renewal equation.")
    a(f"2. **Exhaustive enumeration** (C++, separate code): all {ex['combinations']:,} stop combinations × 20 lines; exact rationals compared with ==.")
    a(f"3. **Monte Carlo** in two languages with different RNGs (numpy PCG64; self-implemented xoshiro256** + Lemire unbiased bounded ints).\n")

    a("## 4. Sample-size plan\n")
    a(f"For a {pl['conf']:.0%} CI of half-width E on the mean of i.i.d. round wins, n = (z·σ/E)², with exact σ = {pl['sigma']:.4f}.\n")
    a("| Target precision (±RTP) | Rounds needed |")
    a("|---|---:|")
    for k, v in pl["n_for"].items():
        a(f"| {k} | {v:,} |")
    a(f"\nAcceptance target used: ±{pl['half_width']*100:.2f}% → **{pl['n_required']:,} rounds**, split over {cp['seeds']} seeds × {cp['per_seed_rounds']:,}.\n")
    a("Why not a fixed tolerance like “within 0.5%”: the right tolerance depends on σ and n. A high-volatility game can miss 0.5% "
      "at 10M rounds through pure chance, while a low-volatility game with a real bug can pass it. Using several seeds also tests that the "
      "CI method itself is calibrated (≈95% of seeds should cover the theory).\n")

    a("## 5. Simulation results\n")
    a("| Run | Rounds | RTP | 95% CI | z vs theory |")
    a("|---|---:|---:|---|---:|")
    a(f"| Python, seed {py['seed']} | {py['rounds']:,} | {p(py['rtp'])} | [{p(py['ci'][0])}, {p(py['ci'][1])}] | {py['z']:+.2f} |")
    a(f"| C++ pooled, seeds 1–{cp['seeds']} | {cp['total_rounds']:,} | {p(cp['pooled_rtp'])} | [{p(cp['pooled_ci'][0])}, {p(cp['pooled_ci'][1])}] | {cp['pooled_z']:+.2f} |")
    a(f"\nPer-seed C++ runs: {cp['coverage']}/{cp['seeds']} CIs contain the theoretical RTP (expected ≈ 19). "
      f"z-scores: mean {cp['z_mean']:+.2f}, std {cp['z_std']:.2f} (expected ≈ 0 and ≈ 1).\n")
    a("| Metric | Theory / exact | Python MC | C++ MC (pooled) |")
    a("|---|---:|---:|---:|")
    tot = cp["total_rounds"]
    c_base = sum(r["base"] * r["rounds"] for r in cp["runs"]) / tot
    c_fs = sum(r["fs"] * r["rounds"] for r in cp["runs"]) / tot
    c_hit = sum(r["hit_rate"] * r["rounds"] for r in cp["runs"]) / tot
    c_trig = sum(r["trigger_rate"] * r["rounds"] for r in cp["runs"]) / tot
    c_fsn = sum(r["mean_fs_spins"] * r["trigger_rate"] * r["rounds"] for r in cp["runs"]) / (c_trig * tot)
    a(f"| Base RTP | {p(th['base_line'] + th['base_scatter'])} | {p(py['base'])} | {p(c_base)} |")
    a(f"| Free-spin RTP | {p(th['free_spins'])} | {p(py['fs'])} | {p(c_fs)} |")
    a(f"| Hit rate | {p(ex['hit_rate'])} | {p(py['hit_rate'])} | {p(c_hit)} |")
    a(f"| Trigger rate | {th['p_trigger']:.5f} | {py['trigger_rate']:.5f} | {c_trig:.5f} |")
    a(f"| Free spins per trigger | {th['expected_fs_spins']:.3f} | {py['mean_fs_spins']:.3f} | {c_fsn:.3f} |")
    a(f"| Std dev σ | {ex['sigma']:.4f} | {py['std']:.4f} | — |\n")

    a("## 6. Distribution, volatility and extremes\n")
    a("| Round win > | Probability (Python MC) |")
    a("|---|---:|")
    for k, v in d["exceed_prob"].items():
        a(f"| {k}× bet | {v:.6f}{'' if v == 0 else f' (1 in {1/v:,.0f})'} |")
    a("\nQuantiles of round win: " + ", ".join(f"{float(k)*100:g}% → {v:.2f}×" for k, v in d["quantiles"].items()) + ".")
    a(f"Free-spin session win (given trigger): " + ", ".join(f"P{float(k)*100:g} {v:.1f}×" for k, v in d["fs_session_quantiles"].items()) + ".")
    a(f"Max observed round win: {d['max_observed_python']:.1f}× (Python), {d['max_observed_cpp']:.1f}× (C++). "
      f"Wins above 50× make up {d['rtp_share_of_wins_over_50x']*100:.1f}% of all money returned.\n")
    a(f"**Player sessions** ({se['spins']} spins, {se['count']:,} sessions): session RTP 5/25/50/75/95th percentiles = "
      + " / ".join(p(v, 1) for v in se["session_rtp_quantiles"].values())
      + f" (theory SD of session RTP = σ/√{se['spins']} = {p(se['theory_session_rtp_sd'], 1)}). "
      f"P(end ahead) = {se['p_end_ahead']:.3f}; P(losing {se['bankroll']} bets at any point) = {se['p_bust_bankroll']:.3f}.\n")

    a("## 7. Mutation test — does the pipeline catch real bugs?\n")
    a("Each mutant is the correct simulator with one realistic bug injected. Detection rule: |z| > 3.29 vs theory (99.9%) "
      f"or a reel-stop chi-square p < 0.001, using {R['meta']['settings']['mutant_rounds']:,} rounds.\n")
    a("| Injected bug | Mutant RTP | Δ vs theory | z | min χ² p | Caught by |")
    a("|---|---:|---:|---:|---:|---|")
    for m in R["mutants"]:
        by = " + ".join(b for b, f in (("RTP z-test", m["caught_by_rtp_z"]), ("χ² stops", m["caught_by_chi2"])) if f) or "**NOT CAUGHT**"
        a(f"| {m['name']} | {p(m['rtp'])} | {m['delta']*100:+.3f}% | {m['z']:+.1f} | {m['min_chi2_p']:.2g} | {by} |")
    a("\nLesson: a bug that shifts RTP by Δ needs roughly n ≈ (3.29·σ / Δ)² rounds to show up in a z-test; small-Δ bugs are "
      "better caught by exact per-window cross-checks (Python vs C++) and by chi-square tests on the RNG output.\n")

    a("## 8. Acceptance checklist\n")
    a("| Check | Result | Detail |")
    a("|---|---|---|")
    for c in R["checks"]:
        a(f"| {c['check']} | {'PASS' if c['pass'] else '**FAIL**'} | {c['detail']} |")
    a("\n## 9. Reproducibility\n")
    s = R["meta"]["settings"]
    a(f"Re-run with `python validate.py {R['meta']['config']}`. Seeds: Python {s['py_seed']}, C++ {s['cpp_seeds'][0]}–{s['cpp_seeds'][-1]}, "
      f"mutants {s['mutant_seed']}. Full numbers in `results.json`. `pytest` holds golden values for regression.")
    return "\n".join(L) + "\n"
