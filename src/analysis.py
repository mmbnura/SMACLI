from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class AnalysisOutput:
    score: int
    recommendation: str
    confidence: str
    notes: list[str]
    technical: dict
    fundamentals: dict


def compute_indicators(history_df: pd.DataFrame) -> dict:
    if history_df.empty or len(history_df) < 60:
        raise ValueError("Insufficient history for indicator computation")

    df = history_df.copy()
    close = df["Close"]

    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()

    delta = close.diff()
    up = np.where(delta > 0, delta, 0)
    down = np.where(delta < 0, -delta, 0)
    roll_up = pd.Series(up, index=close.index).rolling(14).mean()
    roll_down = pd.Series(down, index=close.index).rolling(14).mean()
    rs = roll_up / (roll_down.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()

    return {
        "price": float(close.iloc[-1]),
        "ema20": float(ema20.iloc[-1]),
        "ema50": float(ema50.iloc[-1]),
        "rsi": float(rsi.iloc[-1]),
        "macd": float(macd.iloc[-1]),
        "macd_signal": float(signal.iloc[-1]),
    }


def conservative_score(technical: dict, fundamentals: dict) -> AnalysisOutput:
    score = 0
    notes: list[str] = []

    ema20 = technical.get("ema20")
    ema50 = technical.get("ema50")
    rsi = technical.get("rsi")
    macd = technical.get("macd")
    roe = fundamentals.get("roe")
    pe = fundamentals.get("pe")
    dte = fundamentals.get("debt_to_equity")

    if ema20 is not None and ema50 is not None:
        if ema20 > ema50:
            score += 2
            notes.append("Uptrend (EMA20 > EMA50)")
        else:
            score -= 3
            notes.append("Downtrend risk (EMA20 < EMA50)")

    if rsi is not None:
        if 40 <= rsi <= 60:
            score += 2
            notes.append("Healthy momentum (RSI 40-60)")
        elif rsi > 70:
            score -= 3
            notes.append("Overbought (RSI > 70)")

    if macd is not None:
        if macd > 0:
            score += 1
            notes.append("MACD positive")

    if roe is not None:
        if roe > 15:
            score += 2
            notes.append("Strong ROE")

    if dte is not None and dte > 100:
        score -= 2
        notes.append("High debt risk")

    if pe is not None and pe > 40:
        score -= 2
        notes.append("Very high PE risk")

    recommendation = recommend(score)
    confidence = confidence_band(score)

    if not notes:
        notes.append("Limited signal availability; conservative fallback")

    return AnalysisOutput(
        score=score,
        recommendation=recommendation,
        confidence=confidence,
        notes=notes,
        technical=technical,
        fundamentals=fundamentals,
    )


def recommend(score: int) -> str:
    if score >= 6:
        return "BUY"
    if 3 <= score <= 5:
        return "HOLD"
    return "AVOID"


def confidence_band(score: int) -> str:
    if score >= 7 or score <= 0:
        return "High"
    if score in {5, 6, 1, 2}:
        return "Medium"
    return "Low"
