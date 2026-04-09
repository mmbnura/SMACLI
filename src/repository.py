from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Iterable

import pandas as pd

from src.config import FUNDAMENTAL_REFRESH_HOURS, PRICE_REFRESH_HOURS
from src.db import get_conn

UTC = timezone.utc


class StockRepository:
    def upsert_stocks_master(self, stocks_df: pd.DataFrame) -> None:
        frame = stocks_df.copy()
        frame["cap_category"] = frame["cap_category"].map(self._normalize_cap_category)
        rows = frame[["symbol", "name", "sector", "cap_category"]].dropna().to_dict("records")
        if not rows:
            return

        with get_conn() as conn:
            conn.executemany(
                """
                INSERT INTO stocks_master(symbol, name, sector, cap_category)
                VALUES (:symbol, :name, :sector, :cap_category)
                ON CONFLICT(symbol) DO UPDATE SET
                    name = excluded.name,
                    sector = excluded.sector,
                    cap_category = excluded.cap_category
                """,
                rows,
            )

    def _normalize_cap_category(self, val: str) -> str:
        text = (val or "").strip().lower()
        if "large" in text:
            return "Large"
        if "mid" in text or "medium" in text:
            return "Medium"
        if "small" in text:
            return "Small"
        return "Medium"

    def get_stocks(self, sectors: list[str] | None = None, cap: str | None = None) -> pd.DataFrame:
        query = "SELECT symbol, name, sector, cap_category FROM stocks_master WHERE 1=1"
        params: list[str] = []

        if sectors:
            placeholders = ",".join(["?"] * len(sectors))
            query += f" AND sector IN ({placeholders})"
            params.extend(sectors)

        if cap and cap != "All":
            query += " AND cap_category = ?"
            params.append(cap)

        query += " ORDER BY symbol"
        with get_conn() as conn:
            return pd.read_sql_query(query, conn, params=params)

    def get_all_sectors(self) -> list[str]:
        with get_conn() as conn:
            df = pd.read_sql_query(
                "SELECT DISTINCT sector FROM stocks_master ORDER BY sector", conn
            )
            return df["sector"].dropna().tolist()

    def get_meta(self, key: str) -> str | None:
        with get_conn() as conn:
            row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO app_meta(key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, value),
            )

    def should_refresh_price(self, symbol: str) -> bool:
        cutoff = datetime.now(UTC) - timedelta(hours=PRICE_REFRESH_HOURS)
        with get_conn() as conn:
            row = conn.execute(
                "SELECT MAX(fetched_at) as fetched_at FROM stock_data WHERE symbol = ?",
                (symbol,),
            ).fetchone()
        return not row["fetched_at"] or datetime.fromisoformat(row["fetched_at"]).replace(tzinfo=UTC) < cutoff

    def should_refresh_fundamentals(self, symbol: str) -> bool:
        cutoff = datetime.now(UTC) - timedelta(hours=FUNDAMENTAL_REFRESH_HOURS)
        with get_conn() as conn:
            row = conn.execute(
                "SELECT fetched_at FROM fundamentals WHERE symbol = ?",
                (symbol,),
            ).fetchone()

        if not row:
            return True
        return datetime.fromisoformat(row["fetched_at"]).replace(tzinfo=UTC) < cutoff

    def upsert_stock_history(self, symbol: str, history_df: pd.DataFrame) -> None:
        if history_df.empty:
            return

        frame = history_df.copy()
        frame["symbol"] = symbol
        frame = frame.rename(
            columns={
                "Date": "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")

        records = frame[["symbol", "date", "open", "high", "low", "close", "volume"]].to_dict("records")

        with get_conn() as conn:
            conn.executemany(
                """
                INSERT INTO stock_data(symbol, date, open, high, low, close, volume)
                VALUES (:symbol, :date, :open, :high, :low, :close, :volume)
                ON CONFLICT(symbol, date) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume,
                    fetched_at = CURRENT_TIMESTAMP
                """,
                records,
            )

    def get_stock_history(self, symbol: str) -> pd.DataFrame:
        with get_conn() as conn:
            return pd.read_sql_query(
                """
                SELECT date as Date, open as Open, high as High, low as Low, close as Close, volume as Volume
                FROM stock_data
                WHERE symbol = ?
                ORDER BY date
                """,
                conn,
                params=(symbol,),
                parse_dates=["Date"],
            )

    def upsert_fundamentals(self, symbol: str, fundamentals: dict) -> None:
        payload = {
            "symbol": symbol,
            "roe": fundamentals.get("roe"),
            "pe": fundamentals.get("pe"),
            "debt_to_equity": fundamentals.get("debt_to_equity"),
            "market_cap": fundamentals.get("market_cap"),
        }
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO fundamentals(symbol, roe, pe, debt_to_equity, market_cap)
                VALUES (:symbol, :roe, :pe, :debt_to_equity, :market_cap)
                ON CONFLICT(symbol) DO UPDATE SET
                    roe = excluded.roe,
                    pe = excluded.pe,
                    debt_to_equity = excluded.debt_to_equity,
                    market_cap = excluded.market_cap,
                    fetched_at = CURRENT_TIMESTAMP
                """,
                payload,
            )

    def get_fundamentals(self, symbol: str) -> dict:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT roe, pe, debt_to_equity, market_cap FROM fundamentals WHERE symbol = ?",
                (symbol,),
            ).fetchone()
            return dict(row) if row else {}

    def create_analysis_run(self) -> int:
        with get_conn() as conn:
            cur = conn.execute("INSERT INTO analysis_runs DEFAULT VALUES")
            return int(cur.lastrowid)

    def save_analysis_result(self, result: dict) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO analysis_results(analysis_run_id, symbol, score, recommendation, confidence, notes, technical_snapshot, fundamental_snapshot)
                VALUES (:analysis_run_id, :symbol, :score, :recommendation, :confidence, :notes, :technical_snapshot, :fundamental_snapshot)
                """,
                result,
            )

    def list_analysis_runs(self, limit: int = 50) -> pd.DataFrame:
        with get_conn() as conn:
            return pd.read_sql_query(
                """
                SELECT r.id as run_id, r.run_at, COUNT(ar.id) as stock_count
                FROM analysis_runs r
                LEFT JOIN analysis_results ar ON ar.analysis_run_id = r.id
                GROUP BY r.id, r.run_at
                ORDER BY r.run_at DESC
                LIMIT ?
                """,
                conn,
                params=(limit,),
            )

    def load_analysis_run(self, run_id: int) -> pd.DataFrame:
        with get_conn() as conn:
            df = pd.read_sql_query(
                """
                SELECT ar.symbol, sm.name, sm.sector, sm.cap_category, ar.score, ar.recommendation,
                       ar.confidence, ar.notes, ar.technical_snapshot, ar.fundamental_snapshot, ar.timestamp
                FROM analysis_results ar
                JOIN stocks_master sm ON sm.symbol = ar.symbol
                WHERE ar.analysis_run_id = ?
                ORDER BY ar.score DESC, ar.symbol
                """,
                conn,
                params=(run_id,),
            )
        if df.empty:
            return df
        df["technical"] = df["technical_snapshot"].apply(lambda x: json.loads(x or "{}"))
        df["fundamentals"] = df["fundamental_snapshot"].apply(lambda x: json.loads(x or "{}"))
        df["Price"] = df["technical"].apply(lambda x: round(float(x.get("price", 0) or 0), 2))
        return df

    def get_last_update_timestamp(self) -> str | None:
        with get_conn() as conn:
            row = conn.execute("SELECT MAX(timestamp) as ts FROM analysis_results").fetchone()
            return row["ts"] if row and row["ts"] else None
