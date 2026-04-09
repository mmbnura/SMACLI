from __future__ import annotations

from io import StringIO

import pandas as pd
import requests
import yfinance as yf

from src.config import HISTORY_INTERVAL, HISTORY_PERIOD, MASTER_CSV_PATH, NIFTY500_CSV_URL


class MasterStockLoader:
    REQUIRED_COLUMNS = ["symbol", "name", "sector", "cap_category"]

    def load(self) -> pd.DataFrame:
        if MASTER_CSV_PATH.exists():
            raw = pd.read_csv(MASTER_CSV_PATH)
            return self._normalize(raw)

        response = requests.get(NIFTY500_CSV_URL, timeout=20)
        response.raise_for_status()
        raw = pd.read_csv(StringIO(response.text))
        normalized = self._normalize(raw)
        MASTER_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        normalized.to_csv(MASTER_CSV_PATH, index=False)
        return normalized

    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        mapper = {
            "symbol": "symbol",
            "Symbol": "symbol",
            "Company Name": "name",
            "name": "name",
            "Industry": "sector",
            "sector": "sector",
            "cap_category": "cap_category",
            "Series": "cap_category",
        }
        usable_cols = [c for c in df.columns if c in mapper]
        if not usable_cols:
            raise ValueError("NIFTY 500 master list does not contain expected columns")

        out = df[usable_cols].rename(columns=mapper)
        for col in self.REQUIRED_COLUMNS:
            if col not in out.columns:
                out[col] = "Unknown"

        out["symbol"] = out["symbol"].astype(str).str.strip().str.upper()
        out["name"] = out["name"].astype(str).str.strip()
        out["sector"] = out["sector"].astype(str).str.strip().replace({"": "Unknown"})
        out["cap_category"] = out["cap_category"].astype(str).str.strip().replace({"": "Unknown"})

        out = out.drop_duplicates(subset=["symbol"]).sort_values("symbol")
        return out[self.REQUIRED_COLUMNS]


class YahooFinanceClient:
    def fetch_history(self, symbol: str) -> pd.DataFrame:
        ticker = yf.Ticker(f"{symbol}.NS")
        history = ticker.history(period=HISTORY_PERIOD, interval=HISTORY_INTERVAL, auto_adjust=False)
        if history.empty:
            return pd.DataFrame()

        history = history.reset_index()
        expected = ["Date", "Open", "High", "Low", "Close", "Volume"]
        return history[[c for c in expected if c in history.columns]]

    def fetch_fundamentals(self, symbol: str) -> dict:
        ticker = yf.Ticker(f"{symbol}.NS")
        info = ticker.info

        roe = info.get("returnOnEquity")
        if roe is not None and roe <= 1:
            roe *= 100

        return {
            "roe": roe,
            "pe": info.get("trailingPE") or info.get("forwardPE"),
            "debt_to_equity": info.get("debtToEquity"),
            "market_cap": info.get("marketCap"),
        }
