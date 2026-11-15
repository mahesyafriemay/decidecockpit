"""H01 — Overview & Early Warning (PPC, Supply Planner, Leader Produksi)."""
import pandas as pd
import streamlit as st

from engine import approval_engine as ap
from utils import state
from utils.helpers import fmt_dt, fmt_int
from utils.styles import (W, AMBER, GREEN, NAVY, ORANGE, RED, TEAL, alert_row, badge, kpi_card, page_header,
                          section, style_table)


def render():
    page_header("H01", "Overview & Early Warning",
                "Ringkasan kondisi stok, material, dan usulan jadwal siklus perencanaan ini.",
                "PPC, Supply Planner, Leader Produksi")
    res = state.active_result()
    kpi, buf, sch, mat, feas = res["kpi"], res["buffer"], res["schedule"], res["material"], res["feasibility"]
    wf = st.session_state.workflow

    issues = state.get_data_issues()
    if issues:
        st.error("Data issue terdeteksi — perbaiki data sumber sebelum perhitungan:\n\n- " + "\n- ".join(issues))
    else:
        st.caption(f"✅ Data lengkap & valid · 12 SKU · skenario aktif **{st.session_state.selected_scenario}**")

    # KPI cards ----------------------------------------------------------------
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("SKU Risk of Stockout", kpi["risk_skus"], f"NIP ≤ ROP · {kpi['watch_skus']} SKU Watch", RED)
    with c2:
        kpi_card("SKU Overstock", kpi["overstock_skus"], "NIP > Max Level", AMBER)
    with c3:
        kpi_card("Order Berpotensi Delay", kpi["delayed_orders"] + kpi["hold"],
                 f"{kpi['delayed_orders']} ETA > target · {kpi['hold']} HOLD", ORANGE)
    with c4:
        kpi_card("Schedule Revision", wf["revisions"], f"Status: {wf['status'].replace('_', ' ')}", NAVY)

    left, right = st.columns([1.35, 1])

    # Early warning ------------------------------------------------------------
    with left:
        section("Early Warning — Status Buffer SKU")
        counts = buf["Status"].value_counts()
        st.markdown(" ".join(f"{badge(s)} <b>{counts.get(s, 0)}</b> SKU &nbsp;" for s in ("Risk", "Watch", "Normal")),
                    unsafe_allow_html=True)
        view = buf.sort_values(["Status", "Days_of_Cover"], key=lambda s: s.map({"Risk": 0, "Watch": 1, "Normal": 2})
                               if s.name == "Status" else s)
        view = view[["SKU_ID", "Nama_Produk", "Lifecycle", "NIP", "ROP", "Days_of_Cover", "Status"]]
        st.dataframe(
            style_table(view, ["Status"], {"NIP": fmt_int, "ROP": fmt_int, "Days_of_Cover": "{:.1f}"}),
            hide_index=True, **W, height=300,
            column_config={"Nama_Produk": "Nama Produk", "Days_of_Cover": "Days of Cover"},
        )

    # Material alert -----------------------------------------------------------
    with right:
        section("Material Alert")
        cnt = mat["Alert"].value_counts()
        st.markdown(" ".join(f"{badge(a)} <b>{cnt.get(a, 0)}</b>" for a in
                             ("Material Shortage", "Supplier ETA Risk", "Material Ready")), unsafe_allow_html=True)
        st.write("")
        hold = feas[feas["Status"] == "HOLD"] if not feas.empty else pd.DataFrame()
        for _, h in hold.iterrows():
            alert_row(f"HOLD · {h['SKU_ID']} ({h['Priority_Class']})", h["Reason"], RED)
        for _, m in mat[mat["Alert"] == "Supplier ETA Risk"].iterrows():
            eta = m["Supplier_ETA"].strftime("%d %b") if pd.notna(m["Supplier_ETA"]) else "-"
            alert_row(f"Supplier ETA Risk · {m['Material_Name']}",
                      f"Incoming {fmt_int(m['Incoming_Qty'])} {m['UoM']} ETA {eta}, konfirmasi supplier: "
                      f"{m['Supplier_Confirmed']}", AMBER)
        for fb in st.session_state.material_feedback[-3:]:
            alert_row(f"Feedback Supply Planner · {fb['material']}", fb["note"], AMBER)
        ready = int(cnt.get("Material Ready", 0))
        alert_row(f"Material Ready · {ready} item", "Stok + pasokan siap mencukupi kebutuhan rencana.", TEAL)

    # Proposed schedule summary -----------------------------------------------
    section("Proposed Schedule Summary — Top Prioritas")
    if sch.empty:
        st.info("Tidak ada order LAYAK untuk dijadwalkan pada skenario ini.")
    else:
        top = sch.head(5).copy()
        top["Start"] = top["Start_Time"].map(fmt_dt)
        top["ETA NDC"] = top["ETA_NDC"].map(fmt_dt)
        top["Status"] = top["Late"].map({True: "Late", False: "On time"})
        top = top[["Sequence", "SKU_ID", "Nama_Produk", "Priority_Class", "Quantity", "Start", "ETA NDC", "Status"]]
        st.dataframe(style_table(top, ["Priority_Class", "Status"], {"Quantity": fmt_int}),
                     hide_index=True, **W,
                     column_config={"Nama_Produk": "Nama Produk", "Priority_Class": "Kelas"})
    color = {ap.APPROVED: GREEN, ap.RELEASED: GREEN, ap.MATERIAL_REJECTED: RED,
             ap.REVISION_REQUESTED: RED}.get(wf["status"], NAVY)
    st.markdown(f"Status approval: {badge(ap.STATUS_LABEL[wf['status']], color)}", unsafe_allow_html=True)
