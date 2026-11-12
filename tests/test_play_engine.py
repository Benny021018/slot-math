"""網頁試玩（play/engine.js）和 Python 模型逐盤面比對。

兩邊分開實作：JavaScript 給網頁用，Python 的 line_pay 是參考實作。
同一批停輪位置，線獎、Scatter 個數、Scatter 獎金必須完全一樣。沒有 node 時略過。
"""
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from slotmath.model import line_pay, load

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")

SCRIPT = r"""
const { makeEngine } = require(process.argv[2]);
const data = JSON.parse(require("fs").readFileSync(0, "utf8"));
const E = makeEngine(data.game);
const out = data.stops.map(s => {
  const e = E.evaluate(E.windowAt(s));
  return [e.lineWin, e.scatters, e.scatterPay];
});
process.stdout.write(JSON.stringify(out));
"""


def game_json(g):
    return {
        "rows": g.rows, "wild": g.wild, "scatter": g.scatter,
        "paytable": {s: {str(k): v for k, v in p.items()} for s, p in g.paytable.items()},
        "scatter_pay": {str(k): v for k, v in g.scatter_pay.items()},
        "lines": g.lines, "strips": g.strips,
        "fs_trigger": g.fs_trigger, "fs_award": g.fs_award, "fs_retrigger": g.fs_retrigger, "fs_mult": g.fs_mult,
    }


@pytest.mark.skipif(NODE is None, reason="需要 node")
def test_js_engine_matches_python(tmp_path):
    g = load(ROOT / "config" / "game_v1.yaml")
    rng = random.Random(20261112)
    stops = [[rng.randrange(len(s)) for s in g.strips] for _ in range(50_000)]
    # 一定要包含的邊界盤面：所有 Scatter 位置與所有 Wild 位置各至少一次
    for r, strip in enumerate(g.strips):
        for i, sym in enumerate(strip):
            if sym in (g.wild, g.scatter):
                st = [0] * 5
                st[r] = i
                stops.append(st)
    script = tmp_path / "run.js"
    script.write_text(SCRIPT)
    res = subprocess.run(
        [NODE, str(script), str(ROOT / "play" / "engine.js")],
        input=json.dumps({"game": game_json(g), "stops": stops}),
        capture_output=True, text=True, check=True,
    )
    js = json.loads(res.stdout)
    bad = 0
    for st, (lw, ns, sp) in zip(stops, js):
        win = [[g.strips[r][(st[r] + row) % len(g.strips[r])] for row in range(g.rows)] for r in range(5)]
        py_line = sum(line_pay(g, [win[r][row] for r, row in enumerate(line)]) for line in g.lines)
        py_ns = sum(c.count(g.scatter) for c in win)
        if (py_line, py_ns, g.scatter_pay.get(py_ns, 0)) != (lw, ns, sp):
            bad += 1
    assert len(js) == len(stops) and bad == 0, f"{bad} 個盤面不一致"
