"""Generate reel strips from symbol counts with a fixed seed.
Constraint: any two S on the same strip are >= 3 apart (cyclically),
so a 3-row window shows at most one S per reel (needed by the scatter formula)."""
import random, sys, yaml
COUNTS = [
    dict(W=1, S=1, H1=2, H2=2, H3=3, L1=4, L2=4, L3=4, L4=5),
    dict(W=2, S=1, H1=2, H2=2, H3=3, L1=4, L2=4, L3=4, L4=5),
    dict(W=2, S=2, H1=2, H2=2, H3=3, L1=4, L2=4, L3=4, L4=5),
    dict(W=2, S=1, H1=2, H2=2, H3=3, L1=4, L2=4, L3=4, L4=5),
    dict(W=1, S=1, H1=2, H2=2, H3=3, L1=4, L2=4, L3=4, L4=5),
]
def ok(strip):
    idx = [i for i, s in enumerate(strip) if s == "S"]
    L = len(strip)
    return all(min((a - b) % L, (b - a) % L) >= 3 for a in idx for b in idx if a != b)
def build(seed):
    rng = random.Random(seed)
    strips = []
    for c in COUNTS:
        syms = [s for s, n in c.items() for _ in range(n)]
        while True:
            rng.shuffle(syms)
            if ok(syms):
                strips.append(list(syms)); break
    return strips
if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 20261109
    for s in build(seed):
        print("    - [" + ", ".join(s) + "]")
