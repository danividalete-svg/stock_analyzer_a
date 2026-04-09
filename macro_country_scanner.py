"""
Macro Country Scanner
=====================
Analyzes macroeconomic conditions + stock market opportunity for 15 key countries.

Data sources:
  - Market/Technical: yfinance (index prices, ETFs, 200MA, 52w range, YTD)
  - Macro fundamentals: IMF WEO projections (hardcoded, updated quarterly)
  - Rates: central bank rates (known) + 10Y bond yields from yfinance
  - Currency: yfinance FX pairs vs USD

Output: docs/macro_country_analysis.json
"""

import json
import time
import random
import datetime
from pathlib import Path
from typing import Optional

import yfinance as yf
import numpy as np
import pandas as pd

DOCS = Path('docs')

# ---------------------------------------------------------------------------
# Static macro data — IMF WEO October 2025 / latest available estimates
# Updated: 2025-10. Source: IMF World Economic Outlook
# ---------------------------------------------------------------------------
MACRO_DATA = {
    'US': {
        'name': 'United States',   'flag': '🇺🇸', 'region': 'Americas',
        'gdp_growth': 2.4,         # IMF WEO Jan-2026 Update (2026e)
        'inflation':  2.9,         # CPI % 2026e
        'unemployment': 4.4,
        'current_account': -3.3,
        'rate_direction': 'HOLDING', # Fed: 4.25-4.50%, paused
        'policy_rate': 4.375,
        'debt_to_gdp': 123.0,      # IMF 2025. USD = reserva mundial → riesgo bajo
        'currency_sovereign': True, # emite su propia moneda
        'macro_notes': 'Economía resiliente pero aranceles añaden presión. Fed en pausa hasta ver inflación.',
    },
    'DE': {
        'name': 'Germany',         'flag': '🇩🇪', 'region': 'Europe',
        'gdp_growth': 1.1,         # IMF Jan-2026 (mejora vs Oct-2025)
        'inflation':  1.9,
        'unemployment': 3.4,
        'current_account': 4.3,
        'rate_direction': 'CUTTING', # ECB: 2.25%
        'policy_rate': 2.25,
        'debt_to_gdp': 64.0,       # bajo para eurozona
        'currency_sovereign': False, # usa EUR, no controla su política monetaria
        'macro_notes': 'Recuperación gradual. Nuevo gobierno con mayor gasto fiscal. ECB recortando.',
    },
    'FR': {
        'name': 'France',          'flag': '🇫🇷', 'region': 'Europe',
        'gdp_growth': 1.0,
        'inflation':  1.5,
        'unemployment': 7.3,
        'current_account': -0.9,
        'rate_direction': 'CUTTING',
        'policy_rate': 2.25,
        'debt_to_gdp': 112.0,      # elevado, sin moneda propia = riesgo real
        'currency_sovereign': False,
        'macro_notes': 'Crecimiento moderado. Deuda elevada sin soberanía monetaria. Consolidación fiscal en curso.',
    },
    'GB': {
        'name': 'United Kingdom',  'flag': '🇬🇧', 'region': 'Europe',
        'gdp_growth': 1.3,
        'inflation':  2.5,
        'unemployment': 4.4,
        'current_account': -3.3,
        'rate_direction': 'CUTTING', # BOE: 4.25%
        'policy_rate': 4.25,
        'debt_to_gdp': 100.0,
        'currency_sovereign': True,  # emite GBP
        'macro_notes': 'BOE recortando con cautela. Inflación de servicios aún elevada.',
    },
    'JP': {
        'name': 'Japan',           'flag': '🇯🇵', 'region': 'Asia-Pacific',
        'gdp_growth': 0.6,         # IMF Jan-2026 revisado a la baja
        'inflation':  2.1,
        'unemployment': 2.5,
        'current_account': 3.8,
        'rate_direction': 'HIKING', # BOJ: 0.5%
        'policy_rate': 0.5,
        'debt_to_gdp': 255.0,      # altísimo pero BOJ monetiza → riesgo latente no inmediato
        'currency_sovereign': True,  # emite JPY, BOJ compra deuda masivamente
        'macro_notes': 'BOJ normalizando muy lentamente. Deuda 255% GDP pero monetizada por BOJ. Crecimiento débil.',
    },
    'CN': {
        'name': 'China',           'flag': '🇨🇳', 'region': 'Asia-Pacific',
        'gdp_growth': 4.5,
        'inflation':  0.5,
        'unemployment': 4.0,
        'current_account': 1.5,
        'rate_direction': 'CUTTING', # PBoC: 1.5% MLF
        'policy_rate': 1.5,
        'debt_to_gdp': 83.0,       # deuda pública oficial; deuda corporativa es otro problema
        'currency_sovereign': True,
        'macro_notes': 'Tregua aranceles 90 días (145%→30%). PBoC estimulando. Deuda inmobiliaria sector privado es el riesgo real.',
    },
    'IN': {
        'name': 'India',           'flag': '🇮🇳', 'region': 'Asia-Pacific',
        'gdp_growth': 6.5,
        'inflation':  4.2,
        'unemployment': 8.0,
        'current_account': -1.2,
        'rate_direction': 'CUTTING', # RBI: 6.0%
        'policy_rate': 6.0,
        'debt_to_gdp': 82.0,
        'currency_sovereign': True,
        'macro_notes': 'Motor de crecimiento global. RBI iniciando ciclo bajista de tipos.',
    },
    'KR': {
        'name': 'South Korea',     'flag': '🇰🇷', 'region': 'Asia-Pacific',
        'gdp_growth': 2.3,
        'inflation':  2.0,
        'unemployment': 2.8,
        'current_account': 3.4,
        'rate_direction': 'CUTTING', # BOK: 2.75%
        'policy_rate': 2.75,
        'debt_to_gdp': 54.0,
        'currency_sovereign': True,
        'macro_notes': 'Exportaciones semiconductores fuertes. BOK recortando. Impacto aranceles EE.UU. moderado.',
    },
    'BR': {
        'name': 'Brazil',          'flag': '🇧🇷', 'region': 'Americas',
        'gdp_growth': 1.9,         # IMF Jan-2026 revisado a la baja
        'inflation':  4.0,
        'unemployment': 7.0,
        'current_account': -2.4,
        'rate_direction': 'HIKING', # BCB: 13.25%
        'policy_rate': 13.25,
        'debt_to_gdp': 92.0,       # alto + se financia parcialmente en USD = riesgo real
        'currency_sovereign': False, # emite BRL pero mercados no confían, depende de USD
        'macro_notes': 'Inflación persistente fuerza tipos altos. Deuda elevada con dependencia exterior. Real bajo presión.',
    },
    'AU': {
        'name': 'Australia',       'flag': '🇦🇺', 'region': 'Asia-Pacific',
        'gdp_growth': 1.7,
        'inflation':  2.8,
        'unemployment': 4.0,
        'current_account': -1.8,
        'rate_direction': 'CUTTING', # RBA empezó ciclo bajista en Feb-2026
        'policy_rate': 3.85,
        'debt_to_gdp': 50.0,
        'currency_sovereign': True,
        'macro_notes': 'RBA inició recortes en Feb-2026. Muy expuesta a China vía commodities.',
    },
    'CA': {
        'name': 'Canada',          'flag': '🇨🇦', 'region': 'Americas',
        'gdp_growth': 1.4,
        'inflation':  2.5,
        'unemployment': 6.3,
        'current_account': -1.2,
        'rate_direction': 'CUTTING', # BOC: 2.75%
        'policy_rate': 2.75,
        'debt_to_gdp': 107.0,
        'currency_sovereign': True,
        'macro_notes': 'BOC recortando agresivamente. Impacto aranceles EE.UU.',
    },
    'ES': {
        'name': 'Spain',           'flag': '🇪🇸', 'region': 'Europe',
        'gdp_growth': 2.4,
        'inflation':  2.6,
        'unemployment': 11.5,
        'current_account': 2.8,
        'rate_direction': 'CUTTING',
        'policy_rate': 2.25,
        'debt_to_gdp': 108.0,      # elevado sin moneda propia = vulnerabilidad real
        'currency_sovereign': False,
        'macro_notes': 'Mejor crecimiento de la eurozona pero deuda 108% GDP sin soberanía monetaria. Turismo récord.',
    },
    'IT': {
        'name': 'Italy',           'flag': '🇮🇹', 'region': 'Europe',
        'gdp_growth': 0.7,
        'inflation':  1.7,
        'unemployment': 6.1,
        'current_account': 1.3,
        'rate_direction': 'CUTTING',
        'policy_rate': 2.25,
        'debt_to_gdp': 138.0,      # el mayor riesgo sistémico de la eurozona
        'currency_sovereign': False,
        'macro_notes': 'Deuda 138% GDP sin moneda propia = riesgo sistémico eurozona. Crecimiento anémico. ECB TPI da soporte.',
    },
    'CH': {
        'name': 'Switzerland',     'flag': '🇨🇭', 'region': 'Europe',
        'gdp_growth': 1.5,
        'inflation':  0.9,
        'unemployment': 2.5,
        'current_account': 10.2,
        'rate_direction': 'HOLDING', # SNB: 0.25%
        'policy_rate': 0.25,
        'debt_to_gdp': 40.0,       # deuda bajísima
        'currency_sovereign': True,  # emite CHF
        'macro_notes': 'Franco fuerte, deuda baja, inflación mínima. Refugio defensivo por excelencia.',
    },
    'MX': {
        'name': 'Mexico',          'flag': '🇲🇽', 'region': 'Americas',
        'gdp_growth': 1.3,
        'inflation':  4.0,
        'unemployment': 2.9,
        'current_account': -0.1,
        'rate_direction': 'CUTTING', # Banxico: ~8.5%
        'policy_rate': 8.5,
        'debt_to_gdp': 50.0,
        'currency_sovereign': True,  # emite MXN
        'macro_notes': 'Nearshoring beneficia al sector industrial. Peso volátil. Dependencia económica de EE.UU. alta.',
    },
}

# Country market instruments (index + USD ETF for comparison)
MARKET_CONFIG = {
    'US': {'index': '^GSPC', 'etf': 'SPY',  'currency_pair': None,       'bond_yield': '^TNX'},
    'DE': {'index': '^GDAXI','etf': 'EWG',  'currency_pair': 'EURUSD=X', 'bond_yield': None},
    'FR': {'index': '^FCHI', 'etf': 'EWQ',  'currency_pair': 'EURUSD=X', 'bond_yield': None},
    'GB': {'index': '^FTSE', 'etf': 'EWU',  'currency_pair': 'GBPUSD=X', 'bond_yield': None},
    'JP': {'index': '^N225', 'etf': 'EWJ',  'currency_pair': 'JPYUSD=X', 'bond_yield': None},
    'CN': {'index': '000001.SS','etf':'FXI', 'currency_pair': 'CNYUSD=X', 'bond_yield': None},
    'IN': {'index': '^BSESN','etf': 'INDA', 'currency_pair': 'INRUSD=X', 'bond_yield': None},
    'KR': {'index': '^KS11', 'etf': 'EWY',  'currency_pair': 'KRWUSD=X', 'bond_yield': None},
    'BR': {'index': '^BVSP', 'etf': 'EWZ',  'currency_pair': 'BRLUSD=X', 'bond_yield': None},
    'AU': {'index': '^AXJO', 'etf': 'EWA',  'currency_pair': 'AUDUSD=X', 'bond_yield': None},
    'CA': {'index': '^GSPTSE','etf':'EWC',  'currency_pair': 'CADUSD=X', 'bond_yield': None},
    'ES': {'index': '^IBEX', 'etf': 'EWP',  'currency_pair': 'EURUSD=X', 'bond_yield': None},
    'IT': {'index': 'FTSEMIB.MI','etf':'EWI', 'currency_pair': 'EURUSD=X', 'bond_yield': None},
    'CH': {'index': '^SSMI', 'etf': 'EWL',  'currency_pair': 'CHFUSD=X', 'bond_yield': None},
    'MX': {'index': '^MXX',  'etf': 'EWW',  'currency_pair': 'MXNUSD=X', 'bond_yield': None},
}


def _fetch_market_data(ticker: str, period: str = '1y') -> dict:
    """Fetch price data, 200MA, 52w range, YTD return."""
    try:
        time.sleep(random.uniform(0.3, 0.8))
        hist = yf.download(ticker, period=period, interval='1d',
                           auto_adjust=True, progress=False, timeout=15)
        if hist is None or len(hist) < 20:
            return {}

        closes = hist['Close'].dropna()
        if isinstance(closes, pd.DataFrame):
            closes = closes.iloc[:, 0]
        closes = closes.astype(float)

        if len(closes) < 20:
            return {}

        current = float(closes.iloc[-1])
        ma200 = float(closes.tail(200).mean()) if len(closes) >= 200 else float(closes.mean())
        ma50  = float(closes.tail(50).mean())  if len(closes) >= 50  else float(closes.mean())

        w52_high = float(closes.max())
        w52_low  = float(closes.min())
        pct_from_200 = (current / ma200 - 1) * 100
        pct_from_52h = (current / w52_high - 1) * 100
        position_in_range = (current - w52_low) / (w52_high - w52_low) * 100 if w52_high != w52_low else 50

        # YTD return
        today = datetime.date.today()
        ytd_start = datetime.date(today.year, 1, 1)
        ytd_idx = closes.index[closes.index >= pd.Timestamp(ytd_start)]
        if len(ytd_idx) >= 2:
            ytd_return = (current / float(closes[ytd_idx[0]]) - 1) * 100
        else:
            ytd_return = 0.0

        # 1M return
        m1_closes = closes.tail(21)
        m1_return = (current / float(m1_closes.iloc[0]) - 1) * 100 if len(m1_closes) > 1 else 0.0

        # MA trend (slope)
        if len(closes) >= 10:
            ma200_now = float(closes.tail(200).mean()) if len(closes) >= 200 else float(closes.mean())
            ma200_20d = float(closes.tail(220).head(20).mean()) if len(closes) >= 220 else ma200_now
            ma200_slope = (ma200_now / ma200_20d - 1) * 100 if ma200_20d else 0
        else:
            ma200_slope = 0.0

        return {
            'current': round(current, 2),
            'ma200': round(ma200, 2),
            'ma50': round(ma50, 2),
            'pct_from_200': round(pct_from_200, 1),
            'pct_from_52h': round(pct_from_52h, 1),
            'position_in_range': round(position_in_range, 1),  # 0=52wLow, 100=52wHigh
            'ytd_return': round(ytd_return, 1),
            'm1_return': round(m1_return, 1),
            'ma200_slope': round(ma200_slope, 2),
            'w52_high': round(w52_high, 2),
            'w52_low': round(w52_low, 2),
        }
    except Exception as e:
        print(f"   ⚠ market data error for {ticker}: {e}")
        return {}


def _fetch_currency_ytd(pair: str) -> Optional[float]:
    """Return YTD % change for a currency pair."""
    if not pair:
        return None
    try:
        time.sleep(random.uniform(0.2, 0.5))
        hist = yf.download(pair, period='1y', interval='1d',
                           auto_adjust=True, progress=False, timeout=10)
        if hist is None or len(hist) < 5:
            return None
        closes = hist['Close'].dropna()
        if isinstance(closes, pd.DataFrame):
            closes = closes.iloc[:, 0]
        closes = closes.astype(float)
        today = datetime.date.today()
        ytd_start = datetime.date(today.year, 1, 1)
        ytd_idx = closes.index[closes.index >= pd.Timestamp(ytd_start)]
        if len(ytd_idx) >= 2:
            return round((float(closes.iloc[-1]) / float(closes[ytd_idx[0]]) - 1) * 100, 1)
        return round((float(closes.iloc[-1]) / float(closes.iloc[0]) - 1) * 100, 1)
    except:
        return None


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_macro(m: dict) -> tuple[float, list]:
    """Return (score 0-100, breakdown list)."""
    score = 0.0
    parts = []

    # 1. GDP growth (0-30)
    gdp = m['gdp_growth']
    if gdp >= 5:    g = 30
    elif gdp >= 4:  g = 25
    elif gdp >= 3:  g = 20
    elif gdp >= 2:  g = 15
    elif gdp >= 1:  g = 9
    elif gdp >= 0:  g = 4
    else:           g = 0
    score += g
    parts.append(f"GDP {gdp:+.1f}% → {g}/30")

    # 2. Inflation control (0-25) — optimal 1.5-3%
    inf = m['inflation']
    if 1.5 <= inf <= 3.0:    i = 25
    elif 1.0 <= inf < 1.5:   i = 20
    elif 3.0 < inf <= 4.0:   i = 18
    elif 0.5 <= inf < 1.0:   i = 15
    elif 4.0 < inf <= 5.5:   i = 10
    elif 5.5 < inf <= 7.0:   i = 5
    elif inf < 0.5:           i = 12  # deflation risk but not as bad as high inflation
    else:                      i = 0   # >7%
    score += i
    parts.append(f"Inflación {inf:.1f}% → {i}/25")

    # 3. Unemployment (0-20)
    unemp = m['unemployment']
    if unemp < 3.0:    u = 20
    elif unemp < 4.5:  u = 17
    elif unemp < 6.0:  u = 13
    elif unemp < 8.0:  u = 9
    elif unemp < 10.0: u = 5
    else:              u = 1
    score += u
    parts.append(f"Desempleo {unemp:.1f}% → {u}/20")

    # 4. Rate direction (0-15)
    rd = m['rate_direction']
    r = {'CUTTING': 15, 'HOLDING': 10, 'HOLDING_LOW': 12, 'HIKING': 4}.get(rd, 8)
    score += r
    parts.append(f"Tipos {rd} → {r}/15")

    # 5. Current account (0-10)
    ca = m['current_account']
    if ca > 3:     c = 10
    elif ca > 1:   c = 8
    elif ca > -1:  c = 6
    elif ca > -3:  c = 4
    else:          c = 2
    score += c
    parts.append(f"C/A {ca:+.1f}% GDP → {c}/10")

    # 6. Debt sustainability — penaliza solo si NO hay soberanía monetaria
    # Países que emiten su propia moneda: deuda alta es latente, no urgente
    # Países sin moneda propia (eurozona, Brasil-like): deuda alta = riesgo real de mercado
    debt = m.get('debt_to_gdp', 60.0)
    sovereign = m.get('currency_sovereign', True)
    if not sovereign:
        # Sin soberanía monetaria: la deuda importa aquí y ahora
        if debt < 60:       d = 0
        elif debt < 80:     d = -2
        elif debt < 100:    d = -5
        elif debt < 120:    d = -9
        else:               d = -13  # IT 138% sin EUR propio = máxima penalización
    else:
        # Con soberanía: penalización mucho menor (riesgo latente, no urgente)
        if debt < 80:       d = 0
        elif debt < 120:    d = -1
        elif debt < 180:    d = -3
        else:               d = -5  # JP 255% aún monetizable pero no trivial
    score += d
    debt_note = '' if sovereign else ' (sin moneda propia)'
    parts.append(f"Deuda {debt:.0f}% GDP{debt_note} → {d}/0")

    return round(score, 1), parts


def _score_market(mkt: dict, macro: dict) -> tuple[float, list]:
    """Return (score 0-100, breakdown). Higher = better entry opportunity."""
    if not mkt:
        return 50.0, ['No hay datos de mercado']

    score = 0.0
    parts = []

    # 1. Position vs 200MA (0-35)
    p200 = mkt['pct_from_200']
    if -15 <= p200 <= -3:    m = 35   # correction zone — best entry
    elif -3 < p200 <= 5:     m = 28   # near MA — healthy
    elif 5 < p200 <= 15:     m = 18   # somewhat extended
    elif p200 > 15:          m = 8    # very extended, risky entry
    elif p200 < -15:         m = 20   # below but possibly distressed/recovering
    else:                    m = 15
    score += m
    parts.append(f"vs 200MA {p200:+.1f}% → {m}/35")

    # 2. Position in 52w range (0-30) — contrarian: low = cheap
    pos = mkt['position_in_range']  # 0=52wLow, 100=52wHigh
    if pos < 20:    p = 30   # near lows — oversold
    elif pos < 35:  p = 25
    elif pos < 50:  p = 20
    elif pos < 65:  p = 14
    elif pos < 80:  p = 8
    else:           p = 3    # near highs — stretched
    score += p
    parts.append(f"Rango 52s: {pos:.0f}% → {p}/30")

    # 3. YTD performance context (0-20) — lower = more attractive entry
    ytd = mkt['ytd_return']
    if ytd < -20:   y = 20
    elif ytd < -10: y = 17
    elif ytd < -5:  y = 14
    elif ytd < 0:   y = 11
    elif ytd < 5:   y = 8
    elif ytd < 15:  y = 5
    else:           y = 2
    score += y
    parts.append(f"YTD {ytd:+.1f}% → {y}/20")

    # 4. MA slope (0-15) — uptrend is good, but entry when it's correcting within uptrend
    slope = mkt.get('ma200_slope', 0)
    if slope > 0.5:    s = 15   # strong uptrend
    elif slope > 0.1:  s = 12
    elif slope > -0.1: s = 9    # flat — unclear
    elif slope > -0.5: s = 5    # mild downtrend
    else:              s = 2    # strong downtrend
    score += s
    parts.append(f"Tendencia 200MA {slope:+.2f}% → {s}/15")

    return round(score, 1), parts


def _determine_signal(macro_score: float, market_score: float, macro: dict, mkt: dict) -> dict:
    """
    Combine macro + market to produce signal.

    Logic:
    - Good macro + cheap market = STRONG_BUY
    - Good macro + fairly priced = BUY
    - Good macro + expensive = NEUTRAL (wait)
    - Weak macro + cheap market = WATCH (contrarian risk)
    - Weak macro + expensive = SHORT
    """
    combined = macro_score * 0.45 + market_score * 0.55

    # Hard overrides
    if macro['gdp_growth'] < 0:
        combined = min(combined, 48)  # cap at NEUTRAL if in recession
    if macro['inflation'] > 8:
        combined = min(combined, 52)  # cap if inflation very high

    # Determine signal
    if combined >= 72:    signal, color = 'STRONG_BUY', '#10b981'
    elif combined >= 58:  signal, color = 'BUY',         '#22d3ee'
    elif combined >= 44:  signal, color = 'NEUTRAL',     '#94a3b8'
    elif combined >= 32:  signal, color = 'SHORT',        '#f97316'
    else:                  signal, color = 'STRONG_SHORT','#ef4444'

    # Special case: cheap market but bad macro → flag as contrarian
    contrarian = (market_score >= 65 and macro_score < 45)
    # Special case: good macro but very extended market
    wait_pullback = (macro_score >= 65 and mkt.get('pct_from_200', 0) > 15)

    return {
        'signal': signal,
        'color': color,
        'combined_score': round(combined, 1),
        'contrarian': contrarian,
        'wait_pullback': wait_pullback,
    }


def _ai_analyze_country(country: dict) -> dict:
    """
    Use Groq (llama-3.3-70b) to generate a rich macro narrative + validate the signal.
    Returns: {ai_narrative, ai_risks, ai_opportunities, ai_verdict, ai_confidence}
    """
    import os
    try:
        from groq import Groq
    except ImportError:
        return {}

    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        return {}

    mkt = country.get('etf_data') or country.get('index_data') or {}
    code = country['code']
    name = country['name']

    prompt = f"""You are a global macro analyst at a hedge fund. Analyze the macroeconomic and market situation for {name} ({code}) as of April 2026.

MACRO FUNDAMENTALS (IMF Jan-2026 Update):
- GDP growth 2026e: {country['gdp_growth']:+.1f}%
- Inflation (CPI): {country['inflation']:.1f}%
- Unemployment: {country['unemployment']:.1f}%
- Current account: {country['current_account']:+.1f}% of GDP
- Central bank policy rate: {country['policy_rate']:.2f}%
- Rate direction: {country['rate_direction']}
- Context: {country['macro_notes']}

MARKET DATA (real-time ETF: {country['etf']}):
- Price vs 200-day MA: {mkt.get('pct_from_200', 'N/A'):+.1f}% {'(IN CORRECTION ZONE — potential entry)' if isinstance(mkt.get('pct_from_200'), float) and -20 < mkt.get('pct_from_200', 0) < -3 else ''}
- Position in 52-week range: {mkt.get('position_in_range', 'N/A'):.0f}% (0=52wLow, 100=52wHigh)
- YTD return: {mkt.get('ytd_return', 'N/A'):+.1f}%
- 1-month return: {mkt.get('m1_return', 'N/A'):+.1f}%
- 200MA slope: {mkt.get('ma200_slope', 'N/A'):+.2f}% (positive = uptrend)
- Currency vs USD YTD: {country.get('currency_ytd', 'N/A')}%

QUANTITATIVE SIGNAL:
- Macro score: {country['macro_score']:.0f}/100
- Market opportunity score: {country['market_score']:.0f}/100
- Combined signal: {country['signal']} ({country['combined_score']:.0f}/100)
- Contrarian flag: {country.get('contrarian', False)} (cheap market but weak macro)
- Wait-for-pullback flag: {country.get('wait_pullback', False)} (good macro but extended market)

GLOBAL CONTEXT (April 2026):
- US-China trade truce announced (90 days): tariffs 145%→30% US, 125%→10% China
- Global market in recovery/rally mode after Liberation Day selloff
- Fed on hold at 4.25-4.50%, ECB cutting at 2.25%, BOJ normalizing slowly
- VIX at ~20 (elevated but falling)

YOUR TASK:
1. Write a concise macro narrative (3-4 sentences) explaining the CURRENT situation for this country's economy and stock market
2. Identify 2-3 specific RISKS for equity investors
3. Identify 2-3 specific OPPORTUNITIES for equity investors
4. Validate or challenge the quantitative signal ({country['signal']}) — do you agree? Why?
5. Give ONE actionable insight an investor should know

Respond ONLY with valid JSON (no markdown, no code blocks):
{{"ai_narrative": "3-4 sentence macro narrative", "ai_risks": ["risk1", "risk2", "risk3"], "ai_opportunities": ["opp1", "opp2", "opp3"], "ai_verdict": "STRONG_BUY|BUY|NEUTRAL|SHORT|STRONG_SHORT", "ai_confidence": 0-100, "ai_insight": "one actionable insight"}}"""

    try:
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.3,
            max_tokens=600,
            response_format={'type': 'json_object'},
        )
        result = json.loads(resp.choices[0].message.content)
        return {
            'ai_narrative':     result.get('ai_narrative', ''),
            'ai_risks':         result.get('ai_risks', []),
            'ai_opportunities': result.get('ai_opportunities', []),
            'ai_verdict':       result.get('ai_verdict', country['signal']),
            'ai_confidence':    result.get('ai_confidence', 50),
            'ai_insight':       result.get('ai_insight', ''),
        }
    except Exception as e:
        print(f"   ⚠ AI error for {code}: {e}")
        return {}


def run():
    print("\n" + "=" * 70)
    print("🌍 MACRO COUNTRY SCANNER")
    print("=" * 70)

    results = []

    for code, macro in MACRO_DATA.items():
        mc = MARKET_CONFIG[code]
        print(f"\n[{code}] {macro['flag']} {macro['name']}")

        # --- market data ---
        print(f"   Fetching index: {mc['index']}...")
        idx_data = _fetch_market_data(mc['index'])

        print(f"   Fetching ETF:   {mc['etf']}...")
        etf_data = _fetch_market_data(mc['etf'])

        # --- currency ---
        fx_ytd = None
        if mc['currency_pair']:
            fx_ytd = _fetch_currency_ytd(mc['currency_pair'])
            print(f"   Currency {mc['currency_pair']}: {fx_ytd:+.1f}%" if fx_ytd is not None else f"   Currency: n/a")

        # --- scoring ---
        macro_score, macro_parts = _score_macro(macro)
        market_score, market_parts = _score_market(etf_data if etf_data else idx_data, macro)
        sig = _determine_signal(macro_score, market_score, macro, etf_data if etf_data else idx_data)

        print(f"   Macro: {macro_score:.0f}/100 | Market: {market_score:.0f}/100 | Signal: {sig['signal']} ({sig['combined_score']:.0f})")

        country_entry = {
            'code': code,
            'name': macro['name'],
            'flag': macro['flag'],
            'region': macro['region'],
            # macro fundamentals
            'gdp_growth': macro['gdp_growth'],
            'inflation': macro['inflation'],
            'unemployment': macro['unemployment'],
            'current_account': macro['current_account'],
            'rate_direction': macro['rate_direction'],
            'policy_rate': macro['policy_rate'],
            'macro_notes': macro['macro_notes'],
            'debt_to_gdp': macro.get('debt_to_gdp', None),
            'currency_sovereign': macro.get('currency_sovereign', True),
            # market data (ETF = USD view; index = local)
            'etf': mc['etf'],
            'index': mc['index'],
            'etf_data': etf_data,
            'index_data': idx_data,
            'currency_ytd': fx_ytd,
            # scores
            'macro_score': macro_score,
            'market_score': market_score,
            'macro_breakdown': macro_parts,
            'market_breakdown': market_parts,
            # signal
            **sig,
        }

        # --- AI narrative (optional, needs GROQ_API_KEY) ---
        ai = _ai_analyze_country({**country_entry, **sig})
        if ai:
            country_entry.update(ai)
            verdict = ai.get('ai_verdict', sig['signal'])
            conf = ai.get('ai_confidence', 0)
            print(f"   🤖 AI: {verdict} (conf {conf})")

        results.append(country_entry)

    # Sort by combined_score desc
    results.sort(key=lambda x: x['combined_score'], reverse=True)

    output = {
        'generated_at': datetime.datetime.utcnow().strftime('%Y-%m-%d'),
        'generated_ts': datetime.datetime.utcnow().isoformat(),
        'macro_source': 'IMF WEO Jan-2026 Update (WEO Apr-2026 sale el 14-Apr)',
        'market_source': 'yfinance real-time',
        'countries': results,
        'summary': {
            'strong_buy': [r['code'] for r in results if r['signal'] == 'STRONG_BUY'],
            'buy':         [r['code'] for r in results if r['signal'] == 'BUY'],
            'neutral':     [r['code'] for r in results if r['signal'] == 'NEUTRAL'],
            'short':       [r['code'] for r in results if r['signal'] == 'SHORT'],
            'strong_short':[r['code'] for r in results if r['signal'] == 'STRONG_SHORT'],
        },
    }

    out_path = DOCS / 'macro_country_analysis.json'
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 70}")
    print(f"✅ Guardado: {out_path} ({len(results)} países)")
    print(f"\n📊 RESUMEN:")
    for sig_label in ['STRONG_BUY','BUY','NEUTRAL','SHORT','STRONG_SHORT']:
        items = [r for r in results if r['signal'] == sig_label]
        if items:
            flags = ' '.join(r['flag'] for r in items)
            codes = ', '.join(r['code'] for r in items)
            print(f"   {sig_label:12s}: {flags}  ({codes})")
    print()


if __name__ == '__main__':
    run()
