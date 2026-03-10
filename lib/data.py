"""
Data fetching module.
Fetches running activities from Garmin Connect.
"""

import pandas as pd
import streamlit as st
from datetime import datetime


@st.cache_data(ttl=3600, show_spinner="Recuperation des activites Garmin...")
def fetch_garmin_activities(_garmin_client, start_date="2022-01-01"):
    """Fetch all running activities from Garmin Connect."""
    if _garmin_client is None:
        return []

    activities = _garmin_client.get_activities_by_date(
        start_date, datetime.now().strftime("%Y-%m-%d"), "running"
    )
    return activities


def build_dataframe(activities):
    """Build enriched DataFrame from Garmin activities."""
    rows = []
    for a in activities:
        dist_km = a.get("distance", 0) / 1000
        moving_min = a.get("movingDuration", a.get("duration", 0)) / 60
        elapsed_min = a.get("duration", 0) / 60
        elev = a.get("elevationGain", a.get("totalElevationGain", 0)) or 0
        pace = moving_min / max(dist_km, 0.01)
        elev_per_km = elev / max(dist_km, 0.01)
        gap_factor = 1 + (elev_per_km / 100) * 0.06
        gap = pace / gap_factor

        date_str = a.get("startTimeLocal", "")[:10]
        avg_hr = a.get("averageHR")
        max_hr = a.get("maxHR")

        activity_type = a.get("activityType", {})
        type_key = activity_type.get("typeKey", "running") if isinstance(activity_type, dict) else "running"

        rows.append({
            "date": pd.to_datetime(date_str),
            "name": a.get("activityName", ""),
            "distance_km": round(dist_km, 2),
            "duration_min": round(moving_min, 1),
            "elapsed_min": round(elapsed_min, 1),
            "elevation_m": elev,
            "avg_hr": avg_hr,
            "max_hr": max_hr,
            "pace_minkm": round(pace, 2),
            "gap_minkm": round(gap, 2),
            "elev_per_km": round(elev_per_km, 1),
            "type": type_key,
        })

    if not rows:
        return pd.DataFrame(columns=[
            "date", "name", "distance_km", "duration_min", "elapsed_min",
            "elevation_m", "avg_hr", "max_hr", "pace_minkm", "gap_minkm",
            "elev_per_km", "type",
        ])

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_all_data(garmin_client):
    """Main entry point: load all data from Garmin."""
    activities = fetch_garmin_activities(garmin_client)
    return build_dataframe(activities)
