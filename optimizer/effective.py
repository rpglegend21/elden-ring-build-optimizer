"""
Effective-damage scoring — the "AR lies" layer.

Raw AR sums every damage type as if the target resisted nothing. In-game, each
type is mitigated SEPARATELY by the enemy's per-type damage negation:

    effective = Σ_type  attack_power[type] × (1 − negation[type] / 100)

So a weapon that splits its AR across two damage types loses more against a
resistant target than a weapon that concentrates its damage in one type — which
is why the "highest AR" weapon is often not the one that actually hits hardest.
This module scores weapons by effective damage against a resistance PROFILE, so
the ranking reflects what lands, not the paper number.

Formula source: damage per type = (1 − negation) × … × attack power
(Elden Ring Wiki, "Calculating Damage").

A resistance profile is a dict of negation PERCENT per damage type, e.g.
{PHYSICAL: 10, FIRE: 30, ...}. Missing types default to 0.
"""
from __future__ import annotations

from optimizer.damage import (
    AttackResult, DAMAGE_TYPES, DAMAGE_NAMES,
    PHYSICAL, MAGIC, FIRE, LIGHTNING, HOLY,
)

# Zero resistance everywhere → effective == raw AR (the baseline "AR" ranking).
NEUTRAL = {PHYSICAL: 0, MAGIC: 0, FIRE: 0, LIGHTNING: 0, HOLY: 0}

# ---------------------------------------------------------------------------
# ILLUSTRATIVE profile — NOT sourced enemy data. It exists only to demonstrate
# the re-ranking behavior while the real numbers are sourced. It encodes the
# broad, true pattern (physical is usually resisted less than elements), but the
# exact values are placeholders. Real profiles — a data-derived "average enemy"
# and/or specific bosses — must be extracted from NpcParam and cited in
# SOURCES.md before this ships as a claim. Do not present these as real.
# ---------------------------------------------------------------------------
ILLUSTRATIVE_RESISTANT = {PHYSICAL: 10, MAGIC: 30, FIRE: 30, LIGHTNING: 30, HOLY: 30}


def effective_damage(result: AttackResult, negation: dict | None = None) -> float:
    """Sum of per-type attack power after that type's negation. Unfloored, so
    near-ties stay separable for ranking."""
    neg = negation or NEUTRAL
    return sum(result.attack_power.get(t, 0.0) * (1 - neg.get(t, 0) / 100)
               for t in DAMAGE_TYPES)


def make_score(negation: dict | None = None):
    """Return a score_fn(result) -> float for rank(), for a given profile."""
    neg = negation or NEUTRAL
    return lambda r: effective_damage(r, neg)


def ar_lost(result: AttackResult, negation: dict) -> tuple[int, float]:
    """How much of a weapon's raw AR the profile eats. Returns (points, percent)
    — the headline number for the 'AR lies' story."""
    raw = sum(result.attack_power.get(t, 0.0) for t in DAMAGE_TYPES)
    eff = effective_damage(result, negation)
    pct = (1 - eff / raw) * 100 if raw else 0.0
    return round(raw - eff), pct
