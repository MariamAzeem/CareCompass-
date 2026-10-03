"""UI smoke tests with no internet, no LLM and no Supabase.  Run:  python tests/test_ui_smoke.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.update(SUPABASE_URL="https://abcdefgh.supabase.co", CREWAI_DISABLE_TELEMETRY="true", OTEL_SDK_DISABLED="true",
                  SUPABASE_ANON_KEY="eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiJ9.c2ln")

from streamlit.testing.v1 import AppTest  # noqa: E402

import core.agents as A  # noqa: E402
import core.db as db  # noqa: E402
import core.tools as T  # noqa: E402


def _boom(*a, **k):
    raise RuntimeError("no llm")


A._run = _boom                      # agents fall back to code-only answers
T.serper = lambda *a, **k: {"error": "offline"}
A.clinics_from_places = lambda *a, **k: []
saved = []
db.save_consultation = lambda sb, patient, result: saved.append(result)
db.load_learned = lambda sb: []


def chat_script():
    from ui import pages, theme
    theme.inject_css()
    pages.chat_page()


def hist_script():
    from ui import pages, theme
    theme.inject_css()
    pages.history_page()


def submit(at, city, symptoms):
    at.text_input[0].set_value(city)
    at.text_area[0].set_value(symptoms)
    [b for b in at.button if "care plan" in b.label][0].click()
    at.run()
    return " ".join(m.value for m in at.markdown)


def chat():
    at = AppTest.from_function(chat_script, default_timeout=60)
    at.session_state["sb"] = object()
    return at.run()


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    return cond


ok = True
at = AppTest.from_file("../app.py", default_timeout=60).run()
ok &= check("login page renders", not at.exception and [t.label for t in at.tabs] == ["Log in", "Sign up"])

at = AppTest.from_file("../app.py", default_timeout=60)
at.session_state["splash_done"] = True
at.session_state["user"] = {"id": "u1", "email": "me@test.com"}
at.session_state["sb"] = object()
at.run()
html = " ".join(m.value for m in at.markdown)
ok &= check("home page renders with cautions", not at.exception and "Not a diagnosis" in html)

at = chat()
ok &= check("chat form renders", not at.exception and len(at.text_area) == 1)
html = submit(at, "Hyderabad", "fever and sore throat since two days")
ok &= check("normal case gives specialist, tests and map", not at.exception and "See this doctor first" in html
            and "Tests the doctor may advise" in html and "google.com/maps" in html)
ok &= check("consultation saved to history", len(saved) == 1)

at = chat()
html = submit(at, "Hyderabad", "severe chest pain and sweating")
ok &= check("emergency stops the flow", "Get medical help now" in html and "See this doctor first" not in html)

at = chat()
submit(at, "Hyderabad", "my toe is tingling and itchy at night")
ok &= check("vague text asks follow-up questions", not at.exception and len(at.text_input) >= 1)
at.text_input[0].set_value("only at night, no fever")
[b for b in at.button if b.label == "Continue"][0].click()
at.run()
ok &= check("follow-up answer continues without error", not at.exception)

db.list_consultations = lambda sb, limit=50: [{
    "id": "c1", "created_at": "2026-10-03T12:00:00", "age": 30, "gender": "Female", "city": "Hyderabad",
    "duration": "1 to 3 days", "symptoms": "fever and sore throat", "urgency": "routine",
    "specialist": "General Physician", "result": saved[0]}]
at = AppTest.from_function(hist_script, default_timeout=60)
at.session_state["sb"] = object()
at.run()
ok &= check("history lists saved consultation", not at.exception and len(at.expander) == 1)
sys.exit(0 if ok else 1)
