"""H06 — What-if & Replanning (PPC, Leader Produksi)."""
import altair as alt
import pandas as pd
import streamlit as st

from engine import approval_engine as ap
from engine.scenario_engine import compare_kpis, default_scenario_params
from utils import state
from utils.helpers import fmt_dec, fmt_int, fmt_rp
from utils.styles import W, NAVY, ORANGE, page_header, section, style_table


def _fmt_kpi(key, v):
    if v is None:
        return "-"
    if key == "inventory_value":
        return fmt_rp(v)
    if key in ("total_delay_days", "line_hours"):
        return fmt_dec(v, 1)
    return fmt_int(v)


def _params_table(p):
    return pd.DataFrame([
        ("Demand multiplier", f"× {p['demand_multiplier']:.2f}"),
        ("Campaign uplift multiplier", f"× {p['campaign_uplift_multiplier']:.2f}"),
        ("Material availability", f"{p['material_availability_pct']:.0f}%"),
        ("Supplier ETA shift", f"{p['supplier_eta_shift_days']:+d} hari"),
        ("Line capacity", f"{p['line_capacity_pct']:.0f}%"),
        ("Override qty produksi", ", ".join(f"{k}: {fmt_int(v)}" for k, v in p["qty_override"].items()) or "-"),
    ], columns=["Parameter", "Nilai"])


def render():
    page_header("H06", "What-if & Replanning",
                "Ubah parameter, hitung ulang feasibility, sequence, ETA, dan risiko; bandingkan Baseline vs Scenario.",
                "PPC, Leader Produksi")
    role = st.session_state.role
    base = state.baseline_result()
    ss = st.session_state

    left, right = st.columns([1, 1.25])
    with left:
        section("Baseline Scenario")
        st.dataframe(_params_table(ss.params_baseline), hide_index=True, **W)
        st.caption("Baseline = data aktual snapshot tanpa perubahan parameter.")

    with right:
        section("Alternative Scenario — Editor")
        p = ss.params_alt
        with st.form("scenario_form"):
            c1, c2 = st.columns(2)
            dm = c1.slider("Demand multiplier", 0.5, 2.0, float(p["demand_multiplier"]), 0.05)
            cu = c2.slider("Campaign uplift multiplier", 0.0, 2.0, float(p["campaign_uplift_multiplier"]), 0.1,
                           help="1,0 = uplift sesuai kalender; 0 = campaign diabaikan")
            ma = c1.slider("Material availability (%)", 0, 150, int(p["material_availability_pct"]), 5)
            se = c2.slider("Supplier ETA shift (hari)", -14, 14, int(p["supplier_eta_shift_days"]),
                           help="Negatif = supplier mengirim lebih cepat; positif = terlambat")
            lc = c1.slider("Line capacity (%)", 10, 150, int(p["line_capacity_pct"]), 5)
            st.markdown("**Production quantity** (override per SKU di antrean; kosong/0 = pakai rekomendasi engine)")
            elig = base["priority"][["SKU_ID", "Nama_Produk", "Recommended_Qty"]].copy()
            elig["Qty_Scenario"] = elig["SKU_ID"].map(p["qty_override"]).fillna(0).astype(int)
            edited = st.data_editor(
                elig, hide_index=True, **W, key="qty_editor",
                disabled=["SKU_ID", "Nama_Produk", "Recommended_Qty"],
                column_config={"Recommended_Qty": st.column_config.NumberColumn("Rekomendasi", format="%d"),
                               "Qty_Scenario": st.column_config.NumberColumn("Qty skenario", min_value=0, step=1000,
                                                                             format="%d")})
            b1, b2 = st.columns(2)
            run = b1.form_submit_button("▶ Run Scenario", type="primary", **W)
            reset = b2.form_submit_button("Reset ke baseline", **W)
        if run:
            override = {r.SKU_ID: int(r.Qty_Scenario) for r in edited.itertuples() if r.Qty_Scenario and r.Qty_Scenario > 0}
            ss.params_alt = {**default_scenario_params(), "demand_multiplier": dm, "campaign_uplift_multiplier": cu,
                             "material_availability_pct": float(ma), "supplier_eta_shift_days": int(se),
                             "line_capacity_pct": float(lc), "qty_override": override}
            ss.alt_ran = True
            st.rerun()
        if reset:
            ss.params_alt = default_scenario_params()
            ss.alt_ran = False
            if ss.selected_scenario == "Alternative":
                ss.selected_scenario = "Baseline"
            st.rerun()

    if not ss.alt_ran:
        st.info("Atur parameter lalu klik **Run Scenario** untuk menghitung ulang dan membandingkan dengan baseline.")
        return

    alt_res = state.result_for("Alternative")

    # Perbandingan KPI ------------------------------------------------------
    section("Impact Analysis — Baseline vs Scenario")
    cmp = compare_kpis(base["kpi"], alt_res["kpi"], ("Baseline", "Scenario"))
    disp = cmp.copy()
    disp["Baseline"] = [_fmt_kpi(k, v) for k, v in zip(cmp["key"], cmp["Baseline"])]
    disp["Scenario"] = [_fmt_kpi(k, v) for k, v in zip(cmp["key"], cmp["Scenario"])]
    disp["Selisih"] = [("+" if d > 0 else "") + _fmt_kpi(k, d) for k, d in zip(cmp["key"], cmp["Selisih"])]
    disp = disp.drop(columns="key")

    def _impact(v):
        return {"Lebih baik": "background-color:#DDF3EE;color:#0B6B5C;font-weight:700",
                "Lebih buruk": "background-color:#FBE3E3;color:#9B2323;font-weight:700"}.get(v, "")
    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.dataframe(disp.style.map(_impact, subset=["Dampak"]), hide_index=True, **W)
    with c2:
        keys = ["stockout_risk", "overstock_risk", "delayed_orders", "hold", "layak"]
        long = cmp[cmp["key"].isin(keys)].melt(id_vars=["KPI"], value_vars=["Baseline", "Scenario"],
                                                var_name="Skenario", value_name="Nilai")
        ch = alt.Chart(long).mark_bar(cornerRadiusEnd=3).encode(
            y=alt.Y("KPI:N", title=None), yOffset="Skenario:N", x=alt.X("Nilai:Q", title=None),
            color=alt.Color("Skenario:N", scale=alt.Scale(range=[NAVY, ORANGE]), legend=alt.Legend(orient="top", title=None)),
            tooltip=["KPI", "Skenario", "Nilai"]).properties(height=300)
        st.altair_chart(ch, **W)

    # Perubahan rekomendasi & status -----------------------------------------
    section("Perubahan Rekomendasi per SKU")
    b = base["buffer"][["SKU_ID", "ROP", "Recommended_Qty", "Status"]]
    a = alt_res["buffer"][["SKU_ID", "ROP", "Recommended_Qty", "Status"]]
    m = b.merge(a, on="SKU_ID", suffixes=(" Baseline", " Scenario"))
    fb = base["feasibility"][["SKU_ID", "Status"]].rename(columns={"Status": "Gate Baseline"}) if not base["feasibility"].empty else pd.DataFrame(columns=["SKU_ID", "Gate Baseline"])
    fa = alt_res["feasibility"][["SKU_ID", "Status"]].rename(columns={"Status": "Gate Scenario"}) if not alt_res["feasibility"].empty else pd.DataFrame(columns=["SKU_ID", "Gate Scenario"])
    m = m.merge(fb, on="SKU_ID", how="left").merge(fa, on="SKU_ID", how="left").fillna("-")
    sb = base["schedule"][["SKU_ID", "Sequence"]].rename(columns={"Sequence": "Seq Baseline"}) if not base["schedule"].empty else pd.DataFrame(columns=["SKU_ID", "Seq Baseline"])
    sa = alt_res["schedule"][["SKU_ID", "Sequence"]].rename(columns={"Sequence": "Seq Scenario"}) if not alt_res["schedule"].empty else pd.DataFrame(columns=["SKU_ID", "Seq Scenario"])
    m = m.merge(sb, on="SKU_ID", how="left").merge(sa, on="SKU_ID", how="left")
    for col in ("Seq Baseline", "Seq Scenario"):
        m[col] = m[col].map(lambda v: "-" if pd.isna(v) else str(int(v)))
    st.dataframe(style_table(m, ["Status Baseline", "Status Scenario", "Gate Baseline", "Gate Scenario"],
                             {"ROP Baseline": fmt_int, "ROP Scenario": fmt_int, "Recommended_Qty Baseline": fmt_int,
                              "Recommended_Qty Scenario": fmt_int}),
                 hide_index=True, **W)

    # Pilih skenario --------------------------------------------------------
    section("Selected Scenario")
    choice = st.radio("Skenario yang dipakai sebagai proposed schedule", ["Baseline", "Alternative"],
                      index=["Baseline", "Alternative"].index(ss.selected_scenario), horizontal=True)
    can_use = role == state.PPC
    if st.button("✔ Use Selected Scenario", type="primary", disabled=not can_use):
        ss.selected_scenario = choice
        msg = f"Skenario {choice} dipakai untuk H01–H05 dan proposed schedule di H07."
        if ss.workflow["status"] not in (ap.DRAFT, ap.MATERIAL_REJECTED, ap.REVISION_REQUESTED):
            msg += " Jadwal yang sudah disubmit tetap berlaku — submit ulang di H07 bila perlu."
        ss.flash = msg
        st.rerun()
    if not can_use:
        st.caption("Leader Produksi dapat mensimulasikan skenario; penetapan skenario terpilih dilakukan PPC.")
    st.caption(f"Skenario aktif saat ini: **{ss.selected_scenario}**")
