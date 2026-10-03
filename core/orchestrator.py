"""The orchestrator: plain code that decides which agent runs next (and which steps are skipped)."""
from typing import Callable, List, Optional, Tuple

from .agents import run_directory, run_learner, run_router, run_triage
from .config import CONFIDENT_SCORE, MAX_FOLLOWUP_ROUNDS, NO_MATCH_SCORE
from .kb import get_kb
from .models import URGENCY_RANK, ConsultationResult, MatchedRecord, PatientInput
from .safety import EMERGENCY_NUMBERS, check_emergency
from .tools import maps_link

Step = Callable[[str], None]


def validate(p: PatientInput) -> List[str]:
    errs = []
    if not (0 <= p.age <= 120):
        errs.append("Enter an age between 0 and 120.")
    if len(p.symptoms.strip()) < 3:
        errs.append("Describe your symptoms in a few words.")
    if p.want_clinics and not p.city.strip():
        errs.append("Enter your city so we can find clinics.")
    return errs


def _matched(ids: List[str]) -> List[MatchedRecord]:
    kb, out = get_kb(), []
    for i in ids:
        r = kb.get(i)
        if r:
            out.append(MatchedRecord(id=i, care_category=r["care_category"], source=r.get("source", ""),
                                     origin=r.get("origin", "curated")))
    return out


def run_consultation(p: PatientInput, followups: Optional[List[Tuple[str, str]]] = None, round_no: int = 0,
                     allow_learning: bool = True, step: Step = lambda s: None) -> ConsultationResult:
    res = ConsultationResult()
    log = res.decision_log
    followups = followups or []

    errs = validate(p)
    if errs:
        res.status, res.errors = "invalid", errs
        return res

    extra = " ".join(f"{q} {a}" for q, a in followups)
    full_text = f"{p.symptoms} {extra}"

    # 1. Safety rules (no LLM)
    step("Checking for emergency signs")
    emergency = check_emergency(full_text)
    if emergency:
        log.append(f"Safety rule fired: {emergency['reason']}. All agents skipped.")
        res.status, res.urgency = "emergency", "emergency"
        res.summary, res.emergency_message = emergency["reason"], emergency["message"]
        return res
    log.append("Safety rules: no emergency wording found.")

    # 2. Triage
    step("Triage agent is matching your symptoms")
    triage = run_triage(p, extra)
    log.append(f"Triage: matched {triage.matched_ids or 'nothing'}, urgency {triage.urgency}, confidence {triage.confidence:.2f}.")

    # 3. Symptom not in KB -> Learner agent
    if triage.confidence < NO_MATCH_SCORE and allow_learning:
        step("Not in our database. Learner agent is reading trusted health sites")
        learned = run_learner(full_text)
        if learned:
            get_kb().add_records([learned])
            res.learned_record = learned
            res.warnings.append("This match was learned just now from a trusted health website and has not been "
                                "reviewed by our team yet. Treat it with extra care.")
            log.append(f"Learner: added new record '{learned['id']}' from {learned['source']}.")
            step("Triage agent is checking again with the new record")
            triage = run_triage(p, extra)
            log.append(f"Triage (again): matched {triage.matched_ids}, confidence {triage.confidence:.2f}.")
        else:
            log.append("Learner: could not find a trustworthy page. Falling back to a general doctor.")
            res.warnings.append("We could not find reliable information for these symptoms.")

    res.matched = _matched(triage.matched_ids)
    res.urgency = triage.urgency
    res.summary = triage.summary

    # 4. Emergency from triage -> stop
    if triage.urgency == "emergency":
        log.append("Triage says emergency. Router and Directory skipped.")
        res.status = "emergency"
        res.emergency_message = (f"Your symptoms may be serious. Go to the nearest emergency room now or call "
                                 f"{EMERGENCY_NUMBERS}")
        return res

    # 5. Weak match -> ask follow-up questions (max 2 rounds)
    weak = NO_MATCH_SCORE <= triage.confidence < CONFIDENT_SCORE
    if weak and triage.follow_up_questions and round_no < MAX_FOLLOWUP_ROUNDS:
        log.append(f"Match is weak, asking {len(triage.follow_up_questions)} follow-up question(s) (round {round_no + 1}).")
        res.status, res.follow_up_questions = "need_followup", triage.follow_up_questions
        return res
    if triage.confidence < CONFIDENT_SCORE:
        log.append("Still unsure: Router will send you to a General Physician first.")
        res.warnings.append("We are not fully sure about this match, so we suggest starting with a General Physician.")

    # 6. Router
    step("Clinical Router is choosing the specialist and tests")
    router = run_router(p, triage)
    res.router = router
    log.append(f"Router: {router.specialist} (backup: {router.alt_specialist or 'none'}), {len(router.tests)} test(s).")

    # 7. Directory (skippable)
    if p.want_clinics:
        step(f"Directory agent is looking for {router.specialist} clinics in {p.city}")
        d = run_directory(router.specialist, p.city)
        res.clinics = d.clinics
        res.maps_link = maps_link(router.specialist, p.city)
        log.append(f"Directory: {len(d.clinics)} clinic(s) found." if d.clinics else
                   "Directory: no clinics found online, showing a map search link instead.")
    else:
        log.append("Directory skipped (clinic search turned off).")

    res.status = "ok"
    return res
