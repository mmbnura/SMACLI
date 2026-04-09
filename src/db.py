from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from src.config import DB_PATH, DATA_DIR


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS stocks_master (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sector TEXT NOT NULL,
    cap_category TEXT NOT NULL,
    index_type TEXT DEFAULT 'nifty500',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stock_data (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, date),
    FOREIGN KEY (symbol) REFERENCES stocks_master(symbol)
);

CREATE TABLE IF NOT EXISTS fundamentals (
    symbol TEXT PRIMARY KEY,
    roe REAL,
    pe REAL,
    debt_to_equity REAL,
    market_cap REAL,
    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol) REFERENCES stocks_master(symbol)
);

CREATE TABLE IF NOT EXISTS analysis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_run_id INTEGER,
    symbol TEXT NOT NULL,
    score INTEGER NOT NULL,
    recommendation TEXT NOT NULL,
    confidence TEXT NOT NULL,
    notes TEXT NOT NULL,
    technical_snapshot TEXT,
    fundamental_snapshot TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol) REFERENCES stocks_master(symbol),
    FOREIGN KEY (analysis_run_id) REFERENCES analysis_runs(id)
);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stock_data_symbol_date ON stock_data(symbol, date);
CREATE INDEX IF NOT EXISTS idx_analysis_symbol_timestamp ON analysis_results(symbol, timestamp);
"""


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA_SQL)
        _migrate(conn)
        conn.commit()


def _migrate(conn: sqlite3.Connection) -> None:
    # Add analysis_run_id if missing
    columns = {row[1] for row in conn.execute("PRAGMA table_info(analysis_results)").fetchall()}
    if "analysis_run_id" not in columns:
        conn.execute("ALTER TABLE analysis_results ADD COLUMN analysis_run_id INTEGER")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_run ON analysis_results(analysis_run_id)")
    
    # Add index_type to stocks_master if missing
    columns = {row[1] for row in conn.execute("PRAGMA table_info(stocks_master)").fetchall()}
    if "index_type" not in columns:
        conn.execute("ALTER TABLE stocks_master ADD COLUMN index_type TEXT DEFAULT 'nifty500'")


@contextmanager
def get_conn(db_path: Path = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
