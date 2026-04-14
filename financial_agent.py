#!/usr/bin/env python3
"""
FINANCIAL EXPERT AGENT — Briefing matutino accionable

Corre cada mañana a las 8:30 ET (antes de apertura) y opcionalmente
tras scans intraday de unusual flow.

Flujo:
  1. Carga signals activos: bounce, value (filtrado), unusual flow
  2. Carga posiciones abiertas desde Supabase
  3. Conviction scoring: cuántos signals alinean por ticker
  4. Detecta conflictos (PUT sweep en nuestros picks) y confirmaciones
  5. Groq genera briefing orientado a decisiones, no a descripción
  6. Envía a Telegram

Variables de entorno:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GROQ_API_KEY
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_MONITOR_USER_ID (opcional)

Uso:
  python3 financial_agent.py              # briefing completo
  python3 financial_agent.py --flow-only  # solo alertas de conflicto de flow
  python3 financial_agent.py --no-groq    # briefing estructurado sin IA
"""

import argparse
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN    = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID      = os.environ.get('TELEGRAM_CHAT_ID', '')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GITHUB_PAGES = 'https://raw.githubusercontent.com/tantancansado/stock_analyzer_a/main/docs'

GROQ_MODEL = 'meta-llama/llama-4-scout-17b-16e-instruct'
DOCS       = Path('docs')


# ── Telegram ──────────────────────────────────────────────────────────────────

def _tg(text: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print(text)
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


# ── Data loaders ──────────────────────────────────────────────────────────────

def _load_json(filename: str) -> Optional[dict]:
    """Carga JSON desde docs/ local o GitHub Pages como fallback."""
    local = DOCS / filename
    if local.exists():
        try:
            return json.loads(local.read_text())
        except Exception:
            pass
    try:
        r = requests.get(f'{GITHUB_PAGES}/{filename}', timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _load_csv_tickers(filename: str, score_col: str = 'value_score', n: int = 15) -> list[dict]:
    """Carga los top N tickers de un CSV por score."""
    local = DOCS / filename
    if not local.exists():
        return []
    try:
        import pandas as pd
        df = pd.read_csv(local)
        if score_col in df.columns:
            df = df.sort_values(score_col, ascending=False)
        return df.head(n).to_dict('records')
    except Exception:
        return []


def _load_open_positions() -> list[dict]:
    """
    Carga posiciones abiertas desde Supabase (personal_portfolio_positions).
    Devuelve lista de {ticker, shares, avg_price}.
    """
    supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    service_key  = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    user_id      = os.environ.get('SUPABASE_MONITOR_USER_ID', '')

    if not supabase_url or not service_key:
        return []

    url = f"{supabase_url}/rest/v1/personal_portfolio_positions?select=ticker,shares,avg_price,entry_date"
    if user_id:
        url += f"&user_id=eq.{user_id}"

    req = urllib.request.Request(url, headers={
        'apikey': service_key,
        'Authorization': f'Bearer {service_key}',
        'Content-Type': 'application/json',
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            rows = json.loads(resp.read().decode())
            positions = [
                {
                    'ticker':     r['ticker'],
                    'shares':     r.get('shares'),
                    'avg_price':  r.get('avg_price'),
                    'entry_date': r.get('entry_date', ''),
                }
                for r in rows if r.get('ticker')
            ]
            print(f"  Supabase: {len(positions)} posiciones abiertas")
            return positions
    except Exception as e:
        print(f"  Supabase no disponible: {e}")
        return []


# ── Signal loading ────────────────────────────────────────────────────────────

def load_all_signals() -> dict:
    """Carga todos los signals activos del sistema."""
    signals: dict = {
        'bounce':       [],
        'value_us':     [],
        'value_eu':     [],
        'unusual_flow': [],
        'market_regime': None,
        'vix':          None,
        'open_positions': [],
    }

    # ── Bounce setups (filtrados igual que el frontend) ───────────────────────
    mr = _load_json('mean_reversion_opportunities.json')
    if mr:
        ops = mr.get('opportunities', [])
        signals['market_regime'] = mr.get('market_regime') or (
            ops[0].get('market_regime') if ops else None
        )
        for o in ops:
            if o.get('vix'):
                signals['vix'] = o['vix']
                break
        for o in ops:
            if o.get('strategy') != 'Oversold Bounce':
                continue
            rsi   = o.get('rsi', 0) or 0
            conf  = o.get('bounce_confidence', 0) or 0
            dp    = o.get('dark_pool_signal', '')
            price = o.get('current_price', 0) or 0
            rr    = o.get('risk_reward', 0) or 0
            if (rsi < 30 and rsi > 0 and conf >= 40 and price >= 1.0
                    and not (dp == 'DISTRIBUTION' and conf < 60)
                    and (rr == 0 or rr >= 1.0)):
                signals['bounce'].append({
                    'ticker': o['ticker'],
                    'rsi':    rsi,
                    'conf':   conf,
                    'dp':     dp,
                    'score':  o.get('reversion_score'),
                    'tier':   o.get('conviction_tier', 1),
                    'rr':     rr,
                })

    # ── Value picks — usar CSV filtrado por IA ────────────────────────────────
    for path, key in [
        ('value_opportunities_filtered.csv', 'value_us'),
        ('european_value_opportunities.csv',  'value_eu'),
    ]:
        rows = _load_csv_tickers(path, 'value_score', 10)
        for r in rows:
            ticker = str(r.get('ticker', '')).strip()
            score  = r.get('value_score') or r.get('score', 0)
            grade  = r.get('conviction_grade', r.get('grade', ''))
            sector = r.get('sector', '')
            if ticker:
                signals[key].append({
                    'ticker': ticker, 'score': score,
                    'grade': grade, 'sector': sector,
                    'upside': r.get('analyst_upside_pct'),
                    'fcf_yield': r.get('fcf_yield_pct'),
                })

    # ── Unusual flow ─────────────────────────────────────────────────────────
    uf = _load_json('unusual_flow.json')
    if uf:
        scan_str = uf.get('scan_date', '')
        scan_dt  = None
        if scan_str:
            try:
                scan_dt = datetime.fromisoformat(scan_str.replace('Z', '+00:00'))
            except Exception:
                pass
        for r in uf.get('results', []):
            if r.get('total_premium', 0) < 50_000:
                continue
            if scan_dt:
                age_h = (datetime.now(timezone.utc) - scan_dt).total_seconds() / 3600
                if age_h > 4:
                    continue
            signals['unusual_flow'].append({
                'ticker':              r['ticker'],
                'signal':              r['signal'],
                'flow_interpretation': r.get('flow_interpretation', 'STANDARD'),
                'drawdown_pct':        r.get('drawdown_from_high_pct'),
                'call_pct':            r.get('call_pct', 50),
                'premium':             r.get('total_premium', 0),
                'score':               r.get('unusual_score', 0),
                'sweeps':              [c for c in r.get('top_contracts', []) if c.get('speculative')],
            })

    # ── Open positions ────────────────────────────────────────────────────────
    signals['open_positions'] = _load_open_positions()

    return signals


# ── Conviction scoring ────────────────────────────────────────────────────────

def score_conviction(signals: dict) -> list[dict]:
    """
    Para cada ticker en VALUE, cuenta cuántos otros signals alinean.
    Devuelve lista ordenada por conviction total (más señales = más arriba).
    """
    bounce_tickers = {s['ticker'] for s in signals['bounce']}
    flow_by_ticker = {s['ticker']: s for s in signals['unusual_flow']}
    open_tickers   = {p['ticker'] for p in signals['open_positions']}

    results = []
    all_value = signals['value_us'] + signals['value_eu']

    for v in all_value:
        ticker  = v['ticker']
        reasons = ['VALUE']
        notes   = []

        if ticker in bounce_tickers:
            b = next(s for s in signals['bounce'] if s['ticker'] == ticker)
            reasons.append('BOUNCE')
            notes.append(f"RSI {b['rsi']:.0f} conf {b['conf']}%")

        if ticker in flow_by_ticker:
            f = flow_by_ticker[ticker]
            if f['signal'] == 'BULLISH' and f['call_pct'] > 60:
                reasons.append('FLOW↑')
                notes.append(f"${f['premium']/1e3:.0f}K calls {f['call_pct']:.0f}%")
            elif f['signal'] == 'BEARISH' and f['call_pct'] < 30:
                reasons.append('FLOW↓')   # conflicto
                notes.append(f"⚠️ PUT sweep ${f['premium']/1e3:.0f}K")

        already_open = ticker in open_tickers
        region = 'EU' if v in signals['value_eu'] else 'US'

        results.append({
            'ticker':   ticker,
            'score':    v['score'],
            'grade':    v['grade'],
            'sector':   v['sector'],
            'upside':   v.get('upside'),
            'fcf':      v.get('fcf_yield'),
            'region':   region,
            'signals':  reasons,
            'notes':    notes,
            'n_signals': len(reasons),
            'conflict': 'FLOW↓' in reasons,
            'open':     already_open,
        })

    # Ordenar: conflictos al final, luego por n_signals desc, luego por score
    return sorted(results,
                  key=lambda x: (x['conflict'], -x['n_signals'], -float(x['score'] or 0)))


# ── Cross-signal analysis ─────────────────────────────────────────────────────

def detect_crosssignals(signals: dict) -> dict:
    """Detecta conflictos y confirmaciones entre signals."""
    bounce_tickers = {s['ticker'] for s in signals['bounce']}
    value_tickers  = {s['ticker'] for s in signals['value_us'] + signals['value_eu']}
    flow_by_ticker = {s['ticker']: s for s in signals['unusual_flow']}

    conflicts     = []
    confirmations = []
    big_alerts    = []

    for ticker, flow in flow_by_ticker.items():
        prem     = flow['premium']
        sig      = flow['signal']
        call_pct = flow.get('call_pct', 50)
        interp   = flow.get('flow_interpretation', '')
        drawdown = flow.get('drawdown_pct')

        in_bounce = ticker in bounce_tickers
        in_value  = ticker in value_tickers

        if sig == 'BEARISH' and call_pct < 30:
            if interp == 'PUT_COVERING':
                dd_str = f" {drawdown:.0f}% bajo máx" if drawdown else ''
                confirmations.append({
                    'ticker':   ticker,
                    'reason':   f'Puts recogiendo beneficios{dd_str} — posible suelo técnico',
                    'premium':  prem,
                    'call_pct': call_pct,
                })
            elif in_bounce or in_value:
                kind = 'bounce setup' if in_bounce else 'value pick'
                conflicts.append({
                    'ticker':   ticker,
                    'reason':   f'{kind} con PUT sweep nuevo (${prem/1e3:.0f}K)',
                    'premium':  prem,
                    'call_pct': call_pct,
                    'severity': 'HIGH' if prem > 100_000 else 'MEDIUM',
                })

        if sig == 'BULLISH' and call_pct > 70 and in_value:
            confirmations.append({
                'ticker':  ticker,
                'reason':  f'VALUE + CALL sweep (${prem/1e3:.0f}K)',
                'premium': prem,
                'call_pct': call_pct,
            })

        if prem > 500_000 and not in_bounce and not in_value:
            big_alerts.append({
                'ticker':  ticker,
                'signal':  sig,
                'premium': prem,
                'reason':  f'Flujo grande fuera de nuestro universo (${prem/1e6:.1f}M)',
            })

    return {
        'conflicts':     sorted(conflicts,     key=lambda x: -x['premium']),
        'confirmations': sorted(confirmations, key=lambda x: -x['premium']),
        'big_alerts':    sorted(big_alerts,    key=lambda x: -x['premium'])[:5],
    }


# ── Groq briefing ─────────────────────────────────────────────────────────────

ANALYST_SYSTEM = """Eres un analista financiero VALUE/GARP (estilo Lynch) que genera briefings matutinos.
Tu objetivo: decirle al usuario exactamente QUÉ HACER HOY con sus posiciones y oportunidades.

REGLAS:
- Orientado a decisiones, no a describir señales (el usuario ya ve los datos)
- Máximo 3 oportunidades de entrada — las de mayor conviction (más signals alineados)
- Si hay conflictos (PUT sweep en un pick), es lo PRIMERO que mencionas
- Si hay posiciones abiertas, menciona si hay que hacer algo con ellas
- VIX > 30 = mercado difícil, ser conservador; VIX < 20 = condiciones favorables
- Formato HTML Telegram (<b>, <i>, <code>) — conciso, sin florituras"""


def groq_briefing(signals: dict, conviction: list[dict], cross: dict) -> Optional[str]:
    if not GROQ_API_KEY:
        return None

    # Contexto compacto — solo lo que el LLM necesita
    ctx = [
        f"MERCADO: {signals.get('market_regime','?')} | VIX: {signals.get('vix','?')}",
        "",
        "TOP OPORTUNIDADES (ordenadas por conviction):",
    ]
    for c in conviction[:5]:
        flags = '+'.join(c['signals'])
        upside = f" upside {c['upside']:.0f}%" if c['upside'] else ''
        fcf    = f" FCF {c['fcf']:.1f}%" if c['fcf'] else ''
        open_  = ' [OPEN]' if c['open'] else ''
        conflict_ = ' ⚠️CONFLICT' if c['conflict'] else ''
        notes_ = f" ({'; '.join(c['notes'])})" if c['notes'] else ''
        ctx.append(
            f"  {c['ticker']} [{flags}]{conflict_}{open_} grade={c['grade']}"
            f"{upside}{fcf}{notes_}"
        )

    if cross['conflicts']:
        ctx += ["", "⚠️ CONFLICTOS:"]
        for c in cross['conflicts']:
            ctx.append(f"  {c['ticker']}: {c['reason']} [{c['severity']}]")

    if cross['confirmations']:
        ctx += ["", "✅ CONFIRMACIONES:"]
        for c in cross['confirmations']:
            ctx.append(f"  {c['ticker']}: {c['reason']}")

    if signals['open_positions']:
        ctx += ["", "POSICIONES ABIERTAS:"]
        for p in signals['open_positions'][:8]:
            price_str = f" @ ${p['avg_price']}" if p.get('avg_price') else ''
            ctx.append(f"  {p['ticker']}{price_str}")

    prompt = (
        "Genera el briefing matutino basado en estos datos:\n\n"
        + '\n'.join(ctx)
        + "\n\nEstructura (breve, max 400 palabras):\n"
        "1. 📊 Estado del mercado (1 línea)\n"
        "2. ⚠️ Alertas críticas (solo si hay conflictos — si no, omitir)\n"
        "3. 🎯 Top 3 entradas del día con justificación concreta\n"
        "4. 💼 Mis posiciones: algo que hacer hoy (solo si aplica)\n"
        "Sé directo. Si no hay nada claro que hacer, dilo explícitamente."
    )

    try:
        r = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {GROQ_API_KEY}', 'Content-Type': 'application/json'},
            json={
                'model': GROQ_MODEL,
                'messages': [
                    {'role': 'system', 'content': ANALYST_SYSTEM},
                    {'role': 'user',   'content': prompt},
                ],
                'temperature': 0.25,
                'max_tokens':  700,
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f'[financial_agent] Groq error: {e}')
        return None


# ── Telegram briefing ─────────────────────────────────────────────────────────

def send_briefing(signals: dict, conviction: list[dict], cross: dict,
                  narrative: Optional[str]) -> None:
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M ET')
    regime  = signals.get('market_regime', '?')
    vix     = signals.get('vix')
    vix_str = f'VIX {vix:.1f}' if vix else 'VIX ?'

    regime_icon = '📈' if regime == 'ALCISTA' else '📉' if regime == 'BAJISTA' else '⚠️'

    header = (
        f"🧠 <b>Briefing — {now_str}</b>\n"
        f"{regime_icon} {regime} | {vix_str}\n"
        f"{'━'*28}\n\n"
    )

    # ── Conflicts ─────────────────────────────────────────────────────────────
    conflict_text = ''
    if cross['conflicts']:
        lines = ['⚠️ <b>CONFLICTOS — Revisar antes de entrar:</b>']
        for c in cross['conflicts'][:3]:
            icon = '🔴' if c['severity'] == 'HIGH' else '🟡'
            lines.append(f"{icon} <b>{c['ticker']}</b>: {c['reason']}")
        conflict_text = '\n'.join(lines) + '\n\n'

    # ── Confirmations ─────────────────────────────────────────────────────────
    confirm_text = ''
    if cross['confirmations']:
        lines = ['✅ <b>Confirmaciones (Value + Flow):</b>']
        for c in cross['confirmations'][:3]:
            lines.append(f"💎 <b>{c['ticker']}</b>: {c['reason']}")
        confirm_text = '\n'.join(lines) + '\n\n'

    # ── Top conviction picks ──────────────────────────────────────────────────
    top = [c for c in conviction[:8] if not c['conflict']]
    picks_text = ''
    if top:
        lines = [f"🎯 <b>Top {min(len(top), 5)} por conviction:</b>"]
        for c in top[:5]:
            flags    = '+'.join(c['signals'])
            grade    = c['grade'] or ''
            upside   = f" ↑{c['upside']:.0f}%" if c['upside'] else ''
            open_tag = ' <i>(en cartera)</i>' if c['open'] else ''
            notes    = f" — {'; '.join(c['notes'])}" if c['notes'] else ''
            lines.append(
                f"  <code>{c['ticker']}</code> [{flags}] {grade}{upside}{open_tag}{notes}"
            )
        picks_text = '\n'.join(lines) + '\n\n'

    # ── Big flow outside universe ─────────────────────────────────────────────
    big_flow_text = ''
    if cross['big_alerts']:
        lines = ['💰 <b>Flujo grande fuera del universo:</b>']
        for a in cross['big_alerts'][:3]:
            icon = '🟢' if a['signal'] == 'BULLISH' else '🔴'
            lines.append(f"{icon} <b>{a['ticker']}</b> ${a['premium']/1e6:.1f}M")
        big_flow_text = '\n'.join(lines) + '\n\n'

    # ── AI narrative ──────────────────────────────────────────────────────────
    ai_text = ''
    if narrative:
        ai_text = f"🤖 <b>Análisis:</b>\n{narrative}"
    elif not top and not cross['conflicts']:
        ai_text = '<i>Sin oportunidades de alta conviction hoy.</i>'

    full_msg = header + conflict_text + confirm_text + picks_text + big_flow_text + ai_text

    if len(full_msg) > 4000:
        full_msg = full_msg[:3980] + '\n<i>... (truncado)</i>'

    _tg(full_msg)


def send_flow_conflict_alert(cross: dict) -> None:
    if not cross['conflicts']:
        return
    lines = ['⚠️ <b>ALERTA FLOW: Conflicto detectado</b>']
    for c in cross['conflicts']:
        icon = '🔴' if c['severity'] == 'HIGH' else '🟡'
        lines.append(f"{icon} <b>{c['ticker']}</b>: {c['reason']}")
    _tg('\n'.join(lines))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Financial Expert Agent')
    parser.add_argument('--flow-only',   action='store_true', help='Solo alertas de conflicto de flow')
    parser.add_argument('--no-groq',     action='store_true', help='Sin análisis IA')
    parser.add_argument('--no-telegram', action='store_true', help='Solo output local')
    args = parser.parse_args()

    if args.no_telegram:
        global BOT_TOKEN, CHAT_ID
        BOT_TOKEN = ''
        CHAT_ID = ''

    print(f'\n{"="*60}')
    print(f'🧠 FINANCIAL AGENT — {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print(f'{"="*60}')

    # 1. Cargar signals + posiciones
    print('\n📊 [1/3] Cargando signals...')
    signals = load_all_signals()
    print(f'   Bounce: {len(signals["bounce"])} | Value US: {len(signals["value_us"])} | EU: {len(signals["value_eu"])}')
    print(f'   Flow: {len(signals["unusual_flow"])} | Posiciones: {len(signals["open_positions"])}')
    print(f'   VIX: {signals.get("vix")} | Régimen: {signals.get("market_regime")}')

    # 2. Cross-signals + conviction scoring
    print('\n🔍 [2/3] Analizando conviction y conflictos...')
    cross      = detect_crosssignals(signals)
    conviction = score_conviction(signals)

    if cross['conflicts']:
        print(f'   ⚠️ Conflictos: {len(cross["conflicts"])}')
        for c in cross['conflicts']:
            print(f'      {c["ticker"]}: {c["reason"]}')
    if cross['confirmations']:
        print(f'   ✅ Confirmaciones: {len(cross["confirmations"])}')

    top3 = [c for c in conviction[:3] if not c['conflict']]
    for c in top3:
        print(f'   🎯 {c["ticker"]}: {"+".join(c["signals"])} grade={c["grade"]}')

    if args.flow_only:
        send_flow_conflict_alert(cross)
        print('\n✅ Modo --flow-only completado')
        return

    # 3. Groq
    narrative = None
    if not args.no_groq and GROQ_API_KEY:
        print('\n🤖 [3/3] Generando análisis con Groq...')
        narrative = groq_briefing(signals, conviction, cross)
        if narrative:
            print(f'   Análisis generado ({len(narrative)} chars)')

    send_briefing(signals, conviction, cross, narrative)

    print(f'\n{"="*60}')
    print('✅ Financial Agent completado')
    print(f'{"="*60}\n')


if __name__ == '__main__':
    main()
