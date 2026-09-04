"""
Verification harness. Prints AR + status for known weapon/stat combos so the numbers
can be hand-checked against a trusted calculator (eldenring.tclark.io) before we build
anything on top of this engine.
"""
from optimizer.damage import (Regulation, get_weapon_attack,
                              DAMAGE_TYPES, STATUS_TYPES, DAMAGE_NAMES, STATUS_NAMES)

reg = Regulation("data/regulation-vanilla-v1.17.json")
by_name = {}
for w in reg.weapons:
    by_name.setdefault(w.name, w)  # first (base-game precedence; dlc filtered below anyway)


def show(name, attrs, level=25, two_handing=False):
    w = by_name.get(name)
    if not w:
        print(f"  !! not found: {name}")
        return
    level = min(level, len(w.attack) - 1)  # somber weapons cap at +10
    r = get_weapon_attack(w, attrs, level, two_handing)
    hand = "2H" if two_handing else "1H"
    fp = r.floored_power()  # in-game / tclark convention: floor each type
    dmg = "  ".join(f"{DAMAGE_NAMES[t]} {fp[t]}"
                    for t in DAMAGE_TYPES if t in fp)
    status = "  ".join(f"{STATUS_NAMES[t]} {fp[t]}"
                       for t in STATUS_TYPES if t in fp)
    print(f"  {name} +{level} {hand} | {dmg}  ==> TOTAL AR {r.total_ar_int}"
          + (f"   [status: {status}]" if status else ""))


A = lambda s, d, i, f, ar: {"str": s, "dex": d, "int": i, "fai": f, "arc": ar}

print("=== Verification combos (check against eldenring.tclark.io) ===")
show("Longsword", A(40, 40, 10, 10, 10))
show("Heavy Longsword", A(80, 12, 10, 10, 10))
show("Heavy Longsword", A(54, 12, 10, 10, 10), two_handing=True)  # 54*1.5=81
show("Keen Longsword", A(12, 80, 10, 10, 10))
show("Uchigatana", A(40, 40, 10, 10, 10))          # has bleed
show("Blood Uchigatana", A(18, 40, 10, 10, 45))    # bleed build, arc scaling
show("Moonveil", A(12, 18, 80, 10, 10))            # magic split, INT
show("Rivers of Blood", A(12, 40, 10, 40, 20))     # somber, arc bleed

print()
print(f"Total weapon entries loaded: {len(reg.weapons)} "
      f"(base: {sum(1 for w in reg.weapons if not w.dlc)}, "
      f"dlc: {sum(1 for w in reg.weapons if w.dlc)})")
