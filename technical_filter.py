#!/usr/bin/env python3
"""
TECHNICAL FILTER — MA + ATR + Volume overlay
Runs AFTER super_score_integrator.py.
Reads docs/value_opportunities.csv, adds technical columns, saves back.
Also updates docs/value_opportunities_filtered.csv if it exists.
Saves docs/technical_signals.json for the API.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DOCS = Path("docs")
VALUE_CSV = DOCS / "value_opportunities.csv"
FILTERED_CSV = DOCS / "value_opportunities_filtered.csv"
TECH_JSON = DOCS / "technical_signals.json"

RATE_DELAY = 0.2  # seconds between yfinance calls

TECH_COLS = [
    "is_stage2", "ma_score", "atr_ratio", "volume_dryup",
    "pct_from_52w_high", "pct_from_52w_low", "relative_strength_6m",
    "trend_direction", "tech_stage",
]


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─── Data fetching ─────────────────────────────────────────────────────────────

def _fetch_history(ticker: str, period: str = "1y") -> pd.DataFrame | None:
    """Download daily OHLCV history. Returns None on any error."""
    try:
        df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
        if df is None or df.empty or len(df) < 30:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        return df
    except Exception as exc:
        log.warning("yfinance error for %s: %s", ticker, exc)
        return None


def fetch_spy_6m_return() -> float:
    """Fetch SPY 6-month return. Returns 0.0 on failure."""
    try:
        spy = yf.download("SPY", period="7mo", interval="1d", progress=False, auto_adjust=True)
        if spy is None or spy.empty:
            return 0.0
        close = spy["Close"].squeeze() if isinstance(spy.columns, pd.MultiIndex) else spy["Close"]
        price_now = float(close.iloc[-1])
        price_6m = float(close.iloc[-126]) if len(close) >= 126 else float(close.iloc[0])
        return (price_now - price_6m) / price_6m * 100 if price_6m > 0 else 0.0
    except Exception as exc:
        log.warning("SPY fetch failed: %s", exc)
        return 0.0


# ─── Signal sub-computations ───────────────────────────────────────────────────

def _compute_ma_signals(close: pd.Series, price: float) -> tuple[bool, int, float | None]:
    """Returns (is_stage2, ma_score, ma200_4wk_ago)."""
    ma50 = float(close.rolling(50).mean().iloc[-1])
    ma150 = float(close.rolling(150).mean().iloc[-1]) if len(close) >= 150 else None
    ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
    ma200_4wk = float(close.rolling(200).mean().iloc[-21]) if len(close) >= 220 else None

    valid50 = not np.isnan(ma50)
    valid150 = ma150 is not None and not np.isnan(ma150)
    valid200 = ma200 is not None and not np.isnan(ma200)

    cond1 = price > ma50 if valid50 else False
    cond2 = ma50 > ma150 if (valid50 and valid150) else False
    cond3 = ma150 > ma200 if (valid150 and valid200) else False
    cond4 = (ma200 > ma200_4wk) if (valid200 and ma200_4wk is not None) else False

    is_stage2 = cond1 and cond2 and cond3 and cond4
    ma_score = int(cond1) + int(cond2) + int(cond3)
    return is_stage2, ma_score, ma200_4wk


def _compute_atr_ratio(high: pd.Series, low: pd.Series, close: pd.Series) -> float | None:
    try:
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)
        atr10 = float(tr.rolling(10).mean().iloc[-1])
        atr60 = float(tr.rolling(60).mean().iloc[-1])
        return round(atr10 / atr60, 3) if atr60 > 0 else None
    except Exception:
        return None


def _compute_volume_dryup(volume: pd.Series) -> bool:
    try:
        vol10 = float(volume.iloc[-10:].mean())
        vol60 = float(volume.iloc[-60:].mean())
        return bool(vol10 < vol60 * 0.50) if vol60 > 0 else False
    except Exception:
        return False


def _compute_52w(high: pd.Series, low: pd.Series, price: float) -> tuple[float | None, float | None]:
    try:
        hi52 = float(high.iloc[-252:].max()) if len(high) >= 252 else float(high.max())
        lo52 = float(low.iloc[-252:].min()) if len(low) >= 252 else float(low.min())
        pct_hi = round((price - hi52) / hi52 * 100, 2) if hi52 > 0 else None
        pct_lo = round((price - lo52) / lo52 * 100, 2) if lo52 > 0 else None
        return pct_hi, pct_lo
    except Exception:
        return None, None


def _compute_rs(close: pd.Series, price: float, spy_6m_return: float) -> float | None:
    try:
        price_6m_ago = float(close.iloc[-126]) if len(close) >= 126 else float(close.iloc[0])
        ticker_6m = (price - price_6m_ago) / price_6m_ago * 100 if price_6m_ago > 0 else 0.0
        return round(ticker_6m - spy_6m_return, 2)
    except Exception:
        return None


def _compute_trend(close: pd.Series, price: float) -> str:
    try:
        ma50 = float(close.rolling(50).mean().iloc[-1])
        ma200_val = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
        if ma200_val is None or np.isnan(ma200_val) or np.isnan(ma50):
            return "sideways"
        if price > ma50 and ma50 > ma200_val:
            return "uptrend"
        if price < ma50 and ma50 < ma200_val:
            return "downtrend"
        return "sideways"
    except Exception:
        return "sideways"


def _compute_tech_stage(
    close: pd.Series,
    price: float,
    ma200_4wk: float | None,
    pct_from_52w_high: float | None,
    pct_from_52w_low: float | None,
) -> str:
    try:
        if len(close) < 200:
            return "stage1"
        ma200 = float(close.rolling(200).mean().iloc[-1])
        if np.isnan(ma200):
            return "stage1"

        above_ma200 = price > ma200
        ma200_trending_up = (ma200 > ma200_4wk) if ma200_4wk is not None else False

        if not above_ma200:
            return "stage1" if (pct_from_52w_low is not None and pct_from_52w_low < 15) else "stage4"

        if not ma200_trending_up:
            return "stage1"

        # Above MA200 and trending up
        extended = (pct_from_52w_high is not None and pct_from_52w_high > -5) or (price > ma200 * 1.5)
        return "stage3" if extended else "stage2"
    except Exception:
        return "unknown"


# ─── Main signal computation ───────────────────────────────────────────────────

def compute_technical_signals(ticker: str, spy_6m_return: float) -> dict:
    """Compute all technical signals for a single ticker."""
    base: dict = {
        "ticker": ticker,
        "is_stage2": False,
        "ma_score": 0,
        "atr_ratio": None,
        "volume_dryup": False,
        "pct_from_52w_high": None,
        "pct_from_52w_low": None,
        "relative_strength_6m": None,
        "trend_direction": "sideways",
        "tech_stage": "unknown",
        "computed_at": _now_utc(),
        "error": None,
    }

    df = _fetch_history(ticker, period="1y")
    if df is None:
        base["error"] = "no_data"
        return base

    close = df["Close"].squeeze()
    high = df["High"].squeeze()
    low = df["Low"].squeeze()
    volume = df["Volume"].squeeze()

    if len(close) < 60:
        base["error"] = "insufficient_data"
        return base

    price = float(close.iloc[-1])

    is_stage2, ma_score, ma200_4wk = _compute_ma_signals(close, price)
    pct_hi, pct_lo = _compute_52w(high, low, price)

    base["is_stage2"] = is_stage2
    base["ma_score"] = ma_score
    base["atr_ratio"] = _compute_atr_ratio(high, low, close)
    base["volume_dryup"] = _compute_volume_dryup(volume)
    base["pct_from_52w_high"] = pct_hi
    base["pct_from_52w_low"] = pct_lo
    base["relative_strength_6m"] = _compute_rs(close, price, spy_6m_return)
    base["trend_direction"] = _compute_trend(close, price)
    base["tech_stage"] = _compute_tech_stage(close, price, ma200_4wk, pct_hi, pct_lo)

    return base


# ─── Column merging ────────────────────────────────────────────────────────────

def _merge_tech_signals(df: pd.DataFrame, signals: dict) -> pd.DataFrame:
    """Add/update technical columns in df. ticker must be a plain column."""
    # Build lookup series once per column to avoid lambda closure pitfall
    for col in TECH_COLS:
        lookup = {t: signals.get(t, {}).get(col) for t in signals}
        df[col] = df["ticker"].map(lambda t, lk=lookup: lk.get(str(t).upper()))
    return df


# ─── Main runner ───────────────────────────────────────────────────────────────

def run_technical_filter() -> None:
    if not VALUE_CSV.exists():
        log.error("Value opportunities file not found: %s", VALUE_CSV)
        return

    log.info("Loading %s …", VALUE_CSV)
    df = pd.read_csv(VALUE_CSV)
    if "ticker" not in df.columns:
        log.error("No 'ticker' column in value_opportunities.csv")
        return

    tickers = [str(t).upper().strip() for t in df["ticker"].dropna().unique().tolist()]
    log.info("Computing technical signals for %d tickers …", len(tickers))

    log.info("Fetching SPY 6m return …")
    spy_return = fetch_spy_6m_return()
    log.info("SPY 6m return: %.2f%%", spy_return)
    time.sleep(RATE_DELAY)

    signals: dict = {}
    for i, ticker in enumerate(tickers):
        log.info("  [%d/%d] %s", i + 1, len(tickers), ticker)
        signals[ticker] = compute_technical_signals(ticker, spy_return)
        time.sleep(RATE_DELAY)

    tech_json_out = {
        "generated_at": _now_utc(),
        "spy_6m_return": round(spy_return, 2),
        "signals": signals,
    }
    TECH_JSON.write_text(json.dumps(tech_json_out, indent=2, default=str))
    log.info("Saved %s", TECH_JSON)

    df = _merge_tech_signals(df, signals)
    df.to_csv(VALUE_CSV, index=False)
    log.info("Updated %s with technical columns", VALUE_CSV)

    if FILTERED_CSV.exists():
        log.info("Updating %s …", FILTERED_CSV)
        df_f = pd.read_csv(FILTERED_CSV)
        if "ticker" in df_f.columns:
            df_f = _merge_tech_signals(df_f, signals)
            df_f.to_csv(FILTERED_CSV, index=False)
            log.info("Updated %s", FILTERED_CSV)

    log.info("Technical filter complete.")


if __name__ == "__main__":
    run_technical_filter()
    print("Technical filter done")
