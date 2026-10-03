"""CareCompass AI - entry point.  Run:  streamlit run app.py"""
import importlib.util
import os
import sys
import time

# Some environments ship an older sqlite3 build that ChromaDB can't use.
# This is optional, so only override sqlite3 when the compatibility package exists.
if importlib.util.find_spec("pysqlite3") is not None:
    try:
        import pysqlite3  # type: ignore[import-not-found]
        sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
    except Exception:
        pass

os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

import streamlit as st  # noqa: E402

from core import db  # noqa: E402
from core.config import APP_NAME, ASSETS_DIR  # noqa: E402
from core.kb import get_kb  # noqa: E402
from ui import pages, theme  # noqa: E402

st.set_page_config(page_title=APP_NAME, page_icon=str(ASSETS_DIR / "favicon.png"), layout="wide")
theme.inject_css()

# ---- animated splash (about 2 seconds). The KB loads behind it. ----
if not st.session_state.get("splash_done"):
    holder = st.empty()
    holder.markdown(theme.splash_html(), unsafe_allow_html=True)
    t0 = time.time()
    get_kb()
    time.sleep(max(0.0, 2.0 - (time.time() - t0)))
    holder.empty()
    st.session_state.splash_done = True

if not db.configured():
    st.error("Supabase is not set up yet. Add SUPABASE_URL and SUPABASE_ANON_KEY to .streamlit/secrets.toml (see README).")
    st.stop()

# ---- login gate ----
if "user" not in st.session_state:
    pages.auth_page()
    st.stop()

sb = st.session_state.sb
if not st.session_state.get("learned_loaded"):  # bring in symptoms learned earlier by anyone
    try:
        get_kb().add_records(db.load_learned(sb))
    except Exception:
        pass
    st.session_state.learned_loaded = True

# ---- sidebar navigation ----
st.logo(str(ASSETS_DIR / "logo.png"), size="large")
home = st.Page(pages.home_page, title="Home", icon=":material/home:", url_path="home", default=True)
chat = st.Page(pages.chat_page, title="Chat", icon=":material/chat:", url_path="chat")
hist = st.Page(pages.history_page, title="History", icon=":material/history:", url_path="history")
pages.PAGES.update(home=home, chat=chat, history=hist)
nav = st.navigation([home, chat, hist])

with st.sidebar:
    st.markdown(f'<div class="cc-user">Signed in as<br>{st.session_state.user["email"]}</div>', unsafe_allow_html=True)
    if st.button("Log out"):
        db.sign_out(sb)
        for k in list(st.session_state.keys()):
            if k != "splash_done":
                del st.session_state[k]
        st.rerun()

nav.run()
