#!/usr/bin/env python3
"""
Chart Analyzer — Phase 2: Groq Vision (Llama 4, free tier)

Generates annotated candlestick charts (mplfinance) and sends them to
Groq's vision API (meta-llama/llama-4-maverick) for technical analysis.
Uses JSON mode for clean structured output — no parsing needed.

Pipeline mode (nightly):  python3 chart_analyzer.py --batch
Single ticker (dev/API):  python3 chart_analyzer.py AAPL MSFT
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

DOCS = Path("docs")
CHART_SIGNALS_JSON = DOCS / "chart_signals.json"
TECHNICAL_JSON = DOCS / "technical_signals.json"
FILTERED_CSV = DOCS / "value_opportunities_filtered.csv"

# Groq vision model — Llama 4 Maverick (best multimodal on Groq, free tier)
MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct"
# Fallback if Maverick unavailable
MODEL_FALLBACK = "meta-llama/llama-4-scout-17b-16e-instruct"
ANALYSIS_PROMPT = """\
You are a professional technical analyst reviewing a daily candlestick chart.
The chart shows 6 months of price + volume with 50-day (orange), 150-day (blue),
and 200-day (purple) moving averages.

Analyze ONLY what is visible in the chart. Do NOT invent data or price levels.

Return ONLY valid JSON in this exact structure (no markdown, no explanation):
{
  "trend_direction": "uptrend|downtrend|sideways",
  "above_200ma": true,
  "above_150ma": true,
  "base_forming": false,
  "base_type": "vcp|flat_base|cup_handle|triangle|flag|none",
  "base_weeks": null,
  "volume_dryup_visible": false,
  "volume_breakout": false,
  "extended_from_base": false,
  "key_resistance": null,
  "key_support": null,
  "distribution_signs": false,
  "entry_quality": "ideal|acceptable|wait|avoid",
  "entry_rationale": "1-2 sentences describing what you see",
  "risk_level": "low|medium|high",
  "confidence": "high|medium|low",
  "notes": null
}

Strict rules:
- Use null for prices you cannot determine precisely
- "base_forming" requires at least 3 visible weeks of sideways action
- "extended_from_base" means price is >20% above the last identifiable base
- Set confidence to "low" if the pattern is ambiguous
- "entry_quality": ideal=at pivot/base, acceptable=minor extension, wait=no clear setup, avoid=extended/distribution
"""


# ─── Chart generation ──────────────────────────────────────────────────────────

def generate_chart_bytes(ticker: str, period: str = "6mo") -> bytes | None:
    """Generate an annotated candlestick PNG as bytes (no disk I/O)."""
    try:
        import mplfinance as mpf
        import yfinance as yf
        import pandas as pd

        df = yf.download(ticker, period=period, interval="1d",
                         progress=False, auto_adjust=True)
        if df is None or df.empty or len(df) < 20:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]

        close = df["Close"].squeeze()
        add_plots = []
        if len(close) >= 50:
            add_plots.append(mpf.make_addplot(
                close.rolling(50).mean(), color="#f59e0b", width=1.0, label="MA50"))
        if len(close) >= 150:
            add_plots.append(mpf.make_addplot(
                close.rolling(150).mean(), color="#3b82f6", width=0.8, label="MA150"))
        if len(close) >= 200:
            add_plots.append(mpf.make_addplot(
                close.rolling(200).mean(), color="#8b5cf6", width=0.8, label="MA200"))

        buf = io.BytesIO()
        mpf.plot(
            df,
            type="candle",
            style="charles",
            addplot=add_plots if add_plots else None,
            volume=True,
            figsize=(12, 6),
            tight_layout=True,
            title=f"\n{ticker} — Daily (6 months)",
            savefig=dict(fname=buf, format="png", dpi=100),
        )
        buf.seek(0)
        return buf.read()

    except Exception as e:
        print(f"  Chart gen failed for {ticker}: {e}")
        return None


# ─── Groq API helpers ─────────────────────────────────────────────────────────

def _get_groq_client():
    from groq import Groq
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable not set")
    return Groq(api_key=api_key)


def _call_groq_vision(client, image_bytes: bytes, prompt: str, model: str) -> dict:
    """
    Send one chart image to Groq vision API.
    Uses JSON mode for clean structured output — no markdown parsing needed.
    Falls back to MODEL_FALLBACK if primary model fails.
    """
    b64 = base64.standard_b64encode(image_bytes).decode()
    data_url = f"data:image/png;base64,{b64}"

    for attempt_model in [model, MODEL_FALLBACK]:
        try:
            response = client.chat.completions.create(
                model=attempt_model,
                max_tokens=500,
                response_format={"type": "json_object"},
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            text = response.choices[0].message.content or ""
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # JSON mode should prevent this, but handle gracefully
                start, end = text.find("{"), text.rfind("}") + 1
                if start >= 0 and end > start:
                    return json.loads(text[start:end])
                return {"entry_quality": "wait", "confidence": "low", "error": "parse_failed"}
        except Exception as e:
            err = str(e)
            if attempt_model == MODEL_FALLBACK:
                return {"entry_quality": "wait", "confidence": "low", "error": err}
            print(f"    {attempt_model} failed ({err}), trying fallback...")
            time.sleep(2)

    return {"entry_quality": "wait", "confidence": "low", "error": "all_models_failed"}


def analyze_single(ticker: str, image_bytes: bytes,
                   fundamental_score: float | None = None,
                   grade: str | None = None) -> dict:
    """Synchronous analysis via Groq Vision — fast, free tier."""
    try:
        client = _get_groq_client()
        context = ""
        if fundamental_score is not None:
            context = f"\nFundamental context: Grade={grade or '?'}, Score={fundamental_score:.0f}/100."

        result = _call_groq_vision(client, image_bytes, ANALYSIS_PROMPT + context, MODEL)
        result["ticker"] = ticker.upper()
        result["analyzed_at"] = datetime.now(timezone.utc).isoformat()
        result["model"] = MODEL
        return result

    except Exception as e:
        return {"ticker": ticker, "error": str(e), "entry_quality": "wait", "confidence": "low"}


def analyze_batch(ticker_data: list[dict]) -> dict[str, dict]:
    """
    Sequential vision analysis via Groq.
    Groq doesn't have a batch API but is fast (~200 tok/s).
    With ~20-30 tickers and 1s delay, completes in ~1-2 minutes.
    ticker_data: list of {ticker, image_bytes, fundamental_score, grade}
    """
    results: dict[str, dict] = {}
    if not ticker_data:
        return results

    try:
        client = _get_groq_client()
    except RuntimeError as e:
        print(f"  Groq client error: {e}")
        return results

    total = len(ticker_data)
    for i, item in enumerate(ticker_data):
        ticker = item["ticker"]
        img = item.get("image_bytes")
        if not img:
            print(f"  [{i+1}/{total}] {ticker}: no image — skipping")
            continue

        score = item.get("fundamental_score")
        grade = item.get("grade", "?")
        context = f"\nFundamental context: Grade={grade}, Score={score:.0f}/100." if score else ""

        print(f"  [{i+1}/{total}] {ticker}: sending to Groq vision...")
        result = _call_groq_vision(client, img, ANALYSIS_PROMPT + context, MODEL)
        result["ticker"] = ticker
        result["analyzed_at"] = datetime.now(timezone.utc).isoformat()
        result["model"] = MODEL
        results[ticker] = result

        entry = result.get("entry_quality", "?")
        conf = result.get("confidence", "?")
        print(f"    → entry={entry} confidence={conf}")

        # Groq free tier: ~30 req/min — 2s delay is safe
        time.sleep(2)

    return results


# ─── Ticker selection ──────────────────────────────────────────────────────────

def _get_priority_tickers() -> list[dict]:
    """
    Return tickers worth analyzing: passed fundamental filter AND
    tech_stage is stage2 or ma_score >= 2.
    Loads scores from technical_signals.json and filtered CSV.
    """
    import pandas as pd

    # Load technical signals
    tech_signals: dict = {}
    if TECHNICAL_JSON.exists():
        try:
            data = json.loads(TECHNICAL_JSON.read_text())
            tech_signals = data.get("signals", {})
        except Exception:
            pass

    # Load filtered opportunities (grades + scores)
    fund_data: dict = {}
    if FILTERED_CSV.exists():
        try:
            df = pd.read_csv(FILTERED_CSV)
            for _, row in df.iterrows():
                t = str(row.get("ticker", "")).upper()
                if t:
                    fund_data[t] = {
                        "fundamental_score": row.get("value_score"),
                        "grade": row.get("conviction_grade"),
                    }
        except Exception:
            pass

    # Fallback: use all tickers from value_opportunities.csv
    if not fund_data:
        value_csv = DOCS / "value_opportunities.csv"
        if value_csv.exists():
            try:
                df = pd.read_csv(value_csv)
                for _, row in df.iterrows():
                    t = str(row.get("ticker", "")).upper()
                    if t:
                        fund_data[t] = {
                            "fundamental_score": row.get("value_score"),
                            "grade": row.get("conviction_grade"),
                        }
            except Exception:
                pass

    priority: list[dict] = []
    for ticker, fd in fund_data.items():
        ts = tech_signals.get(ticker, {})
        ma_score = ts.get("ma_score", 0) or 0
        tech_stage = ts.get("tech_stage", "")
        # Include: stage2 confirmed OR at least 2/3 MA conditions
        if tech_stage == "stage2" or ma_score >= 2:
            priority.append({
                "ticker": ticker,
                "fundamental_score": fd.get("fundamental_score"),
                "grade": fd.get("grade"),
            })

    # If no tech data yet, analyze all fundamental picks
    if not priority and fund_data:
        priority = [{"ticker": t, **fd} for t, fd in fund_data.items()]

    print(f"  Priority tickers for chart analysis: {len(priority)}")
    return priority


# ─── Main runner ───────────────────────────────────────────────────────────────

def run_batch_analysis() -> None:
    """Nightly pipeline batch mode."""
    print("Chart Analyzer — batch mode")
    tickers = _get_priority_tickers()
    if not tickers:
        print("  No tickers to analyze")
        return

    # Generate chart images
    print(f"  Generating charts for {len(tickers)} tickers...")
    ticker_data = []
    for item in tickers:
        ticker = item["ticker"]
        img = generate_chart_bytes(ticker)
        if img:
            ticker_data.append({**item, "image_bytes": img})
            print(f"    {ticker}: chart generated ({len(img)//1024}KB)")
        else:
            print(f"    {ticker}: chart failed — skipping")
        time.sleep(0.3)  # rate limit yfinance

    if not ticker_data:
        print("  No charts generated — aborting")
        return

    # Load existing signals to merge
    existing: dict = {}
    if CHART_SIGNALS_JSON.exists():
        try:
            existing = json.loads(CHART_SIGNALS_JSON.read_text()).get("signals", {})
        except Exception:
            pass

    # Analyze
    results = analyze_batch(ticker_data)

    # Merge and save
    merged = {**existing, **results}
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "ticker_count": len(results),
        "signals": merged,
    }
    CHART_SIGNALS_JSON.write_text(json.dumps(output, default=str))
    print(f"Chart signals saved: {len(results)} new / {len(merged)} total → {CHART_SIGNALS_JSON}")


def run_single_tickers(tickers: list[str]) -> None:
    """Synchronous single-ticker analysis for dev/testing."""
    results: dict = {}
    for ticker in tickers:
        print(f"Analyzing {ticker}...")
        img = generate_chart_bytes(ticker)
        if not img:
            print(f"  Chart generation failed")
            continue
        result = analyze_single(ticker, img)
        results[ticker] = result
        print(f"  {ticker}: entry={result.get('entry_quality')} confidence={result.get('confidence')}")
        print(f"  Rationale: {result.get('entry_rationale')}")

    # Merge into existing JSON
    existing: dict = {}
    if CHART_SIGNALS_JSON.exists():
        try:
            existing = json.loads(CHART_SIGNALS_JSON.read_text()).get("signals", {})
        except Exception:
            pass
    merged = {**existing, **results}
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "ticker_count": len(merged),
        "signals": merged,
    }
    CHART_SIGNALS_JSON.write_text(json.dumps(output, default=str))
    print(f"Saved → {CHART_SIGNALS_JSON}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("tickers", nargs="*", help="Specific tickers to analyze")
    parser.add_argument("--batch", action="store_true", help="Run batch mode (nightly pipeline)")
    args = parser.parse_args()

    if args.batch:
        run_batch_analysis()
    elif args.tickers:
        run_single_tickers([t.upper() for t in args.tickers])
    else:
        print("Usage: python3 chart_analyzer.py --batch | python3 chart_analyzer.py AAPL MSFT")
