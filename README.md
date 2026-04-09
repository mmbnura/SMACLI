# Personal Stock Advisor (NSE 500 Analyzer)

A local Streamlit application that performs conservative stock analysis on NSE stocks using a hybrid technical + fundamental model.

## Architecture (brief)

- **UI layer (`app.py`)**: Streamlit dashboard for filters, analysis execution, result table, explainability panel, and exports.
- **Service layer (`src/advisor_service.py`)**: Orchestrates cache refresh, analysis execution, and result persistence.
- **Data providers (`src/data_fetcher.py`)**:
  - `MasterStockLoader`: loads NSE master list from local CSV (or NSE URL fallback).
  - `YahooFinanceClient`: fetches OHLCV + fundamentals via `yfinance`.
- **Analysis engine (`src/analysis.py`)**: computes EMA/RSI/MACD, applies conservative scoring and recommendation logic.
- **Persistence (`src/db.py`, `src/repository.py`)**: SQLite schema + CRUD/upsert operations for stock masters, cache tables, and analysis history.

## Project structure

```text
.
├── app.py
├── init_db.py
├── requirements.txt
├── README.md
├── data/
│   └── nifty500_master.csv
└── src/
    ├── __init__.py
    ├── advisor_service.py
    ├── analysis.py
    ├── bootstrap.py
    ├── config.py
    ├── data_fetcher.py
    ├── db.py
    └── repository.py
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python init_db.py
streamlit run app.py
```

## Features implemented

- Local SQLite database with required tables:
  - `stocks_master`
  - `stock_data`
  - `fundamentals`
  - `analysis_results`
- Conservative analysis model:
  - Technical: EMA20/EMA50, RSI, MACD
  - Fundamental: ROE, PE, Debt-to-Equity
  - Weighted score with penalties
  - BUY / HOLD / AVOID recommendations
- Explainable notes per stock
- Caching and refresh thresholds for historical + fundamental data
- Failure-tolerant analysis loop (skips failed symbols)
- Optional features:
  - Last updated timestamp
  - CSV/Excel export
  - "Only BUY" filter

## Notes

- Yahoo Finance symbols are resolved as `{SYMBOL}.NS`.
- If `data/nifty500_master.csv` is absent, the app attempts to download NSE list from configured URL.
- This is a local, educational advisor and not investment advice.
