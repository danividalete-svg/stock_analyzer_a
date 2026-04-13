#!/usr/bin/env python3
"""
TIKR PRO SCRAPER — Transcripts + NTM multiples + headlines + shareholders + valuation.

Pipeline:
  0. POST /lv              → todos los modelos de valoración del usuario (batch, 1 call)
  1. Algolia search        → resuelve ticker a cid/tid/ric_id (sin auth)
  2. POST /wlp  (batch)    → precio actual + estimados NTM para N tickers
  3. POST /transcripts_v2  → lista earnings calls + conferencias por empresa
  4. POST /headlines       → Reuters news feed (usa RIC format MSFT.O)
  5. POST /shareholders    → accionistas institucionales (usa RIC format MSFT.O)
  6. POST /sigdevs         → eventos corporativos S&P CIQ (M&A, productos, regulatorio)
  7. POST /listReports     → SEC filings (10-Q/10-K/8-K) + earnings press releases + presentaciones

Múltiplos calculados localmente:
  NTM EV/EBITDA, NTM EV/Revenue, NTM EV/EBIT, NTM P/E, NTM FCF Yield %

Stealth-first: delays humanos, sin paralelismo, sesión con cookies,
headers Chrome 146 macOS, cache local de IDs.

Variables de entorno:
  TIKR_EMAIL     — email cuenta Pro
  TIKR_PASSWORD  — contraseña

Uso:
  python3 tikr_scraper.py --test MSFT
  python3 tikr_scraper.py --run
  python3 tikr_scraper.py --run --tier 1
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from pycognito.aws_srp import AWSSRP

# ── Config ────────────────────────────────────────────────────────────────────

TIKR_EMAIL    = os.environ.get('TIKR_EMAIL', '')
TIKR_PASSWORD = os.environ.get('TIKR_PASSWORD', '')

COGNITO_REGION    = 'us-east-1'
COGNITO_POOL_ID   = 'us-east-1_PflCYM8WM'
COGNITO_CLIENT_ID = '7ls0a83u5u94vjb2g6t6mdenik'

TIKR_API = 'https://api.tikr.com'
TIKR_APP = 'https://app.tikr.com'

# Algolia (client-side public key, no auth needed for search)
# ALGOLIA_INDEX: confirm exact name from DevTools request body → "indexName" field
ALGOLIA_BASE    = 'https://tjpay1dyt8-dsn.algolia.net'
ALGOLIA_APP_ID  = 'TJPAY1DYT8'
ALGOLIA_API_KEY = 'd88ea2aa3c22293c96736f5ceb5bab4e'
ALGOLIA_INDEX   = 'tikr-terminal-v1'

CACHE_FILE  = Path('docs/tikr_id_cache.json')
OUTPUT_FILE = Path('docs/tikr_earnings_data.json')

# Tipos de evento de transcripts
EVENT_EARNINGS_CALL   = 48
EVENT_CONFERENCE_PRES = 51

# NTM data item IDs (did) en respuesta /wlp
NTM_DID = {
    100180: 'ntm_revenue',
    100187: 'ntm_ebitda',
    100215: 'ntm_ebit',
    114221: 'ntm_fcf',
    100173: 'ntm_eps',
    100201: 'ntm_eps_consensus',
}

# Mapping exchangesymbol (Algolia) → Reuters RIC exchange suffix
# Usado para construir el id en /headlines y /shareholders (ej: "MSFT.O")
EXCHANGE_RIC = {
    'NasdaqGS':  'O',   # NASDAQ Global Select
    'NasdaqGM':  'O',   # NASDAQ Global Market
    'NasdaqCM':  'O',   # NASDAQ Capital Market
    'NYSE':      'N',   # New York Stock Exchange
    'ARCA':      'N',   # NYSE Arca
    'AMEX':      'A',   # American Stock Exchange
    'TSX':       'TO',  # Toronto Stock Exchange
    'TSXV':      'V',   # TSX Venture Exchange
    'LSE':       'L',   # London Stock Exchange
    'Xetra':     'DE',  # Deutsche Börse Xetra
    'FWB':       'F',   # Frankfurt Stock Exchange
    'ASX':       'AX',  # Australian Securities Exchange
    'TSE':       'T',   # Tokyo Stock Exchange
    'OSE':       'T',   # Osaka (merged with TSE)
    'BVL':       'LM',  # Bolsa de Valores de Lima
}

# Stealth timing
DELAY_MIN        = 4.0
DELAY_MAX        = 9.0
LONG_PAUSE_EVERY = 10
LONG_PAUSE_MIN   = 25.0
LONG_PAUSE_MAX   = 55.0


# ── Auth ───────────────────────────────────────────────────────────────────────

def get_fresh_token() -> str:
    """Autentica contra AWS Cognito via SRP y retorna IdToken (JWT válido ~1h)."""
    if not TIKR_EMAIL or not TIKR_PASSWORD:
        raise RuntimeError("Define TIKR_EMAIL y TIKR_PASSWORD.")
    try:
        import boto3
        client = boto3.client('cognito-idp', region_name=COGNITO_REGION)
        srp = AWSSRP(
            username=TIKR_EMAIL,
            password=TIKR_PASSWORD,
            pool_id=COGNITO_POOL_ID,
            client_id=COGNITO_CLIENT_ID,
            client=client,
        )
        tokens = srp.authenticate_user()
        token = tokens['AuthenticationResult']['IdToken']
        print("  Auth OK — token válido ~1h")
        return token
    except Exception as e:
        msg = str(e)
        if 'NotAuthorized' in msg or 'Incorrect' in msg:
            raise RuntimeError("Credenciales TIKR incorrectas.")
        raise RuntimeError(f"Error auth Cognito SRP: {e}")


# ── Session ────────────────────────────────────────────────────────────────────

def make_session() -> requests.Session:
    """Sesión HTTP con headers idénticos a Chrome 146 en macOS."""
    s = requests.Session()
    s.headers.update({
        'User-Agent':         'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/146.0.0.0 Safari/537.36',
        'Accept':             'application/json, text/plain, */*',
        'Accept-Language':    'es-ES,es;q=0.9,en-GB;q=0.8,en;q=0.7',
        'Accept-Encoding':    'gzip, deflate, br, zstd',
        'Origin':             TIKR_APP,
        'Referer':            f'{TIKR_APP}/',
        'Cache-Control':      'no-cache',
        'Pragma':             'no-cache',
        'DNT':                '1',
        'Priority':           'u=1, i',
        'sec-ch-ua':          '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        'sec-ch-ua-mobile':   '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest':     'empty',
        'sec-fetch-mode':     'cors',
        'sec-fetch-site':     'same-site',
        'Connection':         'keep-alive',
    })
    try:
        s.get(TIKR_APP, timeout=10)
        time.sleep(random.uniform(1.5, 3.0))
    except Exception:
        pass
    return s


# ── Delays ────────────────────────────────────────────────────────────────────

def human_delay(min_s: float = DELAY_MIN, max_s: float = DELAY_MAX):
    """Pausa aleatoria con distribución beta (más natural que uniforme)."""
    t = min_s + (max_s - min_s) * random.betavariate(2, 3)
    time.sleep(t)


# ── Cache ──────────────────────────────────────────────────────────────────────

def load_id_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}


def save_id_cache(cache: dict):
    CACHE_FILE.parent.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


# ── Ticker normalization ───────────────────────────────────────────────────────

# Nuestro formato → formato TIKR para búsqueda Algolia
TIKR_TICKER_MAP = {
    'AI.PA':  'AI',
    'BRK-B':  'BRK/B',
    'CSU.TO': 'CSU',
    'LSEG.L': 'LSEG',
    'EXPN.L': 'EXPN',
    'AUTO.L': 'AUTO',
    'ITRK.L': 'ITRK',
    'G24.DE': 'G24',
    'TNE.AX': 'TNE',
    'DOL.TO': 'DOL',
    'TLC.AX': 'TLC',
    '4684.T': '4684',
    '7741.T': '7741',
    '6383.T': '6383',
}

def tikr_ticker(ticker: str) -> str:
    return TIKR_TICKER_MAP.get(ticker, ticker)


def build_ric_id(tikr_symbol: str, exchange_symbol: str) -> Optional[str]:
    """
    Construye el RIC ID (ej: 'MSFT.O') desde símbolo + exchange Algolia.
    Usado por /headlines y /shareholders.
    """
    suffix = EXCHANGE_RIC.get(exchange_symbol)
    if suffix and tikr_symbol:
        return f"{tikr_symbol}.{suffix}"
    return None


# ── Algolia ticker resolution (sin auth) ──────────────────────────────────────

def algolia_resolve_ticker(ticker: str) -> Optional[dict]:
    """
    Busca un ticker en el índice Algolia de TIKR (sin autenticación).
    Devuelve el hit primario (usprimaryexchange=True o primaryflag=3)
    con companyid (cid), tradingitemid (tid), exchangesymbol, ric_id.

    Más robusto que /trkdids — devuelve todos los campos necesarios en 1 call.
    """
    url = (
        f"{ALGOLIA_BASE}/1/indexes/*/queries"
        f"?x-algolia-agent=Algolia%20for%20JavaScript%20(5.35.0)%3B%20Lite%20(5.35.0)%3B%20Browser"
        f"&x-algolia-api-key={ALGOLIA_API_KEY}"
        f"&x-algolia-application-id={ALGOLIA_APP_ID}"
    )
    payload = {
        "requests": [{
            "indexName": ALGOLIA_INDEX,
            "query":     ticker,
            "hitsPerPage": 10,
        }]
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code != 200:
            return None
        hits = r.json().get('results', [{}])[0].get('hits', [])
        if not hits:
            return None

        # Preferir el hit con usprimaryexchange=True y tickersymbol exacto
        t_upper = ticker.upper()
        primary = None
        for hit in hits:
            sym = (hit.get('tikrSymbol') or hit.get('tickersymbol', '')).upper()
            if sym != t_upper:
                continue
            if hit.get('usprimaryexchange'):
                primary = hit
                break
            if primary is None and hit.get('primaryflag') == 3:
                primary = hit

        if primary is None:
            primary = hits[0]  # fallback: primer resultado

        cid = str(primary.get('companyid', ''))
        tid = str(primary.get('tradingitemid', ''))
        tikr_sym = primary.get('tikrSymbol') or primary.get('tickersymbol', ticker)
        exch = primary.get('exchangesymbol', '')
        ric = build_ric_id(tikr_sym, exch)

        # Reuters Open Access PermID — used by /listReports as the 'id' field
        # Try various field name casings; may also be nested in companyInfo[]
        oa_perm_id = (
            primary.get('OAPermID')
            or primary.get('oapermid')
            or primary.get('permid')
            or primary.get('permId')
        )
        if oa_perm_id is None:
            for ci in primary.get('companyInfo', []):
                if ci.get('OAPermID'):
                    oa_perm_id = ci['OAPermID']
                    break
        if oa_perm_id is not None:
            oa_perm_id = str(oa_perm_id)

        return {
            'cid':          cid,
            'tid':          tid,
            'ric_id':       ric,
            'oa_perm_id':   oa_perm_id,
            'tikr_symbol':  tikr_sym,
            'exchange':     exch,
            'company_name': primary.get('companyname', ''),
            'raw':          primary,
        }
    except Exception as e:
        print(f"    Algolia {ticker}: {e}")
        return None


# ── Fallback: /trkdids ────────────────────────────────────────────────────────

def resolve_ticker_api(
    session: requests.Session,
    token: str,
    ticker: str,
) -> Optional[dict]:
    """Fallback a POST /trkdids si Algolia falla."""
    payload = {
        'auth': token, 'ticker': ticker, 'symbol': ticker,
        'from': 'ciq2ric', 'v': 'v1', 'primaryTicker': False,
    }
    try:
        r = session.post(f'{TIKR_API}/trkdids', json=payload, timeout=20)
        if r.status_code != 200:
            return None
        data = r.json()
        if not data:
            return None
        cid = str(data.get('objectid') or data.get('cid', ''))
        tid = str(data.get('tradingitemid') or data.get('tid', ''))
        return {'cid': cid, 'tid': tid, 'ric_id': None, 'raw': data}
    except Exception:
        return None


def _fetch_oa_perm_id(
    session: requests.Session,
    token: str,
    cid: str,
    tid: str,
) -> Optional[str]:
    """
    POST /trkdids con cid+tid → extrae IssuerOAPermID (Reuters PermID de empresa).
    Requerido por /listReports como campo 'id'.
    """
    try:
        r = session.post(f'{TIKR_API}/trkdids', json={
            'auth': token, 'cid': cid, 'tid': tid, 'from': 'ciq2ric', 'v': 'v1',
        }, timeout=20)
        if r.status_code != 200:
            return None
        return str(r.json().get('data', {}).get('IssuerOAPermID', '') or '') or None
    except Exception:
        return None


def resolve_ticker(
    session: requests.Session,
    token: str,
    ticker: str,
    cache: dict,
) -> Optional[dict]:
    """Intenta Algolia primero; fallback a /trkdids si falla.
    Enriquece con IssuerOAPermID vía /trkdids (necesario para /listReports).
    """
    cache_key = ticker.upper()
    if cache_key in cache:
        cached = cache[cache_key]
        # Back-fill oa_perm_id if missing from older cache entries
        if not cached.get('oa_perm_id') and cached.get('cid') and cached.get('tid'):
            perm_id = _fetch_oa_perm_id(session, token, cached['cid'], cached['tid'])
            if perm_id:
                cached['oa_perm_id'] = perm_id
                cache[cache_key] = cached
                save_id_cache(cache)
        return cached

    result = algolia_resolve_ticker(ticker)
    if not result:
        result = resolve_ticker_api(session, token, ticker)
    if not result:
        return None

    # Enrich with IssuerOAPermID for /listReports
    if not result.get('oa_perm_id') and result.get('cid') and result.get('tid'):
        perm_id = _fetch_oa_perm_id(session, token, result['cid'], result['tid'])
        if perm_id:
            result['oa_perm_id'] = perm_id

    cache[cache_key] = result
    save_id_cache(cache)
    return result


# ── Phase 0: /lv — modelos de valoración del usuario (batch) ──────────────────

def fetch_lv_models(session: requests.Session, token: str) -> dict:
    """
    POST /lv — devuelve todos los modelos de valoración guardados por el usuario.
    1 llamada para todos los tickers, respuesta keyed por cid.

    Extrae por empresa:
      - target_price, irr (tasa interna de retorno implícita)
      - eps_estimates: { '2026': val, '2027': val, ... }
      - revenue_estimates: idem
      - revenue_cagr_1y/3y/5y, eps_cagr_1y/3y/5y
    """
    payload = {'auth': token, 'v': 'v1'}
    try:
        r = session.post(f'{TIKR_API}/lv', json=payload, timeout=30)
        if r.status_code != 200:
            print(f"    /lv: HTTP {r.status_code}")
            return {}
        raw = r.json()
    except Exception as e:
        print(f"    /lv error: {e}")
        return {}

    result = {}
    for cid, models in raw.items():
        if not isinstance(models, list) or not models:
            continue
        m = models[0]  # tomar el primer modelo
        hub = m.get('metadata', {}).get('hubData', {})
        vo = hub.get('valuationOutput', {})

        target_price = (hub.get('targetPrice') or {}).get('v')
        irr          = (hub.get('irr') or {}).get('v')

        def _cagr_series(key: str) -> dict:
            return {
                str(abs(c['relativeKey'])) + 'y': round(c['v'] * 100, 2)
                for c in hub.get(key, [])
                if c.get('v') is not None
            }

        def _estimates(key: str) -> dict:
            return {
                fy.split('##')[0]: round(v['v'], 4)
                for fy, v in vo.get(key, {}).items()
                if v.get('v') is not None and '##FY' in fy
            }

        result[str(cid)] = {
            'target_price':     target_price,
            'irr_pct':          round(irr * 100, 2) if irr else None,
            'eps_estimates':     _estimates('eps'),
            'revenue_estimates': _estimates('revenue'),
            'ebit_estimates':    _estimates('ebit'),
            'revenue_cagr':      _cagr_series('historicalRevenueCagr'),
            'eps_cagr':          _cagr_series('historicalEpsCagr'),
            'company_name':      m.get('metadata', {}).get('companyname', ''),
        }

    print(f"    /lv: {len(result)} modelos")
    return result


# ── Phase 2: /wlp (batch) — precio + NTM estimates ───────────────────────────

def fetch_wlp_batch(
    session: requests.Session,
    token: str,
    ticker_pairs: list,
) -> dict:
    """
    POST /wlp — batch: precio actual + estimados NTM para múltiples tickers.
    ticker_pairs: lista de [cid, tid].
    Retorna dict keyed by tid: {price, ntm, multiples}
    """
    if not ticker_pairs:
        return {}
    payload = {
        'auth':    token,
        'tickers': [[str(c), str(t)] for c, t in ticker_pairs],
        'v':       'v1',
    }
    try:
        r = session.post(f'{TIKR_API}/wlp', json=payload, timeout=40)
        if r.status_code != 200:
            print(f"    /wlp batch: HTTP {r.status_code}")
            return {}
        data = r.json()
    except Exception as e:
        print(f"    /wlp batch error: {e}")
        return {}

    price_by_tid: dict = {}
    for p in data.get('price', []):
        tid = str(p.get('ptid') or p.get('tid', ''))
        if tid:
            price_by_tid[tid] = {
                'c':    p.get('c'),
                'h':    p.get('h'),
                'l':    p.get('l'),
                'mc':   p.get('mc'),
                'tev':  p.get('tev'),
                'sho':  p.get('sho'),
                'curr': p.get('qiso') or p.get('curr', 'USD'),
            }

    ntm_raw_by_tid: dict = {}
    for n in data.get('ntm', []):
        tid = str(n.get('tid', ''))
        did = n.get('did')
        val = n.get('v')
        if tid and did is not None and val is not None:
            ntm_raw_by_tid.setdefault(tid, {})[did] = val

    result: dict = {}
    for tid in set(price_by_tid) | set(ntm_raw_by_tid):
        price   = price_by_tid.get(tid, {})
        ntm_raw = ntm_raw_by_tid.get(tid, {})
        ntm     = {name: ntm_raw[did] for did, name in NTM_DID.items() if did in ntm_raw}
        result[tid] = {
            'price':     price,
            'ntm':       ntm,
            'multiples': _compute_ntm_multiples(price, ntm_raw),
        }
    return result


def _to_float(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _compute_ntm_multiples(price: dict, ntm_raw: dict) -> dict:
    tev     = _to_float(price.get('tev'))
    mc      = _to_float(price.get('mc'))
    close   = _to_float(price.get('c'))
    revenue = _to_float(ntm_raw.get(100180))
    ebitda  = _to_float(ntm_raw.get(100187))
    ebit    = _to_float(ntm_raw.get(100215))
    fcf     = _to_float(ntm_raw.get(114221))
    eps     = _to_float(ntm_raw.get(100173)) or _to_float(ntm_raw.get(100201))
    m: dict = {}
    if tev and ebitda and ebitda > 0:
        m['ntm_ev_ebitda']    = round(tev / ebitda, 1)
    if tev and revenue and revenue > 0:
        m['ntm_ev_revenue']   = round(tev / revenue, 2)
    if tev and ebit and ebit > 0:
        m['ntm_ev_ebit']      = round(tev / ebit, 1)
    if close and eps and eps > 0:
        m['ntm_pe']           = round(close / eps, 1)
    if mc and fcf and mc > 0:
        m['ntm_fcf_yield_pct'] = round(fcf / mc * 100, 2)
    # wlp values are already in millions — no /1e6 needed
    if mc:
        m['market_cap_m'] = round(mc, 0)
    if tev:
        m['ev_m'] = round(tev, 0)
    if close:
        m['price'] = close
    if revenue:
        m['ntm_revenue_m'] = round(revenue, 0)
    if ebitda:
        m['ntm_ebitda_m'] = round(ebitda, 0)
    if eps:
        m['ntm_eps'] = round(eps, 2)
    return m


# ── Phase 3a: /transcripts_v2 ─────────────────────────────────────────────────

def fetch_transcripts(
    session: requests.Session,
    token: str,
    cid: str | int,
    max_earnings: int = 4,
) -> dict:
    payload = {'auth': token, 'cid': str(cid), 'v': 'v1'}
    try:
        r = session.post(f'{TIKR_API}/transcripts_v2', json=payload, timeout=25)
        if r.status_code != 200:
            return {}
        data  = r.json()
        items = data.get('data', [])
        total = data.get('rowCount', len(items))
        earnings = sorted(
            [x for x in items if x.get('eventTypeId') == EVENT_EARNINGS_CALL],
            key=lambda x: x.get('mostimportantdateutc', ''), reverse=True,
        )[:max_earnings]
        conferences = sorted(
            [x for x in items if x.get('eventTypeId') == EVENT_CONFERENCE_PRES],
            key=lambda x: x.get('mostimportantdateutc', ''), reverse=True,
        )[:3]
        return {'raw_count': total, 'earnings_calls': earnings, 'conferences': conferences}
    except Exception:
        return {}


def _extract_earnings_summary(transcripts: dict) -> dict:
    calls = transcripts.get('earnings_calls', [])
    if not calls:
        return {}
    latest = calls[0]
    return {
        'latest_earnings_headline': latest.get('headline', ''),
        'latest_earnings_date':     latest.get('mostimportantdateutc', '')[:10],
        'latest_keydevid':          latest.get('keydevid'),
        'latest_transcriptid':      latest.get('transcriptid'),
        'has_audio':                any(f.get('type') == 'audio' for f in latest.get('files', [])),
        'has_transcript':           any(f.get('type') == 'transcript' for f in latest.get('files', [])),
        'earnings_history': [
            {'headline': c.get('headline', ''), 'date': c.get('mostimportantdateutc', '')[:10],
             'keydevid': c.get('keydevid'), 'transcriptid': c.get('transcriptid')}
            for c in calls
        ],
    }


# ── Phase 3b: /headlines ──────────────────────────────────────────────────────

def fetch_headlines(
    session: requests.Session,
    token: str,
    ric_id: str,
    langs: Optional[list] = None,
    max_headlines: int = 10,
) -> list:
    """
    POST /headlines — feed de noticias Reuters.
    ric_id: formato Reuters RIC (ej: 'MSFT.O', 'AI.PA')
    """
    payload = {'auth': token, 'lang': langs or ['ES', 'EN'], 'id': ric_id}
    try:
        r = session.post(f'{TIKR_API}/headlines', json=payload, timeout=20)
        if r.status_code != 200:
            return []
        hl_list = (
            r.json().get('data', {})
                    .get('HEADLINEML', {})
                    .get('HL', [])
        )
        return [
            {
                'headline':  hl.get('HT', ''),
                'datetime':  hl.get('CT', ''),
                'language':  hl.get('LN', ''),
                'source':    hl.get('PR', ''),
                'news_id':   hl.get('ID', ''),
                'companies': hl.get('CO', ''),
            }
            for hl in hl_list[:max_headlines]
        ]
    except Exception:
        return []


# ── Phase 3c: /shareholders ───────────────────────────────────────────────────

def fetch_shareholders(
    session: requests.Session,
    token: str,
    ric_id: str,
    top_n: int = 10,
) -> dict:
    """
    POST /shareholders — accionistas institucionales vía Reuters.
    ric_id: formato Reuters RIC (ej: 'MSFT.O')

    Retorna:
      total_shareholder_count, top_holders lista de:
        name, type, style, orientation, pct_of_shares, shares_held,
        shares_change_pct, holding_date
    """
    payload = {'ticker': ric_id, 'auth': token}
    try:
        r = session.post(f'{TIKR_API}/shareholders', json=payload, timeout=25)
        if r.status_code != 200:
            return {}
        data = r.json().get('data', {}).get('SymbolReport', {})
        investors = data.get('Shareholders', {}).get('Investor', [])
        total     = data.get('TotalShareholderCount', 0)

        top = []
        for inv in investors[:top_n]:
            h = inv.get('Holding', {})
            top.append({
                'name':              inv.get('Name', ''),
                'type':              inv.get('InvestorType', ''),
                'style':             inv.get('InvestmentStyle', ''),
                'orientation':       inv.get('Orientation', ''),
                'turnover_rating':   inv.get('TurnoverRating', ''),
                'pct_of_shares':     h.get('PctOfSharesOutstanding'),
                'shares_held':       h.get('SharesHeld'),
                'shares_value_usd':  h.get('SharesHeldValue'),
                'shares_change_pct': h.get('SharesHeldChangePct'),
                'holding_date':      (h.get('HoldingsDate') or '')[:10],
            })

        # Contar activos vs pasivos en top holders
        n_active  = sum(1 for h in top if h['orientation'] == 'Active')
        n_passive = sum(1 for h in top if h['orientation'] == 'Passive')

        return {
            'total_shareholder_count': total,
            'top_holders': top,
            'top_holders_active':  n_active,
            'top_holders_passive': n_passive,
        }
    except Exception as e:
        print(f"    /shareholders {ric_id}: {e}")
        return {}


# ── Phase 3d: /sigdevs — Significant Developments ────────────────────────────

def fetch_sigdevs(
    session: requests.Session,
    token: str,
    ric_id: str,
    max_events: int = 15,
) -> list:
    """
    POST /sigdevs — eventos corporativos significativos vía S&P Capital IQ.
    ric_id: formato Reuters RIC (ej: 'MSFT.O')

    Topics relevantes: 201=Products, 207=M&A, 210=Officer Changes,
      213=Divestitures, 231=IPO, 245=Earnings, 253=Strategic, 254=Regulatory.

    Retorna lista de eventos:
      headline, description, date, topics, significance, front_page
    """
    payload = {'id': ric_id, 'auth': token}
    try:
        r = session.post(f'{TIKR_API}/sigdevs', json=payload, timeout=20)
        if r.status_code != 200:
            return []
        items = r.json().get('data', [])
        events = []
        for item in items[:max_events]:
            topics = [
                t.get('Value', '')
                for t in item.get('Topics', {}).values()
                if t.get('Value')
            ]
            events.append({
                'headline':    item.get('Headline', ''),
                'description': item.get('Description', '')[:500],
                'date':        (item.get('Dates', {}).get('Source', '') or '')[:10],
                'topics':      topics,
                'significance': item.get('Flags', {}).get('Significance', 0),
                'front_page':   item.get('Flags', {}).get('FrontPage', False),
            })
        return events
    except Exception:
        return []


# ── Phase 3e: /tf — Historical financial statements (Income Stmt / CF / BS) ──

# dataitemid → friendly name (verified against MSFT + UNH /tf responses)
# Nota: algunos IDs son template-específicos (ej: 28 standard vs 29 insurance)
TF_ITEMS_OF_INTEREST = {
    28:    'total_revenue',        # Total Revenues — template estándar (MSFT, NKE, VRSK…)
    29:    'total_revenue',        # Total Revenues — template aseguradoras/servicios (UNH, CB…)
    10:    'gross_profit',         # Gross Profit
    4051:  'ebitda',               # EBITDA
    21:    'ebit',                 # Operating Income / EBIT
    15:    'net_income',           # Net Income
    142:   'eps_diluted',          # Diluted EPS Excl Extra Items
    2006:  'cash_from_operations', # Cash from Operations
    2021:  'capex',                # Capital Expenditure (negative)
    1096:  'cash',                 # Cash And Equivalents
    4173:  'total_debt',           # Total Debt
    1006:  'total_equity',         # Total Common Equity
    4128:  'roe_pct',              # Return on Equity %
    4094:  'net_margin_pct',       # Net Income Margin %
    4047:  'ebitda_margin_pct',    # EBITDA Margin %
    4193:  'net_debt_ebitda',      # Net Debt / EBITDA
    342:   'shares_diluted',       # Weighted Average Diluted Shares
    2164:  'buybacks',             # Repurchase of Common Stock (negative = buyback)
}


def fetch_tf_financials(
    session: requests.Session,
    token: str,
    cid: str | int,
    tid: str | int = '',
    repid: int = 1,
    lookback_years: int = 7,
) -> dict:
    """
    POST /tf — estados financieros históricos (Income Statement, CF, BS).
    Payload requerido: cid/tid como int, p='1' (annual), repid=1 (standard template).

    u (unidad): 2=millones, 0=ratio/%, 1=miles
    """
    payload = {'auth': token, 'cid': int(cid), 'tid': int(tid) if tid else 0, 'p': '1', 'repid': repid, 'v': 'v1'}
    try:
        r = session.post(f'{TIKR_API}/tf', json=payload, timeout=30)
        if r.status_code != 200:
            print(f"    /tf cid={cid}: HTTP {r.status_code}")
            return {}
        data = r.json()
    except Exception as e:
        print(f"    /tf cid={cid}: {e}")
        return {}

    # Obtener los años anuales ordenados (solo FY, no cuartos intermedios)
    date_entries = data.get('dates', [])
    annual_years = sorted(
        {
            entry['calendaryear']
            for entry in date_entries
            if entry.get('periodtypeid') == 1  # 1 = annual FY
        },
        reverse=True,
    )[:lookback_years]
    if not annual_years:
        return {}

    # Construir claves esperadas (ej: "2024##FY")
    fy_keys = {yr: f"{yr}##FY" for yr in annual_years}

    # Recorrer todos los items financieros y extraer los que nos interesan
    extracted: dict[str, dict[int, float | None]] = {}

    def _process_item(item: dict):
        did = item.get('dataitemid')
        if isinstance(did, list):  # composite items (e.g. FCF = [ops_cf, capex])
            return
        if did not in TF_ITEMS_OF_INTEREST:
            return
        if item.get('tikrdisplay') == '0':
            return
        metric = TF_ITEMS_OF_INTEREST[did]
        # Si ya hay datos reales para esta métrica (ej: ID 28 → total_revenue ya relleno),
        # no sobreescribir con un ID alternativo (ej: ID 29) que podría estar vacío
        if metric in extracted and any(v is not None for v in extracted[metric].values()):
            return
        series: dict[int, float | None] = {}
        for yr, key in fy_keys.items():
            cell = item.get(key)
            if cell and cell.get('v') is not None:
                val = cell['v']
                unit = cell.get('u', 2)
                if unit == 2:        # millions — keep as-is
                    series[yr] = round(val, 1)
                elif unit == 0:      # ratio/% — store as-is (already decimal)
                    series[yr] = round(val, 4)
                else:
                    series[yr] = round(val, 2)
            else:
                series[yr] = None
        # Solo guardar si hay al menos un valor real
        if any(v is not None for v in series.values()):
            extracted[metric] = series

    for section in data.get('financials', []):
        if isinstance(section, list):
            for item in section:
                if isinstance(item, dict):
                    _process_item(item)
        elif isinstance(section, dict):
            _process_item(section)

    if not extracted:
        return {}

    # Calcular revenue CAGR desde extracted data
    rev = extracted.get('total_revenue') or extracted.get('revenue', {})
    rev_cagr: dict = {}
    years_sorted = sorted([y for y, v in rev.items() if v], reverse=True)
    if len(years_sorted) >= 2:
        latest_yr   = years_sorted[0]
        latest_val  = rev[latest_yr]
        for lookback in (3, 5, 7):
            past_yr = latest_yr - lookback
            if past_yr in rev and rev[past_yr]:
                cagr = (latest_val / rev[past_yr]) ** (1 / lookback) - 1
                rev_cagr[f'{lookback}y'] = round(cagr * 100, 2)

    return {
        'annual_years':  annual_years,
        'metrics':       extracted,
        'revenue_cagr':  rev_cagr,
    }


# ── Phase 3f: /est — Analyst consensus estimates (actuals + forward) ──────────

# dataitemid → (friendly_name, scale)
# estimatescaleid 0 = millions, 3 = per share
# IDs verificados contra tabla real de UNH (2024A + 2026E)

# Estimates (forward consensus)
EST_ITEMS = {
    100180: ('revenue',         0),  # Total Revenue ($M)
    100187: ('ebitda',          0),  # EBITDA ($M)
    100215: ('ebit',            0),  # EBIT ($M)
    100250: ('net_income_norm', 0),  # Net Income normalizado ($M)
    100173: ('eps_norm',        3),  # EPS normalizado (per share)
    100278: ('eps_gaap',        3),  # EPS GAAP (per share)
    114221: ('fcf',             0),  # Free Cash Flow ($M)
    100177: ('n_analysts',      3),  # Nº analistas cubriendo revenue
}

# Actuals (reported values) — IDs distintos, verificados contra UNH 2024A
EST_ACTUALS = {
    100186: ('revenue',         0),
    100193: ('ebitda',          0),
    100221: ('ebit',            0),
    100256: ('net_income_norm', 0),
    100179: ('eps_norm',        3),
    100284: ('eps_gaap',        3),
    114220: ('fcf',             0),
}


def fetch_est(
    session: requests.Session,
    token: str,
    cid: str | int,
    tid: str | int,
    fwd_years: int = 4,
) -> dict:
    """
    POST /est — estimaciones consenso analistas (actuals + forward).

    Retorna:
      current_year: año fiscal actual
      forward: {2026: {revenue: X, ebitda: X, eps_norm: X, fcf: X, ...}, 2027: ...}
      actuals: {2024: {revenue: X, ...}, 2025: ...}  (últimos 3 años para contexto)
      revision_flag: 'up' | 'down' | 'stable' — comparando estimado actual vs 30d antes
    """
    payload = {'auth': token, 'cid': int(cid), 'tid': int(tid), 'p': '1', 'v': 'v1'}
    try:
        r = session.post(f'{TIKR_API}/est', json=payload, timeout=30)
        if r.status_code != 200:
            print(f"    /est cid={cid}: HTTP {r.status_code}")
            return {}
        data = r.json()
    except Exception as e:
        print(f"    /est cid={cid}: {e}")
        return {}

    dates     = data.get('dates', [])
    estimates = data.get('estimates', [])
    actuals   = data.get('actuals', [])

    if not dates:
        return {}

    # Mapa consensusid → año calendario
    cons_to_year: dict[int, int] = {}
    for d in dates:
        cons_to_year[d['estimateconsensusid']] = d['calendaryear']

    current_year = datetime.now(timezone.utc).year

    def _parse_entries(entries: list, id_map: dict) -> dict:
        """
        Para cada (year, dataitemid) toma el entry con effectivedate más reciente.
        Retorna {year: {metric: value}}.
        """
        best: dict[tuple, dict] = {}
        for e in entries:
            did = e.get('dataitemid')
            if did not in id_map:
                continue
            yr = cons_to_year.get(e['estimateconsensusid'])
            if yr is None:
                continue
            key = (yr, did)
            if key not in best or e['effectivedate'] > best[key]['effectivedate']:
                best[key] = e

        result: dict[int, dict] = {}
        for (yr, did), e in best.items():
            metric, scale = id_map[did]
            try:
                val = float(e['dataitemvalue'])
            except (TypeError, ValueError):
                continue
            val = round(val, 2) if scale == 3 else round(val, 1)
            result.setdefault(yr, {})[metric] = val
        return result

    fwd_raw = _parse_entries(estimates, EST_ITEMS)
    act_raw = _parse_entries(actuals,   EST_ACTUALS)

    # Separar forward (>= current year) de recientes para contexto
    forward = {yr: v for yr, v in fwd_raw.items()
               if current_year <= yr <= current_year + fwd_years}
    recent  = {yr: v for yr, v in act_raw.items()
               if yr >= current_year - 3}

    # Revision flag: comparar EPS estimado actual vs hace ~30 días
    # Tomamos el entry más reciente y el de hace 30+ días para el año forward+1
    next_yr = current_year + 1
    rev_flag = 'stable'
    eps_entries = [
        e for e in estimates
        if e.get('dataitemid') == 100173
        and cons_to_year.get(e.get('estimateconsensusid')) == next_yr
    ]
    if len(eps_entries) >= 2:
        eps_sorted = sorted(eps_entries, key=lambda x: x['effectivedate'], reverse=True)
        latest_eps = float(eps_sorted[0]['dataitemvalue'])
        older_eps  = float(eps_sorted[-1]['dataitemvalue'])
        if older_eps and abs(older_eps) > 0.01:
            change_pct = (latest_eps - older_eps) / abs(older_eps) * 100
            if change_pct > 1.0:
                rev_flag = 'up'
            elif change_pct < -1.0:
                rev_flag = 'down'

    if not forward and not recent:
        return {}

    return {
        'current_year': current_year,
        'forward':      forward,
        'recent':       recent,
        'revision_flag': rev_flag,
    }


# ── Phase 3g: /listReports — SEC filings + earnings releases + presentations ──

# Prioridad de documentos para análisis de tesis
_VALUABLE_FORM_TYPES = {'10-Q', '10-K', '8-K'}
_EARNINGS_KEYWORDS   = ('earnings', 'quarterly results', 'annual results')
_PRES_KEYWORDS       = ('presentation', 'investor day', 'investor presentation')


def _is_earnings_release(sub: dict) -> bool:
    form_name = (sub.get('formName') or '').lower()
    feed_id   = sub.get('feedID', '')
    return feed_id == 'Bridge' and any(k in form_name for k in _EARNINGS_KEYWORDS)


def _is_presentation(sub: dict) -> bool:
    form_name = (sub.get('formName') or '').lower()
    return (
        any(k in form_name for k in _PRES_KEYWORDS)
        and sub.get('IsPDFDocumentAvailable') == 'Y'
    )


def fetch_list_reports(
    session: requests.Session,
    token: str,
    oa_perm_id: str,
    max_filings: int = 4,
    max_earnings_releases: int = 3,
    max_presentations: int = 2,
) -> dict:
    """
    POST /listReports — archivos SEC + comunicados de resultados + presentaciones.
    oa_perm_id: Reuters Open Access PermID (ej: '4295907168' para MSFT).
                NO es el RIC format — es el PermID numérico.

    Filtra y clasifica:
      - earnings_releases: Bridge feed + formName contiene 'Earnings' (press releases)
      - sec_filings: Edgar 10-Q/10-K/8-K (los más recientes)
      - presentations: PDFs de investor day / quarterly presentations
    """
    if not oa_perm_id:
        return {}
    payloads = [{'auth': token, 'id': oa_perm_id}]

    data = None
    for payload in payloads:
        try:
            r = session.post(f'{TIKR_API}/listReports', json=payload, timeout=25)
            if r.status_code == 200:
                data = r.json()
                break
        except Exception:
            continue

    if not data:
        return {}

    # Aplanar todas las submissionInfo en una lista única
    all_subs = []
    for entry in data.get('data', {}).get('submissionStatusAndInfo', []):
        for sub in entry.get('submissionInfo', []):
            all_subs.append(sub)

    if not all_subs:
        return {}

    earnings_releases = []
    sec_filings       = []
    presentations     = []

    for sub in all_subs:
        form_type = sub.get('formType', '') or sub.get('formName', '')
        feed_id   = sub.get('feedID', '')
        doc = {
            'form_name':    sub.get('formName', ''),
            'form_type':    sub.get('formType', ''),
            'title':        sub.get('documentTitle', ''),
            'period_end':   (sub.get('periodEndDate') or '')[:10],
            'release_date': (sub.get('releaseDate') or '')[:10],
            'feed':         feed_id,
            'has_pdf':      sub.get('IsPDFDocumentAvailable') == 'Y',
            'has_html':     sub.get('IsHTMLDocumentAvailable') == 'Y',
            'accession':    sub.get('accessionNumber', ''),
            'dcn':          sub.get('DCN', ''),
        }
        if _is_earnings_release(sub):
            earnings_releases.append(doc)
        elif feed_id == 'Edgar' and form_type in _VALUABLE_FORM_TYPES:
            sec_filings.append(doc)
        elif _is_presentation(sub):
            presentations.append(doc)

    # Ordenar por fecha más reciente y limitar
    def _sort_key(d):
        return d.get('release_date') or d.get('period_end') or ''

    earnings_releases.sort(key=_sort_key, reverse=True)
    sec_filings.sort(key=_sort_key, reverse=True)
    presentations.sort(key=_sort_key, reverse=True)

    return {
        'earnings_releases': earnings_releases[:max_earnings_releases],
        'sec_filings':       sec_filings[:max_filings],
        'presentations':     presentations[:max_presentations],
        'total_docs':        len(all_subs),
    }


# ── Runner ─────────────────────────────────────────────────────────────────────

def _load_existing_output() -> dict:
    """Carga el output anterior (si existe) para reusar datos aún frescos."""
    if OUTPUT_FILE.exists():
        try:
            return json.loads(OUTPUT_FILE.read_text()).get('data', {})
        except Exception:
            pass
    return {}


def _tf_is_fresh(existing: dict, ticker: str, max_age_days: int = 7) -> bool:
    """True si los financieros históricos del ticker fueron fetched hace < max_age_days."""
    entry = existing.get(ticker, {})
    fh    = entry.get('financials_history', {})
    if not fh.get('metrics'):
        return False
    fetched_at = entry.get('fetched_at', '')
    if not fetched_at:
        return False
    try:
        from datetime import timedelta
        age = datetime.now(timezone.utc) - datetime.fromisoformat(fetched_at)
        return age < timedelta(days=max_age_days)
    except Exception:
        return False


def run(tickers: list, dry_run: bool = False) -> dict:
    # Shufflear orden: evita patrón fijo detectable por TIKR
    tickers = list(tickers)
    random.shuffle(tickers)

    print("\n🔐 Autenticando en TIKR Pro...")
    token = get_fresh_token()

    print("\n🌐 Iniciando sesión HTTP (Chrome 146 / macOS)...")
    session = make_session()

    cache    = load_id_cache()
    existing = _load_existing_output()   # datos del run anterior para cache /tf
    results  = {}
    errors   = []
    total    = len(tickers)

    # ── Phase 0: /lv — modelos de valoración (1 call batch) ──────────────────
    print("\n📈 Fase 0/4 — Modelos de valoración (/lv)...")
    lv_models: dict = {}
    if not dry_run:
        lv_models = fetch_lv_models(session, token)
        human_delay(3.0, 6.0)

    # ── Phase 1: resolver IDs ─────────────────────────────────────────────────
    print(f"\n📋 Fase 1/4 — Resolviendo IDs para {total} tickers...")
    resolved: dict[str, dict] = {}

    for i, ticker in enumerate(tickers, 1):
        t_tikr = tikr_ticker(ticker)
        print(f"  [{i:3d}/{total}] {ticker:<12}", end='', flush=True)

        if dry_run:
            print(" — dry run")
            continue

        ids = resolve_ticker(session, token, t_tikr, cache)
        if not ids:
            print(" no IDs")
            errors.append(ticker)
            human_delay(1.5, 3.0)
            continue

        cid  = ids['cid']
        ric  = ids.get('ric_id') or ''
        perm = ids.get('oa_perm_id') or ''
        print(f" cid={cid} {ric or '(no ric)'} perm={perm or 'N/A'} OK")
        resolved[ticker] = ids
        human_delay(2.0, 4.5)

        if i % LONG_PAUSE_EVERY == 0 and i < total:
            pause = random.uniform(LONG_PAUSE_MIN, LONG_PAUSE_MAX)
            print(f"\n  ⏸  Pausa larga ({pause:.0f}s)...\n")
            time.sleep(pause)

    if dry_run:
        return {}

    # ── Phase 2: /wlp batch — precio + NTM ───────────────────────────────────
    n_resolved = len(resolved)
    print(f"\n📊 Fase 2/4 — NTM batch /wlp ({n_resolved} tickers)...")
    pairs   = [(v['cid'], v['tid']) for v in resolved.values() if v['cid'] and v['tid']]
    wlp_data: dict = {}

    if pairs:
        BATCH = 25
        for start in range(0, len(pairs), BATCH):
            batch  = pairs[start:start + BATCH]
            result = fetch_wlp_batch(session, token, batch)
            wlp_data.update(result)
            n_ok = sum(1 for v in result.values() if v.get('multiples'))
            print(f"    Lote {start//BATCH + 1}: {len(batch)} tickers → {n_ok} con múltiplos")
            if start + BATCH < len(pairs):
                human_delay(4.0, 8.0)

    # ── Phase 3: financials + transcripts + headlines + shareholders + sigdevs ──
    print("\n📝 Fase 3/4 — Financials + Transcripts + Headlines + Shareholders...")

    for i, (ticker, ids) in enumerate(resolved.items(), 1):
        cid = ids['cid']
        ric = ids.get('ric_id')

        print(f"  [{i:3d}/{n_resolved}] {ticker:<12}", end='', flush=True)

        # Transcripts
        transcripts = fetch_transcripts(session, token, cid)
        summary     = _extract_earnings_summary(transcripts)
        n_earn = len(transcripts.get('earnings_calls', []))
        n_conf = len(transcripts.get('conferences', []))
        print(f" {n_earn}Q {n_conf}conf", end='', flush=True)
        human_delay(2.0, 5.0)

        # Financials históricos (/tf — cid+tid)
        # Reusar si el run anterior tiene datos < 7 días (datos anuales no cambian a diario)
        tid = ids.get('tid', '')
        if _tf_is_fresh(existing, ticker):
            financials_history = existing[ticker]['financials_history']
            n_fin = len(financials_history.get('metrics', {}))
            print(f" {n_fin}fin(cached)", end='', flush=True)
        else:
            financials_history = fetch_tf_financials(session, token, cid, tid=tid)
            n_fin = len(financials_history.get('metrics', {}))
            print(f" {n_fin}fin", end='', flush=True)
            human_delay(2.0, 4.0)

        # Analyst estimates (/est — cid+tid)
        analyst_estimates = fetch_est(session, token, cid, tid)
        n_fwd = len(analyst_estimates.get('forward', {}))
        rev   = analyst_estimates.get('revision_flag', '')
        print(f" {n_fwd}fwd({rev})", end='', flush=True)
        human_delay(2.0, 4.0)

        # Headlines + SigDevs + Shareholders + Reports (all use RIC format)
        headlines:    list = []
        sigdevs:      list = []
        shareholders: dict = {}
        reports:      dict = {}
        if ric:
            headlines    = fetch_headlines(session, token, ric)
            human_delay(1.5, 3.5)
            sigdevs      = fetch_sigdevs(session, token, ric)
            human_delay(1.5, 3.5)
            shareholders = fetch_shareholders(session, token, ric)
            human_delay(1.5, 3.5)
            oa_perm_id   = ids.get('oa_perm_id', '')
            reports      = fetch_list_reports(session, token, oa_perm_id)
        n_rep = len(reports.get('earnings_releases', [])) + len(reports.get('sec_filings', []))
        print(f" {len(headlines)}hl {len(sigdevs)}ev {len(shareholders.get('top_holders',[]))}sh {n_rep}rp OK")

        # NTM del batch + modelo /lv
        ntm_info = wlp_data.get(tid, {})
        lv_data  = lv_models.get(cid, {})

        results[ticker] = {
            'ticker':           ticker,
            'tikr_ticker':      tikr_ticker(ticker),
            'cid':              cid,
            'tid':              tid,
            'ric_id':           ric,
            'company_name':     ids.get('company_name', lv_data.get('company_name', '')),
            'price':            ntm_info.get('price', {}),
            'ntm':              ntm_info.get('ntm', {}),
            'multiples':        ntm_info.get('multiples', {}),
            'valuation_model':   lv_data,
            'financials_history':  financials_history,
            'analyst_estimates':   analyst_estimates,
            'transcripts':         transcripts,
            'earnings_summary':    summary,
            'headlines':           headlines,
            'sigdevs':             sigdevs,
            'shareholders':     shareholders,
            'reports':          reports,
            'fetched_at':       datetime.now(timezone.utc).isoformat(),
        }

        _save_output(results, errors)
        human_delay()

        if i % LONG_PAUSE_EVERY == 0 and i < n_resolved:
            pause = random.uniform(LONG_PAUSE_MIN, LONG_PAUSE_MAX)
            print(f"\n  ⏸  Pausa larga ({pause:.0f}s)...\n")
            time.sleep(pause)

    _save_output(results, errors)
    print(f"\nCompletado: {len(results)} OK, {len(errors)} errores")
    if errors:
        print(f"  Errores: {errors}")
    print(f"  Guardado: {OUTPUT_FILE}")
    return results


def _save_output(results: dict, errors: list):
    output = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'total':        len(results),
        'errors':       errors,
        'data':         results,
    }
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False))


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    from curated_tickers import TIER_1, TIER_2, TIER_3, get_universe

    parser = argparse.ArgumentParser(description='TIKR Pro Scraper')
    parser.add_argument('--test',    type=str, help='Test un ticker (ej: MSFT)')
    parser.add_argument('--tickers', type=str, help='Lista separada por comas (ej: MSFT,NKE,V)')
    parser.add_argument('--run',     action='store_true', help='Run universo curado')
    parser.add_argument('--tier',    type=int, choices=[1, 2, 3])
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if args.test:
        run_tickers = [args.test.upper()]
    elif args.tickers:
        run_tickers = [t.strip().upper() for t in args.tickers.split(',') if t.strip()]
    elif args.run:
        run_tickers = {1: TIER_1, 2: TIER_2, 3: TIER_3}.get(args.tier, get_universe())
    else:
        parser.print_help()
        sys.exit(1)

    run(run_tickers, dry_run=args.dry_run)
