#!/usr/bin/env python3
"""
UNUSUAL OPTIONS FLOW SCANNER
Detecta flujo inusual de opciones en nuestro universo de tickers.

Métricas clave (sin depender de OI — bug yfinance):
  - premium_usd = volume × lastPrice × 100  → dinero real apostado
  - near-dated (≤14d) + premium alto → apuesta especulativa/sweep
  - call_premium vs put_premium por ticker → sesgo direccional
  - IV elevada vs IV media del ticker → algo se espera

Señal: BULLISH si calls >> puts, BEARISH si puts >> calls.

Uso:
  python3 unusual_flow_scanner.py           # escanea universo completo
  python3 unusual_flow_scanner.py --quick   # solo VALUE + bounce picks
  python3 unusual_flow_scanner.py --ticker AAPL,NVDA  # tickers específicos

Guarda en:
  docs/unusual_flow.json   → datos estructurados para frontend
  docs/unusual_flow.csv    → tabla plana

Ejecutar cada 30 min en mercado abierto (9:30-16:00 ET) via GitHub Actions.
"""

import argparse
import json
import math
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf
import requests

# ── Rutas ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
DOCS = ROOT / 'docs'

# ── Umbrales ───────────────────────────────────────────────────────────────────
MIN_PREMIUM_USD    = 25_000   # mínimo por contrato para considerar "inusual"
LARGE_PREMIUM_USD  = 100_000  # notificar por Telegram si supera esto
MIN_VOLUME         = 50       # mínimo contratos para no ser ruido
MAX_DTE            = 45       # ignorar opciones a más de 45 días (larguísimas, poco signal)
SPECULATIVE_DTE    = 14       # ≤14 días = apuesta especulativa/sweep
MAX_WORKERS        = 6        # threads paralelos (respetar rate limit)
SLEEP_BETWEEN      = 0.3      # segundos entre requests por thread
TOP_N_PER_TICKER   = 3        # contratos top a guardar por ticker
HISTORY_DAYS       = 5        # días de histórico para calcular vol_vs_avg

# ── Telegram ───────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID   = os.environ.get('TELEGRAM_CHAT_ID', '')


# ─────────────────────────────────────────────────────────────────────────────
# Universe building
# ─────────────────────────────────────────────────────────────────────────────

def load_ticker_universe(quick: bool = False) -> list[str]:
    """Carga los tickers a escanear según el modo."""
    tickers = set()

    # Siempre incluir: VALUE picks filtrados (alta calidad)
    for path in ['value_opportunities_filtered.csv', 'european_value_opportunities_filtered.csv']:
        f = DOCS / path
        if f.exists():
            df = pd.read_csv(f)
            col = 'ticker' if 'ticker' in df.columns else df.columns[0]
            tickers.update(df[col].dropna().str.strip().str.upper().tolist())

    # Siempre incluir: bounce setups actuales
    mr = DOCS / 'mean_reversion_opportunities.json'
    if mr.exists():
        data = json.loads(mr.read_text())
        for opp in data.get('opportunities', []):
            t = opp.get('ticker', '')
            if t:
                tickers.add(t.strip().upper())

    if quick:
        return sorted(tickers)

    # Modo completo: añadir momentum + insider picks
    for path in ['momentum_opportunities.csv', 'value_opportunities.csv',
                 'insider_activity.csv', '5d_opportunities.csv']:
        f = DOCS / path
        if f.exists():
            try:
                df = pd.read_csv(f)
                col = 'ticker' if 'ticker' in df.columns else df.columns[0]
                tickers.update(df[col].dropna().str.strip().str.upper().tolist()[:200])
            except Exception:
                pass

    # Índices principales (siempre útil ver dónde va el dinero en SPY/QQQ)
    tickers.update(['SPY', 'QQQ', 'IWM', 'GLD', 'TLT', 'XLF', 'XLE', 'XLK'])

    # Limpiar tickers inválidos
    clean = [t for t in tickers if t and len(t) <= 5 and t.isalpha()]
    return sorted(clean)


# ─────────────────────────────────────────────────────────────────────────────
# Core: analizar opciones de un ticker
# ─────────────────────────────────────────────────────────────────────────────

def _barchart_oi(ticker: str) -> dict[str, int]:
    """
    Obtiene Open Interest de Barchart para los contratos más activos del ticker.
    Returns dict: {contractSymbol: open_interest}
    Barchart muestra OI actualizado (yfinance tiene bug #2408 donde devuelve 0).
    Parsea el JSON embebido en el HTML del quote de opciones.
    """
    url = f'https://www.barchart.com/stocks/quotes/{ticker}/options'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.barchart.com/',
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return {}
        # Buscar JSON embebido en window.__phx_data__ o similar
        # Barchart inyecta datos en un script con formato específico
        match = re.search(r'"openInterest"\s*:\s*(\d+)[^}]*"symbol"\s*:\s*"([^"]+)"', r.text)
        if not match:
            # Buscar tabla de OI directamente
            pairs = re.findall(r'"symbol"\s*:\s*"([^"]+)"[^}]*"openInterest"\s*:\s*(\d+)', r.text)
            return {sym: int(oi) for sym, oi in pairs if int(oi) > 0}
        return {}
    except Exception:
        return {}


def _safe_float(val) -> Optional[float]:
    try:
        v = float(val)
        return None if math.isnan(v) or math.isinf(v) else v
    except Exception:
        return None


def analyze_ticker_options(ticker: str) -> Optional[dict]:
    """
    Analiza las cadenas de opciones de un ticker.
    Returns dict con señal consolidada o None si no hay opciones / error.
    """
    try:
        t = yf.Ticker(ticker)
        exps = t.options
        if not exps:
            return None

        today = datetime.now(timezone.utc).date()
        unusual_contracts = []
        total_call_premium = 0.0
        total_put_premium  = 0.0
        total_call_volume  = 0
        total_put_volume   = 0
        iv_samples = []

        # Enriquecer OI desde Barchart (yfinance tiene bug que devuelve 0)
        barchart_oi = _barchart_oi(ticker)

        for exp_str in exps[:4]:   # máximo 4 expiries más cercanas
            try:
                exp_date = datetime.strptime(exp_str, '%Y-%m-%d').date()
                dte = (exp_date - today).days
                if dte < 0 or dte > MAX_DTE:
                    continue

                chain = t.option_chain(exp_str)
                time.sleep(SLEEP_BETWEEN)

                for side, df in [('CALL', chain.calls), ('PUT', chain.puts)]:
                    if df is None or df.empty:
                        continue
                    df = df.copy()
                    df = df[df['volume'].notna() & (df['volume'] > 0)]
                    if df.empty:
                        continue

                    df['premium_usd'] = df['volume'] * df['lastPrice'] * 100
                    df['dte'] = dte
                    df['side'] = side

                    # Acumular totales por ticker
                    if side == 'CALL':
                        total_call_premium += float(df['premium_usd'].sum())
                        total_call_volume  += int(df['volume'].sum())
                    else:
                        total_put_premium  += float(df['premium_usd'].sum())
                        total_put_volume   += int(df['volume'].sum())

                    # Recoger IV samples
                    iv_samples.extend(df['impliedVolatility'].dropna().tolist())

                    # Detectar contratos inusuales
                    unusual = df[
                        (df['premium_usd'] >= MIN_PREMIUM_USD) &
                        (df['volume'] >= MIN_VOLUME)
                    ]
                    for _, row in unusual.iterrows():
                        prem   = _safe_float(row.get('premium_usd', 0)) or 0
                        iv     = _safe_float(row.get('impliedVolatility'))
                        itm    = bool(row.get('inTheMoney', False))
                        vol    = int(row.get('volume', 0))
                        sym    = str(row.get('contractSymbol', ''))
                        # OI: preferir Barchart si yfinance devuelve 0
                        oi_yf  = int(row.get('openInterest', 0) or 0)
                        oi     = barchart_oi.get(sym, oi_yf) or oi_yf
                        vol_oi = round(vol / oi, 2) if oi > 0 else None
                        # Last trade date — key to know if trade is fresh (today) vs old
                        ltd_raw = row.get('lastTradeDate')
                        try:
                            ltd = pd.Timestamp(ltd_raw).strftime('%Y-%m-%d %H:%M') if ltd_raw else None
                        except Exception:
                            ltd = None
                        unusual_contracts.append({
                            'side':           side,
                            'strike':         _safe_float(row.get('strike')),
                            'expiry':         exp_str,
                            'dte':            dte,
                            'volume':         vol,
                            'open_interest':  oi,
                            'vol_oi_ratio':   vol_oi,
                            'last_price':     _safe_float(row.get('lastPrice')),
                            'last_trade_date': ltd,
                            'premium_usd':    round(prem, 0),
                            'iv':             round(iv, 3) if iv else None,
                            'itm':            itm,
                            'speculative':    dte <= SPECULATIVE_DTE,
                        })

            except Exception:
                continue

        if total_call_premium == 0 and total_put_premium == 0:
            return None

        # ── Precio actual y contexto de mercado (para interpretación) ─────────
        current_price  = None
        high_52w       = None
        drawdown_pct   = None
        try:
            fi = t.fast_info
            current_price = _safe_float(fi.get('lastPrice'))
            high_52w      = _safe_float(fi.get('yearHigh'))
            if current_price and high_52w and high_52w > 0:
                drawdown_pct = round((current_price - high_52w) / high_52w * 100, 1)
        except Exception:
            pass

        # Top contratos por premium
        top_contracts = sorted(unusual_contracts, key=lambda x: x['premium_usd'], reverse=True)[:TOP_N_PER_TICKER]

        # Señal direccional bruta
        net = total_call_premium - total_put_premium
        total_premium = total_call_premium + total_put_premium
        call_pct = total_call_premium / total_premium * 100 if total_premium > 0 else 50

        if call_pct >= 65:
            raw_signal = 'BULLISH'
        elif call_pct <= 35:
            raw_signal = 'BEARISH'
        else:
            raw_signal = 'MIXED'

        # ── Interpretación contextual ─────────────────────────────────────────
        # Puts muy ITM + acción ya caída mucho = probable profit-taking, no apuesta nueva
        # Calls muy ITM + acción ya subida mucho = probable cierre de calls largas
        flow_interpretation = 'STANDARD'
        interpretation_reason = ''

        if current_price and top_contracts:
            put_contracts  = [c for c in top_contracts if c['side'] == 'PUT']
            call_contracts = [c for c in top_contracts if c['side'] == 'CALL']

            if raw_signal == 'BEARISH' and put_contracts and drawdown_pct is not None:
                avg_put_strike = sum(c['strike'] for c in put_contracts) / len(put_contracts)
                put_itm_pct    = (avg_put_strike - current_price) / current_price * 100

                if put_itm_pct > 10 and drawdown_pct < -15:
                    # Puts profundamente ITM + acción ya cayó mucho = recogida de beneficios
                    flow_interpretation = 'PUT_COVERING'
                    interpretation_reason = (
                        f"Puts {put_itm_pct:.0f}% ITM con acción ya -"
                        f"{abs(drawdown_pct):.0f}% desde máximos. "
                        f"Probable recogida de beneficios, no apuesta bajista nueva. "
                        f"Posible zona de suelo."
                    )
                elif put_itm_pct < 0:
                    # Puts OTM = apuesta a caída desde nivel actual
                    flow_interpretation = 'FRESH_BEARISH'
                    interpretation_reason = (
                        f"Puts OTM ({put_itm_pct:.0f}% bajo precio). "
                        f"Apuesta nueva a caída desde nivel actual."
                    )
                elif put_itm_pct > 3 and (drawdown_pct is None or drawdown_pct > -10):
                    # Puts ITM pero acción no ha caído mucho = hedging o bajista
                    flow_interpretation = 'FRESH_BEARISH'
                    interpretation_reason = (
                        f"Puts {put_itm_pct:.0f}% ITM pero acción solo "
                        f"{drawdown_pct:.0f}% desde máximos. Posición bajista activa."
                    )

            elif raw_signal == 'BULLISH' and call_contracts and drawdown_pct is not None:
                avg_call_strike = sum(c['strike'] for c in call_contracts) / len(call_contracts)
                call_itm_pct    = (current_price - avg_call_strike) / current_price * 100

                if call_itm_pct > 10 and drawdown_pct is not None and drawdown_pct > 20:
                    # Calls profundamente ITM + acción muy subida = recogida de beneficios
                    flow_interpretation = 'CALL_COVERING'
                    interpretation_reason = (
                        f"Calls {call_itm_pct:.0f}% ITM con acción +"
                        f"{drawdown_pct:.0f}% en el año. "
                        f"Posible recogida de beneficios en calls largas."
                    )
                elif call_itm_pct < 0:
                    flow_interpretation = 'FRESH_BULLISH'
                    interpretation_reason = (
                        f"Calls OTM ({abs(call_itm_pct):.0f}% sobre precio). "
                        f"Apuesta nueva alcista desde nivel actual."
                    )

        signal = raw_signal  # La señal bruta no cambia, la interpretación es el contexto

        # IV media
        avg_iv = float(np.mean(iv_samples)) if iv_samples else None

        # Score de "inusualidad" (0-100)
        max_single = max((c['premium_usd'] for c in unusual_contracts), default=0)
        if max_single <= 0:
            unusual_score = 0
        else:
            unusual_score = max(0, min(100, int(
                (math.log10(max(max_single, 1)) - math.log10(MIN_PREMIUM_USD)) /
                (math.log10(LARGE_PREMIUM_USD * 10) - math.log10(MIN_PREMIUM_USD)) * 100
            )))

        return {
            'ticker':                ticker,
            'signal':                signal,
            'flow_interpretation':   flow_interpretation,
            'interpretation_reason': interpretation_reason,
            'current_price':         current_price,
            'drawdown_from_high_pct': drawdown_pct,
            'call_pct':              round(call_pct, 1),
            'total_call_premium':    round(total_call_premium, 0),
            'total_put_premium':     round(total_put_premium, 0),
            'total_premium':         round(total_premium, 0),
            'net_premium':           round(net, 0),
            'total_call_volume':     total_call_volume,
            'total_put_volume':      total_put_volume,
            'avg_iv':                round(avg_iv, 3) if avg_iv else None,
            'unusual_score':         unusual_score,
            'top_contracts':         top_contracts,
            'has_large_premium':     max_single >= LARGE_PREMIUM_USD,
            'max_single_premium':    round(max_single, 0),
            'detected_at':           datetime.now(timezone.utc).isoformat(),
        }

    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Scanner principal
# ─────────────────────────────────────────────────────────────────────────────

def scan(tickers: list[str]) -> list[dict]:
    """Escanea todos los tickers en paralelo."""
    results = []
    total   = len(tickers)
    done    = 0

    print(f'   Escaneando {total} tickers (threads={MAX_WORKERS})...')

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(analyze_ticker_options, t): t for t in tickers}
        for future in as_completed(futures):
            ticker = futures[future]
            done  += 1
            try:
                result = future.result()
                if result and result.get('total_premium', 0) > 0:
                    results.append(result)
                    sig  = result['signal']
                    prem = result['total_premium']
                    icon = '🟢' if sig == 'BULLISH' else '🔴' if sig == 'BEARISH' else '⚪'
                    if prem >= MIN_PREMIUM_USD:
                        print(f'   {icon} {ticker}: {sig} | ${prem/1000:.0f}k total | score={result["unusual_score"]}')
            except Exception:
                pass

            if done % 50 == 0:
                print(f'   Progreso: {done}/{total}')

    # Ordenar por premium total descendente
    results.sort(key=lambda x: x.get('total_premium', 0), reverse=True)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Guardar resultados
# ─────────────────────────────────────────────────────────────────────────────

def save_results(results: list[dict]) -> None:
    now = datetime.now(timezone.utc)

    # ── JSON ──────────────────────────────────────────────────────────────────
    output = {
        'scan_date':    now.isoformat(),
        'total_tickers_with_flow': len(results),
        'unusual_count': sum(1 for r in results if r.get('has_large_premium')),
        'bullish_count': sum(1 for r in results if r.get('signal') == 'BULLISH'),
        'bearish_count': sum(1 for r in results if r.get('signal') == 'BEARISH'),
        'results':      results,
    }

    json_path = DOCS / 'unusual_flow.json'
    with open(json_path, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f'📊 JSON guardado: {json_path}')

    # ── CSV ───────────────────────────────────────────────────────────────────
    rows = []
    for r in results:
        rows.append({
            'ticker':               r['ticker'],
            'signal':               r['signal'],
            'call_pct':             r['call_pct'],
            'total_premium_usd':    r['total_premium'],
            'total_call_premium':   r['total_call_premium'],
            'total_put_premium':    r['total_put_premium'],
            'net_premium':          r['net_premium'],
            'call_volume':          r['total_call_volume'],
            'put_volume':           r['total_put_volume'],
            'avg_iv':               r['avg_iv'],
            'unusual_score':        r['unusual_score'],
            'has_large_premium':    r['has_large_premium'],
            'max_single_premium':   r['max_single_premium'],
            'detected_at':          r['detected_at'],
        })

    df = pd.DataFrame(rows)
    csv_path = DOCS / 'unusual_flow.csv'
    df.to_csv(csv_path, index=False)
    print(f'💾 CSV guardado: {csv_path}')


# ─────────────────────────────────────────────────────────────────────────────
# Telegram alertas
# ─────────────────────────────────────────────────────────────────────────────

def _send_telegram(text: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            data={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'HTML',
                  'disable_web_page_preview': 'true'},
            timeout=10,
        )
    except Exception:
        pass


def send_flow_alerts(results: list[dict]) -> None:
    """Envía Telegram para contratos con premium > LARGE_PREMIUM_USD."""
    large = [r for r in results if r.get('has_large_premium')]
    if not large:
        return

    lines = [f'🔥 <b>UNUSUAL FLOW detectado</b> — {datetime.now().strftime("%H:%M")} ET\n']
    for r in large[:8]:
        sig   = r['signal']
        icon  = '🟢' if sig == 'BULLISH' else '🔴' if sig == 'BEARISH' else '⚪'
        prem  = r['total_premium'] / 1000
        cpct  = r['call_pct']
        lines.append(
            f"{icon} <b>{r['ticker']}</b> — {sig}\n"
            f"   Premium total: ${prem:.0f}k | Calls {cpct:.0f}%\n"
        )
        for c in r.get('top_contracts', [])[:1]:
            side_icon = '📈' if c['side'] == 'CALL' else '📉'
            lines.append(
                f"   {side_icon} {c['side']} ${c['strike']} exp {c['expiry']} "
                f"| vol {c['volume']} | ${c['premium_usd']/1000:.0f}k"
                f"{' ⚡SWEEP' if c['speculative'] else ''}\n"
            )

    _send_telegram('\n'.join(lines))


# ─────────────────────────────────────────────────────────────────────────────
# Display
# ─────────────────────────────────────────────────────────────────────────────

def print_top(results: list[dict], n: int = 15) -> None:
    print(f'\n{"="*70}')
    print(f'🔥 TOP UNUSUAL FLOW ({len(results)} tickers con actividad)')
    print(f'{"="*70}')

    top = [r for r in results if r.get('total_premium', 0) >= MIN_PREMIUM_USD][:n]
    for i, r in enumerate(top, 1):
        sig   = r['signal']
        icon  = '🟢' if sig == 'BULLISH' else '🔴' if sig == 'BEARISH' else '⚪'
        prem  = r['total_premium'] / 1000
        cpct  = r['call_pct']
        score = r['unusual_score']
        print(f'\n{i}. {icon} {r["ticker"]} — {sig} (score: {score}/100)')
        print(f'   Premium total: ${prem:.0f}k | Calls {cpct:.0f}% / Puts {100-cpct:.0f}%')
        for c in r.get('top_contracts', []):
            side_icon = '📈' if c['side'] == 'CALL' else '📉'
            spec = ' ⚡SWEEP' if c['speculative'] else ''
            itm  = ' [ITM]' if c.get('itm') else ''
            iv   = f" IV={c['iv']:.1%}" if c.get('iv') else ''
            print(
                f'   {side_icon} {c["side"]:4} ${c["strike"]} exp {c["expiry"]} ({c["dte"]}d)'
                f' | vol {c["volume"]:,} | ${c["premium_usd"]/1000:.0f}k{spec}{itm}{iv}'
            )

    print(f'\n{"="*70}')
    print(f'✅ Unusual Flow Scanner completado')
    print(f'{"="*70}\n')


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Unusual Options Flow Scanner')
    parser.add_argument('--quick',  action='store_true', help='Solo VALUE + bounce picks')
    parser.add_argument('--ticker', type=str, help='Tickers específicos separados por coma')
    parser.add_argument('--no-telegram', action='store_true', help='Sin alertas Telegram')
    args = parser.parse_args()

    print(f'\n{"="*70}')
    print(f'🔍 UNUSUAL OPTIONS FLOW SCANNER')
    print(f'   {datetime.now().strftime("%Y-%m-%d %H:%M")} ET')
    print(f'{"="*70}')

    # Universo
    if args.ticker:
        tickers = [t.strip().upper() for t in args.ticker.split(',')]
        print(f'📋 Modo específico: {len(tickers)} tickers')
    else:
        tickers = load_ticker_universe(quick=args.quick)
        mode = 'quick' if args.quick else 'completo'
        print(f'📋 Universo {mode}: {len(tickers)} tickers')

    # Scan
    results = scan(tickers)

    # Guardar
    DOCS.mkdir(exist_ok=True)
    save_results(results)

    # Alertas Telegram
    if not args.no_telegram:
        send_flow_alerts(results)

    # Display
    print_top(results)


if __name__ == '__main__':
    main()
