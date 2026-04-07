#!/usr/bin/env python3
"""
Catalyst Scanner — Calendario unificado de catalizadores de mercado.

Fuentes:
  1. Macro       — FOMC, CPI, NFP, PCE, GDP (de economic_calendar.json)
  2. Earnings    — Próximos earnings con historial de sorpresas (yfinance)
  3. FDA/PDUFA   — Fechas de aprobación de fármacos (scraping FDA.gov)
  4. OpEx        — Vencimientos de opciones (3er viernes de cada mes)
  5. Dividendos  — Ex-dividend dates para tickers en nuestro universo

Output: docs/catalysts.json
"""

import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Optional

import yfinance as yf

DOCS = Path('docs')
DOCS.mkdir(exist_ok=True)

TODAY = date.today()
HORIZON_DAYS = 90  # cuántos días hacia adelante cubrir

# ─── Universo de tickers a monitorear ────────────────────────────────────────
# VALUE universe cargado dinámicamente + fallback hardcoded
PHARMA_TICKERS = [
    'LLY', 'NVO', 'PFE', 'MRK', 'ABBV', 'BMY', 'AMGN', 'GILD', 'BIIB',
    'REGN', 'VRTX', 'MRNA', 'BNTX', 'SGEN', 'ALNY', 'RARE', 'SRPT',
    'IONS', 'ACAD', 'FOLD', 'PTCT', 'NBIX', 'INCY', 'JAZZ', 'EXEL',
    'AZN', 'GSK', 'SNY', 'NVS', 'RHHBY',
]

BROAD_UNIVERSE = [
    # Mega caps (alta relevancia macro)
    'AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA', 'BRK-B',
    'JPM', 'V', 'MA', 'UNH', 'HD', 'PG', 'JNJ', 'XOM', 'CVX', 'BAC',
    # Value/GARP targets
    'LMT', 'RTX', 'GD', 'NOC', 'BA', 'CAT', 'DE', 'EMR', 'ETN', 'HON',
    'WMT', 'COST', 'TGT', 'LOW', 'TJX', 'DIS', 'CMCSA', 'NKE', 'MCD',
    'KO', 'PEP', 'PM', 'MO', 'BTI', 'DEO', 'SAP', 'ASML', 'TTE', 'SHEL',
    'BLK', 'GS', 'MS', 'C', 'WFC', 'AXP', 'CB', 'MMC', 'TRV', 'ALL',
    'MCO', 'SPGI', 'ICE', 'MSCI', 'FDS',
    # Healthcare / Managed care
    'CVS', 'HUM', 'ELV', 'CI', 'CNC', 'MOH',
    # Tech secondary
    'CRM', 'ORCL', 'SAP', 'IBM', 'ACN', 'INTU', 'ADBE', 'NOW',
    # Energy
    'SLB', 'HAL', 'PSX', 'VLO', 'MPC',
    # Sector ETFs (para eventos macro)
    'XLF', 'XLK', 'XLV', 'XLE', 'XLI', 'XLU', 'XLRE', 'XLY', 'XLP', 'XLB',
    'TLT', 'HYG', 'GLD', 'SLV', 'USO',
] + PHARMA_TICKERS


# ─── SECTOR IMPACT MAP para eventos macro ────────────────────────────────────
MACRO_SECTOR_IMPACT = {
    'FED': {
        'description': 'Decisión de tipos Fed — impacto directo en renta fija y sectores rate-sensitive',
        'bullish_sectors': ['XLF', 'XLK', 'XLY'],
        'bearish_sectors': ['TLT', 'XLRE', 'XLU'],
        'key_tickers': ['TLT', 'XLF', 'XLRE', 'GLD', 'JPM', 'BAC', 'WFC'],
        'direction': 'VOLATILE',
        'avg_move_pct': 1.2,
    },
    'CPI': {
        'description': 'IPC — dato clave de inflación. Por encima de estimaciones = bearish bonds, bearish growth',
        'bullish_sectors': ['XLE', 'GLD', 'SLV', 'XLRE'],
        'bearish_sectors': ['TLT', 'XLK', 'XLY'],
        'key_tickers': ['TLT', 'GLD', 'XLF', 'XLE', 'AAPL', 'AMZN'],
        'direction': 'VOLATILE',
        'avg_move_pct': 0.9,
    },
    'JOBS': {
        'description': 'NFP — mercado laboral. Muy fuerte = Fed hawkish = bearish tech/growth',
        'bullish_sectors': ['XLF', 'XLY', 'XLK'],
        'bearish_sectors': ['TLT', 'GLD'],
        'key_tickers': ['TLT', 'XLF', 'DIS', 'MCD', 'WMT'],
        'direction': 'VOLATILE',
        'avg_move_pct': 0.7,
    },
    'PCE': {
        'description': 'PCE — inflación preferida de la Fed. Mide presión de precios del consumidor',
        'bullish_sectors': ['XLE', 'GLD'],
        'bearish_sectors': ['TLT', 'XLRE'],
        'key_tickers': ['TLT', 'GLD', 'XLF'],
        'direction': 'VOLATILE',
        'avg_move_pct': 0.5,
    },
    'GDP': {
        'description': 'PIB — crecimiento económico. Por debajo = recesión temor = risk-off',
        'bullish_sectors': ['XLK', 'XLY', 'XLI'],
        'bearish_sectors': ['XLU', 'TLT', 'GLD'],
        'key_tickers': ['SPY', 'QQQ', 'IWM', 'TLT'],
        'direction': 'VOLATILE',
        'avg_move_pct': 0.8,
    },
    'EARNINGS': {
        'description': 'Inicio temporada de resultados — mayor volatilidad individual',
        'bullish_sectors': [],
        'bearish_sectors': [],
        'key_tickers': ['JPM', 'BAC', 'GS', 'WFC'],
        'direction': 'VOLATILE',
        'avg_move_pct': 0.3,
    },
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

def days_until(date_str: str) -> int:
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d').date()
        return (d - TODAY).days
    except Exception:
        return 9999


def third_friday(year: int, month: int) -> date:
    """Tercer viernes del mes — vencimiento estándar de opciones."""
    first_day = date(year, month, 1)
    # weekday() 4 = Friday
    first_friday = first_day + timedelta(days=(4 - first_day.weekday()) % 7)
    return first_friday + timedelta(weeks=2)


def load_value_tickers() -> list:
    """Carga tickers del universo VALUE ya procesado."""
    tickers = set()
    for fname in ['value_opportunities.csv', 'value_opportunities_filtered.csv',
                  'momentum_opportunities.csv', 'fundamental_scores.csv']:
        path = DOCS / fname
        if path.exists():
            try:
                import csv
                with open(path) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        t = row.get('ticker', '').strip().upper()
                        if t and len(t) <= 10:
                            tickers.add(t)
            except Exception:
                pass
    return list(tickers)


# ─── 1. MACRO EVENTS ──────────────────────────────────────────────────────────

def load_macro_events() -> list:
    """Carga eventos macro de economic_calendar.json y enriquece con sector impact."""
    econ_path = DOCS / 'economic_calendar.json'
    if not econ_path.exists():
        return []

    try:
        with open(econ_path) as f:
            data = json.load(f)
    except Exception:
        return []

    events = []
    cutoff = (TODAY + timedelta(days=HORIZON_DAYS)).strftime('%Y-%m-%d')
    today_str = TODAY.strftime('%Y-%m-%d')

    for e in data.get('events', []):
        edate = e.get('date', '')
        if not edate or edate < today_str or edate > cutoff:
            continue

        etype = e.get('type', 'MACRO')
        impact_info = MACRO_SECTOR_IMPACT.get(etype, {})
        days = days_until(edate)

        events.append({
            'id': f"macro-{edate}-{etype}",
            'category': 'MACRO',
            'type': etype,
            'date': edate,
            'days_away': days,
            'title': e.get('event', etype),
            'description': e.get('description', impact_info.get('description', '')),
            'impact': e.get('impact', 'HIGH'),
            'direction_bias': impact_info.get('direction', 'VOLATILE'),
            'avg_move_pct': impact_info.get('avg_move_pct', 0),
            'affected_tickers': impact_info.get('key_tickers', []),
            'bullish_sectors': impact_info.get('bullish_sectors', []),
            'bearish_sectors': impact_info.get('bearish_sectors', []),
            'source': 'BLS/Fed',
            'ticker': None,
            'company': None,
        })

    return events


# ─── 2. OPTIONS EXPIRATION ────────────────────────────────────────────────────

def generate_opex_events() -> list:
    """Genera fechas de vencimiento de opciones (3er viernes del mes)."""
    events = []
    cutoff = TODAY + timedelta(days=HORIZON_DAYS)

    current = date(TODAY.year, TODAY.month, 1)
    while current <= cutoff:
        opex = third_friday(current.year, current.month)
        if opex >= TODAY and opex <= cutoff:
            days = (opex - TODAY).days
            opex_str = opex.strftime('%Y-%m-%d')
            # Semana de OpEx — alta volatilidad intraday
            events.append({
                'id': f"opex-{opex_str}",
                'category': 'OPTIONS_EXPIRY',
                'type': 'OPEX',
                'date': opex_str,
                'days_away': days,
                'title': f"OpEx {opex.strftime('%B %Y')}",
                'description': 'Vencimiento mensual de opciones. Mayor volatilidad intraday, especialmente el jueves-viernes previo.',
                'impact': 'MEDIUM',
                'direction_bias': 'VOLATILE',
                'avg_move_pct': 0.3,
                'affected_tickers': ['SPY', 'QQQ', 'IWM'],
                'bullish_sectors': [],
                'bearish_sectors': [],
                'source': 'CBOE',
                'ticker': None,
                'company': None,
            })
        # Avanzar mes
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    return events


# ─── 3. EARNINGS WITH SURPRISE HISTORY ───────────────────────────────────────

def get_earnings_history(ticker: str) -> dict:
    """
    Obtiene historial de earnings: últimas 4 sorpresas y movimiento post-earnings.
    Returns: {beat_count, miss_count, avg_surprise_pct, avg_move_pct, quarters}
    """
    try:
        tk = yf.Ticker(ticker)
        # Historial de earnings
        hist = tk.earnings_history
        if hist is None or len(hist) == 0:
            return {}

        quarters = []
        for _, row in hist.head(8).iterrows():
            eps_est = row.get('epsEstimate')
            eps_act = row.get('epsActual')
            if eps_est is None or eps_act is None:
                continue
            surprise = 0
            if eps_est != 0:
                surprise = ((eps_act - eps_est) / abs(eps_est)) * 100
            quarters.append({
                'date': str(row.name.date()) if hasattr(row.name, 'date') else str(row.name)[:10],
                'eps_est': round(float(eps_est), 2),
                'eps_act': round(float(eps_act), 2),
                'surprise_pct': round(surprise, 1),
                'beat': surprise > 0,
            })

        if not quarters:
            return {}

        beat_count = sum(1 for q in quarters if q['beat'])
        miss_count = len(quarters) - beat_count
        avg_surprise = sum(q['surprise_pct'] for q in quarters) / len(quarters)

        return {
            'beat_count': beat_count,
            'miss_count': miss_count,
            'total_quarters': len(quarters),
            'avg_surprise_pct': round(avg_surprise, 1),
            'beat_rate': round(beat_count / len(quarters) * 100, 0),
            'last_quarters': quarters[:4],
        }
    except Exception:
        return {}


def load_earnings_events(universe: list) -> list:
    """
    Obtiene próximos earnings con historial de sorpresas.
    Solo tickers con earnings en los próximos HORIZON_DAYS días.
    """
    events = []
    cutoff = TODAY + timedelta(days=HORIZON_DAYS)
    print(f"  Earnings: analizando {len(universe)} tickers...")

    for i, ticker in enumerate(universe):
        try:
            if i > 0 and i % 20 == 0:
                print(f"    [{i}/{len(universe)}] ...")
                time.sleep(1)

            tk = yf.Ticker(ticker)
            cal = tk.calendar

            if cal is None:
                continue

            # Earnings date
            earn_date = None
            if 'Earnings Date' in cal:
                ed = cal['Earnings Date']
                if hasattr(ed, '__iter__') and not isinstance(ed, str):
                    ed = list(ed)
                    earn_date = ed[0] if ed else None
                else:
                    earn_date = ed

            if earn_date is None:
                continue

            # Normalizar a date
            if hasattr(earn_date, 'date'):
                earn_date = earn_date.date()
            elif isinstance(earn_date, str):
                try:
                    earn_date = datetime.strptime(earn_date[:10], '%Y-%m-%d').date()
                except Exception:
                    continue

            if earn_date < TODAY or earn_date > cutoff:
                continue

            earn_str = earn_date.strftime('%Y-%m-%d')
            days = (earn_date - TODAY).days

            # Info básica del ticker
            info = tk.info or {}
            company = info.get('shortName', info.get('longName', ticker))
            sector = info.get('sector', '')
            price = info.get('currentPrice') or info.get('regularMarketPrice')
            mkt_cap = info.get('marketCap')

            # Estimaciones
            eps_est = None
            if 'Earnings Average' in cal:
                eps_est = cal['Earnings Average']
            elif 'EPS Estimate' in cal:
                eps_est = cal['EPS Estimate']

            # Historial de sorpresas (solo si vale la pena — tickers relevantes)
            history = {}
            if mkt_cap and mkt_cap > 5e9:  # solo large/mid caps para no sobrecargar
                time.sleep(0.3)
                history = get_earnings_history(ticker)

            # Clasificación de riesgo/oportunidad
            beat_rate = history.get('beat_rate', 50)
            avg_surprise = history.get('avg_surprise_pct', 0)

            if beat_rate >= 75 and avg_surprise >= 5:
                direction = 'BULLISH'
                label = f"Históricamente bate estimaciones {int(beat_rate)}% del tiempo (+{avg_surprise:.1f}% sorpresa media)"
            elif beat_rate <= 40 or avg_surprise <= -3:
                direction = 'BEARISH'
                label = f"Históricamente decepciona — bate solo {int(beat_rate)}% del tiempo"
            else:
                direction = 'VOLATILE'
                label = f"Resultados mixtos — bate {int(beat_rate)}% del tiempo"

            if not history:
                direction = 'UNKNOWN'
                label = 'Sin historial disponible'

            # Warning si earnings muy próximos (riesgo entrada)
            impact = 'HIGH' if days <= 7 else 'MEDIUM'

            events.append({
                'id': f"earnings-{ticker}-{earn_str}",
                'category': 'EARNINGS',
                'type': 'EARNINGS',
                'date': earn_str,
                'days_away': days,
                'title': f"{ticker} — Earnings Q",
                'description': label,
                'impact': impact,
                'direction_bias': direction,
                'avg_move_pct': abs(avg_surprise) if avg_surprise else None,
                'affected_tickers': [ticker],
                'bullish_sectors': [],
                'bearish_sectors': [],
                'source': 'yfinance',
                'ticker': ticker,
                'company': company,
                'sector': sector,
                'current_price': round(float(price), 2) if price else None,
                'market_cap': mkt_cap,
                'eps_estimate': round(float(eps_est), 2) if eps_est else None,
                'earnings_history': history,
                'earnings_warning': days <= 7,
            })

        except Exception as e:
            if 'Too Many Requests' in str(e):
                print(f"    Rate limit en {ticker}, esperando 10s...")
                time.sleep(10)
            continue

    print(f"  Earnings: {len(events)} próximos encontrados")
    return events


# ─── 4. FDA PDUFA CALENDAR ────────────────────────────────────────────────────

def scrape_fda_pdufa() -> list:
    """
    Obtiene fechas PDUFA de la FDA (decisiones de aprobación de fármacos).
    Fuente: FDA.gov drugs@FDA — filtramos nuestro universo pharma.
    Como fallback, rastreamos eventos conocidos de yfinance para farma.
    """
    events = []
    print("  FDA: rastreando pipeline farmacéutico...")

    # Para cada pharma ticker, buscar en yfinance si tiene eventos próximos
    for ticker in PHARMA_TICKERS:
        try:
            time.sleep(0.4)
            tk = yf.Ticker(ticker)
            info = tk.info or {}

            # Buscar en SEC filings / news si hay PDUFA
            # yfinance no tiene PDUFA directamente pero sí en calendar
            cal = tk.calendar or {}
            company = info.get('shortName', ticker)
            sector = info.get('sector', 'Healthcare')

            # Solo procesamos si es healthcare
            if sector and 'Health' not in sector and 'Pharma' not in sector and 'Biotech' not in sector:
                continue

            # Buscar en news recientes menciones de FDA/PDUFA
            try:
                news = tk.news or []
                for article in news[:5]:
                    title = article.get('title', '').upper()
                    if any(kw in title for kw in ['FDA', 'PDUFA', 'APPROVAL', 'NDA', 'BLA', 'ADVISORY']):
                        pub_date = article.get('providerPublishTime', 0)
                        if pub_date:
                            article_date = datetime.fromtimestamp(pub_date).date()
                            if article_date >= TODAY - timedelta(days=30):
                                events.append({
                                    'id': f"fda-news-{ticker}-{article_date}",
                                    'category': 'FDA',
                                    'type': 'FDA_NEWS',
                                    'date': article_date.strftime('%Y-%m-%d'),
                                    'days_away': (article_date - TODAY).days,
                                    'title': f"{ticker} — {article.get('title', 'FDA Event')[:80]}",
                                    'description': f"Noticia FDA reciente para {company}. Revisar para posible catalizador.",
                                    'impact': 'HIGH',
                                    'direction_bias': 'UNKNOWN',
                                    'avg_move_pct': 8.0,  # FDA approval avg move
                                    'affected_tickers': [ticker],
                                    'bullish_sectors': [],
                                    'bearish_sectors': [],
                                    'source': 'FDA/News',
                                    'ticker': ticker,
                                    'company': company,
                                    'sector': sector,
                                    'current_price': info.get('currentPrice'),
                                    'market_cap': info.get('marketCap'),
                                    'earnings_history': {},
                                    'earnings_warning': False,
                                    'url': article.get('link', ''),
                                })
                        break  # una noticia FDA por ticker es suficiente
            except Exception:
                pass

        except Exception:
            continue

    print(f"  FDA: {len(events)} eventos detectados")
    return events


# ─── 5. DIVIDEND EX-DATES ─────────────────────────────────────────────────────

def load_dividend_events(tickers: list) -> list:
    """Ex-dividend dates para tickers con dividendo en nuestro universo."""
    events = []
    print(f"  Dividendos: rastreando {min(len(tickers), 60)} tickers...")
    cutoff = TODAY + timedelta(days=60)  # ventana más corta para dividendos

    # Solo tickers conocidos por tener dividendo (evitar perder tiempo en growth)
    div_candidates = [t for t in tickers if t in {
        'AAPL', 'MSFT', 'JNJ', 'PG', 'KO', 'PEP', 'XOM', 'CVX', 'JPM', 'BAC',
        'WFC', 'MRK', 'ABBV', 'BMY', 'LMT', 'RTX', 'GD', 'HON', 'CAT', 'DE',
        'TJX', 'HD', 'LOW', 'MCD', 'WMT', 'COST', 'TGT', 'V', 'MA', 'AXP',
        'BLK', 'GS', 'MS', 'CB', 'MMC', 'TRV', 'ALL', 'MCO', 'SPGI',
        'BTI', 'PM', 'MO', 'DEO', 'TTE', 'SHEL', 'BRK-B',
        'XLF', 'XLE', 'XLU', 'XLP', 'TLT', 'GLD',
    }]

    for ticker in div_candidates[:50]:  # máx 50
        try:
            time.sleep(0.3)
            tk = yf.Ticker(ticker)
            info = tk.info or {}
            ex_date = info.get('exDividendDate')
            div_yield = info.get('dividendYield', 0) or 0
            div_rate = info.get('dividendRate', 0) or 0

            if not ex_date or div_yield <= 0:
                continue

            # Convertir timestamp a date
            if isinstance(ex_date, (int, float)):
                ex_date = datetime.fromtimestamp(ex_date).date()
            elif isinstance(ex_date, str):
                try:
                    ex_date = datetime.strptime(ex_date[:10], '%Y-%m-%d').date()
                except Exception:
                    continue

            if ex_date < TODAY or ex_date > cutoff:
                continue

            ex_str = ex_date.strftime('%Y-%m-%d')
            days = (ex_date - TODAY).days
            company = info.get('shortName', ticker)

            events.append({
                'id': f"div-{ticker}-{ex_str}",
                'category': 'DIVIDEND',
                'type': 'EX_DIVIDEND',
                'date': ex_str,
                'days_away': days,
                'title': f"{ticker} — Ex-Dividend ({div_yield:.1%} yield)",
                'description': f"{company} — Fecha ex-dividendo. Dividend: ${div_rate:.2f}/año ({div_yield:.1%} yield). Comprar antes de esta fecha para cobrar dividendo.",
                'impact': 'LOW',
                'direction_bias': 'BULLISH',
                'avg_move_pct': -div_rate / 4 if div_rate else 0,  # aprox drop post ex-date
                'affected_tickers': [ticker],
                'bullish_sectors': [],
                'bearish_sectors': [],
                'source': 'yfinance',
                'ticker': ticker,
                'company': company,
                'sector': info.get('sector', ''),
                'current_price': info.get('currentPrice'),
                'market_cap': info.get('marketCap'),
                'dividend_yield': div_yield,
                'dividend_rate': div_rate,
                'earnings_history': {},
                'earnings_warning': False,
            })

        except Exception:
            continue

    print(f"  Dividendos: {len(events)} ex-dates encontradas")
    return events


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("CATALYST SCANNER")
    print(f"Fecha: {TODAY}  |  Horizonte: {HORIZON_DAYS} días")
    print("=" * 60)

    # Cargar universo VALUE propio + broad universe
    value_tickers = load_value_tickers()
    all_tickers = list(set(BROAD_UNIVERSE + value_tickers))
    print(f"Universo total: {len(all_tickers)} tickers")

    all_events = []

    # 1. Macro
    print("\n[1/5] Cargando eventos macro...")
    macro_events = load_macro_events()
    all_events.extend(macro_events)
    print(f"  Macro: {len(macro_events)} eventos")

    # 2. Options expiry
    print("\n[2/5] Generando vencimientos de opciones...")
    opex_events = generate_opex_events()
    all_events.extend(opex_events)
    print(f"  OpEx: {len(opex_events)} fechas")

    # 3. Earnings
    print("\n[3/5] Analizando earnings próximos...")
    # Earnings universe: value tickers + broad (sin ETFs)
    earnings_universe = [t for t in all_tickers if not t.startswith('XL') and t not in {'TLT','HYG','GLD','SLV','USO','SPY','QQQ','IWM','DIA'}]
    earnings_events = load_earnings_events(earnings_universe[:120])  # máx 120 tickers
    all_events.extend(earnings_events)

    # 4. FDA
    print("\n[4/5] Rastreando catalizadores FDA/Pharma...")
    fda_events = scrape_fda_pdufa()
    all_events.extend(fda_events)

    # 5. Dividendos
    print("\n[5/5] Buscando ex-dividend dates...")
    div_tickers = list(set(BROAD_UNIVERSE + value_tickers))
    div_events = load_dividend_events(div_tickers)
    all_events.extend(div_events)

    # Ordenar por fecha
    all_events.sort(key=lambda e: (e['date'], e['category']))

    # Deduplicate por id
    seen = set()
    unique_events = []
    for e in all_events:
        if e['id'] not in seen:
            seen.add(e['id'])
            unique_events.append(e)

    # Stats
    by_category = {}
    for e in unique_events:
        cat = e['category']
        by_category[cat] = by_category.get(cat, 0) + 1

    output = {
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'scan_date': TODAY.strftime('%Y-%m-%d'),
        'horizon_days': HORIZON_DAYS,
        'total_events': len(unique_events),
        'by_category': by_category,
        'events': unique_events,
    }

    out_path = DOCS / 'catalysts.json'
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n{'=' * 60}")
    print(f"OUTPUT: {out_path}")
    print(f"Total eventos: {len(unique_events)}")
    for cat, count in sorted(by_category.items()):
        print(f"  {cat}: {count}")
    print("=" * 60)


if __name__ == '__main__':
    main()
