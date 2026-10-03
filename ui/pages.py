"""All screens: Home, Chat, History and the login page."""
import html
import re

import streamlit as st

from core import db
from core.config import APP_NAME, secret
from core.kb import get_kb
from core.models import PatientInput
from core.orchestrator import run_consultation, validate
from core.safety import DISCLAIMER, EMERGENCY_NUMBERS
from ui import theme

PAGES = {}  # filled by app.py so pages can link to each other
GENDERS = ["Female", "Male", "Other / prefer not to say"]
DURATIONS = ["Less than a day", "1 to 3 days", "4 to 7 days", "More than a week", "More than a month"]
URG_LABEL = {"routine": "Routine", "urgent": "See a doctor within a day", "emergency": "Emergency"}


def esc(x) -> str:
    return html.escape(str(x or ""))


def _sources_html(src: str) -> str:
    out = []
    for part in [s.strip() for s in str(src).split("|") if s.strip()]:
        m = re.search(r"https?://[^\s)]+", part)
        label = re.sub(r"\s*-?\s*https?://\S+", "", part).strip(" -:") or "Source"
        out.append(f'<a href="{esc(m.group(0))}" target="_blank">{esc(label[:60])}</a>' if m else esc(label[:60]))
    return " &middot; ".join(out)


# ============================ HOME ============================
def home_page():
    st.markdown(f"""<div class="cc-hero"><h1>Not sure which doctor to see?</h1>
    <p>{APP_NAME} turns your symptoms into a clear next step: the right kind of doctor, the tests they may ask for,
    and clinics near you.</p></div>""", unsafe_allow_html=True)
    if "chat" in PAGES:
        st.page_link(PAGES["chat"], label="Start a consultation", icon=":material/chat:")

    st.subheader("How to use it")
    steps = [("1", "Enter your details", "Age, gender, city, how long you have felt unwell, and your symptoms in your own words. English or Roman Urdu is fine."),
             ("2", "Answer follow-ups", "If your description is vague, the Triage agent asks one or two short questions."),
             ("3", "Read your plan", "You get the kind of doctor to see, tests the doctor may advise, and nearby clinics with estimated fees."),
             ("4", "Come back later", "Every consultation is saved in History so you can show it to your doctor.")]
    for col, (n, t, d) in zip(st.columns(4), steps):
        col.markdown(f'<div class="cc-card"><div class="cc-step">{n}</div><h4>{t}</h4><div class="cc-muted">{d}</div></div>',
                     unsafe_allow_html=True)

    st.subheader("What happens behind the scenes")
    st.markdown("""<div class="cc-card">
    <b>Safety rules</b> check first for emergency wording, in plain code. <b>Triage agent</b> searches the medical knowledge base.
    <b>Clinical Router agent</b> picks the specialist and baseline tests. <b>Directory agent</b> finds clinics and fees online.
    If your symptom is not in the database, a <b>Learner agent</b> reads trusted health sites (NHS, MedlinePlus, WHO, CDC)
    and adds a new, clearly marked entry. The <b>Orchestrator</b> decides which steps run, so different people get different paths.
    </div>""", unsafe_allow_html=True)

    st.subheader("Please read")
    st.markdown(f"""
<div class="cc-alert danger"><b>Emergencies.</b> Severe chest pain, trouble breathing, heavy bleeding, fainting, signs of a stroke,
or thoughts of harming yourself: do not use this app. Call {esc(EMERGENCY_NUMBERS)}</div>
<div class="cc-alert warn"><b>Not a diagnosis.</b> {APP_NAME} suggests the type of care to look for. It cannot examine you,
prescribe medicine or replace a doctor. Tests listed are what a doctor <i>may</i> advise.</div>
<div class="cc-alert warn"><b>Fees and clinics are estimates</b> taken from the web. Always call the clinic to confirm.</div>
<div class="cc-alert warn"><b>Unverified entries.</b> Information the app learned from the web is labelled <i>unverified</i> until a person reviews it.</div>
<div class="cc-alert info"><b>Privacy.</b> Do not type your name, CNIC or phone number into the symptoms box. Your history is stored under your account only.
Babies under 3 months with a fever should see a doctor the same day.</div>
""", unsafe_allow_html=True)
    st.caption("Some medical information is adapted from the NHS website under the Open Government Licence v3.0. "
               "Records must be clinically reviewed before real-world use.")


# ============================ RESULT VIEW ============================
def render_result(r: dict, log_in_expander: bool = True):
    if r["status"] == "emergency":
        st.markdown(f'<div class="cc-emerg-box"><h2>Get medical help now</h2><p>{esc(r["emergency_message"])}</p></div>',
                    unsafe_allow_html=True)
        if r.get("summary"):
            st.caption(r["summary"])
    else:
        urg = r["urgency"]
        st.markdown(f"""<div class="cc-card"><span class="cc-badge cc-{urg}">{URG_LABEL[urg]}</span>
        <h4 style="margin-top:.6rem">What this looks like</h4><div>{esc(r.get('summary'))}</div></div>""", unsafe_allow_html=True)
        if urg == "urgent":
            st.markdown('<div class="cc-alert warn"><b>Please be seen within a day,</b> or go to the emergency room if it gets worse.</div>',
                        unsafe_allow_html=True)
        for w in r.get("warnings", []):
            st.markdown(f'<div class="cc-alert warn">{esc(w)}</div>', unsafe_allow_html=True)

        if r.get("matched"):
            rows = ""
            for m in r["matched"]:
                tag = ('<span class="cc-badge cc-unverified">Unverified, learned from web</span>' if m["origin"] == "web_learned"
                       else '<span class="cc-badge cc-verified">From our database</span>')
                rows += f'<div style="margin:.3rem 0">{tag} <b>{esc(m["care_category"])}</b> <span class="cc-muted">{_sources_html(m["source"])}</span></div>'
            st.markdown(f'<div class="cc-card"><h4>Closest matches</h4>{rows}</div>', unsafe_allow_html=True)

        rt = r.get("router")
        if rt:
            c1, c2 = st.columns(2)
            alt = f'<div class="cc-muted">Backup: {esc(rt["alt_specialist"])}</div>' if rt.get("alt_specialist") else ""
            notes = "".join(f"<li>{esc(n)}</li>" for n in rt.get("notes", []))
            c1.markdown(f"""<div class="cc-card"><h4>See this doctor first</h4>
            <div style="font-family:Sora;font-size:1.5rem;font-weight:700;color:{theme.INDIGO}">{esc(rt['specialist'])}</div>
            {alt}<p style="margin-top:.6rem">{esc(rt['reason'])}</p><ul class="cc-muted">{notes}</ul></div>""", unsafe_allow_html=True)
            tests = "".join(f"<li>{esc(t)}</li>" for t in rt.get("tests", [])) or "<li>None listed</li>"
            c2.markdown(f'<div class="cc-card"><h4>Tests the doctor may advise</h4><ul>{tests}</ul></div>', unsafe_allow_html=True)

        if r.get("clinics") or r.get("maps_link"):
            body = ""
            for c in r.get("clinics", []):
                link = f'<a href="{esc(c["link"])}" target="_blank">Website</a>' if str(c.get("link", "")).startswith("http") else ""
                phone = f" &middot; {esc(c['phone'])}" if c.get("phone") else ""
                body += (f'<div class="cc-clinic"><b>{esc(c["name"])}</b><div class="cc-muted">{esc(c.get("area"))}{phone}</div>'
                         f'<div class="cc-muted">Fee: {esc(c.get("fee") or "Not listed")} {link}</div></div>')
            if not body:
                body = '<div class="cc-muted">No clinics found online. Try the map search below.</div>'
            maps = (f'<p style="margin-top:.8rem"><a href="{esc(r["maps_link"])}" target="_blank">Search this on Google Maps</a></p>'
                    if r.get("maps_link") else "")
            st.markdown(f'<div class="cc-card"><h4>Clinics near you</h4>{body}{maps}'
                        f'<div class="cc-muted" style="margin-top:.4rem">Fees are estimates. Call to confirm.</div></div>',
                        unsafe_allow_html=True)

    log = r.get("decision_log", [])
    if log:
        if log_in_expander:
            with st.expander("How the agents decided"):
                for line in log:
                    st.markdown(f"- {line}")
        else:
            st.markdown("**How the agents decided**\n" + "\n".join(f"- {l}" for l in log))
    st.caption(DISCLAIMER)


# ============================ CHAT ============================
def _reset_chat():
    for k in ("chat_patient", "chat_followups", "chat_round", "chat_result", "chat_saved"):
        st.session_state.pop(k, None)


def _execute(patient: dict, followups, round_no: int):
    p = PatientInput(**patient)
    with st.status("The agents are working...", expanded=True) as status:
        res = run_consultation(p, followups, round_no, allow_learning=True, step=lambda s: st.write("• " + s))
        status.update(label="Done", state="complete", expanded=False)
    st.session_state.update(chat_patient=patient, chat_followups=followups, chat_round=round_no,
                            chat_result=res.model_dump(), chat_saved=False)
    st.rerun()


def _persist(patient: dict, result: dict):
    sb = st.session_state.get("sb")
    if not sb:
        return
    try:
        db.save_consultation(sb, patient, result)
    except Exception as e:
        st.toast(f"Could not save to history: {e}")
    if result.get("learned_record"):
        try:
            db.save_learned(sb, result["learned_record"])
        except Exception:
            pass  # already exists or not allowed: the app still works for this session
    st.session_state.chat_saved = True


def chat_page():
    st.title("Chat")
    if not secret("GROQ_API_KEY"):
        st.warning("GROQ_API_KEY is missing, so the app runs in basic mode (search only, no AI reasoning).")
    res = st.session_state.get("chat_result")

    if res is None:
        st.markdown('<div class="cc-alert danger"><b>Emergency?</b> Do not fill this form. Call '
                    f'{esc(EMERGENCY_NUMBERS)}</div>', unsafe_allow_html=True)
        with st.form("patient_form"):
            c1, c2, c3 = st.columns(3)
            age = c1.number_input("Age", 0, 120, 25, step=1)
            gender = c2.selectbox("Gender", GENDERS)
            duration = c3.selectbox("How long have you had this?", DURATIONS)
            city = st.text_input("City / area", placeholder="e.g. Hyderabad, Latifabad")
            symptoms = st.text_area("Describe your symptoms", height=120,
                                    placeholder="e.g. fever and sore throat since two days. English or Roman Urdu is fine.")
            want = st.checkbox("Also find nearby clinics", value=True)
            go = st.form_submit_button("Get my care plan", type="primary")
        if go:
            patient = dict(age=int(age), gender=gender, city=city.strip(), duration=duration,
                           symptoms=symptoms.strip(), want_clinics=want)
            errs = validate(PatientInput(**patient))
            if errs:
                for e in errs:
                    st.error(e)
            else:
                _execute(patient, [], 0)
        return

    patient = st.session_state.chat_patient
    st.markdown(f'<div class="cc-card"><span class="cc-muted">You wrote</span><br>{esc(patient["symptoms"])}'
                f'<div class="cc-muted" style="margin-top:.4rem">{patient["age"]} years &middot; {esc(patient["gender"])} &middot; '
                f'{esc(patient["duration"])} &middot; {esc(patient["city"])}</div></div>', unsafe_allow_html=True)

    if res["status"] == "need_followup":
        st.markdown('<div class="cc-alert info"><b>A little more detail will help.</b> Answer any of these.</div>', unsafe_allow_html=True)
        with st.form("followup_form"):
            answers = [st.text_input(q, key=f"fu_{st.session_state.chat_round}_{i}") for i, q in enumerate(res["follow_up_questions"])]
            ok = st.form_submit_button("Continue", type="primary")
        if ok:
            pairs = [(q, a.strip()) for q, a in zip(res["follow_up_questions"], answers) if a.strip()]
            if not pairs:
                st.error("Answer at least one question, or start over with more detail.")
            else:
                _execute(patient, list(st.session_state.chat_followups) + pairs, st.session_state.chat_round + 1)
    else:
        render_result(res)
        if not st.session_state.get("chat_saved"):
            _persist(patient, res)
    if st.button("Start a new consultation"):
        _reset_chat()
        st.rerun()


# ============================ HISTORY ============================
def history_page():
    st.title("History")
    sb = st.session_state.get("sb")
    try:
        rows = db.list_consultations(sb)
    except Exception as e:
        st.error(f"Could not load history: {e}")
        return
    if not rows:
        st.markdown('<div class="cc-card">No consultations yet. Open <b>Chat</b> to start your first one.</div>', unsafe_allow_html=True)
        return
    for row in rows:
        when = str(row["created_at"])[:16].replace("T", " ")
        urg = (row.get("urgency") or "routine")
        with st.expander(f"{when}  |  {(row.get('symptoms') or '')[:60]}  |  {row.get('specialist') or urg}"):
            st.caption(f"{row.get('age')} years, {row.get('gender')}, {row.get('city')}, {row.get('duration')}")
            render_result(row["result"], log_in_expander=False)
            if st.button("Delete this entry", key=f"del_{row['id']}"):
                db.delete_consultation(sb, row["id"])
                st.rerun()


# ============================ LOGIN ============================
def _set_user(user):
    st.session_state.user = {"id": user.id, "email": user.email}


def auth_page():
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown(f'<div style="text-align:center"><img src="{theme.logo_data_uri()}" width="72"><h2>{APP_NAME}</h2>'
                    f'<div class="cc-muted">Log in to save your consultations</div></div>', unsafe_allow_html=True)
        if "sb" not in st.session_state:
            st.session_state.sb = db.new_client()
        sb = st.session_state.sb
        t_in, t_up = st.tabs(["Log in", "Sign up"])
        with t_in:
            with st.form("login"):
                email = st.text_input("Email")
                pw = st.text_input("Password", type="password")
                if st.form_submit_button("Log in", type="primary"):
                    try:
                        _set_user(db.sign_in(sb, email.strip(), pw))
                        st.rerun()
                    except Exception as e:
                        st.error("Could not log in. Check your email and password, and confirm your email if Supabase asked you to. "
                                 f"({e})")
        with t_up:
            with st.form("signup"):
                email2 = st.text_input("Email", key="su_email")
                pw2 = st.text_input("Password (8+ characters)", type="password", key="su_pw")
                pw3 = st.text_input("Repeat password", type="password", key="su_pw2")
                if st.form_submit_button("Create account", type="primary"):
                    if len(pw2) < 8:
                        st.error("Use at least 8 characters.")
                    elif pw2 != pw3:
                        st.error("The passwords do not match.")
                    else:
                        try:
                            res = db.sign_up(sb, email2.strip(), pw2)
                            if getattr(res, "session", None) and res.user:
                                db._authed(sb)
                                _set_user(res.user)
                                st.rerun()
                            else:
                                st.success("Account created. Check your email to confirm it, then log in.")
                        except Exception as e:
                            st.error(f"Could not sign up: {e}")
