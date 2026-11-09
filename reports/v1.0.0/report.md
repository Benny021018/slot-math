# Validation report — Jade Dragon (synthetic slot) v1.0.0

- Config: `config/game_v1.yaml` · SHA-256 (first 12): `a06063878ae8`
- Run (UTC): 2026-11-09T07:49:11Z · Python 3.13.18 · numpy 2.5.3 · elapsed 73.0 s
- Result: **ALL CHECKS PASS**

## 1. Rules (summary)

5 reels × 3 rows, 20 fixed lines, total bet = 20 × line bet. Line wins pay left to right, 3+ in a row, in line-bet multiples. **W** substitutes for everything except **S** and also pays itself; a line pays the larger of the wild-run pay and the substituted-symbol pay. **S** pays anywhere (3/4/5 → 2/10/100 × total bet). 3+ S trigger 10 free spins, all wins ×2, retrigger +10, same reel strips. Free-spin wins are attributed to the paid spin that triggered them.

## 2. Theoretical RTP and breakdown (exact)

Exact RTP = `3223228345/3334927869` = **96.6506%**

| Source | RTP contribution | Share |
|---|---:|---:|
| Base game — line wins | 61.789% | 63.9% |
| Base game — scatter pays | 4.987% | 5.2% |
| Free spins (incl. retriggers) | 29.874% | 30.9% |
| **Total** | **96.651%** | 100% |

Line-win RTP by paying symbol: W 1.02%, H1 9.89%, H2 5.94%, H3 9.89%, L1 10.58%, L2 9.00%, L3 6.31%, L4 9.16%

| Quantity | Value | How derived |
|---|---:|---|
| P(trigger free spins) per spin | 0.018280 (1 in 54.7) | Poisson-binomial over reels, q_i = 3·#S/L_i |
| Expected free spins per trigger | 12.2369 | T = 10 / (1 − 10p) |
| Expected free-spin session win | 16.3427 × bet | T × 2 × (base line + scatter RTP) |
| Free-spin session win std | 15.6947 × bet | branching-process second moment |
| Hit rate (spin pays or triggers) | 51.824% (1 in 1.93) | exact enumeration |
| Std dev of round win σ | **3.7115** × bet | exact: enumeration + branching process |
| Max base-spin win | 101.00 × bet | exact enumeration |

## 3. Verification design

Three independent routes to the same numbers, so that one implementation's mistake cannot hide:

1. **Analytic counting** (Python, rational arithmetic): per-line expectation over symbol tuples, scatter Poisson-binomial, free-spin renewal equation.
2. **Exhaustive enumeration** (C++, separate code): all 13,798,512 stop combinations × 20 lines; exact rationals compared with ==.
3. **Monte Carlo** in two languages with different RNGs (numpy PCG64; self-implemented xoshiro256** + Lemire unbiased bounded ints).

## 4. Sample-size plan

For a 95% CI of half-width E on the mean of i.i.d. round wins, n = (z·σ/E)², with exact σ = 3.7115.

| Target precision (±RTP) | Rounds needed |
|---|---:|
| +-1.00% | 529,160 |
| +-0.50% | 2,116,639 |
| +-0.20% | 13,228,994 |
| +-0.10% | 52,915,975 |
| +-0.05% | 211,663,897 |

Acceptance target used: ±0.10% → **52,915,975 rounds**, split over 20 seeds × 2,645,799.

Why not a fixed tolerance like “within 0.5%”: the right tolerance depends on σ and n. A high-volatility game can miss 0.5% at 10M rounds through pure chance, while a low-volatility game with a real bug can pass it. Using several seeds also tests that the CI method itself is calibrated (≈95% of seeds should cover the theory).

## 5. Simulation results

| Run | Rounds | RTP | 95% CI | z vs theory |
|---|---:|---:|---|---:|
| Python, seed 20261109 | 5,000,000 | 96.485% | [96.160%, 96.811%] | -1.00 |
| C++ pooled, seeds 1–20 | 52,915,980 | 96.672% | [96.572%, 96.772%] | +0.41 |

Per-seed C++ runs: 19/20 CIs contain the theoretical RTP (expected ≈ 19). z-scores: mean +0.09, std 0.94 (expected ≈ 0 and ≈ 1).

| Metric | Theory / exact | Python MC | C++ MC (pooled) |
|---|---:|---:|---:|
| Base RTP | 66.776% | 66.636% | 66.750% |
| Free-spin RTP | 29.874% | 29.849% | 29.922% |
| Hit rate | 51.824% | 51.805% | 51.818% |
| Trigger rate | 0.01828 | 0.01826 | 0.01829 |
| Free spins per trigger | 12.237 | 12.229 | 12.241 |
| Std dev σ | 3.7115 | 3.7117 | — |

## 6. Distribution, volatility and extremes

| Round win > | Probability (Python MC) |
|---|---:|
| 0× bet | 0.518050 (1 in 2) |
| 1× bet | 0.163288 (1 in 6) |
| 5× bet | 0.036722 (1 in 27) |
| 10× bet | 0.017318 (1 in 58) |
| 50× bet | 0.000914 (1 in 1,094) |
| 100× bet | 0.000092 (1 in 10,846) |
| 200× bet | 0.000009 (1 in 108,696) |

Quantiles of round win: 50% → 0.15×, 90% → 2.00×, 99% → 15.95×, 99.9% → 48.40×, 99.99% → 97.40×.
Free-spin session win (given trigger): P10 3.8×, P50 11.8×, P90 34.3×, P99 74.7×.
Max observed round win: 292.0× (Python), 350.2× (C++). Wins above 50× make up 6.7% of all money returned.

**Player sessions** (200 spins, 25,000 sessions): session RTP 5/25/50/75/95th percentiles = 60.8% / 77.9% / 92.8% / 111.3% / 143.7% (theory SD of session RTP = σ/√200 = 26.2%). P(end ahead) = 0.389; P(losing 50 bets at any point) = 0.321.

## 7. Mutation test — does the pipeline catch real bugs?

Each mutant is the correct simulator with one realistic bug injected. Detection rule: |z| > 3.29 vs theory (99.9%) or a reel-stop chi-square p < 0.001, using 2,000,000 rounds.

| Injected bug | Mutant RTP | Δ vs theory | z | min χ² p | Caught by |
|---|---:|---:|---:|---:|---|
| RNG off-by-one (last stop never drawn) | 98.666% | +2.016% | +7.7 | 0 | RTP z-test + χ² stops |
| Wild-run pay ignored (max rule missing) | 95.548% | -1.102% | -4.2 | 0.043 | RTP z-test |
| Scatter counted on middle row only | 63.088% | -33.562% | -127.9 | 0.041 | RTP z-test |
| Free-spin retrigger not implemented | 91.142% | -5.508% | -21.0 | 0.05 | RTP z-test |

Lesson: a bug that shifts RTP by Δ needs roughly n ≈ (3.29·σ / Δ)² rounds to show up in a z-test; small-Δ bugs are better caught by exact per-window cross-checks (Python vs C++) and by chi-square tests on the RNG output.

## 8. Acceptance checklist

| Check | Result | Detail |
|---|---|---|
| Enumeration base RTP == analytic base RTP (exact rational) | PASS | 575885/862407 vs 575885/862407 |
| Enumeration P(trigger) == analytic P(trigger) (exact rational) | PASS | 173/9464 |
| Enumeration total RTP == analytic total RTP (exact rational) | PASS | 0.966506164934 |
| Python vs C++ per-window evaluation (200,000 random windows) | PASS | 0 mismatches |
| Python MC: theory RTP inside 95% CI | PASS | z=-1.00 |
| C++ pooled MC (52,915,980 rounds): theory inside 95% CI (+-0.100%) | PASS | z=+0.41 |
| C++ per-seed CI coverage >= 17/20 (expected ~19) | PASS | 19/20 |
| z-scores across seeds have std in [0.6, 1.4] | PASS | 0.94 |
| Hit rate: exact value inside Wilson 95% CI of C++ MC | PASS | 0.518181 vs 0.518239 |
| Chi-square: reel stops uniform (all 5 reels p > 0.001) | PASS | 0.321, 0.689, 0.949, 0.678, 0.863 |
| Every injected bug detected (|z|>3.29 or chi2 p<0.001) | PASS | 4/4 |

## 9. Reproducibility

Re-run with `python validate.py config/game_v1.yaml`. Seeds: Python 20261109, C++ 1–20, mutants 7. Full numbers in `results.json`. `pytest` holds golden values for regression.
