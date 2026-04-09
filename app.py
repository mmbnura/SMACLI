from __future__ import annotations

import time
from datetime import datetime

import pandas as pd
import streamlit as st

from src.advisor_service import AdvisorService
from src.bootstrap import bootstrap_master_data
from src.repository import StockRepository

st.set_page_config(page_title="Personal Stock Advisor (NSE 500)", layout="wide")

# Application version
APP_VERSION = "0.5"

# Custom CSS for blueish theme and compact layout
st.markdown("""
<style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button, .stDownloadButton>button {
        background-color: #1f77b4 !important;
        color: white !important;
        border: none !important;
        border-radius: 4px !important;
        font-weight: 500 !important;
        transition: background-color 0.3s !important;
        height: 38px !important;
    }
    .stButton>button:hover, .stDownloadButton>button:hover {
        background-color: #1565c0 !important;
    }
    .stButton>button:disabled {
        background-color: #b0bec5 !important;
        color: #78909c !important;
    }
    .stRadio > div {
        background-color: #e3f2fd !important;
        padding: 8px !important;
        border-radius: 4px !important;
    }
    .stSelectbox, .stMultiselect {
        background-color: #f5f5f5 !important;
    }
    .stCheckbox > div > div {
        background-color: #e3f2fd !important;
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid #1f77b4 !important;
        border-radius: 4px !important;
    }
    .stCaption {
        color: #424242 !important;
    }
    .stSubheader {
        color: #1976d2 !important;
        font-weight: 600 !important;
    }
    .stTitle {
        color: #0d47a1 !important;
    }
</style>
""", unsafe_allow_html=True)


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
        if st.button("← Back", type="primary", use_container_width=True):
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

    # Index Selection - Compact Layout
    st.subheader("Select Index")
    index_row = st.columns([3, 1, 1])
    with index_row[0]:
        selected_index = st.radio(
            "Choose Index",
            options=["Nifty 500", "Nifty Microcap 250"],
            index=0,
            horizontal=True,
            label_visibility="collapsed"
        )
    
    with index_row[1]:
        if st.button("🔄 Refresh", type="primary", use_container_width=True, help="Repull index data from NSE server"):
            with st.spinner("Refreshing data from NSE server..."):
                st.cache_resource.clear()
                bootstrap_master_data(force_refresh=True)
                st.success("✅ Data refreshed successfully!")
                st.rerun()
    
    with index_row[2]:
        if st.button("↺ Reset", type="primary", use_container_width=True, help="Reset all filters to initial state"):
            st.session_state.clear()
            st.rerun()
    
    # Map display name to database filter
    index_filter = "nifty500" if selected_index == "Nifty 500" else "nifty_microcap250"
    
    st.caption(f"Analyzing stocks from **{selected_index}** index")
    st.divider()

    sectors = repo.get_all_sectors(index_type=index_filter)
    
    # Check if data is available for selected index
    stocks_available = repo.get_stocks(index_type=index_filter)
    if stocks_available.empty:
        st.warning(f"❌ No stocks found for **{selected_index}** index. Please ensure the data is available or manually add a CSV file at `data/nifty_microcap250_master.csv` for Nifty Microcap 250.")

    # Filters - Compact Layout
    filter_row = st.columns([3, 2, 1, 1])
    with filter_row[0]:
        selected_sectors = st.multiselect("Sector", options=sectors, default=[], label_visibility="collapsed")
    with filter_row[1]:
        selected_cap = st.selectbox("Market Cap", options=["All", "Large", "Medium", "Small"], index=0, label_visibility="collapsed")
    with filter_row[2]:
        only_buy = st.checkbox("Only BUY", value=False, label_visibility="collapsed")
    with filter_row[3]:
        run_clicked = st.button("Analyze", type="primary", use_container_width=True)

    universe = repo.get_stocks(sectors=selected_sectors, cap=selected_cap, index_type=index_filter)
    st.caption(f"Stocks matching current filters: **{len(universe)}**")

    runs_df = repo.list_analysis_runs(limit=100)
    # Previous Runs - Compact Layout
    if not runs_df.empty:
        run_row = st.columns([4, 1])
        with run_row[0]:
            run_options = runs_df.to_dict("records")
            selected_run = st.selectbox(
                "Load Previous Analysis",
                options=run_options,
                format_func=lambda x: format_run_label(pd.Series(x)),
                index=0,
                label_visibility="collapsed"
            )
        with run_row[1]:
            if st.button("Load Run", type="primary", use_container_width=True):
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

    st.caption("Tip: Check the checkbox to select a stock.")
    
    event = st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="multi-row",
    )

    # Store selected row index
    selected_idx = None
    if event and event.selection and event.selection.rows:
        selected_idx = event.selection.rows[0]

    # Action Buttons - Compact Layout
    action_row = st.columns([1.5, 0.5, 1, 1])
    
    with action_row[0]:
        if selected_idx is not None:
            if st.button("🔍 Deep Dive", use_container_width=True, type="primary"):
                row = show_df.iloc[selected_idx].to_dict()
                st.session_state["detail_row"] = row
                st.session_state["view"] = "detail"
                st.rerun()
        else:
            st.button("🔍 Deep Dive", use_container_width=True, disabled=True)
    
    with action_row[1]:
        st.write("")  # Spacer
    
    with action_row[2]:
        st.download_button(
            "📄 CSV",
            data=export_bytes(show_df[display_cols], kind="csv"),
            file_name="nse500_analysis.csv",
            mime="text/csv",
            use_container_width=True,
        )
    
    with action_row[3]:
        st.download_button(
            "📊 Excel",
            data=export_bytes(show_df[display_cols], kind="excel"),
            file_name="nse500_analysis.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    # Footer
    st.divider()
    footer_col1, footer_col2, footer_col3 = st.columns([1, 1, 1])
    
    with footer_col1:
        st.caption(f"**Version:** {APP_VERSION}")
    
    with footer_col2:
        last_updated = repo.get_last_update_timestamp()
        if last_updated:
            st.caption(f"**Data Updated:** {last_updated}")
    
    with footer_col3:
        st.caption("© 2026 Personal Stock Advisor")


if __name__ == "__main__":
    main()
