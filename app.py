"""
Integrated DECIDE Decision Cockpit — Dynamic Demand to Production Decision System
TI4001 Proyek Rekayasa Inter-Disiplin ITB — Kelompok 39

Prototype MVP. Seluruh data adalah Prototype / Dummy Data dan tidak
terhubung ke SAP maupun sistem PT Paragon.

Jalankan:  streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="DECIDE Decision Cockpit", page_icon="🧭", layout="wide",
                   initial_sidebar_state="expanded")

from engine import approval_engine as ap  # noqa: E402
from utils import state  # noqa: E402
from utils.styles import inject_css  # noqa: E402
from views import (approval, demand_buffer, feasibility, monitoring, overview, priority,  # noqa: E402
                   scenario, sequencing)

RENDER = {
    "Overview": overview.render,
    "Demand & Buffer": demand_buffer.render,
    "Priority": priority.render,
    "Feasibility": feasibility.render,
    "Sequencing & ETA": sequencing.render,
    "What-if": scenario.render,
    "Decision Review": approval.render,
    "Performance": monitoring.render,
}

state.init_state()
inject_css()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<p class="dc-brand">DECIDE<span>.</span></p>'
                '<p class="dc-sub">DEMAND → PRODUCTION DECISION COCKPIT</p>', unsafe_allow_html=True)

    st.selectbox("Select Role", state.ROLES, key="role")
    st.markdown(f'<div class="dc-role"><div class="lbl">Current Role</div>'
                f'<div class="val">{st.session_state.role}</div></div>', unsafe_allow_html=True)

    pages = state.allowed_pages(st.session_state.role)
    if st.session_state.nav not in pages:
        st.session_state.nav = "Overview"

    st.markdown("---")
    st.radio("Menu", pages, key="nav",
             format_func=lambda p: f"{state.PAGES[p][0]} · {p}", label_visibility="collapsed")
    st.markdown("---")

    wf = st.session_state.workflow
    st.markdown(
        f'<div class="dc-side-chip">Skenario aktif: <b>{st.session_state.selected_scenario}</b></div>'
        f'<div class="dc-side-chip">Status jadwal: <b>{ap.STATUS_LABEL[wf["status"]].split(" — ")[0]}</b>'
        f' · v{wf["version"]}</div>'
        f'<div class="dc-side-chip">Snapshot stok: <b>09 Nov 2026</b> · Plan mulai 16 Nov 2026</div>'
        f'<div class="dc-side-chip" style="background:#5A3A12">⚠ Prototype / Dummy Data — '
        f'tidak terhubung SAP</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Halaman
# ---------------------------------------------------------------------------
if st.session_state.get("flash"):
    st.toast(st.session_state.pop("flash"), icon="✅")
RENDER[st.session_state.nav]()
