#!/usr/bin/env python3
"""
Pattern Detector — Phase 3: TA-Lib candlestick patterns + algorithmic VCP.

Uses TA-Lib for 60+ candlestick patterns and a pure-pandas VCP detector.
Saves docs/pattern_signals.json for the API.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

DOCS = Path("docs")
PATTERN_JSON = DOCS / "pattern_signals.json"
FILTERED_CSV = DOCS / "value_opportunities_filtered.csv"
VALUE_CSV = DOCS / "value_opportunities.csv"

# Try TA-Lib — fall back to empty dict if not installed
try:
    import talib
    _TALIB = True
except ImportError:
    _TALIB = False

# Bullish single/dual candle patterns (TA-Lib)
BULL_PATTERNS = {
    "hammer":             "CDLHAMMER",
    "inverted_hammer":    "CDLINVERTEDHAMMER",
    "engulfing_bull":     "CDLENGULFING",
    "morning_star":       "CDLMORNINGSTAR",
    "piercing":           "CDLPIERCING",
    "three_white":        "CDL3WHITESOLDIERS",
    "harami_bull":        "CDLHARAMI",
    "doji":               "CDLDOJI",
    "dragonfly_doji":     "CDLDRAGONFLYDOJI",
}

# Bearish patterns
BEAR_PATTERNS = {
    "hanging_man":        "CDLHANGINGMAN",
    "shooting_star":      "CDLSHOOTINGSTAR",
    "engulfing_bear":     "CDLENGULFING",
    "evening_star":       "CDLEVENINGSTAR",
    "three_black":        "CDL3BLACKCROWS",
    "bearish_harami":     "CDLHARAMI",
    "gravestone_doji":    "CDLGRAVESTONEDOJI",
}


def _fetch(ticker: str) -> pd.DataFrame | None:
    try:
        df = yf.download(ticker, period="1y", interval="1d",
                         progress=False, auto_adjust=True)
        if df is None or df.empty or len(df) < 30:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        return df
    except Exception:
        return None


# ─── TA-Lib pattern detection ──────────────────────────────────────────────────

def detect_talib_patterns(df: pd.DataFrame) -> dict:
    """Run TA-Lib pattern functions and return triggered patterns (last 5 bars)."""
    if not _TALIB:
        return {"talib_available": False}

    op = df["Open"].values.astype(float)
    hi = df["High"].values.astype(float)
    lo = df["Low"].values.astype(float)
    cl = df["Close"].values.astype(float)

    triggered_bull: list[str] = []
    triggered_bear: list[str] = []

    for name, func_name in BULL_PATTERNS.items():
        try:
            func = getattr(talib, func_name)
            result = func(op, hi, lo, cl)
            # Check last 5 bars for signal
            if any(result[-5:] > 0):
                triggered_bull.append(name)
        except Exception:
            pass

    for name, func_name in BEAR_PATTERNS.items():
        try:
            func = getattr(talib, func_name)
            result = func(op, hi, lo, cl)
            if any(result[-5:] < 0):
                triggered_bear.append(name)
        except Exception:
            pass

    return {
        "talib_available": True,
        "bullish_patterns": triggered_bull,
        "bearish_patterns": triggered_bear,
        "pattern_bias": (
            "BULLISH" if len(triggered_bull) > len(triggered_bear)
            else "BEARISH" if len(triggered_bear) > len(triggered_bull)
            else "NEUTRAL"
        ),
    }


# ─── VCP detection (pure pandas, no TA-Lib required) ──────────────────────────

def detect_vcp(df: pd.DataFrame, lookback: int = 60) -> dict:
    """
    Simplified Volatility Contraction Pattern (VCP) detector.

    Identifies contractions by splitting the lookback window into segments
    and checking if successive high-low ranges are contracting.

    Returns:
        detected: bool
        contractions: int (number of identified contractions)
        tightness_score: float (0-1, higher = tighter recent range)
        volume_declining: bool (volume trend in base)
    """
    if len(df) < lookback:
        return {"detected": False, "contractions": 0, "tightness_score": 0.0}

    recent = df.iloc[-lookback:]
    close = recent["Close"].squeeze()
    high  = recent["High"].squeeze()
    low   = recent["Low"].squeeze()
    vol   = recent["Volume"].squeeze()

    # Split into 4 equal segments
    seg_size = lookback // 4
    ranges = []
    for i in range(4):
        seg_high = float(high.iloc[i*seg_size:(i+1)*seg_size].max())
        seg_low  = float(low.iloc[i*seg_size:(i+1)*seg_size].min())
        seg_avg  = float(close.iloc[i*seg_size:(i+1)*seg_size].mean())
        if seg_avg > 0:
            ranges.append((seg_high - seg_low) / seg_avg)  # range as % of avg price

    contractions = 0
    if len(ranges) >= 2:
        for i in range(1, len(ranges)):
            if ranges[i] < ranges[i-1] * 0.80:  # at least 20% contraction
                contractions += 1

    # Tightness: last 10 days ATR vs full lookback ATR
    tr_full   = (high - low).mean()
    tr_recent = (high.iloc[-10:] - low.iloc[-10:]).mean() if len(high) >= 10 else tr_full
    tightness = float(1.0 - min(float(tr_recent) / float(tr_full), 1.0)) if tr_full > 0 else 0.0

    # Volume declining: compare last 10 bars to first 10 bars of base
    vol_early = float(vol.iloc[:10].mean()) if len(vol) >= 10 else float(vol.mean())
    vol_late  = float(vol.iloc[-10:].mean()) if len(vol) >= 10 else float(vol.mean())
    volume_declining = bool(vol_late < vol_early * 0.80)

    # VCP detected if at least 2 contractions + tightening
    detected = contractions >= 2 and tightness > 0.30

    return {
        "detected": detected,
        "contractions": contractions,
        "tightness_score": round(tightness, 3),
        "volume_declining": volume_declining,
    }


# ─── Main signal computation ───────────────────────────────────────────────────

def compute_patterns(ticker: str) -> dict:
    result: dict = {"ticker": ticker, "computed_at": _now_utc()}

    df = _fetch(ticker)
    if df is None:
        result["error"] = "no_data"
        return result

    result.update(detect_talib_patterns(df))
    result["vcp"] = detect_vcp(df)
    return result


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_pattern_detector(delay: float = 0.25) -> None:
    if not _TALIB:
        print("Warning: TA-Lib not installed — only VCP detection will run")
        print("Install: pip install TA-Lib")

    # Load tickers
    tickers: list[str] = []
    for csv_path in [FILTERED_CSV, VALUE_CSV]:
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                if "ticker" in df.columns:
                    tickers = df["ticker"].dropna().str.upper().tolist()
                    break
            except Exception:
                pass

    if not tickers:
        print("No tickers found")
        return

    unique = list(dict.fromkeys(tickers))
    print(f"Pattern detector: processing {len(unique)} tickers...")

    signals: dict = {}
    for i, ticker in enumerate(unique):
        result = compute_patterns(ticker)
        signals[ticker] = result
        vcp = result.get("vcp", {})
        bull = result.get("bullish_patterns", [])
        print(f"  [{i+1}/{len(unique)}] {ticker}: VCP={vcp.get('detected',False)} "
              f"contractions={vcp.get('contractions',0)} bull={bull}")
        time.sleep(delay)

    output = {
        "generated_at": _now_utc(),
        "talib_available": _TALIB,
        "signals": signals,
    }
    PATTERN_JSON.write_text(json.dumps(output, default=str))
    print(f"Pattern signals saved → {PATTERN_JSON}")


if __name__ == "__main__":
    run_pattern_detector()
