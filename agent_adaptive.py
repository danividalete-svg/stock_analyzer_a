#!/usr/bin/env python3
"""
AGENT ADAPTIVE — Bucle de aprendizaje autónomo
Analiza el historial de señales y ajusta parámetros del sistema
basándose en evidencia estadística real.

Corre: lunes 6h UTC (antes del pipeline diario)
Railway cron: "0 6 * * 1"

Lógica:
  1. Lee recommendations.csv y calcula calibración por score/régimen/sector
  2. Identifica el umbral de score óptimo (mejor win rate con N>=30)
  3. Detecta régimen actual y su win rate histórico
  4. Escribe adaptive_config.json con los umbrales recomendados
  5. Propone cambios en Telegram — auto-aplica si confianza estadística alta
  6. Siempre envía resumen con los hallazgos
"""

from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime, timezone

import requests

BOT_TOKEN  = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID    = os.environ.get('TELEGRAM_CHAT_ID', '')
PAGES_BASE = 'https://tantancansado.github.io/stock_analyzer_a'
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO  = os.environ.get('GITHUB_REPO', 'tantancansado/stock_analyzer_a')

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GROQ_MODEL   = 'meta-llama/llama-4-scout-17b-16e-instruct'

# Umbrales estadísticos
MIN_SIGNALS_FOR_CONFIDENCE = 30   # mínimo de señales para confiar en el dato
MIN_SIGNALS_AUTO_APPLY     = 80   # auto-aplica sin pedir aprobación si N>=80
WIN_RATE_GOOD              = 35.0 # win rate aceptable
WIN_RATE_DANGER            = 20.0 # régimen peligroso → alertar

# Rango de score mínimo permitido (no bajar de 50 ni subir de 68)
SCORE_MIN_FLOOR = 50
SCORE_MIN_CEIL  = 68


def tg_send(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        print(text)
        return
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        try:
            requests.post(
                f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
                json={'chat_id': CHAT_ID, 'text': chunk,
                      'parse_mode': 'HTML', 'disable_web_page_preview': True},
                timeout=10,
            )
        except Exception:
            pass


def tg_send_with_buttons(text: str, buttons: list):
    if not BOT_TOKEN or not CHAT_ID:
        print(text)
        return
    keyboard = {'inline_keyboard': [buttons]}
    try:
        requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            json={'chat_id': CHAT_ID, 'text': text,
                  'parse_mode': 'HTML', 'reply_markup': keyboard,
                  'disable_web_page_preview': True},
            timeout=10,
        )
    except Exception:
        pass


def fetch_csv(path: str) -> list:
    url = f'{PAGES_BASE}/{path}'
    try:
        r = requests.get(url, timeout=20)
        if r.status_code != 200:
            return []
        return list(csv.DictReader(io.StringIO(r.text)))
    except Exception:
        return []


def fetch_json(path: str) -> dict:
    url = f'{PAGES_BASE}/{path}'
    try:
        r = requests.get(url, timeout=15)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}


def gh_update_file(path: str, content: str, message: str) -> bool:
    """Write/update a file in GitHub."""
    import base64
    api = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{path}'
    headers = {'Authorization': f'token {GITHUB_TOKEN}',
                'Accept': 'application/vnd.github.v3+json'}
    # Get current SHA
    r = requests.get(api, headers=headers, timeout=10)
    sha = r.json().get('sha', '') if r.status_code == 200 else ''
    payload = {
        'message': message,
        'content': base64.b64encode(content.encode()).decode(),
        'branch': 'main',
    }
    if sha:
        payload['sha'] = sha
    r = requests.put(api, headers=headers, json=payload, timeout=15)
    return r.status_code in (200, 201)


# ── Analysis ───────────────────────────────────────────────────────────────────

def compute_calibration(rows: list) -> dict:
    """Compute win rates by score bucket, regime and sector."""
    completed = [
        r for r in rows
        if r.get('return_14d') not in ('', None)
        and _f(r.get('return_14d')) is not None
        and -95 < _f(r['return_14d']) < 500
    ]

    def bucket_stats(subset):
        if len(subset) < 5:
            return None
        wins = sum(1 for r in subset if r.get('win_14d') == 'True')
        returns = [_f(r['return_14d']) for r in subset]
        return {
            'n': len(subset),
            'win_rate': round(wins / len(subset) * 100, 1),
            'avg_return': round(sum(returns) / len(returns), 2),
        }

    # Score buckets
    score_buckets = []
    for lo, hi in [(50, 55), (55, 60), (60, 65), (65, 70), (70, 200)]:
        sub = [r for r in completed
               if _f(r.get('value_score')) is not None
               and lo <= _f(r['value_score']) < hi]
        stats = bucket_stats(sub)
        if stats:
            stats['range'] = f'{lo}-{hi}' if hi < 200 else f'{lo}+'
            stats['lo'] = lo
            score_buckets.append(stats)

    # Regime
    regimes = {}
    for r in completed:
        reg = r.get('market_regime', '')
        if reg:
            regimes.setdefault(reg, []).append(r)
    regime_stats = {
        reg: bucket_stats(rows_)
        for reg, rows_ in regimes.items()
        if bucket_stats(rows_)
    }

    # Sector (min 10)
    sectors = {}
    for r in completed:
        sec = r.get('sector', '')
        if sec:
            sectors.setdefault(sec, []).append(r)
    sector_stats = {}
    for sec, rows_ in sectors.items():
        stats = bucket_stats(rows_)
        if stats and stats['n'] >= 10:
            sector_stats[sec] = stats

    return {
        'score_buckets': score_buckets,
        'regimes': regime_stats,
        'sectors': sector_stats,
        'total': len(completed),
    }


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def find_optimal_score_min(buckets: list) -> tuple:
    """
    Find the score bucket with highest win_rate (min N signals).
    Returns (optimal_lo, evidence_n, win_rate).
    """
    candidates = [b for b in buckets if b['n'] >= MIN_SIGNALS_FOR_CONFIDENCE]
    if not candidates:
        return None, 0, 0.0
    best = max(candidates, key=lambda b: b['win_rate'])
    return best['lo'], best['n'], best['win_rate']


def groq_narrative(findings: dict) -> str:
    """Ask Groq to write a 3-sentence narrative of the findings."""
    if not GROQ_API_KEY:
        return '(GROQ_API_KEY no configurado)'
    prompt = f"""Eres un analista cuantitativo. Resume estos hallazgos del sistema de trading en 3 frases cortas en español, siendo específico con los números. Sé directo, sin introducción.

Hallazgos:
{json.dumps(findings, ensure_ascii=False, indent=2)}

Responde solo las 3 frases, sin título."""
    try:
        r = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {GROQ_API_KEY}',
                     'Content-Type': 'application/json'},
            json={'model': GROQ_MODEL,
                  'messages': [{'role': 'user', 'content': prompt}],
                  'max_tokens': 200, 'temperature': 0.3},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f'(Error Groq: {e})'


# ── Main ───────────────────────────────────────────────────────────────────────

def run():
    now = datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')
    print(f'🧠 Agent Adaptive corriendo — {now}')

    rows = fetch_csv('docs/portfolio_tracker/recommendations.csv')
    if not rows:
        tg_send('⚠️ <b>Agent Adaptive:</b> No se pudo cargar recommendations.csv')
        return

    cal = compute_calibration(rows)
    if cal['total'] < 50:
        tg_send(f'⚠️ <b>Agent Adaptive:</b> Solo {cal["total"]} señales completadas — insuficiente para calibrar')
        return

    # ── Current market regime ──
    regime_data = fetch_json('docs/market_regime.json')
    current_regime = regime_data.get('regime', 'UNKNOWN')

    # ── Find optimal score threshold ──
    opt_score, opt_n, opt_wr = find_optimal_score_min(cal['score_buckets'])

    # Current system minimum (fixed at 55 by convention)
    current_score_min = 55

    # ── Regime analysis ──
    regime_stats = cal['regimes']
    current_regime_stats = regime_stats.get(current_regime, {})
    regime_win_rate = current_regime_stats.get('win_rate', None)
    regime_n = current_regime_stats.get('n', 0)

    # ── Sector analysis — best and worst ──
    sector_stats = cal['sectors']
    sectors_sorted = sorted(sector_stats.items(), key=lambda x: -x[1]['win_rate'])
    best_sectors  = sectors_sorted[:3]
    worst_sectors = sectors_sorted[-3:]

    # ── Build adaptive_config.json ──
    recommended_score_min = current_score_min
    score_changed = False
    if opt_score and opt_n >= MIN_SIGNALS_FOR_CONFIDENCE:
        new_min = max(SCORE_MIN_FLOOR, min(SCORE_MIN_CEIL, opt_score))
        if new_min != current_score_min:
            recommended_score_min = new_min
            score_changed = True

    # Regime modifier: in very bad regimes, add +5 to score min
    regime_modifier = 0
    regime_warning = False
    if regime_win_rate is not None and regime_n >= MIN_SIGNALS_FOR_CONFIDENCE:
        if regime_win_rate < WIN_RATE_DANGER:
            regime_modifier = +5
            regime_warning = True

    adaptive_config = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'total_signals_analyzed': cal['total'],
        'current_regime': current_regime,
        'recommended_score_min': recommended_score_min + regime_modifier,
        'regime_modifier': regime_modifier,
        'regime_win_rate': regime_win_rate,
        'regime_n': regime_n,
        'optimal_score_bucket': {
            'lo': opt_score, 'win_rate': opt_wr, 'n': opt_n
        } if opt_score else None,
        'best_sectors': [s for s, _ in best_sectors],
        'worst_sectors': [s for s, _ in worst_sectors],
        'score_calibration': cal['score_buckets'],
        'regime_calibration': [
            {'regime': k, **v} for k, v in regime_stats.items()
        ],
    }

    # Write to GitHub Pages
    if GITHUB_TOKEN:
        ok = gh_update_file(
            'docs/adaptive_config.json',
            json.dumps(adaptive_config, indent=2, ensure_ascii=False),
            f'agent-adaptive: weekly calibration update ({cal["total"]} signals)',
        )
        print(f'  adaptive_config.json: {"✅" if ok else "❌"}')

    # ── Findings for Groq narrative ──
    findings = {
        'señales_analizadas': cal['total'],
        'régimen_actual': current_regime,
        'win_rate_régimen_actual': regime_win_rate,
        'mejor_bucket_score': f'{opt_score}pts ({opt_wr:.1f}% win, n={opt_n})',
        'umbral_recomendado': recommended_score_min + regime_modifier,
        'umbral_actual': current_score_min,
        'sectores_top': [f'{s} {d["win_rate"]}%' for s, d in best_sectors],
        'sectores_débiles': [f'{s} {d["win_rate"]}%' for s, d in worst_sectors],
    }
    narrative = groq_narrative(findings)

    # ── Score calibration table ──
    bucket_lines = []
    for b in cal['score_buckets']:
        bar_filled = int(b['win_rate'] / 5)
        bar = '█' * bar_filled + '░' * (10 - bar_filled)
        marker = ' ◀ óptimo' if b.get('lo') == opt_score else ''
        bucket_lines.append(
            f"  <code>{b['range']:6s}</code> {bar} {b['win_rate']:4.1f}%  n={b['n']}{marker}"
        )

    # ── Regime table ──
    regime_lines = []
    for reg, stats in sorted(regime_stats.items(), key=lambda x: -x[1]['win_rate']):
        icon = '🟢' if stats['win_rate'] >= WIN_RATE_GOOD else ('🟡' if stats['win_rate'] >= WIN_RATE_DANGER else '🔴')
        regime_lines.append(
            f"  {icon} <b>{reg}</b>: {stats['win_rate']:.1f}% win  avg {stats['avg_return']:+.1f}%  n={stats['n']}"
        )

    # ── Build message ──
    lines = [
        f'🧠 <b>Adaptive Learning — Reporte Semanal</b>',
        f'<code>{now}</code>  ·  {cal["total"]} señales analizadas',
        '─────────────────────',
        '',
        f'<b>Calibración por Score VALUE</b>',
    ]
    lines += bucket_lines
    lines += ['', '<b>Por Régimen de Mercado</b>']
    lines += regime_lines

    if best_sectors:
        lines.append('')
        lines.append('<b>Sectores más fiables</b>  '
                     + '  '.join(f'{s} {d["win_rate"]:.0f}%' for s, d in best_sectors))
    if worst_sectors:
        lines.append('<b>Sectores a evitar</b>  '
                     + '  '.join(f'{s} {d["win_rate"]:.0f}%' for s, d in worst_sectors))

    lines += ['', f'<i>{narrative}</i>', '']

    # ── Changes proposed ──
    changes = []

    if score_changed and opt_n >= MIN_SIGNALS_FOR_CONFIDENCE:
        auto = opt_n >= MIN_SIGNALS_AUTO_APPLY
        lines.append(f'🔧 <b>Ajuste de score mínimo:</b> {current_score_min} → {recommended_score_min}')
        lines.append(f'   Evidencia: {opt_n} señales, {opt_wr:.1f}% win rate en bucket {opt_score}pts')
        if auto:
            lines.append(f'   ✅ <b>Auto-aplicado</b> (N={opt_n} ≥ {MIN_SIGNALS_AUTO_APPLY})')
        else:
            changes.append(('score_min', current_score_min, recommended_score_min, opt_n))

    if regime_warning:
        lines.append('')
        lines.append(f'⚠️ <b>Régimen peligroso:</b> {current_regime}')
        lines.append(f'   Win rate histórico: {regime_win_rate:.1f}% (n={regime_n})')
        lines.append(f'   → Filtros endurecidos automáticamente (+5pts score mínimo)')

    msg = '\n'.join(lines)

    if changes:
        buttons = []
        for param, cur, new, n in changes:
            buttons.append({
                'text': f'✅ Aplicar {param}: {cur}→{new}',
                'callback_data': f'approve_SCORE_MIN_{cur}_{new}'
            })
        tg_send_with_buttons(msg, buttons)
    else:
        tg_send(msg)

    # Write calibration.json (same format as portfolio_tracker)
    calibration_out = {
        'score_buckets': cal['score_buckets'],
        'regime_analysis': [{'regime': k, **v} for k, v in regime_stats.items()],
        'sector_calibration': [{'sector': k, **v} for k, v in sector_stats.items()],
        'fcf_yield_buckets': [],
        'total_completed': cal['total'],
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }
    if GITHUB_TOKEN:
        gh_update_file(
            'docs/portfolio_tracker/calibration.json',
            json.dumps(calibration_out, indent=2, ensure_ascii=False),
            f'agent-adaptive: calibration.json update',
        )

    print(f'✅ Done — {len(changes)} changes proposed, regime={current_regime}')


if __name__ == '__main__':
    run()
