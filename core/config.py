"""Settings. Values come from .streamlit/secrets.toml (or environment variables)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ASSETS_DIR = ROOT / "assets"

APP_NAME = "CareCompass AI"
APP_TAGLINE = "Find the right care, faster"

CHILD_MAX_AGE = 12          # under this age -> Pediatrician
CONFIDENT_SCORE = 0.60      # >= this: clear KB match
NO_MATCH_SCORE = 0.35       # < this: symptom not in KB -> learn from the web
MAX_FOLLOWUP_ROUNDS = 2

# The agent may only learn from these sites
TRUSTED_DOMAINS = ("nhs.uk", "medlineplus.gov", "who.int", "cdc.gov")


def secret(key: str, default: str = "") -> str:
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.getenv(key, default)
