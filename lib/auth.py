"""
Authentication module for Strava OAuth2 and Garmin Connect.
Supports both local dev (localhost callback) and Streamlit Cloud (query params).
"""

import os
import json
import requests
import streamlit as st
from datetime import datetime


TOKEN_FILE = "strava_token.json"


def get_strava_config():
    """Get Strava credentials from st.secrets or environment."""
    try:
        return st.secrets["strava"]["client_id"], st.secrets["strava"]["client_secret"]
    except Exception:
        from dotenv import load_dotenv
        load_dotenv()
        return os.getenv("STRAVA_CLIENT_ID", ""), os.getenv("STRAVA_CLIENT_SECRET", "")


def get_strava_auth_url(redirect_uri=None):
    """Generate the Strava OAuth authorization URL."""
    client_id, _ = get_strava_config()
    if redirect_uri is None:
        redirect_uri = _get_redirect_uri()
    return (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=activity:read_all"
    )


def _get_redirect_uri():
    """Determine redirect URI based on environment."""
    # Streamlit Cloud sets STREAMLIT_SERVER_ADDRESS or similar
    # For local dev, use localhost
    if os.getenv("STREAMLIT_SHARING_MODE") or os.getenv("STREAMLIT_SERVER_ADDRESS"):
        # On Streamlit Cloud, use the app URL
        return "https://strava-coach.streamlit.app/"
    return "http://localhost:8501/"


def exchange_code_for_token(code):
    """Exchange OAuth code for access + refresh tokens."""
    client_id, client_secret = get_strava_config()
    res = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
    })
    if res.status_code != 200:
        return None
    token_data = res.json()
    # Save locally for persistence between restarts
    try:
        with open(TOKEN_FILE, "w") as f:
            json.dump(token_data, f)
    except OSError:
        pass
    return token_data


def refresh_strava_token(token_data):
    """Refresh an expired Strava token."""
    client_id, client_secret = get_strava_config()
    res = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": token_data["refresh_token"],
    })
    if res.status_code != 200:
        return None
    new_data = res.json()
    try:
        with open(TOKEN_FILE, "w") as f:
            json.dump(new_data, f)
    except OSError:
        pass
    return new_data


def get_strava_token():
    """
    Get a valid Strava access token.
    Checks: session_state -> file cache -> needs auth.
    Returns (token_string, needs_auth_bool).
    """
    # 1. Check session state
    if "strava_token" in st.session_state:
        token_data = st.session_state["strava_token"]
        if token_data["expires_at"] > datetime.now().timestamp():
            return token_data["access_token"], False
        # Refresh
        new_data = refresh_strava_token(token_data)
        if new_data:
            st.session_state["strava_token"] = new_data
            return new_data["access_token"], False

    # 2. Check file cache
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            token_data = json.load(f)
        if token_data.get("expires_at", 0) > datetime.now().timestamp():
            st.session_state["strava_token"] = token_data
            return token_data["access_token"], False
        # Refresh
        new_data = refresh_strava_token(token_data)
        if new_data:
            st.session_state["strava_token"] = new_data
            return new_data["access_token"], False

    # 3. Check URL query params (OAuth callback)
    params = st.query_params
    if "code" in params:
        code = params["code"]
        token_data = exchange_code_for_token(code)
        if token_data and "access_token" in token_data:
            st.session_state["strava_token"] = token_data
            st.query_params.clear()
            return token_data["access_token"], False

    # 4. Need auth
    return None, True


def get_garmin_client():
    """Login to Garmin Connect and return the client."""
    if "garmin_client" in st.session_state:
        return st.session_state["garmin_client"]

    try:
        email = st.secrets["garmin"]["email"]
        password = st.secrets["garmin"]["password"]
    except Exception:
        from dotenv import load_dotenv
        load_dotenv()
        email = os.getenv("GARMIN_EMAIL")
        password = os.getenv("GARMIN_PASSWORD")

    if not email or not password:
        return None

    try:
        from garminconnect import Garmin
        garmin = Garmin(email, password)
        garmin.login()
        st.session_state["garmin_client"] = garmin
        return garmin
    except Exception as e:
        st.warning(f"Connexion Garmin echouee : {e}")
        return None
