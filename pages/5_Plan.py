"""
Plan - Plan d'entrainement hebdomadaire structure pour le trail
Avec historique des semaines (SQLite) et prevu vs realise (Garmin).
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from lib.metrics import FC_MAX
from lib.db import get_week_start, save_plan, get_plan, get_all_plans, update_notes

st.set_page_config(page_title="Plan", page_icon="📋", layout="wide")

# --- Semaine plan template ---

WEEK_PLAN = [
    {
        "jour": "Lundi",
        "jour_num": 0,
        "titre": "Renforcement musculaire",
        "emoji": "💪",
        "type": "renfo",
        "duree": "50-60 min",
        "intensite": "Moderee",
        "fc_cible": None,
        "allure_cible": None,
        "km_cible": 0,
        "description": "Rotation A/B. Recup 30-45 sec entre chaque serie. Attention au dos et position !",
        "details": None,
        "rotations_renfo": {
            "Semaine A — RENFO EXC/Conc (force + charges)": [
                {
                    "titre": "Echauffement",
                    "exercices": [
                        "Run 20 min",
                        "8 Squats / 8 fentes alternees / 10' chaise — x2",
                    ],
                },
                {
                    "titre": "Au sol / Sur banc",
                    "exercices": [
                        "15 Hip Thrust 2 jambes (+20kg, dos sur banc) / 2x12 sur 1 jambe LENTEMENT — x1",
                    ],
                },
                {
                    "titre": "Sur barre guidee (ou barre libre)",
                    "exercices": [
                        "20 Squats 20kg (descente 2 temps/sec + poussee 1 temps rapide)",
                        "20 Squats 30kg",
                        "15 Squats 40kg — x2",
                    ],
                },
                {
                    "titre": "Sur Leg Press",
                    "exercices": [
                        "12 Leg Press 40kg",
                        "16 Leg Press 50kg (poussee 2 jambes / RETOUR 1 jambe en 4 sec, alterner D et G)",
                        "12 Leg Press 60kg (poussee 2 jambes / RETOUR 1 jambe en 4 sec, alterner D et G) — x2",
                    ],
                },
                {
                    "titre": "Debout avec KB 15kg",
                    "exercices": [
                        "2x10 Deadlift Roumain par jambe (recup 20'')",
                    ],
                },
            ],
            "Semaine B — Circuit Training (cardio + endurance musculaire)": [
                {
                    "titre": "Echauffement",
                    "exercices": [
                        "Run 15 min + mobilite articulaire 5 min",
                    ],
                },
                {
                    "titre": "Circuit — 4 tours, 30'' travail / 15'' recup, 2 min recup entre tours",
                    "exercices": [
                        "Jump Squats",
                        "Pompes",
                        "Fentes sautees alternees",
                        "Mountain Climbers",
                        "Box Step-ups (rapides, banc haut)",
                        "Burpees",
                        "Planche dynamique (epaule taps)",
                        "Squat isometrique (chaise)",
                    ],
                },
                {
                    "titre": "Gainage & Stabilite",
                    "exercices": [
                        "Planche ventrale — 3x45 sec",
                        "Planche laterale — 3x30 sec/cote",
                        "Copenhagen Plank — 3x20 sec/cote",
                        "Bird Dog — 3x10/cote",
                        "Superman — 3x12",
                    ],
                },
                {
                    "titre": "Retour au calme",
                    "exercices": [
                        "Etirements 10 min (ischio-jambiers, quadriceps, psoas, mollets)",
                    ],
                },
            ],
        },
    },
    {
        "jour": "Mardi",
        "jour_num": 1,
        "titre": "Qualite 1 — Intervalles / VMA / Cotes",
        "emoji": "⚡",
        "type": "qualite",
        "duree": "65-80 min",
        "intensite": "Haute (Z4-Z5)",
        "fc_cible": f"{int(FC_MAX * 0.85)}-{FC_MAX} bpm",
        "allure_cible": "< 4:00/km",
        "km_cible": 13.5,
        "description": "Puissance aerobie et force en montee. 12-15 km.",
        "rotations": [
            "Semaine A — Cotes + Relance",
            "Semaine B — VMA courte",
            "Semaine C — Fartlek terrain",
        ],
        "rotations_detail": {
            "Semaine A — Cotes + Relance": [
                {"phase": "Echauffement", "duree": "15 min", "allure": "~5:30/km → 5:00/km", "fc": "Z1→Z2", "details": "Progressif, finir par 3-4 accelerations de 10''"},
                {"phase": "Corps de seance", "duree": "30-35 min", "allure": "< 4:00/km en montee", "fc": "Z4-Z5 (163-192 bpm)", "details": "8x(3' cote raide 10-15% + descente trot recup). Cible : 300-400m D+. Pas courts, buste droit, regard devant."},
                {"phase": "Retour au calme", "duree": "10-15 min", "allure": "~5:30/km", "fc": "Z1", "details": "Trot tres facile, etirements dynamiques"},
            ],
            "Semaine B — VMA courte": [
                {"phase": "Echauffement", "duree": "15 min", "allure": "~5:30/km → 5:00/km", "fc": "Z1→Z2", "details": "Progressif + 3 lignes droites de 80m"},
                {"phase": "Bloc 1 — VMA", "duree": "20 min", "allure": "3:45-3:55/km", "fc": "Z5 (173-192 bpm)", "details": "10x(1' vite / 1' recup trot). Vise une allure reguliere sur les 10 repetitions."},
                {"phase": "Bloc 2 — Sprints cote", "duree": "10 min", "allure": "Max", "fc": "Z5", "details": "6x(30'' sprint en cote / 30'' recup marche). Explosivite pure."},
                {"phase": "Retour au calme", "duree": "10-15 min", "allure": "~5:30/km", "fc": "Z1", "details": "Trot facile"},
            ],
            "Semaine C — Fartlek terrain": [
                {"phase": "Echauffement", "duree": "15 min", "allure": "~5:00/km", "fc": "Z2", "details": "Sur sentier/chemin, mise en route progressive"},
                {"phase": "Fartlek", "duree": "40 min", "allure": "Variable : 4:00-5:00/km", "fc": "Z2-Z5", "details": "Au feeling : accelere en montee (Z4-Z5), relance en descente (Z3-Z4), recup sur le plat (Z2). Travail de lecture de terrain et proprioception."},
                {"phase": "Retour au calme", "duree": "10 min", "allure": "~5:30/km", "fc": "Z1", "details": "Trot facile + etirements"},
            ],
        },
    },
    {
        "jour": "Mercredi",
        "jour_num": 2,
        "titre": "Footing recuperation",
        "emoji": "🟢",
        "type": "facile",
        "duree": "45-55 min",
        "intensite": "Basse (Z1-Z2)",
        "fc_cible": f"< {int(FC_MAX * 0.70)} bpm",
        "allure_cible": "5:20-5:30/km",
        "km_cible": 9,
        "description": "Recuperation active. 8-10 km. Respiration nasale.",
    },
    {
        "jour": "Jeudi",
        "jour_num": 3,
        "titre": "Qualite 2 — Seuil / Allure specifique",
        "emoji": "🔥",
        "type": "qualite",
        "duree": "70-85 min",
        "intensite": "Moderee-Haute (Z3-Z4)",
        "fc_cible": f"{int(FC_MAX * 0.80)}-{int(FC_MAX * 0.90)} bpm",
        "allure_cible": "~4:15/km",
        "km_cible": 15.5,
        "description": "Seuil lactique, effort prolonge. 14-17 km.",
        "rotations": [
            "Semaine A — Seuil continu",
            "Semaine B — Progressif",
            "Semaine C — Allure spe trail",
        ],
        "rotations_detail": {
            "Semaine A — Seuil continu": [
                {"phase": "Echauffement", "duree": "20 min", "allure": "~5:00/km", "fc": "Z2", "details": "Progressif, finir par 2-3 accelerations de 15''"},
                {"phase": "Corps de seance", "duree": "36 min", "allure": "~4:15/km", "fc": "Z4 (154-173 bpm)", "details": "3x10 min a allure seuil, recup 3 min trot entre chaque. L'effort est soutenu mais controlable — tu peux dire quelques mots."},
                {"phase": "Retour au calme", "duree": "15 min", "allure": "~5:30/km", "fc": "Z1", "details": "Trot facile"},
            ],
            "Semaine B — Progressif": [
                {"phase": "Echauffement", "duree": "15 min", "allure": "~5:00/km", "fc": "Z2", "details": "Mise en route progressive"},
                {"phase": "Progressif", "duree": "30 min", "allure": "5:00 → 4:30 → 4:15/km", "fc": "Z2→Z3→Z4", "details": "10 min Z2 (~5:00/km) → 10 min Z3 (~4:30/km) → 10 min Z4 (~4:15/km). Chaque palier doit etre stable. Simule la gestion d'effort en course."},
                {"phase": "Retour au calme", "duree": "15 min", "allure": "~5:30/km", "fc": "Z1", "details": "Trot facile"},
            ],
            "Semaine C — Allure spe trail": [
                {"phase": "Echauffement", "duree": "20 min", "allure": "~5:00/km", "fc": "Z2", "details": "Sur terrain vallonne si possible"},
                {"phase": "Corps de seance", "duree": "40 min", "allure": "~4:15/km (plat), effort Z4 (montee)", "fc": "Z4 (154-173 bpm)", "details": "4x(8 min seuil + 2 min recup trot). 2 series sur le plat, 2 series en montee. En montee : gere par FC, pas par allure."},
                {"phase": "Retour au calme", "duree": "15 min", "allure": "~5:30/km", "fc": "Z1", "details": "Trot facile, descente si possible pour travailler la technique"},
            ],
        },
    },
    {
        "jour": "Vendredi",
        "jour_num": 4,
        "titre": "Footing aerobie",
        "emoji": "🏃",
        "type": "facile",
        "duree": "55-65 min",
        "intensite": "Moderee (Z2)",
        "fc_cible": f"{int(FC_MAX * 0.60)}-{int(FC_MAX * 0.70)} bpm",
        "allure_cible": "~5:00/km",
        "km_cible": 11,
        "description": "Maintien du volume, pre-activation. 10-12 km.",
    },
    {
        "jour": "Samedi",
        "jour_num": 5,
        "titre": "Sortie longue trail",
        "emoji": "⛰️",
        "type": "longue",
        "duree": "2h30-4h30",
        "intensite": "Basse (Z1-Z2)",
        "fc_cible": f"< {int(FC_MAX * 0.75)} bpm",
        "allure_cible": "Effort, pas allure",
        "km_cible": 25,
        "description": "Endurance, temps sur pieds, D+. 20-30 km, 800-1500m D+.",
    },
    {
        "jour": "Dimanche",
        "jour_num": 6,
        "titre": "Recuperation / Enchainement",
        "emoji": "🧘",
        "type": "facile",
        "duree": "45-55 min",
        "intensite": "Tres basse (Z1)",
        "fc_cible": f"< {int(FC_MAX * 0.65)} bpm",
        "allure_cible": "6:00-6:30/km",
        "km_cible": 9,
        "description": "Recup active sur jambes fatiguees. 8-10 km.",
    },
]

DECHARGE_FACTOR = 0.70
JOUR_NAMES_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def build_week_plan(week_num_in_cycle):
    """Build the plan for a given week in the 3:1 cycle (1-4). Week 4 = decharge."""
    is_decharge = (week_num_in_cycle == 4)
    plan = []
    for session in WEEK_PLAN:
        s = dict(session)
        if is_decharge:
            if s["type"] == "qualite":
                s["km_cible"] = round(s["km_cible"] * DECHARGE_FACTOR, 1)
                s["duree"] = "45-55 min"
                s["intensite"] += " (allege)"
            elif s["type"] == "longue":
                s["km_cible"] = round(s["km_cible"] * 0.60, 1)
                s["duree"] = "1h30-2h"
            elif s["type"] == "facile":
                s["km_cible"] = round(s["km_cible"] * DECHARGE_FACTOR, 1)
        # Pick rotation for running quality sessions
        if s.get("rotations") and not is_decharge:
            idx = (week_num_in_cycle - 1) % len(s["rotations"])
            s["rotation_active"] = s["rotations"][idx]
            # Pick detailed breakdown if available
            if s.get("rotations_detail") and s["rotation_active"] in s["rotations_detail"]:
                s["phases"] = s["rotations_detail"][s["rotation_active"]]
        elif s.get("rotations") and is_decharge:
            s["rotation_active"] = "Seance allegee — garde la structure mais reduis le volume de 30%"
        # Pick rotation for renfo (A/B)
        if s.get("rotations_renfo"):
            keys = list(s["rotations_renfo"].keys())
            if is_decharge:
                # Decharge = semaine A (force) mais avec moins de series
                s["renfo_active_name"] = keys[0] + " (allege : -1 serie par exercice)"
                s["renfo_active_blocks"] = s["rotations_renfo"][keys[0]]
            else:
                idx = (week_num_in_cycle - 1) % len(keys)
                s["renfo_active_name"] = keys[idx]
                s["renfo_active_blocks"] = s["rotations_renfo"][keys[idx]]
        plan.append(s)
    return plan


def get_realise_for_week(df, week_start):
    """Extract Garmin activities for a given week (Mon-Sun)."""
    if df is None or df.empty:
        return None
    week_end = week_start + timedelta(days=6)
    mask = (df["date"].dt.date >= week_start) & (df["date"].dt.date <= week_end)
    week_df = df[mask].copy()
    if week_df.empty:
        return None
    week_df["jour_semaine"] = week_df["date"].dt.weekday
    return week_df


# =============================================
# PAGE
# =============================================

st.title("📋 Plan d'entrainement")

# --- Sidebar ---

with st.sidebar:
    st.subheader("Semaine")
    today = date.today()
    current_monday = get_week_start(today)

    week_options = []
    for i in range(-1, 5):
        monday = current_monday + timedelta(weeks=i)
        label = f"{monday.strftime('%d/%m')} - {(monday + timedelta(days=6)).strftime('%d/%m/%Y')}"
        if monday == current_monday:
            label += " (cette semaine)"
        week_options.append((label, monday))

    selected_label = st.selectbox(
        "Choisir la semaine",
        [label for label, _ in week_options],
        index=1,
    )
    selected_monday = next(monday for label, monday in week_options if label == selected_label)

    st.markdown("---")
    st.subheader("Cycle 3:1")
    cycle_week = st.radio(
        "Semaine dans le cycle",
        [1, 2, 3, 4],
        format_func=lambda x: f"S{x} — {'Decharge' if x == 4 else 'Charge'}",
        index=0,
        help="3 semaines de charge progressive, 1 semaine de decharge (-30%)",
    )

# --- Build or load plan ---

existing_plan = get_plan(selected_monday)
week_plan = build_week_plan(cycle_week)

# Serialize plan for saving
plan_data = {
    "week_start": selected_monday.isoformat(),
    "cycle_week": cycle_week,
    "is_decharge": cycle_week == 4,
    "sessions": [
        {
            "jour": s["jour"],
            "titre": s["titre"],
            "type": s["type"],
            "km_cible": s["km_cible"],
            "duree": s["duree"],
            "intensite": s["intensite"],
            "rotation_active": s.get("rotation_active", ""),
        }
        for s in week_plan
    ],
    "km_total_cible": round(sum(s["km_cible"] for s in week_plan), 1),
}

# --- Header ---

week_end = selected_monday + timedelta(days=6)
phase_label = "Decharge (-30%)" if cycle_week == 4 else f"Charge S{cycle_week}"
st.caption(
    f"Semaine du {selected_monday.strftime('%d/%m')} au {week_end.strftime('%d/%m/%Y')} — "
    f"Cycle {phase_label} — Volume cible : {plan_data['km_total_cible']} km"
)

# --- Save button ---

col_save, col_status = st.columns([1, 3])
with col_save:
    if st.button("💾 Sauvegarder cette semaine"):
        notes = existing_plan["notes"] if existing_plan else ""
        save_plan(selected_monday, plan_data, notes)
        st.rerun()

with col_status:
    if existing_plan:
        st.success(f"Plan sauvegarde le {existing_plan['created_at']}")
    else:
        st.info("Plan non sauvegarde pour cette semaine")


# --- Prevu vs Realise ---

df = st.session_state.get("df")
realise = get_realise_for_week(df, selected_monday)

if realise is not None:
    st.markdown("---")
    st.subheader("📊 Prevu vs Realise")

    total_prevu = plan_data["km_total_cible"]
    total_realise = round(realise["distance_km"].sum(), 1)
    total_elev = round(realise["elevation_m"].sum())
    nb_seances = len(realise)
    total_time = round(realise["duration_min"].sum())

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("km prevu", f"{total_prevu} km")
    col2.metric("km realise", f"{total_realise} km", f"{total_realise - total_prevu:+.1f} km")
    col3.metric("D+ total", f"{total_elev} m")
    col4.metric("Seances", f"{nb_seances}")
    col5.metric("Temps total", f"{total_time // 60:.0f}h{total_time % 60:02.0f}")

    # Per-day comparison
    st.markdown("**Detail par jour :**")

    day_data = []
    for session in week_plan:
        jour_num = session["jour_num"]
        day_date = selected_monday + timedelta(days=jour_num)
        activities = realise[realise["jour_semaine"] == jour_num]

        prevu = session["titre"]
        km_prevu = session["km_cible"]

        if not activities.empty:
            km_fait = round(activities["distance_km"].sum(), 1)
            duree_fait = round(activities["duration_min"].sum())
            fc_moy = round(activities["avg_hr"].mean()) if activities["avg_hr"].notna().any() else "-"
            elev = round(activities["elevation_m"].sum())
            status = "✅"
        else:
            km_fait = 0
            duree_fait = 0
            fc_moy = "-"
            elev = 0
            status = "❌" if km_prevu > 0 else "—"

        day_data.append({
            "": status,
            "Jour": f"{session['emoji']} {session['jour']} {day_date.strftime('%d/%m')}",
            "Prevu": prevu,
            "km prevu": km_prevu,
            "km fait": km_fait,
            "Duree (min)": duree_fait,
            "FC moy": fc_moy,
            "D+": elev,
        })

    day_df = pd.DataFrame(day_data)
    st.dataframe(day_df, use_container_width=True, hide_index=True)


# --- Plan detail ---

st.markdown("---")
st.subheader("📋 Seances de la semaine")

for session in week_plan:
    day_date = selected_monday + timedelta(days=session["jour_num"])
    header = f"{session['emoji']} **{session['jour']} {day_date.strftime('%d/%m')}** — {session['titre']}"

    with st.expander(header, expanded=True):
        cols = st.columns(4)
        cols[0].metric("Duree", session["duree"])
        cols[1].metric("Intensite", session["intensite"])
        if session.get("fc_cible"):
            cols[2].metric("FC cible", session["fc_cible"])
        if session.get("allure_cible"):
            cols[3].metric("Allure cible", session["allure_cible"])

        if session["km_cible"] > 0:
            st.markdown(f"*{session['description']}* — **{session['km_cible']} km**")
        else:
            st.markdown(f"*{session['description']}*")

        if session.get("rotation_active"):
            st.info(f"Cette semaine : {session['rotation_active']}")

        # Detailed phase breakdown for quality sessions
        if session.get("phases"):
            phase_data = []
            for p in session["phases"]:
                phase_data.append({
                    "Phase": p["phase"],
                    "Duree": p["duree"],
                    "Allure": p["allure"],
                    "FC": p["fc"],
                })
            st.dataframe(pd.DataFrame(phase_data), use_container_width=True, hide_index=True)
            for p in session["phases"]:
                st.markdown(f"**{p['phase']}** — {p['details']}")

        elif session.get("rotations") and not session.get("rotation_active"):
            for r in session["rotations"]:
                st.markdown(f"- {r}")

        if session.get("renfo_active_blocks"):
            st.info(f"Cette semaine : {session['renfo_active_name']}")
            for block in session["renfo_active_blocks"]:
                st.markdown(f"**{block['titre']}**")
                for ex in block["exercices"]:
                    st.markdown(f"- {ex}")

        elif session.get("details"):
            for detail in session["details"]:
                st.markdown(f"- {detail}")

        # Show realise for this day
        if realise is not None:
            activities = realise[realise["jour_semaine"] == session["jour_num"]]
            if not activities.empty:
                st.markdown("**Realise :**")
                for _, act in activities.iterrows():
                    pace = f"{act['pace_minkm']:.2f} min/km" if pd.notna(act.get("pace_minkm")) else ""
                    hr = f"FC {int(act['avg_hr'])}" if pd.notna(act.get("avg_hr")) else ""
                    elev = f"{int(act['elevation_m'])}m D+" if act.get("elevation_m", 0) > 0 else ""
                    parts = [
                        f"{act['distance_km']:.1f} km",
                        f"{int(act['duration_min'])} min",
                        pace, hr, elev,
                    ]
                    st.success(" | ".join(p for p in parts if p))


# --- Notes ---

st.markdown("---")
st.subheader("📝 Notes de la semaine")

current_notes = existing_plan["notes"] if existing_plan else ""
notes = st.text_area(
    "Notes personnelles (ressenti, fatigue, ajustements...)",
    value=current_notes,
    height=100,
    key=f"notes_{selected_monday}",
)

if notes != current_notes and existing_plan:
    update_notes(selected_monday, notes)
    st.caption("Notes sauvegardees automatiquement")


# --- Historique ---

st.markdown("---")
st.subheader("📆 Historique des semaines")

all_plans = get_all_plans()

if not all_plans:
    st.info("Aucun plan sauvegarde pour l'instant. Clique sur 'Sauvegarder cette semaine' pour commencer.")
else:
    history_data = []
    for p in all_plans:
        plan = p["plan"]
        ws = p["week_start"]
        we = ws + timedelta(days=6)

        # Get realise if Garmin data available
        km_realise = "-"
        if df is not None and not df.empty:
            week_activities = get_realise_for_week(df, ws)
            if week_activities is not None:
                km_realise = f"{week_activities['distance_km'].sum():.0f} km"

        history_data.append({
            "Semaine": f"{ws.strftime('%d/%m')} - {we.strftime('%d/%m')}",
            "Phase": "Decharge" if plan.get("is_decharge") else f"Charge S{plan.get('cycle_week', '?')}",
            "km prevu": f"{plan.get('km_total_cible', 0)} km",
            "km realise": km_realise,
            "Notes": p["notes"][:50] + "..." if len(p["notes"]) > 50 else p["notes"],
        })

    hist_df = pd.DataFrame(history_data)
    st.dataframe(hist_df, use_container_width=True, hide_index=True)


# --- Zones de reference ---

with st.expander("📊 Zones de reference", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Zones FC** (FC Max = {FC_MAX} bpm)")
        for name, pcts in [("Z1 Recup", "< 60%"), ("Z2 Endurance", "60-70%"),
                           ("Z3 Tempo", "70-80%"), ("Z4 Seuil", "80-90%"), ("Z5 VO2max", "> 90%")]:
            lo = int(FC_MAX * (int(pcts.split("-")[0].replace("<", "0").replace(">", "90").strip().rstrip("%")) / 100))
            st.markdown(f"- **{name}** : {pcts} = {lo}-{int(lo * 1.1)} bpm")
    with col2:
        st.markdown("**Zones d'allure (GAP)**")
        for zone, allure in [("Recup", "5:20-5:30/km"), ("Facile (Z2)", "~5:00/km"),
                             ("Tempo (Z3)", "~4:30/km"), ("Seuil (Z4)", "~4:15/km"),
                             ("Intervalles (Z5)", "< 4:00/km")]:
            st.markdown(f"- **{zone}** : {allure}")


# --- Principes ---

with st.expander("📌 Principes cles", expanded=False):
    for title, text in [
        ("80/20", "80% en Z1-Z2, 20% en Z3-Z5. Evite le piege Z3."),
        ("Charge 3:1", "3 semaines de charge, 1 semaine de decharge (-30%)."),
        ("Qualite espacee", "Chaque seance intense encadree par du facile."),
        ("Nutrition longue", "Mange toutes les 30-40 min sur les sorties > 1h30."),
        ("Sommeil", "8h minimum. C'est la que tu progresses."),
    ]:
        st.markdown(f"- **{title}** — {text}")
