"""
Coach - Diagnostic + Plan d'entrainement personnalise par objectif course
"""

import streamlit as st
import pandas as pd
from lib.coaching import (
    diagnose, generate_weekly_plan, generate_race_plan,
    generate_progression, nutrition_recovery_tips,
    estimate_race_paces, compute_weeks_to_race,
    get_default_utmb_index, RACE_PROFILES, FC_MAX,
)

st.set_page_config(page_title="Coach", page_icon="🧠", layout="wide")

if "df" not in st.session_state:
    st.warning("Retourne a la page d'accueil pour charger les donnees.")
    st.stop()

df = st.session_state["df"]

st.title("🧠 Coach")

# --- Sidebar config ---
with st.sidebar:
    st.subheader("Parametres")
    sessions_week = st.selectbox("Sorties par semaine", [3, 4], index=1)
    analysis_weeks = st.selectbox("Semaines d'analyse", [8, 12, 16], index=1)

    st.markdown("---")
    st.subheader("Objectif course")

    race_options = {p["label"]: k for k, p in RACE_PROFILES.items()}
    race_label = st.selectbox("Type de course", list(race_options.keys()), index=0)
    race_key = race_options[race_label]

    race_date = None
    elevation_profile = None
    utmb_index = None

    if race_key != "general":
        race_date = st.date_input(
            "Date de la course (optionnel)",
            value=None,
            min_value=pd.Timestamp.today().date(),
        )

        if race_key.startswith("trail"):
            elevation_profile = st.radio(
                "Profil de denivele",
                ["Plat / peu de denivele", "Denivele significatif"],
                index=1,
            )
            utmb_index = st.number_input(
                "Indice UTMB",
                min_value=100, max_value=999,
                value=get_default_utmb_index(),
                help="Ton indice UTMB (visible sur utmb.world). Sert a estimer les temps de course trail.",
            )

# --- Diagnostic ---
diag = diagnose(df, weeks=analysis_weeks)

st.subheader("📋 Diagnostic")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Volume moyen", f"{diag['avg_km_week']} km/sem")
col2.metric("D+ moyen", f"{diag['avg_elev_week']} m/sem")
col3.metric("Sorties/semaine", f"{diag['avg_runs_week']}")
col4.metric("Heures/semaine", f"{diag['avg_hours_week']}h")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Allure GAP", f"{diag['gap_recent']} min/km")

pace_trend = diag["pace_trend"]
col2.metric("Tendance allure", f"{pace_trend:+.2f} min/km",
            delta="plus rapide" if pace_trend < 0 else "plus lent",
            delta_color="inverse")

col3.metric("Sorties longues", f"{diag['long_runs_count']} (>{20}km)")
col4.metric("Repos moyen", f"{diag['avg_rest_days']}j")

if diag.get("cardiac_efficiency"):
    st.metric("Efficacite cardiaque", f"{diag['cardiac_efficiency']} bpm/(km/h)",
              help="Plus bas = plus efficace. Ratio FC moyenne / vitesse sur terrain plat.")

# --- Volume warning for race objectives ---
if race_key != "general":
    profile = RACE_PROFILES[race_key]
    if diag["avg_km_week"] < profile["min_weekly_km"]:
        st.warning(
            f"⚠️ Ton volume actuel ({diag['avg_km_week']} km/sem) est en dessous du minimum "
            f"recommande ({profile['min_weekly_km']} km/sem) pour un {profile['label']}. "
            f"Le plan sera adapte mais prevois un cycle de montee en volume avant."
        )

# --- Recommendations ---
st.markdown("---")
st.subheader("💡 Recommandations")

for rec in diag["recommendations"]:
    priority = rec["priority"]
    if priority == "HAUTE":
        st.error(f"**{rec['category']}** — {rec['message']}")
    elif priority == "ATTENTION":
        st.warning(f"**{rec['category']}** — {rec['message']}")
    elif priority == "POSITIF":
        st.success(f"**{rec['category']}** — {rec['message']}")
    else:
        st.info(f"**{rec['category']}** — {rec['message']}")

if not diag["recommendations"]:
    st.success("Tout est en ordre ! Continue comme ca.")

# --- Race paces (if race selected) ---
if race_key != "general":
    st.markdown("---")
    st.subheader(f"🎯 Allures estimees — {profile['label']}")

    if race_date:
        weeks_to_race = compute_weeks_to_race(race_date)
        st.caption(f"Course dans {weeks_to_race} semaines ({race_date.strftime('%d/%m/%Y')})")

    paces = estimate_race_paces(diag, race_key, utmb_index)

    if "info" in paces:
        st.info(paces["info"])
    else:
        # Separate numeric paces from text descriptions
        numeric_paces = {k: v for k, v in paces.items() if isinstance(v, (int, float))}
        text_paces = {k: v for k, v in paces.items() if isinstance(v, str) and k != "temps_estime" and k != "km_effort"}

        if "temps_estime" in paces:
            if race_key.startswith("trail") and utmb_index:
                help_text = f"Base sur indice UTMB {utmb_index}. {int(paces.get('km_effort', 0))} km effort."
            else:
                help_text = f"Base sur ton allure GAP recente ({diag['gap_recent']} min/km)."
            st.metric("Temps de course estime", paces["temps_estime"], help=help_text)

        if numeric_paces:
            cols = st.columns(len(numeric_paces))
            for i, (k, v) in enumerate(numeric_paces.items()):
                label = k.replace("_", " ").capitalize()
                cols[i].metric(label, f"{v} min/km")

        for k, v in text_paces.items():
            label = k.replace("_", " ").capitalize()
            st.info(f"**{label}** : {v}")

# --- Plan semaine type ---
st.markdown("---")

if race_key == "general":
    st.subheader("📅 Plan semaine type")
    plan, target_km = generate_weekly_plan(diag, sessions_per_week=sessions_week)
else:
    st.subheader(f"📅 Plan semaine type — {profile['label']}")
    plan, target_km = generate_race_plan(diag, race_key, sessions_week, elevation_profile, utmb_index)

st.caption(f"Volume cible : {target_km} km/semaine")

for session in plan:
    with st.expander(f"**{session['jour']}** — {session['type']} ({session['distance_km']} km, ~{session['duree_min']} min)", expanded=True):
        col1, col2, col3 = st.columns(3)
        col1.metric("Distance", f"{session['distance_km']} km")
        col2.metric("Duree estimee", f"{session['duree_min']} min")
        col3.metric("FC cible", session["fc_cible"])
        st.markdown(session["details"])

# --- Regles cles ---
with st.expander("📌 Regles cles", expanded=False):
    if race_key == "general":
        st.markdown(f"""
- **Facile = VRAIMENT facile** : < {int(FC_MAX * 0.70)} bpm, meme si ca veut dire marcher en montee
- **Seuil = court mais intense** : 20-25 min suffisent, FC entre {int(FC_MAX * 0.80)}-{int(FC_MAX * 0.90)} bpm
- **Longue = lente** : la duree compte, pas l'allure. Vise 1h30+ progressivement
- **Pas de Z3** : si ta FC est entre {int(FC_MAX * 0.70)}-{int(FC_MAX * 0.80)}, soit tu ralentis (Z2), soit tu acceleres (Z4)
""")
    elif race_key == "10km":
        st.markdown(f"""
- **Intervalles** : la seance cle. Respect les temps de recup entre les fractions
- **Tempo** : 20-25 min suffisent a allure seuil, pas plus
- **Longue** : ne depasse pas 18km, l'objectif est l'endurance de base, pas le volume
- **Avant la course** : 1 semaine d'affutage avec volume reduit de moitie
""")
    elif race_key == "semi":
        st.markdown(f"""
- **Tempo** : la seance cle. Allure semi = confortablement dur, tu peux dire quelques mots
- **Intervalles** : plus courts et rapides, pour developper la VMA
- **Longue** : monte progressivement vers 22-24km max
- **Les 2 derniers km du tempo** : accelere legerement, ca simule la fin de course
""")
    elif race_key == "marathon":
        st.markdown(f"""
- **Sortie longue** : LA seance cle. Monte de 2km/semaine, max 35km
- **Allure marathon** : 40-60min a allure cible, pas plus. C'est un effort modere (Z3)
- **Alimentation** : teste ta nutrition en course pendant les longues (gels, boisson, solide)
- **Taper** : 2 semaines de reduction. Tu te sentiras lourd — c'est normal et benefique
""")
    elif race_key.startswith("trail"):
        st.markdown(f"""
- **Temps sur pieds** > distance : une sortie de 4h a 6 min/km vaut mieux que 25km a 5 min/km
- **Marche active en montee** : c'est une technique, pas un echec. Entraine-la avec batons
- **Enchainement (back-to-back)** : simule la fatigue de course. Le J2 est aussi important que le J1
- **Descente** : entraine la descente technique, c'est la ou se jouent les blessures et le temps
- **Nutrition** : en ultra, mange tot et regulierement (toutes les 30-45 min). N'attends pas d'avoir faim
""")

# --- Progression ---
st.markdown("---")

if race_key == "general":
    st.subheader("📈 Progression 8 semaines")
    progression = generate_progression(diag, weeks=8, sessions_per_week=sessions_week)
else:
    plan_weeks = profile["plan_weeks"]
    if race_date:
        weeks_to_race = compute_weeks_to_race(race_date)
        if weeks_to_race:
            plan_weeks = max(6, min(weeks_to_race, plan_weeks))

    st.subheader(f"📈 Progression {plan_weeks} semaines — {profile['label']}")
    progression = generate_progression(
        diag, weeks=plan_weeks, sessions_per_week=sessions_week,
        race_key=race_key, race_date=race_date,
    )

prog_df = pd.DataFrame(progression)
prog_df = prog_df[["semaine", "phase", "km_total", "sortie_longue_km", "nb_seances", "seances", "note"]]
prog_df.columns = ["Semaine", "Phase", "km total", "Longue (km)", "Seances", "Contenu", "Note"]

st.dataframe(
    prog_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Semaine": st.column_config.NumberColumn(format="S%d", width="small"),
        "Phase": st.column_config.TextColumn(width="small"),
        "km total": st.column_config.NumberColumn(format="%.0f km"),
        "Longue (km)": st.column_config.NumberColumn(format="%.0f km"),
        "Seances": st.column_config.NumberColumn(format="%d", width="small"),
        "Contenu": st.column_config.TextColumn(width="large"),
        "Note": st.column_config.TextColumn(width="medium"),
    }
)

if race_key == "general":
    st.caption("Schema 3:1 — 3 semaines de montee progressive, 1 semaine de decharge (-30%)")
else:
    st.caption(f"Schema 3:1 avec {profile['taper_weeks']} semaine(s) d'affutage avant la course")

# --- Nutrition & Recovery ---
st.markdown("---")
st.subheader("🥗 Nutrition & Recuperation")

tips = nutrition_recovery_tips(diag)
for tip in tips:
    with st.expander(f"**{tip['category']}**"):
        st.write(tip["tip"])
