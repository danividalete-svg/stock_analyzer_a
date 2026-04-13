#!/usr/bin/env python3
"""
AGENT DATA QUALITY — Cron 2x/día (10h y 18h UTC)
Detecta anomalías en los datos antes de que lleguen al usuario:
  - Scan desactualizado (>28h desde el último análisis)
  - CSV de value vacío o con muy pocas entradas
  - Retornos extremos en portfolio (señal de bug GBp/GBP u otro error)
  - Sin señales de bounce a pesar de VIX bajo (filtros demasiado estrictos?)

Variables de entorno: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
Railway cron: "0 10,18 * * 1-5"
"""

import io
import json
import os
import csv
from datetime import datetime, timezone, timedelta

import requests

BOT_TOKEN  = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID    = os.environ.get('TELEGRAM_CHAT_ID', '')
PAGES_BASE = 'https://tantancansado.github.io/stock_analyzer_a'

SCAN_STALE_HOURS   = 28     # alerta si el scan tiene más de N horas
VALUE_MIN_ROWS     = 3      # alerta si el CSV filtrado tiene menos de N filas
EXTREME_RETURN_PCT = 95.0   # alerta si algún retorno > abs(N%)
BOUNCE_LOW_VIX     = 25.0   # si VIX < N y 0 bounces → posibles filtros demasiado estrictos


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
    issues = []
    now = datetime.now(timezone.utc)

    # ── 1. Scan age ────────────────────────────────────────────────────────────
    mr = fetch(f'{PAGES_BASE}/mean_reversion_opportunities.json', as_json=True)
    vix = None
    bounce_count = 0

    if mr is None:
        issues.append("❌ <b>mean_reversion_opportunities.json</b> no disponible (pipeline caído?)")
    else:
        scan_date_str = mr.get('scan_date', '')
        if scan_date_str:
            try:
                scan_dt = datetime.fromisoformat(scan_date_str.replace('Z', '+00:00'))
                if scan_dt.tzinfo is None:
                    scan_dt = scan_dt.replace(tzinfo=timezone.utc)
                age_h = (now - scan_dt).total_seconds() / 3600
                if age_h > SCAN_STALE_HOURS:
                    issues.append(
                        f"🕐 <b>Scan desactualizado:</b> {age_h:.0f}h desde el último análisis "
                        f"(máx esperado: {SCAN_STALE_HOURS}h)"
                    )
            except Exception:
                pass

        ops = mr.get('opportunities', [])
        bounce_ops = [o for o in ops if o.get('strategy') == 'Oversold Bounce']
        bounce_count = len(bounce_ops)

        for o in ops:
            if o.get('vix'):
                vix = float(o['vix'])
                break

    # ── 2. 0 bounces con VIX bajo ──────────────────────────────────────────────
    if vix is not None and vix < BOUNCE_LOW_VIX and bounce_count == 0:
        issues.append(
            f"🟡 <b>0 bounces con VIX {vix:.1f}</b> — mercado tranquilo pero sin setups. "
            f"¿Filtros demasiado estrictos?"
        )

    # ── 3. Value CSV vacío ────────────────────────────────────────────────────
    value_csv = fetch(f'{PAGES_BASE}/value_opportunities_filtered.csv')
    if value_csv is None:
        issues.append("❌ <b>value_opportunities_filtered.csv</b> no disponible")
    else:
        rows = [r for r in value_csv.strip().split('\n') if r]
        n_value = max(0, len(rows) - 1)  # quitar header
        if n_value < VALUE_MIN_ROWS:
            issues.append(
                f"⚠️ <b>Value muy bajo:</b> solo {n_value} oportunidades filtradas "
                f"(mínimo esperado: {VALUE_MIN_ROWS})"
            )

    # ── 4. Retornos extremos en portfolio ─────────────────────────────────────
    recs_csv = fetch(f'{PAGES_BASE}/portfolio_tracker/recommendations.csv')
    if recs_csv:
        reader = csv.DictReader(io.StringIO(recs_csv))
        extremes = []
        for row in reader:
            ticker = row.get('ticker', '?')
            for col in ('return_7d', 'return_14d', 'return_30d'):
                val = row.get(col, '')
                if val:
                    try:
                        pct = float(val)
                        if abs(pct) > EXTREME_RETURN_PCT:
                            extremes.append(
                                f"  • <code>{ticker}</code> {col}: {pct:+.1f}% (posible error de datos)"
                            )
                            break
                    except ValueError:
                        pass
        if extremes:
            issues.append(
                f"🔴 <b>Retornos extremos detectados ({len(extremes)}):</b>\n"
                + '\n'.join(extremes[:5])
                + ("\n  <i>...y más</i>" if len(extremes) > 5 else "")
                + "\n<i>Posible bug GBp/GBP o split. Revisar portfolio_tracker.</i>"
            )

    # ── Enviar solo si hay problemas ──────────────────────────────────────────
    if not issues:
        print('✅ Data quality OK — sin anomalías')
        return

    msg = (
        f"🔍 <b>Data Quality Alert — {now.strftime('%d/%m %H:%M')} UTC</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        + '\n\n'.join(issues)
    )
    tg(msg)
    print(f'⚠️ {len(issues)} problema(s) detectado(s)')


if __name__ == '__main__':
    main()
