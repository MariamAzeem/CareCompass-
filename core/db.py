"""Supabase: login (Supabase Auth), consultation history, and KB records learned from the web."""
import json
from typing import List, Optional

from supabase import Client, create_client

from .config import secret


def configured() -> bool:
    return bool(secret("SUPABASE_URL") and secret("SUPABASE_ANON_KEY"))


def new_client() -> Client:
    """One client PER USER SESSION (store it in st.session_state, never in a shared cache)."""
    return create_client(secret("SUPABASE_URL"), secret("SUPABASE_ANON_KEY"))


def _authed(sb: Client):
    """Refresh the token if needed and make sure the database calls use it."""
    session = sb.auth.get_session()
    if session:
        try:
            sb.postgrest.auth(session.access_token)
        except Exception:
            pass
    return session


# ---------- auth ----------
def sign_up(sb: Client, email: str, password: str):
    return sb.auth.sign_up({"email": email, "password": password})


def sign_in(sb: Client, email: str, password: str):
    res = sb.auth.sign_in_with_password({"email": email, "password": password})
    _authed(sb)
    return res.user


def sign_out(sb: Client):
    try:
        sb.auth.sign_out()
    except Exception:
        pass


def reset_password(sb: Client, email: str):
    sb.auth.reset_password_for_email(email)


# ---------- history ----------
def save_consultation(sb: Client, patient: dict, result: dict):
    _authed(sb)
    sb.table("consultations").insert({
        "age": patient["age"], "gender": patient["gender"], "city": patient["city"],
        "duration": patient["duration"], "symptoms": patient["symptoms"],
        "urgency": result.get("urgency"),
        "specialist": (result.get("router") or {}).get("specialist"),
        "result": result,
    }).execute()


def list_consultations(sb: Client, limit: int = 50) -> List[dict]:
    _authed(sb)
    return sb.table("consultations").select("*").order("created_at", desc=True).limit(limit).execute().data or []


def delete_consultation(sb: Client, cid: str):
    _authed(sb)
    sb.table("consultations").delete().eq("id", cid).execute()


# ---------- learned KB ----------
def load_learned(sb: Client) -> List[dict]:
    _authed(sb)
    rows = sb.table("kb_learned").select("record").execute().data or []
    return [r["record"] for r in rows if r.get("record")]


def save_learned(sb: Client, record: dict):
    _authed(sb)
    sb.table("kb_learned").upsert({"id": record["id"], "record": record}).execute()
