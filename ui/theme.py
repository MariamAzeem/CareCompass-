"""Colors (from the reference palette), CSS, logo and the animated splash screen."""
import base64

import streamlit as st

from core.config import APP_NAME, APP_TAGLINE, ASSETS_DIR

INDIGO, BLUE, DEEP = "#5E57FF", "#4A8BFE", "#2355D4"
ICE, INK, MUTED = "#F4F7FF", "#1C2150", "#5B6390"
TEAL, CORAL, AMBER, DANGER = "#14DCCC", "#FE9199", "#F6B84B", "#E5484D"
GRADIENT = f"linear-gradient(135deg, #6054FD 0%, {BLUE} 100%)"


def logo_data_uri() -> str:
    svg = (ASSETS_DIR / "logo.svg").read_bytes()
    return "data:image/svg+xml;base64," + base64.b64encode(svg).decode()


CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Sora:wght@600;700&display=swap');
html, body, .stApp, [class*="css"] {{ font-family: 'DM Sans', system-ui, sans-serif; }}
.stApp {{ background: {ICE}; color: {INK}; }}
h1, h2, h3, h4 {{ font-family: 'Sora', 'DM Sans', sans-serif !important; color: {INK}; letter-spacing: -0.01em; }}
footer {{ visibility: hidden; }}
.block-container {{ padding-top: 2rem; max-width: 1080px; }}

/* sidebar */
[data-testid="stSidebar"] {{ background: linear-gradient(190deg, #6054FD 0%, {BLUE} 100%); }}
[data-testid="stSidebar"] * {{ color: #fff !important; }}
[data-testid="stSidebar"] a {{ border-radius: 12px; font-weight: 500; }}
[data-testid="stSidebar"] a:hover {{ background: rgba(255,255,255,.14); }}
[data-testid="stSidebar"] a[aria-current="page"] {{ background: rgba(255,255,255,.22); font-weight: 700; }}
[data-testid="stSidebar"] .stButton > button {{ background: transparent; border: 1px solid rgba(255,255,255,.7); border-radius: 12px; }}
[data-testid="stSidebar"] .stButton > button:hover {{ background: rgba(255,255,255,.16); }}
.cc-user {{ font-size: .85rem; opacity: .9; word-break: break-all; margin-bottom: .5rem; }}

/* buttons + inputs */
.stFormSubmitButton > button, .stButton > button[kind="primary"] {{
  background: {GRADIENT}; color: #fff; border: 0; border-radius: 12px; font-weight: 700; padding: .55rem 1.4rem; }}
.stFormSubmitButton > button:hover, .stButton > button[kind="primary"]:hover {{ filter: brightness(1.07); color: #fff; }}
.stTextInput input, .stTextArea textarea, .stNumberInput input, [data-baseweb="select"] > div {{ border-radius: 12px !important; }}

/* cards + hero */
.cc-hero {{ background: {GRADIENT}; color: #fff; border-radius: 24px; padding: 2.2rem 2.4rem; margin-bottom: 1.4rem; }}
.cc-hero h1 {{ color: #fff !important; margin: 0 0 .4rem 0; font-size: 2.2rem; }}
.cc-hero p {{ color: rgba(255,255,255,.92); font-size: 1.08rem; margin: 0; max-width: 40rem; }}
.cc-card {{ background: #fff; border: 1px solid #E1E6FF; border-radius: 18px; padding: 1.2rem 1.4rem; margin-bottom: 1rem;
  box-shadow: 0 8px 24px rgba(94,87,255,.07); }}
.cc-card h4 {{ margin: 0 0 .4rem 0; }}
.cc-muted {{ color: {MUTED}; font-size: .92rem; }}
.cc-step {{ font-family: 'Sora', sans-serif; font-weight: 700; color: {INDIGO}; font-size: 1.4rem; }}
.cc-badge {{ display: inline-block; padding: .18rem .7rem; border-radius: 999px; font-size: .8rem; font-weight: 700; margin-right: .4rem; }}
.cc-routine {{ background: #D9FBF7; color: #087A70; }}
.cc-urgent {{ background: #FFF0CF; color: #8A5B00; }}
.cc-emergency {{ background: #FFE1E3; color: #B3202A; }}
.cc-unverified {{ background: #FFE5E8; color: #B3202A; }}
.cc-verified {{ background: #E5E8FF; color: {DEEP}; }}
.cc-alert {{ border-radius: 14px; padding: .9rem 1.1rem; margin: .6rem 0 1rem 0; border-left: 6px solid; }}
.cc-alert.danger {{ background: #FFF0F1; border-color: {DANGER}; }}
.cc-alert.warn {{ background: #FFF8E6; border-color: {AMBER}; }}
.cc-alert.info {{ background: #EEF2FF; border-color: {INDIGO}; }}
.cc-emerg-box {{ background: {DANGER}; color: #fff; border-radius: 20px; padding: 1.6rem 1.8rem; margin: 1rem 0; }}
.cc-emerg-box h2 {{ color: #fff !important; margin-top: 0; }}
.cc-clinic {{ border-bottom: 1px solid #EEF0FF; padding: .6rem 0; }}
.cc-clinic:last-child {{ border-bottom: 0; }}
@media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; transition: none !important; }} }}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def splash_html() -> str:
    return f"""
<style>
.cc-splash {{ position: fixed; inset: 0; z-index: 999999; display: flex; align-items: center; justify-content: center;
  background: {GRADIENT}; animation: ccOut .5s ease 1.5s forwards; }}
.cc-splash-inner {{ text-align: center; color: #fff; }}
.cc-splash img {{ width: 96px; height: 96px; animation: ccPop .9s cubic-bezier(.2,1.3,.4,1) both; }}
.cc-splash .t {{ font-family: 'Sora', sans-serif; font-weight: 700; font-size: 2rem; margin-top: 1rem; animation: ccUp .6s ease .35s both; }}
.cc-splash .s {{ opacity: .9; margin-top: .3rem; animation: ccUp .6s ease .55s both; }}
.cc-splash .bar {{ width: 150px; height: 4px; background: rgba(255,255,255,.3); border-radius: 4px; margin: 1.4rem auto 0; overflow: hidden; }}
.cc-splash .bar span {{ display: block; height: 100%; background: #fff; border-radius: 4px; animation: ccFill 1.6s ease-out both; }}
@keyframes ccPop {{ from {{ transform: scale(.3) rotate(-25deg); opacity: 0; }} to {{ transform: scale(1) rotate(0); opacity: 1; }} }}
@keyframes ccUp {{ from {{ transform: translateY(14px); opacity: 0; }} to {{ transform: none; opacity: 1; }} }}
@keyframes ccFill {{ from {{ width: 0; }} to {{ width: 100%; }} }}
@keyframes ccOut {{ to {{ opacity: 0; visibility: hidden; }} }}
</style>
<div class="cc-splash"><div class="cc-splash-inner">
  <img src="{logo_data_uri()}" alt="logo">
  <div class="t">{APP_NAME}</div><div class="s">{APP_TAGLINE}</div>
  <div class="bar"><span></span></div>
</div></div>
"""
