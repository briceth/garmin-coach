"""
Zones - FC reelles (Garmin) + GAP + Polarisation
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from lib.metrics import compute_hr_zones, compute_gap_zones, compute_polarization, FC_MAX

st.set_page_config(page_title="Zones", page_icon="❤️", layout="wide")

if "df" not in st.session_state:
    st.warning("Retourne a la page d'accueil pour charger les donnees.")
    st.stop()

df = st.session_state["df"]
has_hr = df["avg_hr"].notna().any()

st.title("❤️ Zones d'entrainement")

# --- Polarisation ---
st.subheader("Polarisation de l'entrainement")
col1, col2 = st.columns([1, 2])

with col1:
    weeks = st.selectbox("Periode d'analyse", [4, 8, 12, 26, 52], index=2, format_func=lambda w: f"{w} semaines")
    polar = compute_polarization(df, weeks)

    st.metric("Zone facile (Z1-Z2)", f"{polar['easy_pct']}%", delta=f"Objectif: 80%",
              delta_color="normal" if polar["easy_pct"] >= 75 else "inverse")
    st.metric("Zone moderee (Z3)", f"{polar['moderate_pct']}%", delta=f"Objectif: < 10%",
              delta_color="normal" if polar["moderate_pct"] <= 15 else "inverse")
    st.metric("Zone intense (Z4-Z5)", f"{polar['hard_pct']}%", delta=f"Objectif: 20%",
              delta_color="normal" if 15 <= polar["hard_pct"] <= 25 else "off")

    if polar["easy_pct"] < 75:
        st.error(f"⚠️ {polar['assessment']}")
    else:
        st.success(f"✅ {polar['assessment']}")

with col2:
    fig_polar = go.Figure(data=[go.Pie(
        labels=["Z1-Z2 Facile", "Z3 Moderee", "Z4-Z5 Intense"],
        values=[polar.get("easy_km", 0), polar.get("moderate_km", 0), polar.get("hard_km", 0)],
        marker_colors=["#06D6A0", "#FFD166", "#E84855"],
        hole=0.4,
        textinfo="label+percent",
        textfont_size=12,
        hovertemplate="%{label}<br>%{value:.0f} km (%{percent})<extra></extra>",
    )])
    fig_polar.update_layout(
        height=350, margin=dict(t=20, b=20),
        showlegend=False,
    )
    st.plotly_chart(fig_polar, use_container_width=True)

st.markdown("---")

# --- Zones FC + GAP cote a cote ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("Zones FC reelles (Garmin)")
    if has_hr:
        hr_zones = compute_hr_zones(df)
        if not hr_zones.empty:
            zone_colors = ["#06D6A0", "#4ECDC4", "#FFD166", "#FF6B35", "#E84855"]
            fig_hr = go.Figure(go.Bar(
                y=hr_zones["Zone"], x=hr_zones["Distance_km"],
                orientation="h",
                marker_color=zone_colors[:len(hr_zones)],
                text=[f"{v:.0f} km" for v in hr_zones["Distance_km"]],
                textposition="outside",
                hovertemplate="%{y}<br>%{x:.0f} km<extra></extra>",
            ))
            fig_hr.update_layout(height=300, margin=dict(t=10, b=10, l=100))
            st.plotly_chart(fig_hr, use_container_width=True)
    else:
        st.info("FC non disponible. Connecte Garmin pour voir les zones FC.")

with col2:
    st.subheader("Zones d'effort (GAP)")
    gap_zones = compute_gap_zones(df)
    if not gap_zones.empty:
        zone_colors = ["#06D6A0", "#4ECDC4", "#FFD166", "#FF6B35", "#E84855"]
        fig_gap = go.Figure(go.Bar(
            y=gap_zones["Zone"], x=gap_zones["Distance_km"],
            orientation="h",
            marker_color=zone_colors[:len(gap_zones)],
            text=[f"{v:.0f} km" for v in gap_zones["Distance_km"]],
            textposition="outside",
            hovertemplate="%{y}<br>%{x:.0f} km<extra></extra>",
        ))
        fig_gap.update_layout(height=300, margin=dict(t=10, b=10, l=100))
        st.plotly_chart(fig_gap, use_container_width=True)

# --- FC mensuelle ---
if has_hr:
    st.markdown("---")
    st.subheader("FC moyenne mensuelle")
    df_hr = df[df["avg_hr"].notna() & (df["avg_hr"] > 0)].copy()
    df_hr["month"] = df_hr["date"].dt.to_period("M")
    monthly_hr = df_hr.groupby("month")["avg_hr"].mean().reset_index()
    monthly_hr["month_str"] = monthly_hr["month"].astype(str)

    fig_fc = go.Figure()
    fig_fc.add_trace(go.Scatter(
        x=monthly_hr["month_str"], y=monthly_hr["avg_hr"],
        mode="lines+markers", name="FC moyenne",
        line=dict(color="#E84855", width=2), marker=dict(size=6),
        hovertemplate="%{x}<br>%{y:.0f} bpm<extra></extra>",
    ))

    for pct, label, color in [(0.60, "Z1/Z2 (60%)", "#06D6A0"), (0.80, "Z3/Z4 (80%)", "orange"), (0.90, "Z4/Z5 (90%)", "#E84855")]:
        fig_fc.add_hline(y=FC_MAX * pct, line_dash="dash", line_color=color, line_width=1,
                        annotation_text=f"{label}: {int(FC_MAX * pct)} bpm",
                        annotation_position="bottom right", annotation_font_size=10)

    fig_fc.update_layout(
        yaxis_title="bpm",
        height=350, margin=dict(t=30, b=30),
    )
    st.plotly_chart(fig_fc, use_container_width=True)
