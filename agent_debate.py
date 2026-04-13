#!/usr/bin/env python3
"""
MULTI-AGENT DEBATE SYSTEM
4 agentes especializados analizan un ticker en paralelo y debaten.
Cada agente tiene su perspectiva y busca activamente fallos en los otros.
El árbitro sintetiza y da un veredicto final ponderado.

Uso standalone:  python3 agent_debate.py AAPL
Uso Telegram:    /debate AAPL  (desde agent_monitor.py)

Agentes:
  FundamentalAgent  — balance, FCF, ROE, márgenes, deuda
  MacroAgent        — ciclo económico, sector, tipos, divisa
  TechnicalAgent    — RSI, soportes, momentum, options flow
  DevilsAdvocate    — busca activamente por qué la tesis falla

Variables de entorno: GROQ_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import csv
import io
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests

PAGES_BASE   = 'https://tantancansado.github.io/stock_analyzer_a'
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
BOT_TOKEN    = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID      = os.environ.get('TELEGRAM_CHAT_ID', '')

# Scout para los 4 agentes (rápido, paralelo); Maverick para el árbitro
MODEL_AGENT  = 'meta-llama/llama-4-scout-17b-16e-instruct'
MODEL_JUDGE  = 'meta-llama/llama-4-scout-17b-16e-instruct'

EMOJI = {
    'fundamental': '📊',
    'macro':       '🌍',
    'technical':   '📈',
    'devil':       '😈',
    'judge':       '⚖️',
}


# ── Data gathering ─────────────────────────────────────────────────────────────

def _get(url: str, as_json=False, timeout=12):
    try:
        r = requests.get(url, timeout=timeout,
                         headers={'User-Agent': 'StockAnalyzer/2.0'})
        if r.status_code != 200:
            return None
        return r.json() if as_json else r.text
    except Exception:
        return None


def gather_context(ticker: str) -> dict:
    """Recoge todos los datos disponibles para el ticker."""
    ctx: dict = {'ticker': ticker}

    # Fundamental scores
    text = _get(f'{PAGES_BASE}/fundamental_scores.csv')
    if text:
        for row in csv.DictReader(io.StringIO(text)):
            if row.get('ticker', '').upper() == ticker.upper():
                ctx.update({k: v for k, v in row.items() if v})
                break

    # Value opportunities US
    for fname in ('value_opportunities_filtered.csv',
                  'european_value_opportunities_filtered.csv'):
        text = _get(f'{PAGES_BASE}/{fname}')
        if text:
            for row in csv.DictReader(io.StringIO(text)):
                if row.get('ticker', '').upper() == ticker.upper():
                    ctx['in_value_list'] = fname
                    ctx['value_grade']   = row.get('grade', '')
                    break

    # Mean reversion / bounce
    mr = _get(f'{PAGES_BASE}/mean_reversion_opportunities.json',
              as_json=True)
    if mr:
        ctx['market_regime'] = mr.get('market_regime', '')
        for o in mr.get('opportunities', []):
            if str(o.get('ticker', '')).upper() == ticker.upper():
                ctx['rsi']              = o.get('rsi')
                ctx['bounce_confidence']= o.get('bounce_confidence')
                ctx['dark_pool']        = o.get('dark_pool_signal')
                ctx['support_distance'] = o.get('distance_to_support_pct')
                ctx['vix']              = o.get('vix')
                ctx['conviction_tier']  = o.get('conviction_tier')
                break
        if 'vix' not in ctx:
            ops = mr.get('opportunities', [])
            ctx['vix'] = next((o.get('vix') for o in ops if o.get('vix')), None)
            ctx['market_regime'] = mr.get('market_regime') or (
                ops[0].get('market_regime') if ops else None)

    # Portfolio history
    text = _get(f'{PAGES_BASE}/portfolio_tracker/recommendations.csv')
    if text:
        returns = []
        for row in csv.DictReader(io.StringIO(text)):
            if row.get('ticker', '').upper() == ticker.upper():
                for col in ('return_7d', 'return_14d', 'return_30d'):
                    if row.get(col):
                        try: returns.append((col, float(row[col])))
                        except: pass
        if returns:
            ctx['past_signals'] = returns

    return ctx


# ── Individual agents ──────────────────────────────────────────────────────────

AGENT_PROMPTS = {
    'fundamental': """Eres un analista VALUE fundamental estilo Buffett.
Analiza SOLO los aspectos fundamentales de {ticker}.

Datos disponibles:
{context}

Evalúa: FCF yield, ROE, márgenes, deuda/equity, interest coverage, payout ratio.
Da tu veredicto: BUY / WATCH / AVOID con una puntuación de convicción 1-10.
Máximo 120 palabras. Sé directo y específico con los números.""",

    'macro': """Eres un macro analyst especializado en ciclos económicos y rotación sectorial.
Analiza el contexto MACRO para {ticker}.

Datos disponibles:
{context}

Evalúa: sector (¿favorable en el ciclo actual?), régimen de mercado, VIX, tipos de interés implícitos.
Si el ticker es europeo, considera EUR/USD y política BCE.
Da tu veredicto: FAVORABLE / NEUTRAL / DESFAVORABLE con puntuación 1-10.
Máximo 120 palabras.""",

    'technical': """Eres un analista técnico especializado en mean reversion y momentum.
Analiza la situación TÉCNICA de {ticker}.

Datos disponibles:
{context}

Evalúa: RSI, distancia a soportes, dark pool signals, bounce confidence, conviction tier.
¿Está en zona de entrada técnica o en territorio de riesgo?
Da tu veredicto: COMPRA TÉCNICA / ESPERAR / EVITAR con puntuación 1-10.
Máximo 120 palabras.""",

    'devil': """Eres el Devil's Advocate. Tu trabajo es encontrar POR QUÉ la inversión en {ticker} puede FALLAR.
No puedes decir que todo está bien. Debes encontrar al menos 2 riesgos reales.

Datos disponibles:
{context}

Busca: trampas de valor, deuda oculta, sector en declive, riesgo earnings, insiders vendiendo,
señales técnicas contradictorias, riesgo macro específico.
Da tu nivel de preocupación: ALTO / MEDIO / BAJO con puntuación 1-10 (10 = muy preocupante).
Máximo 120 palabras.""",
}

JUDGE_PROMPT = """Eres el árbitro de un debate de inversión. 4 analistas han dado su opinión sobre {ticker}.

ANÁLISIS FUNDAMENTAL:
{fundamental}

ANÁLISIS MACRO:
{macro}

ANÁLISIS TÉCNICO:
{technical}

DEVIL'S ADVOCATE (riesgos):
{devil}

Sintetiza el debate y da el VEREDICTO FINAL en este formato exacto:

**VEREDICTO:** [BUY / WATCH / AVOID]
**CONVICCIÓN:** [X/10]
**CONSENSO:** [Alta / Media / Baja — explica si hay desacuerdo entre agentes]
**TESIS EN UNA LÍNEA:** [máx 20 palabras]
**RIESGO PRINCIPAL:** [máx 15 palabras]
**CONDICIÓN DE ENTRADA:** [qué necesita ocurrir para comprar — si WATCH/AVOID]

Sé directo. Si los agentes no coinciden, el veredicto debe reflejar esa incertidumbre."""


# ── Groq calls ─────────────────────────────────────────────────────────────────

def _groq(prompt: str, model: str, max_tokens: int = 300) -> str:
    if not GROQ_API_KEY:
        return '(sin GROQ_API_KEY)'
    try:
        r = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {GROQ_API_KEY}',
                     'Content-Type': 'application/json'},
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.25,
                'max_tokens': max_tokens,
            },
            timeout=45,
        )
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f'(error: {e})'


def run_agent(agent_name: str, ticker: str, ctx_str: str) -> tuple[str, str]:
    prompt = AGENT_PROMPTS[agent_name].format(ticker=ticker, context=ctx_str)
    result = _groq(prompt, MODEL_AGENT, max_tokens=250)
    return agent_name, result


# ── Telegram ───────────────────────────────────────────────────────────────────

def tg_send(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        print(text)
        return
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        try:
            requests.post(
                f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
                json={'chat_id': CHAT_ID, 'text': chunk, 'parse_mode': 'HTML',
                      'disable_web_page_preview': True},
                timeout=10,
            )
        except Exception:
            pass


# ── Main ───────────────────────────────────────────────────────────────────────

def debate(ticker: str, send_telegram: bool = True) -> str:
    ticker = ticker.strip().upper()
    now = datetime.now(timezone.utc).strftime('%d/%m %H:%M UTC')
    print(f'⚖️ Iniciando debate sobre {ticker}...')

    # 1. Gather context
    print('  📥 Recopilando datos...')
    ctx = gather_context(ticker)
    ctx_str = '\n'.join(f'- {k}: {v}' for k, v in ctx.items() if v and k != 'ticker')
    if not ctx_str:
        msg = f'❌ Sin datos para <b>{ticker}</b> en el sistema.'
        if send_telegram:
            tg_send(msg)
        return msg

    # 2. Run 4 agents in parallel
    print('  🧠 4 agentes analizando en paralelo...')
    results: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(run_agent, name, ticker, ctx_str): name
            for name in AGENT_PROMPTS
        }
        for future in as_completed(futures):
            name, text = future.result()
            results[name] = text
            print(f'    ✓ {name}')

    # 3. Judge synthesizes
    print('  ⚖️ Árbitro sintetizando...')
    judge_prompt = JUDGE_PROMPT.format(
        ticker=ticker,
        fundamental=results.get('fundamental', ''),
        macro=results.get('macro', ''),
        technical=results.get('technical', ''),
        devil=results.get('devil', ''),
    )
    verdict = _groq(judge_prompt, MODEL_JUDGE, max_tokens=400)

    # 4. Build message
    def fmt(text: str) -> str:
        """Convert **bold** to HTML bold for Telegram."""
        import re
        return re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

    lines = [
        f'⚖️ <b>Debate: {ticker}</b> · <code>{now}</code>',
        '━━━━━━━━━━━━━━━━━━━━━',
        '',
        f'{EMOJI["fundamental"]} <b>Fundamental</b>',
        fmt(results.get('fundamental', '')),
        '',
        f'{EMOJI["macro"]} <b>Macro</b>',
        fmt(results.get('macro', '')),
        '',
        f'{EMOJI["technical"]} <b>Técnico</b>',
        fmt(results.get('technical', '')),
        '',
        f'{EMOJI["devil"]} <b>Devil\'s Advocate</b>',
        fmt(results.get('devil', '')),
        '',
        '━━━━━━━━━━━━━━━━━━━━━',
        f'{EMOJI["judge"]} <b>VEREDICTO FINAL</b>',
        fmt(verdict),
    ]

    msg = '\n'.join(lines)
    if send_telegram:
        tg_send(msg)
        print(f'✅ Debate enviado para {ticker}')

    return msg


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Uso: python3 agent_debate.py <TICKER>')
        print('Ejemplo: python3 agent_debate.py MSFT')
        sys.exit(1)

    result = debate(sys.argv[1], send_telegram=bool(BOT_TOKEN))
    if not BOT_TOKEN:
        print('\n' + result)
