"""
Garmin Coach - Page d'accueil
"""

import streamlit as st
import pandas as pd
from lib.auth import get_garmin_client
from lib.data import load_all_data
from lib.metrics import compute_training_load

st.set_page_config(
    page_title="Garmin Coach",
    page_icon="🏃",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Sidebar ---
with st.sidebar:
    st.title("🏃 Garmin Coach")
    st.caption("Analyse & coaching personnalise")

# --- Auth ---
garmin, auth_error = get_garmin_client()

if auth_error:
    st.title("🏃 Garmin Coach")
    st.markdown("---")
    st.error(auth_error)
    st.stop()

# --- Load data ---
if "df" not in st.session_state:
    with st.spinner("Chargement des donnees Garmin..."):
        df = load_all_data(garmin)
        if df.empty:
            st.error("Aucune course trouvee sur Garmin Connect.")
            st.stop()
        st.session_state["df"] = df
        st.session_state["load_df"] = compute_training_load(df)

df = st.session_state["df"]
load_df = st.session_state["load_df"]

# --- Refresh button ---
with st.sidebar:
    if st.button("🔄 Rafraichir les donnees"):
        for key in ["df", "load_df"]:
            if key in st.session_state:
                del st.session_state[key]
        st.cache_data.clear()
        st.rerun()

    hr_count = df["avg_hr"].notna().sum()
    st.success(f"✅ Garmin connecte ({len(df)} courses)")
    if hr_count > 0:
        st.success(f"✅ FC disponible ({hr_count}/{len(df)} sorties)")

    st.markdown("---")
    st.caption(f"Derniere activite : {df['date'].max().strftime('%d/%m/%Y')}")

# --- Main page ---
st.title("🏃 Garmin Coach")
st.markdown(f"**{len(df)} courses** du {df['date'].min().strftime('%d/%m/%Y')} au {df['date'].max().strftime('%d/%m/%Y')}")

# --- Key metrics ---
total_days = (df["date"].max() - df["date"].min()).days
weekly_km = df["distance_km"].sum() / max(total_days / 7, 1)
weekly_elev = df["elevation_m"].sum() / max(total_days / 7, 1)
last_load = load_df.iloc[-1]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Distance totale", f"{df['distance_km'].sum():,.0f} km")
col2.metric("Denivele total", f"{df['elevation_m'].sum():,.0f} m D+")
col3.metric("Temps total", f"{df['duration_min'].sum() / 60:,.0f} h")
col4.metric("Nb sorties", f"{len(df)}")

st.markdown("---")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Moyenne hebdo", f"{weekly_km:.0f} km/sem")
col2.metric("D+ hebdo", f"{weekly_elev:.0f} m/sem")

tsb = last_load["TSB"]
tsb_label = "En forme" if tsb >= 0 else "Fatigue"
col3.metric("TSB (forme)", f"{tsb:.0f}", delta=tsb_label, delta_color="normal" if tsb >= 0 else "inverse")
col4.metric("CTL (fitness)", f"{last_load['CTL']:.0f}")

# --- Recent trend ---
st.markdown("---")
st.subheader("Tendance recente")

four_w = df["date"].max() - pd.Timedelta(weeks=4)
eight_w = df["date"].max() - pd.Timedelta(weeks=8)
recent = df[df["date"] >= four_w]
previous = df[(df["date"] >= eight_w) & (df["date"] < four_w)]

if not previous.empty and not recent.empty:
    col1, col2, col3 = st.columns(3)
    km_change = (recent["distance_km"].sum() - previous["distance_km"].sum()) / max(previous["distance_km"].sum(), 1) * 100
    col1.metric("Volume 4 sem.", f"{recent['distance_km'].sum():.0f} km", f"{km_change:+.0f}%")

    pace_change = recent[recent["distance_km"] > 5]["gap_minkm"].mean() - previous[previous["distance_km"] > 5]["gap_minkm"].mean()
    pace_label = "plus rapide" if pace_change < 0 else "plus lent"
    col2.metric("Allure GAP", f"{recent[recent['distance_km'] > 5]['gap_minkm'].mean():.2f} min/km",
                f"{pace_change:+.2f} ({pace_label})", delta_color="inverse")

    col3.metric("Sorties 4 sem.", f"{len(recent)}", f"{len(recent) - len(previous):+d} vs precedent")

# --- Records ---
st.markdown("---")
st.subheader("Records")
col1, col2, col3 = st.columns(3)

longest = df.loc[df["distance_km"].idxmax()]
col1.metric("Plus longue", f"{longest['distance_km']:.1f} km")
col1.caption(f"{longest['name']}")

most_elev = df.loc[df["elevation_m"].idxmax()]
col2.metric("Plus de D+", f"{most_elev['elevation_m']:.0f} m")
col2.caption(f"{most_elev['name']}")

fast_df = df[df["distance_km"] > 10]
if not fast_df.empty:
    fastest = fast_df.loc[fast_df["pace_minkm"].idxmin()]
    col3.metric("Plus rapide (>10km)", f"{fastest['pace_minkm']:.2f} min/km")
    col3.caption(f"{fastest['name']}")
