"""
Records - Meilleures sorties, distribution, allure vs denivele
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

st.set_page_config(page_title="Records", page_icon="🏆", layout="wide")

if "df" not in st.session_state:
    st.warning("Retourne a la page d'accueil pour charger les donnees.")
    st.stop()

df = st.session_state["df"]

st.title("🏆 Records & Stats")

# --- Top records ---
st.subheader("Records personnels")
col1, col2, col3 = st.columns(3)

longest = df.loc[df["distance_km"].idxmax()]
col1.metric("Plus longue sortie", f"{longest['distance_km']:.1f} km")
col1.caption(f"📍 {longest['name']} ({longest['date'].strftime('%d/%m/%Y')})")

most_elev = df.loc[df["elevation_m"].idxmax()]
col2.metric("Plus gros denivele", f"{most_elev['elevation_m']:.0f} m D+")
col2.caption(f"📍 {most_elev['name']} ({most_elev['date'].strftime('%d/%m/%Y')})")

fast_df = df[df["distance_km"] > 10]
if not fast_df.empty:
    fastest = fast_df.loc[fast_df["pace_minkm"].idxmin()]
    col3.metric("Plus rapide (>10km)", f"{fastest['pace_minkm']:.2f} min/km")
    col3.caption(f"📍 {fastest['name']} ({fastest['date'].strftime('%d/%m/%Y')})")

longest_time = df.loc[df["duration_min"].idxmax()]
col1.metric("Plus longue en temps", f"{longest_time['duration_min'] / 60:.1f}h")
col1.caption(f"📍 {longest_time['name']}")

if df["avg_hr"].notna().any():
    max_hr = df.loc[df["max_hr"].idxmax()]
    col2.metric("FC max observee", f"{max_hr['max_hr']:.0f} bpm")
    col2.caption(f"📍 {max_hr['name']}")

most_vert = df[df["distance_km"] > 5]
if not most_vert.empty:
    steepest = most_vert.loc[most_vert["elev_per_km"].idxmax()]
    col3.metric("Plus raide (>5km)", f"{steepest['elev_per_km']:.0f} m/km")
    col3.caption(f"📍 {steepest['name']}")

# --- Allure vs Denivele ---
st.markdown("---")
st.subheader("Allure vs Denivele")

df_trail = df[df["distance_km"] > 3].copy()
fig_scatter = px.scatter(
    df_trail, x="elev_per_km", y="pace_minkm",
    color="distance_km", size="duration_min",
    color_continuous_scale="YlOrRd",
    labels={"elev_per_km": "D+ par km (m/km)", "pace_minkm": "Allure (min/km)",
            "distance_km": "Distance (km)", "duration_min": "Duree (min)"},
    hover_data={"name": True, "date": True},
    opacity=0.6,
)

# Add regression line
mask = df_trail["elev_per_km"] < 150
if mask.sum() > 10:
    z = np.polyfit(df_trail.loc[mask, "elev_per_km"], df_trail.loc[mask, "pace_minkm"], 1)
    x_fit = np.linspace(0, df_trail.loc[mask, "elev_per_km"].max(), 50)
    fig_scatter.add_trace(go.Scatter(
        x=x_fit, y=np.polyval(z, x_fit),
        mode="lines", name=f"+{z[0]*100:.1f} min/km par 100m D+/km",
        line=dict(color="#E84855", width=2, dash="dash"),
    ))

fig_scatter.update_layout(height=400, margin=dict(t=30, b=30))
st.plotly_chart(fig_scatter, use_container_width=True)

# --- Distribution des distances ---
st.markdown("---")
st.subheader("Distribution des distances")

bins = [0, 5, 10, 15, 20, 25, 30, 40, 50, 100, 200]
labels = ["<5", "5-10", "10-15", "15-20", "20-25", "25-30", "30-40", "40-50", "50-100", "100+"]
df_dist = df.copy()
df_dist["dist_bin"] = pd.cut(df_dist["distance_km"], bins=bins, labels=labels, right=False)
dist_counts = df_dist["dist_bin"].value_counts().sort_index().reset_index()
dist_counts.columns = ["Tranche", "Nombre"]

fig_dist = px.bar(dist_counts, x="Tranche", y="Nombre",
                  color_discrete_sequence=["#1A535C"],
                  text="Nombre",
                  labels={"Tranche": "km", "Nombre": "Nombre de sorties"})
fig_dist.update_traces(textposition="outside")
fig_dist.update_layout(height=350, margin=dict(t=30, b=30))
st.plotly_chart(fig_dist, use_container_width=True)

# --- Recuperation ---
st.markdown("---")
st.subheader("Jours de repos entre les sorties")

df_sorted = df.sort_values("date").copy()
df_sorted["rest_days"] = df_sorted["date"].diff().dt.days.fillna(0)
rest_counts = df_sorted["rest_days"].value_counts().sort_index().head(10).reset_index()
rest_counts.columns = ["Jours", "Frequence"]

fig_rest = px.bar(rest_counts, x="Jours", y="Frequence",
                  color_discrete_sequence=["#9B5DE5"],
                  labels={"Jours": "Jours de repos", "Frequence": "Nombre de fois"})
mean_rest = df_sorted["rest_days"].mean()
fig_rest.add_vline(x=mean_rest, line_dash="dash", line_color="#E84855",
                   annotation_text=f"Moyenne: {mean_rest:.1f}j")
fig_rest.update_layout(height=350, margin=dict(t=30, b=30))
st.plotly_chart(fig_rest, use_container_width=True)

# --- Evolution annuelle ---
st.markdown("---")
st.subheader("Evolution annuelle")

df_year = df.copy()
df_year["year"] = df_year["date"].dt.year
yearly = df_year.groupby("year").agg(
    km=("distance_km", "sum"),
    elev=("elevation_m", "sum"),
    runs=("distance_km", "count"),
    hours=("duration_min", lambda x: round(x.sum() / 60)),
).reset_index()
yearly.columns = ["Annee", "Distance (km)", "Denivele (m)", "Sorties", "Heures"]

st.dataframe(
    yearly,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Annee": st.column_config.NumberColumn(format="%d"),
        "Distance (km)": st.column_config.NumberColumn(format="%,.0f km"),
        "Denivele (m)": st.column_config.NumberColumn(format="%,.0f m"),
        "Sorties": st.column_config.NumberColumn(format="%d"),
        "Heures": st.column_config.NumberColumn(format="%d h"),
    }
)

# --- Top 10 sorties ---
st.markdown("---")
st.subheader("Top 10 sorties les plus longues")
top10 = df.nlargest(10, "distance_km")[["date", "name", "distance_km", "duration_min", "elevation_m", "pace_minkm", "avg_hr"]].copy()
top10["date"] = top10["date"].dt.strftime("%d/%m/%Y")
top10["duration_min"] = (top10["duration_min"] / 60).round(1)
top10.columns = ["Date", "Nom", "Distance (km)", "Duree (h)", "D+ (m)", "Allure (min/km)", "FC moy (bpm)"]

st.dataframe(top10, use_container_width=True, hide_index=True)
