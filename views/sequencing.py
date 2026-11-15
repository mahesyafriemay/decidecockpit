"""H05 — Sequencing & ETA (PPC, Leader Produksi)."""
import altair as alt
import pandas as pd
import streamlit as st

from engine import config as cfg
from utils import state
from utils.helpers import fmt_dec, fmt_dt, fmt_int
from utils.styles import W, CLASS_SCALE, NAVY, ORANGE, RED, TEAL, kpi_card, page_header, section, style_table


def render():
    page_header("H05", "Sequencing & ETA",
                "Urutan produksi satu line liquid (P1 → P2 → P3, CR terkecil, kelompok kategori) dan estimasi tiba di NDC.",
                "PPC, Leader Produksi")
    res = state.active_result()
    sch, feas = res["schedule"], res["feasibility"]
    p = res["params"]

    with st.expander("Parameter ETA engine", expanded=False):
        c = st.columns(5)
        c[0].metric("Line rate", f"{fmt_int(p['line_rate'])} unit/jam")
        c[1].metric("Setup", f"{fmt_dec(p['setup_hours'], 1)} jam")
        c[2].metric("Ganti kategori", f"+{fmt_dec(cfg.CATEGORY_CHANGEOVER_HOURS, 1)} jam")
        c[3].metric("QC", f"{cfg.QC_WORKING_DAYS} hari kerja")
        c[4].metric("Distribusi", f"{cfg.DISTRIBUTION_WORKING_DAYS} hari kerja")
        st.caption("Production Time = Qty ÷ Line Rate + Setup · ETA NDC = Finish Produksi + QC + Distribusi · "
                   "Target = Snapshot (09 Nov) + Days of Cover (perkiraan stok NDC habis). "
                   "Line mulai 16 Nov 07:00, 2 shift (16 jam), Rabu 18 Nov maintenance 4 jam.")

    if sch.empty:
        st.warning("Tidak ada order LAYAK. Kembali ke H04/H06 untuk revisi rencana.")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Order dijadwalkan", len(sch), f"{fmt_int(sch['Quantity'].sum())} unit", NAVY)
    with c2:
        kpi_card("Jam line", fmt_dec(sch["Production_Duration_Hours"].sum(), 1),
                 f"{int((sch['Changeover'] == 'Ganti kategori').sum())}× ganti kategori", ORANGE)
    with c3:
        kpi_card("Flag terlambat", int(sch["Late"].sum()), f"Total {fmt_dec(sch['Delay_Days'].sum(), 1)} hari", RED)
    with c4:
        kpi_card("ETA terakhir", fmt_dt(sch["ETA_NDC"].max()), "Tiba di NDC", TEAL)

    section("Production Sequence")
    tbl = sch.copy()
    for col in ("Start_Time", "Finish_Production", "Finish_QC", "ETA_NDC", "Target_Date"):
        tbl[col] = tbl[col].map(fmt_dt)
    tbl = tbl[["Sequence", "SKU_ID", "Nama_Produk", "Priority_Class", "AHP_Score", "Critical_Ratio", "Quantity",
               "Production_Duration_Hours", "Start_Time", "Finish_Production", "Finish_QC", "ETA_NDC",
               "Target_Date", "Status_Delay"]]
    st.dataframe(
        style_table(tbl, ["Priority_Class", "Status_Delay"], {
            "AHP_Score": "{:.3f}", "Critical_Ratio": "{:.2f}", "Quantity": fmt_int,
            "Production_Duration_Hours": "{:.1f} jam"}),
        hide_index=True, **W,
        column_config={"Nama_Produk": "Nama Produk", "Priority_Class": "Kelas", "AHP_Score": "AHP Score",
                       "Critical_Ratio": "Critical Ratio", "Production_Duration_Hours": "Production Duration",
                       "Start_Time": "Start Time", "Finish_Production": "Finish Production",
                       "Finish_QC": "Finish QC", "ETA_NDC": "ETA NDC", "Target_Date": "Target (stok habis)",
                       "Status_Delay": "Status Delay"},
    )

    section("Gantt — Line LQ-01")
    g = sch[["Sequence", "SKU_ID", "Priority_Class", "Start_Time", "Finish_Production", "Quantity", "Changeover"]].copy()
    g["Label"] = g["Sequence"].astype(str) + ". " + g["SKU_ID"]
    gantt = alt.Chart(g).mark_bar(cornerRadius=4, height=18).encode(
        x=alt.X("Start_Time:T", title=None, axis=alt.Axis(format="%a %d %b %H:%M")),
        x2="Finish_Production:T",
        y=alt.Y("Label:N", sort=list(g["Label"]), title=None),
        color=alt.Color("Priority_Class:N", scale=alt.Scale(**CLASS_SCALE), legend=alt.Legend(title="Kelas", orient="top")),
        tooltip=["SKU_ID", "Priority_Class", alt.Tooltip("Quantity:Q", format=",.0f"), "Changeover",
                 alt.Tooltip("Start_Time:T", format="%d %b %H:%M"), alt.Tooltip("Finish_Production:T", format="%d %b %H:%M")],
    ).properties(height=40 + 32 * len(g))
    st.altair_chart(gantt, **W)

    late = sch[sch["Late"]]
    if len(late):
        section("Order Terlambat")
        for _, r in late.iterrows():
            st.markdown(f"🚩 **{r['SKU_ID']}** — ETA {fmt_dt(r['ETA_NDC'])} melewati target {fmt_dt(r['Target_Date'])} "
                        f"(**{fmt_dec(r['Delay_Days'], 1)} hari**). Pertimbangkan alokasi stok DC lain atau "
                        f"percepatan QC.")

    hold = feas[feas["Status"] == "HOLD"] if not feas.empty else pd.DataFrame()
    if len(hold):
        st.info("Tidak masuk sequencing (HOLD): " + ", ".join(f"{r.SKU_ID} ({r.Priority_Class})" for r in hold.itertuples()))
    st.caption(f"Rule 3: SKU sekategori dimajukan bila selisih Critical Ratio ≤ {cfg.GROUPING_CR_TOLERANCE} "
               "dan tidak melompati kelas prioritas.")
