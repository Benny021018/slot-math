// Independent C++ implementation (shares NO code with the Python package; reads the flat spec).
//   ./slot enum <spec>                 exact enumeration of every base-game stop combination
//   ./slot mc   <spec> <rounds> <seed> Monte Carlo of the full game (base + free spins)
// All money output is in TOTAL-bet units.
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <map>
#include <string>
#include <vector>
using namespace std;

struct Spec {
  int nsym, W, S;
  vector<array<long long, 6>> pay;  // [sym][count]
  long long spay[6];
  int trig, award, retrig, mult;
  vector<array<int, 5>> lines;
  vector<vector<int>> strips;
};

static Spec load(const char* path) {
  ifstream f(path);
  Spec s;
  f >> s.nsym >> s.W >> s.S;
  s.pay.resize(s.nsym);
  for (int i = 0; i < s.nsym; i++)
    for (int k = 0; k < 6; k++) f >> s.pay[i][k];
  for (int k = 0; k < 6; k++) f >> s.spay[k];
  f >> s.trig >> s.award >> s.retrig >> s.mult;
  int nl;
  f >> nl;
  s.lines.resize(nl);
  for (auto& l : s.lines)
    for (int r = 0; r < 5; r++) f >> l[r];
  s.strips.resize(5);
  for (auto& st : s.strips) {
    int L;
    f >> L;
    st.resize(L);
    for (auto& x : st) f >> x;
  }
  return s;
}

// Evaluate one window. Returns win in LINE-bet units; sets nscat.
static long long eval(const Spec& s, const int win[5][3], int& nscat) {
  long long total = 0;
  for (const auto& l : s.lines) {
    int sym[5];
    for (int r = 0; r < 5; r++) sym[r] = win[r][l[r]];
    int kw = 0;
    while (kw < 5 && sym[kw] == s.W) kw++;
    long long best = s.pay[s.W][kw];
    if (kw < 5 && sym[kw] != s.S) {
      int t = sym[kw], k = kw;
      while (k < 5 && (sym[k] == s.W || sym[k] == t)) k++;
      if (s.pay[t][k] > best) best = s.pay[t][k];
    }
    total += best;
  }
  nscat = 0;
  for (int r = 0; r < 5; r++)
    for (int row = 0; row < 3; row++) nscat += (win[r][row] == s.S);
  return total + s.spay[nscat] * (long long)s.lines.size();
}

static void fill(const Spec& s, const int stop[5], int win[5][3]) {
  for (int r = 0; r < 5; r++) {
    int L = s.strips[r].size();
    for (int row = 0; row < 3; row++) win[r][row] = s.strips[r][(stop[r] + row) % L];
  }
}

static int run_enum(const Spec& s) {
  // Exact base-spin distribution. Accumulate integer sums to avoid float error.
  map<long long, long long> hist;            // base win (line bets) -> count
  map<long long, long long> hist_trig;       // same, restricted to triggering spins
  long long N = 1;
  for (auto& st : s.strips) N *= st.size();
  int stop[5], win[5][3], ns;
  long long scat_cnt[6] = {0};
  for (stop[0] = 0; stop[0] < (int)s.strips[0].size(); stop[0]++)
    for (stop[1] = 0; stop[1] < (int)s.strips[1].size(); stop[1]++)
      for (stop[2] = 0; stop[2] < (int)s.strips[2].size(); stop[2]++)
        for (stop[3] = 0; stop[3] < (int)s.strips[3].size(); stop[3]++)
          for (stop[4] = 0; stop[4] < (int)s.strips[4].size(); stop[4]++) {
            fill(s, stop, win);
            long long w = eval(s, win, ns);
            hist[w]++;
            scat_cnt[ns]++;
            if (ns >= s.trig) hist_trig[w]++;
          }
  printf("{\"combinations\": %lld, \"n_lines\": %zu,\n \"scatter_count\": [", N, s.lines.size());
  for (int k = 0; k < 6; k++) printf("%lld%s", scat_cnt[k], k < 5 ? ", " : "],\n");
  printf(" \"hist\": {");
  bool first = true;
  for (auto& [w, c] : hist) printf("%s\"%lld\": %lld", first ? "" : ", ", w, c), first = false;
  printf("},\n \"hist_trigger\": {");
  first = true;
  for (auto& [w, c] : hist_trig) printf("%s\"%lld\": %lld", first ? "" : ", ", w, c), first = false;
  printf("}}\n");
  return 0;
}

// xoshiro256** seeded by splitmix64, + Lemire's unbiased bounded integer.
// Self-implemented so results are bit-identical across compilers/platforms.
struct Rng {
  uint64_t s[4];
  static uint64_t sm(uint64_t& x) {
    uint64_t z = (x += 0x9e3779b97f4a7c15ULL);
    z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL;
    z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL;
    return z ^ (z >> 31);
  }
  explicit Rng(uint64_t seed) { for (auto& v : s) v = sm(seed); }
  static uint64_t rotl(uint64_t x, int k) { return (x << k) | (x >> (64 - k)); }
  uint64_t next() {
    uint64_t r = rotl(s[1] * 5, 7) * 9, t = s[1] << 17;
    s[2] ^= s[0]; s[3] ^= s[1]; s[1] ^= s[2]; s[0] ^= s[3]; s[2] ^= t; s[3] = rotl(s[3], 45);
    return r;
  }
  uint32_t below(uint32_t n) {  // unbiased in [0, n)
    uint64_t m = (uint64_t)(uint32_t)(next() >> 32) * n;
    uint32_t l = (uint32_t)m;
    if (l < n) {
      uint32_t t = (0u - n) % n;
      while (l < t) { m = (uint64_t)(uint32_t)(next() >> 32) * n; l = (uint32_t)m; }
    }
    return m >> 32;
  }
};

static int run_mc(const Spec& s, long long rounds, uint64_t seed) {
  Rng rng(seed);
  const double nl = s.lines.size();
  int stop[5], win[5][3], ns;
  double sum = 0, sum2 = 0, base_sum = 0, fs_sum = 0, mx = 0;
  long long hits = 0, trig = 0, fs_spins = 0;
  const double th[] = {0, 1, 5, 10, 50, 100, 500, 1000};
  long long exceed[8] = {0};
  for (long long i = 0; i < rounds; i++) {
    for (int r = 0; r < 5; r++) stop[r] = rng.below(s.strips[r].size());
    fill(s, stop, win);
    double b = eval(s, win, ns) / nl, f = 0;
    const bool triggered = ns >= s.trig;
    if (triggered) {
      trig++;
      int left = s.award;
      while (left > 0) {
        left--;
        for (int r = 0; r < 5; r++) stop[r] = rng.below(s.strips[r].size());
        fill(s, stop, win);
        f += s.mult * eval(s, win, ns) / nl;
        fs_spins++;
        if (ns >= s.trig) left += s.retrig;
      }
    }
    double x = b + f;
    sum += x; sum2 += x * x; base_sum += b; fs_sum += f;
    if (b > 0 || triggered) hits++;  // hit = base spin pays or triggers FS
    if (x > mx) mx = x;
    for (int k = 0; k < 8; k++) exceed[k] += (x > th[k]);
  }
  double mean = sum / rounds, var = (sum2 - rounds * mean * mean) / (rounds - 1);
  printf("{\"rounds\": %lld, \"seed\": %llu, \"rtp\": %.10f, \"std\": %.10f, \"base\": %.10f, "
         "\"fs\": %.10f, \"hit_rate\": %.10f, \"trigger_rate\": %.10f, \"mean_fs_spins\": %.6f, "
         "\"max_win\": %.4f, \"exceed\": {",
         rounds, (unsigned long long)seed, mean, sqrt(var), base_sum / rounds, fs_sum / rounds,
         (double)hits / rounds, (double)trig / rounds, trig ? (double)fs_spins / trig : 0.0, mx);
  for (int k = 0; k < 8; k++) printf("\"%g\": %lld%s", th[k], exceed[k], k < 7 ? ", " : "}}\n");
  return 0;
}

// Read "s0 s1 s2 s3 s4" stop lines from stdin, print "<win_line_bets> <nscat>" per line.
static int run_eval(const Spec& s) {
  int stop[5], win[5][3], ns;
  while (scanf("%d %d %d %d %d", &stop[0], &stop[1], &stop[2], &stop[3], &stop[4]) == 5) {
    fill(s, stop, win);
    long long w = eval(s, win, ns);
    printf("%lld %d\n", w, ns);
  }
  return 0;
}

int main(int argc, char** argv) {
  if (argc < 3) { fprintf(stderr, "usage: slot enum|mc spec [rounds seed]\n"); return 1; }
  Spec s = load(argv[2]);
  string mode = argv[1];
  if (mode == "enum") return run_enum(s);
  if (mode == "eval") return run_eval(s);
  if (mode == "mc" && argc == 5) return run_mc(s, atoll(argv[3]), strtoull(argv[4], nullptr, 10));
  fprintf(stderr, "bad args\n");
  return 1;
}
