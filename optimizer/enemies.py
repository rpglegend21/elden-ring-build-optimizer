"""
Enemy roster — real, sourced damage-negation AND status-resistance profiles.

Two payloads per enemy:

1. `negation` — per-type damage negation PERCENT, used by optimizer.effective to
   score weapons by what actually lands (the v1 "resistance charts lie" story).

2. `status` — the buildup a status effect must accumulate before it PROCS, per
   effect, as the game's escalating ladder: each successful proc raises the bar
   for the next (Malenia bleeds at 421, then 519, then 809, then 1266). `None`
   means the enemy is IMMUNE to that effect. This is the v2 payload: it's why a
   bleed weapon shreds Malenia but does literally nothing extra to the Crucible
   Knight or Radagon (both bleed-immune), and why the Elden Beast — immune to
   everything — is still the pure-physical case from v1.

Both are from the Elden Ring Wiki (Fextralife) enemy pages, which publish the
datamined NpcParam tables. Physical negation is stored as STANDARD physical
(Slash/Strike/Pierce sub-splits are a documented v2+ refinement). Godfrey uses
his Phase-1 profile. NG HP shown for context.

Note on status data completeness: a few enemy pages list only the first proc
threshold for some effects (Radahn's bleed/frost/rot); where only one value is
published we store the one value, and the kill simulation simply stops procing
that effect after the last known threshold (conservative — it never invents a
proc). Sleep/Madness are omitted here (not damage effects); every roster enemy
is Madness-immune anyway.
"""
from __future__ import annotations
from optimizer.damage import (
    PHYSICAL, MAGIC, FIRE, LIGHTNING, HOLY,
    BLEED, FROST, SCARLET_ROT, POISON,
)


def _p(phys, mag, fire, ltn, holy):
    return {PHYSICAL: phys, MAGIC: mag, FIRE: fire, LIGHTNING: ltn, HOLY: holy}


class Enemy:
    def __init__(self, key, name, hp, negation, status, note, source):
        self.key = key
        self.name = name
        self.hp = hp
        self.negation = negation
        self.status = status          # {status_id: [thresholds] | None-if-immune}
        self.note = note
        self.source = source

    def immune_to(self, status_id: int) -> bool:
        return self.status.get(status_id) is None

    def status_summary(self) -> str:
        """Short 'what sticks' line for the UI, e.g. 'Bleed 421 · Frost 306'."""
        parts = []
        for sid, label in ((BLEED, "Bleed"), (FROST, "Frost"),
                           (SCARLET_ROT, "Rot"), (POISON, "Poison")):
            ladder = self.status.get(sid)
            if ladder:
                parts.append(f"{label} {ladder[0]}")
        return " · ".join(parts) if parts else "immune to all status"


ROSTER = [
    Enemy(
        "crucible_knight", "Crucible Knight", 2782,
        _p(35, 40, 20, 20, 40),
        {BLEED: None, FROST: [517, 807, 1264], SCARLET_ROT: [517, 807, 1264],
         POISON: [517, 807, 1264]},
        "Non-boss wall. Heavy physical/magic/holy negation; relatively soft to "
        "fire and lightning. Bleed-IMMUNE — a blood build's whole gimmick does "
        "nothing here; elemental burst quietly overperforms.",
        "https://eldenring.wiki.fextralife.com/Crucible+Knight",
    ),
    Enemy(
        "radahn", "Starscourge Radahn", 9572,
        _p(10, 20, 20, 20, 40),
        {BLEED: [334], FROST: [334], SCARLET_ROT: [243], POISON: [334, 432, 722, 1179]},
        "The first real equipment check: huge HP, low physical negation, holy-"
        "resistant. Low status thresholds (~330) mean bleed/frost land fast — a "
        "clean physical bleed weapon does double duty.",
        "https://eldenring.wiki.fextralife.com/Starscourge+Radahn",
    ),
    Enemy(
        "godfrey", "Godfrey, First Elden Lord", 21903,
        _p(10, 20, 20, 0, 40),
        {BLEED: [601, 891, 1348], FROST: [601, 891, 1348],
         SCARLET_ROT: [367, 465, 755, 1212], POISON: [367, 465, 755, 1212]},
        "The teacher (Phase 1). No standout defense except holy; weak to "
        "lightning. Bleeds and freezes on moderate thresholds — status is a "
        "bonus, not the plan.",
        "https://eldenring.wiki.fextralife.com/Godfrey,_First_Elden_Lord",
    ),
    Enemy(
        "malenia", "Malenia, Blade of Miquella", 33251,
        _p(10, 20, 0, 20, 40),
        {BLEED: [421, 519, 809, 1266], FROST: [306, 348, 446, 736, 1193],
         SCARLET_ROT: [1481, 1938], POISON: [1481, 1938]},
        "The headline. Takes FULL fire (0% negation) AND bleeds/freezes on the "
        "game's lowest thresholds — but is highly ROT-resistant (1481), the "
        "irony given she inflicts it. Bleed + frost, not rot, are her real "
        "counters. The textbook case where 'best AR' loses to a bleed pick.",
        "https://eldenring.wiki.fextralife.com/Malenia+Blade+of+Miquella",
    ),
    Enemy(
        "fire_giant", "Fire Giant", 42363,
        _p(0, 0, 50, 0, 20),
        {BLEED: [566, 856, 1313], FROST: [1217, 1674],
         SCARLET_ROT: [566, 856, 1313], POISON: [566, 856, 1313]},
        "The irony engine: negates 50% fire, so your top 'Fire ___' AR pick "
        "becomes one of the worst here — raw physical wins. Bleeds on moderate "
        "thresholds; frost-resistant (1217).",
        "https://eldenring.wiki.fextralife.com/Fire+Giant",
    ),
    Enemy(
        "elden_beast", "Elden Beast", 22127,
        _p(10, 40, 40, 40, 80),
        {BLEED: None, FROST: None, SCARLET_ROT: None, POISON: None},
        "Resists everything elemental (holy 80%!) AND is immune to every status. "
        "No tricks land — physical damage is the only thing that reliably works. "
        "The clearest 'stick to raw physical' case in the game.",
        "https://eldenring.wiki.fextralife.com/Elden+Beast",
    ),
    Enemy(
        "radagon", "Radagon of the Golden Order", 13339,
        _p(35, 20, 0, 20, 80),
        {BLEED: None, FROST: [627, 917, 1374], SCARLET_ROT: [627, 917, 1374],
         POISON: [627, 917, 1374]},
        "Holy wall (80%) with heavy physical negation, but 0% fire — a fire "
        "weapon flips from mediocre to excellent. Bleed-IMMUNE, so pair fire "
        "with frost, not blood.",
        "https://eldenring.wiki.fextralife.com/Radagon+of+the+Golden+Order",
    ),
]

BY_KEY = {e.key: e for e in ROSTER}


def profile(key: str) -> dict:
    """Negation dict for an enemy key, for optimizer.effective.make_score."""
    return BY_KEY[key].negation
