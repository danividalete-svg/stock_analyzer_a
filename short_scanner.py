#!/usr/bin/env python3
"""
Short Scanner — Identifica oportunidades en corto con bajo riesgo de squeeze.

Scoring (0–100):
  Técnico     40 pts  — debajo MA50/MA200, Death Cross, Weinstein S4
  Fundamental 35 pts  — revenue negativo, FCF negativo, ROE negativo, Piotroski bajo, alta deuda
  Bajada      15 pts  — target analistas < precio, recomendación sell/underperform
  Seguridad   10 pts  — bajo short interest, sin earnings próximos

Filtros duros (score = 0):
  • short_interest > 25 %   → riesgo squeeze extremo
  • earnings < 5 días        → riesgo gap overnight
  • precio < 5 $             → penny stock / manipulable
  • market_cap < 500 M$      → sin liquidez para pedir prestado

Output: docs/short_opportunities.csv + docs/short_opportunities.json
"""

import csv
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

DOCS = Path('docs')
DOCS.mkdir(exist_ok=True)

# ── Universe ──────────────────────────────────────────────────────────────────
# Mix of large/mid caps across sectors; scanner decides which are actual shorts.
SHORT_UNIVERSE = [
    # ── Tech / High-Multiple / Declining ──────────────────────────────────
    'INTC', 'HPE', 'WDC', 'STX', 'NTAP', 'LUMN', 'CSCO', 'DELL', 'NCR',
    'SNAP', 'PINS', 'TWTR', 'MTCH', 'IAC', 'ZG', 'OPEN', 'RDFN',
    'U', 'RBLX', 'HOOD', 'COIN', 'MSTR', 'RIOT', 'MARA', 'CLSK',
    'NKLA', 'RIVN', 'LCID', 'FFIE', 'MULN', 'GOEV',
    'BYND', 'OATLY', 'SPCE', 'ASTR',
    'PARA', 'WBD', 'FOX', 'NYT',
    # ── Consumer Discretionary / Retail ───────────────────────────────────
    'M', 'JWN', 'KSS', 'GPS', 'BBWI', 'PRTY', 'BGFV',
    'BBY', 'BBBY', 'DG', 'DLTR', 'FIVE', 'BIG',
    'NWSA', 'GCI', 'LEG', 'HBI', 'PVH', 'VF', 'RL',
    # ── Real Estate (commercial + leveraged) ──────────────────────────────
    'VNO', 'SLG', 'BXP', 'HPP', 'JBGS', 'PDM', 'HIW', 'CIO',
    'MPW', 'OHI', 'SBRA', 'CTRE', 'LTC',
    'NYCB', 'AVAL',
    # ── Regional Banks ────────────────────────────────────────────────────
    'KEY', 'ZION', 'FHN', 'RF', 'FITB', 'CFG', 'HBAN',
    'PACW', 'WAL', 'CMA', 'FNB',
    # ── Healthcare / Pharma under pressure ───────────────────────────────
    'BAX', 'BDX', 'PRGO', 'HUM', 'CVS', 'CAH', 'MCK', 'HSIC',
    'CTIC', 'HZNP', 'ENDP', 'CRON', 'ACB', 'TLRY', 'SNDL',
    # ── Industrial / Legacy ───────────────────────────────────────────────
    'GE', 'F', 'GM', 'STLA', 'GOGL', 'NAT', 'ZIM',
    'X', 'CLF', 'HCC', 'ARCH', 'BTU',
    'FMC', 'MOS', 'CF', 'OLN',
    # ── Energy ────────────────────────────────────────────────────────────
    'RIG', 'VAL', 'NE', 'DO', 'PTEN', 'OII',
    'AR', 'RRC', 'SWN', 'CIVI', 'CHK',
    # ── China ADRs (geopolitical + regulatory risk) ───────────────────────
    'BABA', 'JD', 'PDD', 'BIDU', 'NIO', 'LI', 'XPEV',
    'EDU', 'TAL', 'GOTU', 'IQ', 'BILI',
    # ── Cruise / Airlines (leveraged balance sheets) ──────────────────────
    'CCL', 'RCL', 'NCLH', 'SAVE', 'JBLU', 'HA',
    # ── Other known troubled sectors ─────────────────────────────────────
    'IEP', 'SHLS', 'BLNK', 'CHPT', 'EVGO', 'PTRA',
    'SPT', 'BRLT', 'AFRM', 'UPST', 'SOFI', 'LC', 'NU',
    'NTRA', 'PACB', 'ILMN', 'NVAX', 'MRNA',
]

# Remove obvious delisted / hard to borrow
_EXCLUDE = {'TWTR', 'BBBY', 'FFIE', 'MULN', 'GOEV', 'ASTR', 'SPCE', 'BRLT',
            'PRTY', 'BGFV', 'BIG', 'NCR', 'AVAL'}
SHORT_UNIVERSE = [t for t in SHORT_UNIVERSE if t not in _EXCLUDE]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff().dropna()
    if len(delta) < period:
        return float('nan')
    gain = delta.clip(lower=0).ewm(com=period - 1, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=period - 1, adjust=False).mean()
    rs   = gain / loss.replace(0, float('nan'))
    return float(100 - 100 / (1 + rs.iloc[-1]))


def _ma_slope(series: pd.Series, lookback: int = 20) -> float:
    """Return % slope of MA over last `lookback` bars (positive = rising)."""
    s = series.dropna()
    if len(s) < lookback + 1:
        return 0.0
    return float((s.iloc[-1] / s.iloc[-lookback - 1] - 1) * 100)


def _weinstein_stage(close: pd.Series) -> int:
    """
    Simplified Weinstein stage using MA40w.
    1=Accumulation, 2=Markup, 3=Distribution, 4=Markdown.
    """
    try:
        weekly = close.resample('W-FRI').last().dropna()
        if len(weekly) < 42:
            return 0
        ma40 = weekly.rolling(40).mean().dropna()
        if len(ma40) < 2:
            return 0
        price_above = close.iloc[-1] > float(ma40.iloc[-1])
        ma_rising   = float(ma40.iloc[-1]) > float(ma40.iloc[-5]) if len(ma40) >= 5 else False
        if price_above and ma_rising:
            return 2
        if price_above and not ma_rising:
            return 3
        if not price_above and not ma_rising:
            return 4
        return 1  # below MA but MA rising → Stage 1
    except Exception:
        return 0


def _piotroski(info: dict) -> Optional[int]:
    """Lightweight Piotroski F-score (0-9) from yfinance info fields."""
    score = 0
    try:
        roe = info.get('returnOnEquity') or 0
        if roe > 0: score += 1

        op_cf = info.get('operatingCashflow') or 0
        if op_cf > 0: score += 1

        roa = info.get('returnOnAssets') or 0
        # Proxy: check if profitable
        if (info.get('profitMargins') or 0) > 0: score += 1

        de = info.get('debtToEquity') or 0
        if de < 100: score += 1  # < 1× debt/equity

        cr = info.get('currentRatio') or 0
        if cr > 1: score += 1

        # Revenue growth positive
        if (info.get('revenueGrowth') or 0) > 0: score += 1

        # Operating margin positive
        if (info.get('operatingMargins') or 0) > 0: score += 1

        # Free cash flow positive
        fcf = info.get('freeCashflow') or 0
        if fcf > 0: score += 1

        # No dilution: shares not growing (proxy)
        shares_growth = info.get('sharesPercentSharesOut') or 0
        if shares_growth <= 0: score += 1

        return score
    except Exception:
        return None


def _days_to_earnings(info: dict) -> Optional[int]:
    try:
        ts = info.get('nextFiscalYearEnd') or info.get('earningsTimestamp')
        if ts:
            dt = datetime.fromtimestamp(int(ts))
            d = (dt - datetime.now()).days
            return d if d >= 0 else None
    except Exception:
        pass
    return None


def _safe_float(val, default=None) -> Optional[float]:
    try:
        v = float(val)
        return v if not (v != v) else default  # NaN check
    except Exception:
        return default


# ── Main scorer ───────────────────────────────────────────────────────────────

def _score_ticker(ticker: str, fund_row: Optional[dict] = None) -> Optional[dict]:
    """
    Fetch data and compute short score for a single ticker.
    Returns None if data unavailable or hard filter triggered.
    """
    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}

        # Basic filters
        price = _safe_float(info.get('currentPrice') or info.get('regularMarketPrice'))
        if not price or price < 5:
            return None

        mktcap = _safe_float(info.get('marketCap'))
        if not mktcap or mktcap < 500_000_000:
            return None

        # Short interest filter
        short_pct = _safe_float(info.get('shortPercentOfFloat'))
        if short_pct is None:
            short_pct = _safe_float(info.get('shortRatio'))
            if short_pct:
                # shortRatio in days; convert to rough % of float (proxy)
                avg_vol = _safe_float(info.get('averageVolume')) or 1
                shares_out = _safe_float(info.get('sharesOutstanding')) or 1
                short_pct = (short_pct * avg_vol / shares_out) * 100
        if short_pct is not None and short_pct > 25:
            return None  # HARD REJECT: squeeze risk

        # Earnings filter
        days_earn = _days_to_earnings(info)
        if days_earn is not None and days_earn < 5:
            return None  # HARD REJECT: gap risk

        # Price history
        hist = tk.history(period='2y')
        if hist is None or len(hist) < 60:
            return None

        close = hist['Close'].dropna()

        # ── Technical sub-score (40 pts) ──────────────────────────────────
        tech_score = 0

        ma50  = float(close.rolling(50).mean().dropna().iloc[-1]) if len(close) >= 50 else None
        ma200 = float(close.rolling(200).mean().dropna().iloc[-1]) if len(close) >= 200 else None

        below_ma50  = (price < ma50)  if ma50  else False
        below_ma200 = (price < ma200) if ma200 else False
        death_cross = (ma50 < ma200)  if (ma50 and ma200) else False

        if below_ma50:  tech_score += 10
        if below_ma200: tech_score += 12
        if death_cross: tech_score += 8

        stage = _weinstein_stage(close)
        if stage == 4:   tech_score += 10
        elif stage == 3: tech_score += 5

        # RSI (momentum confirmation)
        rsi_d = _rsi(close)
        if not (rsi_d != rsi_d) and rsi_d < 45:
            tech_score += min(5, int((45 - rsi_d) / 5))

        # Distance from 52w high
        hi52 = float(close.tail(252).max())
        pct_from_hi52 = (price / hi52 - 1) * 100
        if pct_from_hi52 < -30: tech_score += 5
        elif pct_from_hi52 < -20: tech_score += 3

        tech_score = min(tech_score, 40)

        # ── Fundamental sub-score (35 pts) ────────────────────────────────
        fund_score = 0

        rev_growth  = _safe_float(info.get('revenueGrowth'))       # decimal: -0.10 = -10%
        fcf         = _safe_float(info.get('freeCashflow'))
        roe         = _safe_float(info.get('returnOnEquity'))
        de_ratio    = _safe_float(info.get('debtToEquity'))
        op_margin   = _safe_float(info.get('operatingMargins'))
        profit_mg   = _safe_float(info.get('profitMargins'))
        int_cover   = _safe_float(info.get('ebitda'))
        int_exp     = None
        try:
            fin = tk.financials
            if fin is not None and not fin.empty:
                ie_row = [r for r in fin.index if 'Interest' in str(r) and 'Expense' in str(r)]
                ebit_row = [r for r in fin.index if 'EBIT' == str(r) or 'Operating Income' in str(r)]
                if ie_row and ebit_row:
                    ie_val   = float(fin.loc[ie_row[0]].iloc[0])
                    ebit_val = float(fin.loc[ebit_row[0]].iloc[0])
                    if ie_val != 0:
                        int_cover = abs(ebit_val / ie_val)
        except Exception:
            pass

        if rev_growth is not None:
            rev_pct = rev_growth * 100
            if rev_pct < -10:  fund_score += 12
            elif rev_pct < -5: fund_score += 8
            elif rev_pct < 0:  fund_score += 5

        if fcf is not None and mktcap and mktcap > 0:
            fcf_yield = (fcf / mktcap) * 100
            if fcf_yield < -5:  fund_score += 10
            elif fcf_yield < 0: fund_score += 6

        if roe is not None:
            if roe < -0.10:  fund_score += 8
            elif roe < 0:    fund_score += 5

        if de_ratio is not None:
            if de_ratio > 300:  fund_score += 5   # >3× debt/equity
            elif de_ratio > 200: fund_score += 3

        if profit_mg is not None and profit_mg < -0.05:
            fund_score += 5

        # Piotroski from fundamentals CSV if available, otherwise compute
        piotroski = None
        if fund_row:
            piotroski = _safe_float(fund_row.get('piotroski_score'))
        if piotroski is None:
            piotroski = _piotroski(info)
        if piotroski is not None:
            if piotroski <= 2:   fund_score += 5
            elif piotroski <= 3: fund_score += 3

        fund_score = min(fund_score, 35)

        # ── Downside sub-score (15 pts) ────────────────────────────────────
        down_score = 0

        analyst_target = _safe_float(info.get('targetMeanPrice'))
        analyst_upside = None
        if analyst_target and price:
            analyst_upside = (analyst_target / price - 1) * 100
            if analyst_upside < -15: down_score += 10
            elif analyst_upside < -5: down_score += 6
            elif analyst_upside < 0:  down_score += 3

        # Analyst recommendation
        rec = (info.get('recommendationKey') or '').lower()
        if rec in ('sell', 'strong_sell', 'underperform'):
            down_score += 5
        elif rec == 'hold':
            down_score += 2

        # Negative analyst revision (proxy: revenueGrowth declining)
        if rev_growth is not None and rev_growth < -0.05:
            down_score += 3

        down_score = min(down_score, 15)

        # ── Safety sub-score (10 pts) ──────────────────────────────────────
        safety_score = 0

        if short_pct is not None:
            if short_pct < 5:   safety_score += 5   # Not crowded
            elif short_pct < 10: safety_score += 3

        if days_earn is None or days_earn > 14:
            safety_score += 5
        elif days_earn > 7:
            safety_score += 2

        safety_score = min(safety_score, 10)

        # ── Total & quality ───────────────────────────────────────────────
        total = tech_score + fund_score + down_score + safety_score

        if total < 40:
            return None  # Below threshold — not a convincing short

        if total >= 70:
            quality = 'ALTA'
        elif total >= 55:
            quality = 'MEDIA'
        else:
            quality = 'BAJA'

        # ── Squeeze risk label ────────────────────────────────────────────
        if short_pct is not None:
            if short_pct > 15:   squeeze = 'HIGH'
            elif short_pct > 8:  squeeze = 'MEDIUM'
            else:                squeeze = 'LOW'
        else:
            squeeze = 'UNKNOWN'

        # ── Key risks ─────────────────────────────────────────────────────
        risks = []
        if squeeze in ('HIGH', 'MEDIUM'):
            risks.append(f'SHORT_INTEREST_{short_pct:.0f}pct')
        if days_earn is not None and days_earn <= 14:
            risks.append(f'EARNINGS_{days_earn}d')
        if de_ratio and de_ratio > 200:
            risks.append('HIGH_DEBT')
        if below_ma50 and not below_ma200:
            risks.append('ABOVE_MA200_YET')  # partial breakdown
        if not death_cross and below_ma50:
            risks.append('NO_DEATH_CROSS')

        # ── Rev growth as pct ─────────────────────────────────────────────
        rev_pct = (rev_growth * 100) if rev_growth is not None else None
        fcf_yield_pct = ((fcf / mktcap) * 100) if (fcf and mktcap and mktcap > 0) else None
        roe_pct = (roe * 100) if roe is not None else None

        return {
            'ticker':             ticker,
            'company_name':       info.get('longName') or info.get('shortName') or ticker,
            'sector':             info.get('sector') or '',
            'industry':           info.get('industry') or '',
            'short_score':        round(total, 1),
            'short_quality':      quality,
            'tech_score':         tech_score,
            'fund_score':         fund_score,
            'down_score':         down_score,
            'safety_score':       safety_score,
            'current_price':      round(price, 2),
            'market_cap':         int(mktcap),
            'analyst_target':     round(analyst_target, 2) if analyst_target else None,
            'analyst_upside_pct': round(analyst_upside, 1) if analyst_upside is not None else None,
            'analyst_rec':        rec,
            'short_interest_pct': round(short_pct, 1) if short_pct is not None else None,
            'squeeze_risk':       squeeze,
            'days_to_earnings':   days_earn,
            'earnings_warning':   bool(days_earn is not None and days_earn <= 14),
            'below_ma50':         below_ma50,
            'below_ma200':        below_ma200,
            'death_cross':        death_cross,
            'weinstein_stage':    stage,
            'pct_from_52w_high':  round(pct_from_hi52, 1),
            'rsi_daily':          round(rsi_d, 1) if rsi_d == rsi_d else None,
            'rev_growth_yoy':     round(rev_pct, 1) if rev_pct is not None else None,
            'fcf_yield_pct':      round(fcf_yield_pct, 1) if fcf_yield_pct is not None else None,
            'roe_pct':            round(roe_pct, 1) if roe_pct is not None else None,
            'debt_to_equity':     round(de_ratio / 100, 2) if de_ratio is not None else None,
            'operating_margin':   round(op_margin * 100, 1) if op_margin is not None else None,
            'piotroski_score':    int(piotroski) if piotroski is not None else None,
            'key_risks':          json.dumps(risks),
            'short_thesis':       '',
            'analyzed_at':        datetime.now().strftime('%Y-%m-%d %H:%M'),
        }

    except Exception as e:
        print(f"    {ticker}: error — {e}")
        return None


# ── AI thesis generator ────────────────────────────────────────────────────────

def _generate_theses(opportunities: list) -> list:
    """Use Groq to generate a concise short thesis for top candidates."""
    api_key = os.environ.get('GROQ_API_KEY', '')
    if not api_key:
        return opportunities

    top = [o for o in opportunities if o['short_quality'] == 'ALTA'][:8]
    if not top:
        top = opportunities[:5]
    if not top:
        return opportunities

    try:
        import requests
        summaries = []
        for o in top:
            summaries.append(
                f"{o['ticker']} ({o['company_name']}): "
                f"score {o['short_score']}/100, "
                f"below MA50={o['below_ma50']}, MA200={o['below_ma200']}, "
                f"Death Cross={o['death_cross']}, Weinstein S{o['weinstein_stage']}, "
                f"Rev growth={o['rev_growth_yoy']}%, FCF yield={o['fcf_yield_pct']}%, "
                f"ROE={o['roe_pct']}%, Analyst target={o['analyst_target']} "
                f"({o['analyst_upside_pct']}% upside/{('downside' if (o['analyst_upside_pct'] or 0) < 0 else '')}), "
                f"Squeeze risk={o['squeeze_risk']}, Risks={o['key_risks']}"
            )

        prompt = (
            "Eres un analista bajista experto. Para cada empresa genera una tesis corta "
            "en español (máx 2 frases) explicando POR QUÉ es un buen corto ahora mismo. "
            "Sé específico con los datos. Responde en JSON: "
            "{\"tickers\": [{\"ticker\": \"X\", \"thesis\": \"...\"}]}\n\n"
            + "\n".join(summaries)
        )

        resp = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={
                'model': 'llama-3.3-70b-versatile',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.3,
                'max_tokens': 1200,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            raw = resp.json()['choices'][0]['message']['content']
            # Extract JSON
            start = raw.find('{')
            end   = raw.rfind('}') + 1
            if start >= 0 and end > start:
                parsed = json.loads(raw[start:end])
                thesis_map = {t['ticker']: t['thesis'] for t in parsed.get('tickers', [])}
                for o in opportunities:
                    if o['ticker'] in thesis_map:
                        o['short_thesis'] = thesis_map[o['ticker']]
                print(f"  AI theses generated for {len(thesis_map)} tickers")
    except Exception as e:
        print(f"  AI thesis generation failed: {e}")

    return opportunities


# ── Main ──────────────────────────────────────────────────────────────────────

def run_short_scanner(extra_tickers: Optional[list] = None) -> list:
    # Build universe: deduplicated list
    universe = list(dict.fromkeys(SHORT_UNIVERSE + (extra_tickers or [])))

    # Load existing fundamental scores for data reuse
    fund_by_ticker: dict = {}
    fund_csv = DOCS / 'fundamental_scores.csv'
    if fund_csv.exists():
        with open(fund_csv) as f:
            for row in csv.DictReader(f):
                fund_by_ticker[row['ticker']] = row

    # Add tickers from fundamental scores that might be overvalued
    for ticker, row in fund_by_ticker.items():
        try:
            upside = float(row.get('analyst_upside_pct') or 0)
            if upside < -5 and ticker not in universe:
                universe.append(ticker)
        except Exception:
            pass

    print(f"Short scanner: {len(universe)} tickers to analyze")

    results = []
    for i, ticker in enumerate(universe):
        print(f"  [{i+1}/{len(universe)}] {ticker}...", end=' ', flush=True)
        row = _score_ticker(ticker, fund_row=fund_by_ticker.get(ticker))
        if row:
            results.append(row)
            print(f"score={row['short_score']} ({row['short_quality']})")
        else:
            print("skip")
        time.sleep(0.25)

    # Sort by score descending
    results.sort(key=lambda x: x['short_score'], reverse=True)

    # Generate AI theses for top picks
    results = _generate_theses(results)

    # Save CSV
    if results:
        csv_path = DOCS / 'short_opportunities.csv'
        fieldnames = list(results[0].keys())
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"\nSaved {len(results)} short opportunities → {csv_path}")

        # Save JSON (for API)
        json_path = DOCS / 'short_opportunities.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                'scan_date': datetime.now().strftime('%Y-%m-%d'),
                'count': len(results),
                'alta':  sum(1 for r in results if r['short_quality'] == 'ALTA'),
                'media': sum(1 for r in results if r['short_quality'] == 'MEDIA'),
                'baja':  sum(1 for r in results if r['short_quality'] == 'BAJA'),
                'data':  results,
            }, f, indent=2, default=str)

    else:
        print("\nNo short opportunities found with current criteria.")

    return results


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--tickers', nargs='*', help='Additional tickers to scan')
    args = parser.parse_args()
    run_short_scanner(extra_tickers=args.tickers)
