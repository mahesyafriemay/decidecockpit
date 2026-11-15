"""H07 — Decision Review & Approval (PPC, Supply Planner, Leader Produksi)."""
import pandas as pd
import streamlit as st

from engine import approval_engine as ap
from utils import state
from utils.helpers import fmt_dt, fmt_int, fmt_rp
from utils.styles import W, AMBER, GREEN, NAVY, ORANGE, RED, alert_row, banner, page_header, section, stepper, style_table


def _plan_records(sch: pd.DataFrame) -> list:
    cols = ["Sequence", "SKU_ID", "Nama_Produk", "Priority_Class", "Quantity", "Start_Time", "Finish_Production",
            "ETA_NDC", "Target_Date", "Status_Delay"]
    recs = sch[cols].copy()
    for c in ("Start_Time", "Finish_Production", "ETA_NDC", "Target_Date"):
        recs[c] = recs[c].map(fmt_dt)
    return recs.to_dict("records")


def _steps(wf):
    s = wf["status"]
    ppc = ("done", "Submitted v%d" % wf["version"]) if s not in (ap.DRAFT,) else ("active", "Menunggu submit")
    if s in (ap.MATERIAL_REJECTED, ap.REVISION_REQUESTED):
        ppc = ("active", "Revisi & submit ulang")
    sup = {ap.SUBMITTED: ("active", "Menunggu konfirmasi"), ap.MATERIAL_REJECTED: ("blocked", "Reject — material")}.get(
        s, ("done", "Material confirmed") if s in (ap.MATERIAL_CONFIRMED, ap.APPROVED, ap.RELEASED, ap.REVISION_REQUESTED)
        else ("todo", "-"))
    lead = {ap.MATERIAL_CONFIRMED: ("active", "Menunggu review"), ap.REVISION_REQUESTED: ("blocked", "Revise"),
            ap.APPROVED: ("done", "Approved"), ap.RELEASED: ("done", "Approved")}.get(s, ("todo", "-"))
    rel = {ap.APPROVED: ("active", "Ready for SAP release"), ap.RELEASED: ("done", "Released (simulasi)")}.get(s, ("todo", "-"))
    return [("PPC — Submit schedule", ppc[1], ppc[0]), ("Supply Planner — Konfirmasi material", sup[1], sup[0]),
            ("Leader Produksi — Review", lead[1], lead[0]), ("PPC — Rilis ke SAP (simulasi)", rel[1], rel[0])]


def render():
    page_header("H07", "Decision Review & Approval",
                "PPC submit → Supply Planner konfirmasi material → Leader Produksi approve / revise → rilis (simulasi).",
                "PPC, Supply Planner, Leader Produksi")
    ss = st.session_state
    wf = ss.workflow
    role = ss.role
    res = state.active_result()

    color = {ap.APPROVED: GREEN, ap.RELEASED: GREEN, ap.MATERIAL_REJECTED: RED, ap.REVISION_REQUESTED: RED,
             ap.SUBMITTED: ORANGE, ap.MATERIAL_CONFIRMED: ORANGE}.get(wf["status"], NAVY)
    banner(ap.STATUS_LABEL[wf["status"]], color)
    stepper(_steps(wf))

    # Proposed schedule -------------------------------------------------------
    submitted = wf["plan"] is not None and wf["status"] != ap.DRAFT
    section("Proposed Schedule" + (f" — v{wf['version']} (skenario {wf['scenario']})" if submitted
                                    else f" — draft dari skenario {ss.selected_scenario}"))
    plan = pd.DataFrame(wf["plan"]) if submitted else (pd.DataFrame(_plan_records(res["schedule"]))
                                                       if not res["schedule"].empty else pd.DataFrame())
    if plan.empty:
        st.warning("Tidak ada order LAYAK pada skenario aktif. Revisi di H06 What-if.")
    else:
        st.dataframe(style_table(plan, ["Priority_Class", "Status_Delay"], {"Quantity": fmt_int}),
                     hide_index=True, **W,
                     column_config={"Nama_Produk": "Nama Produk", "Priority_Class": "Kelas",
                                    "Start_Time": "Start", "Finish_Production": "Finish Prod.",
                                    "ETA_NDC": "ETA NDC", "Target_Date": "Target", "Status_Delay": "Status Delay"})
    kpi = wf["kpi"] if submitted and wf["kpi"] else res["kpi"]
    c = st.columns(5)
    c[0].metric("Order", len(plan))
    c[1].metric("Total qty", fmt_int(plan["Quantity"].sum()) if len(plan) else 0)
    c[2].metric("Order HOLD (tidak dijadwalkan)", kpi["hold"])
    c[3].metric("Flag terlambat", kpi["delayed_orders"])
    c[4].metric("Nilai inventori", fmt_rp(kpi["inventory_value"]))

    # Feedback terakhir --------------------------------------------------------
    if wf["material_confirmation"] and wf["material_confirmation"]["decision"] == "Reject":
        mc = wf["material_confirmation"]
        alert_row("Supply Planner: Reject / Need Revision", f"{mc['reason']} — Constraint: {mc['constraint']}", RED)
    if wf["leader_decision"] and wf["leader_decision"]["decision"] == "Revise":
        alert_row("Leader Produksi: Revise", f"Revision reason: {wf['leader_decision']['reason']}", RED)

    # Panel aksi per role ----------------------------------------------------
    section(f"Aksi — {role}")
    try:
        if role == state.PPC:
            _ppc_panel(wf, res)
        elif role == state.SUPPLY:
            _supply_panel(wf, res)
        else:
            _leader_panel(wf)
    except ap.WorkflowError as e:
        st.error(str(e))

    # Decision summary & history ---------------------------------------------
    section("Decision Summary & Audit Trail")
    c1, c2, c3 = st.columns(3)
    mc, ld = wf["material_confirmation"], wf["leader_decision"]
    c1.markdown(f"**Material confirmation**  \n{mc['decision'] if mc else '—'}")
    c2.markdown(f"**Leader decision**  \n{ld['decision'] if ld else '—'}")
    c3.markdown(f"**Jumlah schedule revision**  \n{wf['revisions']}  ({fmt_rp(wf['revisions'] * 2_500_000)})")
    if wf["history"]:
        st.dataframe(pd.DataFrame(wf["history"])[::-1], hide_index=True, **W)
    else:
        st.caption("Belum ada aktivitas approval.")


def _ppc_panel(wf, res):
    ss = st.session_state
    s = wf["status"]
    if s in (ap.DRAFT, ap.MATERIAL_REJECTED, ap.REVISION_REQUESTED):
        if s != ap.DRAFT:
            st.info("Jadwal dikembalikan. Revisi parameter di **H06 What-if**, pilih skenario, lalu submit ulang.")
            st.button("Buka H06 What-if", on_click=state.go_to, args=("What-if",))
        note = st.text_input("Catatan untuk reviewer (opsional)")
        if st.button(f"📤 Submit proposed schedule (skenario {ss.selected_scenario})", type="primary",
                     disabled=res["schedule"].empty):
            new = ap.submit(wf, ss.selected_scenario, _plan_records(res["schedule"]), res["kpi"])
            if note:
                new["history"][-1]["note"] += f" | {note}"
            state.set_workflow(new)
            ss.flash = "Proposed schedule disubmit ke Supply Planner."
            st.rerun()
    elif s == ap.APPROVED:
        st.success("Jadwal APPROVED — Ready for SAP Release. Prototype tidak menulis ke SAP; rilis hanya disimulasikan.")
        if st.button("🚀 Rilis jadwal final (simulasi SAP)", type="primary"):
            state.set_workflow(ap.release(wf))
            ss.flash = "Jadwal dirilis (simulasi). Pantau hasil di H08."
            st.rerun()
    elif s == ap.RELEASED:
        st.success("Jadwal final telah dirilis (simulasi). Lanjut pantau di H08 Performance Monitoring.")
        if st.button("Mulai siklus perencanaan berikutnya"):
            state.set_workflow(ap.reset(wf))
            st.rerun()
    else:
        st.info("Menunggu keputusan Supply Planner / Leader Produksi. Ganti role di sidebar untuk mensimulasikan.")


def _supply_panel(wf, res):
    ss = st.session_state
    if wf["status"] != ap.SUBMITTED:
        st.info("Belum ada jadwal yang menunggu konfirmasi material." if wf["status"] == ap.DRAFT
                else "Konfirmasi material sudah diberikan / tidak diperlukan pada status ini.")
        return
    skus = [r["SKU_ID"] for r in wf["plan"]]
    det = res["feasibility_detail"]
    det = det[det["SKU_ID"].isin(skus)] if not det.empty else det
    if not det.empty:
        agg = det.groupby(["Material_Name", "UoM"], as_index=False)[["Gross_Requirement", "Net_Shortage"]].sum()
        st.markdown("**Kebutuhan material jadwal yang disubmit**")
        st.dataframe(agg.style.format({"Gross_Requirement": fmt_int, "Net_Shortage": fmt_int}),
                     hide_index=True, **W)
    risk = res["material"][res["material"]["Alert"] != "Material Ready"]
    for _, m in risk.iterrows():
        alert_row(f"{m['Alert']} · {m['Material_Name']}", f"Konfirmasi supplier: {m['Supplier_Confirmed']}", AMBER)

    decision = st.radio("Keputusan material", ["Confirm", "Reject / Need Revision"], horizontal=True)
    reason = st.text_area("Reason" + (" (wajib)" if decision != "Confirm" else " (opsional)"))
    constraint = ""
    if decision != "Confirm":
        constraint = st.text_input("Supplier ETA / material constraint (wajib)",
                                   placeholder="Contoh: Tube 20 ml baru tiba 23 Nov, parsial 15.000 set 18 Nov")
    if st.button("Kirim keputusan material", type="primary"):
        try:
            new = ap.supply_decision(wf, "Confirm" if decision == "Confirm" else "Reject", reason, constraint)
        except ap.WorkflowError as e:
            st.error(str(e))
            return
        state.set_workflow(new)
        ss.flash = "Material dikonfirmasi — diteruskan ke Leader Produksi." if decision == "Confirm" \
            else "Jadwal dikembalikan ke PPC untuk revisi."
        st.rerun()


def _leader_panel(wf):
    ss = st.session_state
    if wf["status"] != ap.MATERIAL_CONFIRMED:
        if wf["status"] == ap.SUBMITTED:
            st.warning("Approve belum tersedia: material belum dikonfirmasi Supply Planner.")
            st.button("Approve", disabled=True)
        else:
            st.info("Tidak ada jadwal yang menunggu review Leader.")
        return
    decision = st.radio("Keputusan Leader", ["Approve", "Revise"], horizontal=True)
    reason = st.text_area("Revision Reason (wajib)" if decision == "Revise" else "Catatan (opsional)")
    if st.button("Kirim keputusan", type="primary"):
        try:
            new = ap.leader_decision(wf, decision, reason)
        except ap.WorkflowError as e:
            st.error(str(e))
            return
        state.set_workflow(new)
        ss.flash = "APPROVED — Ready for SAP Release" if decision == "Approve" else "Revisi dikirim ke PPC."
        st.rerun()
