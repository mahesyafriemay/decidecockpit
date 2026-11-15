"""H04 — Feasibility Gate (PPC, Supply Planner)."""
from datetime import datetime

import pandas as pd
import streamlit as st

from engine import config as cfg
from utils import state
from utils.helpers import fmt_date, fmt_dec, fmt_int
from utils.styles import W, AMBER, RED, TEAL, alert_row, kpi_card, page_header, section, style_table


def render():
    page_header("H04", "Feasibility Gate",
                "MRP material (BOM × qty vs stok + pasokan siap) dan RCCP kapasitas line. Output: LAYAK atau HOLD.",
                "PPC, Supply Planner")
    res = state.active_result()
    feas, detail, mat = res["feasibility"], res["feasibility_detail"], res["material"]
    if feas.empty:
        st.info("Tidak ada SKU di antrean produksi.")
        return

    hrs_av = feas.attrs.get("hours_available", 0.0)
    hrs_left = feas.attrs.get("hours_left", 0.0)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Order LAYAK", int((feas["Status"] == "LAYAK").sum()), "Masuk sequencing", TEAL)
    with c2:
        kpi_card("Order HOLD", int((feas["Status"] == "HOLD").sum()), "Material / kapasitas", RED)
    with c3:
        kpi_card("Kapasitas Line", f"{fmt_dec(hrs_av - hrs_left, 1)} / {fmt_dec(hrs_av, 1)} jam",
                 "Terpakai / tersedia (16–20 Nov)", AMBER)
    with c4:
        kpi_card("Tanggal Butuh Material", fmt_date(pd.Timestamp(cfg.MATERIAL_NEED_DATE)),
                 "Pasokan siap jika ETA ≤ tanggal ini", TEAL)

    # Tabel gate ------------------------------------------------------------
    section("Hasil Feasibility Gate (urut prioritas P1 → P3, CR terkecil)")
    tbl = feas[["SKU_ID", "Priority_Class", "Recommended_Qty", "BOM_Requirement", "Available_Material",
                "Incoming_Supply", "Supplier_ETA", "Capacity_Availability", "Changeover_Requirement",
                "Material_Shortage", "Status"]]
    st.dataframe(
        style_table(tbl, ["Priority_Class", "Status"], {"Recommended_Qty": fmt_int}),
        hide_index=True, **W,
        column_config={"Priority_Class": "Kelas", "Recommended_Qty": "Recommended Production Qty",
                       "BOM_Requirement": st.column_config.TextColumn("BOM Material Requirement", width="large"),
                       "Available_Material": "Available Material", "Incoming_Supply": "Incoming Supply",
                       "Supplier_ETA": "Supplier ETA", "Capacity_Availability": "Capacity Availability",
                       "Changeover_Requirement": "Changeover Requirement",
                       "Material_Shortage": st.column_config.TextColumn("Material Shortage", width="medium")},
    )

    hold = feas[feas["Status"] == "HOLD"]
    if len(hold):
        section("Alasan HOLD")
        for _, h in hold.iterrows():
            alert_row(f"{h['SKU_ID']} · {h['Nama_Produk']} ({h['Priority_Class']})", h["Reason"], RED)
        st.caption("SKU HOLD tidak masuk sequencing. PPC dapat merevisi qty / skenario di H06, "
                   "Supply Planner mengklarifikasi pasokan.")

    # Detail per SKU ----------------------------------------------------------
    section("Detail Kebutuhan Material per SKU")
    sid = st.selectbox("SKU", feas["SKU_ID"],
                       format_func=lambda s: f"{s} — {feas.set_index('SKU_ID').loc[s, 'Status']}")
    d = detail[detail["SKU_ID"] == sid][["Material_Name", "UoM", "Qty_per_Unit", "Gross_Requirement",
                                         "Available_Stock", "Ready_Incoming", "Incoming_Not_Ready",
                                         "Supplier_ETA", "Net_Shortage"]].copy()
    d["Supplier_ETA"] = d["Supplier_ETA"].map(fmt_date)
    st.dataframe(d.style.format({c: fmt_int for c in ("Gross_Requirement", "Available_Stock", "Ready_Incoming",
                                                       "Incoming_Not_Ready", "Net_Shortage")}),
                 hide_index=True, **W,
                 column_config={"Material_Name": "Komponen", "Qty_per_Unit": "Per unit",
                                "Gross_Requirement": "Kebutuhan bruto", "Available_Stock": "Stok tersedia*",
                                "Ready_Incoming": "Pasokan siap*", "Incoming_Not_Ready": "Pasokan belum siap",
                                "Net_Shortage": "Net shortage"})
    st.caption("*Sisa setelah dialokasikan ke SKU berprioritas lebih tinggi. "
               "Net Shortage = max(0, Gross − Available − Ready Incoming).")

    # Material & supplier readiness ---------------------------------------------
    section("Material & Supplier Readiness")
    sup = state.get_data()["supplier"].set_index("Supplier_ID")["Supplier_Name"]
    m = mat.copy()
    m["Supplier"] = m["Supplier_ID"].map(sup)
    m["Supplier_ETA"] = m["Supplier_ETA"].map(fmt_date)
    m = m[["Material_Name", "UoM", "Stock_Available", "Incoming_Qty", "Supplier_ETA", "Supplier",
           "Supplier_Confirmed", "Gross_Requirement", "Shortage", "Alert"]]
    st.dataframe(style_table(m, ["Alert"], {c: fmt_int for c in ("Stock_Available", "Incoming_Qty",
                                                                  "Gross_Requirement", "Shortage")}),
                 hide_index=True, **W,
                 column_config={"Material_Name": "Material", "Stock_Available": "Stok", "Incoming_Qty": "Incoming",
                                "Supplier_ETA": "ETA Supplier", "Supplier_Confirmed": "Konfirmasi",
                                "Gross_Requirement": "Kebutuhan rencana"})

    # Feedback Supply Planner -------------------------------------------------
    if st.session_state.role in (state.SUPPLY, state.PPC):
        section("Feedback Material (Supply Planner)")
        if st.session_state.role != state.SUPPLY:
            st.caption("Hanya Supply Planner yang dapat mengirim feedback; PPC melihat feedback di bawah.")
        else:
            with st.form("material_feedback", clear_on_submit=True):
                c1, c2 = st.columns([1, 2])
                mname = c1.selectbox("Material", mat["Material_Name"])
                new_eta = c1.date_input("Update ETA supplier (opsional)", value=None)
                note = c2.text_area("Catatan kendala / kesiapan supplier",
                                    placeholder="Contoh: Supplier tube konfirmasi kirim parsial 15.000 set tanggal 18 Nov")
                if st.form_submit_button("Kirim feedback ke PPC", type="primary"):
                    if not note.strip():
                        st.error("Catatan wajib diisi.")
                    else:
                        st.session_state.material_feedback.append({
                            "time": datetime.now().strftime("%d %b %H:%M"), "material": mname,
                            "eta": str(new_eta) if new_eta else "-", "note": note.strip()})
                        st.success("Feedback terkirim — memicu indikator replanning di H08.")
        for fb in reversed(st.session_state.material_feedback):
            alert_row(f"{fb['time']} · {fb['material']} · ETA baru: {fb['eta']}", fb["note"], AMBER)
