"""
Design system DECIDE Decision Cockpit: warna, CSS, komponen kartu & badge.
Palet: dark navy, white, orange (accent), teal/green (aman).
"""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

NAVY = "#0B1F3A"
NAVY_2 = "#16305A"
ORANGE = "#F07F1E"
TEAL = "#0E9F8A"
GREEN = "#2BA36B"
RED = "#D64545"
AMBER = "#E8A33D"
BG = "#F4F6FA"
TEXT = "#1B2A41"
MUTED = "#6B7A90"
BORDER = "#E3E8F0"



def _stretch_kwargs() -> dict:
    """Kompatibilitas: Streamlit >= 1.49 memakai width="stretch", versi lama use_container_width."""
    try:
        major, minor = (int(x) for x in st.__version__.split(".")[:2])
    except Exception:  # noqa: BLE001
        return {"width": "stretch"}
    return {"width": "stretch"} if (major, minor) >= (1, 49) else {"use_container_width": True}


W = _stretch_kwargs()   # dipakai: st.dataframe(df, **W)

BADGE_COLORS = {
    "P1": RED, "P2": ORANGE, "P3": GREEN,
    "Risk": RED, "Watch": AMBER, "Normal": TEAL,
    "LAYAK": TEAL, "HOLD": RED,
    "Material Shortage": RED, "Supplier ETA Risk": AMBER, "Material Ready": TEAL,
    "On time": TEAL, "Late": RED,
}

CLASS_SCALE = {"domain": ["P1", "P2", "P3"], "range": [RED, ORANGE, GREEN]}
STATUS_SCALE = {"domain": ["Risk", "Watch", "Normal"], "range": [RED, AMBER, TEAL]}

CSS = f"""
<style>
:root {{ --navy:{NAVY}; --orange:{ORANGE}; --teal:{TEAL}; }}
.stApp {{ background:{BG}; }}
.block-container {{ padding-top:1.4rem; padding-bottom:2rem; max-width:1400px; }}
h1, h2, h3, h4 {{ color:{NAVY}; letter-spacing:-0.01em; }}

/* Sidebar */
section[data-testid="stSidebar"] {{ background:{NAVY}; }}
section[data-testid="stSidebar"] * {{ color:#E8EDF5; }}
section[data-testid="stSidebar"] [data-baseweb="select"] * {{ color:{TEXT}; }}
section[data-testid="stSidebar"] [role="radiogroup"] label {{
    padding:7px 10px; border-radius:8px; margin-bottom:2px; width:100%;
}}
section[data-testid="stSidebar"] [role="radiogroup"] label:hover {{ background:{NAVY_2}; }}
section[data-testid="stSidebar"] hr {{ border-color:#2A426B; }}
.dc-brand {{ font-size:1.65rem; font-weight:800; letter-spacing:0.08em; color:#FFFFFF; margin:0; }}
.dc-brand span {{ color:{ORANGE}; }}
.dc-sub {{ font-size:0.72rem; color:#9FB0CC !important; margin-top:-2px; letter-spacing:0.04em; }}
.dc-role {{ background:{NAVY_2}; border-left:4px solid {ORANGE}; border-radius:8px; padding:8px 10px; margin:6px 0 4px 0; }}
.dc-role .lbl {{ font-size:0.68rem; text-transform:uppercase; letter-spacing:0.08em; color:#9FB0CC !important; }}
.dc-role .val {{ font-size:0.95rem; font-weight:700; }}
.dc-side-chip {{ font-size:0.75rem; background:{NAVY_2}; border-radius:6px; padding:6px 8px; margin-top:6px; }}

/* Header */
.dc-header {{ display:flex; justify-content:space-between; align-items:flex-end;
    border-bottom:2px solid {BORDER}; padding-bottom:10px; margin-bottom:16px; }}
.dc-code {{ font-size:0.75rem; font-weight:700; color:{ORANGE}; letter-spacing:0.12em; }}
.dc-title {{ font-size:1.6rem; font-weight:800; color:{NAVY}; line-height:1.15; }}
.dc-desc {{ font-size:0.88rem; color:{MUTED}; margin-top:2px; }}
.dc-tags {{ text-align:right; }}

/* Cards */
.dc-card {{ background:#FFFFFF; border:1px solid {BORDER}; border-radius:14px; padding:14px 16px;
    box-shadow:0 1px 2px rgba(11,31,58,0.04); height:100%; }}
.dc-kpi {{ border-top:4px solid var(--accent, {NAVY}); }}
.dc-kpi .k-label {{ font-size:0.74rem; text-transform:uppercase; letter-spacing:0.06em; color:{MUTED}; font-weight:600; }}
.dc-kpi .k-value {{ font-size:2rem; font-weight:800; color:{NAVY}; line-height:1.15; margin-top:4px; }}
.dc-kpi .k-sub {{ font-size:0.78rem; color:{MUTED}; margin-top:2px; }}
.dc-section {{ font-size:0.8rem; font-weight:700; color:{NAVY}; text-transform:uppercase;
    letter-spacing:0.08em; margin:18px 0 8px 0; border-left:4px solid {ORANGE}; padding-left:8px; }}

/* Badges */
.dc-badge {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.74rem; font-weight:700;
    color:#FFFFFF; letter-spacing:0.02em; white-space:nowrap; }}
.dc-pill {{ display:inline-block; padding:3px 10px; border-radius:999px; font-size:0.72rem; font-weight:600;
    border:1px solid {BORDER}; background:#FFFFFF; color:{MUTED}; margin-left:4px; }}
.dc-dummy {{ background:#FFF4E8; color:#9A4D00; border:1px solid #F7C99A; }}

/* Alert rows */
.dc-alert {{ display:flex; gap:10px; align-items:flex-start; padding:9px 12px; border-radius:10px;
    background:#FFFFFF; border:1px solid {BORDER}; margin-bottom:6px; font-size:0.86rem; }}
.dc-alert .bar {{ width:4px; align-self:stretch; border-radius:4px; }}
.dc-alert b {{ color:{NAVY}; }}

/* Stepper */
.dc-steps {{ display:flex; gap:8px; margin:6px 0 14px 0; }}
.dc-step {{ flex:1; background:#FFFFFF; border:1px solid {BORDER}; border-radius:12px; padding:10px 12px; }}
.dc-step .s-no {{ font-size:0.7rem; color:{MUTED}; font-weight:700; letter-spacing:0.08em; }}
.dc-step .s-t {{ font-size:0.9rem; font-weight:700; color:{NAVY}; }}
.dc-step .s-st {{ font-size:0.76rem; margin-top:3px; }}
.dc-step.done {{ border-top:4px solid {TEAL}; }}
.dc-step.active {{ border-top:4px solid {ORANGE}; }}
.dc-step.blocked {{ border-top:4px solid {RED}; }}
.dc-step.todo {{ border-top:4px solid {BORDER}; }}

/* Status banner */
.dc-banner {{ border-radius:12px; padding:12px 16px; font-weight:700; font-size:1rem; color:#FFFFFF; margin:6px 0 12px 0; }}

div[data-testid="stMetric"] {{ background:#FFFFFF; border:1px solid {BORDER}; border-radius:12px; padding:10px 14px; }}
.stTabs [data-baseweb="tab"] {{ font-weight:600; }}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def badge(text: str, color: str | None = None) -> str:
    c = color or BADGE_COLORS.get(str(text), NAVY)
    return f'<span class="dc-badge" style="background:{c}">{html.escape(str(text))}</span>'


def page_header(code: str, title: str, desc: str, users: str):
    st.markdown(
        f"""<div class="dc-header">
        <div><div class="dc-code">{code}</div><div class="dc-title">{html.escape(title)}</div>
        <div class="dc-desc">{html.escape(desc)}</div></div>
        <div class="dc-tags"><span class="dc-pill">User: {html.escape(users)}</span>
        <span class="dc-pill dc-dummy">Prototype / Dummy Data</span></div></div>""",
        unsafe_allow_html=True,
    )


def section(title: str):
    st.markdown(f'<div class="dc-section">{html.escape(title)}</div>', unsafe_allow_html=True)


def kpi_card(label: str, value, sub: str = "", accent: str = NAVY):
    st.markdown(
        f"""<div class="dc-card dc-kpi" style="--accent:{accent}">
        <div class="k-label">{html.escape(label)}</div>
        <div class="k-value">{html.escape(str(value))}</div>
        <div class="k-sub">{sub}</div></div>""",
        unsafe_allow_html=True,
    )


def alert_row(title: str, body: str, color: str):
    st.markdown(
        f"""<div class="dc-alert"><div class="bar" style="background:{color}"></div>
        <div><b>{html.escape(title)}</b><br><span style="color:{MUTED}">{html.escape(body)}</span></div></div>""",
        unsafe_allow_html=True,
    )


def banner(text: str, color: str):
    st.markdown(f'<div class="dc-banner" style="background:{color}">{html.escape(text)}</div>',
                unsafe_allow_html=True)


def stepper(steps: list[tuple[str, str, str]]):
    """steps: list (judul, status_text, state) ; state in done/active/blocked/todo."""
    parts = []
    for i, (title, st_text, state) in enumerate(steps, 1):
        color = {"done": TEAL, "active": ORANGE, "blocked": RED}.get(state, MUTED)
        parts.append(f'<div class="dc-step {state}"><div class="s-no">STEP {i}</div>'
                     f'<div class="s-t">{html.escape(title)}</div>'
                     f'<div class="s-st" style="color:{color}">{html.escape(st_text)}</div></div>')
    st.markdown(f'<div class="dc-steps">{"".join(parts)}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# DataFrame styling
# ---------------------------------------------------------------------------
def _badge_css(v):
    c = BADGE_COLORS.get(str(v))
    if c is None and str(v).startswith("FLAG TERLAMBAT"):
        c = RED
    if c is None:
        return ""
    return f"background-color:{c}; color:white; font-weight:700; text-align:center;"


def style_table(df: pd.DataFrame, badge_cols=(), formats: dict | None = None):
    sty = df.style
    cols = [c for c in badge_cols if c in df.columns]
    if cols:
        sty = sty.map(_badge_css, subset=cols)
    if formats:
        sty = sty.format({k: v for k, v in formats.items() if k in df.columns}, na_rep="-")
    return sty
