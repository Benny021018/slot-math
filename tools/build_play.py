"""產生網頁試玩 play/index.html。

規則、賠率、線型、輪帶讀 config/game_v1.yaml；理論值讀驗收報告的 results.json；
計分引擎是 play/engine.js。三者一起內嵌到 play/template.html，輸出單一個 HTML 檔。
用法：python tools/build_play.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from slotmath.model import load  # noqa: E402


def main():
    g = load(ROOT / "config" / "game_v1.yaml")
    res = json.loads((ROOT / "reports" / f"v{g.version}" / "results.json").read_text(encoding="utf-8"))
    game = {
        "version": g.version, "config_sha256_12": g.config_hash,
        "rows": g.rows, "symbols": g.symbols, "wild": g.wild, "scatter": g.scatter,
        "paytable": {s: {str(k): v for k, v in p.items()} for s, p in g.paytable.items()},
        "scatter_pay": {str(k): v for k, v in g.scatter_pay.items()},
        "lines": g.lines, "strips": g.strips,
        "fs_trigger": g.fs_trigger, "fs_award": g.fs_award, "fs_retrigger": g.fs_retrigger, "fs_mult": g.fs_mult,
    }
    ex, th = res["exact"], res["theory"]
    theory = {
        "rtp": ex["rtp"], "sigma": ex["sigma"], "hit_rate": ex["hit_rate"],
        "p_trigger": ex["p_trigger"], "expected_fs_spins": th["expected_fs_spins"],
    }
    html = (ROOT / "play" / "template.html").read_text(encoding="utf-8")
    html = html.replace("/*__GAME__*/", "const GAME = " + json.dumps(game, separators=(",", ":")) + ";\n"
                        + "const THEORY = " + json.dumps(theory) + ";")
    html = html.replace("/*__ENGINE__*/", (ROOT / "play" / "engine.js").read_text(encoding="utf-8"))
    (ROOT / "play" / "index.html").write_text(html, encoding="utf-8")
    print(f"wrote play/index.html (model {g.version}, config {g.config_hash})")


if __name__ == "__main__":
    main()
