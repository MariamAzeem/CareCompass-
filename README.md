# CareCompass AI

Multi-agent patient triage and clinic directory (CrewAI, ChromaDB, Groq, Serper, Supabase, Streamlit).
Informational only. It does not diagnose. Have a doctor review `data/knowledge_base.json` before real use.

## 1. Get the free keys
| Service | Where | Put in secrets as |
|---|---|---|
| Groq (LLM) | console.groq.com -> API Keys | `GROQ_API_KEY` |
| Serper (web search, clinics) | serper.dev -> API key (free credits) | `SERPER_API_KEY` |
| Supabase (login + history) | supabase.com -> New project | `SUPABASE_URL`, `SUPABASE_ANON_KEY` |

In Supabase: **Project Settings -> API** has the URL and the `anon public` key. Use the anon key only. Never use the service_role key.

## 2. Set up Supabase (5 minutes)
1. **SQL Editor -> New query**, paste all of `supabase_schema.sql`, click **Run**. This creates the history and learned-KB tables with row level security (each user sees only their own history).
2. **Authentication -> Providers -> Email** is on by default. For a faster demo, turn **Confirm email** off. If you leave it on, new users must click the email link before they can log in.
3. Login and sign up are already built into the app (`ui/pages.py -> auth_page`, `core/db.py`). Nothing else to code.

## 3. Run locally
```
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .streamlit\secrets.toml.example .streamlit\secrets.toml   # then fill in your keys
streamlit run app.py
```
Use Python 3.11 or 3.12. The first run downloads a small embedding model (about 80 MB) for ChromaDB.

## 4. Deploy (Streamlit Community Cloud)
Push to GitHub (secrets.toml is git-ignored), create the app from the repo, choose `app.py`, and paste the same keys under **Advanced settings -> Secrets**.

## 5. Project map
```
app.py                 splash, login gate, sidebar navigation
core/orchestrator.py   decides which agent runs (emergency stop, follow-ups, skips, learning)
core/agents.py         Triage, Clinical Router, Directory and Learner agents (CrewAI)
core/tools.py          KB search, clinic search, trusted-page reader (the agents' tools)
core/kb.py             ChromaDB + keyword search (English, Roman Urdu, Urdu)
core/safety.py         emergency and self-harm rules (plain code, no LLM)
core/db.py             Supabase login, history, learned KB
ui/theme.py, pages.py  colors, logo, splash, Home / Chat / History / Login
data/knowledge_base.json   merged KB (102 records)     scripts/merge_kb.py rebuilds it
data/backup_clinics.json   add REAL clinics here (used if live search fails)
tests/test_ui_smoke.py     python tests/test_ui_smoke.py
```

## 6. How the agents decide
Safety rules first -> Triage (KB search) -> if the symptom is unknown the Learner reads NHS / MedlinePlus / WHO / CDC and adds an
**unverified** record to the KB (saved in Supabase so it persists) -> weak match asks up to 2 follow-up questions -> Router picks specialist
and tests (child -> Pediatrician, unsure -> General Physician) -> Directory finds clinics. If Groq or Serper fails, code-only fallbacks still answer.

## 7. Know these limits
- Refreshing the browser logs you out (Streamlit keeps sessions in memory).
- There is no in-app "forgot password". Reset it from Supabase -> Authentication -> Users.
- Learned records are marked unverified. Review rows in the `kb_learned` table and delete bad ones.
- Verify the emergency numbers in `core/safety.py` for your city.
- Groq and Serper free tiers have rate limits. Cache or demo with prepared cases.
