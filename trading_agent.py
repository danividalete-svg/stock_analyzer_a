#!/usr/bin/env python3
"""
TRADING AGENT — Agente de trading autónomo con validación multi-señal

Extiende bounce_trader.py añadiendo inteligencia de:
  - Flujo de opciones (unusual_flow.json): conflictos FRESH_BEARISH / confirmaciones
  - Valor fundamental (value CSVs): refuerza setup si el ticker es un pick VALUE
  - Análisis Groq: 1-2 frases de contexto antes de proponer al usuario
  - Tarjeta Telegram enriquecida con puntuación de convicción 0–10

Flujo por ciclo (cada 15 min en horario de mercado):
  1. Escanear tickers (bounce_trader._analyze)
  2. Cross-reference con flow + value → puntuación de convicción
  3. Para cada setup (más convicción primero):
       a. Groq commentary
       b. Proponer a usuario via Telegram (botones ✅/❌)
       c. Si aprobado → ejecutar bracket en IBKR
  4. Monitorear posiciones abiertas (fills + cierres)

Requiere TWS abierto en 127.0.0.1:7497 (paper) o 7496 (live).

Uso:
  python3 trading_agent.py              # paper, una pasada
  python3 trading_agent.py --loop       # loop cada 15 min
  python3 trading_agent.py --dry-run    # simula sin órdenes reales
  python3 trading_agent.py --live       # puerto real 7496
  python3 trading_agent.py --status     # ver posiciones (delega a bounce_trader)
"""

import json
import os
import sys
import time
from datetime import timedelta
from pathlib import Path
from typing import Optional

import requests

# ── Paths / credentials ───────────────────────────────────────────────────────
ROOT      = Path(__file__).parent
DOCS      = ROOT / 'docs'
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID   = os.environ.get('TELEGRAM_CHAT_ID', '')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')

# ── Reuse bounce_trader — all scanning/execution/monitor/telegram logic ───────
sys.path.insert(0, str(ROOT))
import bounce_trader as bt


# ─────────────────────────────────────────────────────────────────────────────
# Signal loaders
# ─────────────────────────────────────────────────────────────────────────────

def _load_flow_signals() -> dict[str, dict]:
    """Carga unusual_flow.json → {ticker: flow_result}."""
    path = DOCS / 'unusual_flow.json'
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
        out: dict[str, dict] = {}
        for r in raw.get('results', []):
            t = str(r.get('ticker', '')).strip().upper()
            if t:
                # Guardar solo el más reciente (el JSON ya viene ordenado)
                if t not in out:
                    out[t] = r
        return out
    except Exception:
        return {}


def _load_value_signals() -> dict[str, dict]:
    """Carga value CSVs filtrados → {ticker: {score, grade, sector}}."""
    import pandas as pd
    out: dict[str, dict] = {}
    for fname in (
        'value_opportunities_filtered.csv',
        'european_value_opportunities_filtered.csv',
    ):
        fpath = DOCS / fname
        if not fpath.exists():
            continue
        try:
            df = pd.read_csv(fpath)
            for _, row in df.iterrows():
                t = str(row.get('ticker', '')).strip().upper()
                if not t:
                    continue
                score = float(row.get('value_score') or 0)
                if score < 50:
                    continue
                if t not in out or score > out[t]['score']:
                    out[t] = {
                        'score':  score,
                        'grade':  str(row.get('grade')  or '').strip(),
                        'sector': str(row.get('sector') or '').strip(),
                    }
        except Exception:
            pass
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Multi-signal conviction score
# ─────────────────────────────────────────────────────────────────────────────

def _conviction_score(m: dict, flow: Optional[dict], value: Optional[dict]) -> int:
    """
    Combina señales técnicas + flow + value en una puntuación 0–10.

    Bounce:          FLASH=4, ACUMULACION=3
    Value (si lo es): score≥70 → +3, score≥55 → +2, cualquier → +1
    Flow:
      BULLISH >$100K  → +3
      BULLISH ≤$100K  → +2
      PUT_COVERING    → +1  (confirmación de suelo, no penaliza)
      FRESH_BEARISH   → −2  (conflicto — opciones bajistas frescas sobre el ticker)
    """
    score = 0

    strat = m.get('strategy', '')
    if strat == 'FLASH':
        score += 4
    elif strat == 'ACUMULACION':
        score += 3

    if value:
        vs = value.get('score', 0)
        score += 3 if vs >= 70 else (2 if vs >= 55 else 1)

    if flow:
        interp = flow.get('flow_interpretation', 'STANDARD')
        signal = flow.get('signal', '')
        prem   = float(flow.get('total_premium') or 0)
        if signal == 'BULLISH':
            score += 3 if prem > 100_000 else 2
        elif interp == 'PUT_COVERING':
            score += 1
        elif interp == 'FRESH_BEARISH':
            score -= 2

    return max(0, min(10, score))


# ─────────────────────────────────────────────────────────────────────────────
# Groq 1-liner
# ─────────────────────────────────────────────────────────────────────────────

def _groq_insight(m: dict, flow: Optional[dict], value: Optional[dict]) -> str:
    """Genera 1-2 frases de análisis con Groq antes de proponer al usuario."""
    if not GROQ_API_KEY:
        return ''
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        parts = [
            f"{m['ticker']}: caída {m['drop_vs_prev']:+.1f}% hoy "
            f"({m['drop_vs_peak']:+.1f}% desde máx 20d), "
            f"RSI {m['rsi']:.0f}, R:R {m['rr']:.1f}x, estrategia {m.get('strategy','')}."
        ]
        if value:
            parts.append(
                f"Es pick VALUE: score {value['score']:.0f}pts "
                f"({value.get('grade','')}, {value.get('sector','')})."
            )
        if flow:
            interp = flow.get('flow_interpretation', 'STANDARD')
            prem   = float(flow.get('total_premium') or 0)
            pct_c  = float(flow.get('call_pct') or 50)
            parts.append(
                f"Flujo opciones: {interp}, ${prem/1000:.0f}K premium, {pct_c:.0f}% calls."
            )

        resp = client.chat.completions.create(
            model='meta-llama/llama-4-scout-17b-16e-instruct',
            max_tokens=60,
            messages=[{
                'role': 'user',
                'content': (
                    'Eres un trader experto. Analiza este setup de rebote en máximo 15 palabras, '
                    'en español, sin saludos. Sé concreto sobre si operar o no y por qué. '
                    f'Setup: {" ".join(parts)}'
                ),
            }],
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return ''


# ─────────────────────────────────────────────────────────────────────────────
# Telegram — tarjeta enriquecida con aprobación
# ─────────────────────────────────────────────────────────────────────────────

def _send_telegram(text: str):
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


def _tg_propose(
    m: dict,
    flow: Optional[dict],
    value: Optional[dict],
    groq_text: str,
    conv_score: int,
    fund: Optional[dict] = None,
) -> bool:
    """
    Envía tarjeta enriquecida a Telegram con ✅ Ejecutar / ❌ Rechazar.
    Muestra: setup técnico + value context + flow context + Groq insight.
    Returns True si aprobado, False si rechazado o timeout.
    Sin Telegram configurado → aprueba automáticamente.
    """
    if not BOT_TOKEN or not CHAT_ID:
        return True

    ticker    = m['ticker']
    strat     = m.get('strategy', 'SETUP')
    strat_tag = '⚡ FLASH' if strat == 'FLASH' else '📈 ACUMULACIÓN'
    rsi_w_str = f"/{m['rsi_weekly']:.0f}w" if m.get('rsi_weekly') else ''
    t_src     = '📡' if m.get('target_source') == 'analyst' else '📐'
    timeout   = bt.CONFIRM_TIMEOUT_MIN

    lines = [
        f"🎯 <b>TRADING AGENT</b>  {strat_tag}  [{conv_score}/10]",
        f"📉 <b>{ticker}</b>  {m['drop_vs_prev']:+.1f}% hoy  RSI {m['rsi']:.0f}{rsi_w_str}",
        '━━━━━━━━━━━━━━━━━━━━━',
        f"💰 Entrada: <b>${m['entry']:.2f}</b>",
        f"🎯 Target:  ${m['target']:.2f}  (+{m['upside_pct']:.1f}%) {t_src}",
        f"🛑 Stop:    ${m['stop']:.2f}  (R:R {m['rr']:.1f}x)",
    ]

    # Value context
    if value:
        grade_str  = f"  {value.get('grade','')}"  if value.get('grade')  else ''
        sector_str = f"  {value.get('sector','')}" if value.get('sector') else ''
        lines += [
            '━━━━━━━━━━━━━━━━━━━━━',
            f"💎 Value:  {value['score']:.0f}pts{grade_str}{sector_str}",
        ]

    # Flow context
    if flow:
        interp = flow.get('flow_interpretation', 'STANDARD')
        signal = flow.get('signal', '')
        prem   = float(flow.get('total_premium') or 0)
        pct_c  = float(flow.get('call_pct') or 50)
        prem_fmt = f"${prem/1_000_000:.1f}M" if prem >= 1_000_000 else f"${prem/1_000:.0f}K"

        if interp == 'PUT_COVERING':
            flow_line = f"🔄 Flow:  Recogida Puts — suelo probable  {prem_fmt}"
        elif interp == 'FRESH_BEARISH':
            flow_line = f"⚠️ Flow:  CONFLICTO — bajista fresco {prem_fmt}"
        elif signal == 'BULLISH':
            flow_line = f"⚡ Flow:  BULLISH  {prem_fmt}  ({pct_c:.0f}% calls)"
        else:
            flow_line = f"📊 Flow:  {signal}  {prem_fmt}"

        lines += ['━━━━━━━━━━━━━━━━━━━━━', flow_line]

    # Groq insight
    if groq_text:
        lines += ['━━━━━━━━━━━━━━━━━━━━━', f"🧠 {groq_text}"]

    lines += [
        '━━━━━━━━━━━━━━━━━━━━━',
        f"📊 Vol {m['vol_ratio']:.1f}x  |  Caída {m['drop_vs_peak']:+.1f}% desde máx",
        f"⏳ <i>Tienes {timeout} min para decidir</i>",
    ]

    text = '\n'.join(lines)
    keyboard = {'inline_keyboard': [[
        {'text': '✅ Ejecutar',  'callback_data': f'approve_{ticker}'},
        {'text': '❌ Rechazar', 'callback_data': f'reject_{ticker}'},
    ]]}

    try:
        resp = requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            json={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'HTML',
                  'reply_markup': keyboard, 'disable_web_page_preview': True},
            timeout=10,
        ).json()
        msg_id = resp['result']['message_id']
    except Exception:
        return True  # si falla enviar → ejecutar igual

    # Limpiar webhook para no bloquear getUpdates
    try:
        requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook',
                      json={'drop_pending_updates': False}, timeout=5)
    except Exception:
        pass

    # Offset para ignorar callbacks anteriores
    try:
        upd    = requests.get(f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates',
                              params={'limit': 1, 'allowed_updates': ['callback_query']},
                              timeout=10).json()
        offset = (upd['result'][-1]['update_id'] + 1) if upd.get('result') else 0
    except Exception:
        offset = 0

    deadline = time.time() + timeout * 60
    approved = False
    decided  = False

    while time.time() < deadline and not decided:
        wait = min(30, int(deadline - time.time()))
        if wait <= 0:
            break
        try:
            upd = requests.get(
                f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates',
                params={'timeout': wait, 'offset': offset,
                        'allowed_updates': ['callback_query']},
                timeout=wait + 5,
            ).json()
            for update in upd.get('result', []):
                offset = update['update_id'] + 1
                cq = update.get('callback_query')
                if not cq:
                    continue
                data = cq.get('data', '')
                if data == f'approve_{ticker}':
                    approved, decided = True, True
                elif data == f'reject_{ticker}':
                    approved, decided = False, True
                if decided:
                    requests.post(
                        f'https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery',
                        json={'callback_query_id': cq['id'],
                              'text': '✅ Ejecutando orden...' if approved else '❌ Trade rechazado'},
                        timeout=5,
                    )
                    break
        except Exception:
            time.sleep(5)

    # Editar mensaje con resultado final
    if decided:
        final = f"{'✅ APROBADO' if approved else '❌ RECHAZADO'} — <b>{ticker}</b> {strat_tag}  [{conv_score}/10]"
    else:
        final = f"⏰ Sin respuesta ({timeout}min) — <b>{ticker}</b> no ejecutado"
        approved = False
    try:
        requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/editMessageText',
            json={'chat_id': CHAT_ID, 'message_id': msg_id,
                  'text': final, 'parse_mode': 'HTML'},
            timeout=5,
        )
    except Exception:
        pass

    return approved


# ─────────────────────────────────────────────────────────────────────────────
# Main agent loop
# ─────────────────────────────────────────────────────────────────────────────

def run_agent(port: int, dry_run: bool):
    print(f"\n{'='*60}")
    print(f"  TRADING AGENT  {bt._now_et().strftime('%Y-%m-%d %H:%M ET')}")
    mode_str = 'DRY RUN' if dry_run else ('PAPER' if port == bt.IB_PORT_PAPER else '⚠️  LIVE REAL')
    print(f"  Modo: {mode_str}")
    print(f"{'='*60}")

    # ── Macro context ────────────────────────────────────────────────────────
    regime, vix, fund_df = bt._load_project_data()
    print(f"  Macro: {regime}  |  VIX: {vix:.1f}")

    if regime == 'CRISIS' and not dry_run:
        msg = '🚨 <b>Trading Agent</b>: régimen CRISIS — sin operaciones hasta normalización.'
        print('  🚨 CRISIS — trading suspendido.')
        _send_telegram(msg)
        return

    if not bt._is_any_market_open() and not dry_run:
        print('  Mercados cerrados — nada que hacer.')
        return

    # ── Load all signal sources ──────────────────────────────────────────────
    print('\n  Cargando señales multi-fuente...')
    flow_signals  = _load_flow_signals()
    value_signals = _load_value_signals()
    print(f'  → Flow: {len(flow_signals)} tickers  |  Value: {len(value_signals)} tickers')

    # ── Log + open positions ─────────────────────────────────────────────────
    log    = bt._load_log()
    open_t = bt._open_trades(log)

    if not dry_run and open_t:
        print('\n  Monitoreando posiciones abiertas...')
        log, closures = bt._check_positions(port, log)
        bt._save_log(log)
        for c in closures:
            bt._tg_closure(c)
        open_t = bt._open_trades(log)

    # Limits
    is_live    = (port == bt.IB_PORT_LIVE)
    max_trades = bt.MAX_OPEN_TRADES if is_live else bt.MAX_OPEN_TRADES_PAPER
    if regime in ('STRESS', 'ALERT'):
        max_trades = max(max_trades - 3, 3)

    open_cnt = len(open_t)
    print(f'  Trades abiertos: {open_cnt}/{max_trades}')

    if open_cnt >= max_trades and not dry_run:
        print('  ⚠️  Límite de trades alcanzado — solo monitoreando.')
        return

    if not dry_run and is_live:
        day_pnl = bt._daily_pnl(log)
        if day_pnl <= -bt.DAILY_LOSS_LIMIT_USD:
            msg = f'🛑 Daily loss limit ({day_pnl:+.0f} USD) — sin nuevas órdenes hoy.'
            print(f'  {msg}')
            _send_telegram(msg)
            return

    # ── Scan ─────────────────────────────────────────────────────────────────
    tickers = bt._load_tickers()
    print(f'\n  Escaneando {len(tickers)} tickers...')

    open_sectors: dict = {}
    for ot in open_t:
        sec = ot.get('sector')
        if sec:
            open_sectors[sec] = open_sectors.get(sec, 0) + 1

    setups: list[tuple] = []  # (conv_score, ticker, company, m, fund, flow, value)

    for ticker, company, from_mr in tickers:
        if not dry_run:
            if bt._is_eu_ticker(ticker) and not bt._is_eu_open():
                continue
            if not bt._is_eu_ticker(ticker) and not bt._is_us_open() and not bt._is_us_extended():
                continue

        fund = bt._get_fund(ticker, fund_df)
        dte  = fund.get('days_to_earnings')
        if dte is not None and 0 <= dte <= 5:
            continue
        if fund.get('earnings_warning'):
            continue

        m = bt._analyze(ticker, fund)
        if m is None:
            continue

        entry_price = m.get('entry', 0)
        if entry_price < 2.0:
            continue
        if from_mr and entry_price < 5.0:
            continue

        ok, _ = bt._qualifies(m)
        if not ok:
            continue

        if regime == 'ALERT' and m.get('strategy') != 'FLASH' and not dry_run:
            continue

        m['vix'] = vix

        flow  = flow_signals.get(ticker)
        value = value_signals.get(ticker)
        conv  = _conviction_score(m, flow, value)

        setups.append((conv, ticker, company, m, fund, flow, value))

    # Sort by conviction (highest first)
    setups.sort(key=lambda x: -x[0])

    print(f'\n  {len(setups)} setup(s) encontrado(s)')
    if not setups:
        print(f"{'='*60}")
        return

    # Print summary table
    print(f"\n  {'TICKER':<9} {'CONV':>5} {'STRAT':<12} {'RSI':>4} {'R:R':>5}  SEÑALES")
    print(f"  {'─'*60}")
    for conv, ticker, _, m, _, flow, value in setups:
        flow_tag  = f" +Flow({flow.get('flow_interpretation','')[:7]})" if flow else ''
        value_tag = f" +Value({value.get('score',0):.0f})" if value else ''
        conflict  = ' ⚠️CONFLICTO' if (flow and flow.get('flow_interpretation') == 'FRESH_BEARISH') else ''
        print(f"  {ticker:<9} {conv:>4}/10  {m.get('strategy',''):12}  "
              f"{m['rsi']:>4.0f}  {m['rr']:>5.1f}x{flow_tag}{value_tag}{conflict}")

    # ── Process setups ────────────────────────────────────────────────────────
    executed = 0
    for conv, ticker, company, m, fund, flow, value in setups:
        if open_cnt >= max_trades and not dry_run:
            print(f'\n  Límite {max_trades} trades alcanzado — deteniendo.')
            break

        in_cooldown, label = bt._recently_traded(log, ticker)
        if in_cooldown:
            print(f'\n  [{ticker}] ⏭ {label}')
            continue

        sector = fund.get('sector')
        if sector and open_sectors.get(sector, 0) >= bt.MAX_SAME_SECTOR and not dry_run:
            print(f'\n  [{ticker}] ⏭ sector {sector} ya cubierto')
            continue

        grade_key = (fund.get('grade') or 'AVERAGE').upper()
        if bt.GRADE_RISK_MULT.get(grade_key, 0.7) == 0.0 and not dry_run:
            print(f'\n  [{ticker}] ⛔ Grade WEAK — no se opera')
            continue

        if flow and flow.get('flow_interpretation') == 'FRESH_BEARISH':
            print(f'\n  [{ticker}] ⚠️  FRESH_BEARISH conflict — mostrando advertencia en tarjeta')

        # Groq insight (best-effort, no blocking)
        print(f'\n  [{ticker}] Analizando con Groq...')
        groq_text = _groq_insight(m, flow, value)
        if groq_text:
            print(f'  🧠 {groq_text}')

        m['outside_rth'] = (
            bt._is_us_extended()
            and not bt._is_eu_ticker(ticker)
            and not bt._is_us_open()
        )

        # Propose via Telegram
        approved = _tg_propose(m, flow, value, groq_text, conv, fund)
        if not approved:
            print(f'  ❌ {ticker} rechazado o timeout')
            continue

        print(f'  ✅ {ticker} aprobado — ejecutando bracket IBKR...')
        result = bt._execute_order(m, port, dry_run, grade=fund.get('grade'))
        result.update({'ticker': ticker, 'company': company, 'sector': sector})
        log.append(result)
        bt._save_log(log)

        if result['status'] in ('EXECUTED', 'DRY_RUN', 'EU_PENDING'):
            executed += 1
            if not dry_run:
                open_cnt += 1
                if sector:
                    open_sectors[sector] = open_sectors.get(sector, 0) + 1
            bt._tg_entry(m, result, fund)

    print(f'\n  ✔ {len(setups)} setup(s) | {executed} ejecutado(s)')
    print(f"{'='*60}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Trading Agent — bounce + flow + value + Groq')
    parser.add_argument('--loop',    action='store_true', help='Bucle cada 15 min')
    parser.add_argument('--dry-run', action='store_true', help='Simular sin órdenes reales')
    parser.add_argument('--live',    action='store_true', help='Puerto real 7496')
    parser.add_argument('--status',  action='store_true', help='Ver posiciones (delega a bounce_trader)')
    args = parser.parse_args()

    if args.status:
        bt.show_status()
        return

    port = bt.IB_PORT_LIVE if args.live else bt.IB_PORT_PAPER

    if args.live and not args.dry_run:
        print('⚠️  MODO LIVE — órdenes con dinero REAL')
        if input('Escribe "CONFIRMO": ').strip() != 'CONFIRMO':
            print('Abortado.')
            return

    if not args.dry_run and not bt._check_tws(port):
        print(f'❌ TWS no detectado en puerto {port}.')
        print('   Abre TWS/IB Gateway y vuelve a intentarlo.')
        sys.exit(1)

    if args.loop:
        caff = bt._prevent_sleep()
        mode = 'DRY RUN' if args.dry_run else f'PAPER (:{port})'
        print(f'\n🚀 Trading Agent arrancado — {mode}')
        print(f'   Scan cada {bt.SCAN_INTERVAL_MIN} min | Ctrl+C para detener\n')
        try:
            while True:
                try:
                    run_agent(port, args.dry_run)
                except Exception as e:
                    print(f'Error en ciclo: {e}')
                mins = bt._minutes_to_open()
                wait = bt.SCAN_INTERVAL_MIN * 60 if mins <= 0 else min(mins * 60, bt.SCAN_INTERVAL_MIN * 60)
                next_et = bt._now_et() + timedelta(seconds=wait)
                print(f'  Próximo scan: {next_et.strftime("%H:%M ET")}')
                time.sleep(wait)
        except KeyboardInterrupt:
            print('\n\nDetenido por el usuario.')
        finally:
            if caff:
                caff.terminate()
                print('☕ caffeinate liberado.')
    else:
        run_agent(port, args.dry_run)


if __name__ == '__main__':
    main()
