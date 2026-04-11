#!/usr/bin/env python3
"""
AGENT WEEKLY REPORT — Cron domingos 19h UTC
Genera un resumen de la semana con Groq y lo manda a Telegram.
Sin botones, sin aprobación. Solo información.

Variables de entorno: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GROQ_API_KEY
Railway cron: "0 19 * * 0"
"""

import io
import json
import os
import csv
from datetime import datetime, timezone, timedelta

import requests

BOT_TOKEN    = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID      = os.environ.get('TELEGRAM_CHAT_ID', '')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
PAGES_BASE   = 'https://tantancansado.github.io/stock_analyzer_a'
GROQ_MODEL   = 'meta-llama/llama-4-scout-17b-16e-instruct'


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


def groq_summary(data: dict) -> str:
    if not GROQ_API_KEY:
        return ''
    prompt = f"""Eres un analista de inversiones VALUE. Resume esta semana de trading en 3 frases directas en español.
Datos: {json.dumps(data, ensure_ascii=False)}
Menciona: rendimiento vs expectativas, qué funcionó, qué vigilar la próxima semana.
Responde solo con las 3 frases, sin introducción ni título."""
    try:
        r = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {GROQ_API_KEY}', 'Content-Type': 'application/json'},
            json={
                'model': GROQ_MODEL,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.3,
                'max_tokens': 300,
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content'].strip()
    except Exception:
        return ''


def main():
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=7)).strftime('%Y-%m-%d')

    # ── Datos del summary ──────────────────────────────────────────────────────
    summary = fetch(f'{PAGES_BASE}/docs/portfolio_tracker/summary.json', as_json=True)
    if not summary:
        tg('⚠️ <b>Weekly Report:</b> sin datos de portfolio esta semana.')
        return

    overall = summary.get('overall', {})
    w7  = overall.get('7d', {})
    w14 = overall.get('14d', {})

    win_7d   = w7.get('win_rate')
    avg_7d   = w7.get('avg_return')
    win_14d  = w14.get('win_rate')
    avg_14d  = w14.get('avg_return')
    total    = summary.get('total_signals', 0)
    active   = summary.get('active_signals', 0)

    # ── Señales de la semana ────────────────────────────────────────────────────
    recs_csv = fetch(f'{PAGES_BASE}/docs/portfolio_tracker/recommendations.csv')
    week_signals = []
    best_this_week = None
    worst_this_week = None

    if recs_csv:
        reader = csv.DictReader(io.StringIO(recs_csv))
        for row in reader:
            sig_date = row.get('signal_date', '')
            if sig_date >= week_start:
                week_signals.append(row)

        # Best/worst con retorno 7d de la semana
        with_return = [r for r in week_signals if r.get('return_7d')]
        if with_return:
            try:
                best_this_week  = max(with_return, key=lambda r: float(r['return_7d']))
                worst_this_week = min(with_return, key=lambda r: float(r['return_7d']))
            except Exception:
                pass

    # ── Top performers del summary ─────────────────────────────────────────────
    top = summary.get('top_performers', [])
    worst = summary.get('worst_performers', [])

    # ── Análisis Groq ──────────────────────────────────────────────────────────
    groq_data = {
        'win_rate_7d': win_7d,
        'avg_return_7d': avg_7d,
        'win_rate_14d': win_14d,
        'avg_return_14d': avg_14d,
        'total_signals': total,
        'new_signals_this_week': len(week_signals),
        'active_signals': active,
        'top_performer': top[0] if top else None,
        'worst_performer': worst[0] if worst else None,
    }
    ai_analysis = groq_summary(groq_data)

    # ── Construir mensaje ──────────────────────────────────────────────────────
    def fmt_pct(v):
        if v is None:
            return 'N/A'
        sign = '+' if v >= 0 else ''
        return f'{sign}{v:.1f}%'

    def grade_wr(wr):
        if wr is None:
            return ''
        if wr >= 55:
            return '🟢'
        if wr >= 40:
            return '🟡'
        return '🔴'

    lines = [
        f"📊 <b>Weekly Report — semana {week_start}</b>",
        '━━━━━━━━━━━━━━━━━━━━━',
        '',
        '<b>Rendimiento acumulado</b>',
        f"  7d:  {grade_wr(win_7d)} Win {fmt_pct(win_7d)} · Avg {fmt_pct(avg_7d)}",
        f"  14d: {grade_wr(win_14d)} Win {fmt_pct(win_14d)} · Avg {fmt_pct(avg_14d)}",
        '',
        f"<b>Actividad</b>",
        f"  Nuevas señales esta semana: {len(week_signals)}",
        f"  Total activas: {active} · Total históricas: {total}",
    ]

    if top:
        p = top[0]
        lines += ['', f"<b>Mejor posición:</b> <code>{p['ticker']}</code> {fmt_pct(p.get('return_14d'))} (14d)"]
    if worst:
        p = worst[0]
        lines += [f"<b>Peor posición:</b> <code>{p['ticker']}</code> {fmt_pct(p.get('return_14d'))} (14d)"]

    if ai_analysis:
        lines += ['', '🤖 <i>' + ai_analysis.replace('\n', ' ') + '</i>']

    tg('\n'.join(lines))
    print('✅ Weekly report enviado')


if __name__ == '__main__':
    main()
