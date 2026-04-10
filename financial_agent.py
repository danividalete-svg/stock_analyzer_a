#!/usr/bin/env python3
"""
FINANCIAL EXPERT AGENT — Agente Analista Financiero Autónomo
Nivel 2: Briefing matutino + detección de conflictos + noticias

Corre cada mañana a las 8:30 ET (antes de la apertura) y opcionalmente
tras cada scan intraday de unusual flow.

Flujo:
  1. Recoge todos los signals activos (bounce, value, unusual flow)
  2. Busca noticias recientes para los top picks (Yahoo Finance)
  3. Detecta conflictos: PUT sweep en ticker con bounce recommendation
  4. Detecta confirmaciones: CALL sweep + VALUE pick = alta convicción
  5. Usa Groq para generar análisis narrativo
  6. Envía briefing estructurado a Telegram

Variables de entorno:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  GROQ_API_KEY

Uso:
  python3 financial_agent.py              # briefing completo
  python3 financial_agent.py --flow-only  # solo alertas de flow nuevo
  python3 financial_agent.py --ticker SPY # análisis de ticker específico
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import requests
import yfinance as yf

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN    = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID      = os.environ.get('TELEGRAM_CHAT_ID', '')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GITHUB_PAGES = 'https://raw.githubusercontent.com/tantancansado/stock_analyzer_a/main/docs'

GROQ_MODEL   = 'meta-llama/llama-4-scout-17b-16e-instruct'
DOCS         = Path('docs')

# ── Telegram ──────────────────────────────────────────────────────────────────

def _tg(text: str, parse_mode: str = 'HTML') -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print(text)
        return
    try:
        requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            data={'chat_id': CHAT_ID, 'text': text, 'parse_mode': parse_mode,
                  'disable_web_page_preview': 'true'},
            timeout=10,
        )
    except Exception:
        pass


# ── Data loaders ──────────────────────────────────────────────────────────────

def _load_json(filename: str) -> Optional[dict]:
    """Carga JSON desde docs/ local (GitHub Actions) o GitHub Pages (Railway)."""
    local = DOCS / filename
    if local.exists():
        try:
            return json.loads(local.read_text())
        except Exception:
            pass
    # Fallback: GitHub Pages
    try:
        r = requests.get(f'{GITHUB_PAGES}/{filename}', timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _load_csv_tickers(filename: str, score_col: str = 'value_score', n: int = 20) -> list[dict]:
    """Carga los top N tickers de un CSV por score."""
    local = DOCS / filename
    if not local.exists():
        return []
    try:
        import pandas as pd
        df = pd.read_csv(local)
        if score_col in df.columns:
            df = df.sort_values(score_col, ascending=False)
        ticker_col = 'ticker' if 'ticker' in df.columns else df.columns[0]
        return df.head(n).to_dict('records')
    except Exception:
        return []


# ── News ──────────────────────────────────────────────────────────────────────

def get_ticker_news(ticker: str, max_items: int = 3) -> list[dict]:
    """Obtiene noticias recientes de Yahoo Finance para un ticker."""
    try:
        t = yf.Ticker(ticker)
        raw_news = t.news or []
        result = []
        for item in raw_news[:max_items * 2]:
            content = item.get('content', {})
            title   = content.get('title', '')
            summary = content.get('summary', '')
            pub_str = content.get('pubDate', '')
            provider = (content.get('provider') or {}).get('displayName', '')
            if not title:
                continue
            # Parsear fecha
            pub_dt = None
            if pub_str:
                try:
                    pub_dt = datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
                except Exception:
                    pass
            # Solo noticias de las últimas 48h
            if pub_dt:
                age_h = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600
                if age_h > 48:
                    continue
            result.append({
                'title':    title,
                'summary':  summary[:200] if summary else '',
                'pub_date': pub_str[:10] if pub_str else '',
                'provider': provider,
            })
            if len(result) >= max_items:
                break
        return result
    except Exception:
        return []


# ── Signal loading ────────────────────────────────────────────────────────────

def load_all_signals() -> dict:
    """Carga todos los signals activos del sistema."""
    signals = {
        'bounce': [],
        'value_us': [],
        'value_eu': [],
        'unusual_flow': [],
        'market_regime': None,
        'vix': None,
    }

    # ── Bounce setups ─────────────────────────────────────────────────────────
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
        # Filtrar solo Oversold Bounce que pasa los filtros de calidad
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
                })

    # ── Value picks (top 10 por score) ────────────────────────────────────────
    for path, key in [('value_opportunities_filtered.csv', 'value_us'),
                      ('european_value_opportunities_filtered.csv', 'value_eu')]:
        rows = _load_csv_tickers(path, 'value_score', 10)
        for r in rows:
            ticker = str(r.get('ticker', '')).strip()
            score  = r.get('value_score') or r.get('score', 0)
            grade  = r.get('grade', '')
            sector = r.get('sector', '')
            if ticker:
                signals[key].append({
                    'ticker': ticker, 'score': score,
                    'grade': grade, 'sector': sector,
                })

    # ── Unusual flow (últimas 2h) ─────────────────────────────────────────────
    uf = _load_json('unusual_flow.json')
    if uf:
        scan_str = uf.get('scan_date', '')
        scan_dt  = None
        if scan_str:
            try:
                scan_dt = datetime.fromisoformat(scan_str.replace('Z', '+00:00'))
            except Exception:
                pass
        results = uf.get('results', [])
        # Solo tickers con premium significativo
        for r in results:
            if r.get('total_premium', 0) < 50_000:
                continue
            # Solo flows frescos (últimas 4h) si tenemos fecha
            if scan_dt:
                age_h = (datetime.now(timezone.utc) - scan_dt).total_seconds() / 3600
                if age_h > 4:
                    continue
            signals['unusual_flow'].append({
                'ticker':  r['ticker'],
                'signal':  r['signal'],
                'call_pct': r.get('call_pct', 50),
                'premium': r.get('total_premium', 0),
                'score':   r.get('unusual_score', 0),
                'sweeps':  [c for c in r.get('top_contracts', []) if c.get('speculative')],
            })

    return signals


# ── Cross-signal analysis ─────────────────────────────────────────────────────

def detect_crosssignals(signals: dict) -> dict:
    """Detecta conflictos y confirmaciones entre signals."""
    bounce_tickers  = {s['ticker'] for s in signals['bounce']}
    value_tickers   = {s['ticker'] for s in signals['value_us'] + signals['value_eu']}
    flow_by_ticker  = {s['ticker']: s for s in signals['unusual_flow']}

    conflicts     = []   # PUT flow en ticker que tenemos como bounce/value
    confirmations = []   # CALL flow en ticker que tenemos como value pick
    alerts        = []   # flujo muy grande sin otro signal

    for ticker, flow in flow_by_ticker.items():
        prem = flow['premium']
        sig  = flow['signal']
        call_pct = flow.get('call_pct', 50)

        in_bounce = ticker in bounce_tickers
        in_value  = ticker in value_tickers

        if sig == 'BEARISH' and call_pct < 30:
            if in_bounce or in_value:
                reason = 'bounce' if in_bounce else 'value pick'
                conflicts.append({
                    'ticker':  ticker,
                    'reason':  f'{reason} con PUT sweep (${prem/1e6:.1f}M)',
                    'premium': prem,
                    'call_pct': call_pct,
                    'severity': 'HIGH' if prem > 100_000 else 'MEDIUM',
                })

        if sig == 'BULLISH' and call_pct > 70:
            if in_value:
                confirmations.append({
                    'ticker':  ticker,
                    'reason':  f'VALUE + CALL sweep (${prem/1e6:.1f}M)',
                    'premium': prem,
                    'call_pct': call_pct,
                })

        if prem > 500_000 and not in_bounce and not in_value:
            alerts.append({
                'ticker':  ticker,
                'signal':  sig,
                'premium': prem,
                'reason':  f'Flujo grande (${prem/1e6:.1f}M) — no en nuestro universo',
            })

    return {
        'conflicts':     sorted(conflicts,     key=lambda x: -x['premium']),
        'confirmations': sorted(confirmations, key=lambda x: -x['premium']),
        'alerts':        sorted(alerts,        key=lambda x: -x['premium'])[:5],
    }


# ── News for top tickers ──────────────────────────────────────────────────────

def gather_top_news(signals: dict) -> dict[str, list]:
    """Busca noticias para los tickers más relevantes."""
    # Prioridad: conflictos + bounce + top value
    priority = set()
    for s in signals['bounce'][:5]:
        priority.add(s['ticker'])
    for s in signals['value_us'][:5]:
        priority.add(s['ticker'])
    for f in signals['unusual_flow'][:5]:
        priority.add(f['ticker'])

    news = {}
    for ticker in list(priority)[:12]:
        items = get_ticker_news(ticker, max_items=2)
        if items:
            news[ticker] = items
        time.sleep(0.2)
    return news


# ── Groq analysis ─────────────────────────────────────────────────────────────

ANALYST_SYSTEM = """Eres un analista financiero experto en trading de acciones US/EU.
Tu rol es generar briefings matutinos concisos y accionables.
Analiza los signals del sistema y genera insights relevantes.

REGLAS:
- Sé directo y conciso (máximo 800 tokens de output)
- Prioriza conflictos (PUT sweeps en nuestros picks) — son alertas de riesgo
- Las confirmaciones (CALL sweeps + VALUE) aumentan convicción
- Menciona noticias relevantes que expliquen el flujo inusual
- Si el VIX > 30, tono cauteloso; si < 20, tono constructivo
- NO inventar datos que no estén en el contexto
- Formato: HTML de Telegram (<b>, <i>, solo eso)"""

def groq_briefing(signals: dict, cross: dict, news: dict[str, list]) -> Optional[str]:
    """Genera el briefing con Groq."""
    if not GROQ_API_KEY:
        return None

    # Construir contexto compacto
    ctx_parts = [
        f"FECHA: {datetime.now().strftime('%Y-%m-%d %H:%M ET')}",
        f"MERCADO: {signals.get('market_regime','?')} | VIX: {signals.get('vix','?')}",
        "",
        f"BOUNCE SETUPS ({len(signals['bounce'])}):",
        *[f"  {s['ticker']}: RSI={s['rsi']:.0f}, conf={s['conf']}%, DP={s['dp']}, tier={s['tier']}" for s in signals['bounce'][:6]],
        "",
        f"VALUE PICKS US ({len(signals['value_us'])}):",
        *[f"  {s['ticker']}: score={s['score']}, {s['grade']}, {s['sector']}" for s in signals['value_us'][:5]],
        "",
        f"UNUSUAL FLOW ({len(signals['unusual_flow'])} tickers activos):",
        *[f"  {f['ticker']}: {f['signal']} ${f['premium']/1e3:.0f}K calls={f['call_pct']:.0f}%" for f in signals['unusual_flow'][:8]],
    ]

    if cross['conflicts']:
        ctx_parts += ["", "⚠️ CONFLICTOS DETECTADOS:"]
        for c in cross['conflicts']:
            ctx_parts.append(f"  {c['ticker']}: {c['reason']} [{c['severity']}]")

    if cross['confirmations']:
        ctx_parts += ["", "✅ CONFIRMACIONES (VALUE + CALL flow):"]
        for c in cross['confirmations']:
            ctx_parts.append(f"  {c['ticker']}: {c['reason']}")

    if cross['alerts']:
        ctx_parts += ["", "🔔 FLUJO GRANDE SIN SETUP:"]
        for a in cross['alerts']:
            ctx_parts.append(f"  {a['ticker']}: {a['signal']} ${a['premium']/1e6:.1f}M")

    if news:
        ctx_parts += ["", "NOTICIAS RECIENTES:"]
        for ticker, items in list(news.items())[:6]:
            for n in items[:1]:
                ctx_parts.append(f"  [{ticker}] {n['title']} ({n['pub_date']})")

    context = '\n'.join(ctx_parts)

    prompt = f"""Genera el briefing matutino basado en estos datos del sistema:

{context}

Estructura el briefing con estas secciones (usa emojis y HTML de Telegram):
1. 📊 Estado del mercado (1-2 líneas)
2. ⚠️ Alertas críticas (solo si hay conflictos serios — si no, omitir)
3. 🎯 Oportunidades del día (bounce + value con convicción)
4. 💡 Insights del flow inusual (qué está apostando el dinero grande)
5. 📰 Noticias clave que mueven los picks (si hay)

Sé directo. Máximo 600 palabras."""

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
                'temperature': 0.3,
                'max_tokens':  900,
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f'[financial_agent] Groq error: {e}')
        return None


# ── Telegram briefing ─────────────────────────────────────────────────────────

def send_briefing(signals: dict, cross: dict, narrative: Optional[str]) -> None:
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M ET')

    # ── Header ────────────────────────────────────────────────────────────────
    regime = signals.get('market_regime', '?')
    vix    = signals.get('vix')
    vix_str = f'VIX {vix:.1f}' if vix else ''
    regime_icon = '📈' if regime == 'ALCISTA' else '📉' if regime == 'BAJISTA' else '⚠️'

    header = (
        f"🧠 <b>Financial Agent — Briefing Matutino</b>\n"
        f"{regime_icon} {regime} | {vix_str} | {now_str}\n"
        f"{'━'*30}\n"
    )

    # ── Conflicts (most important) ─────────────────────────────────────────────
    conflict_text = ''
    if cross['conflicts']:
        lines = ['⚠️ <b>CONFLICTOS — Revisar antes de entrar:</b>']
        for c in cross['conflicts'][:3]:
            sev = '🔴' if c['severity'] == 'HIGH' else '🟡'
            lines.append(f"{sev} <b>{c['ticker']}</b>: {c['reason']}")
        conflict_text = '\n'.join(lines) + '\n\n'

    # ── Confirmations ─────────────────────────────────────────────────────────
    confirm_text = ''
    if cross['confirmations']:
        lines = ['✅ <b>ALTA CONVICCIÓN (Value + Call Flow):</b>']
        for c in cross['confirmations'][:3]:
            lines.append(f"💎 <b>{c['ticker']}</b>: {c['reason']}")
        confirm_text = '\n'.join(lines) + '\n\n'

    # ── Bounce setups ─────────────────────────────────────────────────────────
    bounce_text = ''
    if signals['bounce']:
        lines = [f"🎯 <b>Bounce Setups ({len(signals['bounce'])}):</b>"]
        for s in signals['bounce'][:5]:
            tier_icon = '💎' if s['tier'] == 2 else '📊'
            dp_icon   = '🟢' if s['dp'] == 'ACCUMULATION' else '🔴' if s['dp'] == 'DISTRIBUTION' else '⚪'
            lines.append(
                f"{tier_icon} <b>{s['ticker']}</b> RSI={s['rsi']:.0f} "
                f"conf={s['conf']}% {dp_icon}DP"
            )
        bounce_text = '\n'.join(lines) + '\n\n'

    # ── Big flow alerts ────────────────────────────────────────────────────────
    flow_text = ''
    big_flows = [f for f in signals['unusual_flow'] if f['premium'] > 100_000]
    if big_flows:
        lines = [f"💰 <b>Flujo Inusual Grande:</b>"]
        for f in big_flows[:5]:
            sig_icon  = '🟢' if f['signal'] == 'BULLISH' else '🔴' if f['signal'] == 'BEARISH' else '⚪'
            sweep_str = f" ⚡{len(f['sweeps'])} sweeps" if f['sweeps'] else ''
            lines.append(
                f"{sig_icon} <b>{f['ticker']}</b> ${f['premium']/1e3:.0f}K "
                f"| calls {f['call_pct']:.0f}%{sweep_str}"
            )
        flow_text = '\n'.join(lines) + '\n\n'

    # ── AI narrative ──────────────────────────────────────────────────────────
    ai_text = ''
    if narrative:
        ai_text = f"🤖 <b>Análisis IA:</b>\n{narrative}\n"

    full_msg = header + conflict_text + confirm_text + bounce_text + flow_text + ai_text

    # Telegram max 4096 chars
    if len(full_msg) > 4000:
        full_msg = full_msg[:3980] + '\n<i>... (truncado)</i>'

    _tg(full_msg)


# ── Conflict-only alert (triggered after flow scan) ───────────────────────────

def send_flow_conflict_alert(cross: dict) -> None:
    """Alerta rápida si aparece un conflicto en el flow intraday."""
    if not cross['conflicts']:
        return
    lines = ['⚠️ <b>ALERTA FLOW: Conflicto detectado</b>']
    for c in cross['conflicts']:
        sev_icon = '🔴' if c['severity'] == 'HIGH' else '🟡'
        lines.append(f"{sev_icon} <b>{c['ticker']}</b>: {c['reason']}")
    _tg('\n'.join(lines))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Financial Expert Agent')
    parser.add_argument('--flow-only',  action='store_true', help='Solo alertas de conflicto de flow')
    parser.add_argument('--ticker',     type=str, help='Análisis de ticker específico')
    parser.add_argument('--no-groq',    action='store_true', help='Sin análisis IA')
    parser.add_argument('--no-telegram', action='store_true', help='Solo output local')
    args = parser.parse_args()

    if args.no_telegram:
        global BOT_TOKEN, CHAT_ID
        BOT_TOKEN = ''
        CHAT_ID = ''

    print(f'\n{"="*60}')
    print(f'🧠 FINANCIAL EXPERT AGENT — {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print(f'{"="*60}')

    # 1. Cargar signals
    print('\n📊 [1/4] Cargando signals...')
    signals = load_all_signals()
    print(f'   Bounce: {len(signals["bounce"])} | Value US: {len(signals["value_us"])} | Value EU: {len(signals["value_eu"])}')
    print(f'   Unusual flow: {len(signals["unusual_flow"])} | VIX: {signals.get("vix")} | Régimen: {signals.get("market_regime")}')

    # 2. Cross-signal analysis
    print('\n🔍 [2/4] Detectando conflictos y confirmaciones...')
    cross = detect_crosssignals(signals)
    if cross['conflicts']:
        print(f'   ⚠️ Conflictos: {len(cross["conflicts"])}')
        for c in cross['conflicts']:
            print(f'      {c["ticker"]}: {c["reason"]} [{c["severity"]}]')
    if cross['confirmations']:
        print(f'   ✅ Confirmaciones: {len(cross["confirmations"])}')
        for c in cross['confirmations']:
            print(f'      {c["ticker"]}: {c["reason"]}')
    if not cross['conflicts'] and not cross['confirmations']:
        print('   Sin conflictos ni confirmaciones destacables')

    if args.flow_only:
        send_flow_conflict_alert(cross)
        print('\n✅ Modo --flow-only completado')
        return

    # 3. Noticias
    print('\n📰 [3/4] Buscando noticias para top picks...')
    news = gather_top_news(signals)
    print(f'   Noticias encontradas para {len(news)} tickers')
    for ticker, items in list(news.items())[:3]:
        for n in items[:1]:
            print(f'   [{ticker}] {n["title"][:60]}...')

    # 4. Groq analysis
    narrative = None
    if not args.no_groq:
        print('\n🤖 [4/4] Generando análisis con Groq...')
        narrative = groq_briefing(signals, cross, news)
        if narrative:
            print(f'   Análisis generado ({len(narrative)} chars)')

    # 5. Enviar briefing
    send_briefing(signals, cross, narrative)
    print(f'\n{"="*60}')
    print('✅ Financial Agent completado')
    print(f'{"="*60}\n')


if __name__ == '__main__':
    main()
