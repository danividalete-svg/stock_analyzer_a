#!/usr/bin/env python3
"""
AUTO TELEGRAM ALERTS — Mensaje diario conciso
Contenido: Cerebro AI briefing + entradas activas + alertas críticas
"""
import sys
import json
import os
import requests
from pathlib import Path
from datetime import datetime


DOCS = Path('docs')
APP_URL = 'https://tantancansado.github.io/stock_analyzer_a/app/'

REGIME_EMOJI = {
    'BULL':       '🟢',
    'RECOVERY':   '🔵',
    'NEUTRAL':    '⚪',
    'CORRECTION': '🟡',
    'BEAR':       '🔴',
    'STRESS':     '🔴',
}

SIGNAL_EMOJI = {
    'STRONG_BUY': '🚀',
    'BUY':        '✅',
    'MONITOR':    '👁',
    'WAIT':       '⏳',
    'EXIT':       '🚪',
    'TRAP':       '⚠️',
}


def _load_json(filename: str):
    p = DOCS / filename
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _send(token: str, chat_id: str, text: str) -> bool:
    try:
        r = requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML',
                  'disable_web_page_preview': True},
            timeout=10
        )
        return r.ok
    except Exception as e:
        print(f'  ❌ Telegram error: {e}')
        return False


def build_message() -> str:
    lines = []
    today = datetime.now().strftime('%d %b %Y')

    # ── HEADER ────────────────────────────────────────────────────────────────
    plan = _load_json('cerebro_daily_plan.json') or {}
    regime = (plan.get('macro_regime') or 'NEUTRAL').upper()
    sesgo  = plan.get('sesgo', '—')
    conf   = plan.get('confianza', '—')
    situacion = plan.get('situacion', '')
    r_emoji = REGIME_EMOJI.get(regime, '⚪')

    lines.append(f'<b>🧠 Cerebro · {today}</b>')
    lines.append(f'{r_emoji} <b>{regime}</b> · Sesgo: {sesgo} · Confianza: {conf}%')
    if situacion:
        lines.append(f'<i>{situacion}</i>')

    # ── ACCIONES INMEDIATAS (top 3, solo COMPRAR/VENDER) ──────────────────────
    acciones = [a for a in plan.get('acciones_inmediatas', [])
                if a.get('accion') in ('COMPRAR', 'VENDER')][:3]
    if acciones:
        lines.append('')
        lines.append('📋 <b>Acciones prioritarias:</b>')
        for a in acciones:
            verb  = '🟢 Comprar' if a['accion'] == 'COMPRAR' else '🔴 Vender'
            inst  = a.get('instrumento', '')
            razon = (a.get('razon') or '')[:70]
            lines.append(f'  {verb} <b>{inst}</b> — {razon}')

    # ── ENTRADAS ACTIVAS (señales Cerebro BUY/STRONG_BUY, top 5) ─────────────
    entry_data = _load_json('cerebro_entry_signals.json') or {}
    signals = entry_data.get('signals', []) if isinstance(entry_data, dict) else []
    buys = [s for s in signals if s.get('signal') in ('BUY', 'STRONG_BUY')]
    buys.sort(key=lambda x: x.get('entry_score', 0), reverse=True)

    if buys:
        lines.append('')
        lines.append(f'✅ <b>Entradas activas ({len(buys)}):</b>')
        for s in buys[:5]:
            t     = s.get('ticker', '')
            score = s.get('entry_score', 0)
            up    = s.get('analyst_upside_pct')
            fcf   = s.get('fcf_yield_pct')
            earn  = ' ⚠️earn' if s.get('earnings_warning') else ''
            up_str  = f' 🎯{up:.0f}%' if up else ''
            fcf_str = f' FCF{fcf:.1f}%' if fcf else ''
            em = SIGNAL_EMOJI.get(s.get('signal', ''), '')
            lines.append(f'  {em} <b>{t}</b> ({score}pts){up_str}{fcf_str}{earn}')

    # ── SALIDAS / TRAMPAS (solo HIGH, top 4) ──────────────────────────────────
    exit_data  = _load_json('cerebro_exit_signals.json') or {}
    exits = [e for e in (exit_data.get('exits', []) if isinstance(exit_data, dict) else [])
             if e.get('severity') == 'HIGH'][:4]

    traps_data = _load_json('cerebro_value_traps.json') or {}
    traps = [t for t in (traps_data.get('traps', []) if isinstance(traps_data, dict) else [])
             if t.get('trap_score', 0) >= 7][:3]

    if exits or traps:
        lines.append('')
        lines.append('🚪 <b>Salidas/Trampas:</b>')
        for e in exits:
            t = e.get('ticker', '')
            reasons = e.get('reasons') or []
            r = (reasons[0] if reasons else e.get('signal', ''))[:60]
            lines.append(f'  🔴 <b>{t}</b> — {r}')
        for trap in traps:
            t  = trap.get('ticker', '')
            sc = trap.get('trap_score', 0)
            lines.append(f'  ⚠️ <b>{t}</b> — Value trap {sc}/10')

    # ── SMART MONEY (insiders con alta convicción, top 3) ─────────────────────
    alerts_data = _load_json('cerebro_alerts.json') or {}
    all_alerts  = alerts_data.get('alerts', []) if isinstance(alerts_data, dict) else []
    insider_hi  = [a for a in all_alerts
                   if a.get('type') == 'INSIDER_BUYING' and a.get('severity') == 'HIGH'][:3]

    if insider_hi:
        lines.append('')
        lines.append('🐳 <b>Insiders comprando:</b>')
        for a in insider_hi:
            t   = a.get('ticker', '')
            msg = (a.get('message') or '')[:55]
            lines.append(f'  💼 <b>{t}</b> — {msg}')

    # ── MACRO PLAYS (top 2 del plan) ──────────────────────────────────────────
    macro_plays = plan.get('macro_plays', [])[:2]
    if macro_plays:
        lines.append('')
        lines.append('🌍 <b>Macro plays:</b>')
        for mp in macro_plays:
            inst   = mp.get('instrument', '')
            dir_   = mp.get('direction', '')
            thesis = (mp.get('thesis') or '')[:65]
            tf     = mp.get('timeframe', '')
            d_em   = '🟢' if dir_ == 'LONG' else '🔴'
            lines.append(f'  {d_em} <b>{inst}</b> ({tf}) — {thesis}')

    # ── FOOTER ────────────────────────────────────────────────────────────────
    lines.append('')
    lines.append(f'<a href="{APP_URL}cerebro">→ Cerebro completo</a>')

    return '\n'.join(lines)


def main():
    token   = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')

    if not token or not chat_id:
        try:
            import config
            token   = token   or getattr(config, 'TELEGRAM_BOT_TOKEN', None)
            chat_id = chat_id or getattr(config, 'TELEGRAM_CHAT_ID', None)
        except ImportError:
            pass

    if not token or not chat_id:
        print('❌ TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID no configurados')
        return 1

    print('🧠 Generando mensaje Cerebro...')
    msg = build_message()
    print(msg)
    print()

    ok = _send(token, chat_id, msg)
    if ok:
        print('✅ Mensaje enviado')
        return 0
    else:
        print('❌ Error al enviar')
        return 1


if __name__ == '__main__':
    sys.exit(main())
