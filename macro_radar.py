#!/usr/bin/env python3
"""
MACRO RADAR — Early Warning System
Detects market regime changes before they happen using empirically-validated signals.

Signals:
  1. VIX             — Market fear gauge (percentile vs 1yr)
  2. Yield Curve     — 2s10s spread (TNX - IRX): inversion = recession signal
  3. Credit HY/IG    — HYG/LQD ratio: spread compression/widening
  4. Copper/Gold     — Dr. Copper economic optimism vs safe haven
  5. Gold/SPY        — Safe haven demand vs risk assets
  6. Oil             — Geopolitical pass-through, CL=F
  7. Defense/SPY     — ITA vs SPY: geopolitical escalation early warning
  8. Dollar (DXY)    — USD strength = EM stress, risk-off
  9. Yen (USDJPY)    — Safe haven currency: falling = fear
  10. Market Breadth  — SPY momentum vs 200d MA (proxy for breadth)

Regime scoring: each signal -2 to +2 → composite → CALM/WATCH/STRESS/ALERT/CRISIS

Output: docs/macro_radar.json
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from typing import Optional

# ── Groq AI analysis ──────────────────────────────────────────────────────────
try:
    from groq import Groq
    _GROQ_KEY = os.environ.get('GROQ_API_KEY', '')
    _groq = Groq(api_key=_GROQ_KEY) if _GROQ_KEY else None
except Exception:
    _groq = None

DOCS = Path('docs')
DOCS.mkdir(exist_ok=True)

# ── Signal definitions ────────────────────────────────────────────────────────
SIGNALS = {
    'vix': {
        'label': 'Volatilidad (VIX)',
        'ticker': '^VIX',
        'direction': 'inverse',   # high VIX = bad
        'description': 'Fear gauge. >30 = stress, >40 = crisis, <15 = complacency',
    },
    'yield_curve': {
        'label': 'Curva Tipos (2s10s)',
        'tickers': ['^TNX', '^IRX'],   # 10yr - 2yr (approx: ^IRX ≈ 3m but close)
        'direction': 'normal',         # positive spread = good, inversion = bad
        'description': '87.5% recession accuracy since 1968. Inversion = -2',
    },
    'credit': {
        'label': 'Crédito HY/IG',
        'tickers': ['HYG', 'LQD'],
        'direction': 'normal',         # higher ratio = tighter spreads = good
        'description': 'HY spread >400bps = systemic stress. Ratio compression = risk-off',
    },
    'copper_gold': {
        'label': 'Cobre/Oro (Dr. Copper)',
        'tickers': ['HG=F', 'GLD'],
        'direction': 'normal',         # higher = economic optimism
        'description': 'Falling = recession pessimism. Most underappreciated indicator',
    },
    'gold_spy': {
        'label': 'Oro vs Mercado',
        'tickers': ['GLD', 'SPY'],
        'direction': 'inverse',        # gold outperforming SPY = risk-off
        'description': 'Gold outperformance signals safe-haven rotation',
    },
    'oil': {
        'label': 'Petróleo (Geopolítico)',
        'ticker': 'CL=F',
        'direction': 'context',        # needs context: spike up = bad
        'description': 'Fastest commodity to price geopolitical conflicts. Spike = risk',
    },
    'defense': {
        'label': 'Defensa vs Mercado',
        'tickers': ['ITA', 'SPY'],
        'direction': 'inverse',        # defense outperforming = geopolitical risk
        'description': 'ITA/XAR vs SPY. Outperformance precedes geopolitical escalations',
    },
    'dollar': {
        'label': 'Dólar (DXY)',
        'ticker': 'DX-Y.NYB',
        'direction': 'context',        # moderate = ok, spike = EM stress
        'description': 'Rising USD = EM stress, global risk-off. Spike = dollar squeeze',
    },
    'yen': {
        'label': 'Yen (Safe Haven)',
        'ticker': 'USDJPY=X',
        'direction': 'normal',         # USDJPY falling (yen strengthening) = fear
        'description': 'USDJPY falling = yen strengthening = risk-off / fear',
    },
    'breadth': {
        'label': 'Amplitud Mercado',
        'tickers': ['SPY'],
        'direction': 'normal',         # SPY above 200d MA = good
        'description': 'SPY vs 200d MA + momentum. Proxy for broad market health',
    },
    # ── Smart Money / Hidden Signals ──────────────────────────────────────
    'skew': {
        'label': 'SKEW Index (Tail Risk)',
        'ticker': '^SKEW',
        'direction': 'inverse',        # high SKEW = institutions buying crash insurance = bad
        'description': 'CBOE SKEW: when VIX is calm but SKEW >130 = institutions buying deep OTM puts. Retail never checks this.',
    },
    'vvix': {
        'label': 'VVIX (Vol of Vol)',
        'ticker': '^VVIX',
        'direction': 'inverse',        # high VVIX = uncertainty about uncertainty = bad
        'description': 'Volatility of VIX. Rising VVIX while VIX is moderate = smart money buying vol insurance. Precedes VIX spikes.',
    },
    'regional_banks': {
        'label': 'Bancos Regionales (KRE)',
        'tickers': ['KRE', 'SPY'],
        'direction': 'normal',         # KRE outperforming = credit system healthy
        'description': 'KRE vs SPY. Regional banks lead credit stress. SVB was -40% before collapse. Underperformance = systemic risk brewing.',
    },
    'small_cap': {
        'label': 'Small Cap vs Large (IWM)',
        'tickers': ['IWM', 'SPY'],
        'direction': 'normal',         # IWM outperforming = broad liquidity = good
        'description': 'IWM/SPY ratio. Small caps access credit differently. Divergence = liquidity concentrating = late cycle signal.',
    },
    'real_yields': {
        'label': 'Yields Reales (TIP/TLT)',
        'tickers': ['TIP', 'TLT'],
        'direction': 'normal',         # TIP outperforming TLT = real yields falling = good for risk
        'description': 'TIP vs TLT proxy for real yield direction. Rising real yields crush growth stocks. Perfect 2022 crash signal.',
    },
}

REGIME_LABELS = {
    (3, 30):   ('CALM',   '#10b981', 'Mercado en calma. Condiciones favorables para operar.'),
    (0, 3):    ('WATCH',  '#84cc16', 'Precaución. Señales mixtas, mantener vigilancia.'),
    (-6, 0):   ('STRESS', '#f59e0b', 'Estrés moderado. Reducir exposición, gestionar riesgo.'),
    (-12, -6): ('ALERT',  '#f97316', 'Alerta elevada. Riesgo sistémico aumentando.'),
    (-30, -12):('CRISIS', '#ef4444', 'Crisis potencial. Capital preservation mode.'),
}


def _fetch(ticker: str, period_days: int = 400) -> Optional[pd.DataFrame]:
    """Fetch historical data for a ticker with retry. Normalizes multi-level columns."""
    start = (datetime.now() - timedelta(days=period_days)).strftime('%Y-%m-%d')
    for attempt in range(3):
        try:
            df = yf.download(ticker, start=start, progress=False, auto_adjust=True)
            if df is None or len(df) < 20:
                continue
            # Flatten multi-level columns (yfinance >=0.2.x returns MultiIndex)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]
            return df
        except Exception as e:
            print(f"  Attempt {attempt+1} failed for {ticker}: {e}")
            time.sleep(2 ** attempt)
    return None


def _percentile(series: pd.Series, current_val: float) -> float:
    """Compute percentile of current_val within the series (0-100)."""
    if series is None or len(series) == 0:
        return 50.0
    return float((series < current_val).mean() * 100)


def _score_vix(df: pd.DataFrame) -> dict:
    """VIX: high = bad. Score -2 to +2."""
    close = df['Close'].dropna()
    current = float(close.iloc[-1])
    pct = _percentile(close, current)
    change_5d = float((close.iloc[-1] / close.iloc[-6] - 1) * 100) if len(close) > 5 else 0

    # Score: VIX level-based
    if current > 40:
        score = -2
    elif current > 30:
        score = -1.5
    elif current > 25:
        score = -1
    elif current > 20:
        score = -0.5
    elif current > 15:
        score = 0.5
    else:
        score = 1

    # Spike bonus: if VIX jumped >30% in 5 days → extra -1
    if change_5d > 30:
        score -= 0.5

    return {
        'current': round(current, 2),
        'percentile': round(pct, 1),
        'score': max(-2, min(2, score)),
        'change_5d': round(change_5d, 1),
        'interpretation': f"VIX {current:.1f} ({'alto' if current > 25 else 'moderado' if current > 18 else 'bajo'})",
    }


def _score_yield_curve(df10: pd.DataFrame, df2: pd.DataFrame) -> dict:
    """2s10s spread. Inversion = recession. Score -2 to +2."""
    c10 = df10['Close'].dropna()
    c2 = df2['Close'].dropna()

    # Align by date
    c10.name = 't10'
    c2.name = 't2'
    aligned = pd.concat([c10, c2], axis=1).dropna()
    if len(aligned) < 10:
        return {'current': 0, 'percentile': 50, 'score': 0, 'interpretation': 'Sin datos'}

    # Spread in bps
    spread = (aligned['t10'] - aligned['t2'])
    current = float(spread.iloc[-1])
    pct = _percentile(spread, current)

    # Score
    if current < -0.5:    # deeply inverted
        score = -2
    elif current < 0:     # inverted
        score = -1.5
    elif current < 0.25:  # flat
        score = -0.5
    elif current < 0.75:  # normal
        score = 0.5
    elif current < 1.5:   # healthy
        score = 1.5
    else:
        score = 2          # very steep = strong expansion

    state = 'invertida' if current < 0 else 'plana' if current < 0.3 else 'normal' if current < 1.0 else 'empinada'
    return {
        'current': round(current * 100, 1),  # display in bps
        'percentile': round(pct, 1),
        'score': score,
        'interpretation': f"Spread 2s10s: {current*100:.0f}bps ({state})",
    }


def _score_ratio(df_num: pd.DataFrame, df_den: pd.DataFrame, signal_key: str) -> dict:
    """Ratio-based signal (copper/gold, gold/spy, credit, defense)."""
    c_num = df_num['Close'].dropna()
    c_den = df_den['Close'].dropna()

    c_num.name = 'num'
    c_den.name = 'den'
    aligned = pd.concat([c_num, c_den], axis=1).dropna()
    if len(aligned) < 20:
        return {'current': 0, 'percentile': 50, 'score': 0, 'interpretation': 'Sin datos'}

    ratio = aligned['num'] / aligned['den']
    current = float(ratio.iloc[-1])
    pct = _percentile(ratio, current)

    # 20d momentum of ratio
    mom_20d = float((ratio.iloc[-1] / ratio.iloc[-21] - 1) * 100) if len(ratio) > 20 else 0
    mom_5d  = float((ratio.iloc[-1] / ratio.iloc[-6]  - 1) * 100) if len(ratio) > 5  else 0

    if signal_key == 'credit':
        # HYG/LQD: higher = tighter spreads = risk-on = good
        if pct > 70 and mom_20d > 0:
            score = 2
        elif pct > 50:
            score = 1
        elif pct > 30:
            score = 0
        elif pct > 15:
            score = -1
        else:
            score = -2
        label = 'spreads apretados' if pct > 60 else 'spreads amplios' if pct < 30 else 'spreads neutros'
        interp = f"HYG/LQD ratio en p{pct:.0f} ({label})"

    elif signal_key == 'copper_gold':
        # Copper/Gold: higher = economic optimism = good
        if pct > 70 and mom_20d > 0:
            score = 2
        elif pct > 55:
            score = 1
        elif pct > 40:
            score = 0
        elif pct > 20:
            score = -1
        else:
            score = -2
        trend = 'subiendo' if mom_5d > 1 else 'cayendo' if mom_5d < -1 else 'estable'
        interp = f"Cobre/Oro en p{pct:.0f}, {trend} ({mom_5d:+.1f}% 5d)"

    elif signal_key == 'gold_spy':
        # Gold/SPY: higher = gold outperforming = risk-off = bad
        if pct > 75 and mom_20d > 3:
            score = -2
        elif pct > 60:
            score = -1
        elif pct > 40:
            score = 0
        elif pct > 25:
            score = 1
        else:
            score = 2
        label = 'superando mercado' if pct > 60 else 'rezagado' if pct < 40 else 'en línea'
        interp = f"Oro {label} vs SPY (p{pct:.0f})"

    elif signal_key == 'defense':
        # Defense/SPY: higher = defense outperforming = geopolitical risk = bad
        if pct > 80 and mom_20d > 3:
            score = -2
        elif pct > 65:
            score = -1
        elif pct > 45:
            score = 0
        elif pct > 30:
            score = 1
        else:
            score = 2
        label = 'superando' if pct > 60 else 'rezagado' if pct < 40 else 'en línea'
        interp = f"Defensa (ITA) {label} vs SPY (p{pct:.0f})"
    elif signal_key == 'regional_banks':
        # KRE/SPY: underperforming = credit stress brewing = bad
        if pct < 20 and mom_20d < -3:
            score = -2
        elif pct < 30:
            score = -1
        elif pct < 45:
            score = -0.5
        elif pct > 60:
            score = 1
        else:
            score = 0
        trend = 'rezagado' if pct < 35 else 'en línea' if pct < 60 else 'superando'
        interp = f"KRE/SPY {trend} (p{pct:.0f}, {mom_20d:+.1f}% 20d)"

    elif signal_key == 'small_cap':
        # IWM/SPY: underperforming = liquidity concentrating = late cycle = bad
        if pct < 20 and mom_20d < -3:
            score = -2
        elif pct < 30:
            score = -1
        elif pct < 45:
            score = -0.5
        elif pct > 65:
            score = 1.5
        elif pct > 50:
            score = 0.5
        else:
            score = 0
        trend = 'rezagado (liquidez concentrada)' if pct < 35 else 'en línea' if pct < 60 else 'superando (risk-on)'
        interp = f"IWM/SPY {trend} (p{pct:.0f})"

    elif signal_key == 'real_yields':
        # TIP/TLT: falling ratio = rising real yields = bad for risk assets
        if pct < 15 and mom_20d < -3:
            score = -2
        elif pct < 25:
            score = -1
        elif pct < 40:
            score = -0.5
        elif pct > 65:
            score = 1
        else:
            score = 0
        trend = 'yields reales subiendo (presión growth)' if pct < 35 else 'neutrales' if pct < 60 else 'yields reales bajando (favorable)'
        interp = f"TIP/TLT en p{pct:.0f} ({trend})"

    else:
        score = 0
        interp = 'Ratio'

    return {
        'current': round(current, 4),
        'percentile': round(pct, 1),
        'score': max(-2, min(2, score)),
        'change_5d': round(mom_5d, 1),
        'change_20d': round(mom_20d, 1),
        'interpretation': interp,
    }


def _score_oil(df: pd.DataFrame) -> dict:
    """Oil: spike = geopolitical risk = bad. Moderate rise = economic activity = neutral."""
    close = df['Close'].dropna()
    current = float(close.iloc[-1])
    pct = _percentile(close, current)
    change_5d  = float((close.iloc[-1] / close.iloc[-6]  - 1) * 100) if len(close) > 5  else 0
    change_20d = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 20 else 0

    # Spike detection: >10% in 5 days or >15% in 20 days = geopolitical signal
    if change_5d > 10 or change_20d > 20:
        score = -2
        label = 'spike geopolitico'
    elif change_5d > 5:
        score = -1
        label = 'subida rapida'
    elif pct > 85:
        score = -0.5
        label = 'precio elevado'
    elif pct < 20 and change_5d < 0:
        score = -0.5
        label = 'caida brusca (recesion?)'
    else:
        score = 0
        label = 'rango normal'

    return {
        'current': round(current, 2),
        'percentile': round(pct, 1),
        'score': max(-2, min(2, score)),
        'change_5d': round(change_5d, 1),
        'change_20d': round(change_20d, 1),
        'interpretation': f"Petroleo ${current:.1f} ({label})",
    }


def _score_dollar(df: pd.DataFrame) -> dict:
    """DXY: moderate = ok; rapid spike = EM stress = bad; crash = USD panic."""
    close = df['Close'].dropna()
    current = float(close.iloc[-1])
    pct = _percentile(close, current)
    change_5d  = float((close.iloc[-1] / close.iloc[-6]  - 1) * 100) if len(close) > 5  else 0
    change_20d = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 20 else 0

    # Spike in USD = EM stress, dollar crunch
    if change_5d > 2 and pct > 80:
        score = -1.5
        label = 'spike dolar (EM stress)'
    elif pct > 85:
        score = -1
        label = 'dolar muy fuerte'
    elif pct < 10:
        score = -0.5
        label = 'dolar muy debil'
    elif 35 < pct < 65:
        score = 1
        label = 'rango neutro'
    else:
        score = 0.5
        label = 'ligeramente' + (' fuerte' if pct > 50 else ' debil')

    return {
        'current': round(current, 2),
        'percentile': round(pct, 1),
        'score': max(-2, min(2, score)),
        'change_5d': round(change_5d, 2),
        'change_20d': round(change_20d, 2),
        'interpretation': f"DXY {current:.1f} ({label})",
    }


def _score_yen(df: pd.DataFrame) -> dict:
    """USDJPY: falling (yen strengthening) = risk-off = bad."""
    close = df['Close'].dropna()
    current = float(close.iloc[-1])
    pct = _percentile(close, current)
    change_5d  = float((close.iloc[-1] / close.iloc[-6]  - 1) * 100) if len(close) > 5  else 0
    change_20d = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 20 else 0

    # USDJPY falling = yen strengthening = risk-off = bad
    if change_5d < -2:
        score = -2
        label = 'yen fortaleciendose (miedo)'
    elif change_5d < -1 or pct < 20:
        score = -1
        label = 'yen fuerte'
    elif pct > 75:
        score = 1
        label = 'yen debil (risk-on)'
    elif 35 < pct < 65:
        score = 0.5
        label = 'rango neutro'
    else:
        score = 0
        label = 'ligeramente' + (' debil' if pct > 50 else ' fuerte')

    return {
        'current': round(current, 2),
        'percentile': round(pct, 1),
        'score': max(-2, min(2, score)),
        'change_5d': round(change_5d, 2),
        'change_20d': round(change_20d, 2),
        'interpretation': f"USD/JPY {current:.1f} ({label})",
    }


def _score_breadth(df_spy: pd.DataFrame) -> dict:
    """Market breadth proxy: SPY vs 200d MA + 50d MA."""
    close = df_spy['Close'].dropna()
    current = float(close.iloc[-1])

    ma50  = float(close.iloc[-50:].mean())  if len(close) >= 50  else None
    ma200 = float(close.iloc[-200:].mean()) if len(close) >= 200 else None
    pct_from_200 = float((current / ma200 - 1) * 100) if ma200 else 0
    pct_from_50  = float((current / ma50  - 1) * 100) if ma50  else 0
    change_20d   = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 20 else 0

    # Score: above 200d + momentum = good
    if pct_from_200 > 5 and pct_from_50 > 2:
        score = 2
        label = 'tendencia alcista fuerte'
    elif pct_from_200 > 0 and pct_from_50 > -2:
        score = 1
        label = 'por encima MA200'
    elif pct_from_200 > -3:
        score = 0
        label = 'en zona de soporte'
    elif pct_from_200 > -7:
        score = -1
        label = 'corrección moderada'
    else:
        score = -2
        label = 'mercado bajista'

    return {
        'current': round(current, 2),
        'ma50': round(ma50, 2) if ma50 else None,
        'ma200': round(ma200, 2) if ma200 else None,
        'pct_from_200': round(pct_from_200, 1),
        'pct_from_50': round(pct_from_50, 1),
        'score': max(-2, min(2, score)),
        'change_20d': round(change_20d, 1),
        'interpretation': f"SPY {pct_from_200:+.1f}% vs MA200 ({label})",
    }


def _score_skew(df: pd.DataFrame) -> dict:
    """CBOE SKEW: >130 = institutions buying deep OTM puts = tail risk = bad."""
    close = df['Close'].dropna()
    current = float(close.iloc[-1])
    pct = _percentile(close, current)
    change_5d = float((close.iloc[-1] / close.iloc[-6] - 1) * 100) if len(close) > 5 else 0

    # Level-based: SKEW above 130 means institutional crash insurance demand
    if current > 145:
        score = -2
        label = 'crash insurance extremo'
    elif current > 135:
        score = -1.5
        label = 'alta demanda put OTM'
    elif current > 125:
        score = -0.5
        label = 'precaución institucional'
    elif current > 115:
        score = 0.5
        label = 'rango normal'
    else:
        score = 1
        label = 'baja demanda tail risk'

    return {
        'current': round(current, 2),
        'percentile': round(pct, 1),
        'score': max(-2, min(2, score)),
        'change_5d': round(change_5d, 1),
        'interpretation': f"SKEW {current:.0f} ({label})",
    }


def _score_vvix(df: pd.DataFrame) -> dict:
    """VVIX: volatility of VIX. High percentile = smart money buying vol insurance = bad."""
    close = df['Close'].dropna()
    current = float(close.iloc[-1])
    pct = _percentile(close, current)
    change_5d = float((close.iloc[-1] / close.iloc[-6] - 1) * 100) if len(close) > 5 else 0

    # Percentile-based: high VVIX precedes VIX spikes
    if pct > 85:
        score = -2
        label = 'extrema incertidumbre sobre vol'
    elif pct > 70:
        score = -1
        label = 'incertidumbre elevada'
    elif pct > 55:
        score = -0.5
        label = 'precaución'
    elif pct > 35:
        score = 0.5
        label = 'rango normal'
    else:
        score = 1
        label = 'baja incertidumbre'

    return {
        'current': round(current, 2),
        'percentile': round(pct, 1),
        'score': max(-2, min(2, score)),
        'change_5d': round(change_5d, 1),
        'interpretation': f"VVIX {current:.1f} (p{pct:.0f}, {label})",
    }


def _get_regime(composite: float) -> dict:
    """Map composite score to regime label."""
    for (low, high), (name, color, desc) in REGIME_LABELS.items():
        if low <= composite < high:
            return {'name': name, 'color': color, 'description': desc}
    return {'name': 'WATCH', 'color': '#84cc16', 'description': 'Señales mixtas, mantener vigilancia.'}


def _groq_analysis(signals: dict, composite: float, regime: str) -> Optional[str]:
    """Ask Groq AI for a narrative analysis of the current signals."""
    if not _groq:
        return None

    summary_lines = []
    for key, sig in signals.items():
        label = SIGNALS[key]['label']
        score = sig.get('score', 0)
        interp = sig.get('interpretation', '')
        summary_lines.append(f"- {label}: score={score:+.1f}, {interp}")

    summary = '\n'.join(summary_lines)
    prompt = f"""Eres un analista macro de mercados financieros con 20 años de experiencia.
Analiza estos indicadores macro actuales y proporciona un análisis conciso (3-4 oraciones)
del régimen de mercado actual. La puntuación compuesta es {composite:.1f}/20 → régimen {regime}.

Señales actuales:
{summary}

Proporciona:
1. Una interpretación del régimen actual citando las señales más relevantes
2. El principal riesgo o catalizador a vigilar
3. Una recomendación de posicionamiento general (no ticker específico)

Responde en español, tono profesional, máximo 120 palabras."""

    try:
        resp = _groq.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=200,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"  Groq analysis failed: {e}")
        return None


# ── Historical episode fingerprints ───────────────────────────────────────────
# Each episode is defined by approximate percentile values of key signals at peak stress.
# Used to compute pattern similarity with the current macro environment.
_HISTORICAL_EPISODES = [
    {
        'id': 'ukraine_war_2022',
        'name': 'Guerra Ucrania',
        'date': 'Feb 2022',
        'duration_days': 20,
        'fingerprint': {
            'vix': 70, 'copper_gold': 55, 'gold_spy': 90,
            'oil': 99, 'defense': 99, 'credit': 45,
            'regional_banks': 50, 'small_cap': 40, 'real_yields': 70,
        },
        'outcome': {
            'spy_30d': -8, 'spy_90d': -15, 'spy_180d': -20,
            'description': 'Inicio del mercado bajista 2022. SPY -20% en 6 meses.',
        },
        'key_difference': 'Geopolítica + inflación estructural. No fue shock temporal — dio paso al ciclo bajista completo.',
    },
    {
        'id': 'bear_market_2022',
        'name': 'Mercado Bajista 2022',
        'date': 'Ene-Dic 2022',
        'duration_days': 280,
        'fingerprint': {
            'vix': 65, 'copper_gold': 30, 'gold_spy': 60,
            'oil': 85, 'defense': 80, 'credit': 25,
            'regional_banks': 40, 'small_cap': 30, 'real_yields': 15,
        },
        'outcome': {
            'spy_30d': -8, 'spy_90d': -18, 'spy_180d': -22,
            'description': 'SPY -22% en el año. NASDAQ -33%. Peor año desde 2008.',
        },
        'key_difference': 'Impulsado por yields reales al alza. Las growth stocks sufrieron más.',
    },
    {
        'id': 'svb_crisis_2023',
        'name': 'Crisis SVB',
        'date': 'Mar 2023',
        'duration_days': 14,
        'fingerprint': {
            'vix': 75, 'copper_gold': 40, 'gold_spy': 75,
            'oil': 40, 'defense': 45, 'credit': 20,
            'regional_banks': 5, 'small_cap': 35, 'real_yields': 50,
        },
        'outcome': {
            'spy_30d': 5, 'spy_90d': 12, 'spy_180d': 20,
            'description': 'Susto contenido. FED intervino. SPY +12% en 3 meses.',
        },
        'key_difference': 'Riesgo sistémico pero localizado. Bancos regionales fue la señal clave (KRE -40%).',
    },
    {
        'id': 'covid_crash_2020',
        'name': 'COVID Crash',
        'date': 'Feb-Mar 2020',
        'duration_days': 33,
        'fingerprint': {
            'vix': 98, 'copper_gold': 20, 'gold_spy': 85,
            'oil': 5, 'defense': 50, 'credit': 5,
            'regional_banks': 10, 'small_cap': 15, 'real_yields': 30,
        },
        'outcome': {
            'spy_30d': -34, 'spy_90d': 22, 'spy_180d': 38,
            'description': 'SPY -34% en 33 días. Rebote en V completo en 5 meses.',
        },
        'key_difference': 'Shock exógeno puro. Sin precedentes. La velocidad del rebote también fue única.',
    },
    {
        'id': 'gfc_2008',
        'name': 'Crisis Financiera Global',
        'date': 'Sep-Nov 2008',
        'duration_days': 150,
        'fingerprint': {
            'vix': 100, 'copper_gold': 5, 'gold_spy': 70,
            'oil': 15, 'defense': 60, 'credit': 2,
            'regional_banks': 5, 'small_cap': 10, 'real_yields': 20,
        },
        'outcome': {
            'spy_30d': -30, 'spy_90d': -40, 'spy_180d': -45,
            'description': 'SPY -55% desde máximos. Recuperación tardó 5 años.',
        },
        'key_difference': 'Colapso crediticio sistémico. Crédito HY y bancos regionales en colapso total.',
    },
    {
        'id': 'china_slowdown_2015',
        'name': 'Desaceleración China',
        'date': 'Ago 2015',
        'duration_days': 45,
        'fingerprint': {
            'vix': 80, 'copper_gold': 12, 'gold_spy': 55,
            'oil': 10, 'defense': 50, 'credit': 35,
            'regional_banks': 45, 'small_cap': 30, 'real_yields': 45,
        },
        'outcome': {
            'spy_30d': -11, 'spy_90d': -5, 'spy_180d': 8,
            'description': 'Corrección -14%. Recuperación completa en 6 meses.',
        },
        'key_difference': 'Cobre/Oro muy bajo = preocupación recesión global. Corrección sin crisis bancaria.',
    },
]

_MATCH_KEYS = ['vix', 'copper_gold', 'gold_spy', 'oil', 'defense', 'credit', 'regional_banks', 'small_cap', 'real_yields']


def _scan_index_breakouts() -> list:
    """
    Monitorea los 6 índices principales buscando roturas de medias clave.
    Detecta: MA50d, MA200d (~10 meses), MA10m (mensual), MA20m (mensual).
    Retorna lista de eventos ordenada por frescura y magnitud.

    Campos por evento:
      index, index_name, ma_key, ma_label, current_price, ma_value,
      pct_from_ma, direction, fresh_cross, days_since_cross, signal
    """
    INDICES = [
        ('QQQ', 'Nasdaq 100 (QQQ)'),
        ('SPY', 'S&P 500 (SPY)'),
        ('IWM', 'Russell 2000 (IWM)'),
        ('DIA', 'Dow Jones (DIA)'),
        ('EWG', 'DAX / Alemania (EWG)'),
        ('EEM', 'Mercados Emergentes (EEM)'),
    ]

    MA_DEFS = [
        {'key': 'ma50d',  'label': 'MA 50d',   'window': 50,  'freq': 'D', 'fresh_days': 5},
        {'key': 'ma200d', 'label': 'MA 200d',  'window': 200, 'freq': 'D', 'fresh_days': 5},
        {'key': 'ma10m',  'label': 'MA 10 mes','window': 10,  'freq': 'M', 'fresh_days': 35},
        {'key': 'ma20m',  'label': 'MA 20 mes','window': 20,  'freq': 'M', 'fresh_days': 35},
    ]

    results = []

    for ticker, name in INDICES:
        print(f"  Breakouts: {ticker}...")
        df = _fetch(ticker, period_days=1800)
        if df is None or len(df) < 60:
            continue

        close = df['Close'].dropna()
        current_price = float(close.iloc[-1])
        last_date = close.index[-1]

        for ma_def in MA_DEFS:
            try:
                if ma_def['freq'] == 'D':
                    if len(close) < ma_def['window'] + 10:
                        continue
                    ma_series = close.rolling(ma_def['window']).mean().dropna()
                else:
                    # Monthly close → rolling MA → ffill to daily
                    try:
                        monthly = close.resample('ME').last().dropna()
                    except Exception:
                        monthly = close.resample('M').last().dropna()
                    if len(monthly) < ma_def['window'] + 3:
                        continue
                    ma_monthly = monthly.rolling(ma_def['window']).mean().dropna()
                    ma_series = ma_monthly.reindex(close.index, method='ffill').dropna()

                if len(ma_series) < 15:
                    continue

                ma_current = float(ma_series.iloc[-1])
                pct_from_ma = (current_price / ma_current - 1) * 100
                currently_above = current_price > ma_current

                # Align price and MA on same dates
                combined = pd.concat(
                    [close.rename('price'), ma_series.rename('ma')], axis=1
                ).dropna()

                if len(combined) < ma_def['fresh_days'] + 5:
                    continue

                # Was price on the other side N days ago?
                ref_row = combined.iloc[-(ma_def['fresh_days'] + 1)]
                was_above = bool(ref_row['price'] > ref_row['ma'])
                fresh_cross = (currently_above != was_above)

                # Find exact days since last cross (look back 60 calendar days)
                lookback_n = min(60, len(combined) - 1)
                recent = combined.tail(lookback_n)
                above_flags = (recent['price'] > recent['ma'])
                changes = (above_flags != above_flags.shift(1)).fillna(False)
                cross_dates = above_flags[changes].index
                if len(cross_dates) > 0:
                    last_cross = cross_dates[-1]
                    days_since = int((last_date - last_cross).days)
                else:
                    days_since = 999

                # Signal classification
                if fresh_cross and not currently_above:
                    signal = 'BEARISH_BREAK'
                elif fresh_cross and currently_above:
                    signal = 'BULLISH_BREAK'
                elif not currently_above:
                    signal = 'BELOW'
                else:
                    signal = 'ABOVE'

                # Only include: fresh crosses OR significant distance (>3% from MA)
                if not fresh_cross and abs(pct_from_ma) < 3:
                    continue

                results.append({
                    'index':          ticker,
                    'index_name':     name,
                    'ma_key':         ma_def['key'],
                    'ma_label':       ma_def['label'],
                    'current_price':  round(current_price, 2),
                    'ma_value':       round(ma_current, 2),
                    'pct_from_ma':    round(pct_from_ma, 2),
                    'direction':      'ABOVE' if currently_above else 'BELOW',
                    'fresh_cross':    fresh_cross,
                    'days_since_cross': days_since,
                    'signal':         signal,
                })

            except Exception as e:
                print(f"    {ticker}/{ma_def['key']} error: {e}")
                continue

    # Sort: fresh BEARISH first, then fresh BULLISH, then by abs pct from MA
    def sort_key(r):
        fresh_order = 0 if r['fresh_cross'] else 1
        bearish_order = 0 if r['signal'] == 'BEARISH_BREAK' else (1 if r['signal'] == 'BULLISH_BREAK' else 2)
        return (fresh_order, bearish_order, -abs(r['pct_from_ma']))

    results.sort(key=sort_key)
    return results


def _send_telegram_breakout_alert(breakouts: list) -> None:
    """Send immediate Telegram alert for fresh index MA breakouts."""
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id   = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not bot_token or not chat_id:
        return

    fresh = [b for b in breakouts if b['fresh_cross']]
    if not fresh:
        return

    lines = ['📊 <b>Macro Radar — Roturas de Índices</b>', '']

    bearish = [b for b in fresh if b['signal'] == 'BEARISH_BREAK']
    bullish = [b for b in fresh if b['signal'] == 'BULLISH_BREAK']

    if bearish:
        lines.append('🔴 <b>Roturas BAJISTAS (ventas / cautela):</b>')
        for b in bearish:
            lines.append(
                f"  ↓ <b>{b['index']}</b> ({b['index_name'].split('(')[0].strip()}) "
                f"ha roto la <b>{b['ma_label']}</b> a la baja\n"
                f"    ${b['current_price']:.2f} vs MA ${b['ma_value']:.2f} "
                f"({b['pct_from_ma']:+.1f}%)"
            )

    if bullish:
        if bearish:
            lines.append('')
        lines.append('🟢 <b>Roturas ALCISTAS (recuperación):</b>')
        for b in bullish:
            lines.append(
                f"  ↑ <b>{b['index']}</b> ({b['index_name'].split('(')[0].strip()}) "
                f"ha recuperado la <b>{b['ma_label']}</b>\n"
                f"    ${b['current_price']:.2f} vs MA ${b['ma_value']:.2f} "
                f"({b['pct_from_ma']:+.1f}%)"
            )

    lines.append('')
    lines.append('<i>Detectado hoy · Macro Radar</i>')

    text = '\n'.join(lines)
    try:
        import requests as _req
        _req.post(
            f'https://api.telegram.org/bot{bot_token}/sendMessage',
            json={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML',
                  'disable_web_page_preview': True},
            timeout=10,
        )
        print(f"  Telegram breakout alert sent ({len(fresh)} fresh crosses)")
    except Exception as e:
        print(f"  Telegram breakout alert failed: {e}")


def _compute_historical_analogs(signals: dict) -> list:
    """Compare current signal percentiles to historical episodes via mean absolute deviation."""
    # Build current percentile vector
    current_vec: dict[str, float] = {}
    for k in _MATCH_KEYS:
        sig = signals.get(k, {})
        pct = sig.get('percentile')
        if pct is None:
            pct = 50.0
        current_vec[k] = float(pct)

    results = []
    for ep in _HISTORICAL_EPISODES:
        fp = ep['fingerprint']
        diffs = [abs(current_vec.get(k, 50) - fp.get(k, 50)) for k in _MATCH_KEYS]
        mad = sum(diffs) / len(diffs)
        similarity = max(0.0, 100.0 - mad)

        # Top 3 matching/diverging signals for context
        signal_deltas = sorted(
            [(k, abs(current_vec.get(k, 50) - fp.get(k, 50))) for k in _MATCH_KEYS],
            key=lambda x: x[1],
        )
        closest = [k for k, _ in signal_deltas[:3]]    # signals most similar
        diverging = [k for k, _ in signal_deltas[-2:]]  # signals most different

        results.append({
            'id': ep['id'],
            'name': ep['name'],
            'date': ep['date'],
            'duration_days': ep['duration_days'],
            'similarity': round(similarity, 1),
            'outcome': ep['outcome'],
            'key_difference': ep['key_difference'],
            'closest_signals': closest,
            'diverging_signals': diverging,
        })

    results.sort(key=lambda x: x['similarity'], reverse=True)
    return results[:3]


def _identify_systemic_risks(signals: dict) -> list:
    """Rules engine: map current signal state to named systemic risks."""
    risks = []

    def pct(key: str) -> float:
        return float(signals.get(key, {}).get('percentile') or 50)

    def chg20(key: str) -> float:
        return float(signals.get(key, {}).get('change_20d') or 0)

    def chg5(key: str) -> float:
        return float(signals.get(key, {}).get('change_5d') or 0)

    def val(key: str, field: str = 'current') -> float:
        return float(signals.get(key, {}).get(field) or 0)

    # Geopolitical escalation
    if pct('defense') > 85 and chg20('oil') > 15:
        risks.append({
            'id': 'geopolitical',
            'name': 'Escalada Geopolítica',
            'severity': 'HIGH',
            'color': '#ef4444',
            'description': f"Defensa (ITA) en p{pct('defense'):.0f} + petróleo +{chg20('oil'):.0f}% (20d). Institucionales rotando a sectores de guerra.",
            'implication': 'Reducir cíclicos. Energía y defensa como cobertura parcial.',
        })

    # Recession signal from Dr. Copper
    if pct('copper_gold') < 15:
        risks.append({
            'id': 'recession_signal',
            'name': 'Señal de Recesión (Dr. Copper)',
            'severity': 'HIGH',
            'color': '#f97316',
            'description': f"Cobre/Oro en p{pct('copper_gold'):.0f} — el mercado descuenta contracción económica global.",
            'implication': 'Sobreponderar defensivos: consumer staples, healthcare, utilities.',
        })

    # Volatility regime change
    if pct('vvix') > 85 and val('skew', 'current') > 130:
        risks.append({
            'id': 'vol_regime',
            'name': 'Cambio de Régimen de Volatilidad',
            'severity': 'HIGH',
            'color': '#f97316',
            'description': f"VVIX p{pct('vvix'):.0f} + SKEW {val('skew','current'):.0f} — institucionales comprando seguro tail risk masivamente.",
            'implication': 'Reducir apalancamiento. Puts como cobertura eficiente vs caro en vol alta.',
        })

    # Safe haven rotation
    if pct('gold_spy') > 85:
        risks.append({
            'id': 'safe_haven_rotation',
            'name': 'Rotación a Activos Refugio',
            'severity': 'MEDIUM',
            'color': '#f59e0b',
            'description': f"Oro supera al mercado en p{pct('gold_spy'):.0f} — capital saliendo de renta variable hacia activos seguros.",
            'implication': 'El smart money está reduciendo riesgo. Señal de cautela para nuevas entradas.',
        })

    # Banking system stress
    if pct('regional_banks') < 20 and chg20('regional_banks') < -8:
        risks.append({
            'id': 'banking_stress',
            'name': 'Estrés Sistema Bancario',
            'severity': 'HIGH',
            'color': '#ef4444',
            'description': f"KRE/SPY en p{pct('regional_banks'):.0f}, -{abs(chg20('regional_banks')):.1f}% (20d). Patrón precursor de SVB 2023.",
            'implication': 'Vigilar spreads de crédito. Evitar financieras regionales.',
        })

    # Yield curve inversion
    yc_spread = val('yield_curve', 'current')
    if yc_spread < 0:
        risks.append({
            'id': 'yield_inversion',
            'name': 'Inversión Curva de Tipos',
            'severity': 'HIGH',
            'color': '#f97316',
            'description': f"2s10s en {yc_spread:.0f}bps — señal con 87.5% precisión histórica. Recesión típicamente en 12-18 meses.",
            'implication': 'Escalar hacia defensivos gradualmente. No actuar de golpe — el lag puede ser largo.',
        })

    # Dollar squeeze
    if pct('dollar') > 88 and chg5('dollar') > 1.5:
        risks.append({
            'id': 'dollar_squeeze',
            'name': 'Dollar Squeeze',
            'severity': 'HIGH',
            'color': '#ef4444',
            'description': f"DXY en p{pct('dollar'):.0f} subiendo rápido (+{chg5('dollar'):.1f}% 5d) — estrés en emergentes y carry trades.",
            'implication': 'Salir de posiciones en mercados emergentes. Riesgo de crisis EM.',
        })

    # VIX spike
    vix_val = val('vix', 'current')
    if vix_val > 30 and chg5('vix') > 25:
        severity = 'CRITICAL' if vix_val > 40 else 'HIGH'
        color = '#ef4444'
        risks.append({
            'id': 'vix_spike',
            'name': 'Spike de Volatilidad' + (' Extremo' if vix_val > 40 else ''),
            'severity': severity,
            'color': color,
            'description': f"VIX {vix_val:.0f} (+{chg5('vix'):.0f}% en 5d) — máximo miedo de corto plazo.",
            'implication': 'Momento de máximo miedo = posible punto de entrada value si los fundamentales no han cambiado.',
        })

    # Credit stress
    if pct('credit') < 20:
        risks.append({
            'id': 'credit_stress',
            'name': 'Estrés de Crédito HY',
            'severity': 'HIGH',
            'color': '#ef4444',
            'description': f"HYG/LQD en p{pct('credit'):.0f} — spreads de alto rendimiento ampliándose. Señal precursora de recesión.",
            'implication': 'Evitar high yield. Crédito investment grade o cash.',
        })

    if not risks:
        risks.append({
            'id': 'none',
            'name': 'Sin riesgos sistémicos activos',
            'severity': 'LOW',
            'color': '#10b981',
            'description': 'Condiciones de mercado dentro de parámetros normales en todos los indicadores sistémicos.',
            'implication': 'Condiciones favorables para mantener exposición normal al mercado.',
        })

    return risks


def run_macro_radar() -> dict:
    """Main function: fetch all signals, score, and output JSON."""
    print("=== MACRO RADAR — Early Warning System ===")
    print(f"Running at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {}
    errors = []

    # ── 1. VIX ─────────────────────────────────────────────────────────────
    print("Fetching VIX...")
    df = _fetch('^VIX')
    if df is not None:
        results['vix'] = _score_vix(df)
        print(f"  VIX: {results['vix']['current']} → score {results['vix']['score']:+.1f}")
    else:
        errors.append('vix')
        results['vix'] = {'current': None, 'score': 0, 'interpretation': 'Sin datos'}

    # ── 2. Yield Curve (2s10s) ────────────────────────────────────────────
    print("Fetching yield curve (TNX, IRX)...")
    df10 = _fetch('^TNX')
    df2  = _fetch('^IRX')
    if df10 is not None and df2 is not None:
        results['yield_curve'] = _score_yield_curve(df10, df2)
        print(f"  Yield Curve: {results['yield_curve']['current']}bps → score {results['yield_curve']['score']:+.1f}")
    else:
        errors.append('yield_curve')
        results['yield_curve'] = {'current': None, 'score': 0, 'interpretation': 'Sin datos'}

    # ── 3. Credit spreads (HYG/LQD) ──────────────────────────────────────
    print("Fetching credit spreads (HYG, LQD)...")
    df_hyg = _fetch('HYG')
    df_lqd = _fetch('LQD')
    if df_hyg is not None and df_lqd is not None:
        results['credit'] = _score_ratio(df_hyg, df_lqd, 'credit')
        print(f"  Credit: ratio {results['credit']['current']} → score {results['credit']['score']:+.1f}")
    else:
        errors.append('credit')
        results['credit'] = {'current': None, 'score': 0, 'interpretation': 'Sin datos'}

    # ── 4. Copper/Gold ────────────────────────────────────────────────────
    print("Fetching Copper/Gold (HG=F, GLD)...")
    df_cu  = _fetch('HG=F')
    df_gld = _fetch('GLD')
    if df_cu is not None and df_gld is not None:
        results['copper_gold'] = _score_ratio(df_cu, df_gld, 'copper_gold')
        print(f"  Copper/Gold: ratio {results['copper_gold']['current']} → score {results['copper_gold']['score']:+.1f}")
    else:
        errors.append('copper_gold')
        results['copper_gold'] = {'current': None, 'score': 0, 'interpretation': 'Sin datos'}

    # ── 5. Gold/SPY ───────────────────────────────────────────────────────
    print("Fetching Gold/SPY (GLD, SPY)...")
    df_spy = _fetch('SPY')
    if df_gld is not None and df_spy is not None:
        results['gold_spy'] = _score_ratio(df_gld, df_spy, 'gold_spy')
        print(f"  Gold/SPY: ratio {results['gold_spy']['current']} → score {results['gold_spy']['score']:+.1f}")
    else:
        errors.append('gold_spy')
        results['gold_spy'] = {'current': None, 'score': 0, 'interpretation': 'Sin datos'}

    # ── 6. Oil ────────────────────────────────────────────────────────────
    print("Fetching Oil (CL=F)...")
    df_oil = _fetch('CL=F')
    if df_oil is not None:
        results['oil'] = _score_oil(df_oil)
        print(f"  Oil: ${results['oil']['current']} → score {results['oil']['score']:+.1f}")
    else:
        errors.append('oil')
        results['oil'] = {'current': None, 'score': 0, 'interpretation': 'Sin datos'}

    # ── 7. Defense vs SPY (ITA/SPY) ───────────────────────────────────────
    print("Fetching Defense/SPY (ITA, SPY)...")
    df_ita = _fetch('ITA')
    if df_ita is not None and df_spy is not None:
        results['defense'] = _score_ratio(df_ita, df_spy, 'defense')
        print(f"  Defense: ratio {results['defense']['current']} → score {results['defense']['score']:+.1f}")
    else:
        errors.append('defense')
        results['defense'] = {'current': None, 'score': 0, 'interpretation': 'Sin datos'}

    # ── 8. Dollar (DXY) ───────────────────────────────────────────────────
    print("Fetching Dollar (DX-Y.NYB)...")
    df_dxy = _fetch('DX-Y.NYB')
    if df_dxy is not None:
        results['dollar'] = _score_dollar(df_dxy)
        print(f"  Dollar: {results['dollar']['current']} → score {results['dollar']['score']:+.1f}")
    else:
        errors.append('dollar')
        results['dollar'] = {'current': None, 'score': 0, 'interpretation': 'Sin datos'}

    # ── 9. Yen (USDJPY) ───────────────────────────────────────────────────
    print("Fetching Yen (USDJPY=X)...")
    df_yen = _fetch('USDJPY=X')
    if df_yen is not None:
        results['yen'] = _score_yen(df_yen)
        print(f"  Yen: {results['yen']['current']} → score {results['yen']['score']:+.1f}")
    else:
        errors.append('yen')
        results['yen'] = {'current': None, 'score': 0, 'interpretation': 'Sin datos'}

    # ── 10. Breadth (SPY vs MAs) ──────────────────────────────────────────
    print("Computing market breadth (SPY)...")
    if df_spy is not None:
        results['breadth'] = _score_breadth(df_spy)
        print(f"  Breadth: SPY {results['breadth']['pct_from_200']:+.1f}% vs MA200 → score {results['breadth']['score']:+.1f}")
    else:
        errors.append('breadth')
        results['breadth'] = {'current': None, 'score': 0, 'interpretation': 'Sin datos'}

    # ── 11. SKEW Index (Tail Risk) ────────────────────────────────────────
    print("Fetching SKEW Index (^SKEW)...")
    df_skew = _fetch('^SKEW')
    if df_skew is not None:
        results['skew'] = _score_skew(df_skew)
        print(f"  SKEW: {results['skew']['current']} → score {results['skew']['score']:+.1f}")
    else:
        errors.append('skew')
        results['skew'] = {'current': None, 'score': 0, 'interpretation': 'Sin datos'}

    # ── 12. VVIX (Vol of Vol) ─────────────────────────────────────────────
    print("Fetching VVIX (^VVIX)...")
    df_vvix = _fetch('^VVIX')
    if df_vvix is not None:
        results['vvix'] = _score_vvix(df_vvix)
        print(f"  VVIX: {results['vvix']['current']} → score {results['vvix']['score']:+.1f}")
    else:
        errors.append('vvix')
        results['vvix'] = {'current': None, 'score': 0, 'interpretation': 'Sin datos'}

    # ── 13. Regional Banks (KRE/SPY) ─────────────────────────────────────
    print("Fetching Regional Banks (KRE, SPY)...")
    df_kre = _fetch('KRE')
    if df_kre is not None and df_spy is not None:
        results['regional_banks'] = _score_ratio(df_kre, df_spy, 'regional_banks')
        print(f"  Regional Banks: ratio {results['regional_banks']['current']} → score {results['regional_banks']['score']:+.1f}")
    else:
        errors.append('regional_banks')
        results['regional_banks'] = {'current': None, 'score': 0, 'interpretation': 'Sin datos'}

    # ── 14. Small Cap vs Large (IWM/SPY) ──────────────────────────────────
    print("Fetching Small Cap (IWM, SPY)...")
    df_iwm = _fetch('IWM')
    if df_iwm is not None and df_spy is not None:
        results['small_cap'] = _score_ratio(df_iwm, df_spy, 'small_cap')
        print(f"  Small Cap: ratio {results['small_cap']['current']} → score {results['small_cap']['score']:+.1f}")
    else:
        errors.append('small_cap')
        results['small_cap'] = {'current': None, 'score': 0, 'interpretation': 'Sin datos'}

    # ── 15. Real Yields (TIP/TLT) ─────────────────────────────────────────
    print("Fetching Real Yields (TIP, TLT)...")
    df_tip = _fetch('TIP')
    df_tlt = _fetch('TLT')
    if df_tip is not None and df_tlt is not None:
        results['real_yields'] = _score_ratio(df_tip, df_tlt, 'real_yields')
        print(f"  Real Yields: ratio {results['real_yields']['current']} → score {results['real_yields']['score']:+.1f}")
    else:
        errors.append('real_yields')
        results['real_yields'] = {'current': None, 'score': 0, 'interpretation': 'Sin datos'}

    # ── Composite score ────────────────────────────────────────────────────
    scores = [results[k]['score'] for k in results if results[k]['score'] is not None]
    composite = sum(scores)
    max_possible = len(scores) * 2

    # Normalize to 0-100 for display, but keep raw for regime
    composite_pct = (composite + max_possible) / (2 * max_possible) * 100

    regime = _get_regime(composite)

    print(f"\nComposite score: {composite:.1f} / {max_possible} → {regime['name']}")

    # ── Groq narrative ────────────────────────────────────────────────────
    print("Requesting Groq AI analysis...")
    ai_narrative = _groq_analysis(results, composite, regime['name'])
    if ai_narrative:
        print(f"  AI: {ai_narrative[:80]}...")

    # ── Enrich signals with metadata ──────────────────────────────────────
    enriched = {}
    for key, data in results.items():
        sig_def = SIGNALS.get(key, {})
        enriched[key] = {
            **data,
            'label': sig_def.get('label', key),
            'description': sig_def.get('description', ''),
        }

    # ── Historical analogs + systemic risks ───────────────────────────────
    print("Computing historical analogs...")
    historical_analogs = _compute_historical_analogs(enriched)
    for a in historical_analogs[:2]:
        print(f"  Analog: {a['name']} ({a['similarity']:.0f}% similar)")

    print("Identifying systemic risks...")
    systemic_risks = _identify_systemic_risks(enriched)
    for r in systemic_risks:
        print(f"  Risk: {r['name']} [{r['severity']}]")

    # ── Index MA breakouts ─────────────────────────────────────────────────
    print("Scanning index breakouts (Nasdaq, S&P, Russell, DAX...)...")
    index_breakouts = _scan_index_breakouts()
    fresh_breaks = [b for b in index_breakouts if b['fresh_cross']]
    bearish_breaks = [b for b in fresh_breaks if b['signal'] == 'BEARISH_BREAK']
    bullish_breaks = [b for b in fresh_breaks if b['signal'] == 'BULLISH_BREAK']
    print(f"  Breakouts: {len(index_breakouts)} total, {len(bearish_breaks)} bearish fresh, {len(bullish_breaks)} bullish fresh")

    # ── Build output ──────────────────────────────────────────────────────
    output = {
        'timestamp': datetime.now().isoformat(),
        'date': datetime.now().strftime('%Y-%m-%d'),
        'regime': regime,
        'composite_score': round(composite, 2),
        'composite_pct': round(composite_pct, 1),
        'max_score': max_possible,
        'signals': enriched,
        'errors': errors,
        'ai_narrative': ai_narrative,
        'historical_analogs': historical_analogs,
        'systemic_risks': systemic_risks,
        'index_breakouts': index_breakouts,
        'signal_order': [
            'vix', 'yield_curve', 'credit', 'copper_gold', 'gold_spy',
            'oil', 'defense', 'dollar', 'yen', 'breadth',
            'skew', 'vvix', 'regional_banks', 'small_cap', 'real_yields',
        ],
    }

    # ── Detect regime change (compare to yesterday's saved JSON) ─────────────
    out_path = DOCS / 'macro_radar.json'
    previous_regime = None
    if out_path.exists():
        try:
            with open(out_path) as f:
                prev = json.load(f)
            previous_regime = prev.get('regime', {}).get('name')
        except Exception:
            pass

    # Save
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nSaved to {out_path}")
    print(f"Regime: {regime['name']} | Composite: {composite:.1f}/{max_possible} | Errors: {errors or 'none'}")

    # ── Telegram alerts ───────────────────────────────────────────────────
    _send_telegram_regime_alert(regime['name'], previous_regime, composite, max_possible, ai_narrative, enriched)
    _send_telegram_breakout_alert(index_breakouts)

    return output


def _send_telegram_regime_alert(
    current_regime: str,
    previous_regime: Optional[str],
    composite: float,
    max_possible: int,
    ai_narrative: Optional[str],
    signals: dict,
) -> None:
    """Send Telegram message if regime changed or is ALERT/CRISIS."""
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id   = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not bot_token or not chat_id:
        print("  Telegram: no credentials configured, skipping")
        return

    regime_changed = previous_regime and previous_regime != current_regime
    is_danger = current_regime in ('ALERT', 'CRISIS')

    # Only alert on regime change or daily summary for danger zones
    if not regime_changed and not is_danger:
        print(f"  Telegram: regime stable ({current_regime}), skipping")
        return

    REGIME_EMOJI = {
        'CALM':   '🟢',
        'WATCH':  '🟡',
        'STRESS': '🟠',
        'ALERT':  '🔴',
        'CRISIS': '🚨',
    }
    emoji = REGIME_EMOJI.get(current_regime, '⚪')

    if regime_changed:
        arrow = '→'
        header = f"{REGIME_EMOJI.get(previous_regime,'⚪')} <b>{previous_regime}</b> {arrow} {emoji} <b>{current_regime}</b>"
        title = "🔔 <b>Macro Radar: Cambio de Régimen</b>"
    else:
        header = f"{emoji} <b>Régimen: {current_regime}</b>"
        title = f"{'🚨' if current_regime == 'CRISIS' else '🔴'} <b>Macro Radar: {current_regime}</b>"

    # Top worst signals
    sorted_sigs = sorted(signals.items(), key=lambda x: x[1].get('score', 0))
    worst = [(k, v) for k, v in sorted_sigs if v.get('score', 0) < 0][:3]
    worst_lines = '\n'.join(
        f"  • {v.get('label', k)}: <b>{v.get('score', 0):+.1f}</b> — {v.get('interpretation','')}"
        for k, v in worst
    ) or '  Sin señales negativas'

    text = f"""{title}

{header}
Puntuación: <b>{composite:.1f}/{max_possible}</b>

<b>Señales de alerta:</b>
{worst_lines}"""

    if ai_narrative:
        text += f"\n\n<i>{ai_narrative[:300]}</i>"

    try:
        import urllib.request
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = json.dumps({
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True,
        }).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=10)
        print(f"  Telegram: alert sent ({current_regime}{f' ← {previous_regime}' if regime_changed else ''})")
    except Exception as e:
        print(f"  Telegram: send failed: {e}")


if __name__ == '__main__':
    run_macro_radar()
