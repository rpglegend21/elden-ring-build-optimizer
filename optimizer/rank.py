"""
Ranking layer — the optimizer proper.

Given a player's stats (+ upgrade level + two-handing), score and rank every
base-game weapon/affinity and explain what's carrying the damage. Built on the
verified AR engine in damage.py; the score is pluggable so a target-resistance
re-rank (the "resistance charts lie" thesis) can drop in later without touching
this file.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from optimizer.damage import (
    Regulation, Weapon, get_weapon_attack, AttackResult,
    DAMAGE_TYPES, STATUS_TYPES, DAMAGE_NAMES, STATUS_NAMES, ATTRIBUTES,
)

# ---- weapon category ids (from the regulation; Richard-verifiable) -----------
# Staves/seals are already filtered by the engine's sorcery/incantation flags,
# but shields, torches, and ranged weapons need their type ids to exclude.
SMALL_SHIELD, MEDIUM_SHIELD, GREATSHIELD = 65, 67, 69
TORCH = 87
THRUSTING_SHIELD = 90                      # DLC; pokes, but shield-class
SHIELD_TYPES = {SMALL_SHIELD, MEDIUM_SHIELD, GREATSHIELD, THRUSTING_SHIELD}
RANGED_TYPES = {50, 51, 53, 55, 56}        # bows, greatbows, crossbows, ballistae

# Melee weapon-type id -> display name (base game; verified against the data).
# Used for the category filter. Ranged/casting/shield types are excluded by
# default elsewhere, so they're intentionally not listed here.
WEAPON_TYPE_NAMES = {
    1: "Dagger", 3: "Straight Sword", 5: "Greatsword", 7: "Colossal Sword",
    9: "Curved Sword", 11: "Curved Greatsword", 13: "Katana", 14: "Twinblade",
    15: "Thrusting Sword", 16: "Heavy Thrusting Sword", 17: "Axe", 19: "Greataxe",
    21: "Hammer", 23: "Great Hammer", 24: "Flail", 25: "Spear", 28: "Great Spear",
    29: "Halberd", 31: "Reaper", 35: "Fist", 37: "Claw", 39: "Whip",
    41: "Colossal Weapon",
}

# Affinity id -> display name (base game; Ashes of War infusions).
AFFINITY_NAMES = {
    -1: "Unique", 0: "Standard", 1: "Heavy", 2: "Keen", 3: "Quality",
    4: "Fire", 5: "Flame Art", 6: "Lightning", 7: "Sacred",
    8: "Magic", 9: "Cold", 10: "Poison", 11: "Blood", 12: "Occult",
}


def scaling_grade(coeff: float, tiers: list) -> str:
    """Map a raw scaling coefficient to its in-game letter (S/A/B/C/D/E)."""
    for threshold, letter in tiers:
        if coeff >= threshold:
            return letter
    return "-"


@dataclass
class Ranked:
    name: str                 # full name incl. affinity, e.g. "Heavy Longsword"
    weapon_name: str          # base name, e.g. "Longsword"
    affinity: str             # display affinity, e.g. "Heavy"
    weapon_type: int
    upgrade_level: int
    total_ar: int             # in-game AR (floored)
    score: float              # ranking key (unfloored total AR by default)
    breakdown: dict           # {damage type name: floored int} (>0 only)
    status: dict              # {status name: floored int} (>0 only)
    scaling: dict             # {attr: letter grade} (scaling attrs only)
    meets_requirements: bool
    missing: dict             # {attr: required value} you don't meet
    result: AttackResult = field(default=None, repr=False)

    def why(self) -> str:
        """One-line 'what's carrying this' — dominant damage + top scaling stat."""
        if not self.breakdown:
            return "no damage"
        top_type, top_val = max(self.breakdown.items(), key=lambda kv: kv[1])
        share = top_val / self.total_ar if self.total_ar else 0
        if share >= 0.85:
            dmg = f"{top_type}-focused ({top_val})"
        else:
            parts = "/".join(f"{k} {v}" for k, v in
                             sorted(self.breakdown.items(), key=lambda kv: -kv[1]))
            dmg = f"split {parts}"
        # best scaling stat the player actually has damage-relevant investment in
        if self.scaling:
            best = sorted(self.scaling.items(), key=lambda kv: "SABCDE-".index(kv[1]))
            grades = ", ".join(f"{a.upper()} {g}" for a, g in best)
            dmg += f" | scales {grades}"
        if self.status:
            dmg += " | " + ", ".join(f"{k} {v}" for k, v in self.status.items())
        if not self.meets_requirements:
            need = ", ".join(f"{a.upper()} {v}" for a, v in self.missing.items())
            dmg += f"  [!] needs {need} (-40% until met)"
        return dmg


def default_score(r: AttackResult) -> float:
    """Pure total attack rating (unfloored, so near-ties stay separable)."""
    return r.total_ar


def rank(
    reg: Regulation,
    attrs: dict,
    *,
    upgrade: int = 25,
    two_handing: bool = False,
    include_dlc: bool = False,
    include_ranged: bool = False,
    include_shields: bool = False,
    weapon_types: set | None = None,
    requirements_only: bool = False,
    collapse_affinities: bool = False,
    score_fn=default_score,
    limit: int | None = 25,
) -> list[Ranked]:
    """Rank weapon/affinity combos for a build.

    attrs: {str,dex,int,fai,arc}. upgrade: requested level (somber weapons cap
    at +10 automatically). collapse_affinities: keep only each base weapon's
    single best-scoring affinity (answers "which weapon", not "which infusion").
    """
    tiers = reg.scaling_tiers
    out: list[Ranked] = []

    for w in reg.weapons:
        if w.dlc and not include_dlc:
            continue
        if w.sorcery_tool or w.incantation_tool:      # staves, seals
            continue
        if not include_shields and w.weapon_type in SHIELD_TYPES:
            continue
        if not include_ranged and w.weapon_type in RANGED_TYPES:
            continue
        if weapon_types is not None and w.weapon_type not in weapon_types:
            continue

        lvl = min(upgrade, len(w.attack) - 1)          # somber cap
        r = get_weapon_attack(w, attrs, lvl, two_handing)

        missing = {a: w.requirements[a] for a in r.ineffective_attributes}
        if requirements_only and missing:
            continue

        fp = r.floored_power()
        breakdown = {DAMAGE_NAMES[t]: fp[t] for t in DAMAGE_TYPES
                     if fp.get(t, 0) > 0}
        status = {STATUS_NAMES[t]: fp[t] for t in STATUS_TYPES
                  if fp.get(t, 0) > 0}
        scaling = {}
        for a in ATTRIBUTES:
            c = w.attribute_scaling[lvl].get(a, 0)
            if c > 0:
                scaling[a] = scaling_grade(c, tiers)

        out.append(Ranked(
            name=w.name, weapon_name=w.weapon_name,
            affinity=AFFINITY_NAMES.get(w.affinity_id, str(w.affinity_id)),
            weapon_type=w.weapon_type, upgrade_level=lvl,
            total_ar=r.total_ar_int, score=score_fn(r),
            breakdown=breakdown, status=status, scaling=scaling,
            meets_requirements=not missing, missing=missing, result=r,
        ))

    out.sort(key=lambda x: x.score, reverse=True)

    if collapse_affinities:
        seen, collapsed = set(), []
        for rk in out:
            if rk.weapon_name in seen:
                continue
            seen.add(rk.weapon_name)
            collapsed.append(rk)
        out = collapsed

    return out[:limit] if limit else out
