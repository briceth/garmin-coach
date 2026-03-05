"""
Coaching module: training diagnosis and plan generation.
Analyzes recent training patterns and generates personalized recommendations.
"""

import pandas as pd
import numpy as np
from lib.metrics import FC_MAX, compute_polarization


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


def generate_weekly_plan(diagnosis, sessions_per_week=4):
    """
    Generate a weekly training plan based on diagnosis.
    Returns a list of session dicts.
    """
    avg_km = diagnosis["avg_km_week"]
    target_km = avg_km * 1.05  # +5% progression

    # Distribute volume
    if sessions_per_week == 3:
        distribution = [
            {"day": "Mardi", "type": "Facile + cotes", "pct": 0.20,
             "fc_target": f"< {int(FC_MAX * 0.70)} bpm (Z2)",
             "details": f"Course facile avec 4-6 accelerations en cote de 30s. Recuperation complete entre chaque."},
            {"day": "Jeudi", "type": "Tempo / Seuil", "pct": 0.25,
             "fc_target": f"{int(FC_MAX * 0.80)}-{int(FC_MAX * 0.90)} bpm (Z4)",
             "details": "15 min echauffement Z1-Z2, puis 20-25 min a allure seuil, 10 min retour calme."},
            {"day": "Samedi", "type": "Sortie longue", "pct": 0.55,
             "fc_target": f"< {int(FC_MAX * 0.70)} bpm (Z2)",
             "details": "En nature/trail si possible. Allure tres facile, respirtion nasale. Le plus lent possible."},
        ]
    else:  # 4 sessions
        distribution = [
            {"day": "Mardi", "type": "Facile + cotes", "pct": 0.15,
             "fc_target": f"< {int(FC_MAX * 0.70)} bpm (Z2)",
             "details": "Course facile avec 4-6 accelerations en cote de 30s. Recuperation complete entre chaque."},
            {"day": "Mercredi", "type": "Tempo / Seuil", "pct": 0.20,
             "fc_target": f"{int(FC_MAX * 0.80)}-{int(FC_MAX * 0.90)} bpm (Z4)",
             "details": "15 min echauffement Z1-Z2, puis 20-25 min a allure seuil, 10 min retour calme."},
            {"day": "Samedi", "type": "Sortie longue", "pct": 0.45,
             "fc_target": f"< {int(FC_MAX * 0.70)} bpm (Z2)",
             "details": "En nature/trail si possible. Allure tres facile. Le plus lent possible."},
            {"day": "Dimanche", "type": "Recup active", "pct": 0.20,
             "fc_target": f"< {int(FC_MAX * 0.60)} bpm (Z1)",
             "details": "Tres facile, conversation possible. Aide la recuperation du long de la veille."},
        ]

    plan = []
    for session in distribution:
        km = round(target_km * session["pct"], 1)
        est_pace = diagnosis["gap_recent"] if "Facile" in session["type"] or "Recup" in session["type"] else diagnosis["gap_recent"] - 1.0
        est_dur = round(km * max(est_pace, 4.5))

        plan.append({
            "jour": session["day"],
            "type": session["type"],
            "distance_km": km,
            "duree_min": est_dur,
            "fc_cible": session["fc_target"],
            "details": session["details"],
        })

    return plan, round(target_km, 1)


def generate_progression(diagnosis, weeks=8, sessions_per_week=4):
    """
    Generate an 8-week progressive training plan.
    Follows 3:1 load/deload pattern.
    """
    base_km = diagnosis["avg_km_week"]
    plan = []

    for week in range(1, weeks + 1):
        # 3:1 pattern: 3 weeks build, 1 week deload
        if week % 4 == 0:
            # Deload week
            factor = 0.70
            note = "Decharge (-30%)"
        else:
            # Progressive build: +5% per build week
            build_week = week - (week // 4)
            factor = 1.0 + (build_week - 1) * 0.05
            note = f"+{int((factor - 1) * 100)}% vs base"

        week_km = round(base_km * factor, 1)
        long_km = round(week_km * 0.45, 1) if week % 4 != 0 else round(week_km * 0.40, 1)

        plan.append({
            "semaine": week,
            "km_total": week_km,
            "sortie_longue_km": long_km,
            "nb_seances": sessions_per_week if week % 4 != 0 else sessions_per_week - 1,
            "note": note,
        })

    return plan


def nutrition_recovery_tips(diagnosis):
    """Generate nutrition and recovery recommendations."""
    tips = []

    # General tips
    tips.append({
        "category": "Hydratation",
        "tip": "Bois 500ml dans les 30 min post-entrainement. Pendant les sorties >1h, vise 500ml/h."
    })

    # Dysbiosis-specific
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

    # Intensity-related
    if diagnosis["polarization"]["easy_pct"] < 70:
        tips.append({
            "category": "Stress & cortisol",
            "tip": "Trop d'entrainement en zone moderee (Z3) eleve le cortisol chroniquement. "
                   "Cela aggrave la dysbiose et perturbe le sommeil. Plus de Z1-Z2 = moins de cortisol."
        })

    # Recovery
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
