"""
Status-effect + hits-to-kill layer — the "the number lies twice" engine.

v1 showed the first lie: raw AR ignores the enemy's per-type damage negation.
This layer shows the second: raw AR ignores STATUS. A katana that reads lower on
paper can kill Malenia faster than a higher-AR straight sword, because every few
hits it procs Hemorrhage for ~10.5% of her max HP — damage that never appears in
any attack-rating number.

We model this by SIMULATING the fight hit by hit:

  * Each hit deals `effective` direct damage (v1's after-negation number).
  * Each hit also adds this weapon's per-hit status BUILDUP (bleed/frost/rot/
    poison — computed by the AR engine, arcane-scaled) to a running meter.
  * When a meter crosses the enemy's next threshold (the escalating ladder in
    enemies.py), the effect PROCS: bleed and frost apply an instant burst; the
    meter resets and the next proc needs the higher threshold.
  * Frostbite also lowers the target's damage absorption 20% — every direct hit
    after the first frost proc lands 20% harder.

Hits-to-kill = the hit on which cumulative damage reaches the enemy's HP.

PROC FORMULAS (main-game bosses; Elden Ring Wiki):
  * Hemorrhage: 10.5% max HP + 70 flat  (per proc; a few dedicated blood
    weapons deal +140 — we use the standard +70, and for boss-scale HP the flat
    is a rounding error next to the 10.5%).            [/Hemorrhage]
  * Frostbite:  7% max HP + 21 flat, and −20% absorption (≈ +20% damage taken)
    for 30s.                                            [/Frostbite]
  * Scarlet Rot (weapon tier): 0.18% max HP + 15 /s for 90s → 16.2% + 1350 total.
  * Poison (deadly, weapon tier): 0.14% max HP + 14 /s for 30s → 4.2% + 420 total.

HONEST SCOPE (stated, not hidden):
  * Bleed and Frost procs are INSTANT bursts, so they fold cleanly into a
    hit count. Rot and Poison are damage-OVER-TIME; folding a 30–90s DoT into a
    hit count needs an attack-cadence model we haven't built, so we DON'T put
    them in hits-to-kill — we report them separately as "if it procs, +X over
    Ys". Their thresholds are still tracked so we can say whether they'd land.
  * FROST procs at most ONCE per fight — the wiki's Frostbite page says buildup
    can't rebuild until the 30s debuff clears, so we take the first proc and then
    keep its −20% absorption (≈ +20% damage taken) on for the rest of the fight
    rather than modeling the 30s expiry. BLEED has no such cooldown (per the
    Hemorrhage page), so it keeps procing along the escalating ladder.
  * No buildup DECAY: we assume sustained aggression (buildup only grows). Real
    buildup bleeds off if you stop hitting, so slow/poke playstyles proc slower
    than modeled.
  * One hit = one status application (no motion values / multi-hit attacks).
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field

from optimizer.damage import AttackResult, BLEED, FROST, SCARLET_ROT, POISON
from optimizer.effective import effective_damage

# proc coefficients (fraction of max HP, flat), main-game bosses
BLEED_PCT, BLEED_FLAT = 0.105, 70
FROST_PCT, FROST_FLAT = 0.07, 21
FROST_VULN = 0.20                      # +20% damage taken after a frost proc
ROT_PCT_TOTAL, ROT_FLAT_TOTAL = 0.162, 1350     # over 90s
POISON_PCT_TOTAL, POISON_FLAT_TOTAL = 0.042, 420  # over 30s

_HIT_CAP = 400                         # safety bound for the sim loop


@dataclass
class KillResult:
    hits: int | None                   # hits to kill (None if not killed in _HIT_CAP)
    hits_no_status: int | None         # same fight ignoring status, for contrast
    bleed_procs: int = 0
    frost_procs: int = 0
    frost_debuff: bool = False         # did the +20% vuln ever turn on
    dot_note: str = ""                 # separate rot/poison DoT annotation
    hits_saved: int = 0                # hits_no_status − hits (how much status buys)

    def summary(self) -> str:
        if self.hits is None:
            return "can't kill (too weak in this sim)"
        s = f"{self.hits} hits"
        procs = []
        if self.bleed_procs:
            procs.append(f"{self.bleed_procs}× bleed")
        if self.frost_procs:
            procs.append(f"{self.frost_procs}× frost")
        if procs:
            s += " (" + ", ".join(procs)
            if self.hits_saved > 0:
                s += f"; saves {self.hits_saved}"
            s += ")"
        return s


def _proc_ladder(enemy, sid):
    """The escalating threshold list for a status on an enemy, or None if immune."""
    return enemy.status.get(sid)


def simulate_kill(result: AttackResult, enemy, negation: dict) -> KillResult:
    """Hit-by-hit fight sim. `result` carries per-hit damage AND per-hit status
    buildup; `enemy` carries HP + escalating status thresholds; `negation` is the
    per-type damage negation used for effective per-hit damage."""
    eff = effective_damage(result, negation)

    # baseline: no status folded in
    no_status = math.ceil(enemy.hp / eff) if eff > 0 else None

    if eff <= 0:
        return KillResult(hits=None, hits_no_status=no_status)

    bleed_bu = result.attack_power.get(BLEED, 0.0)
    frost_bu = result.attack_power.get(FROST, 0.0)
    rot_bu = result.attack_power.get(SCARLET_ROT, 0.0)
    pois_bu = result.attack_power.get(POISON, 0.0)

    bleed_lad = _proc_ladder(enemy, BLEED)
    frost_lad = _proc_ladder(enemy, FROST)

    remaining = float(enemy.hp)
    acc_bleed = acc_frost = 0.0
    n_bleed = n_frost = 0
    frost_on = False
    hits = 0

    while remaining > 0 and hits < _HIT_CAP:
        hits += 1
        dmg = eff * (1 + FROST_VULN) if frost_on else eff
        remaining -= dmg
        if remaining <= 0:
            break

        # bleed
        if bleed_bu > 0 and bleed_lad and n_bleed < len(bleed_lad):
            acc_bleed += bleed_bu
            if acc_bleed >= bleed_lad[n_bleed]:
                n_bleed += 1
                acc_bleed = 0.0
                remaining -= BLEED_PCT * enemy.hp + BLEED_FLAT
                if remaining <= 0:
                    break
        # frost — ONE proc only: the wiki's Frostbite page says buildup can't
        # rebuild until the 30s debuff clears, so repeated frost procs in a normal
        # fight aren't real. The lasting value is the −20% absorption, which we
        # keep on for the rest of the fight (we don't model the 30s expiry).
        # (Bleed, by contrast, has "no cooldowns or limits" per /Hemorrhage, so it
        # keeps procing up its escalating ladder above.)
        if frost_bu > 0 and frost_lad and n_frost < 1:
            acc_frost += frost_bu
            if acc_frost >= frost_lad[0]:
                n_frost += 1
                acc_frost = 0.0
                remaining -= FROST_PCT * enemy.hp + FROST_FLAT
                frost_on = True
                if remaining <= 0:
                    break

    killed = hits if remaining <= 0 else None
    saved = (no_status - killed) if (killed and no_status) else 0

    # rot / poison: reported separately (DoT, not folded into the hit count)
    dot_bits = []
    if rot_bu > 0 and _proc_ladder(enemy, SCARLET_ROT):
        dot_bits.append(f"rot ~{round(ROT_PCT_TOTAL*enemy.hp + ROT_FLAT_TOTAL):,} over 90s")
    if pois_bu > 0 and _proc_ladder(enemy, POISON):
        dot_bits.append(f"poison ~{round(POISON_PCT_TOTAL*enemy.hp + POISON_FLAT_TOTAL):,} over 30s")
    dot_note = ("if built up: " + ", ".join(dot_bits)) if dot_bits else ""

    return KillResult(
        hits=killed, hits_no_status=no_status,
        bleed_procs=n_bleed, frost_procs=n_frost, frost_debuff=frost_on,
        dot_note=dot_note, hits_saved=max(0, saved),
    )


def make_ttk_score(enemy, negation: dict):
    """score_fn for rank(): higher is better, so we return a value that ranks
    FEWER hits first. Ties (and unkillable weapons) fall back to effective damage
    so the ordering stays total and sensible."""
    def score(r: AttackResult) -> float:
        k = simulate_kill(r, enemy, negation)
        eff = effective_damage(r, negation)
        if k.hits is None:
            return -1e9 + eff          # can't kill: sink to the bottom, but ordered
        # fewer hits ranks higher; effective damage breaks ties within a hit-count
        return -k.hits * 1e6 + eff
    return score
