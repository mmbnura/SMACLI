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
    volume = df.get("Volume", pd.Series(0, index=df.index))

    # === TREND INDICATORS ===
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean() if len(close) >= 200 else ema50

    # === MOMENTUM INDICATORS ===
    # RSI
    delta = close.diff()
    up = np.where(delta > 0, delta, 0)
    down = np.where(delta < 0, -delta, 0)
    roll_up = pd.Series(up, index=close.index).rolling(14).mean()
    roll_down = pd.Series(down, index=close.index).rolling(14).mean()
    rs = roll_up / (roll_down.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    macd_histogram = macd - signal

    # === VOLATILITY INDICATORS ===
    # Bollinger Bands
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    bb_upper = sma20 + (std20 * 2)
    bb_lower = sma20 - (std20 * 2)
    bb_position = (close - bb_lower) / (bb_upper - bb_lower)
    
    # Volatility (ATR-like)
    high = df.get("High", close)
    low = df.get("Low", close)
    tr = np.maximum(high - low, np.maximum(abs(high - close.shift(1)), abs(low - close.shift(1))))
    atr = pd.Series(tr, index=close.index).rolling(14).mean()
    volatility = (atr / close) * 100  # Volatility as % of price

    # === TREND STRENGTH (ADX-like) ===
    # Simplified ADX calculation
    tr_series = pd.Series(tr, index=close.index)
    tr14 = tr_series.rolling(14).mean()
    
    plus_dm = np.where((high - high.shift(1)) > (low.shift(1) - low), (high - high.shift(1)), 0)
    minus_dm = np.where((low.shift(1) - low) > (high - high.shift(1)), (low.shift(1) - low), 0)
    
    plus_di = 100 * (pd.Series(plus_dm, index=close.index).rolling(14).mean() / tr14)
    minus_di = 100 * (pd.Series(minus_dm, index=close.index).rolling(14).mean() / tr14)
    di_diff = abs(plus_di - minus_di)
    adx = di_diff.rolling(14).mean()

    # === VOLUME ANALYSIS ===
    avg_volume = volume.rolling(20).mean()
    volume_ratio = volume / (avg_volume if avg_volume.iloc[-1] > 0 else 1)

    # Price momentum (acceleration)
    price_change_5d = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100 if len(close) >= 5 else 0
    price_change_20d = (close.iloc[-1] - close.iloc[-20]) / close.iloc[-20] * 100 if len(close) >= 20 else 0

    return {
        "price": float(close.iloc[-1]),
        "ema20": float(ema20.iloc[-1]),
        "ema50": float(ema50.iloc[-1]),
        "ema200": float(ema200.iloc[-1]),
        "rsi": float(rsi.iloc[-1]),
        "macd": float(macd.iloc[-1]),
        "macd_signal": float(signal.iloc[-1]),
        "macd_histogram": float(macd_histogram.iloc[-1]),
        "bb_upper": float(bb_upper.iloc[-1]),
        "bb_lower": float(bb_lower.iloc[-1]),
        "bb_position": float(bb_position.iloc[-1]),  # 0=lower band, 1=upper band
        "volatility": float(volatility.iloc[-1]),
        "atr": float(atr.iloc[-1]),
        "adx": float(adx.iloc[-1]),
        "volume_ratio": float(volume_ratio.iloc[-1]),
        "price_change_5d": float(price_change_5d),
        "price_change_20d": float(price_change_20d),
    }


def conservative_score(technical: dict, fundamentals: dict) -> AnalysisOutput:
    """
    Enhanced conservative scoring with:
    - Better weighted indicators
    - Volatility assessment
    - Growth metrics
    - Quality metrics
    - Dynamic thresholds
    """
    score = 0
    notes: list[str] = []

    # === TECHNICAL ANALYSIS (Total: ~30 points) ===
    
    # Trend strength (EMA crossovers) - 8 points
    ema20 = technical.get("ema20")
    ema50 = technical.get("ema50")
    ema200 = technical.get("ema200")
    
    if ema20 is not None and ema50 is not None:
        if ema20 > ema50 > ema200:
            score += 8
            notes.append("Strong uptrend (EMA20 > EMA50 > EMA200)")
        elif ema20 > ema50:
            score += 4
            notes.append("Uptrend (EMA20 > EMA50)")
        elif ema20 > ema200:
            score += 1
            notes.append("Medium-term uptrend")
        else:
            score -= 4
            notes.append("Downtrend risk (EMA20 < EMA50)")

    # Momentum (RSI) - 6 points
    rsi = technical.get("rsi")
    if rsi is not None:
        if 45 <= rsi <= 55:
            score += 6
            notes.append("Excellent momentum (RSI 45-55)")
        elif 40 <= rsi <= 60:
            score += 4
            notes.append("Good momentum (RSI 40-60)")
        elif 30 <= rsi <= 70:
            score += 1
            notes.append("Neutral momentum (RSI 30-70)")
        elif rsi > 70:
            score -= 4
            notes.append("Overbought warning (RSI > 70)")
        elif rsi < 30:
            score -= 2
            notes.append("Oversold condition (RSI < 30)")

    # MACD - 5 points
    macd = technical.get("macd")
    macd_signal = technical.get("macd_signal")
    macd_histogram = technical.get("macd_histogram")
    
    if macd is not None and macd_signal is not None:
        if macd > macd_signal and macd > 0:
            score += 5
            notes.append("MACD bullish signal (above signal line and positive)")
        elif macd > macd_signal:
            score += 2
            notes.append("MACD crossover upward")
        elif macd_histogram is not None and macd_histogram < 0:
            score -= 3
            notes.append("MACD histogram negative")

    # Bollinger Bands position - 4 points
    bb_position = technical.get("bb_position")
    if bb_position is not None:
        if 0.3 <= bb_position <= 0.7:
            score += 4
            notes.append("Price within Bollinger Band range (stable)")
        elif bb_position > 0.8:
            score -= 2
            notes.append("Price near upper Bollinger Band (potential pullback)")

    # Trend strength (ADX) - 3 points
    adx = technical.get("adx")
    if adx is not None:
        if adx > 25:
            score += 3
            notes.append(f"Strong trend (ADX {adx:.1f})")
        elif adx < 15:
            score -= 1
            notes.append(f"Weak trend (ADX {adx:.1f})")

    # Volume confirmation - 2 points
    volume_ratio = technical.get("volume_ratio")
    if volume_ratio is not None and volume_ratio > 1.2:
        score += 2
        notes.append("Strong volume confirmation")

    # Price momentum - 2 points
    price_change_5d = technical.get("price_change_5d")
    if price_change_5d is not None and price_change_5d > 2:
        score += 2
        notes.append("Positive short-term momentum")
    elif price_change_5d is not None and price_change_5d < -2:
        score -= 2
        notes.append("Negative short-term momentum")

    # === VOLATILITY ASSESSMENT (~5 points) ===
    volatility = technical.get("volatility", 0)
    if volatility < 1.5:
        score += 2
        notes.append("Low volatility (stable)")
    elif 1.5 <= volatility <= 3:
        score += 1
        notes.append("Moderate volatility (acceptable)")
    elif volatility > 5:
        score -= 2
        notes.append("High volatility (risky)")

    # === FUNDAMENTAL ANALYSIS (~30 points) ===
    
    # Profitability (ROE) - 6 points
    roe = fundamentals.get("roe")
    if roe is not None:
        if roe > 20:
            score += 6
            notes.append(f"Excellent ROE ({roe:.1f}%)")
        elif roe > 15:
            score += 4
            notes.append(f"Good ROE ({roe:.1f}%)")
        elif roe > 10:
            score += 2
            notes.append(f"Fair ROE ({roe:.1f}%)")
        elif roe < 5:
            score -= 3
            notes.append(f"Weak ROE ({roe:.1f}%)")

    # Profit Margin - 4 points
    profit_margin = fundamentals.get("profit_margin")
    if profit_margin is not None:
        if profit_margin > 15:
            score += 4
            notes.append(f"Strong profit margin ({profit_margin:.1f}%)")
        elif profit_margin > 10:
            score += 2
            notes.append(f"Good profit margin ({profit_margin:.1f}%)")
        elif profit_margin < 5:
            score -= 2
            notes.append(f"Low profit margin ({profit_margin:.1f}%)")

    # Growth metrics - 6 points
    revenue_growth = fundamentals.get("revenue_growth", 0)
    earnings_growth = fundamentals.get("earnings_growth", 0)
    
    avg_growth = (revenue_growth + earnings_growth) / 2 if revenue_growth and earnings_growth else revenue_growth or earnings_growth or 0
    
    if avg_growth > 15:
        score += 6
        notes.append(f"Strong growth ({avg_growth:.1f}%)")
    elif avg_growth > 10:
        score += 4
        notes.append(f"Good growth ({avg_growth:.1f}%)")
    elif avg_growth > 5:
        score += 2
        notes.append(f"Moderate growth ({avg_growth:.1f}%)")
    elif avg_growth < 0:
        score -= 3
        notes.append("Negative growth (declining)")

    # Valuation (PE ratio) - 6 points
    pe = fundamentals.get("pe")
    if pe is not None and pe > 0:
        if pe < 15:
            score += 6
            notes.append(f"Cheap valuation (PE {pe:.1f})")
        elif pe < 20:
            score += 4
            notes.append(f"Fair valuation (PE {pe:.1f})")
        elif pe < 30:
            score += 1
            notes.append(f"Moderate valuation (PE {pe:.1f})")
        elif pe > 40:
            score -= 4
            notes.append(f"Expensive valuation (PE {pe:.1f})")

    # PEG Ratio (PE to Growth) - 4 points
    peg_ratio = fundamentals.get("peg_ratio")
    if peg_ratio is not None and peg_ratio > 0:
        if peg_ratio < 1:
            score += 4
            notes.append(f"Excellent value (PEG {peg_ratio:.1f})")
        elif peg_ratio < 2:
            score += 2
            notes.append(f"Good value (PEG {peg_ratio:.1f})")
        elif peg_ratio > 3:
            score -= 2
            notes.append(f"Overvalued (PEG {peg_ratio:.1f})")

    # Financial Health (Debt-to-Equity) - 4 points
    dte = fundamentals.get("debt_to_equity")
    if dte is not None:
        if dte < 0.5:
            score += 4
            notes.append(f"Excellent debt health (D/E {dte:.1f})")
        elif dte < 1:
            score += 2
            notes.append(f"Good debt health (D/E {dte:.1f})")
        elif dte > 2:
            score -= 4
            notes.append(f"High debt risk (D/E {dte:.1f})")

    # Liquidity (Current Ratio) - 3 points
    current_ratio = fundamentals.get("current_ratio")
    if current_ratio is not None:
        if current_ratio > 1.5:
            score += 3
            notes.append(f"Strong liquidity (Current {current_ratio:.1f})")
        elif current_ratio < 0.8:
            score -= 3
            notes.append(f"Liquidity concern (Current {current_ratio:.1f})")

    # Dividend Yield - 2 points
    dividend_yield = fundamentals.get("dividend_yield")
    if dividend_yield is not None and dividend_yield > 2:
        score += 2
        notes.append(f"Good dividend yield ({dividend_yield:.1f}%)")

    # === FINAL RECOMMENDATION ===
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
    """
    Generate recommendation based on enhanced scoring system.
    Score range: typically -20 to +60
    """
    if score >= 35:
        return "BUY"
    if 15 <= score <= 34:
        return "HOLD"
    return "AVOID"


def confidence_band(score: int) -> str:
    """
    Generate confidence level based on score strength.
    Higher absolute scores = higher confidence
    """
    abs_score = abs(score)
    
    if abs_score >= 40:
        return "High"
    if 20 <= abs_score < 40:
        return "Medium"
    return "Low"
