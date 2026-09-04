"""
Side-by-side: rank by raw AR vs rank by EFFECTIVE damage against a resistant
target. Shows the "AR lies" effect — split-elemental weapons fall, concentrated
weapons rise. NOTE: the resistance profile here is ILLUSTRATIVE, not sourced
enemy data (see optimizer/effective.py). It demonstrates the mechanism only.
"""
from optimizer.damage import Regulation
from optimizer.rank import rank
from optimizer.effective import make_score, ILLUSTRATIVE_RESISTANT, effective_damage, ar_lost

reg = Regulation("data/regulation-vanilla-v1.17.json")
A = lambda s, d, i, f, ar: {"str": s, "dex": d, "int": i, "fai": f, "arc": ar}

profile = ILLUSTRATIVE_RESISTANT


def compare(title, attrs, **kw):
    kw.setdefault("two_handing", False)
    print(f"\n{'='*82}\n{title}\n(illustrative target: Phys -10%, all elements -30%)\n{'='*82}")

    by_ar = rank(reg, attrs, collapse_affinities=True, limit=6, **kw)
    by_eff = rank(reg, attrs, collapse_affinities=True, limit=6,
                  score_fn=make_score(profile), **kw)

    print("\n  RANKED BY RAW AR:")
    for i, r in enumerate(by_ar, 1):
        lost, pct = ar_lost(r.result, profile)
        eff = round(effective_damage(r.result, profile))
        print(f"  {i}. {r.name:<30} AR {r.total_ar:>4}  ->  effective {eff:>4}  "
              f"(loses {pct:4.0f}%)")

    print("\n  RANKED BY EFFECTIVE DAMAGE (what actually lands):")
    for i, r in enumerate(by_eff, 1):
        eff = round(effective_damage(r.result, profile))
        print(f"  {i}. {r.name:<30} effective {eff:>4}  (raw AR {r.total_ar})  "
              f"|  {r.why()}")


compare("STRENGTH — 60 STR / 14 DEX, two-handed, +25",
        A(60, 14, 10, 10, 10), upgrade=25, two_handing=True)

compare("DEXTERITY — 18 STR / 60 DEX, +25",
        A(18, 60, 10, 10, 10), upgrade=25)
