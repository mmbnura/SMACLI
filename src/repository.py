from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

import pandas as pd

from src.config import FUNDAMENTAL_REFRESH_HOURS, PRICE_REFRESH_HOURS
from src.db import get_conn

UTC = timezone.utc


class StockRepository:
    def upsert_stocks_master(self, stocks_df: pd.DataFrame) -> None:
        rows = stocks_df[["symbol", "name", "sector", "cap_category"]].dropna().to_dict("records")
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

    def get_all_caps(self) -> list[str]:
        with get_conn() as conn:
            df = pd.read_sql_query(
                "SELECT DISTINCT cap_category FROM stocks_master ORDER BY cap_category", conn
            )
            return df["cap_category"].dropna().tolist()

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

    def save_analysis_result(self, result: dict) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO analysis_results(symbol, score, recommendation, confidence, notes, technical_snapshot, fundamental_snapshot)
                VALUES (:symbol, :score, :recommendation, :confidence, :notes, :technical_snapshot, :fundamental_snapshot)
                """,
                result,
            )

    def get_latest_analysis(self, symbols: Iterable[str]) -> pd.DataFrame:
        symbols = list(symbols)
        if not symbols:
            return pd.DataFrame()

        placeholders = ",".join(["?"] * len(symbols))
        query = f"""
        SELECT ar1.*
        FROM analysis_results ar1
        JOIN (
            SELECT symbol, MAX(timestamp) AS max_ts
            FROM analysis_results
            WHERE symbol IN ({placeholders})
            GROUP BY symbol
        ) ar2 ON ar1.symbol = ar2.symbol AND ar1.timestamp = ar2.max_ts
        """
        with get_conn() as conn:
            return pd.read_sql_query(query, conn, params=symbols)

    def get_last_update_timestamp(self) -> str | None:
        with get_conn() as conn:
            row = conn.execute("SELECT MAX(timestamp) as ts FROM analysis_results").fetchone()
            return row["ts"] if row and row["ts"] else None
