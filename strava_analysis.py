"""
Strava + Garmin Running Analysis
=================================
Donnees Strava enrichies avec FC Garmin Connect.
Analyse : Performance, Charge (CTL/ATL/TSB), Zones FC, Allure/Denivele, Recuperation

SETUP :
  pip install requests pandas matplotlib seaborn numpy garminconnect python-dotenv

USAGE :
  1. Remplir .env avec GARMIN_EMAIL et GARMIN_PASSWORD
  2. python strava_analysis.py
"""

import matplotlib
matplotlib.use("Agg")

import os
import json
import webbrowser
import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------
# CONFIGURATION
# ---------------------------------------------
CLIENT_ID     = os.getenv("STRAVA_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET", "")
TOKEN_FILE    = "strava_token.json"
GARMIN_CACHE  = "garmin_hr_cache.json"

FC_MAX = 185

FC_ZONES = {
    "Z1 Recup":     (0,              0.60 * FC_MAX),
    "Z2 Endurance": (0.60 * FC_MAX,  0.70 * FC_MAX),
    "Z3 Tempo":     (0.70 * FC_MAX,  0.80 * FC_MAX),
    "Z4 Seuil":     (0.80 * FC_MAX,  0.90 * FC_MAX),
    "Z5 VO2max":    (0.90 * FC_MAX,  FC_MAX * 1.1),
}

# ---------------------------------------------
# AUTH STRAVA
# ---------------------------------------------

class OAuthHandler(BaseHTTPRequestHandler):
    code = None
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        if "code" in params:
            OAuthHandler.code = params["code"][0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<h2>Autorisation OK ! Tu peux fermer cet onglet.</h2>")
    def log_message(self, format, *args):
        pass


def get_strava_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            token_data = json.load(f)
        if token_data["expires_at"] < datetime.now().timestamp():
            print("Rafraichissement du token Strava...")
            res = requests.post("https://www.strava.com/oauth/token", data={
                "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
                "grant_type": "refresh_token", "refresh_token": token_data["refresh_token"],
            })
            token_data = res.json()
            with open(TOKEN_FILE, "w") as f:
                json.dump(token_data, f)
        return token_data["access_token"]

    auth_url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={CLIENT_ID}&redirect_uri=http://localhost:8765"
        f"&response_type=code&scope=activity:read_all"
    )
    print("Ouverture du navigateur pour l'autorisation Strava...")
    server = HTTPServer(("localhost", 8765), OAuthHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    webbrowser.open(auth_url)
    thread.join(timeout=60)

    if not OAuthHandler.code:
        raise RuntimeError("Pas de code OAuth recu.")

    res = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "code": OAuthHandler.code, "grant_type": "authorization_code",
    })
    token_data = res.json()
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f)
    print("Authentification Strava reussie !")
    return token_data["access_token"]


# ---------------------------------------------
# GARMIN CONNECT — FC
# ---------------------------------------------

def fetch_garmin_hr():
    """Recupere les FC depuis Garmin Connect et les cache localement."""
    if os.path.exists(GARMIN_CACHE):
        with open(GARMIN_CACHE) as f:
            cached = json.load(f)
        print(f"Cache Garmin charge : {len(cached)} activites")
        return cached

    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    if not email or not password:
        print("Garmin : pas de credentials dans .env, FC non disponible")
        return {}

    from garminconnect import Garmin
    print("Connexion a Garmin Connect...")
    garmin = Garmin(email, password)
    garmin.login()
    print("Garmin Connect OK !")

    print("Recuperation des activites Garmin (peut prendre un moment)...")
    activities = garmin.get_activities_by_date("2022-01-01", datetime.now().strftime("%Y-%m-%d"), "running")
    print(f"{len(activities)} activites running Garmin recuperees")

    # Index par (date, distance_arrondie) pour matcher avec Strava
    hr_data = {}
    for a in activities:
        date_str = a.get("startTimeLocal", "")[:10]
        dist_km = round(a.get("distance", 0) / 1000, 1)
        avg_hr = a.get("averageHR")
        max_hr = a.get("maxHR")
        if avg_hr:
            key = f"{date_str}_{dist_km}"
            hr_data[key] = {"avg_hr": avg_hr, "max_hr": max_hr}

    with open(GARMIN_CACHE, "w") as f:
        json.dump(hr_data, f)
    print(f"Cache Garmin sauvegarde : {len(hr_data)} activites avec FC")
    return hr_data


# ---------------------------------------------
# STRAVA — ACTIVITES
# ---------------------------------------------

def fetch_strava_activities(token, max_pages=10):
    headers = {"Authorization": f"Bearer {token}"}
    activities = []
    page = 1
    print("Recuperation des activites Strava...")
    while page <= max_pages:
        res = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers=headers, params={"per_page": 200, "page": page}
        )
        data = res.json()
        if not data:
            break
        runs = [a for a in data if a["type"] in ("Run", "TrailRun", "VirtualRun")]
        activities.extend(runs)
        if len(data) < 200:
            break
        page += 1
    print(f"{len(activities)} courses Strava recuperees")
    return activities


def build_dataframe(activities, garmin_hr):
    """Construit le DataFrame en enrichissant avec la FC Garmin."""
    rows = []
    matched = 0
    for a in activities:
        dist_km = a.get("distance", 0) / 1000
        moving_min = a.get("moving_time", 0) / 60
        elev = a.get("total_elevation_gain", 0)
        pace = moving_min / max(dist_km, 0.01)
        elev_per_km = elev / max(dist_km, 0.01)
        gap_factor = 1 + (elev_per_km / 100) * 0.06
        gap = pace / gap_factor

        date_str = pd.to_datetime(a["start_date_local"]).strftime("%Y-%m-%d")

        # FC : d'abord Strava, sinon Garmin
        avg_hr = a.get("average_heartrate")
        max_hr = a.get("max_heartrate")

        if not avg_hr and garmin_hr:
            # Match par date + distance (tolerant a 0.5km pres)
            dist_rounded = round(dist_km, 1)
            key = f"{date_str}_{dist_rounded}"
            if key in garmin_hr:
                avg_hr = garmin_hr[key]["avg_hr"]
                max_hr = garmin_hr[key]["max_hr"]
                matched += 1
            else:
                # Chercher avec tolerance sur la distance
                for delta in [0.1, -0.1, 0.2, -0.2, 0.3, -0.3, 0.5, -0.5]:
                    alt_key = f"{date_str}_{round(dist_rounded + delta, 1)}"
                    if alt_key in garmin_hr:
                        avg_hr = garmin_hr[alt_key]["avg_hr"]
                        max_hr = garmin_hr[alt_key]["max_hr"]
                        matched += 1
                        break

        rows.append({
            "date":           pd.to_datetime(date_str),
            "name":           a.get("name", ""),
            "distance_km":    round(dist_km, 2),
            "duration_min":   round(moving_min, 1),
            "elapsed_min":    round(a.get("elapsed_time", 0) / 60, 1),
            "elevation_m":    elev,
            "avg_hr":         avg_hr,
            "max_hr":         max_hr,
            "pace_minkm":     round(pace, 2),
            "gap_minkm":      round(gap, 2),
            "elev_per_km":    round(elev_per_km, 1),
            "type":           a.get("sport_type", a.get("type", "Run")),
        })

    if garmin_hr:
        print(f"FC Garmin matchee sur {matched}/{len(activities)} activites")

    df = pd.DataFrame(rows).sort_values("date")
    df["date"] = pd.to_datetime(df["date"])
    return df


# ---------------------------------------------
# CHARGE D'ENTRAINEMENT (avec FC si dispo)
# ---------------------------------------------

def compute_training_load(df):
    """
    Si FC disponible : hrTSS = duree * (FC_moy/FC_max)^2 * 100
    Sinon : estimation via allure + denivele
    CTL = EWMA 42j, ATL = EWMA 7j, TSB = CTL - ATL
    """
    df_calc = df.copy()

    def row_load(r):
        if pd.notna(r["avg_hr"]) and r["avg_hr"] > 0:
            # TRIMP (Training Impulse) : duree * intensite FC
            # Intensite = (FC_moy - FC_repos) / (FC_max - FC_repos)
            fc_repos = FC_MAX * 0.35  # ~65 bpm
            hr_ratio = (r["avg_hr"] - fc_repos) / (FC_MAX - fc_repos)
            hr_ratio = max(0, min(hr_ratio, 1))
            return r["duration_min"] * hr_ratio * 0.64 * np.exp(1.92 * hr_ratio)
        else:
            speed = r["distance_km"] / (r["duration_min"] / 60) if r["duration_min"] > 0 else 0
            return r["duration_min"] * (speed / 10) ** 1.5 * (1 + r["elev_per_km"] * 0.01)

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


# ---------------------------------------------
# ZONES
# ---------------------------------------------

def compute_hr_zones(df):
    """Zones FC reelles basees sur la FC Garmin."""
    df_hr = df[df["avg_hr"].notna() & (df["avg_hr"] > 0)].copy()
    if df_hr.empty:
        return pd.DataFrame(columns=["Zone", "Distance_km"])
    def classify(hr):
        for zone, (lo, hi) in FC_ZONES.items():
            if lo <= hr < hi:
                return zone
        return "Z5 VO2max"
    df_hr["zone"] = df_hr["avg_hr"].apply(classify)
    zone_dist = df_hr.groupby("zone")["distance_km"].sum().reset_index()
    zone_dist.columns = ["Zone", "Distance_km"]
    order = list(FC_ZONES.keys())
    zone_dist["Zone"] = pd.Categorical(zone_dist["Zone"], categories=order, ordered=True)
    return zone_dist.sort_values("Zone")


def compute_effort_zones(df):
    """Zones basees sur l'allure GAP."""
    zones_def = [
        ("Z1 Recup",     6.5,  99),
        ("Z2 Endurance", 5.5,  6.5),
        ("Z3 Tempo",     4.75, 5.5),
        ("Z4 Seuil",     4.0,  4.75),
        ("Z5 VO2max",    0,    4.0),
    ]
    def classify(gap):
        for name, lo, hi in zones_def:
            if lo <= gap < hi:
                return name
        return "Z1 Recup"
    df_z = df.copy()
    df_z["zone"] = df_z["gap_minkm"].apply(classify)
    zone_dist = df_z.groupby("zone")["distance_km"].sum().reset_index()
    zone_dist.columns = ["Zone", "Distance_km"]
    order = [z[0] for z in zones_def]
    zone_dist["Zone"] = pd.Categorical(zone_dist["Zone"], categories=order, ordered=True)
    return zone_dist.sort_values("Zone")


# ---------------------------------------------
# VISUALISATION
# ---------------------------------------------

def plot_all(df, load_df, hr_zone_df, gap_zone_df, has_hr):
    sns.set_theme(style="darkgrid")
    rows = 5 if has_hr else 4
    fig = plt.figure(figsize=(20, rows * 5.5))
    fig.suptitle("Analyse Strava + Garmin - Running & Trail", fontsize=18, fontweight="bold", y=0.995)

    C_ORANGE = "#FF6B35"
    C_TEAL   = "#1A535C"
    C_CYAN   = "#4ECDC4"
    C_BLUE   = "#2E86AB"
    C_RED    = "#E84855"
    C_PURPLE = "#9B5DE5"
    C_GREEN  = "#06D6A0"

    plot_idx = 1

    # ── 1. Volume hebdomadaire ──
    ax = fig.add_subplot(rows, 2, plot_idx); plot_idx += 1
    weekly = df.set_index("date").resample("W").agg(
        km=("distance_km", "sum"), elev=("elevation_m", "sum")
    ).reset_index()
    ax.bar(weekly["date"], weekly["km"], color=C_ORANGE, width=5, alpha=0.8)
    ax.set_title("Volume hebdomadaire (km)", fontsize=11)
    ax.set_ylabel("km")
    ax_r = ax.twinx()
    ax_r.plot(weekly["date"], weekly["elev"], color=C_PURPLE, linewidth=1.2, alpha=0.7)
    ax_r.set_ylabel("D+ (m)", color=C_PURPLE)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30)

    # ── 2. Progression allure ──
    ax = fig.add_subplot(rows, 2, plot_idx); plot_idx += 1
    df_pace = df[df["distance_km"] > 5].copy()
    df_pace["pace_roll"] = df_pace["pace_minkm"].rolling(10, min_periods=3).mean()
    df_pace["gap_roll"] = df_pace["gap_minkm"].rolling(10, min_periods=3).mean()
    ax.scatter(df_pace["date"], df_pace["pace_minkm"], alpha=0.15, color=C_CYAN, s=15)
    ax.plot(df_pace["date"], df_pace["pace_roll"], color=C_RED, linewidth=2, label="Allure (moy. 10)")
    ax.plot(df_pace["date"], df_pace["gap_roll"], color=C_GREEN, linewidth=2, linestyle="--", label="GAP (eq. plat)")
    ax.set_title("Progression allure - sorties > 5km", fontsize=11)
    ax.set_ylabel("min/km")
    ax.invert_yaxis()
    ax.legend(fontsize=7)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30)

    # ── 3. CTL / ATL / TSB ──
    ax = fig.add_subplot(rows, 2, plot_idx); plot_idx += 1
    ax.plot(load_df["date"], load_df["CTL"], label="CTL (Fitness 42j)", color=C_BLUE, linewidth=2)
    ax.plot(load_df["date"], load_df["ATL"], label="ATL (Fatigue 7j)", color=C_RED, linewidth=1.5)
    ax.fill_between(load_df["date"], load_df["TSB"], 0,
                    where=load_df["TSB"] >= 0, alpha=0.15, color="green", label="TSB+ (Forme)")
    ax.fill_between(load_df["date"], load_df["TSB"], 0,
                    where=load_df["TSB"] < 0, alpha=0.15, color="red", label="TSB- (Fatigue)")
    ax.axhline(0, color="gray", linewidth=0.5)
    ax.set_title("Charge d'entrainement (CTL / ATL / TSB)", fontsize=11)
    ax.legend(fontsize=7)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30)

    # ── 4. Zones GAP ──
    ax = fig.add_subplot(rows, 2, plot_idx); plot_idx += 1
    zone_colors_gap = [C_GREEN, C_CYAN, "#FFD166", C_ORANGE, C_RED]
    if not gap_zone_df.empty:
        bars = ax.barh(gap_zone_df["Zone"], gap_zone_df["Distance_km"], color=zone_colors_gap[:len(gap_zone_df)])
        ax.bar_label(bars, fmt="%.0f km", padding=3, fontsize=9)
    ax.set_title("Zones d'effort (allure GAP)", fontsize=11)
    ax.set_xlabel("km")

    # ── 5 & 6. Zones FC + FC mensuelle (si FC dispo) ──
    if has_hr:
        ax = fig.add_subplot(rows, 2, plot_idx); plot_idx += 1
        zone_colors_hr = [C_GREEN, C_CYAN, "#FFD166", C_ORANGE, C_RED]
        if not hr_zone_df.empty:
            bars = ax.barh(hr_zone_df["Zone"], hr_zone_df["Distance_km"], color=zone_colors_hr[:len(hr_zone_df)])
            ax.bar_label(bars, fmt="%.0f km", padding=3, fontsize=9)
        ax.set_title("Zones FC reelles (Garmin)", fontsize=11)
        ax.set_xlabel("km")

        ax = fig.add_subplot(rows, 2, plot_idx); plot_idx += 1
        df_hr = df[df["avg_hr"].notna() & (df["avg_hr"] > 0)].copy()
        df_hr["month"] = df_hr["date"].dt.to_period("M")
        monthly_hr = df_hr.groupby("month")["avg_hr"].mean()
        ax.plot([str(m) for m in monthly_hr.index], monthly_hr.values, marker="o", color=C_RED, linewidth=2)
        ax.set_title("FC moyenne mensuelle", fontsize=11)
        ax.set_ylabel("bpm")
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=7)
        for pct, label, color in [(0.60, "Z1/Z2", C_GREEN), (0.80, "Z3/Z4", "orange"), (0.90, "Z4/Z5", C_RED)]:
            ax.axhline(FC_MAX * pct, color=color, linestyle="--", linewidth=1, alpha=0.5,
                      label=f"{int(pct*100)}% FCmax ({int(FC_MAX*pct)})")
        ax.legend(fontsize=6)

    # ── 7. Allure vs Denivele ──
    ax = fig.add_subplot(rows, 2, plot_idx); plot_idx += 1
    df_trail = df[df["distance_km"] > 3].copy()
    scatter = ax.scatter(df_trail["elev_per_km"], df_trail["pace_minkm"],
                        c=df_trail["distance_km"], cmap="YlOrRd", s=20, alpha=0.6)
    plt.colorbar(scatter, ax=ax, label="Distance (km)", shrink=0.8)
    mask = df_trail["elev_per_km"] < 150
    if mask.sum() > 10:
        z = np.polyfit(df_trail.loc[mask, "elev_per_km"], df_trail.loc[mask, "pace_minkm"], 1)
        x_fit = np.linspace(0, df_trail.loc[mask, "elev_per_km"].max(), 50)
        ax.plot(x_fit, np.polyval(z, x_fit), color=C_RED, linewidth=2, linestyle="--",
               label=f"+{z[0]*100:.1f} min/km par 100m D+/km")
        ax.legend(fontsize=7)
    ax.set_title("Allure vs Denivele", fontsize=11)
    ax.set_xlabel("D+ par km (m/km)")
    ax.set_ylabel("Allure (min/km)")

    # ── 8. Distribution distances ──
    ax = fig.add_subplot(rows, 2, plot_idx); plot_idx += 1
    bins = [0, 5, 10, 15, 20, 25, 30, 40, 50, 100, 200]
    labels = ["<5", "5-10", "10-15", "15-20", "20-25", "25-30", "30-40", "40-50", "50-100", "100+"]
    df_dist = df.copy()
    df_dist["dist_bin"] = pd.cut(df_dist["distance_km"], bins=bins, labels=labels, right=False)
    dist_counts = df_dist["dist_bin"].value_counts().sort_index()
    ax.bar(range(len(dist_counts)), dist_counts.values, color=C_TEAL, alpha=0.8)
    ax.set_xticks(range(len(dist_counts)))
    ax.set_xticklabels(dist_counts.index, rotation=30, fontsize=8)
    ax.set_title("Distribution des distances", fontsize=11)
    ax.set_ylabel("Nb sorties")
    for i, v in enumerate(dist_counts.values):
        if v > 0:
            ax.text(i, v + 1, str(v), ha="center", fontsize=8)

    # ── 9. Recuperation ──
    if plot_idx <= rows * 2:
        ax = fig.add_subplot(rows, 2, plot_idx); plot_idx += 1
        df_sorted = df.sort_values("date").copy()
        df_sorted["rest_days"] = df_sorted["date"].diff().dt.days.fillna(0)
        rest_counts = df_sorted["rest_days"].value_counts().sort_index().head(10)
        ax.bar(rest_counts.index.astype(int), rest_counts.values, color=C_PURPLE, alpha=0.8)
        ax.set_title("Jours de repos entre les sorties", fontsize=11)
        ax.set_xlabel("Jours")
        ax.set_ylabel("Frequence")
        ax.set_xticks(rest_counts.index.astype(int))
        mean_rest = df_sorted["rest_days"].mean()
        ax.axvline(mean_rest, color=C_RED, linestyle="--", linewidth=1.5, label=f"Moyenne: {mean_rest:.1f}j")
        ax.legend(fontsize=8)

    # ── 10. Volume mensuel ──
    if plot_idx <= rows * 2:
        ax = fig.add_subplot(rows, 2, plot_idx); plot_idx += 1
        monthly = df.set_index("date").resample("ME").agg(
            km=("distance_km", "sum"), elev=("elevation_m", "sum"), runs=("distance_km", "count")
        ).reset_index()
        x = range(len(monthly))
        ax.bar(x, monthly["km"], color=C_ORANGE, alpha=0.7)
        ax_r = ax.twinx()
        ax_r.plot(x, monthly["elev"], color=C_PURPLE, marker="o", markersize=3, linewidth=1.5)
        ax.set_xticks(list(x[::3]))
        ax.set_xticklabels([d.strftime("%b %y") for d in monthly["date"]][::3], rotation=30, fontsize=8)
        ax.set_title("Volume mensuel", fontsize=11)
        ax.set_ylabel("km", color=C_ORANGE)
        ax_r.set_ylabel("D+ (m)", color=C_PURPLE)

    plt.tight_layout()
    plt.savefig("strava_analysis.png", dpi=150, bbox_inches="tight")
    print("Graphique sauvegarde : strava_analysis.png")


# ---------------------------------------------
# STATS RESUMEES
# ---------------------------------------------

def print_summary(df, load_df):
    total_days = (df["date"].max() - df["date"].min()).days
    weekly_avg_km = df["distance_km"].sum() / max(total_days / 7, 1)
    weekly_avg_elev = df["elevation_m"].sum() / max(total_days / 7, 1)

    print("\n" + "=" * 60)
    print("  RESUME DE TES COURSES (Strava + Garmin)")
    print("=" * 60)
    print(f"  Periode           : {df['date'].min().date()} -> {df['date'].max().date()} ({total_days} jours)")
    print(f"  Nombre de sorties : {len(df)}")
    print(f"  Distance totale   : {df['distance_km'].sum():,.0f} km")
    print(f"  Denivele total    : {df['elevation_m'].sum():,.0f} m D+")
    print(f"  Temps total       : {df['duration_min'].sum() / 60:,.1f} h")
    print(f"  Distance moy/sortie : {df['distance_km'].mean():.1f} km")
    print(f"  Denivele moy/sortie : {df['elevation_m'].mean():.0f} m D+")
    print(f"  Moyenne hebdo     : {weekly_avg_km:.1f} km / {weekly_avg_elev:.0f} m D+")
    print(f"  Allure moyenne    : {df['pace_minkm'].mean():.2f} min/km")
    print(f"  GAP moyen         : {df['gap_minkm'].mean():.2f} min/km")

    n_hr = df["avg_hr"].notna().sum()
    if n_hr > 0:
        print(f"\n  -- Frequence cardiaque ({n_hr}/{len(df)} sorties) --")
        print(f"  FC moyenne       : {df['avg_hr'].dropna().mean():.0f} bpm")
        print(f"  FC max observee  : {df['max_hr'].dropna().max():.0f} bpm")

    print(f"\n  -- Records --")
    longest = df.loc[df["distance_km"].idxmax()]
    print(f"  Plus longue sortie : {longest['distance_km']:.1f} km ({longest['name']}, {longest['date'].date()})")
    most_elev = df.loc[df["elevation_m"].idxmax()]
    print(f"  Plus gros denivele : {most_elev['elevation_m']:.0f} m D+ ({most_elev['name']}, {most_elev['date'].date()})")
    fast_df = df[df["distance_km"] > 10]
    if not fast_df.empty:
        fastest = fast_df.loc[fast_df["pace_minkm"].idxmin()]
        print(f"  Meilleure allure (>10km) : {fastest['pace_minkm']:.2f} min/km ({fastest['name']}, {fastest['date'].date()})")

    last = load_df.iloc[-1]
    print(f"\n  -- Charge actuelle --")
    print(f"  CTL (fitness)  : {last['CTL']:.1f}")
    print(f"  ATL (fatigue)  : {last['ATL']:.1f}")
    print(f"  TSB (forme)    : {last['TSB']:.1f}  {'[En forme]' if last['TSB'] >= 0 else '[Fatigue]'}")

    four_weeks_ago = df["date"].max() - pd.Timedelta(weeks=4)
    eight_weeks_ago = df["date"].max() - pd.Timedelta(weeks=8)
    recent = df[df["date"] >= four_weeks_ago]
    previous = df[(df["date"] >= eight_weeks_ago) & (df["date"] < four_weeks_ago)]
    if len(previous) > 0 and len(recent) > 0:
        km_change = (recent["distance_km"].sum() - previous["distance_km"].sum()) / max(previous["distance_km"].sum(), 1) * 100
        pace_change = recent["gap_minkm"].mean() - previous["gap_minkm"].mean()
        print(f"\n  -- Tendance (4 sem. vs 4 sem. precedentes) --")
        print(f"  Volume  : {'+' if km_change >= 0 else ''}{km_change:.0f}%")
        print(f"  Allure GAP : {'+' if pace_change >= 0 else ''}{pace_change:.2f} min/km {'(ralenti)' if pace_change > 0 else '(plus rapide)'}")

    print("=" * 60 + "\n")


# ---------------------------------------------
# MAIN
# ---------------------------------------------

if __name__ == "__main__":
    # 1. Garmin FC
    garmin_hr = fetch_garmin_hr()

    # 2. Strava activities
    token = get_strava_token()
    activities = fetch_strava_activities(token)

    if not activities:
        print("Aucune course trouvee.")
        exit(0)

    # 3. Build enriched dataframe
    df = build_dataframe(activities, garmin_hr)
    has_hr = df["avg_hr"].notna().any()
    hr_pct = df["avg_hr"].notna().sum() / len(df) * 100
    print(f"FC disponible sur {df['avg_hr'].notna().sum()}/{len(df)} sorties ({hr_pct:.0f}%)")

    # 4. Compute metrics
    load_df = compute_training_load(df)
    hr_zone_df = compute_hr_zones(df) if has_hr else pd.DataFrame()
    gap_zone_df = compute_effort_zones(df)

    # 5. Output
    print_summary(df, load_df)
    plot_all(df, load_df, hr_zone_df, gap_zone_df, has_hr)
