"""
Coaching module: training diagnosis and plan generation.
Analyzes recent training patterns and generates personalized recommendations.
Supports race-specific plans (10K, semi, marathon, trails).
"""

import os
import pandas as pd
import numpy as np
from lib.metrics import FC_MAX, compute_polarization


# ---------------------------------------------
# RACE PROFILES
# ---------------------------------------------

RACE_PROFILES = {
    "general": {
        "label": "Entrainement general",
        "distance_km": None,
        "plan_weeks": 8,
        "taper_weeks": 0,
        "max_long_run_pct": 0.45,
        "long_run_cap_km": None,
        "min_weekly_km": 0,
        "elevation_focus": False,
        "back_to_back": False,
        "session_types": ["easy_hills", "tempo", "long", "recovery"],
    },
    "10km": {
        "label": "10 km",
        "distance_km": 10,
        "plan_weeks": 8,
        "taper_weeks": 1,
        "max_long_run_pct": 0.40,
        "long_run_cap_km": 18,
        "min_weekly_km": 15,
        "elevation_focus": False,
        "back_to_back": False,
        "session_types": ["intervals", "tempo", "long", "easy"],
    },
    "semi": {
        "label": "Semi-marathon (21.1 km)",
        "distance_km": 21.1,
        "plan_weeks": 10,
        "taper_weeks": 1,
        "max_long_run_pct": 0.45,
        "long_run_cap_km": 24,
        "min_weekly_km": 20,
        "elevation_focus": False,
        "back_to_back": False,
        "session_types": ["tempo", "intervals", "long", "easy"],
    },
    "marathon": {
        "label": "Marathon (42.2 km)",
        "distance_km": 42.2,
        "plan_weeks": 16,
        "taper_weeks": 2,
        "max_long_run_pct": 0.50,
        "long_run_cap_km": 35,
        "min_weekly_km": 30,
        "elevation_focus": False,
        "back_to_back": False,
        "session_types": ["long", "tempo", "marathon_pace", "easy"],
    },
    "trail_court": {
        "label": "Trail court (20-30 km)",
        "distance_km": 25,
        "plan_weeks": 10,
        "taper_weeks": 1,
        "max_long_run_pct": 0.45,
        "long_run_cap_km": 28,
        "min_weekly_km": 25,
        "elevation_focus": True,
        "back_to_back": False,
        "session_types": ["hills", "tempo", "long_trail", "easy"],
    },
    "trail_moyen": {
        "label": "Trail moyen (40-60 km)",
        "distance_km": 50,
        "plan_weeks": 14,
        "taper_weeks": 2,
        "max_long_run_pct": 0.45,
        "long_run_cap_km": 35,
        "min_weekly_km": 35,
        "elevation_focus": True,
        "back_to_back": True,
        "session_types": ["hills", "long_trail", "back_to_back", "easy"],
    },
    "trail_long": {
        "label": "Trail long / Ultra (80+ km)",
        "distance_km": 90,
        "plan_weeks": 20,
        "taper_weeks": 2,
        "max_long_run_pct": 0.40,
        "long_run_cap_km": 45,
        "min_weekly_km": 40,
        "elevation_focus": True,
        "back_to_back": True,
        "session_types": ["long_trail", "back_to_back", "hills", "hiking_power"],
    },
}


# ---------------------------------------------
# SESSION TEMPLATES
# ---------------------------------------------

SESSION_TEMPLATES = {
    "intervals": {
        "type": "Intervalles",
        "pct": 0.15,
        "day": "Mardi",
        "fc_target": f"{int(FC_MAX * 0.90)}-{int(FC_MAX * 0.95)} bpm (Z5)",
        "details": {
            "10km": (
                "Echauffement 15min progressif (Z1→Z2). "
                "8-10x400m a allure 10km ({pace_intervalles}/km), recup 200m trot lent entre chaque. "
                "Retour calme 10min. Variante : 5x1000m (recup 400m) pour travailler le maintien d'allure."
            ),
            "semi": (
                "Echauffement 15min progressif (Z1→Z2). "
                "5-6x1000m a allure semi ({pace_course}/km), recup 400m trot lent. "
                "Retour calme 10min. Focus : reguler son effort sur des fractions longues."
            ),
            "marathon": (
                "Echauffement 15min progressif. "
                "6-8x1000m a allure semi/10km ({pace_intervalles}/km), recup 400m trot. "
                "Retour calme 10min. Objectif : developper la VMA pour avoir de la reserve le jour J."
            ),
            "default": (
                "Echauffement 15min progressif (Z1→Z2). "
                "6-8x800m rapide (recup 400m trot). Retour calme 10min."
            ),
        },
    },
    "tempo": {
        "type": "Tempo / Seuil",
        "pct": 0.20,
        "day": "Mercredi",
        "fc_target": f"{int(FC_MAX * 0.80)}-{int(FC_MAX * 0.90)} bpm (Z4)",
        "details": {
            "10km": (
                "Echauffement 15min Z1-Z2. "
                "2x10min a allure tempo ({pace_tempo}/km), recup 3min trot. "
                "Retour calme 10min. L'allure doit etre soutenue mais controlable."
            ),
            "semi": (
                "Echauffement 15min Z1-Z2. "
                "25-30min continu a allure tempo ({pace_tempo}/km). "
                "Retour calme 10min. Les 5 derneres min : accelere legerement vers allure semi."
            ),
            "marathon": (
                "Echauffement 15min Z1-Z2. "
                "20-25min a allure seuil ({pace_tempo}/km). "
                "Retour calme 10min. Seance complementaire, ne pas depasser 25min d'effort."
            ),
            "trail_court": (
                "Echauffement 15min. "
                "3x8min a allure tempo ({pace_tempo}/km) sur terrain vallonne, recup 3min. "
                "Retour calme. Adapte l'effort a la pente : plus lent en montee, plus rapide en descente."
            ),
            "trail_moyen": (
                "Echauffement 15min. "
                "20-25min a allure tempo sur sentier vallonne. "
                "Gere l'effort par sensation (Z4), pas par l'allure. Retour calme 10min."
            ),
            "default": (
                "Echauffement 15min Z1-Z2. "
                "20-30min a allure seuil ({pace_tempo}/km). Retour calme 10min."
            ),
        },
    },
    "marathon_pace": {
        "type": "Allure marathon",
        "pct": 0.25,
        "day": "Mercredi",
        "fc_target": f"{int(FC_MAX * 0.75)}-{int(FC_MAX * 0.82)} bpm (Z3)",
        "details": {
            "marathon": (
                "Echauffement 15min Z1-Z2. "
                "40-60min a allure marathon cible ({pace_course}/km). "
                "Retour calme 10min. Seance cle : apprends a courir a cette allure les yeux fermes. "
                "Teste ta nutrition (gel toutes les 30-40min, boisson isotonique)."
            ),
            "default": (
                "Echauffement 15min. "
                "40-60min a allure marathon cible ({pace_course}/km). Retour calme 10min. "
                "Teste ta strategie nutritionnelle pendant cette seance."
            ),
        },
    },
    "long": {
        "type": "Sortie longue",
        "pct": 0.45,
        "day": "Samedi",
        "fc_target": f"< {int(FC_MAX * 0.70)} bpm (Z2)",
        "details": {
            "10km": (
                "Course tres facile ({pace_facile}/km ou plus lent). "
                "Respiration nasale, conversation possible. Duree 1h10-1h30. "
                "Pas besoin de depasser 16-18km. Si possible sur sentier/nature."
            ),
            "semi": (
                "Course tres facile ({pace_facile}/km ou plus lent). "
                "Monte progressivement vers 22-24km max. Duree 1h30-2h. "
                "Les 20 dernieres min : accelere legerement vers allure semi pour simuler la fin de course."
            ),
            "marathon": (
                "Depart tres lent ({pace_recup}/km), puis installe-toi a allure facile ({pace_facile}/km). "
                "Monte de 2km par semaine, max 32-35km. Duree 2h30-3h30. "
                "A partir de 25km : teste ta nutrition de course (gels, eau, solides). "
                "Variante fin de plan : les 10 derniers km a allure marathon ({pace_course}/km)."
            ),
            "default": (
                "Course tres facile ({pace_facile}/km). "
                "Respiration nasale, conversation possible. Objectif : temps sur pieds."
            ),
        },
    },
    "long_trail": {
        "type": "Sortie longue trail",
        "pct": 0.45,
        "day": "Samedi",
        "fc_target": f"< {int(FC_MAX * 0.75)} bpm (Z2-Z3)",
        "details": {
            "trail_court": (
                "Sortie en sentier/montagne, 2h-3h. "
                "Marche active en montee (>15% de pente), course facile en plat et descente. "
                "Travaille la technique de descente (pas courts, regard loin). "
                "Emporte 500ml d'eau et une barre energetique."
            ),
            "trail_moyen": (
                "Sortie longue en montagne, 3h-5h. Gros D+ (800-1500m). "
                "Marche avec batons en montee raide, course Z2 sur les portions roulantes. "
                "Teste ton equipement de course (sac, batons, nutrition). "
                "Mange toutes les 30-40min (barre, gel, fruits secs). Bois 500ml/h."
            ),
            "trail_long": (
                "Sortie ultra-longue en montagne, 4h-7h. Gros D+ (1500m+). "
                "Simule les conditions de course : meme sac, meme nutrition, memes batons. "
                "Alterne marche/course selon le terrain. Gere ton effort comme en course : "
                "depart conservateur, alimentation reguliere (300-400 kcal/h), hydratation constante. "
                "Profites-en pour tester la gestion des points bas (fatigue mentale)."
            ),
            "default": (
                "En montagne/sentiers. Marche active en montee, course facile en plat/descente. "
                "Batons recommandes pour les sorties > 3h."
            ),
        },
    },
    "back_to_back": {
        "type": "Enchainement J2",
        "pct": 0.25,
        "day": "Dimanche",
        "fc_target": f"< {int(FC_MAX * 0.70)} bpm (Z2)",
        "details": {
            "trail_moyen": (
                "Lendemain de la longue trail. Sortie 1h30-2h30 sur jambes fatiguees. "
                "Allure libre, ecoute du corps. Inclus du denivele si possible. "
                "Objectif : apprendre a gerer la fatigue cumulee comme en course. "
                "Si les jambes ne repondent plus, marche — c'est aussi de l'entrainement."
            ),
            "trail_long": (
                "Lendemain de la longue ultra. Sortie 2h-3h en terrain vallonne. "
                "Demarre tres lent, laisse le corps se remettre en route. "
                "Simule les heures 15-25 d'un ultra : fatigue, alimentation, mental. "
                "Mange pendant cette sortie comme en course. Batons recommandes."
            ),
            "default": (
                "Lendemain de la longue. Sortie 1h-2h sur jambes fatiguees. "
                "Allure libre, ecoute du corps. Simule la fatigue cumulee de course."
            ),
        },
    },
    "hills": {
        "type": "Cotes / D+",
        "pct": 0.15,
        "day": "Mardi",
        "fc_target": f"{int(FC_MAX * 0.80)}-{int(FC_MAX * 0.90)} bpm en montee",
        "details": {
            "trail_court": (
                "Echauffement 15min facile. "
                "6-8x3min en cote raide (8-12%), recuperation descente trot. "
                "Focus technique : pas courts, buste droit, regard devant. "
                "Retour calme 10min. Variante : 4x5min en cote moyenne (5-8%)."
            ),
            "trail_moyen": (
                "Echauffement 15min. "
                "8-10x3min en cote raide (10-15%), recup descente lente. "
                "Alterne : une serie en courant, une serie en marche rapide avec batons. "
                "Travaille les deux modes de locomotion. 400-600m D+ total vise."
            ),
            "trail_long": (
                "Echauffement 15min. "
                "Seance en cote longue : 4-6x6min en montee soutenue (Z4), recup descente. "
                "Ou : 1 grosse montee de 30-45min en continu (marche + course). "
                "Objectif : 600-1000m D+ total. Batons en option pour travailler les 2 modes."
            ),
            "default": (
                "Echauffement 15min. "
                "6-10x3min en cote raide (8-12%), recup descente trot. Travail puissance en montee."
            ),
        },
    },
    "easy_hills": {
        "type": "Facile + cotes",
        "pct": 0.20,
        "day": "Mardi",
        "fc_target": f"< {int(FC_MAX * 0.70)} bpm (Z2)",
        "details": {
            "default": (
                "Course facile ({pace_facile}/km) avec 4-6 accelerations en cote de 30s. "
                "Recuperation complete entre chaque (1-2min trot). "
                "L'objectif est le rappel de puissance, pas l'epuisement."
            ),
        },
    },
    "easy": {
        "type": "Facile / Recup",
        "pct": 0.15,
        "day": "Jeudi",
        "fc_target": f"< {int(FC_MAX * 0.65)} bpm (Z1-Z2)",
        "details": {
            "10km": (
                "Footing tres facile ({pace_facile}/km ou plus lent), 30-45min. "
                "Conversation possible en continu. Si tu ne peux pas parler, ralentis. "
                "Seance de recuperation active entre les seances intenses."
            ),
            "semi": (
                "Footing facile ({pace_facile}/km), 40-50min. "
                "Terrain plat de preference. Conversation aisee. "
                "Bon moment pour travailler la technique : cadence 170-180 pas/min, posture haute."
            ),
            "marathon": (
                "Footing facile ({pace_facile}/km), 40-50min. "
                "Recuperation active. Si les jambes sont lourdes apres la longue, "
                "n'hesite pas a reduire a 30min. Le repos est aussi de l'entrainement."
            ),
            "trail_court": (
                "Footing facile sur terrain plat, 30-40min. "
                "Recuperation apres les seances de D+. Etirements legers apres."
            ),
            "default": (
                "Footing tres facile ({pace_facile}/km), 30-45min. "
                "Conversation possible. Recuperation active."
            ),
        },
    },
    "recovery": {
        "type": "Recup active",
        "pct": 0.20,
        "day": "Dimanche",
        "fc_target": f"< {int(FC_MAX * 0.60)} bpm (Z1)",
        "details": {
            "default": (
                "Footing tres lent ({pace_recup}/km), 30-40min. "
                "Conversation facile en continu. Aide la recuperation du long de la veille. "
                "Alternative : 30min de velo ou natation si les jambes sont trop lourdes."
            ),
        },
    },
    "hiking_power": {
        "type": "Marche active / Puissance",
        "pct": 0.15,
        "day": "Jeudi",
        "fc_target": f"{int(FC_MAX * 0.70)}-{int(FC_MAX * 0.80)} bpm (Z2-Z3)",
        "details": {
            "trail_moyen": (
                "Rando rapide avec batons, 1h30-2h30. Terrain montagneux, gros D+ sur courte distance. "
                "Travaille la marche active en montee : pas courts, frequence elevee, appui batons. "
                "Objectif : 500-800m D+. Descente libre (trot ou marche)."
            ),
            "trail_long": (
                "Rando puissance avec batons, 2h-3h. Enchaine les montees. "
                "Travaille le rythme de marche que tu tiendras en course (ultra). "
                "Objectif : 800-1200m D+. Emporte de quoi manger/boire comme en course. "
                "Descente en trottinant pour travailler le technique."
            ),
            "default": (
                "Rando rapide avec batons en terrain montagneux, 1h30-2h30. "
                "Travail de la marche active en montee. Gros D+ sur courte distance."
            ),
        },
    },
}


# Days assignment for 3 and 4 sessions
DAYS_3 = ["Mardi", "Jeudi", "Samedi"]
DAYS_4 = ["Mardi", "Mercredi", "Samedi", "Dimanche"]


# ---------------------------------------------
# UTMB INDEX
# ---------------------------------------------

def get_default_utmb_index():
    """Get UTMB index from config."""
    try:
        import streamlit as st
        return st.secrets.get("athlete", {}).get("utmb_index", 630)
    except Exception:
        from dotenv import load_dotenv
        load_dotenv()
        return int(os.getenv("UTMB_INDEX", "630"))


def estimate_trail_time(distance_km, elevation_m, utmb_index):
    """Estimate trail race time from UTMB index.
    Returns estimated time in hours.
    km effort = distance + elevation_m / 100 (coefficient Kilian).
    """
    km_effort = distance_km + elevation_m / 100

    # Speed in km_effort/h by index bracket (calibrated on ITRA data)
    speed_table = {400: 4.5, 500: 6.0, 600: 7.5, 700: 9.0, 800: 10.5}
    bracket_low = max(400, min(800, (utmb_index // 100) * 100))
    bracket_high = min(900, bracket_low + 100)
    speed_low = speed_table.get(bracket_low, 6.0)
    speed_high = speed_table.get(bracket_high, speed_low + 1.5)

    pct = (utmb_index - bracket_low) / 100
    base_speed = speed_low + pct * (speed_high - speed_low)

    # Fatigue factor for ultra distances
    if km_effort > 150:
        fatigue = 0.80
    elif km_effort > 80:
        fatigue = 0.85
    elif km_effort > 50:
        fatigue = 0.92
    else:
        fatigue = 0.96

    return round(km_effort / (base_speed * fatigue), 1)


# ---------------------------------------------
# PACE ESTIMATION
# ---------------------------------------------

def estimate_race_paces(diagnosis, race_key, utmb_index=None):
    """Estimate training and race paces based on current fitness.
    For road races: derived from GAP using speed ratios.
    For trails: effort-based with UTMB time estimate.
    """
    gap = diagnosis["gap_recent"]
    if gap <= 0:
        return {"info": "Pas assez de donnees pour estimer les allures."}

    profile = RACE_PROFILES[race_key]

    # GAP is easy-run pace (min/km). Convert to speed, apply ratio, convert back.
    # Speed ratios relative to easy pace (higher = faster).
    _clamp = lambda p: round(max(3.0, min(9.0, p)), 2)

    paces = {
        "facile": _clamp(gap),
        "recup": _clamp(gap * 1.10),
    }

    if race_key == "10km":
        paces["allure_course"] = _clamp(gap / 1.40)
        paces["intervalles"] = _clamp(gap / 1.50)
        paces["tempo"] = _clamp(gap / 1.25)
    elif race_key == "semi":
        paces["allure_course"] = _clamp(gap / 1.30)
        paces["intervalles"] = _clamp(gap / 1.45)
        paces["tempo"] = _clamp(gap / 1.20)
    elif race_key == "marathon":
        paces["allure_course"] = _clamp(gap / 1.20)
        paces["intervalles"] = _clamp(gap / 1.40)
        paces["tempo"] = _clamp(gap / 1.25)
    elif race_key.startswith("trail"):
        paces["effort_montee"] = "Z2-Z3, marche active si pente > 15%"
        paces["effort_plat"] = "Z2, course facile"
        paces["tempo"] = _clamp(gap / 1.15)

    # Estimated finish time
    dist = profile["distance_km"]
    if dist and race_key.startswith("trail"):
        if utmb_index:
            elev = int(dist * 60)  # ~60m D+/km average trail
            time_h = estimate_trail_time(dist, elev, utmb_index)
            paces["temps_estime"] = _format_time(time_h)
            paces["km_effort"] = round(dist + elev / 100, 0)
    elif dist and "allure_course" in paces:
        time_min = paces["allure_course"] * dist
        paces["temps_estime"] = _format_time(time_min / 60)

    return paces


def _format_time(hours):
    """Format hours as Xh or XhMM."""
    h = int(hours)
    m = int((hours - h) * 60)
    if m == 0:
        return f"{h}h"
    return f"{h}h{m:02d}"


# ---------------------------------------------
# DIAGNOSIS
# ---------------------------------------------

def diagnose(df, weeks=12):
    """
    Full training diagnosis based on recent data.
    Returns a dict with all diagnostic metrics and recommendations.
    """
    cutoff = df["date"].max() - pd.Timedelta(weeks=weeks)
    recent = df[df["date"] >= cutoff].copy()
    total_days = (df["date"].max() - df["date"].min()).days

    if recent.empty:
        return {"error": "Pas assez de donnees recentes"}

    # --- Volume ---
    weekly = recent.set_index("date").resample("W").agg(
        km=("distance_km", "sum"),
        elev=("elevation_m", "sum"),
        runs=("distance_km", "count"),
        dur=("duration_min", "sum"),
    )
    avg_km_week = weekly["km"].mean()
    avg_elev_week = weekly["elev"].mean()
    avg_runs_week = weekly["runs"].mean()
    avg_hours_week = weekly["dur"].mean() / 60

    # --- Polarization ---
    polar = compute_polarization(df, weeks)

    # --- Long runs ---
    long_runs = recent[recent["distance_km"] > 20]
    long_runs_count = len(long_runs)
    long_run_avg_km = long_runs["distance_km"].mean() if not long_runs.empty else 0
    max_long_run_km = recent["distance_km"].max() if not recent.empty else 0

    # --- Recovery ---
    sorted_recent = recent.sort_values("date")
    sorted_recent["rest_days"] = sorted_recent["date"].diff().dt.days
    avg_rest = sorted_recent["rest_days"].mean()
    rest_std = sorted_recent["rest_days"].std()

    # --- Pace trends ---
    recent_pace = recent[recent["distance_km"] > 5].copy()
    gap_recent = recent_pace["gap_minkm"].mean() if not recent_pace.empty else 0

    prev_cutoff = cutoff - pd.Timedelta(weeks=weeks)
    previous = df[(df["date"] >= prev_cutoff) & (df["date"] < cutoff)]
    prev_pace = previous[previous["distance_km"] > 5]
    gap_prev = prev_pace["gap_minkm"].mean() if not prev_pace.empty else gap_recent

    pace_trend = gap_recent - gap_prev  # negative = faster

    # --- Volume trend ---
    prev_weekly = previous.set_index("date").resample("W").agg(km=("distance_km", "sum")) if not previous.empty else pd.DataFrame()
    prev_avg_km = prev_weekly["km"].mean() if not prev_weekly.empty else avg_km_week
    volume_change_pct = ((avg_km_week - prev_avg_km) / max(prev_avg_km, 1)) * 100

    # --- Cardiac efficiency ---
    flat_runs = recent[(recent["avg_hr"].notna()) & (recent["distance_km"] > 5) & (recent["elev_per_km"] < 15)]
    if not flat_runs.empty:
        speed_kmh = flat_runs["distance_km"] / (flat_runs["duration_min"] / 60)
        efficiency = (flat_runs["avg_hr"] / speed_kmh).mean()
    else:
        efficiency = None

    # --- Trail ratio ---
    trail_pct = (recent[recent["elev_per_km"] > 20].shape[0] / max(len(recent), 1)) * 100

    # --- Build recommendations ---
    recommendations = []

    if polar["easy_pct"] < 75:
        recommendations.append({
            "priority": "HAUTE",
            "category": "Intensite",
            "message": f"Seulement {polar['easy_pct']}% de ton volume en zone facile (objectif: 80%). "
                       f"Tu passes {polar['moderate_pct']}% en zone moderee (Z3). "
                       f"Ralentis tes sorties faciles sous {int(FC_MAX * 0.70)} bpm.",
        })

    if long_runs_count < 2:
        recommendations.append({
            "priority": "HAUTE",
            "category": "Sortie longue",
            "message": f"Seulement {long_runs_count} sortie(s) longue(s) (>20km) en {weeks} semaines. "
                       f"Vise 2-3 par mois pour maintenir l'endurance.",
        })

    if avg_runs_week < 3:
        recommendations.append({
            "priority": "MOYENNE",
            "category": "Frequence",
            "message": f"Moyenne de {avg_runs_week:.1f} sorties/semaine. "
                       f"3-4 sorties est ideal pour la progression avec bonne recuperation.",
        })

    if volume_change_pct < -25:
        recommendations.append({
            "priority": "INFO",
            "category": "Volume",
            "message": f"Volume en baisse de {abs(volume_change_pct):.0f}% vs les {weeks} semaines precedentes. "
                       f"Si c'est une decharge volontaire, c'est bien. Sinon, remonte progressivement (+10%/sem max).",
        })
    elif volume_change_pct > 20:
        recommendations.append({
            "priority": "ATTENTION",
            "category": "Volume",
            "message": f"Volume en hausse de {volume_change_pct:.0f}%. "
                       f"Attention a ne pas depasser +10% par semaine pour eviter les blessures.",
        })

    if avg_rest < 1.2:
        recommendations.append({
            "priority": "ATTENTION",
            "category": "Recuperation",
            "message": f"Repos moyen de {avg_rest:.1f} jours entre les sorties. "
                       f"Integre au moins 1-2 jours de repos complet par semaine.",
        })

    if pace_trend < -0.3:
        recommendations.append({
            "priority": "POSITIF",
            "category": "Progression",
            "message": f"Allure GAP amelioree de {abs(pace_trend):.2f} min/km. Continue comme ca !",
        })

    return {
        "period_weeks": weeks,
        "avg_km_week": round(avg_km_week, 1),
        "avg_elev_week": round(avg_elev_week),
        "avg_runs_week": round(avg_runs_week, 1),
        "avg_hours_week": round(avg_hours_week, 1),
        "polarization": polar,
        "long_runs_count": long_runs_count,
        "long_run_avg_km": round(long_run_avg_km, 1),
        "max_long_run_km": round(max_long_run_km, 1),
        "avg_rest_days": round(avg_rest, 1),
        "rest_std": round(rest_std, 1) if not pd.isna(rest_std) else 0,
        "gap_recent": round(gap_recent, 2),
        "pace_trend": round(pace_trend, 2),
        "volume_change_pct": round(volume_change_pct),
        "cardiac_efficiency": round(efficiency, 1) if efficiency else None,
        "trail_pct": round(trail_pct),
        "recommendations": recommendations,
        "total_runs": len(df),
        "total_km": round(df["distance_km"].sum()),
        "total_elev": round(df["elevation_m"].sum()),
        "total_days": total_days,
    }


# ---------------------------------------------
# GENERIC WEEKLY PLAN (kept for "general" mode)
# ---------------------------------------------

def generate_weekly_plan(diagnosis, sessions_per_week=4):
    """
    Generate a generic weekly training plan based on diagnosis.
    Returns a list of session dicts.
    """
    avg_km = diagnosis["avg_km_week"]
    target_km = avg_km * 1.05
    gap = diagnosis["gap_recent"]
    p_facile = _format_pace(gap)
    p_recup = _format_pace(gap * 1.10)
    p_seuil = _format_pace(gap / 1.20)

    if sessions_per_week == 3:
        distribution = [
            {"day": "Mardi", "type": "Facile + cotes", "pct": 0.20,
             "fc_target": f"< {int(FC_MAX * 0.70)} bpm (Z2)",
             "details": f"Course facile ({p_facile}/km) avec 4-6 accelerations en cote de 30s. Recuperation complete entre chaque (1-2min trot). L'objectif est le rappel de puissance, pas l'epuisement."},
            {"day": "Jeudi", "type": "Tempo / Seuil", "pct": 0.25,
             "fc_target": f"{int(FC_MAX * 0.80)}-{int(FC_MAX * 0.90)} bpm (Z4)",
             "details": f"Echauffement 15min Z1-Z2. 2x10min a allure seuil ({p_seuil}/km), recup 3min trot. Retour calme 10min. L'allure doit etre soutenue mais controlable."},
            {"day": "Samedi", "type": "Sortie longue", "pct": 0.55,
             "fc_target": f"< {int(FC_MAX * 0.70)} bpm (Z2)",
             "details": f"En nature/trail si possible. Allure tres facile ({p_facile}/km ou plus lent), respiration nasale. Duree 1h30+. Le plus lent possible, c'est le temps sur pieds qui compte."},
        ]
    else:
        distribution = [
            {"day": "Mardi", "type": "Facile + cotes", "pct": 0.15,
             "fc_target": f"< {int(FC_MAX * 0.70)} bpm (Z2)",
             "details": f"Course facile ({p_facile}/km) avec 4-6 accelerations en cote de 30s. Recuperation complete entre chaque (1-2min trot)."},
            {"day": "Mercredi", "type": "Tempo / Seuil", "pct": 0.20,
             "fc_target": f"{int(FC_MAX * 0.80)}-{int(FC_MAX * 0.90)} bpm (Z4)",
             "details": f"Echauffement 15min Z1-Z2. 20-25min a allure seuil ({p_seuil}/km). Retour calme 10min. L'effort est soutenu mais tu peux dire quelques mots."},
            {"day": "Samedi", "type": "Sortie longue", "pct": 0.45,
             "fc_target": f"< {int(FC_MAX * 0.70)} bpm (Z2)",
             "details": f"En nature/trail si possible. Allure tres facile ({p_facile}/km ou plus lent). Duree 1h30+. Le temps sur pieds compte plus que la distance."},
            {"day": "Dimanche", "type": "Recup active", "pct": 0.20,
             "fc_target": f"< {int(FC_MAX * 0.60)} bpm (Z1)",
             "details": f"Footing tres lent ({p_recup}/km), 30-40min. Conversation facile en continu. Alternative : 30min de velo ou natation si les jambes sont lourdes."},
        ]

    MIN_DURATION = 45  # minimum 45 min per session

    plan = []
    for session in distribution:
        km = round(target_km * session["pct"], 1)
        est_pace = diagnosis["gap_recent"] if "Facile" in session["type"] or "Recup" in session["type"] else diagnosis["gap_recent"] - 1.0
        est_dur = round(km * max(est_pace, 4.5))

        # Enforce minimum duration
        if est_dur < MIN_DURATION:
            est_dur = MIN_DURATION
            km = round(MIN_DURATION / max(est_pace, 4.5), 1)

        plan.append({
            "jour": session["day"],
            "type": session["type"],
            "distance_km": km,
            "duree_min": est_dur,
            "fc_cible": session["fc_target"],
            "details": session["details"],
        })

    return plan, round(target_km, 1)


# ---------------------------------------------
# RACE-SPECIFIC WEEKLY PLAN
# ---------------------------------------------

def _format_pace(min_per_km):
    """Format pace as M'SS\\" (e.g. 4'15\\")."""
    m = int(min_per_km)
    s = int((min_per_km - m) * 60)
    return f"{m}'{s:02d}\""


def generate_race_plan(diagnosis, race_key, sessions_per_week=4, elevation_profile=None, utmb_index=None):
    """
    Generate a race-specific weekly training plan.
    Returns (plan_list, target_km).
    """
    profile = RACE_PROFILES[race_key]
    avg_km = diagnosis["avg_km_week"]
    target_km = min(avg_km * 1.05, avg_km * 2.0)  # +5% but cap at 2x

    # Calculate paces for template injection
    paces = estimate_race_paces(diagnosis, race_key, utmb_index)
    pace_vars = {
        "pace_facile": _format_pace(paces.get("facile", diagnosis["gap_recent"])),
        "pace_recup": _format_pace(paces.get("recup", diagnosis["gap_recent"] * 1.10)),
        "pace_course": _format_pace(paces["allure_course"]) if "allure_course" in paces else "",
        "pace_intervalles": _format_pace(paces["intervalles"]) if "intervalles" in paces else "",
        "pace_tempo": _format_pace(paces["tempo"]) if "tempo" in paces else "",
    }

    # Select session types, trim to sessions_per_week
    session_keys = profile["session_types"][:sessions_per_week]
    days = DAYS_3 if sessions_per_week == 3 else DAYS_4

    plan = []
    for i, key in enumerate(session_keys):
        template = SESSION_TEMPLATES[key]
        pct = template["pct"]

        # Cap long run distance
        km = round(target_km * pct, 1)
        if "long" in key and profile["long_run_cap_km"]:
            km = min(km, profile["long_run_cap_km"])

        # Get details for this race type
        details_dict = template["details"]
        details = details_dict.get(race_key, details_dict["default"])

        # Inject actual paces into template
        details = details.format(**pace_vars)

        # Add D+ target for trail elevation sessions
        if elevation_profile == "Denivele significatif" and profile["elevation_focus"]:
            avg_elev = diagnosis["avg_elev_week"]
            if "long" in key:
                details += f" Vise {int(avg_elev * 0.6)}+ m D+."
            elif key == "hills":
                details += f" Vise {int(avg_elev * 0.3)}+ m D+."

        est_pace = diagnosis["gap_recent"] if key in ("easy", "recovery", "long", "long_trail", "back_to_back", "hiking_power") else diagnosis["gap_recent"] - 0.8
        est_dur = round(km * max(est_pace, 4.5))

        # Enforce minimum duration (45 min)
        if est_dur < 45:
            est_dur = 45
            km = round(45 / max(est_pace, 4.5), 1)

        plan.append({
            "jour": days[i] if i < len(days) else template["day"],
            "type": template["type"],
            "distance_km": km,
            "duree_min": est_dur,
            "fc_cible": template["fc_target"],
            "details": details,
        })

    return plan, round(target_km, 1)


# ---------------------------------------------
# PROGRESSION
# ---------------------------------------------

def compute_weeks_to_race(race_date):
    """Compute weeks remaining until race date."""
    if race_date is None:
        return None
    days = (pd.Timestamp(race_date) - pd.Timestamp.today()).days
    return max(1, days // 7)


def _describe_week_sessions(profile, phase, race_key, sessions_per_week):
    """Return a short description of the key sessions for this week's phase."""
    session_keys = profile["session_types"][:sessions_per_week]

    if phase == "Course":
        return "Semaine de course ! 1-2 footings courts + la course"

    if phase == "Affutage":
        # Keep quality sessions but shorter
        parts = []
        for k in session_keys:
            t = SESSION_TEMPLATES.get(k)
            if not t:
                continue
            name = t["type"]
            if k in ("long", "long_trail"):
                parts.append(f"{name} courte (-40%)")
            elif k in ("back_to_back", "recovery", "hiking_power"):
                continue  # skip these in taper
            elif k in ("intervals", "tempo", "marathon_pace", "hills"):
                parts.append(f"{name} (volume reduit)")
            else:
                parts.append(name)
        parts.append("Repos ++")
        return " + ".join(parts)

    if phase == "Decharge":
        parts = []
        for k in session_keys:
            t = SESSION_TEMPLATES.get(k)
            if not t:
                continue
            if k in ("back_to_back",):
                continue
            parts.append(t["type"])
        return " + ".join(parts) + " (allege)"

    # Build phase
    parts = []
    for k in session_keys:
        t = SESSION_TEMPLATES.get(k)
        if t:
            parts.append(t["type"])
    return " + ".join(parts)


def generate_progression(diagnosis, weeks=8, sessions_per_week=4, race_key="general", race_date=None):
    """
    Generate a progressive training plan.
    Follows 3:1 load/deload pattern with optional taper for races.
    """
    profile = RACE_PROFILES[race_key]
    base_km = diagnosis["avg_km_week"]
    volume_cap = base_km * 2.0

    # Determine plan length
    if race_key != "general" and weeks == 8:
        weeks = profile["plan_weeks"]
    if race_date:
        weeks_to_race = compute_weeks_to_race(race_date)
        if weeks_to_race:
            weeks = max(6, min(weeks_to_race, weeks))

    taper_weeks = profile["taper_weeks"]
    build_weeks = weeks - taper_weeks

    # Long run starting point and cap
    max_long_current = diagnosis.get("max_long_run_km", base_km * 0.45)
    long_run_cap = profile["long_run_cap_km"] or (base_km * 0.50)

    plan = []
    for week in range(1, weeks + 1):
        # --- Taper phase ---
        if week > build_weeks:
            taper_num = week - build_weeks
            if taper_num == 1 and taper_weeks >= 2:
                factor = 0.65
                phase = "Affutage"
                note = "Affutage S1 (-35%)"
            elif taper_num == taper_weeks:
                factor = 0.50
                phase = "Affutage"
                note = "Affutage final (-50%)" if week < weeks else "COURSE"
            else:
                factor = 0.55
                phase = "Affutage"
                note = "Affutage"

            if week == weeks:
                phase = "Course"
                note = f"COURSE : {profile['label']}"

            week_km = round(base_km * factor, 1)
            long_km = round(week_km * 0.35, 1)
            nb = sessions_per_week - 1

        # --- Build phase (3:1 pattern) ---
        else:
            if week % 4 == 0:
                factor = 0.70
                phase = "Decharge"
                note = "Decharge (-30%)"
                week_km = round(base_km * factor, 1)
                long_km = round(week_km * 0.40, 1)
                nb = sessions_per_week - 1
            else:
                build_num = week - (week // 4)
                factor = 1.0 + (build_num - 1) * 0.05
                phase = "Build"
                note = f"+{int((factor - 1) * 100)}% vs base"
                week_km = round(min(base_km * factor, volume_cap), 1)

                # Progressive long run
                long_target = max_long_current + (build_num - 1) * 2
                long_km = round(min(long_target, long_run_cap, week_km * profile["max_long_run_pct"]), 1)
                nb = sessions_per_week

        sessions_desc = _describe_week_sessions(profile, phase, race_key, sessions_per_week)

        plan.append({
            "semaine": week,
            "km_total": week_km,
            "sortie_longue_km": long_km,
            "nb_seances": nb,
            "phase": phase,
            "seances": sessions_desc,
            "note": note,
        })

    return plan


# ---------------------------------------------
# NUTRITION & RECOVERY
# ---------------------------------------------

def nutrition_recovery_tips(diagnosis):
    """Generate nutrition and recovery recommendations."""
    tips = []

    tips.append({
        "category": "Hydratation",
        "tip": "Bois 500ml dans les 30 min post-entrainement. Pendant les sorties >1h, vise 500ml/h."
    })

    tips.append({
        "category": "Microbiote",
        "tip": "Reduis les gels et sucres raffines pendant l'effort. Prefere des aliments reels : "
               "dattes, banane, puree de patate douce, riz."
    })
    tips.append({
        "category": "Microbiote",
        "tip": "Integre des aliments fermentes quotidiennement : kefir, kombucha, choucroute, miso. "
               "Ils aident a restaurer la diversite du microbiote."
    })
    tips.append({
        "category": "Microbiote",
        "tip": "Attends 30-45 min apres une seance intense avant de manger. "
               "Le flux sanguin vers l'intestin est reduit pendant l'effort."
    })

    if diagnosis["polarization"]["easy_pct"] < 70:
        tips.append({
            "category": "Stress & cortisol",
            "tip": "Trop d'entrainement en zone moderee (Z3) eleve le cortisol chroniquement. "
                   "Cela aggrave la dysbiose et perturbe le sommeil. Plus de Z1-Z2 = moins de cortisol."
        })

    tips.append({
        "category": "Sommeil",
        "tip": "Vise 7-9h de sommeil. Le sommeil profond est la ou se fait 80% de la recuperation musculaire."
    })

    if diagnosis["avg_rest_days"] < 1.5:
        tips.append({
            "category": "Repos",
            "tip": "Integre au moins 1 jour de repos complet par semaine (zero activite). "
                   "Le repos est un entrainement en soi."
        })

    return tips
