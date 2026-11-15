"""H08 — Performance Monitoring (PPC, Leader Produksi)."""
import altair as alt
import pandas as pd
import streamlit as st

from engine import approval_engine as ap
from engine import config as cfg
from engine.scenario_engine import no_production_kpis
from utils import state
from utils.helpers import fmt_dec, fmt_int, fmt_rp
from utils.styles import W, AMBER, GREEN, NAVY, ORANGE, RED, TEAL, alert_row, banner, kpi_card, page_header, section

MUTED_GREY = "#A9B4C6"


def _triggers(res, wf, data):
    p = res["params"]
    mat = res["material"]
    k = res["kpi"]
    buf = res["buffer"]
    last_week = data["weekly_demand"].sort_values("Week_Start").groupby("SKU_ID").tail(1).set_index("SKU_ID")["Demand_Units"]
    surge = [s for s, b in zip(buf["SKU_ID"], buf["Baseline_B"]) if s in last_week and last_week[s] > 1.25 * b]
    t = [
        ("Material berubah",
         bool(st.session_state.material_feedback) or p["material_availability_pct"] != 100 or (mat["Alert"] == "Material Shortage").any(),
         f"{int((mat['Alert'] == 'Material Shortage').sum())} material shortage · {len(st.session_state.material_feedback)} feedback Supply Planner"),
        ("Demand meningkat",
         p["demand_multiplier"] > 1 or p["campaign_uplift_multiplier"] > 1 or bool(surge),
         f"Multiplier ×{p['demand_multiplier']:.2f}; lonjakan minggu terakhir: {', '.join(surge) or 'tidak ada'}"),
        ("Supplier delay",
         p["supplier_eta_shift_days"] > 0 or (mat["Alert"] == "Supplier ETA Risk").any()
         or res["feasibility_detail"].get("Incoming_Not_Ready", pd.Series(dtype=float)).gt(0).any(),
         f"ETA shift {p['supplier_eta_shift_days']:+d} hari · {int((mat['Alert'] == 'Supplier ETA Risk').sum())} supplier ETA risk"),
        ("Kapasitas turun",
         p["line_capacity_pct"] < 100 or (not res["feasibility"].empty and (~res["feasibility"]["Capacity_OK"]).any()),
         f"Kapasitas line {p['line_capacity_pct']:.0f}%"),
        ("KPI melewati threshold",
         k["stockout_risk"] >= cfg.KPI_THRESHOLDS["stockout_risk"] or k["delayed_orders"] >= cfg.KPI_THRESHOLDS["delayed_orders"]
         or k["overstock_risk"] >= cfg.KPI_THRESHOLDS["overstock"],
         f"Stockout {k['stockout_risk']} (≥{cfg.KPI_THRESHOLDS['stockout_risk']}), delay {k['delayed_orders']} "
         f"(≥{cfg.KPI_THRESHOLDS['delayed_orders']}), overstock {k['overstock_risk']} (≥{cfg.KPI_THRESHOLDS['overstock']})"),
    ]
    return t


def render():
    page_header("H08", "Performance Monitoring",
                "Evaluasi stockout, overstock, delay, nilai inventori, dan biaya revisi; pemicu replanning.",
                "PPC, Leader Produksi")
    ss = st.session_state
    wf = ss.workflow
    res = state.active_result()
    base = state.baseline_result()
    approved = wf["status"] in (ap.APPROVED, ap.RELEASED) and ss.approved_kpi
    k = ss.approved_kpi if approved else res["kpi"]
    label = f"Approved Plan (v{wf['version']}, {wf['scenario']})" if approved else f"Rencana aktif ({ss.selected_scenario}, belum approved)"
    st.caption(f"KPI ditampilkan untuk: **{label}**")

    rev_cost = wf["revisions"] * cfg.REVISION_COST_PER_EVENT
    c = st.columns(6)
    with c[0]:
        kpi_card("Stockout Risk", k["stockout_risk"], "SKU terlambat / HOLD P1", RED)
    with c[1]:
        kpi_card("Overstock Risk", k["overstock_risk"], "Posisi > Max Level", AMBER)
    with c[2]:
        kpi_card("Delay", k["delayed_orders"], f"{fmt_dec(k['total_delay_days'], 1)} hari total", ORANGE)
    with c[3]:
        kpi_card("Inventory Value", fmt_rp(k["inventory_value"]), "NIP + produksi × COGS", NAVY)
    with c[4]:
        kpi_card("Revision Cost", fmt_rp(rev_cost), f"{fmt_rp(cfg.REVISION_COST_PER_EVENT)}/revisi (asumsi)", NAVY)
    with c[5]:
        kpi_card("Schedule Revisions", wf["revisions"], ap.STATUS_LABEL[wf["status"]].split(" — ")[0], TEAL)

    # Scenario comparison ----------------------------------------------------
    section("Scenario Comparison")
    none = no_production_kpis(base)
    cols = {"Tanpa rencana produksi": none, "Baseline Scenario": base["kpi"]}
    if approved:
        cols["Approved Plan"] = ss.approved_kpi
    elif ss.alt_ran:
        cols["Alternative Scenario"] = state.result_for("Alternative")["kpi"]
    metrics = [("Stockout count", "stockout_risk", fmt_int), ("Overstock count", "overstock_risk", fmt_int),
               ("Delayed orders", "delayed_orders", fmt_int), ("Inventory value", "inventory_value", fmt_rp)]
    rows = []
    for lbl, key, f in metrics:
        rows.append({"KPI": lbl, **{n: ("-" if d.get(key) is None else f(d[key])) for n, d in cols.items()}})
    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.dataframe(pd.DataFrame(rows), hide_index=True, **W)
        st.caption("'Tanpa rencana produksi' = seluruh SKU Risk dibiarkan tanpa replenishment (referensi as-is).")
    with c2:
        long = pd.DataFrame([{"Skenario": n, "KPI": lbl, "Nilai": d.get(key) or 0}
                             for n, d in cols.items() for lbl, key, _ in metrics[:3]])
        ch = alt.Chart(long).mark_bar(cornerRadiusEnd=3).encode(
            y=alt.Y("KPI:N", title=None), yOffset="Skenario:N", x=alt.X("Nilai:Q", title="Jumlah SKU / order"),
            color=alt.Color("Skenario:N", scale=alt.Scale(range=[MUTED_GREY, NAVY, ORANGE]),
                            legend=alt.Legend(orient="top", title=None)),
            tooltip=["Skenario", "KPI", "Nilai"]).properties(height=230)
        st.altair_chart(ch, **W)

    # Trigger replanning ------------------------------------------------------
    section("Trigger Replanning")
    trig = _triggers(res, wf, state.get_data())
    fired = [t for t in trig if t[1]]
    if fired:
        banner(f"PERLU REPLANNING — {len(fired)} pemicu aktif", RED)
    else:
        banner("Tidak perlu replanning — kondisi sesuai rencana", GREEN)
    for name, on, detail in trig:
        alert_row(("🔴 " if on else "🟢 ") + name, detail, RED if on else TEAL)
    if fired and ss.role == state.PPC:
        st.button("↻ Mulai replanning di H06 What-if", type="primary", on_click=state.go_to, args=("What-if",))

