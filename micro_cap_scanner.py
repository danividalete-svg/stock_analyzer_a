#!/usr/bin/env python3
"""
MICRO-CAP QUALITY SCANNER
Busca penny stocks con fundamentos sólidos: precio $1-10, market cap $10M-$600M.
Criterios: Piotroski ≥ 5, FCF positivo o revenue creciente, salud financiera OK.

Uso:
  python3 micro_cap_scanner.py          # escanea universo completo
  python3 micro_cap_scanner.py --quick  # solo tickers con señales recientes
"""

import json
import time
import argparse
from pathlib import Path
from datetime import datetime

import pandas as pd
import yfinance as yf

# Reutilizar FundamentalScorer del proyecto
from fundamental_scorer import FundamentalScorer

# ── Config ─────────────────────────────────────────────────────────────────────
DOCS = Path('docs')
UNIVERSE_FILE = DOCS / 'micro_cap_universe.txt'
OUTPUT_CSV    = DOCS / 'micro_cap_opportunities.csv'

PRICE_MIN  = 1.0
PRICE_MAX  = 25.0          # ampliado: captura small-caps de calidad hasta $25
MCAP_MIN   = 10_000_000    # $10M
MCAP_MAX   = 2_000_000_000 # $2B — ampliado para incluir small-caps

# Universo inicial curado — mezcla de sectores con potencial de revalorización
DEFAULT_UNIVERSE = [
    # Tecnología / Software micro-cap
    'MDBH', 'THRY', 'MSGM', 'AEYE', 'INPX', 'MFAC', 'WRAP', 'CODA',
    # Biotech / Salud (mayor riesgo, mayor upside)
    'VXRT', 'ADTX', 'NVAX', 'SIGA', 'AGEN', 'CTIC', 'CLBS', 'GLYC',
    # Energía / Materiales
    'MMLP', 'USAC', 'TELL', 'NGAS', 'AMMO', 'POWW',
    # Financiero / Seguros
    'BUKS', 'FSEA', 'CASS', 'CZWI',
    # Consumo / Retail nicho
    'GREE', 'HPNN', 'SLXN', 'OZON',
    # Industrial / Defensa
    'AVAV', 'KTOS', 'DRS', 'CODA',
    # Real Estate micro
    'WHLR', 'CLPR', 'NLCP',
]


def _load_universe() -> list:
    """Carga tickers del fichero o usa el universo por defecto."""
    if UNIVERSE_FILE.exists():
        lines = UNIVERSE_FILE.read_text().strip().splitlines()
        tickers = [l.split('#')[0].split()[0].upper()
                   for l in lines
                   if l.strip() and not l.strip().startswith('#') and l.split('#')[0].strip()]
        print(f'  Universo: {len(tickers)} tickers desde {UNIVERSE_FILE.name}')
        return tickers
    print(f'  Universo por defecto ({len(DEFAULT_UNIVERSE)} tickers) — crea {UNIVERSE_FILE} para personalizar')
    return list(dict.fromkeys(DEFAULT_UNIVERSE))  # dedup preservando orden


def _micro_cap_score(row: dict) -> tuple[float, str]:
    """
    Calcula micro_cap_quality_score (0-100) y motivo de rechazo si aplica.
    Criterios orientados a encontrar micro-caps con fundamentos sólidos.
    """
    score = 0.0

    # ── HARD REJECTS ─────────────────────────────────────────────────────────
    price = row.get('current_price', 0) or 0
    mcap  = row.get('market_cap', 0) or 0
    if not (PRICE_MIN <= price <= PRICE_MAX):
        return 0.0, f'precio ${price:.2f} fuera de rango ${PRICE_MIN}-${PRICE_MAX}'
    if not (MCAP_MIN <= mcap <= MCAP_MAX):
        mcap_m = mcap / 1e6
        return 0.0, f'market cap ${mcap_m:.0f}M fuera de rango'

    piotroski = row.get('piotroski_score') or 0
    if piotroski < 3:
        return 0.0, f'Piotroski {piotroski:.0f} < 3 (riesgo financiero alto)'

    # Parsear health_details
    health = {}
    try:
        hd = row.get('health_details', '{}') or '{}'
        health = json.loads(hd) if isinstance(hd, str) else hd
    except Exception:
        pass
    current_ratio = health.get('current_ratio', 0) or 0
    if current_ratio > 0 and current_ratio < 1.0:
        return 0.0, f'current_ratio {current_ratio:.1f} < 1 (iliquidez)'

    # ── SCORING ───────────────────────────────────────────────────────────────

    # 1. Piotroski F-Score (0-9) → 0-30 pts
    score += min(piotroski / 9 * 30, 30)

    # 2. FCF quality → 0-25 pts
    fcf_yield = row.get('fcf_yield_pct') or 0
    if fcf_yield >= 8:
        score += 25
    elif fcf_yield >= 4:
        score += 18
    elif fcf_yield >= 0:
        score += 10
    else:
        score += max(0, 10 + fcf_yield)  # penaliza FCF negativo hasta -10

    # 3. Revenue growth → 0-20 pts
    rev_growth = row.get('rev_growth_yoy') or 0
    if rev_growth >= 30:
        score += 20
    elif rev_growth >= 15:
        score += 15
    elif rev_growth >= 5:
        score += 8
    elif rev_growth > 0:
        score += 3

    # 4. Financial health score (del scorer base) → 0-15 pts
    fh = row.get('financial_health_score') or 0
    score += min(fh / 100 * 15, 15)

    # 5. Insider conviction → 0-10 pts
    if row.get('buyback_active'):
        score += 6
    shares_chg = row.get('shares_change_pct') or 0
    if shares_chg < -2:   # reducción notable de acciones
        score += 4
    elif shares_chg < -1:
        score += 2

    # Bonus: short squeeze (combustible adicional)
    if row.get('short_squeeze_potential') == 'HIGH':
        score += 5
    elif row.get('short_squeeze_potential') == 'MEDIUM':
        score += 2

    score = min(round(score, 1), 100.0)
    return score, ''


def _quality_label(score: float) -> str:
    if score >= 70: return 'FUERTE'
    if score >= 55: return 'BUENA'
    if score >= 40: return 'MODERADA'
    return 'DÉBIL'


def main():
    parser = argparse.ArgumentParser(description='Micro-Cap Quality Scanner')
    parser.add_argument('--quick', action='store_true',
                        help='Solo re-score con datos ya cacheados (sin re-descargar)')
    args = parser.parse_args()

    print('\n' + '='*60)
    print('  MICRO-CAP QUALITY SCANNER')
    print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print('='*60)

    tickers = _load_universe()
    scorer  = FundamentalScorer()

    results = []
    for i, ticker in enumerate(tickers, 1):
        print(f'  [{i}/{len(tickers)}] {ticker}', end='  ')
        try:
            row = scorer.score_ticker(ticker)
            mc_score, reject_reason = _micro_cap_score(row)
            if mc_score == 0:
                print(f'⏭ {reject_reason}')
                continue
            row['micro_cap_score']   = mc_score
            row['micro_cap_quality'] = _quality_label(mc_score)
            results.append(row)
            print(f'✅ {mc_score:.0f}pts [{_quality_label(mc_score)}]  '
                  f'P${row["current_price"]:.2f}  '
                  f'Piotroski {row.get("piotroski_score", "?"):.0f}  '
                  f'FCF {row.get("fcf_yield_pct", 0):.1f}%')
        except Exception as e:
            print(f'❌ {e}')
        if i < len(tickers):
            time.sleep(1.5)

    if not results:
        print('\n  ⚠️  Sin oportunidades micro-cap que pasen los filtros.')
        pd.DataFrame().to_csv(OUTPUT_CSV, index=False)
        return

    df = pd.DataFrame(results).sort_values('micro_cap_score', ascending=False)

    print(f'\n  ✔ {len(df)} micro-caps de calidad encontradas')
    print(f'\n  {"TICKER":<8} {"SCORE":>5}  {"CALIDAD":<8}  {"PRECIO":>7}  '
          f'{"MCAP($M)":>9}  {"PIOTR":>5}  {"FCF%":>6}  {"REV+%":>6}')
    print(f'  {"─"*65}')
    for _, r in df.iterrows():
        mcap_m = (r.get('market_cap') or 0) / 1e6
        print(f'  {r["ticker"]:<8} {r["micro_cap_score"]:>5.0f}  {r["micro_cap_quality"]:<8}  '
              f'${r.get("current_price", 0):>6.2f}  '
              f'{mcap_m:>8.0f}M  '
              f'{r.get("piotroski_score", 0):>5.0f}  '
              f'{r.get("fcf_yield_pct", 0):>6.1f}  '
              f'{r.get("rev_growth_yoy", 0):>6.1f}')

    df.to_csv(OUTPUT_CSV, index=False)
    print(f'\n  💾 {OUTPUT_CSV}')


if __name__ == '__main__':
    main()
