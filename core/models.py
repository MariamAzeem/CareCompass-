"""Data shapes shared by the agents, orchestrator and UI (the "JSON contract")."""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

Urgency = Literal["emergency", "urgent", "routine"]
URGENCY_RANK = {"routine": 0, "urgent": 1, "emergency": 2}


class PatientInput(BaseModel):
    age: int
    gender: str
    city: str
    duration: str
    symptoms: str
    want_clinics: bool = True


class TriageResult(BaseModel):
    matched_ids: List[str] = Field(default_factory=list)
    urgency: Urgency = "routine"
    red_flags_found: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    follow_up_questions: List[str] = Field(default_factory=list)
    summary: str = ""


class RouterResult(BaseModel):
    specialist: str
    alt_specialist: str = ""
    reason: str = ""
    tests: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    source_ids: List[str] = Field(default_factory=list)


class Clinic(BaseModel):
    name: str
    area: str = ""
    fee: str = "Not listed"
    link: str = ""
    phone: str = ""


class DirectoryResult(BaseModel):
    clinics: List[Clinic] = Field(default_factory=list)


class KBRecord(BaseModel):
    """What the Learner agent produces when a symptom is not in the KB."""
    id: str
    symptom_keywords: List[str]
    description: str
    care_category: str
    urgency: Urgency
    red_flags: List[str] = Field(default_factory=list)
    specialist: str
    alt_specialist: str = ""
    age_notes: str = ""
    gender_notes: str = ""
    baseline_tests: List[str] = Field(default_factory=list)
    source: str


class MatchedRecord(BaseModel):
    id: str
    care_category: str
    source: str = ""
    origin: str = "curated"   # curated | web_learned
    score: float = 0.0


class ConsultationResult(BaseModel):
    status: Literal["ok", "emergency", "need_followup", "invalid"] = "ok"
    urgency: Urgency = "routine"
    summary: str = ""
    emergency_message: str = ""
    follow_up_questions: List[str] = Field(default_factory=list)
    matched: List[MatchedRecord] = Field(default_factory=list)
    router: Optional[RouterResult] = None
    clinics: List[Clinic] = Field(default_factory=list)
    maps_link: str = ""
    learned_record: Optional[dict] = None
    warnings: List[str] = Field(default_factory=list)
    decision_log: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
