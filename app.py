from __future__ import annotations

import time
from datetime import datetime

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


def format_run_label(run: pd.Series) -> str:
    run_at = datetime.fromisoformat(run["run_at"]).strftime("%Y-%m-%d %H:%M:%S")
    return f"{run_at} | Run #{int(run['run_id'])} | {int(run['stock_count'])} stocks"


def show_deep_analysis(repo: StockRepository) -> None:
    row = st.session_state.get("detail_row")
    if not row:
        st.session_state["view"] = "home"
        st.rerun()

    top_left, top_right = st.columns([1, 5])
    with top_left:
        if st.button("← Back", use_container_width=True):
            st.session_state["view"] = "home"
            st.rerun()

    with top_right:
        st.title(f"Deep Analysis: {row['Stock']} - {row['Name']}")
        st.markdown(
            f"**Recommendation:** `{row['Recommendation']}` | **Score:** `{row['Score']}` | **Confidence:** `{row['Confidence']}`"
        )

    notes = str(row["Notes"]).split(" | ")
    st.subheader("Reasoning")
    for note in notes:
        st.write(f"- {note}")

    tcol, fcol = st.columns(2)
    with tcol:
        st.subheader("Technical Snapshot")
        st.json(row.get("technical", {}))
    with fcol:
        st.subheader("Fundamental Snapshot")
        st.json(row.get("fundamentals", {}))

    history = repo.get_stock_history(row["Stock"])
    if not history.empty:
        st.subheader("Price Trend (1Y cached history)")
        chart = history[["Date", "Close"]].set_index("Date")
        st.line_chart(chart)


def main() -> None:
    st.title("Personal Stock Advisor (NSE 500 Analyzer)")
    st.caption("Conservative rule-based advisor using technical + fundamental signals.")

    repo, advisor = init_app()

    if "view" not in st.session_state:
        st.session_state["view"] = "home"

    if st.session_state["view"] == "detail":
        show_deep_analysis(repo)
        return

    sectors = repo.get_all_sectors()

    col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
    with col1:
        selected_sectors = st.multiselect("Sector", options=sectors, default=[])
    with col2:
        selected_cap = st.selectbox("Market Cap", options=["All", "Large", "Medium", "Small"], index=0)
    with col3:
        only_buy = st.checkbox("Only BUY", value=False)
    with col4:
        run_clicked = st.button("Analyze", type="primary", use_container_width=True)

    universe = repo.get_stocks(sectors=selected_sectors, cap=selected_cap)
    st.caption(f"Stocks matching current filters: **{len(universe)}**")

    runs_df = repo.list_analysis_runs(limit=100)
    if not runs_df.empty:
        run_options = runs_df.to_dict("records")
        selected_run = st.selectbox(
            "Load Previous Analysis",
            options=run_options,
            format_func=lambda x: format_run_label(pd.Series(x)),
            index=0,
        )
        if st.button("Load Selected Run"):
            loaded = repo.load_analysis_run(int(selected_run["run_id"]))
            if not loaded.empty:
                st.session_state["analysis_df"] = loaded.rename(
                    columns={
                        "symbol": "Stock",
                        "name": "Name",
                        "sector": "Sector",
                        "cap_category": "Cap",
                        "score": "Score",
                        "recommendation": "Recommendation",
                        "confidence": "Confidence",
                        "notes": "Notes",
                    }
                )
                st.success("Loaded previous analysis run.")

    if run_clicked:
        if universe.empty:
            st.warning("No stocks found for selected filters.")
            return

        with st.spinner("Running conservative analysis..."):
            result_df, run_id = advisor.analyze_universe(universe)

        if result_df.empty:
            st.error("No analyzable stocks. Data fetch may have failed for all selected symbols.")
            return

        st.session_state["analysis_df"] = result_df
        st.session_state["analysis_run_id"] = run_id

    if "analysis_df" not in st.session_state:
        st.info("Select filters and click Analyze.")
        return

    show_df = st.session_state["analysis_df"].copy()
    if only_buy:
        show_df = show_df[show_df["Recommendation"] == "BUY"]

    if show_df.empty:
        st.warning("No records after applying current filters.")
        return

    display_cols = [
        "Stock",
        "Name",
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

    st.caption("Tip: Double-click the same row quickly to open Deep Analysis.")
    event = st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    if event and event.selection and event.selection.rows:
        idx = event.selection.rows[0]
        row = show_df.iloc[idx].to_dict()
        symbol = row["Stock"]
        now = time.time()
        last_symbol = st.session_state.get("last_clicked_symbol")
        last_time = st.session_state.get("last_clicked_time", 0.0)

        if symbol == last_symbol and (now - last_time) < 1.2:
            st.session_state["detail_row"] = row
            st.session_state["view"] = "detail"
            st.rerun()

        st.session_state["last_clicked_symbol"] = symbol
        st.session_state["last_clicked_time"] = now

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


if __name__ == "__main__":
    main()
