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

import streamlit as st

from optimizer.damage import Regulation, ATTRIBUTES
from optimizer.rank import rank, WEAPON_TYPE_NAMES, AFFINITY_NAMES
from optimizer.effective import make_score, effective_damage, ar_lost, NEUTRAL
from optimizer.enemies import ROSTER, BY_KEY
from optimizer.status import simulate_kill, make_ttk_score

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
  /* results table — themed so scaling is color-coded per attribute */
  .rtbl-wrap { overflow-x:auto; border:1px solid #3a2f22; border-radius:10px;
               margin-top:6px; }
  .rtbl { border-collapse:collapse; width:100%; font-size:.9rem; }
  .rtbl th { text-align:left; color:#b8a888; font-weight:600; background:#221b13;
             padding:8px 12px; border-bottom:1px solid #3a2f22; white-space:nowrap; }
  .rtbl td { padding:7px 12px; border-bottom:1px solid #241d15; color:#d8c9a5;
             white-space:nowrap; }
  .rtbl tbody tr:nth-child(odd) { background:#181410; }
  .rtbl tbody tr:hover { background:#2a2013; }
  .rtbl .num { text-align:right; font-variant-numeric:tabular-nums; }
  .rtbl .wname { color:#e0b45a; font-weight:600; }
  .statlbl { text-align:center; font-weight:700; font-size:.78rem;
             padding-bottom:2px; margin-bottom:1px; border-bottom:2px solid transparent; }
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
# Signature color per attribute — used on the sidebar inputs AND the scaling
# column, so "ARC" reads the same purple everywhere.
STAT_COLORS = dict(str="#e0684f", dex="#6cc06f", int="#5aa2e0",
                   fai="#e8cf5b", arc="#b57fe0")

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
    'Clear, observable feedback is what makes it good design instead of a bug. '
    '<span style="color:#c98a8a">And it lies a second way:</span> bleed and frost '
    'never appear in that number, yet each proc tears off a share of the '
    'enemy&rsquo;s health &mdash; pick a target and rank by <i>hits-to-kill</i> to '
    'watch a blood weapon overtake the &ldquo;strongest&rdquo; one.'
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

    _now = {a: st.session_state[f"stat_{a}"] for a in ATTRIBUTES}
    _peak = max(_now.values())
    scols = st.columns(5)
    for c, a in zip(scols, ATTRIBUTES):
        with c:
            focus = _now[a] == _peak and _peak > 9      # the build's headline stat
            border = STAT_COLORS[a] if focus else "transparent"
            bg = "background:rgba(255,255,255,.06);border-radius:5px 5px 0 0;" if focus else ""
            st.markdown(
                f'<div class="statlbl" style="color:{STAT_COLORS[a]};'
                f'border-bottom-color:{border};{bg}">{LABELS[a]}</div>',
                unsafe_allow_html=True)
            st.number_input(LABELS[a], 1, 99, key=f"stat_{a}",
                            label_visibility="collapsed")
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

    rank_mode = "Effective damage / hit"
    if enemy:
        rank_mode = st.radio(
            "Rank by",
            ["Hits to kill (with status)", "Effective damage / hit"],
            index=1,
            help="Hits-to-kill simulates the whole fight, folding in bleed & "
                 "frost procs — that's where blood/cold weapons overtake the "
                 "highest-damage pick. Effective damage ranks by a single hit.")

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

rank_by_ttk = bool(enemy) and rank_mode.startswith("Hits")
score_fn = make_ttk_score(enemy, profile) if rank_by_ttk else make_score(profile)

results = rank(reg, attrs, upgrade=upgrade, two_handing=two_handing,
               weapon_types=weapon_types, requirements_only=requirements_only,
               collapse_affinities=collapse, score_fn=score_fn,
               limit=top_n)

# ---- target card + headline -----------------------------------------------
DTYPE_LABELS = [("Phys", 0), ("Magic", 1), ("Fire", 2), ("Ltn", 3), ("Holy", 4)]

left, right = st.columns([2, 1])
with left:
    if enemy:
        st.markdown(f"### Best picks vs **{enemy.name}**")
        if results:
            top = results[0]
            eff_top = math.floor(effective_damage(top.result, profile))
            k = simulate_kill(top.result, enemy, profile)
            if rank_by_ttk:
                extras = []
                if k.bleed_procs:
                    extras.append(f"{k.bleed_procs}× bleed")
                if k.frost_procs:
                    extras.append(f"{k.frost_procs}× frost")
                tail = f"; {', '.join(extras)}" if extras else ""
                st.markdown(
                    f'Fastest kill: <span class="pick">{top.name}</span> — '
                    f'**{k.hits} hits** <span class="muted">({eff_top} dmg/hit'
                    f'{tail})</span>.', unsafe_allow_html=True)
                # the flip: the highest single-hit-damage weapon vs this one
                dmg_ranked = rank(reg, attrs, upgrade=upgrade, two_handing=two_handing,
                                  weapon_types=weapon_types,
                                  requirements_only=requirements_only,
                                  collapse_affinities=collapse,
                                  score_fn=make_score(profile), limit=1)
                if dmg_ranked:
                    dtop = dmg_ranked[0]
                    dk = simulate_kill(dtop.result, enemy, profile)
                    if dtop.name != top.name and dk.hits and k.hits and dk.hits > k.hits:
                        st.markdown(
                            f'<span class="muted">The highest-damage weapon here, '
                            f'<b>{dtop.name}</b> '
                            f'({math.floor(effective_damage(dtop.result, profile))}/hit), '
                            f'needs <b>{dk.hits} hits</b> — {dk.hits - k.hits} more. '
                            f'The paper "best" loses the race.</span>',
                            unsafe_allow_html=True)
                        st.markdown(
                            '<span class="muted">Why? Bleed and frost never '
                            'appear in the damage number &mdash; bleed tears off '
                            'a share of the enemy&rsquo;s max HP, frost strips '
                            'its absorption &mdash; so a lower-hitting weapon can '
                            'end the fight in fewer swings than the '
                            'highest-damage pick.</span>',
                            unsafe_allow_html=True)
            else:
                lost, pct = ar_lost(top.result, profile)
                kill = f'; ~{k.hits} hits to kill' if k.hits else ''
                st.markdown(
                    f'Top choice: <span class="pick">{top.name}</span> — '
                    f'**{eff_top}** effective damage <span class="muted">(raw AR '
                    f'{top.total_ar}; the target eats {pct:.0f}%{kill})</span>.',
                    unsafe_allow_html=True)
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
                    f'<div class="muted" style="margin-top:8px;font-size:.82rem">'
                    f'<b style="color:#c98a8a">Status to proc:</b> '
                    f'{enemy.status_summary()} '
                    f'<span style="font-size:.9em">(first threshold; lower = '
                    f'procs sooner)</span></div>'
                    f'<div class="muted" style="margin-top:6px;font-size:.86rem">'
                    f'{enemy.note}</div></div>', unsafe_allow_html=True)

# ---- results table (themed HTML so scaling is color-coded per attribute) ----
def _scaling_html(scaling: dict) -> str:
    if not scaling:
        return '<span class="muted">—</span>'
    out = []
    for a, g in sorted(scaling.items(), key=lambda kv: "SABCDE-".index(kv[1])):
        out.append(f'<span style="color:{STAT_COLORS[a]};font-weight:700">'
                   f'{LABELS[a]}</span>&nbsp;{g}')
    return " ".join(out)


def _reqs_html(r) -> str:
    if r.meets_requirements:
        return '<span style="color:#6cc06f">✓</span>'
    need = " ".join(f'<span style="color:{STAT_COLORS[a]};font-weight:700">'
                    f'{LABELS[a]} {v}</span>' for a, v in r.missing.items())
    return f'<span style="color:#d98a5a">needs</span> {need}'


HDR_TIPS = {
    "Hits to kill": "Whole-fight sim: direct damage + bleed/frost procs vs this "
                    "target's HP. '(saves N)' = hits the status saved vs pure "
                    "damage. Rot/poison DoT shown separately, not counted here.",
    "Effective dmg": "Per-hit damage after this target's negation.",
    "Raw AR": "Attack Rating with no resistances — the paper number.",
}
headers = ["#", "Weapon"]
headers += (["Hits to kill", "Effective dmg", "Raw AR"] if enemy else ["Raw AR"])
headers += ["Damage", "Scaling", "Status", "Requirements"]

body = ""
for i, r in enumerate(results, 1):
    eff = math.floor(effective_damage(r.result, profile))
    dmg = " · ".join(f"{k} {v}" for k, v in
                     sorted(r.breakdown.items(), key=lambda kv: -kv[1])) or "—"
    status = " · ".join(f"{k} {v}" for k, v in r.status.items()) or "—"
    tds = [f'<td class="num">{i}</td>', f'<td class="wname">{r.name}</td>']
    if enemy:
        tds.append(f'<td>{simulate_kill(r.result, enemy, profile).summary()}</td>')
        tds.append(f'<td class="num">{eff}</td>')
    tds.append(f'<td class="num">{r.total_ar}</td>')
    tds.append(f'<td>{dmg}</td>')
    tds.append(f'<td>{_scaling_html(r.scaling)}</td>')
    tds.append(f'<td>{status}</td>')
    tds.append(f'<td>{_reqs_html(r)}</td>')
    body += f"<tr>{''.join(tds)}</tr>"

head = "".join(
    (f'<th title="{HDR_TIPS[h]}">{h}</th>' if h in HDR_TIPS else f'<th>{h}</th>')
    for h in headers)
legend = " · ".join(f'<span style="color:{STAT_COLORS[a]};font-weight:700">'
                    f'{LABELS[a]}</span>' for a in ATTRIBUTES)
st.markdown(f'<div class="muted" style="font-size:.8rem;margin:4px 0 2px">'
            f'Scaling &amp; requirement colors: {legend}</div>',
            unsafe_allow_html=True)
st.markdown(f'<div class="rtbl-wrap"><table class="rtbl"><thead><tr>{head}</tr>'
            f'</thead><tbody>{body}</tbody></table></div>',
            unsafe_allow_html=True)

if enemy and results:
    _kr_top = simulate_kill(results[0].result, enemy, profile)
    if _kr_top.dot_note:
        st.caption(f"Top pick would also apply {_kr_top.dot_note} — damage-over-"
                   "time, not folded into hits-to-kill (see the notes below).")

# ---- honest scope + sources ------------------------------------------------
with st.expander("How this works & what it does *not* model"):
    st.markdown("""
**The number lies twice.** Raw Attack Rating sums every damage type as if the
enemy resisted nothing — and it ignores status entirely.

1. **Negation (v1).** Each damage type is reduced *separately* by the enemy's
   negation, so a split-damage weapon loses more against a resistant target.
   **Effective damage** = Σ (type damage × (1 − that type's negation)).
2. **Status (v2).** Bleed and frost don't show up in any AR number, but they
   chunk a percentage of the enemy's *max HP*. So the tool simulates the whole
   fight hit-by-hit — direct damage **plus** procs — and ranks by
   **hits-to-kill**. That's where a blood or cold weapon overtakes the
   highest-damage pick (the classic Malenia case).

**What it models:** per-hit direct damage, scaling (incl. soft caps), two-handed
STR×1.5, the −40% under-requirement penalty, somber vs standard upgrade caps,
each target's per-type negation, and **status procs** — per-hit buildup vs each
target's real escalating thresholds (and immunities), with sourced proc damage:
bleed 10.5% max HP +70, frost 7% +21 and −20% absorption, rot/poison DoT.

**Honest limits (stated, not hidden):**
- **Frost procs once.** The wiki says frost can't rebuild until its 30s debuff
  clears, so we take one proc and keep the −20% absorption on for the rest of the
  fight. **Bleed** has no cooldown, so it keeps procing up the escalating ladder.
- **Rot / poison are damage-over-time**, so they're reported separately, *not*
  folded into hits-to-kill (that needs an attack-cadence model we haven't built).
- **No buildup decay** — assumes sustained aggression; slow/poke play procs slower.
- **One hit = one application.** No motion values (some swings hit harder / twice)
  and no physical Slash/Strike/Pierce sub-types — physical is treated as Standard.
""")
    st.markdown("**Sources & method:** weapon params from "
                "[ThomasJClark/elden-ring-weapon-calculator]"
                "(https://github.com/ThomasJClark/elden-ring-weapon-calculator) "
                "(MIT); AR math re-derived and verified against eldenring.tclark.io; "
                "enemy negation, status thresholds, and proc formulas from the "
                "Elden Ring Wiki ([Hemorrhage]"
                "(https://eldenring.wiki.fextralife.com/Hemorrhage), [Frostbite]"
                "(https://eldenring.wiki.fextralife.com/Frostbite), [Scarlet Rot]"
                "(https://eldenring.wiki.fextralife.com/Scarlet+Rot), and each "
                "[boss page](https://eldenring.wiki.fextralife.com/Bosses)). "
                "Base game, patch 1.17.")

st.caption("Not affiliated with FromSoftware / Bandai Namco. A build-direction "
           "portfolio project — real data, verified numbers.")
