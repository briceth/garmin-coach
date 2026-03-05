"""
Coach - Diagnostic + Plan d'entrainement personnalise
"""

import streamlit as st
import pandas as pd
from lib.coaching import diagnose, generate_weekly_plan, generate_progression, nutrition_recovery_tips

st.set_page_config(page_title="Coach", page_icon="🧠", layout="wide")

if "df" not in st.session_state:
    st.warning("Retourne a la page d'accueil pour charger les donnees.")
    st.stop()

df = st.session_state["df"]

st.title("🧠 Coach")

# --- Config ---
with st.sidebar:
    st.subheader("Parametres")
    sessions_week = st.selectbox("Sorties par semaine", [3, 4], index=1)
    analysis_weeks = st.selectbox("Semaines d'analyse", [8, 12, 16], index=1)

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

# --- Plan semaine type ---
st.markdown("---")
st.subheader("📅 Plan semaine type")

plan, target_km = generate_weekly_plan(diag, sessions_per_week=sessions_week)
st.caption(f"Volume cible : {target_km} km/semaine")

plan_df = pd.DataFrame(plan)
plan_df.columns = ["Jour", "Type", "Distance (km)", "Duree (min)", "FC cible", "Details"]

# Style the table
st.dataframe(
    plan_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Jour": st.column_config.TextColumn(width="small"),
        "Type": st.column_config.TextColumn(width="medium"),
        "Distance (km)": st.column_config.NumberColumn(format="%.1f km"),
        "Duree (min)": st.column_config.NumberColumn(format="%d min"),
        "FC cible": st.column_config.TextColumn(width="medium"),
        "Details": st.column_config.TextColumn(width="large"),
    }
)

# --- Regles cles ---
with st.expander("📌 Regles cles", expanded=False):
    st.markdown(f"""
- **Facile = VRAIMENT facile** : < {int(185 * 0.70)} bpm, meme si ca veut dire marcher en montee
- **Seuil = court mais intense** : 20-25 min suffisent, FC entre {int(185 * 0.80)}-{int(185 * 0.90)} bpm
- **Longue = lente** : la duree compte, pas l'allure. Vise 1h30+ progressivement
- **Pas de Z3** : si ta FC est entre {int(185 * 0.70)}-{int(185 * 0.80)}, soit tu ralentis (Z2), soit tu acceleres (Z4)
""")

# --- Progression 8 semaines ---
st.markdown("---")
st.subheader("📈 Progression 8 semaines")

progression = generate_progression(diag, weeks=8, sessions_per_week=sessions_week)
prog_df = pd.DataFrame(progression)
prog_df.columns = ["Semaine", "km total", "Longue (km)", "Nb seances", "Note"]

st.dataframe(
    prog_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Semaine": st.column_config.NumberColumn(format="S%d", width="small"),
        "km total": st.column_config.NumberColumn(format="%.0f km"),
        "Longue (km)": st.column_config.NumberColumn(format="%.0f km"),
        "Nb seances": st.column_config.NumberColumn(format="%d", width="small"),
        "Note": st.column_config.TextColumn(width="medium"),
    }
)

st.caption("Schema 3:1 — 3 semaines de montee progressive, 1 semaine de decharge (-30%)")

# --- Nutrition & Recovery ---
st.markdown("---")
st.subheader("🥗 Nutrition & Recuperation")

tips = nutrition_recovery_tips(diag)
for tip in tips:
    with st.expander(f"**{tip['category']}**"):
        st.write(tip["tip"])
