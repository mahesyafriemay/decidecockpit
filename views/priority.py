"""H03 — Production Priority Ranking (PPC, Leader Produksi)."""
import altair as alt
import pandas as pd
import streamlit as st

from engine import config as cfg
from engine.priority_engine import criteria_weights_from_matrix
from utils import state
from utils.helpers import fmt_dec, fmt_int
from utils.styles import W, CLASS_SCALE, badge, page_header, section, style_table


def render():
    page_header("H03", "Production Priority Ranking",
                "AHP scoring 4 kriteria untuk SKU dengan NIP ≤ ROP, lalu klasifikasi P1/P2/P3 berbasis Critical Ratio.",
                "PPC, Leader Produksi")
    res = state.active_result()
    pri = res["priority"]
    if pri.empty:
        st.success("Tidak ada SKU dengan NIP ≤ ROP — tidak ada rekomendasi produksi baru. Lanjut ke H08 Monitoring.")
        return

    # Kriteria & bobot ----------------------------------------------------------
    ahp = criteria_weights_from_matrix()
    c1, c2 = st.columns([1.3, 1])
    with c1:
        section("Kriteria & Bobot AHP")
        crit = pd.DataFrame({
            "Kode": list(cfg.AHP_WEIGHTS),
            "Kriteria": [cfg.AHP_CRITERIA_LABEL[k] for k in cfg.AHP_WEIGHTS],
            "Ukuran": ["Days of Cover ÷ P (makin kecil makin urgen)", "Order Committed",
                       "Tambahan demand campaign dalam horizon", "Margin/unit × qty rekomendasi"],
            "Bobot": [f"{w:.1%}" for w in cfg.AHP_WEIGHTS.values()],
        })
        st.dataframe(crit, hide_index=True, **W)
    with c2:
        section("Consistency Test")
        a, b, c = st.columns(3)
        a.metric("λ maks", fmt_dec(ahp["lambda_max"], 3))
        b.metric("CI", fmt_dec(ahp["CI"], 3))
        c.metric("CR", fmt_dec(ahp["CR"], 3))
        if ahp["CR"] < 0.1:
            st.success("CR < 0,1 → penilaian konsisten, bobot dapat digunakan.")
        else:
            st.error("CR ≥ 0,1 → matriks perbandingan perlu direvisi.")
        with st.expander("Matriks perbandingan kriteria"):
            mat = pd.DataFrame(cfg.AHP_PAIRWISE, index=list(cfg.AHP_WEIGHTS), columns=list(cfg.AHP_WEIGHTS))
            st.dataframe(mat.round(3), **W)

    # Ranking ---------------------------------------------------------------
    section("Ranking Prioritas Produksi")
    counts = pri["Priority_Class"].value_counts()
    st.markdown(" ".join(f"{badge(p)} <b>{counts.get(p, 0)}</b> SKU &nbsp;" for p in ("P1", "P2", "P3"))
                + f" &nbsp;·&nbsp; Median skor AHP SKU non-P1: <b>{fmt_dec(pri['Median_NonP1'].iloc[0], 3)}</b>",
                unsafe_allow_html=True)
    tbl = pri[["Rank", "SKU_ID", "Nama_Produk", "Days_of_Cover", "Order_Committed", "Campaign_Add_C",
               "Margin_Contribution", "AHP_Score", "Critical_Ratio", "Priority_Class"]].copy()
    tbl["Margin_Contribution"] = tbl["Margin_Contribution"] / 1e6
    st.dataframe(
        style_table(tbl, ["Priority_Class"], {
            "Days_of_Cover": "{:.1f}", "Order_Committed": fmt_int, "Campaign_Add_C": fmt_int,
            "Margin_Contribution": "{:,.0f}", "AHP_Score": "{:.3f}", "Critical_Ratio": "{:.2f}"}),
        hide_index=True, **W,
        column_config={"Rank": "Ranking", "Nama_Produk": "Nama Produk", "Days_of_Cover": "Days of Cover",
                       "Order_Committed": "Order Committed", "Campaign_Add_C": "Campaign Impact",
                       "Margin_Contribution": "Margin Contribution (Rp jt)", "AHP_Score": "AHP Score",
                       "Critical_Ratio": "Critical Ratio", "Priority_Class": "Priority Class"},
    )
    st.caption("P1 = Critical Ratio < 1 (stok habis sebelum produksi + QC selesai) · "
               "P2/P3 = CR ≥ 1, dipisah median skor AHP SKU non-P1.")

    c1, c2 = st.columns([1.2, 1])
    with c1:
        section("AHP Score per SKU")
        ch = alt.Chart(pri).mark_bar(cornerRadiusEnd=4).encode(
            y=alt.Y("SKU_ID:N", sort="-x", title=None),
            x=alt.X("AHP_Score:Q", title="AHP Score"),
            color=alt.Color("Priority_Class:N", scale=alt.Scale(**CLASS_SCALE), legend=alt.Legend(title="Kelas", orient="top")),
            tooltip=["SKU_ID", "Nama_Produk", alt.Tooltip("AHP_Score:Q", format=".3f"),
                     alt.Tooltip("Critical_Ratio:Q", format=".2f"), "Priority_Class"],
        ).properties(height=280)
        st.altair_chart(ch, **W)
    with c2:
        section("Alasan Prioritas")
        for _, r in pri.iterrows():
            st.markdown(f"{badge(r['Priority_Class'])} **{r['SKU_ID']}** — {r['Reason']}", unsafe_allow_html=True)

    with st.expander("Skor lokal per kriteria (hasil perbandingan berpasangan antar SKU)"):
        det = pri[["SKU_ID", "K1_Value", "K1_Score", "K2_Score", "K3_Score", "K4_Score", "AHP_Score"]]
        st.dataframe(det.style.format({"K1_Value": "{:.2f}", "K1_Score": "{:.3f}", "K2_Score": "{:.3f}",
                                       "K3_Score": "{:.3f}", "K4_Score": "{:.3f}", "AHP_Score": "{:.3f}"}),
                     hide_index=True, **W,
                     column_config={"K1_Value": "DoC ÷ P", "K1_Score": "K1 (51,9%)", "K2_Score": "K2 (20,1%)",
                                    "K3_Score": "K3 (20,1%)", "K4_Score": "K4 (7,9%)"})
