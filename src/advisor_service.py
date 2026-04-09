from __future__ import annotations

import json
from dataclasses import asdict

import pandas as pd

from src.analysis import conservative_score, compute_indicators
from src.data_fetcher import YahooFinanceClient
from src.repository import StockRepository


class AdvisorService:
    def __init__(self, repository: StockRepository | None = None, yf_client: YahooFinanceClient | None = None):
        self.repository = repository or StockRepository()
        self.yf_client = yf_client or YahooFinanceClient()

    def update_stock_cache(self, symbol: str) -> tuple[pd.DataFrame, dict]:
        if self.repository.should_refresh_price(symbol):
            try:
                history = self.yf_client.fetch_history(symbol)
                self.repository.upsert_stock_history(symbol, history)
            except Exception:
                pass

        if self.repository.should_refresh_fundamentals(symbol):
            try:
                fundamentals = self.yf_client.fetch_fundamentals(symbol)
                self.repository.upsert_fundamentals(symbol, fundamentals)
            except Exception:
                pass

        return self.repository.get_stock_history(symbol), self.repository.get_fundamentals(symbol)

    def analyze_symbol(self, symbol: str) -> dict | None:
        history, fundamentals = self.update_stock_cache(symbol)
        if history.empty:
            return None

        try:
            technical = compute_indicators(history)
            analysis = conservative_score(technical, fundamentals)
        except Exception:
            return None

        result = {
            "symbol": symbol,
            "score": analysis.score,
            "recommendation": analysis.recommendation,
            "confidence": analysis.confidence,
            "notes": " | ".join(analysis.notes),
            "technical_snapshot": json.dumps(analysis.technical),
            "fundamental_snapshot": json.dumps(analysis.fundamentals),
        }
        self.repository.save_analysis_result(result)

        payload = asdict(analysis)
        payload.update({"symbol": symbol, "price": analysis.technical.get("price")})
        return payload

    def analyze_universe(self, stocks_df: pd.DataFrame) -> pd.DataFrame:
        results = []
        for _, row in stocks_df.iterrows():
            output = self.analyze_symbol(row["symbol"])
            if not output:
                continue
            results.append(
                {
                    "Stock": row["symbol"],
                    "Name": row["name"],
                    "Sector": row["sector"],
                    "Cap": row["cap_category"],
                    "Price": round(output.get("price", 0.0), 2),
                    "Score": output["score"],
                    "Recommendation": output["recommendation"],
                    "Confidence": output["confidence"],
                    "Notes": " | ".join(output["notes"]),
                    "technical": output["technical"],
                    "fundamentals": output["fundamentals"],
                }
            )

        if not results:
            return pd.DataFrame()

        out = pd.DataFrame(results)
        return out.sort_values(by=["Score", "Price"], ascending=[False, False]).reset_index(drop=True)
