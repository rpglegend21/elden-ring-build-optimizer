"""
Demo the ranking layer against a few classic builds. Eyeball the results:
do the right weapons/affinities rise to the top for each stat spread?
"""
from optimizer.damage import Regulation
from optimizer.rank import rank

reg = Regulation("data/regulation-vanilla-v1.17.json")
A = lambda s, d, i, f, ar: {"str": s, "dex": d, "int": i, "fai": f, "arc": ar}


def show(title, attrs, **kw):
    kw.setdefault("limit", 10)
    kw.setdefault("collapse_affinities", True)
    print(f"\n{'='*78}\n{title}\n{'='*78}")
    for i, r in enumerate(rank(reg, attrs, **kw), 1):
        print(f"{i:2}. {r.name:<34} AR {r.total_ar:>4}  |  {r.why()}")


# A pure Strength build, colossal-swinging, two-handed, maxed standard upgrade.
show("STRENGTH build — 60 STR / 14 DEX, two-handed, +25 (best weapon each)",
     A(60, 14, 10, 10, 10), upgrade=25, two_handing=True)

# Classic Dexterity build.
show("DEXTERITY build — 18 STR / 60 DEX, one-handed, +25 (best weapon each)",
     A(18, 60, 10, 10, 10), upgrade=25)

# Quality (even STR/DEX).
show("QUALITY build — 50 STR / 50 DEX, +25 (best weapon each)",
     A(50, 50, 10, 10, 10), upgrade=25)

# An Intelligence caster's melee sidearm.
show("INT build — 12 STR / 18 DEX / 60 INT, +25 (best weapon each)",
     A(12, 18, 60, 10, 10), upgrade=25)

# Arcane bleed build — show every affinity (not collapsed) so we can see Blood/Occult.
show("ARCANE/BLEED — 18 STR / 20 DEX / 60 ARC, +25 (all affinities)",
     A(18, 20, 10, 10, 60), upgrade=25, collapse_affinities=False, limit=12)
