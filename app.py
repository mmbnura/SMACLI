from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from src.advisor_service import AdvisorService
from src.bootstrap import bootstrap_master_data
from src.repository import StockRepository

st.set_page_config(page_title="Personal Stock Advisor (NSE 500)", layout="wide")


@st.cache_resource
def init_app() -> tuple[StockRepository, AdvisorService]:
    bootstrap_master_data()
    repo = StockRepository()
    advisor = AdvisorService(repository=repo)
    return repo, advisor


def style_recommendation(val: str) -> str:
    color_map = {
        "BUY": "background-color: #2e7d32; color: white; font-weight: 700",
        "HOLD": "background-color: #f9a825; color: black; font-weight: 700",
        "AVOID": "background-color: #c62828; color: white; font-weight: 700",
    }
    return color_map.get(val, "")


def export_bytes(df: pd.DataFrame, kind: str) -> bytes:
    if kind == "csv":
        return df.to_csv(index=False).encode("utf-8")
    if kind == "excel":
        from io import BytesIO

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="analysis")
        return buffer.getvalue()
    raise ValueError("Unsupported export format")


def main() -> None:
    st.title("Personal Stock Advisor (NSE 500 Analyzer)")
    st.caption("Conservative rule-based advisor using technical + fundamental signals.")

    repo, advisor = init_app()

    sectors = repo.get_all_sectors()
    caps = repo.get_all_caps()

    col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
    with col1:
        selected_sectors = st.multiselect("Sector", options=sectors, default=[])
    with col2:
        selected_cap = st.selectbox("Market Cap", options=["All", *caps], index=0)
    with col3:
        only_buy = st.checkbox("Only BUY", value=False)
    with col4:
        run_clicked = st.button("Analyze", type="primary", use_container_width=True)

    if run_clicked:
        universe = repo.get_stocks(sectors=selected_sectors, cap=selected_cap)

        if universe.empty:
            st.warning("No stocks found for selected filters.")
            return

        with st.spinner("Running conservative analysis..."):
            result_df = advisor.analyze_universe(universe)

        if result_df.empty:
            st.error("No analyzable stocks. Data fetch may have failed for all selected symbols.")
            return

        if only_buy:
            result_df = result_df[result_df["Recommendation"] == "BUY"]

        st.session_state["analysis_df"] = result_df

    if "analysis_df" not in st.session_state:
        st.info("Select filters and click Analyze.")
        return

    show_df = st.session_state["analysis_df"].copy()
    if show_df.empty:
        st.warning("No records after applying current filters.")
        return

    display_cols = [
        "Stock",
        "Sector",
        "Cap",
        "Price",
        "Score",
        "Recommendation",
        "Confidence",
        "Notes",
    ]

    last_updated = repo.get_last_update_timestamp()
    if last_updated:
        st.caption(f"Last updated: {last_updated} UTC")

    styler = show_df[display_cols].style
    if hasattr(styler, "map"):
        styled = styler.map(style_recommendation, subset=["Recommendation"])
    else:
        styled = styler.applymap(style_recommendation, subset=["Recommendation"])

    event = st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    export_col1, export_col2 = st.columns(2)
    with export_col1:
        st.download_button(
            "Export CSV",
            data=export_bytes(show_df[display_cols], kind="csv"),
            file_name="nse500_analysis.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with export_col2:
        st.download_button(
            "Export Excel",
            data=export_bytes(show_df[display_cols], kind="excel"),
            file_name="nse500_analysis.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    if event and event.selection and event.selection.rows:
        idx = event.selection.rows[0]
        row = show_df.iloc[idx]
        st.subheader(f"Detailed Reasoning: {row['Stock']} ({row['Name']})")
        st.markdown(f"**Recommendation:** `{row['Recommendation']}` | **Score:** `{row['Score']}`")

        notes = row["Notes"].split(" | ")
        st.markdown("**Signal notes**")
        for note in notes:
            st.write(f"- {note}")

        tech = row["technical"]
        funda = row["fundamentals"]

        left, right = st.columns(2)
        with left:
            st.markdown("**Technical Snapshot**")
            st.json(tech)
        with right:
            st.markdown("**Fundamental Snapshot**")
            st.json(funda)


if __name__ == "__main__":
    main()
