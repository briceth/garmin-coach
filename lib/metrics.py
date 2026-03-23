"""
Training metrics: TRIMP, CTL/ATL/TSB, HR zones, GAP effort zones.
"""

import numpy as np
import pandas as pd

FC_MAX = 192

HR_ZONES = {
    "Z1 Recup":     (0,              0.60 * FC_MAX),
    "Z2 Endurance": (0.60 * FC_MAX,  0.70 * FC_MAX),
    "Z3 Tempo":     (0.70 * FC_MAX,  0.80 * FC_MAX),
    "Z4 Seuil":     (0.80 * FC_MAX,  0.90 * FC_MAX),
    "Z5 VO2max":    (0.90 * FC_MAX,  FC_MAX * 1.1),
}

GAP_ZONES = [
    ("Z1 Recup",     5.5,  99),
    ("Z2 Endurance", 4.75, 5.5),
    ("Z3 Tempo",     4.25, 4.75),
    ("Z4 Seuil",     3.92, 4.25),
    ("Z5 VO2max",    0,    3.92),
]


def compute_trimp(duration_min, avg_hr):
    """Compute TRIMP (Training Impulse) for a single activity."""
    if pd.notna(avg_hr) and avg_hr > 0:
        fc_repos = FC_MAX * 0.35
        hr_ratio = (avg_hr - fc_repos) / (FC_MAX - fc_repos)
        hr_ratio = max(0, min(hr_ratio, 1))
        return duration_min * hr_ratio * 0.64 * np.exp(1.92 * hr_ratio)
    return 0


def compute_load_no_hr(duration_min, distance_km, elev_per_km):
    """Estimate load without HR data (pace + elevation based)."""
    if duration_min <= 0:
        return 0
    speed = distance_km / (duration_min / 60)
    return duration_min * (speed / 10) ** 1.5 * (1 + elev_per_km * 0.01)


def compute_training_load(df):
    """
    Compute daily CTL (42d), ATL (7d), TSB from TRIMP.
    Returns a daily DataFrame with load metrics.
    """
    df_calc = df.copy()

    def row_load(r):
        if pd.notna(r["avg_hr"]) and r["avg_hr"] > 0:
            return compute_trimp(r["duration_min"], r["avg_hr"])
        return compute_load_no_hr(r["duration_min"], r["distance_km"], r["elev_per_km"])

    df_calc["load"] = df_calc.apply(row_load, axis=1)

    daily = df_calc.groupby("date").agg(
        total_load=("load", "sum"),
        total_min=("duration_min", "sum"),
        total_km=("distance_km", "sum"),
        total_elev=("elevation_m", "sum"),
    ).reset_index()

    date_range = pd.date_range(df["date"].min(), df["date"].max())
    daily = daily.set_index("date").reindex(date_range, fill_value=0).reset_index()
    daily.columns = ["date", "total_load", "total_min", "total_km", "total_elev"]

    alpha_ctl = 2 / (42 + 1)
    alpha_atl = 2 / (7 + 1)
    ctl_val = atl_val = 0
    ctl, atl = [], []
    for load in daily["total_load"]:
        ctl_val = ctl_val * (1 - alpha_ctl) + load * alpha_ctl
        atl_val = atl_val * (1 - alpha_atl) + load * alpha_atl
        ctl.append(round(ctl_val, 1))
        atl.append(round(atl_val, 1))

    daily["CTL"] = ctl
    daily["ATL"] = atl
    daily["TSB"] = daily["CTL"] - daily["ATL"]
    return daily


def compute_hr_zones(df):
    """Classify activities by HR zone and return distance per zone."""
    df_hr = df[df["avg_hr"].notna() & (df["avg_hr"] > 0)].copy()
    if df_hr.empty:
        return pd.DataFrame(columns=["Zone", "Distance_km"])

    def classify(hr):
        for zone, (lo, hi) in HR_ZONES.items():
            if lo <= hr < hi:
                return zone
        return "Z5 VO2max"

    df_hr["zone"] = df_hr["avg_hr"].apply(classify)
    result = df_hr.groupby("zone")["distance_km"].sum().reset_index()
    result.columns = ["Zone", "Distance_km"]
    order = list(HR_ZONES.keys())
    result["Zone"] = pd.Categorical(result["Zone"], categories=order, ordered=True)
    return result.sort_values("Zone")


def compute_gap_zones(df):
    """Classify activities by GAP (Grade Adjusted Pace) zone."""
    def classify(gap):
        for name, lo, hi in GAP_ZONES:
            if lo <= gap < hi:
                return name
        return "Z1 Recup"

    df_z = df.copy()
    df_z["zone"] = df_z["gap_minkm"].apply(classify)
    result = df_z.groupby("zone")["distance_km"].sum().reset_index()
    result.columns = ["Zone", "Distance_km"]
    order = [z[0] for z in GAP_ZONES]
    result["Zone"] = pd.Categorical(result["Zone"], categories=order, ordered=True)
    return result.sort_values("Zone")


def compute_polarization(df, weeks=12):
    """
    Compute training polarization over recent weeks.
    Returns dict with zone percentages and assessment.
    """
    cutoff = df["date"].max() - pd.Timedelta(weeks=weeks)
    recent = df[(df["date"] >= cutoff) & df["avg_hr"].notna() & (df["avg_hr"] > 0)].copy()

    if recent.empty:
        return {"easy_pct": 0, "moderate_pct": 0, "hard_pct": 0, "assessment": "Pas de donnees FC"}

    easy = recent[recent["avg_hr"] < FC_MAX * 0.70]["distance_km"].sum()
    moderate = recent[(recent["avg_hr"] >= FC_MAX * 0.70) & (recent["avg_hr"] < FC_MAX * 0.80)]["distance_km"].sum()
    hard = recent[recent["avg_hr"] >= FC_MAX * 0.80]["distance_km"].sum()
    total = easy + moderate + hard

    if total == 0:
        return {"easy_pct": 0, "moderate_pct": 0, "hard_pct": 0, "assessment": "Pas de donnees"}

    easy_pct = round(easy / total * 100, 1)
    mod_pct = round(moderate / total * 100, 1)
    hard_pct = round(hard / total * 100, 1)

    if easy_pct >= 75:
        assessment = "Bonne polarisation"
    elif easy_pct >= 60:
        assessment = "Polarisation moderee — plus de Z1-Z2 recommande"
    else:
        assessment = "Trop d'intensite moderee (zone 3 trap)"

    return {
        "easy_pct": easy_pct,
        "moderate_pct": mod_pct,
        "hard_pct": hard_pct,
        "easy_km": round(easy, 1),
        "moderate_km": round(moderate, 1),
        "hard_km": round(hard, 1),
        "assessment": assessment,
    }
