"""
Dashboard - Graphiques principaux
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")

if "df" not in st.session_state:
    st.warning("Retourne a la page d'accueil pour charger les donnees.")
    st.stop()

df = st.session_state["df"]
load_df = st.session_state["load_df"]

st.title("📊 Dashboard")

# --- Filters ---
with st.sidebar:
    st.subheader("Filtres")
    date_range = st.date_input(
        "Periode",
        value=(df["date"].min().date(), df["date"].max().date()),
        min_value=df["date"].min().date(),
        max_value=df["date"].max().date(),
    )
    if len(date_range) == 2:
        mask = (df["date"].dt.date >= date_range[0]) & (df["date"].dt.date <= date_range[1])
        df_filtered = df[mask]
        load_mask = (load_df["date"].dt.date >= date_range[0]) & (load_df["date"].dt.date <= date_range[1])
        load_filtered = load_df[load_mask]
    else:
        df_filtered = df
        load_filtered = load_df

    dist_min, dist_max = st.slider("Distance (km)", 0, int(df["distance_km"].max()) + 1, (0, int(df["distance_km"].max()) + 1))
    df_filtered = df_filtered[(df_filtered["distance_km"] >= dist_min) & (df_filtered["distance_km"] <= dist_max)]

st.caption(f"{len(df_filtered)} sorties selectionnees")

# --- 1. Volume hebdomadaire ---
st.subheader("Volume hebdomadaire")
weekly = df_filtered.set_index("date").resample("W").agg(
    km=("distance_km", "sum"), elev=("elevation_m", "sum"), runs=("distance_km", "count")
).reset_index()

fig_vol = go.Figure()
fig_vol.add_trace(go.Bar(x=weekly["date"], y=weekly["km"], name="km",
                         marker_color="#FF6B35", opacity=0.8,
                         hovertemplate="%{x|%d %b %Y}<br>%{y:.0f} km<extra></extra>"))
fig_vol.add_trace(go.Scatter(x=weekly["date"], y=weekly["elev"], name="D+ (m)",
                             yaxis="y2", line=dict(color="#9B5DE5", width=1.5),
                             hovertemplate="%{y:.0f} m D+<extra></extra>"))
fig_vol.update_layout(
    yaxis=dict(title="km"),
    yaxis2=dict(title="D+ (m)", overlaying="y", side="right", showgrid=False),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    height=350, margin=dict(t=30, b=30),
)
st.plotly_chart(fig_vol, use_container_width=True)

# --- 2. Progression allure ---
st.subheader("Progression allure")
df_pace = df_filtered[df_filtered["distance_km"] > 5].copy()
if not df_pace.empty:
    df_pace["pace_roll"] = df_pace["pace_minkm"].rolling(10, min_periods=3).mean()
    df_pace["gap_roll"] = df_pace["gap_minkm"].rolling(10, min_periods=3).mean()

    fig_pace = go.Figure()
    fig_pace.add_trace(go.Scatter(x=df_pace["date"], y=df_pace["pace_minkm"],
                                  mode="markers", name="Allure brute",
                                  marker=dict(color="#4ECDC4", size=5, opacity=0.3),
                                  hovertemplate="%{x|%d %b %Y}<br>%{y:.2f} min/km<extra></extra>"))
    fig_pace.add_trace(go.Scatter(x=df_pace["date"], y=df_pace["pace_roll"],
                                  name="Allure (moy. 10)", line=dict(color="#E84855", width=2),
                                  hovertemplate="%{y:.2f} min/km<extra></extra>"))
    fig_pace.add_trace(go.Scatter(x=df_pace["date"], y=df_pace["gap_roll"],
                                  name="GAP (eq. plat)", line=dict(color="#06D6A0", width=2, dash="dash"),
                                  hovertemplate="%{y:.2f} min/km<extra></extra>"))
    fig_pace.update_layout(
        yaxis=dict(title="min/km", autorange="reversed"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=350, margin=dict(t=30, b=30),
    )
    st.plotly_chart(fig_pace, use_container_width=True)

# --- 3. Charge d'entrainement ---
st.subheader("Charge d'entrainement (CTL / ATL / TSB)")
fig_load = go.Figure()
fig_load.add_trace(go.Scatter(x=load_filtered["date"], y=load_filtered["CTL"],
                              name="CTL (Fitness 42j)", line=dict(color="#2E86AB", width=2),
                              hovertemplate="%{x|%d %b %Y}<br>CTL: %{y:.1f}<extra></extra>"))
fig_load.add_trace(go.Scatter(x=load_filtered["date"], y=load_filtered["ATL"],
                              name="ATL (Fatigue 7j)", line=dict(color="#E84855", width=1.5),
                              hovertemplate="ATL: %{y:.1f}<extra></extra>"))
fig_load.add_trace(go.Scatter(x=load_filtered["date"], y=load_filtered["TSB"],
                              name="TSB (Forme)", fill="tozeroy",
                              line=dict(color="rgba(100,100,100,0.3)"),
                              fillcolor="rgba(6,214,160,0.15)",
                              hovertemplate="TSB: %{y:.1f}<extra></extra>"))
fig_load.add_hline(y=0, line_dash="dash", line_color="gray", line_width=0.5)
fig_load.update_layout(
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    height=350, margin=dict(t=30, b=30),
)
st.plotly_chart(fig_load, use_container_width=True)

# --- 4. Volume mensuel ---
st.subheader("Volume mensuel")
monthly = df_filtered.set_index("date").resample("ME").agg(
    km=("distance_km", "sum"), elev=("elevation_m", "sum"), runs=("distance_km", "count")
).reset_index()

fig_month = go.Figure()
fig_month.add_trace(go.Bar(x=monthly["date"], y=monthly["km"], name="km",
                           marker_color="#FF6B35", opacity=0.7,
                           text=monthly["runs"].astype(int).astype(str) + " runs",
                           textposition="outside", textfont_size=9,
                           hovertemplate="%{x|%b %Y}<br>%{y:.0f} km<br>%{text}<extra></extra>"))
fig_month.add_trace(go.Scatter(x=monthly["date"], y=monthly["elev"], name="D+ (m)",
                               yaxis="y2", line=dict(color="#9B5DE5", width=1.5),
                               marker=dict(size=4),
                               hovertemplate="%{y:.0f} m D+<extra></extra>"))
fig_month.update_layout(
    yaxis=dict(title="km"),
    yaxis2=dict(title="D+ (m)", overlaying="y", side="right", showgrid=False),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    height=350, margin=dict(t=30, b=30),
)
st.plotly_chart(fig_month, use_container_width=True)
