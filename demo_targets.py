"""
The payoff demo: one build, ranked against real enemies. Watch the recommendation
flip as the target changes — the "resistance charts lie" thesis, on sourced data.
"""
from optimizer.damage import Regulation
from optimizer.rank import rank
from optimizer.effective import make_score, effective_damage
from optimizer.enemies import ROSTER, profile

reg = Regulation("data/regulation-vanilla-v1.17.json")
A = lambda s, d, i, f, ar: {"str": s, "dex": d, "int": i, "fai": f, "arc": ar}

# A Strength build (fire infusions topped its RAW-AR ranking earlier).
attrs = A(60, 14, 10, 10, 10)
KW = dict(upgrade=25, two_handing=True, collapse_affinities=True, limit=5)


def board(title, score_fn):
    rows = rank(reg, attrs, score_fn=score_fn, **KW) if score_fn else rank(reg, attrs, **KW)
    print(f"\n{title}")
    for i, r in enumerate(rows, 1):
        val = round(effective_damage(r.result, prof)) if score_fn else r.total_ar
        tag = "eff" if score_fn else "AR "
        print(f"  {i}. {r.name:<28} {tag} {val:>4}  (raw AR {r.total_ar})")


print("STRENGTH build — 60 STR / 14 DEX, two-handed, +25")
print("Same build, different targets. Notice what sits at #1 each time.\n" + "=" * 60)

prof = None
board("BY RAW AR (what most calculators show):", None)

for e in ROSTER:
    if e.key not in ("malenia", "fire_giant", "elden_beast", "radagon"):
        continue
    prof = e.negation
    board(f"vs {e.name}  (fire negation {e.negation[2]}%):", make_score(prof))
