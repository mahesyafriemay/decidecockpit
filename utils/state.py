"""
Session state, role-based access, dan akses hasil decision engine (cached).
"""
from __future__ import annotations

import copy
import json

import streamlit as st

from engine import approval_engine as ap
from engine import config as cfg
from engine.scenario_engine import default_scenario_params, run_pipeline
from utils.helpers import load_data, validate_data

ROLES = ["PPC / Production Planner", "Supply Planner", "Leader Produksi"]
PPC, SUPPLY, LEADER = ROLES

# Menu sidebar -> (kode, judul, role yang boleh akses) — mengikuti UI Tree
PAGES = {
    "Overview": ("H01", "Overview & Early Warning", [PPC, SUPPLY, LEADER]),
    "Demand & Buffer": ("H02", "Demand & Buffer Monitoring", [PPC, SUPPLY, LEADER]),
    "Priority": ("H03", "Production Priority Ranking", [PPC, LEADER]),
    "Feasibility": ("H04", "Feasibility Gate", [PPC, SUPPLY]),
    "Sequencing & ETA": ("H05", "Sequencing & ETA", [PPC, LEADER]),
    "What-if": ("H06", "What-if & Replanning", [PPC, LEADER]),
    "Decision Review": ("H07", "Decision Review & Approval", [PPC, SUPPLY, LEADER]),
    "Performance": ("H08", "Performance Monitoring", [PPC, LEADER]),
}

# Halaman yang hanya dapat dilihat (tanpa aksi) oleh role tertentu
VIEW_ONLY = {("Demand & Buffer", LEADER), ("Demand & Buffer", SUPPLY)}


def allowed_pages(role: str) -> list[str]:
    return [k for k, (_, _, roles) in PAGES.items() if role in roles]


def init_state():
    ss = st.session_state
    ss.setdefault("role", PPC)
    ss.setdefault("nav", "Overview")
    ss.setdefault("params_baseline", default_scenario_params())
    ss.setdefault("params_alt", default_scenario_params())
    ss.setdefault("alt_ran", False)
    ss.setdefault("selected_scenario", "Baseline")
    ss.setdefault("workflow", ap.new_workflow())
    ss.setdefault("material_feedback", [])
    ss.setdefault("approved_kpi", None)


@st.cache_data(show_spinner=False)
def get_data():
    return load_data()


@st.cache_data(show_spinner=False)
def get_data_issues():
    return validate_data(load_data())


@st.cache_data(show_spinner="Menjalankan decision engine...")
def _run_cached(params_json: str):
    return run_pipeline(load_data(), json.loads(params_json))


def run_with(params: dict) -> dict:
    return _run_cached(json.dumps(params, sort_keys=True, default=str))


def scenario_params(name: str) -> dict:
    return st.session_state.params_baseline if name == "Baseline" else st.session_state.params_alt


def result_for(name: str) -> dict:
    return run_with(scenario_params(name))


def active_result() -> dict:
    """Hasil skenario terpilih (dipakai H01-H05, H07)."""
    return result_for(st.session_state.selected_scenario)


def baseline_result() -> dict:
    return result_for("Baseline")


def set_workflow(wf: dict):
    st.session_state.workflow = wf
    if wf["status"] == ap.APPROVED and wf.get("kpi"):
        st.session_state.approved_kpi = copy.deepcopy(wf["kpi"])


def go_to(page: str):
    st.session_state.nav = page


def is_view_only(page: str, role: str) -> bool:
    return (page, role) in VIEW_ONLY


PLAN_START = cfg.PLAN_START
