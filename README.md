# ⚔️ Elden Ring Build Optimizer

**[Live app →](https://elden-ring-build-optimizer.streamlit.app)** · base game (patch 1.17)

Most weapon calculators answer *"what's the highest Attack Rating?"* — and that's
the wrong question. Your weapon shows one number. You swing at a boss and barely
scratch it. The game never tells you why; it just lets you see it. **That gap is
the lesson.**

This tool makes the gap explicit. Give it your stats and it ranks every base-game
weapon/affinity by **effective damage against the enemy in front of you** — what
actually lands after that enemy's per-type damage negation — not the paper AR.

The result: the "best AR" weapon is often *not* the one that hits hardest. Same
Strength build, the #1 pick **flips** from a Fire weapon (vs Malenia, who takes
full fire) to a pure-physical one (vs the Fire Giant, who negates 50% of it).

## Why AR "lies" — and why that's good design

Attack Rating assumes the enemy resists nothing. Real damage is what's left after
negation, applied *separately* per damage type — so a weapon that splits its AR
across two types loses more against a resistant target. Surfacing a number that
doesn't predict real damage sounds like a design flaw. It works because it's
**observable**: you feel the chip damage, so the number becomes something to
investigate, not something to trust blindly. Clear, observable feedback is what
makes it good design instead of a bug. This tool just makes the lesson legible.

## What it does

- Ranks weapons/affinities for **your** stats, upgrade level, and one/two-handing.
- Re-ranks by **effective damage** against a roster of real enemies (Crucible
  Knight, Starscourge Radahn, Godfrey, Malenia, Fire Giant, Elden Beast, Radagon)
  — each with its actual damage-negation profile.
- Explains the *why*: damage breakdown, scaling grades (S–E), status buildup, and
  a flag when you don't meet a weapon's requirements (the −40% penalty).
- Preset builds (Strength / Dexterity / Quality / Int / Faith / Arcane) that fill
  the stat fields, plus full manual control.

## How it's built

- `optimizer/damage.py` — a from-scratch Python port of Elden Ring's AR formula
  (reinforce params, calc-correct soft-cap curves, attack-element-correct,
  two-handed STR×1.5, requirement penalties, somber vs standard upgrades).
- `optimizer/effective.py` — the per-type negation model: `effective = Σ type
  damage × (1 − negation)`.
- `optimizer/enemies.py` — the sourced enemy roster.
- `optimizer/rank.py` — the ranking/optimization layer.
- `verify.py` — cross-checks the engine against a trusted calculator; all combos
  match exactly.

Every number is one we can re-derive and hand-verify — the point of the project is
the judgment, not a black-box call. See [`SOURCES.md`](SOURCES.md) for provenance.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Sources & credit

- Weapon params: [ThomasJClark/elden-ring-weapon-calculator](https://github.com/ThomasJClark/elden-ring-weapon-calculator) (MIT), extracted from the game's own files.
- AR math verified against [eldenring.tclark.io](https://eldenring.tclark.io).
- Enemy damage negation: [Elden Ring Wiki (Fextralife)](https://eldenring.wiki.fextralife.com/Bosses).

Not affiliated with FromSoftware / Bandai Namco. A portfolio project about product
direction and verification — real data, verified numbers.
