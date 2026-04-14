#!/usr/bin/env python3
"""
AGENT PORTFOLIO ALERTS — Cron diario (lun-vie 8h UTC)

Alerta cuando hay algo accionable en las posiciones activas:
  🔴 Stop-loss zone (retorno < -8%) — salir
  🟡 Win rate semanal < 30% — endurecer filtros
  🟢 Profit-taking zone (retorno >= 12%) — considerar recoger
  🔵 Approaching target (retorno 8-12%) — vigilar
  ⚪ Posicion sin retorno registrado > 9 dias (fallo de datos)

Variables: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
Railway cron: "0 8 * * 1-5"
"""

import csv
import io
import os
from datetime import datetime, timezone

import requests

BOT_TOKEN  = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID    = os.environ.get('TELEGRAM_CHAT_ID', '')
PAGES_BASE = 'https://tantancansado.github.io/stock_analyzer_a'

STOP_LOSS_PCT     = -8.0
PROFIT_TARGET_PCT = 12.0
NEAR_TARGET_PCT   = 8.0
WIN_RATE_WARN     = 30.0
STALE_DAYS        = 9


def fetch(url: str, as_json=False):
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return None
        return r.json() if as_json else r.text
    except Exception:
        return None


def tg(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        print(text)
        return
    try:
        requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            json={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'HTML',
                  'disable_web_page_preview': True},
            timeout=10,
        )
    except Exception:
        pass


def _best_return(row: dict) -> tuple[float | None, str]:
    """Devuelve (mejor_retorno, columna) para una fila del CSV."""
    for col in ('return_14d', 'return_7d'):
        val = row.get(col, '')
        if val:
            try:
                return float(val), col
            except ValueError:
                pass
    return None, ''


def _classify_row(row: dict, today: datetime) -> tuple[str | None, str | None]:
    """Clasifica una fila activa. Devuelve (categoria, linea_html)."""
    ticker = row.get('ticker', '?')
    ret, col = _best_return(row)
    period = col.replace('return_', '') if col else '?d'

    if ret is not None:
        line = f"  • <code>{ticker}</code> ({period}): <b>{ret:+.1f}%</b>"
        if ret <= STOP_LOSS_PCT:
            return 'stop', line + " — revisar tesis"
        if ret >= PROFIT_TARGET_PCT:
            return 'profit', line
        if ret >= NEAR_TARGET_PCT:
            return 'near', line
        return None, None

    sig_date_str = row.get('signal_date', '')
    if not sig_date_str:
        return None, None
    try:
        sig_dt = datetime.fromisoformat(str(sig_date_str).replace('Z', '+00:00'))
        if sig_dt.tzinfo is None:
            sig_dt = sig_dt.replace(tzinfo=timezone.utc)
        days = (today - sig_dt).days
        if days > STALE_DAYS:
            return 'stale', f"  • <code>{ticker}</code> ({days}d sin datos)"
    except Exception:
        pass
    return None, None


def _check_win_rate() -> str | None:
    summary = fetch(f'{PAGES_BASE}/docs/portfolio_tracker/summary.json', as_json=True)
    if not summary:
        return None
    wr  = summary.get('overall', {}).get('7d', {}).get('win_rate')
    avg = summary.get('overall', {}).get('7d', {}).get('avg_return') or 0
    if wr is not None and wr < WIN_RATE_WARN:
        return (f"⚠️ <b>Win rate 7d bajo:</b> {wr:.1f}% "
                f"(avg {avg:+.1f}%) — considera endurecer filtros")
    return None


def _scan_positions() -> dict[str, list[str]]:
    csv_text = fetch(f'{PAGES_BASE}/docs/portfolio_tracker/recommendations.csv')
    if not csv_text:
        return {}

    today   = datetime.now(timezone.utc)
    buckets: dict[str, list[str]] = {'stop': [], 'profit': [], 'near': [], 'stale': []}

    for row in csv.DictReader(io.StringIO(csv_text)):
        if row.get('status') != 'ACTIVE':
            continue
        cat, line = _classify_row(row, today)
        if cat and line:
            buckets[cat].append(line)

    return buckets


def _build_alerts(buckets: dict[str, list[str]]) -> list[str]:
    alerts = []
    if buckets.get('stop'):
        n = len(buckets['stop'])
        alerts.append(
            f"🔴 <b>Stop-loss zone ({n} posicion{'es' if n > 1 else ''}):</b>\n"
            + '\n'.join(buckets['stop'])
        )
    if buckets.get('profit'):
        alerts.append(
            f"🟢 <b>Profit-taking (>={PROFIT_TARGET_PCT:.0f}% — considera recoger):</b>\n"
            + '\n'.join(buckets['profit'])
        )
    if buckets.get('near'):
        alerts.append(
            f"🔵 <b>Cerca del objetivo ({NEAR_TARGET_PCT:.0f}-{PROFIT_TARGET_PCT:.0f}% — vigilar):</b>\n"
            + '\n'.join(buckets['near'])
        )
    if buckets.get('stale'):
        alerts.append(
            "🟡 <b>Sin retorno registrado:</b>\n"
            + '\n'.join(buckets['stale'])
            + "\n<i>Puede ser fallo del pipeline o holiday.</i>"
        )
    return alerts


def main():
    alerts = []

    win_rate_alert = _check_win_rate()
    if win_rate_alert:
        alerts.append(win_rate_alert)

    buckets = _scan_positions()
    if not buckets:
        return  # sin datos CSV, silencio

    alerts.extend(_build_alerts(buckets))

    if not alerts:
        print('Portfolio OK — sin alertas')
        return

    now_str = datetime.now(timezone.utc).strftime('%d/%m %H:%M')
    msg = (
        f"📊 <b>Portfolio Alerts — {now_str} UTC</b>\n"
        f"{'━'*22}\n\n"
        + '\n\n'.join(alerts)
    )
    tg(msg)
    print(f'📱 {len(alerts)} alerta(s) enviadas')


if __name__ == '__main__':
    main()
