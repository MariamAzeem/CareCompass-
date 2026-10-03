"""The CrewAI agents. Each agent has one job, its own tools and a structured (JSON) output.
Every run_* function has a no-LLM fallback so the app still answers if Groq is busy."""
import json
import re
import time
from typing import Optional, Type, TypeVar

from crewai import LLM, Agent, Crew, Process, Task

from .config import CHILD_MAX_AGE, CONFIDENT_SCORE, secret
from .kb import get_kb
from .models import (URGENCY_RANK, Clinic, DirectoryResult, KBRecord, PatientInput, RouterResult, TriageResult)
from .tools import (backup_clinics, clinics_from_places, get_kb_record, is_trusted_url, read_trusted_page,
                    search_clinics, search_medical_kb, search_trusted_medical_sources)

T = TypeVar("T")


def get_llm() -> LLM:
    return LLM(model=f"groq/{secret('GROQ_MODEL', 'llama-3.3-70b-versatile')}", api_key=secret("GROQ_API_KEY"),
               temperature=0.1, max_tokens=1500)


def _parse(result, model: Type[T]) -> T:
    obj = getattr(result, "pydantic", None)
    if isinstance(obj, model):
        return obj
    raw = getattr(result, "raw", None) or str(result)
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("agent did not return JSON")
    return model.model_validate(json.loads(m.group(0)))


def _run(agent: Agent, description: str, expected: str, model: Type[T], tries: int = 2) -> T:
    last: Optional[Exception] = None
    for i in range(tries):
        try:
            task = Task(description=description, expected_output=expected, agent=agent, output_pydantic=model)
            crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False, memory=False)
            return _parse(crew.kickoff(), model)
        except Exception as e:  # rate limit, bad JSON, network...
            last = e
            time.sleep(3 * (i + 1) if "rate" in str(e).lower() or "429" in str(e) else 1)
    raise RuntimeError(f"agent failed: {last}")


def _agent(role, goal, backstory, tools):
    return Agent(role=role, goal=goal, backstory=backstory, tools=tools, llm=get_llm(),
                 allow_delegation=False, verbose=False, max_iter=5)


# ======================= 1. TRIAGE =======================
def run_triage(p: PatientInput, extra: str = "") -> TriageResult:
    kb = get_kb()
    text = f"{p.symptoms}. {extra}".strip()
    hits = kb.search(text, k=4)          # code-side search: the trusted confidence score
    top = hits[0] if hits else None

    def fallback() -> TriageResult:
        urg = top["record"]["urgency"] if top and top["score"] >= CONFIDENT_SCORE else "routine"
        return TriageResult(matched_ids=[h["id"] for h in hits[:2] if h["score"] >= 0.35],
                            urgency=urg, confidence=top["score"] if top else 0.0,
                            follow_up_questions=[] if top and top["score"] >= CONFIDENT_SCORE else
                            ["Where exactly do you feel it, and does anything make it better or worse?",
                             "Do you also have fever, vomiting, or trouble breathing?"],
                            summary="Matched using keyword and vector search (AI reasoning was unavailable).")
    try:
        agent = _agent(
            "Medical Triage Specialist",
            "Match the patient's symptoms to the knowledge base, judge urgency, and ask for missing details.",
            "You are careful and never diagnose. You only use records returned by the search tool. "
            "You never name a specialist or tests, because another agent does that.",
            [search_medical_kb])
        out = _run(agent, f"""Patient: age {p.age}, gender {p.gender}, symptoms for {p.duration}.
Symptoms (patient's words): {text}

Steps:
1. Call the search_medical_kb tool with the symptoms in plain words.
2. Pick the 1-3 best matching record ids FROM THE TOOL RESULT ONLY.
3. urgency: 'emergency' if any red flag of a matched record clearly applies; 'urgent' if the patient should be seen within a day; otherwise 'routine'.
4. red_flags_found: only red flags the patient actually described.
5. confidence: use the best tool score (0 to 1).
6. If confidence is below 0.6 or the description is vague, add at most 2 short follow-up questions in simple words. Otherwise leave it empty.
7. summary: one neutral sentence about which kind of problem this looks like. No diagnosis, no specialist, no tests.""",
                   "A JSON object matching the TriageResult schema.", TriageResult)
    except Exception:
        return fallback()

    out.matched_ids = [i for i in out.matched_ids if kb.get(i)] or fallback().matched_ids
    out.confidence = top["score"] if top else 0.0                   # code decides confidence
    if top and top["record"]["urgency"] == "emergency" and top["score"] >= 0.75:
        out.urgency = "emergency"                                   # code can only escalate, never lower
    out.follow_up_questions = out.follow_up_questions[:2]
    return out


# ======================= 2. CLINICAL ROUTER =======================
def run_router(p: PatientInput, t: TriageResult) -> RouterResult:
    kb = get_kb()
    recs = [kb.get(i) for i in t.matched_ids if kb.get(i)]
    top = recs[0] if recs else None

    def fallback() -> RouterResult:
        if not top:
            return RouterResult(specialist="General Physician", reason="No close match, so start with a general doctor.")
        return RouterResult(specialist=top["specialist"], alt_specialist=top.get("alt_specialist", ""),
                            reason=f"Usual first doctor for {top['care_category'].lower()}.",
                            tests=top["baseline_tests"], source_ids=[top["id"]])
    try:
        agent = _agent(
            "Clinical Router",
            "Decide which specialist the patient should see first and which baseline tests a doctor may advise.",
            "You turn a triage result into a clear next step using only the knowledge base records. "
            "You never prescribe medicine and never diagnose.",
            [get_kb_record])
        out = _run(agent, f"""Patient: age {p.age}, gender {p.gender}.
Triage matched record ids: {t.matched_ids}. Urgency: {t.urgency}. Confidence: {t.confidence:.2f}.
Triage summary: {t.summary}

Steps:
1. Call get_kb_record for each matched id.
2. Choose the specialist from those records (specialist field; alt_specialist as the backup).
3. Apply age_notes and gender_notes when they fit this patient.
4. tests: only tests from the records' baseline_tests, written as tests a doctor MAY advise.
5. reason: one plain sentence explaining the choice. source_ids: the record ids you used.""",
                   "A JSON object matching the RouterResult schema.", RouterResult)
    except Exception:
        out = fallback()

    # ---- code-side rules (always applied) ----
    out.notes = list(out.notes)
    if not out.tests and top:
        out.tests = top["baseline_tests"]
    if p.age < CHILD_MAX_AGE and out.specialist.lower() != "pediatrician":
        out.alt_specialist = out.alt_specialist or out.specialist
        out.specialist = "Pediatrician"
        out.notes.append(f"Patient is under {CHILD_MAX_AGE}, so a Pediatrician is the first choice.")
    elif t.confidence < CONFIDENT_SCORE and out.specialist.lower() != "general physician":
        out.alt_specialist = out.alt_specialist or out.specialist
        out.specialist = "General Physician"
        out.notes.append("The match was not certain, so start with a General Physician who can refer you.")
    if t.urgency == "urgent":
        out.notes.append("Please be seen within a day, or sooner if symptoms get worse.")
    out.notes.append("The doctor decides which tests are really needed.")
    return out


# ======================= 3. DIRECTORY =======================
def run_directory(specialist: str, city: str) -> DirectoryResult:
    def from_code() -> DirectoryResult:
        rows = clinics_from_places(specialist, city, 5) or backup_clinics(specialist, city)
        return DirectoryResult(clinics=[Clinic(**{k: r.get(k, "") for k in ("name", "area", "fee", "link", "phone")})
                                        for r in rows[:5]])
    try:
        agent = _agent(
            "Clinic Directory Agent",
            "Find real nearby clinics and any consultation fee information found online.",
            "You report only what the search tool returns. You never invent clinics, phone numbers or fees.",
            [search_clinics])
        out = _run(agent, f"""Find up to 5 {specialist} clinics in {city}, Pakistan.
Call search_clinics with specialist='{specialist}' and city='{city}'.
For each clinic return name, area (address), phone, link, and fee. Put a fee only if a snippet clearly states it for that clinic
or that doctor, written like 'About Rs 2000 (estimate)'. Otherwise write 'Not listed'.
If the tool returns SEARCH_UNAVAILABLE or nothing, return an empty clinics list.""",
                   "A JSON object matching the DirectoryResult schema.", DirectoryResult)
        if not out.clinics:
            return from_code()
        out.clinics = out.clinics[:5]
        return out
    except Exception:
        return from_code()


# ======================= 4. LEARNER (adds new symptoms to the KB) =======================
def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:40] or "unknown"


def run_learner(symptoms: str) -> Optional[dict]:
    """Search trusted sites, summarize in our own words, return a KB record (or None)."""
    try:
        agent = _agent(
            "Medical Research Librarian",
            "Create one safe, short knowledge-base record for symptoms that are missing from the database.",
            "You only use NHS, MedlinePlus, WHO or CDC pages. You write in your own words, you are cautious about "
            "urgency (if unsure choose 'urgent'), and you never copy long text.",
            [search_trusted_medical_sources, read_trusted_page])
        rec = _run(agent, f"""The patient described: "{symptoms}". No record matches this.
1. Call search_trusted_medical_sources with the symptoms.
2. Call read_trusted_page for the most relevant 1 page.
3. Write ONE record: id (short snake_case, start with 'learned_'), symptom_keywords (6-12 words people use, English plus Roman Urdu if you know them),
description (1-2 sentences, own words), care_category, urgency (emergency/urgent/routine), red_flags (3-6), specialist (a doctor type used in Pakistan),
alt_specialist, age_notes, gender_notes, baseline_tests (tests a doctor MAY advise), source (the exact page URL you read).
If you cannot find a trustworthy page, set specialist to 'General Physician' and urgency to 'urgent'.""",
                   "A JSON object matching the KBRecord schema.", KBRecord)
    except Exception:
        return None
    if not is_trusted_url(rec.source) or not rec.symptom_keywords or not rec.specialist:
        return None
    d = rec.model_dump()
    d["id"] = "learned_" + _slug(d["id"].replace("learned_", ""))
    d["source"] = f"{rec.source} (learned from web, unverified)"
    d["origin"] = "web_learned"
    return d
