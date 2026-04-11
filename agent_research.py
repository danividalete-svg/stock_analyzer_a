#!/usr/bin/env python3
"""
AUTONOMOUS RESEARCH AGENT
Dado un ticker, en ~60s genera un informe completo de inversión:
  1. Datos fundamentales de la app (scores, FCF, R/R, earnings)
  2. Último filing SEC EDGAR (10-K / 10-Q) con extracto del texto
  3. Noticias recientes via yfinance
  4. Groq sintetiza todo en una tesis de inversión con pros, contras y riesgo

Uso standalone:  python3 agent_research.py AAPL
Uso Telegram:    /research AAPL  (desde agent_monitor.py)
"""

import csv
import io
import json
import os
import sys
import textwrap
from datetime import datetime, timezone

import requests

PAGES_BASE   = 'https://tantancansado.github.io/stock_analyzer_a'
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
BOT_TOKEN    = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID      = os.environ.get('TELEGRAM_CHAT_ID', '')
GROQ_MODEL   = 'meta-llama/llama-4-maverick-17b-128e-instruct'  # mejor razonamiento
EDGAR_SEARCH = 'https://efts.sec.gov/LATEST/search-index'
EDGAR_BASE   = 'https://www.sec.gov'


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get(url: str, as_json=False, timeout=15, headers=None):
    try:
        h = {'User-Agent': 'StockAnalyzer research@stock-analyzer.bot'}
        if headers:
            h.update(headers)
        r = requests.get(url, timeout=timeout, headers=h)
        if r.status_code != 200:
            return None
        return r.json() if as_json else r.text
    except Exception:
        return None


def _csv_find(filename: str, ticker: str) -> dict | None:
    text = _get(f'{PAGES_BASE}/docs/{filename}')
    if not text:
        return None
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        if row.get('ticker', '').upper() == ticker.upper():
            return row
    return None


def tg_send(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        print(text)
        return
    # Telegram limit 4096 chars — split if needed
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


# ── 1. App data ────────────────────────────────────────────────────────────────

def get_app_data(ticker: str) -> dict:
    """Recoge todos los datos que ya tiene la app sobre este ticker."""
    data = {'ticker': ticker}

    fund = _csv_find('fundamental_scores.csv', ticker)
    if fund:
        data['value_score']          = fund.get('value_score')
        data['fundamental_score']    = fund.get('fundamental_score')
        data['grade']                = fund.get('grade')
        data['sector']               = fund.get('sector')
        data['roe_pct']              = fund.get('roe_pct')
        data['profit_margin_pct']    = fund.get('profit_margin_pct')
        data['debt_to_equity']       = fund.get('debt_to_equity')
        data['fcf_yield_pct']        = fund.get('fcf_yield_pct')
        data['analyst_upside_pct']   = fund.get('analyst_upside_pct')
        data['risk_reward_ratio']    = fund.get('risk_reward_ratio')
        data['dividend_yield_pct']   = fund.get('dividend_yield_pct')
        data['buyback_active']       = fund.get('buyback_active')
        data['earnings_warning']     = fund.get('earnings_warning')
        data['days_to_earnings']     = fund.get('days_to_earnings')
        data['interest_coverage']    = fund.get('interest_coverage')

    # Mean reversion
    mr = _get(f'{PAGES_BASE}/docs/mean_reversion_opportunities.json', as_json=True)
    if mr:
        for o in mr.get('opportunities', []):
            if str(o.get('ticker', '')).upper() == ticker.upper():
                data['rsi']              = o.get('rsi')
                data['bounce_confidence'] = o.get('bounce_confidence')
                data['dark_pool']        = o.get('dark_pool_signal')
                data['conviction_tier']  = o.get('conviction_tier')
                break

    # Portfolio history
    recs_text = _get(f'{PAGES_BASE}/docs/portfolio_tracker/recommendations.csv')
    if recs_text:
        reader = csv.DictReader(io.StringIO(recs_text))
        returns = []
        for row in reader:
            if row.get('ticker', '').upper() == ticker.upper():
                for col in ('return_7d', 'return_14d'):
                    if row.get(col):
                        try: returns.append(float(row[col]))
                        except: pass
        if returns:
            data['historical_returns'] = returns
            data['historical_win_rate'] = round(sum(1 for x in returns if x > 0) / len(returns) * 100, 1)

    return data


# ── 2. SEC EDGAR ───────────────────────────────────────────────────────────────

def get_edgar_filing(ticker: str) -> dict:
    """Busca el último 10-K o 10-Q en SEC EDGAR y extrae un resumen."""
    result = {'found': False}

    # Buscar CIK del ticker
    cik_data = _get(
        f'https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&forms=10-K,10-Q&dateRange=custom&startdt=2024-01-01&hits.hits._source=period_of_report,entity_name,file_date,form_type,biz_location',
        as_json=True
    )
    if not cik_data:
        # Intentar con la API de tickers de EDGAR
        tickers_data = _get('https://www.sec.gov/files/company_tickers.json', as_json=True)
        if tickers_data:
            cik = None
            for item in tickers_data.values():
                if item.get('ticker', '').upper() == ticker.upper():
                    cik = str(item['cik_str']).zfill(10)
                    result['company_name'] = item.get('title', '')
                    break
            if cik:
                filings = _get(
                    f'https://data.sec.gov/submissions/CIK{cik}.json',
                    as_json=True
                )
                if filings:
                    result['company_name'] = filings.get('name', result.get('company_name', ''))
                    recent = filings.get('filings', {}).get('recent', {})
                    forms  = recent.get('form', [])
                    dates  = recent.get('filingDate', [])
                    desc   = recent.get('primaryDocument', [])
                    acc    = recent.get('accessionNumber', [])
                    for i, form in enumerate(forms):
                        if form in ('10-K', '10-Q'):
                            result['found']       = True
                            result['form']        = form
                            result['date']        = dates[i] if i < len(dates) else ''
                            result['accession']   = acc[i].replace('-', '') if i < len(acc) else ''
                            result['document']    = desc[i] if i < len(desc) else ''
                            result['url'] = (
                                f"https://www.sec.gov/Archives/edgar/full-index/"
                                f"{result['date'][:4]}/QTR{(int(result['date'][5:7])-1)//3+1}/"
                            ) if result['date'] else ''
                            break
    return result


# ── 3. Noticias ────────────────────────────────────────────────────────────────

def get_news(ticker: str) -> list[dict]:
    """Obtiene las últimas noticias via yfinance."""
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        news = stock.news or []
        return [
            {
                'title':   n.get('content', {}).get('title', n.get('title', '')),
                'date':    datetime.fromtimestamp(
                    n.get('providerPublishTime', n.get('content', {}).get('pubDate', 0) or 0),
                    tz=timezone.utc
                ).strftime('%Y-%m-%d') if n.get('providerPublishTime') or n.get('content', {}).get('pubDate') else '',
                'source':  n.get('content', {}).get('provider', {}).get('displayName', n.get('publisher', '')),
            }
            for n in news[:8]
        ]
    except Exception:
        return []


# ── 4. Groq synthesis ─────────────────────────────────────────────────────────

RESEARCH_PROMPT = """Eres un analista de inversiones VALUE experto (estilo Lynch/Buffett).
Analiza estos datos de {ticker} y genera un informe de inversión conciso y accionable.

DATOS DE LA APP:
{app_data}

FILINGS SEC:
{edgar_info}

NOTICIAS RECIENTES:
{news_text}

Genera el informe en este formato EXACTO (en español, sin introducción extra):

**TESIS:** [1-2 frases sobre el caso de inversión core]

**✅ PROS:**
• [punto 1]
• [punto 2]
• [punto 3 si existe]

**❌ CONTRAS / RIESGOS:**
• [punto 1]
• [punto 2]
• [punto 3 si existe]

**🎯 VEREDICTO:** [BUY/WATCH/AVOID] — [1 frase de por qué]
Score actual: {score}/100 [{grade}]

Sé directo, específico con los números. Máximo 250 palabras total."""


def groq_synthesize(ticker: str, app_data: dict, edgar: dict, news: list) -> str:
    if not GROQ_API_KEY:
        return '(GROQ_API_KEY no configurado)'

    app_str = '\n'.join(f'- {k}: {v}' for k, v in app_data.items()
                        if v and k != 'ticker')

    edgar_str = (
        f"Último filing: {edgar.get('form', '?')} ({edgar.get('date', '?')}) "
        f"— {edgar.get('company_name', '')}"
        if edgar.get('found') else 'No encontrado en EDGAR (ticker no-US o sin filings recientes)'
    )

    news_str = '\n'.join(
        f'- [{n["date"]}] {n["title"]} ({n["source"]})'
        for n in news
    ) or 'Sin noticias recientes'

    prompt = RESEARCH_PROMPT.format(
        ticker=ticker,
        app_data=app_str or 'Sin datos en la app',
        edgar_info=edgar_str,
        news_text=news_str,
        score=app_data.get('value_score', '?'),
        grade=app_data.get('grade', '?'),
    )

    try:
        r = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {GROQ_API_KEY}',
                     'Content-Type': 'application/json'},
            json={
                'model': GROQ_MODEL,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.2,
                'max_tokens': 700,
            },
            timeout=45,
        )
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f'(Error Groq: {e})'


# ── Main ───────────────────────────────────────────────────────────────────────

def research(ticker: str, send_telegram: bool = True) -> str:
    """
    Función principal. Devuelve el informe como string
    y opcionalmente lo envía por Telegram.
    """
    ticker = ticker.strip().upper()
    print(f'🔍 Researching {ticker}...')

    print('  1/4 App data...')
    app_data = get_app_data(ticker)

    print('  2/4 SEC EDGAR...')
    edgar = get_edgar_filing(ticker)

    print('  3/4 News...')
    news = get_news(ticker)

    print('  4/4 Groq synthesis...')
    analysis = groq_synthesize(ticker, app_data, edgar, news)

    # ── Construir mensaje final ────────────────────────────────────────────────
    now = datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')
    sector = app_data.get('sector', '')
    company = edgar.get('company_name', '')

    header = [
        f'🔬 <b>Research: {ticker}</b>',
        f'<i>{company or sector}</i>' if (company or sector) else '',
        f'<code>{now}</code>',
        '━━━━━━━━━━━━━━━━━━━━━',
    ]

    # Datos clave en una línea
    kpis = []
    if app_data.get('value_score'):
        kpis.append(f'Score: <b>{app_data["value_score"]}</b> [{app_data.get("grade","")}]')
    if app_data.get('analyst_upside_pct'):
        kpis.append(f'Upside: {app_data["analyst_upside_pct"]}%')
    if app_data.get('fcf_yield_pct'):
        kpis.append(f'FCF: {app_data["fcf_yield_pct"]}%')
    if app_data.get('risk_reward_ratio'):
        kpis.append(f'R/R: {app_data["risk_reward_ratio"]}x')
    if kpis:
        header.append(' · '.join(kpis))

    if app_data.get('earnings_warning') == 'True':
        header.append('⚠️ <b>Earnings en &lt;7 días</b>')

    if edgar.get('found'):
        header.append(f'📄 Último filing: {edgar["form"]} ({edgar["date"]})')

    news_lines = []
    if news:
        news_lines = ['\n<b>Noticias:</b>']
        for n in news[:4]:
            title = n['title'][:80] + ('…' if len(n['title']) > 80 else '')
            news_lines.append(f'  · <i>{n["date"]}</i> {title}')

    msg = '\n'.join([l for l in header if l]) + '\n\n' + \
          analysis.replace('**', '<b>', 1).replace('**', '</b>', 1) \
                  .replace('**', '<b>').replace('**', '</b>') + \
          '\n'.join(news_lines)

    # Limpiar markdown que no soporta HTML de Telegram
    msg = msg.replace('**', '<b>').replace('**', '</b>')

    if send_telegram:
        tg_send(msg)
        print(f'✅ Research report enviado para {ticker}')

    return msg


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Uso: python3 agent_research.py <TICKER>')
        print('Ejemplo: python3 agent_research.py AAPL')
        sys.exit(1)

    ticker_arg = sys.argv[1]
    result = research(ticker_arg, send_telegram=bool(BOT_TOKEN))
    if not BOT_TOKEN:
        print('\n' + result)
