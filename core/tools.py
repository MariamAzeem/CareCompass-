"""Tools the agents can call. Plain helpers (no LLM) + CrewAI @tool wrappers."""
import json
import re
from typing import List
from urllib.parse import quote_plus, urlparse

import requests

from .config import DATA_DIR, TRUSTED_DOMAINS, secret
from .kb import get_kb

SERPER = "https://google.serper.dev"
TIMEOUT = 15


# ---------------- plain helpers ----------------
def serper(endpoint: str, payload: dict) -> dict:
    key = secret("SERPER_API_KEY")
    if not key:
        return {"error": "SERPER_API_KEY is not set"}
    try:
        r = requests.post(f"{SERPER}/{endpoint}", headers={"X-API-KEY": key, "Content-Type": "application/json"},
                          json=payload, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def is_trusted_url(url: str) -> bool:
    try:
        u = urlparse(url)
        host = (u.hostname or "").lower()
        return u.scheme == "https" and any(host == d or host.endswith("." + d) for d in TRUSTED_DOMAINS)
    except Exception:
        return False


def fetch_trusted_page(url: str, max_chars: int = 6000) -> str:
    if not is_trusted_url(url):
        return "BLOCKED: only these sites are allowed: " + ", ".join(TRUSTED_DOMAINS)
    try:
        from bs4 import BeautifulSoup
        r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "CareCompass-Student-Project/1.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            t.decompose()
        main = soup.find("main") or soup.body or soup
        text = " ".join(p.get_text(" ", strip=True) for p in main.find_all(["h1", "h2", "h3", "p", "li"]))
        return re.sub(r"\s+", " ", text)[:max_chars]
    except Exception as e:
        return f"ERROR: could not read page ({e})"


def maps_link(specialist: str, city: str) -> str:
    return "https://www.google.com/maps/search/" + quote_plus(f"{specialist} doctor clinic {city}")


def clinics_from_places(specialist: str, city: str, limit: int = 6) -> List[dict]:
    data = serper("places", {"q": f"{specialist} clinic {city}", "gl": "pk", "num": limit})
    out = []
    for p in data.get("places", [])[:limit]:
        out.append({"name": p.get("title", ""), "area": p.get("address", ""), "fee": "Not listed",
                    "link": p.get("website", "") or "", "phone": p.get("phoneNumber", "") or ""})
    return [c for c in out if c["name"]]


def backup_clinics(specialist: str, city: str) -> List[dict]:
    """Clinics your team typed into data/backup_clinics.json (used when live search fails)."""
    try:
        rows = json.load(open(DATA_DIR / "backup_clinics.json", encoding="utf-8")).get("clinics", [])
    except Exception:
        return []
    sp, ct = specialist.lower(), city.lower()
    return [r for r in rows if r.get("name") and ct in r.get("city", "").lower()
            and (sp in r.get("specialist", "").lower() or r.get("specialist", "").lower() in sp)]


# ---------------- CrewAI tools ----------------
from crewai.tools import tool  # noqa: E402


@tool("search_medical_kb")
def search_medical_kb(query: str) -> str:
    """Search the medical knowledge base. Input: the patient's symptoms in plain words.
    Returns the best matching records (id, score 0-1, care category, urgency, red flags, symptoms)."""
    hits = get_kb().search(query, k=4)
    rows = [{"id": h["id"], "score": h["score"], "care_category": h["record"]["care_category"],
             "urgency": h["record"]["urgency"], "red_flags": h["record"]["red_flags"],
             "symptoms": h["record"]["symptom_keywords"][:6]} for h in hits]
    return json.dumps(rows, ensure_ascii=False)


@tool("get_kb_record")
def get_kb_record(record_id: str) -> str:
    """Fetch one full knowledge-base record by id: specialist, alternative specialist, age and gender notes,
    baseline tests and source."""
    r = get_kb().get(record_id.strip())
    if not r:
        return json.dumps({"error": f"no record with id {record_id}"})
    keep = ["id", "care_category", "urgency", "specialist", "alt_specialist", "age_notes", "gender_notes",
            "baseline_tests", "red_flags", "source"]
    return json.dumps({k: r.get(k) for k in keep}, ensure_ascii=False)


@tool("search_clinics")
def search_clinics(specialist: str, city: str) -> str:
    """Find real clinics for a specialist in a city. Returns clinic names, addresses, phones, websites and
    web snippets that may mention consultation fees."""
    places = clinics_from_places(specialist, city, 8)
    snippets = serper("search", {"q": f"{specialist} consultation fee {city}", "gl": "pk", "num": 6})
    snip = [{"title": s.get("title", ""), "snippet": s.get("snippet", ""), "link": s.get("link", "")}
            for s in snippets.get("organic", [])[:6]]
    if not places and not snip:
        return "SEARCH_UNAVAILABLE"
    return json.dumps({"clinics": places, "fee_snippets": snip}, ensure_ascii=False)


@tool("search_trusted_medical_sources")
def search_trusted_medical_sources(symptoms: str) -> str:
    """Search only trusted health sites (NHS, MedlinePlus, WHO, CDC) for the given symptoms.
    Returns title, url and snippet for each result."""
    sites = " OR ".join(f"site:{d}" for d in TRUSTED_DOMAINS)
    data = serper("search", {"q": f"{symptoms} symptoms when to see a doctor ({sites})", "num": 6})
    if "error" in data:
        return "SEARCH_UNAVAILABLE: " + data["error"]
    rows = [{"title": o.get("title", ""), "url": o.get("link", ""), "snippet": o.get("snippet", "")}
            for o in data.get("organic", []) if is_trusted_url(o.get("link", ""))]
    return json.dumps(rows[:5], ensure_ascii=False) if rows else "NO_TRUSTED_RESULTS"


@tool("read_trusted_page")
def read_trusted_page(url: str) -> str:
    """Read the text of one trusted health page (NHS, MedlinePlus, WHO, CDC only)."""
    return fetch_trusted_page(url.strip())
