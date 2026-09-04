"""
Elden Ring attack-rating (AR) engine.

Faithful Python port of the calculation in ThomasJClark/elden-ring-weapon-calculator
(MIT-licensed), computed against the game's own regulation params. We re-implement the
math ourselves so every number is one we can re-derive and verify by hand — the whole
point of the piece is the judgment, not a black-box call.

Data: data/regulation-vanilla-v1.17.json  (base game, patch 1.17; DLC entries flagged `dlc`)
"""

from __future__ import annotations
import json
import math
from pathlib import Path
from dataclasses import dataclass

# ---- enums (from the source; keys used throughout the regulation JSON) -------
PHYSICAL, MAGIC, FIRE, LIGHTNING, HOLY = 0, 1, 2, 3, 4
POISON, SCARLET_ROT, BLEED, FROST, SLEEP, MADNESS, DEATH_BLIGHT = 5, 6, 7, 8, 9, 10, 11

DAMAGE_TYPES = [PHYSICAL, MAGIC, FIRE, LIGHTNING, HOLY]
STATUS_TYPES = [POISON, SCARLET_ROT, BLEED, FROST, SLEEP, MADNESS, DEATH_BLIGHT]
ALL_TYPES = DAMAGE_TYPES + STATUS_TYPES

ATTRIBUTES = ["str", "dex", "int", "fai", "arc"]

DAMAGE_NAMES = {PHYSICAL: "Physical", MAGIC: "Magic", FIRE: "Fire",
                LIGHTNING: "Lightning", HOLY: "Holy"}
STATUS_NAMES = {POISON: "Poison", SCARLET_ROT: "Scarlet Rot", BLEED: "Bleed",
                FROST: "Frost", SLEEP: "Sleep", MADNESS: "Madness",
                DEATH_BLIGHT: "Death Blight"}

DEFAULT_DAMAGE_CALC_CORRECT_ID = 0
DEFAULT_STATUS_CALC_CORRECT_ID = 6

INEFFECTIVE_ATTRIBUTE_PENALTY = 0.4  # -40% if you don't meet a scaling stat's requirement


def _evaluate_calc_correct_graph(graph: list[dict]) -> list[float]:
    """Expand a calc-correct graph definition into a per-stat-level array of scaling
    multipliers. Direct port of evaluateCalcCorrectGraph (the soft-cap saturation curve)."""
    arr = [0.0] * 150  # index by attribute value; 0 == "not set" (matches JS `!arr[x]`)
    for i in range(1, len(graph)):
        prev, stage = graph[i - 1], graph[i]
        lo = 1 if i == 1 else prev["maxVal"] + 1
        hi = 148 if i == len(graph) - 1 else stage["maxVal"]
        for v in range(lo, hi + 1):
            if v < len(arr) and not arr[v]:
                span = stage["maxVal"] - prev["maxVal"]
                ratio = 0.0 if span == 0 else max(0.0, min(1.0, (v - prev["maxVal"]) / span))
                adj = prev["adjPt"]
                if adj > 0:
                    ratio = ratio ** adj
                elif adj < 0:
                    ratio = 1 - (1 - ratio) ** (-adj)
                arr[v] = prev["maxGrowVal"] + (stage["maxGrowVal"] - prev["maxGrowVal"]) * ratio
    return arr


@dataclass
class Weapon:
    name: str            # full name incl. affinity, e.g. "Heavy Longsword"
    weapon_name: str     # base name, e.g. "Longsword"
    affinity_id: int
    weapon_type: int
    requirements: dict            # {attr: int}
    attack: list                  # attack[level][type] -> float
    attribute_scaling: list       # attribute_scaling[level][attr] -> float
    attack_element_correct: dict  # {type: {attr: number|True}}
    calc_correct_graphs: dict     # {type: [per-level array]}
    paired: bool
    sorcery_tool: bool
    incantation_tool: bool
    dlc: bool


class Regulation:
    """Loads regulation JSON and decodes weapons into ready-to-calc objects."""

    def __init__(self, path: str | Path):
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        self._raw = raw

        self._graphs = {int(k): _evaluate_calc_correct_graph(v)
                        for k, v in raw["calcCorrectGraphs"].items()}

        # attackElementCorrect: which attributes scale which damage types.
        # Status effects always scale with ARC (added manually, as in the source).
        self._aec = {}
        for k, v in raw["attackElementCorrects"].items():
            aec = {int(t): dict(m) for t, m in v.items()}
            for st in (POISON, BLEED, MADNESS, SLEEP):
                aec[st] = {"arc": True}
            self._aec[int(k)] = aec

        self._reinforce = {int(k): v for k, v in raw["reinforceTypes"].items()}
        self._status_params = {int(k): v for k, v in raw["statusSpEffectParams"].items()}

        # [threshold, letter] pairs (S/A/B/C/D/E), sorted high→low, for scaling grades
        self.scaling_tiers = raw.get("scalingTiers", [])

        self.weapons = [self._decode(w) for w in raw["weapons"]]

    def _graph(self, gid: int) -> list[float]:
        return self._graphs[gid]

    def _decode(self, w: dict) -> Weapon:
        reinforce = self._reinforce[w["reinforceTypeId"]]  # list per upgrade level
        unupg_attack = {int(t): val for t, val in w["attack"]}
        unupg_scaling = {a: val for a, val in w["attributeScaling"]}
        ccg_ids = {int(t): gid for t, gid in (w.get("calcCorrectGraphIds") or {}).items()}
        status_ids = w.get("statusSpEffectParamIds") or []

        # attack[level][type] and attribute_scaling[level][attr]
        attack, scaling = [], []
        for rp in reinforce:
            lvl_attack = {}
            for t, base in unupg_attack.items():
                lvl_attack[t] = base * rp["attack"].get(str(t), 0)
            offsets = [rp.get("statusSpEffectId1"), rp.get("statusSpEffectId2"),
                       rp.get("statusSpEffectId3")]
            for i, sp_id in enumerate(status_ids):
                if sp_id:
                    sp = self._status_params.get(sp_id + (offsets[i] or 0))
                    if sp:
                        for t, val in sp.items():
                            lvl_attack[int(t)] = val
            attack.append(lvl_attack)

            lvl_scaling = {}
            for a, base in unupg_scaling.items():
                lvl_scaling[a] = base * rp["attributeScaling"].get(a, 0)
            scaling.append(lvl_scaling)

        ccg = {}
        for t in DAMAGE_TYPES:
            ccg[t] = self._graph(ccg_ids.get(t, DEFAULT_DAMAGE_CALC_CORRECT_ID))
        for t in STATUS_TYPES:
            ccg[t] = self._graph(ccg_ids.get(t, DEFAULT_STATUS_CALC_CORRECT_ID))

        return Weapon(
            name=w["name"], weapon_name=w["weaponName"], affinity_id=w["affinityId"],
            weapon_type=w["weaponType"], requirements=w.get("requirements", {}),
            attack=attack, attribute_scaling=scaling,
            attack_element_correct=self._aec[w["attackElementCorrectId"]],
            calc_correct_graphs=ccg,
            paired=bool(w.get("paired")), sorcery_tool=bool(w.get("sorceryTool")),
            incantation_tool=bool(w.get("incantationTool")), dlc=bool(w.get("dlc")),
        )


# weaponType ids that can only be two-handed (bows/ballista) — get the bonus always
_BOW_TYPES = {19, 20, 21, 22}  # LIGHT_BOW, BOW, GREATBOW, BALLISTA


def _adjust_two_handing(weapon: Weapon, attrs: dict, two_handing: bool) -> dict:
    bonus = two_handing
    if weapon.paired:
        bonus = False
    if weapon.weapon_type in _BOW_TYPES:
        bonus = True
    if bonus:
        out = dict(attrs)
        out["str"] = int(attrs["str"] * 1.5)  # floor
        return out
    return attrs


@dataclass
class AttackResult:
    upgrade_level: int
    attack_power: dict          # {type: float}
    ineffective_attributes: list
    ineffective_types: list

    @property
    def total_ar(self) -> float:
        """Exact (unfloored) summed attack power across damage types. Use this for
        ranking/optimization so near-ties stay distinguishable."""
        return sum(self.attack_power.get(t, 0.0) for t in DAMAGE_TYPES)

    @property
    def total_ar_int(self) -> int:
        """In-game / tclark AR: floor of the summed raw damage (floored independently,
        NOT the sum of the floored per-type values)."""
        return math.floor(self.total_ar)

    def floored_power(self) -> dict:
        """Per-type attack power floored to integers, as shown in-game and on tclark."""
        return {t: math.floor(v) for t, v in self.attack_power.items()}


def get_weapon_attack(weapon: Weapon, attrs: dict, upgrade_level: int,
                      two_handing: bool = False) -> AttackResult:
    """Port of getWeaponAttack. `attrs` = {str,dex,int,fai,arc}. Returns per-type
    attack power (damage types + status buildup)."""
    adj = _adjust_two_handing(weapon, attrs, two_handing)

    ineffective = [a for a, req in weapon.requirements.items() if adj.get(a, 0) < req]
    ineffective_types = []
    power = {}

    for t in ALL_TYPES:
        is_damage = t in DAMAGE_TYPES
        base = weapon.attack[upgrade_level].get(t, 0) or 0
        if not (base or weapon.sorcery_tool or weapon.incantation_tool):
            continue

        scaling_attrs = weapon.attack_element_correct.get(t, {})
        total_scaling = 1.0

        if any(scaling_attrs.get(a) for a in ineffective):
            total_scaling = 1 - INEFFECTIVE_ATTRIBUTE_PENALTY
            ineffective_types.append(t)
        else:
            eff = adj if is_damage else attrs
            for a in ATTRIBUTES:
                ac = scaling_attrs.get(a)
                if not ac:
                    continue
                if ac is True:
                    sc = weapon.attribute_scaling[upgrade_level].get(a, 0)
                else:
                    base0 = weapon.attribute_scaling[0].get(a, 0)
                    sc = (ac * weapon.attribute_scaling[upgrade_level].get(a, 0) / base0) if base0 else 0
                if sc:
                    val = eff.get(a, 0)
                    curve = weapon.calc_correct_graphs[t]
                    total_scaling += (curve[val] if 0 <= val < len(curve) else 0) * sc

        if base:
            power[t] = base * total_scaling

    return AttackResult(upgrade_level, power, ineffective, ineffective_types)
