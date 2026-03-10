"""
Authentication module for Garmin Connect.
"""

import os
import streamlit as st


def get_garmin_config():
    """Get Garmin credentials from st.secrets or environment."""
    try:
        return st.secrets["garmin"]["email"], st.secrets["garmin"]["password"]
    except Exception:
        from dotenv import load_dotenv
        load_dotenv()
        return os.getenv("GARMIN_EMAIL", ""), os.getenv("GARMIN_PASSWORD", "")


def get_garmin_client():
    """Login to Garmin Connect and return the client.
    Returns (client, error_message) tuple.
    """
    if "garmin_client" in st.session_state:
        return st.session_state["garmin_client"], None

    email, password = get_garmin_config()
    if not email or not password:
        return None, "Credentials Garmin manquants. Configure GARMIN_EMAIL et GARMIN_PASSWORD."

    try:
        from garminconnect import Garmin
        garmin = Garmin(email, password)
        garmin.login()
        st.session_state["garmin_client"] = garmin
        return garmin, None
    except Exception as e:
        return None, f"Connexion Garmin echouee : {e}"
