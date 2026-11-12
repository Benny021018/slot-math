// Jade Dragon 的 JavaScript 計分引擎（網頁試玩用）。
// 規則只讀 config/game_v1.yaml 轉出來的 GAME 資料；和 Python 模型分開實作，
// tests/test_play_engine.py 會用 node 逐盤面比對兩邊的結果。
(function (root) {
  "use strict";

  function makeEngine(G) {
    const W = G.wild;
    const S = G.scatter;
    const nLines = G.lines.length;

    // 停輪位置 stop 是畫面最上面那一列：第 row 列 = strip[(stop + row) % L]
    function windowAt(stops) {
      return stops.map(function (s, r) {
        const strip = G.strips[r];
        const out = [];
        for (let row = 0; row < G.rows; row++) out.push(strip[(s + row) % strip.length]);
        return out;
      });
    }

    // 一條線的獎金（線注倍數）。取「開頭 Wild 連線」與「替代後符號連線」較大者。
    function linePay(syms) {
      let kw = 0;
      while (kw < 5 && syms[kw] === W) kw++;
      const wildPay = (G.paytable[W] || {})[kw] || 0;
      if (kw === 5) return { pay: wildPay, symbol: W, count: 5 };
      const first = syms[kw];
      if (first === S) return { pay: wildPay, symbol: W, count: kw };
      let k = kw;
      while (k < 5 && (syms[k] === W || syms[k] === first)) k++;
      const symPay = (G.paytable[first] || {})[k] || 0;
      if (wildPay >= symPay) return { pay: wildPay, symbol: W, count: kw };
      return { pay: symPay, symbol: first, count: k };
    }

    // 評估一個畫面：線獎（線注倍數）、各中獎線、Scatter 個數與 Scatter 獎金（總押注倍數）
    function evaluate(win) {
      let lineWin = 0;
      const wins = [];
      for (let i = 0; i < nLines; i++) {
        const rows = G.lines[i];
        const syms = rows.map(function (row, r) { return win[r][row]; });
        const p = linePay(syms);
        if (p.pay > 0) {
          lineWin += p.pay;
          wins.push({ line: i, pay: p.pay, symbol: p.symbol, count: p.count });
        }
      }
      let ns = 0;
      for (const col of win) for (const x of col) if (x === S) ns++;
      return { lineWin: lineWin, wins: wins, scatters: ns, scatterPay: G.scatter_pay[ns] || 0 };
    }

    // 無偏的整數亂數 [0, n)：用 32 位元亂數做拒絕抽樣，避免取餘數造成的偏差
    function cryptoRand(n) {
      const buf = new Uint32Array(1);
      const limit = Math.floor(0x100000000 / n) * n;
      let x;
      do {
        root.crypto.getRandomValues(buf);
        x = buf[0];
      } while (x >= limit);
      return x % n;
    }

    function randomStops(rand) {
      return G.strips.map(function (s) { return rand(s.length); });
    }

    // 轉一次（主遊戲或免費遊戲）。win 以「總押注」為單位。
    function spin(stops, inFree) {
      const w = windowAt(stops);
      const e = evaluate(w);
      const mult = inFree ? G.fs_mult : 1;
      const award = e.scatters >= G.fs_trigger ? (inFree ? G.fs_retrigger : G.fs_award) : 0;
      return {
        stops: stops, window: w, wins: e.wins, scatters: e.scatters, mult: mult, award: award,
        lineWin: e.lineWin * mult / nLines,
        scatterWin: e.scatterPay * mult,
        win: (e.lineWin / nLines + e.scatterPay) * mult,
      };
    }

    // 玩完一整局（一次付費轉動＋它觸發的所有免費遊戲），回傳總獎金（總押注倍數）
    function playRound(rand) {
      let r = spin(randomStops(rand), false);
      let total = r.win;
      let left = r.award;
      const hit = r.win > 0 || r.award > 0;
      const triggered = r.award > 0;
      let freeSpins = 0;
      while (left > 0) {
        left--;
        freeSpins++;
        r = spin(randomStops(rand), true);
        total += r.win;
        left += r.award;
      }
      return { win: total, hit: hit, triggered: triggered, freeSpins: freeSpins };
    }

    return {
      G: G, nLines: nLines, windowAt: windowAt, linePay: linePay, evaluate: evaluate,
      randomStops: randomStops, spin: spin, playRound: playRound, cryptoRand: cryptoRand,
    };
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { makeEngine: makeEngine };
  else root.JadeEngine = { makeEngine: makeEngine };
})(typeof globalThis !== "undefined" ? globalThis : this);
