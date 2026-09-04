# Data & formula provenance

**Weapon params:** `data/regulation-vanilla-v1.17.json` is the base-game regulation data
extracted by **[ThomasJClark/elden-ring-weapon-calculator](https://github.com/ThomasJClark/elden-ring-weapon-calculator)**
(MIT-licensed), which generates it directly from Elden Ring's own game files. Used with
credit under MIT. The underlying game data belongs to FromSoftware / Bandai Namco.

**Damage formula:** the AR math in `optimizer/damage.py` is our own Python re-implementation
of the calculation described in that project (`src/calculator/calculator.ts` +
`src/regulationData.ts`) — re-derived so every number is one we can verify by hand rather
than a black-box call. Cross-check reference: the community
[TarnishedSpreadsheet](https://github.com/TomPoulton/elden-ring-damage-calculator).

**Enemy damage negation:** the roster in `optimizer/enemies.py` uses per-type negation
values published on the **[Elden Ring Wiki (Fextralife)](https://eldenring.wiki.fextralife.com/Bosses)**
enemy pages (each enemy's `source` field links its page), which surface the game's datamined
`NpcParam` negation tables. Physical is stored as Standard negation; the Slash/Strike/Pierce
sub-splits are a v2 refinement. HP is NG. Godfrey uses his Phase-1 profile.

**Verification:** numbers are hand-checked against **eldenring.tclark.io** (same data source,
independent JS implementation). Note: this engine reports unfloored attack power (matching
tclark's display); in-game per-hit AR is the floor of the summed damage types.

**Scope:** base game only (patch 1.17). DLC (Shadow of the Erdtree) entries are present in
the file flagged `dlc: true` and are filtered out for v1.
