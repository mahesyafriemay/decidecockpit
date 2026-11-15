"""H02 — Demand & Buffer Monitoring (PPC utama; Leader Produksi & Supply Planner lihat)."""
import altair as alt
import pandas as pd
import streamlit as st

from engine import config as cfg
from utils import state
from utils.helpers import fmt_dec, fmt_int
from utils.styles import W, NAVY, ORANGE, TEAL, page_header, section, style_table


def render():
    page_header("H02", "Demand & Buffer Monitoring",
                "Baseline demand per lifecycle, variabilitas, dampak campaign, ROP/Max Level, NIP, dan qty rekomendasi.",
                "PPC (utama), Leader Produksi (lihat)")
    if state.is_view_only("Demand & Buffer", st.session_state.role):
        st.caption("👁 Mode lihat — perubahan parameter hanya oleh PPC melalui H06 What-if.")

    res = state.active_result()
    buf = res["buffer"].copy()
    data = state.get_data()

    # Filter ------------------------------------------------------------------
    f1, f2, f3 = st.columns(3)
    kat = f1.multiselect("Kategori", sorted(buf["Kategori"].unique()), default=sorted(buf["Kategori"].unique()))
    life = f2.multiselect("Lifecycle", ["Matang", "Growing", "Baru"], default=["Matang", "Growing", "Baru"])
    stat = f3.multiselect("Status", ["Normal", "Watch", "Risk"], default=["Normal", "Watch", "Risk"])
    view = buf[buf["Kategori"].isin(kat) & buf["Lifecycle"].isin(life) & buf["Status"].isin(stat)]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("SKU ditampilkan", len(view))
    m2.metric("Perlu produksi (NIP ≤ ROP)", int(view["Need_Production"].sum()))
    m3.metric("Total qty rekomendasi", fmt_int(view["Recommended_Qty"].sum()))
    m4.metric("Rata-rata Days of Cover", fmt_dec(view["Days_of_Cover"].mean() if len(view) else 0, 1))

    # Tabel -------------------------------------------------------------------
    section("Buffer / ROP per SKU")
    tbl = view.assign(Variability=view["Sigma"].map(fmt_int) + " (CV " + (view["CV"] * 100).round(0).astype(int).astype(str) + "%)")
    tbl = tbl[["SKU_ID", "Nama_Produk", "Lifecycle", "Baseline_B", "Variability", "Campaign_Add_C", "Lead_Time_Total",
               "NIP", "ROP", "Max_Level", "Days_of_Cover", "Recommended_Qty", "Status"]]
    num = {c: fmt_int for c in ("Baseline_B", "Campaign_Add_C", "NIP", "ROP", "Max_Level", "Recommended_Qty")}
    num["Days_of_Cover"] = "{:.1f}"
    st.dataframe(
        style_table(tbl, ["Status"], num), hide_index=True, **W,
        column_config={
            "SKU_ID": "SKU_ID", "Nama_Produk": "Nama Produk", "Baseline_B": "Baseline Demand (B/mgg)",
            "Variability": "Demand Variability (σ)", "Campaign_Add_C": "Campaign Impact (C)",
            "Lead_Time_Total": "Lead Time (hari)", "Max_Level": "Max Level", "Days_of_Cover": "Days of Cover",
            "Recommended_Qty": "Recommended Production Qty",
        },
    )

    # Chart NIP vs ROP --------------------------------------------------------
    section("NIP vs ROP per SKU")
    if len(view):
        long = view.melt(id_vars=["SKU_ID", "Status"], value_vars=["NIP", "ROP"], var_name="Metric", value_name="Unit")
        bars = alt.Chart(long).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
            x=alt.X("SKU_ID:N", title=None, axis=alt.Axis(labelAngle=0)),
            xOffset=alt.XOffset("Metric:N", sort=["NIP", "ROP"]),
            y=alt.Y("Unit:Q", title="Unit", axis=alt.Axis(format=",.0f")),
            color=alt.Color("Metric:N", scale=alt.Scale(domain=["NIP", "ROP"], range=[TEAL, ORANGE]),
                            legend=alt.Legend(orient="top", title=None)),
            tooltip=["SKU_ID", "Metric", alt.Tooltip("Unit:Q", format=",.0f"), "Status"],
        )
        maxl = alt.Chart(view).mark_tick(color=NAVY, thickness=2, size=26).encode(
            x="SKU_ID:N", y="Max_Level:Q", tooltip=[alt.Tooltip("Max_Level:Q", format=",.0f", title="Max Level")])
        st.altair_chart((bars + maxl).properties(height=320), **W)
        st.caption("Batang teal = NIP, oranye = ROP, garis navy = Max Level. SKU dengan NIP ≤ ROP masuk antrean produksi.")

    # Detail perhitungan ------------------------------------------------------
    section("Detail Perhitungan per SKU")
    sid = st.selectbox("Pilih SKU", buf["SKU_ID"], format_func=lambda s: f"{s} — {buf.set_index('SKU_ID').loc[s, 'Nama_Produk']}")
    r = buf.set_index("SKU_ID").loc[sid]
    c1, c2 = st.columns([1, 1.2])
    with c1:
        steps = pd.DataFrame([
            ("Baseline B", f"{fmt_int(r['Baseline_B'])} unit/mgg", r["Baseline_Method"]),
            ("σ", fmt_int(r["Sigma"]), f"max(std, CV floor {cfg.CV_FLOOR[r['Lifecycle']]:.0%} × B)"),
            ("P (hari)", r["P_Days"], f"LT total {r['Lead_Time_Total']} + review {cfg.REVIEW_DAYS}"),
            ("Campaign C", fmt_int(r["Campaign_Add_C"]), r["Campaign_Detail"]),
            ("Safety Stock", fmt_int(r["Safety_Stock"]), f"Z {r['Z']} × σ × √(P/7)"),
            ("ROP", fmt_int(r["ROP"]), "B × P/7 + C + SS"),
            ("Max Level", fmt_int(r["Max_Level"]), f"ROP + B × {cfg.CYCLE_COVER_WEEKS} mgg"),
            ("NIP", fmt_int(r["NIP"]), f"{fmt_int(r['Stock_OnHand'])} + {fmt_int(r['Stock_WIP'])} − {fmt_int(r['Order_Committed'])}"),
            ("Days of Cover", fmt_dec(r["Days_of_Cover"], 1), "NIP / [(B×P/7 + C)/P]"),
            ("Rekomendasi", fmt_int(r["Recommended_Qty"]), f"Max − NIP, dibulatkan ke batch {fmt_int(r['Batch_Size'])}"
             if r["Need_Production"] else "NIP > ROP → 0"),
        ], columns=["Komponen", "Nilai", "Keterangan"])
        st.dataframe(steps.astype(str), hide_index=True, **W)
    with c2:
        hist = data["weekly_demand"][data["weekly_demand"]["SKU_ID"] == sid]
        ch = alt.Chart(hist).mark_line(point=True, color=NAVY).encode(
            x=alt.X("Week_Start:T", title=None), y=alt.Y("Demand_Units:Q", title="Demand / minggu"),
            tooltip=["Week_Start:T", alt.Tooltip("Demand_Units:Q", format=",.0f"), "Campaign_ID"])
        camp = alt.Chart(hist[hist["Is_Campaign"] == 1]).mark_point(color=ORANGE, size=90, filled=True).encode(
            x="Week_Start:T", y="Demand_Units:Q", tooltip=["Campaign_ID"])
        rule = alt.Chart(pd.DataFrame({"B": [r["Baseline_B"]]})).mark_rule(color=TEAL, strokeDash=[5, 4]).encode(y="B:Q")
        st.altair_chart((ch + camp + rule).properties(height=280, title="Histori demand mingguan (titik oranye = minggu campaign)"),
                        **W)
