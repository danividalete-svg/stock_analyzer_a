#!/usr/bin/env python3
"""
AGENT PORTFOLIO ALERTS — Cron diario (lun-vie 8h)
Lee las posiciones activas y alerta solo cuando hay algo accionable:
  - Posición en zona stop-loss (retorno < -8%)
  - Win rate semanal cae por debajo del 30%
  - Posición lleva >9 días activa sin retorno registrado (fallo de datos)

Variables de entorno: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
Railway cron: "0 8 * * 1-5"
"""

import csv
import io
import json
import os
from datetime import datetime, timezone

import requests

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID   = os.environ.get('TELEGRAM_CHAT_ID', '')
PAGES_BASE = 'https://tantancansado.github.io/stock_analyzer_a'

STOP_LOSS_PCT  = -8.0   # alerta si retorno < este valor
WIN_RATE_WARN  = 30.0   # alerta si win_rate_7d < este valor
STALE_DAYS     = 9      # alerta si activa > N días sin return_7d


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


def main():
    alerts = []

    # ── 1. Win rate ────────────────────────────────────────────────────────────
    summary = fetch(f'{PAGES_BASE}/docs/portfolio_tracker/summary.json', as_json=True)
    if summary:
        wr = summary.get('overall', {}).get('7d', {}).get('win_rate')
        avg = summary.get('overall', {}).get('7d', {}).get('avg_return')
        if wr is not None and wr < WIN_RATE_WARN:
            alerts.append(
                f"⚠️ <b>Win rate 7d bajo:</b> {wr:.1f}% "
                f"(avg {avg:+.1f}%) — considera endurecer filtros"
            )

    # ── 2. Posiciones activas ──────────────────────────────────────────────────
    csv_text = fetch(f'{PAGES_BASE}/docs/portfolio_tracker/recommendations.csv')
    if not csv_text:
        return  # sin datos, silencio

    reader = csv.DictReader(io.StringIO(csv_text))
    today = datetime.now(timezone.utc)
    stop_loss_hits = []
    stale_positions = []

    for row in reader:
        if row.get('status') != 'ACTIVE':
            continue

        ticker = row.get('ticker', '?')

        # Stop loss check (return_7d o return_14d)
        for col in ('return_7d', 'return_14d'):
            val = row.get(col, '')
            if val:
                try:
                    pct = float(val)
                    if pct < STOP_LOSS_PCT:
                        stop_loss_hits.append(
                            f"  • <code>{ticker}</code> {col.replace('return_', '')}: <b>{pct:+.1f}%</b>"
                        )
                        break
                except ValueError:
                    pass

        # Stale position check
        sig_date_str = row.get('signal_date', '')
        if sig_date_str and not row.get('return_7d'):
            try:
                sig_dt = datetime.fromisoformat(str(sig_date_str).replace('Z', '+00:00'))
                if sig_dt.tzinfo is None:
                    sig_dt = sig_dt.replace(tzinfo=timezone.utc)
                days = (today - sig_dt).days
                if days > STALE_DAYS:
                    stale_positions.append(f"  • <code>{ticker}</code> ({days}d sin datos)")
            except Exception:
                pass

    if stop_loss_hits:
        alerts.append(
            f"🔴 <b>Stop-loss zone ({len(stop_loss_hits)} posición{'es' if len(stop_loss_hits)>1 else ''}):</b>\n"
            + '\n'.join(stop_loss_hits)
        )

    if stale_positions:
        alerts.append(
            f"🟡 <b>Sin retorno registrado:</b>\n"
            + '\n'.join(stale_positions)
            + "\n<i>Puede ser fallo del pipeline o holiday.</i>"
        )

    # ── Enviar solo si hay algo ────────────────────────────────────────────────
    if not alerts:
        print('✅ Portfolio OK — sin alertas')
        return

    msg = (
        f"📊 <b>Portfolio Alerts — {today.strftime('%d/%m %H:%M')} UTC</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        + '\n\n'.join(alerts)
    )
    tg(msg)
    print(f'📱 {len(alerts)} alerta(s) enviadas')


if __name__ == '__main__':
    main()
