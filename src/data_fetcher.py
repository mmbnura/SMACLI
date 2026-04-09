from __future__ import annotations

from io import StringIO

import pandas as pd
import requests
import yfinance as yf

from src.config import (
    HISTORY_INTERVAL,
    HISTORY_PERIOD,
    MASTER_CSV_PATH,
    MASTER_MICROCAP250_CSV_PATH,
    NIFTY500_CSV_URL,
    NIFTY_MICROCAP250_CSV_URLS,
)


class MasterStockLoader:
    REQUIRED_COLUMNS = ["symbol", "name", "sector", "cap_category"]

    def load(self, index_type: str = "nifty500", prefer_remote: bool = True) -> pd.DataFrame:
        """
        Load master stock list from either Nifty 500 or Nifty Microcap 250.
        
        Args:
            index_type: "nifty500" or "nifty_microcap250"
            prefer_remote: Try to fetch from remote first
            
        Returns:
            DataFrame with stock data, or empty DataFrame if not found
        """
        if index_type == "nifty_microcap250":
            csv_path = MASTER_MICROCAP250_CSV_PATH
            urls = NIFTY_MICROCAP250_CSV_URLS if isinstance(NIFTY_MICROCAP250_CSV_URLS, list) else [NIFTY_MICROCAP250_CSV_URLS]
        else:
            csv_path = MASTER_CSV_PATH
            urls = [NIFTY500_CSV_URL]

        if prefer_remote:
            for url in urls:
                try:
                    remote = self._download_from_nse(url)
                    csv_path.parent.mkdir(parents=True, exist_ok=True)
                    remote.to_csv(csv_path, index=False)
                    return remote
                except Exception:
                    continue

        if csv_path.exists():
            raw = pd.read_csv(csv_path)
            return self._normalize(raw)

        # Return empty DataFrame instead of raising for optional indices
        if index_type != "nifty500":
            return pd.DataFrame()

        raise RuntimeError(f"Unable to load {index_type} master list from both NSE and local CSV")

    def _download_from_nse(self, url: str) -> pd.DataFrame:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/csv,application/csv,*/*",
            "Referer": "https://www.nseindia.com/",
        }
        with requests.Session() as session:
            session.get("https://www.nseindia.com", headers=headers, timeout=20)
            response = session.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            raw = pd.read_csv(StringIO(response.text))
            return self._normalize(raw)

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
            raise ValueError("Master list does not contain expected columns")

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

        # Enhanced fundamentals
        pe = info.get("trailingPE") or info.get("forwardPE")
        debt_to_equity = info.get("debtToEquity")
        
        # Additional metrics
        profit_margin = info.get("profitMargins")  # Net profit margin
        if profit_margin is not None and profit_margin <= 1:
            profit_margin *= 100
            
        revenue_growth = info.get("revenueGrowth")  # YoY revenue growth
        if revenue_growth is not None and revenue_growth <= 1:
            revenue_growth *= 100
            
        earnings_growth = info.get("earningsGrowth")  # YoY earnings growth
        if earnings_growth is not None and earnings_growth <= 1:
            earnings_growth *= 100
            
        current_ratio = info.get("currentRatio")  # Short-term liquidity
        dividend_yield = info.get("dividendYield")
        if dividend_yield is not None and dividend_yield <= 1:
            dividend_yield *= 100
            
        peg_ratio = info.get("pegRatio")  # PE to growth ratio

        return {
            "roe": roe,
            "pe": pe,
            "debt_to_equity": debt_to_equity,
            "market_cap": info.get("marketCap"),
            "profit_margin": profit_margin,
            "revenue_growth": revenue_growth,
            "earnings_growth": earnings_growth,
            "current_ratio": current_ratio,
            "dividend_yield": dividend_yield,
            "peg_ratio": peg_ratio,
        }
