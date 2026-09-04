"""
Enemy roster — real, sourced damage-negation profiles.

Each profile is the enemy's per-type damage negation PERCENT, used by
optimizer.effective to score weapons by what actually lands against that target.
This is the "resistance charts lie" payload: the same weapon's ranking swings
hard from one enemy to another (Malenia takes full Fire; the Fire Giant negates
half of it).

Values are from the Elden Ring Wiki (Fextralife) enemy pages, which publish the
datamined NpcParam negation tables. Physical is stored as the STANDARD physical
negation — most melee hits land as Standard/Slash/Strike, which are usually
equal; the Slash/Strike/Pierce sub-splits (e.g. Fire Giant is extra-weak to
Slash, Radagon to Strike, Radahn/Godfrey to Pierce) are a documented v2 refinement.
Godfrey uses his Phase-1 profile (the "wall" phase). NG HP shown for context.
"""
from __future__ import annotations
from optimizer.damage import PHYSICAL, MAGIC, FIRE, LIGHTNING, HOLY


def _p(phys, mag, fire, ltn, holy):
    return {PHYSICAL: phys, MAGIC: mag, FIRE: fire, LIGHTNING: ltn, HOLY: holy}


class Enemy:
    def __init__(self, key, name, hp, negation, note, source):
        self.key = key
        self.name = name
        self.hp = hp
        self.negation = negation
        self.note = note
        self.source = source


ROSTER = [
    Enemy(
        "crucible_knight", "Crucible Knight", 2782,
        _p(35, 40, 20, 20, 40),
        "Non-boss wall. Heavy physical/magic/holy negation; relatively soft to "
        "fire and lightning. A patience-and-parry fight where elemental burst "
        "quietly overperforms.",
        "https://eldenring.wiki.fextralife.com/Crucible+Knight",
    ),
    Enemy(
        "radahn", "Starscourge Radahn", 9572,
        _p(10, 20, 20, 20, 40),
        "The first real equipment check: huge HP, punishes bad setups. Even "
        "negation across the board, holy-resistant. Low physical negation "
        "rewards a clean physical weapon.",
        "https://eldenring.wiki.fextralife.com/Starscourge+Radahn",
    ),
    Enemy(
        "godfrey", "Godfrey, First Elden Lord", 21903,
        _p(10, 20, 20, 0, 40),
        "The teacher (Phase 1). No standout defense except holy; weak to "
        "lightning. Rewards discipline, not gimmicks.",
        "https://eldenring.wiki.fextralife.com/Godfrey,_First_Elden_Lord",
    ),
    Enemy(
        "malenia", "Malenia, Blade of Miquella", 33251,
        _p(10, 20, 0, 20, 40),
        "You know why. Takes FULL fire damage (0% negation) and bleeds — the "
        "textbook case where the 'best AR' weapon loses to a fire/bleed pick.",
        "https://eldenring.wiki.fextralife.com/Malenia+Blade+of+Miquella",
    ),
    Enemy(
        "fire_giant", "Fire Giant", 42363,
        _p(0, 0, 50, 0, 20),
        "The irony engine: negates 50% fire. Your top 'Fire ___' AR pick becomes "
        "one of the worst choices here; raw physical wins.",
        "https://eldenring.wiki.fextralife.com/Fire+Giant",
    ),
    Enemy(
        "elden_beast", "Elden Beast", 22127,
        _p(10, 40, 40, 40, 80),
        "Resists everything elemental (holy 80%!). Physical is the only thing "
        "that reliably lands — the clearest 'stick to physical' case.",
        "https://eldenring.wiki.fextralife.com/Elden+Beast",
    ),
    Enemy(
        "radagon", "Radagon of the Golden Order", 13339,
        _p(35, 20, 0, 20, 80),
        "Holy wall (80%) with heavy physical negation, but 0% fire — a fire "
        "weapon flips from mediocre to excellent against him.",
        "https://eldenring.wiki.fextralife.com/Radagon+of+the+Golden+Order",
    ),
]

BY_KEY = {e.key: e for e in ROSTER}


def profile(key: str) -> dict:
    """Negation dict for an enemy key, for optimizer.effective.make_score."""
    return BY_KEY[key].negation
