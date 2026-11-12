"""Render README figures from reports/v<version>/results.json.

    python tools/make_figures.py reports/v1.0.0/results.json docs/figures
"""
import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

BLUE, ORANGE, INK, MUTED, GRID, SURFACE = "#2a78d6", "#eb6834", "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": "#c3c2b7", "axes.labelcolor": "#52514e", "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
    "axes.titlesize": 12, "axes.titlecolor": INK, "axes.titlelocation": "left",
})


def seed_ci(R, out):
    th, sigma = R["theory"]["rtp"], R["exact"]["sigma"]
    runs = R["cpp_mc"]["runs"]
    fig, ax = plt.subplots(figsize=(8, 6.2))
    ax.axvline(th * 100, color=ORANGE, lw=2, ls=(0, (5, 3)), zorder=1)
    ax.text(th * 100 + 0.02, len(runs) + 0.75, f"exact theoretical RTP {th*100:.3f}%", color="#52514e", ha="left", fontsize=9)
    ax.set_ylim(0.4, len(runs) + 1.2)
    for i, r in enumerate(runs):
        hw = 1.959964 * sigma / math.sqrt(r["rounds"])
        y = len(runs) - i
        ok = abs(r["rtp"] - th) <= hw
        col = BLUE if ok else "#e34948"
        ax.plot([(r["rtp"] - hw) * 100, (r["rtp"] + hw) * 100], [y, y], color=col, lw=2, solid_capstyle="round", zorder=2)
        ax.plot(r["rtp"] * 100, y, "o" if ok else "D", color=col, ms=7, mec=SURFACE, mew=2, zorder=3)
    ax.set_yticks(range(1, len(runs) + 1), [f"seed {len(runs) - k + 1}" for k in range(1, len(runs) + 1)], fontsize=8)
    ax.set_xlabel("simulated RTP (%) with 95% confidence interval")
    ax.grid(axis="x", color=GRID, lw=1)
    ax.set_axisbelow(True)
    cov = R["cpp_mc"]["coverage"]
    ax.set_title(f"{cov} of {len(runs)} independent seeds cover the exact RTP "
                 f"({runs[0]['rounds']:,} rounds each)")
    ax.legend(handles=[Line2D([], [], marker="o", color=BLUE, label="interval covers theory"),
                       Line2D([], [], marker="D", color="#e34948", label="interval misses (expected ~1 in 20)")],
              loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=2, frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "seed_ci.png", dpi=150)
    plt.close(fig)


def exceedance(R, out):
    ex = R["distribution"]["exceed_prob"]
    keys = [k for k in ex if ex[k] > 0]
    vals = [ex[k] for k in keys]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    bars = ax.bar([f"> {k}x" for k in keys], vals, color=BLUE, width=0.55)
    ax.set_yscale("log")
    ax.set_ylim(min(vals) / 3, 2)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v * 1.25, f"1 in {1/v:,.0f}", ha="center", fontsize=8, color="#52514e")
    ax.set_ylabel("probability per paid round (log)")
    ax.set_xlabel("round win (multiples of total bet, incl. free spins)")
    ax.grid(axis="y", color=GRID, lw=1)
    ax.set_axisbelow(True)
    ax.set_title(f"Win-size tail: about half of rounds pay nothing, 1 in {1/ex['100']:,.0f} pays over 100x")
    fig.tight_layout()
    fig.savefig(out / "win_tail.png", dpi=150)
    plt.close(fig)


def mutants(R, out):
    rows = [("Correct: C++ pooled, 52.9M rounds", abs(R["cpp_mc"]["pooled_z"]), False),
            ("Correct: Python, 5M rounds", abs(R["python_mc"]["z"]), False)]
    short = {"RNG off-by-one (last stop never drawn)": "Bug: RNG off-by-one",
             "Wild-run pay ignored (max rule missing)": "Bug: wild max-rule missing",
             "Scatter counted on middle row only": "Bug: scatter middle row only",
             "Free-spin retrigger not implemented": "Bug: no free-spin retrigger"}
    rows += [(short[m["name"]], abs(m["z"]), True) for m in R["mutants"]]
    rows.sort(key=lambda r: r[1])
    fig, ax = plt.subplots(figsize=(8, 3.9))
    ys = range(len(rows))
    ax.barh(ys, [r[1] for r in rows], color=[ORANGE if r[2] else BLUE for r in rows], height=0.55)
    ax.set_xscale("log")
    ax.set_yticks(list(ys), [r[0] for r in rows], fontsize=9)
    for y, r in zip(ys, rows):
        ax.text(r[1] * 1.08, y, f"|z| = {r[1]:.1f}", va="center", fontsize=8, color="#52514e")
    ax.axvline(3.29, color=INK, lw=1, ls=(0, (4, 3)))
    ax.text(3.29 * 1.05, -0.75, "bug threshold |z| = 3.29", fontsize=8, color="#52514e")
    ax.set_ylim(-1.0, len(rows) - 0.5)
    ax.set_xlim(0.2, 400)
    ax.set_xlabel("|z| of simulated RTP vs exact theory (log scale)")
    ax.grid(axis="x", color=GRID, lw=1)
    ax.set_axisbelow(True)
    ax.legend(handles=[Patch(color=BLUE, label="correct simulator"), Patch(color=ORANGE, label="deliberately injected bug")],
              loc="lower right", frameon=False, fontsize=9)
    ax.set_title("Mutation test: every injected bug crosses the |z| = 3.29 threshold")
    fig.tight_layout()
    fig.savefig(out / "mutation_z.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    res = json.loads(Path(sys.argv[1]).read_text())
    o = Path(sys.argv[2])
    o.mkdir(parents=True, exist_ok=True)
    seed_ci(res, o)
    exceedance(res, o)
    mutants(res, o)
    print("ok")
