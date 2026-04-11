#!/usr/bin/env python3
"""
AGENT ASK — RAG sobre filings SEC + datos del sistema
Dado un ticker y una pregunta en lenguaje natural, extrae el texto relevante
del último 10-K/10-Q (EDGAR) y lo combina con datos de la app para responder.

Uso Telegram: /ask AAPL ¿Cuánto deuda tiene y cuál es el riesgo principal?
Uso standalone: python3 agent_ask.py AAPL "¿Cómo está el balance?"
"""

import csv
import io
import os
import re
import sys
from datetime import datetime, timezone

import requests

PAGES_BASE   = 'https://tantancansado.github.io/stock_analyzer_a'
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
BOT_TOKEN    = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID      = os.environ.get('TELEGRAM_CHAT_ID', '')
GROQ_MODEL   = 'meta-llama/llama-4-maverick-17b-128e-instruct'

MAX_CHUNK_CHARS = 6000   # chars de filing text enviados a Groq
EDGAR_UA        = 'StockAnalyzer research@stock-analyzer.bot'


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get(url: str, as_json=False, timeout=20, headers=None):
    try:
        h = {'User-Agent': EDGAR_UA}
        if headers:
            h.update(headers)
        r = requests.get(url, timeout=timeout, headers=h)
        if r.status_code != 200:
            return None
        return r.json() if as_json else r.text
    except Exception:
        return None


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


# ── 1. Find filing on EDGAR ────────────────────────────────────────────────────

def _find_filing(ticker: str) -> dict:
    """Returns {cik, accession, form, date, company_name} or empty dict."""
    tickers_data = _get('https://www.sec.gov/files/company_tickers.json', as_json=True)
    if not tickers_data:
        return {}

    cik = None
    company = ''
    for item in tickers_data.values():
        if item.get('ticker', '').upper() == ticker.upper():
            cik = str(item['cik_str']).zfill(10)
            company = item.get('title', '')
            break
    if not cik:
        return {}

    filings = _get(f'https://data.sec.gov/submissions/CIK{cik}.json', as_json=True)
    if not filings:
        return {}

    recent = filings.get('filings', {}).get('recent', {})
    forms  = recent.get('form', [])
    dates  = recent.get('filingDate', [])
    accs   = recent.get('accessionNumber', [])
    docs   = recent.get('primaryDocument', [])

    for i, form in enumerate(forms):
        if form in ('10-K', '10-Q'):
            acc_clean = accs[i].replace('-', '') if i < len(accs) else ''
            return {
                'cik':          cik,
                'company':      filings.get('name', company),
                'form':         form,
                'date':         dates[i] if i < len(dates) else '',
                'accession':    acc_clean,
                'primary_doc':  docs[i] if i < len(docs) else '',
            }
    return {}


# ── 2. Fetch filing text ───────────────────────────────────────────────────────

def _clean(text: str) -> str:
    """Remove HTML tags, excess whitespace from EDGAR HTM filing."""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _section_extract(text: str, query: str, max_chars: int) -> str:
    """Simple relevance extraction: find paragraphs mentioning query keywords."""
    keywords = [w.lower() for w in query.split() if len(w) > 3]
    paragraphs = [p.strip() for p in re.split(r'\n{2,}|\. {2,}', text) if len(p.strip()) > 80]

    scored = []
    for p in paragraphs:
        p_low = p.lower()
        score = sum(1 for kw in keywords if kw in p_low)
        if score > 0:
            scored.append((score, p))

    scored.sort(key=lambda x: -x[0])

    # Take top paragraphs up to max_chars
    result = []
    total = 0
    for _, p in scored:
        if total + len(p) > max_chars:
            break
        result.append(p)
        total += len(p)

    # If nothing matched keywords, fall back to first N chars of doc
    if not result:
        result = [text[:max_chars]]

    return '\n\n'.join(result)


def fetch_filing_text(filing: dict, query: str) -> str:
    """Fetch and extract relevant text from the 10-K/10-Q filing."""
    cik = filing['cik']
    acc = filing['accession']
    doc = filing['primary_doc']

    # Primary doc URL
    base = f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/'
    url  = base + doc

    raw = _get(url, timeout=30)
    if not raw:
        # Try index to find an htm document
        idx = _get(f'{base}{acc}-index.htm', timeout=15)
        if not idx:
            return ''
        # Find first .htm link
        match = re.search(r'href="([^"]+\.htm)"', idx, re.IGNORECASE)
        if match:
            raw = _get(base + match.group(1), timeout=30)

    if not raw:
        return ''

    cleaned = _clean(raw)
    return _section_extract(cleaned, query, MAX_CHUNK_CHARS)


# ── 3. App data ────────────────────────────────────────────────────────────────

def _app_snapshot(ticker: str) -> str:
    """Quick snapshot of key metrics from the app's CSVs."""
    lines = []
    url = f'{PAGES_BASE}/docs/fundamental_scores.csv'
    text = _get(url)
    if text:
        for row in csv.DictReader(io.StringIO(text)):
            if row.get('ticker', '').upper() == ticker.upper():
                keep = ['value_score', 'grade', 'sector', 'roe_pct', 'profit_margin_pct',
                        'debt_to_equity', 'fcf_yield_pct', 'analyst_upside_pct',
                        'interest_coverage', 'earnings_warning', 'days_to_earnings']
                for k in keep:
                    if row.get(k):
                        lines.append(f'- {k}: {row[k]}')
                break
    return '\n'.join(lines) or '(sin datos en el sistema)'


# ── 4. Groq answer ────────────────────────────────────────────────────────────

ASK_PROMPT = """Eres un analista financiero experto. El usuario pregunta sobre {ticker}.

DATOS DEL SISTEMA (scores, FCF, ratios):
{app_data}

EXTRACTO DEL ÚLTIMO {form} ({date}) — {company}:
{filing_text}

PREGUNTA DEL USUARIO:
{question}

Responde de forma concisa y directa (máximo 200 palabras).
Cita números específicos del filing cuando sean relevantes.
Si el filing no contiene información relevante para la pregunta, dilo claramente y usa los datos del sistema.
Responde en español."""


def ask(ticker: str, question: str, send_telegram: bool = True) -> str:
    ticker = ticker.upper().strip()
    now    = datetime.now(timezone.utc).strftime('%d/%m %H:%M UTC')

    print(f'🔎 Buscando filing para {ticker}...')
    filing = _find_filing(ticker)

    filing_text = ''
    if filing:
        print(f'  📄 {filing["form"]} ({filing["date"]}) — fetching text...')
        filing_text = fetch_filing_text(filing, question)
        if filing_text:
            print(f'  ✅ {len(filing_text)} chars extraídos')
        else:
            print('  ⚠️ No se pudo descargar el filing')
    else:
        print('  ⚠️ No encontrado en EDGAR (no-US o no listado)')

    print('  🤖 Consultando Groq...')
    app_data = _app_snapshot(ticker)

    if not GROQ_API_KEY:
        answer = '(GROQ_API_KEY no configurado)'
    else:
        prompt = ASK_PROMPT.format(
            ticker=ticker,
            app_data=app_data,
            form=filing.get('form', '10-K') if filing else '10-K/10-Q',
            date=filing.get('date', '?') if filing else '?',
            company=filing.get('company', ticker) if filing else ticker,
            filing_text=filing_text or '(no disponible)',
            question=question,
        )
        try:
            r = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={'Authorization': f'Bearer {GROQ_API_KEY}',
                         'Content-Type': 'application/json'},
                json={
                    'model': GROQ_MODEL,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.15,
                    'max_tokens': 500,
                },
                timeout=45,
            )
            r.raise_for_status()
            answer = r.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            answer = f'(Error Groq: {e})'

    filing_line = ''
    if filing:
        filing_line = f'\n📄 Fuente: {filing["form"]} {filing["date"]} — {filing.get("company", "")}'

    msg = (
        f'🔎 <b>{ticker}</b> · <i>{question[:80]}</i>\n'
        f'<code>{now}</code>'
        f'{filing_line}\n'
        '━━━━━━━━━━━━━━━━━━━━━\n'
        f'{answer}'
    )

    if send_telegram:
        tg_send(msg)
    return msg


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Uso: python3 agent_ask.py <TICKER> "<pregunta>"')
        print('Ejemplo: python3 agent_ask.py AAPL "¿Cuánta deuda tiene?"')
        sys.exit(1)

    result = ask(sys.argv[1], ' '.join(sys.argv[2:]), send_telegram=bool(BOT_TOKEN))
    if not BOT_TOKEN:
        print('\n' + result)
