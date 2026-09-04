"""
Elden Ring Build Optimizer — v1 (base game).

Rank every base-game weapon/affinity for YOUR stats, then re-rank by what
actually lands against a real enemy's damage negation. The point the tool makes:
the highest-AR weapon is often not the one that hits hardest.
"""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(_HERE)                       # so data/ paths resolve
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)         # so `optimizer` imports resolve

import pandas as pd
import streamlit as st

from optimizer.damage import Regulation, ATTRIBUTES
from optimizer.rank import rank, WEAPON_TYPE_NAMES, AFFINITY_NAMES
from optimizer.effective import make_score, effective_damage, ar_lost, NEUTRAL
from optimizer.enemies import ROSTER, BY_KEY

st.set_page_config(page_title="Elden Ring Build Optimizer",
                   page_icon="⚔️", layout="wide")

# ---- styling ---------------------------------------------------------------
st.markdown("""
<style>
  .stApp { background: #14100c; }
  h1, h2, h3 { color: #e8d9b5; letter-spacing: .3px; }
  .tagline { color:#b8a888; font-size:1.02rem; margin-top:-.4rem; }
  .card { background:#1e1812; border:1px solid #3a2f22; border-radius:10px;
          padding:14px 16px; margin:6px 0; }
  .neg { display:inline-block; min-width:52px; color:#d8c9a5; font-variant-numeric:tabular-nums; }
  .barwrap { background:#2a2118; border-radius:4px; height:9px; width:120px;
             display:inline-block; vertical-align:middle; overflow:hidden; }
  .bar { height:9px; background:linear-gradient(90deg,#b8863b,#e0b45a); }
  .pick { color:#e0b45a; font-weight:700; }
  .muted { color:#8f8266; }
  [data-testid="stMetricValue"] { color:#e0b45a; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load():
    return Regulation("data/regulation-vanilla-v1.17.json")


reg = load()

PRESETS = {
    "Strength":          dict(str=60, dex=14, int=9,  fai=9,  arc=9),
    "Dexterity":         dict(str=14, dex=60, int=9,  fai=9,  arc=9),
    "Quality":           dict(str=50, dex=50, int=9,  fai=9,  arc=9),
    "Intelligence":      dict(str=14, dex=12, int=60, fai=9,  arc=9),
    "Faith":             dict(str=14, dex=14, int=9,  fai=60, arc=9),
    "Arcane / Bleed":    dict(str=16, dex=18, int=9,  fai=9,  arc=60),
}
LABELS = dict(str="STR", dex="DEX", int="INT", fai="FAI", arc="ARC")

# ---- header ----------------------------------------------------------------
st.title("⚔️ Elden Ring Build Optimizer")
st.markdown(
    '<div class="tagline">Your weapon shows one number. You hit the boss and '
    'barely scratch it. The game never tells you why — it just lets you see it. '
    'That gap is the lesson. This tool makes it explicit: what your weapon '
    '<i>claims</i>, versus what actually lands. Base game.</div>',
    unsafe_allow_html=True)

st.markdown(
    '<div class="card" style="margin-top:12px"><b style="color:#e0b45a">'
    'Why the number &ldquo;lies&rdquo; &mdash; and why that&rsquo;s good design.</b> '
    'Attack Rating assumes zero resistance. Real damage is what&rsquo;s left after '
    'the enemy&rsquo;s negation, and the game never spells that out. Surfacing a '
    'number that doesn&rsquo;t predict real damage sounds like a flaw &mdash; it '
    'works because it&rsquo;s <i>observable</i>. You feel the chip damage, so the '
    'number becomes something to investigate, not something to trust blindly. '
    'Clear, observable feedback is what makes it good design instead of a bug.'
    '</div>', unsafe_allow_html=True)

# ---- sidebar: build + target ----------------------------------------------
with st.sidebar:
    st.markdown("### Your build")
    st.caption("Load a preset, then fine-tune.")
    pcols = st.columns(2)
    for i, (name, vals) in enumerate(PRESETS.items()):
        if pcols[i % 2].button(name, width="stretch"):
            for a in ATTRIBUTES:
                st.session_state[f"stat_{a}"] = vals[a]
    for a in ATTRIBUTES:
        st.session_state.setdefault(f"stat_{a}", PRESETS["Strength"][a])

    scols = st.columns(5)
    for c, a in zip(scols, ATTRIBUTES):
        c.number_input(LABELS[a], 1, 99, key=f"stat_{a}")
    st.caption("Damage scaling slows at soft caps — roughly 20, 50–60, and 80. "
               "Presets stop at 60: a soft cap for STR/DEX/Arcane, and a strong "
               "practical point for INT/Faith (which cap at 50 and 80).")

    st.markdown("---")
    upgrade = st.slider("Upgrade level (+N)", 0, 25, 25,
                        help="Somber weapons cap at +10 automatically.")
    two_handing = st.checkbox("Two-handed (STR ×1.5)", value=False)

    st.markdown("### Target")
    target_names = ["No target — raw AR"] + [e.name for e in ROSTER]
    target_choice = st.selectbox("Rank damage against:", target_names,
                                 help="Switch targets and watch the ranking flip.")
    enemy = None if target_choice.startswith("No target") else \
        next(e for e in ROSTER if e.name == target_choice)

    with st.expander("Filters"):
        cat_names = sorted(WEAPON_TYPE_NAMES.values())
        chosen_cats = st.multiselect("Weapon categories", cat_names,
                                     help="Empty = all melee categories.")
        requirements_only = st.checkbox("Only weapons I can wield", value=False,
                                        help="Hide weapons you don't meet the "
                                             "requirements for (−40% penalty).")
        collapse = st.checkbox("Best affinity per weapon only", value=True,
                               help="Off = show every affinity separately.")
        top_n = st.slider("Show top", 5, 50, 15)

# ---- compute ---------------------------------------------------------------
attrs = {a: st.session_state[f"stat_{a}"] for a in ATTRIBUTES}
profile = enemy.negation if enemy else NEUTRAL
name_to_id = {v: k for k, v in WEAPON_TYPE_NAMES.items()}
weapon_types = {name_to_id[c] for c in chosen_cats} or None

results = rank(reg, attrs, upgrade=upgrade, two_handing=two_handing,
               weapon_types=weapon_types, requirements_only=requirements_only,
               collapse_affinities=collapse, score_fn=make_score(profile),
               limit=top_n)

# ---- target card + headline -----------------------------------------------
DTYPE_LABELS = [("Phys", 0), ("Magic", 1), ("Fire", 2), ("Ltn", 3), ("Holy", 4)]

left, right = st.columns([2, 1])
with left:
    if enemy:
        st.markdown(f"### Best picks vs **{enemy.name}**")
        if results:
            top = results[0]
            lost, pct = ar_lost(top.result, profile)
            st.markdown(
                f'Top choice: <span class="pick">{top.name}</span> — '
                f'**{math.floor(effective_damage(top.result, profile))}** effective '
                f'damage <span class="muted">(raw AR {top.total_ar}; the target '
                f'eats {pct:.0f}%)</span>.', unsafe_allow_html=True)
    else:
        st.markdown("### Best picks by raw AR")
        st.markdown('<span class="muted">This is what most calculators show. '
                    'Pick a target on the left to see what actually lands.</span>',
                    unsafe_allow_html=True)
with right:
    if enemy:
        bars = ""
        for lbl, t in DTYPE_LABELS:
            n = enemy.negation[t]
            bars += (f'<div><span class="neg">{lbl} {n}%</span>'
                     f'<span class="barwrap"><span class="bar" '
                     f'style="width:{n}%"></span></span></div>')
        st.markdown(f'<div class="card"><b>{enemy.name}</b><br>'
                    f'<span class="muted">NG HP {enemy.hp:,}</span>'
                    f'<div style="margin-top:6px">{bars}</div>'
                    f'<div class="muted" style="margin-top:8px;font-size:.86rem">'
                    f'{enemy.note}</div></div>', unsafe_allow_html=True)

# ---- results table ---------------------------------------------------------
rows = []
for i, r in enumerate(results, 1):
    eff = math.floor(effective_damage(r.result, profile))
    dmg = " · ".join(f"{k} {v}" for k, v in
                     sorted(r.breakdown.items(), key=lambda kv: -kv[1]))
    scal = " ".join(f"{a.upper()} {g}" for a, g in
                    sorted(r.scaling.items(), key=lambda kv: "SABCDE-".index(kv[1])))
    status = " · ".join(f"{k} {v}" for k, v in r.status.items())
    warn = "" if r.meets_requirements else \
        "needs " + ", ".join(f"{a.upper()} {v}" for a, v in r.missing.items())
    rows.append({
        "#": i, "Weapon": r.name,
        "Effective": eff, "Raw AR": r.total_ar,
        "Damage": dmg, "Scaling": scal, "Status": status,
        "Requirements": warn or "✓",
    })

df = pd.DataFrame(rows)
cols = ["#", "Weapon", "Effective", "Raw AR", "Damage", "Scaling", "Status", "Requirements"]
if not enemy:
    cols.remove("Effective")   # raw AR mode: effective == AR, don't double up

st.dataframe(
    df[cols], hide_index=True, width="stretch",
    column_config={
        "#": st.column_config.NumberColumn(width="small"),
        "Effective": st.column_config.NumberColumn(
            "Effective dmg", help="Per-hit damage after this target's negation."),
        "Raw AR": st.column_config.NumberColumn(
            "Raw AR", help="Attack Rating with no resistances — the paper number."),
    },
)

# ---- honest scope + sources ------------------------------------------------
with st.expander("How this works & what it does *not* model"):
    st.markdown("""
**The idea.** Raw Attack Rating sums every damage type as if the enemy resisted
nothing. In-game, each type is reduced *separately* by the enemy's damage
negation, so a weapon that splits its AR across two types loses more against a
resistant target. This tool ranks by **effective damage** =
Σ (type damage × (1 − that type's negation)).

**What it models:** per-hit direct damage, scaling (incl. soft caps), the
two-handed STR×1.5 bonus, the −40% penalty when you don't meet requirements,
somber vs standard upgrade caps, and each target's real per-type negation.

**What it does _not_ model (yet):** status effects (bleed / frost / rot procs —
e.g. the actual anti-Malenia strategy), hits-to-kill / HP, motion values (some
weapons swing harder per hit), and physical sub-types (Slash / Strike / Pierce —
so a target's specific Slash or Pierce weakness isn't captured). Physical is
treated as Standard. These are the honest v1 limits, not hidden.
""")
    st.markdown("**Sources & method:** weapon params from "
                "[ThomasJClark/elden-ring-weapon-calculator]"
                "(https://github.com/ThomasJClark/elden-ring-weapon-calculator) "
                "(MIT); AR math re-derived and verified against eldenring.tclark.io; "
                "enemy negation from the [Elden Ring Wiki]"
                "(https://eldenring.wiki.fextralife.com/Bosses). Base game, patch 1.17.")

st.caption("Not affiliated with FromSoftware / Bandai Namco. A build-direction "
           "portfolio project — real data, verified numbers.")
