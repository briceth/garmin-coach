"""
Data fetching and enrichment module.
Fetches Strava activities, enriches with Garmin HR data.
"""

import json
import os
import requests
import pandas as pd
import streamlit as st
from datetime import datetime


GARMIN_CACHE_FILE = "garmin_hr_cache.json"


@st.cache_data(ttl=3600, show_spinner="Recuperation des activites Strava...")
def fetch_strava_activities(token, max_pages=10):
    """Fetch all running activities from Strava API."""
    headers = {"Authorization": f"Bearer {token}"}
    activities = []
    page = 1
    while page <= max_pages:
        res = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers=headers,
            params={"per_page": 200, "page": page}
        )
        if res.status_code != 200:
            break
        data = res.json()
        if not data:
            break
        runs = [a for a in data if a.get("type") in ("Run", "TrailRun", "VirtualRun")]
        activities.extend(runs)
        if len(data) < 200:
            break
        page += 1
    return activities


@st.cache_data(ttl=86400, show_spinner="Recuperation FC Garmin...")
def fetch_garmin_hr(_garmin_client):
    """Fetch HR data from Garmin Connect. Cached for 24h."""
    # Try file cache first
    if os.path.exists(GARMIN_CACHE_FILE):
        try:
            with open(GARMIN_CACHE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    if _garmin_client is None:
        return {}

    activities = _garmin_client.get_activities_by_date(
        "2022-01-01", datetime.now().strftime("%Y-%m-%d"), "running"
    )

    hr_data = {}
    for a in activities:
        date_str = a.get("startTimeLocal", "")[:10]
        dist_km = round(a.get("distance", 0) / 1000, 1)
        avg_hr = a.get("averageHR")
        max_hr = a.get("maxHR")
        if avg_hr:
            key = f"{date_str}_{dist_km}"
            hr_data[key] = {"avg_hr": avg_hr, "max_hr": max_hr}

    # Save to file cache
    try:
        with open(GARMIN_CACHE_FILE, "w") as f:
            json.dump(hr_data, f)
    except OSError:
        pass

    return hr_data


def build_dataframe(activities, garmin_hr=None):
    """Build enriched DataFrame from Strava activities + Garmin HR."""
    if garmin_hr is None:
        garmin_hr = {}

    rows = []
    for a in activities:
        dist_km = a.get("distance", 0) / 1000
        moving_min = a.get("moving_time", 0) / 60
        elev = a.get("total_elevation_gain", 0)
        pace = moving_min / max(dist_km, 0.01)
        elev_per_km = elev / max(dist_km, 0.01)
        gap_factor = 1 + (elev_per_km / 100) * 0.06
        gap = pace / gap_factor

        date_str = pd.to_datetime(a["start_date_local"]).strftime("%Y-%m-%d")

        # HR: Strava first, then Garmin fallback
        avg_hr = a.get("average_heartrate")
        max_hr = a.get("max_heartrate")

        if not avg_hr and garmin_hr:
            dist_r = round(dist_km, 1)
            for delta in [0, 0.1, -0.1, 0.2, -0.2, 0.3, -0.3, 0.5, -0.5]:
                key = f"{date_str}_{round(dist_r + delta, 1)}"
                if key in garmin_hr:
                    avg_hr = garmin_hr[key]["avg_hr"]
                    max_hr = garmin_hr[key]["max_hr"]
                    break

        rows.append({
            "date": pd.to_datetime(date_str),
            "name": a.get("name", ""),
            "distance_km": round(dist_km, 2),
            "duration_min": round(moving_min, 1),
            "elapsed_min": round(a.get("elapsed_time", 0) / 60, 1),
            "elevation_m": elev,
            "avg_hr": avg_hr,
            "max_hr": max_hr,
            "pace_minkm": round(pace, 2),
            "gap_minkm": round(gap, 2),
            "elev_per_km": round(elev_per_km, 1),
            "type": a.get("sport_type", a.get("type", "Run")),
        })

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_all_data(strava_token, garmin_client=None):
    """Main entry point: load and enrich all data."""
    activities = fetch_strava_activities(strava_token)
    garmin_hr = fetch_garmin_hr(garmin_client) if garmin_client else {}

    # Also try file cache if no garmin client
    if not garmin_hr and os.path.exists(GARMIN_CACHE_FILE):
        try:
            with open(GARMIN_CACHE_FILE) as f:
                garmin_hr = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    df = build_dataframe(activities, garmin_hr)
    return df
