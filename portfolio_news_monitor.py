#!/usr/bin/env python3
"""
Portfolio News Monitor — Monitoriza noticias de tus posiciones y envía alertas Telegram.

Lee los tickers de Supabase (personal_portfolio_positions) o, como fallback, de docs/portfolio_watch.json.
Para cada ticker:
  - Obtiene noticias recientes (yfinance, últimas 48h)
  - Detecta earnings próximos / recientes
  - Clasifica importancia (ALTA / MEDIA / BAJA)
  - Envía Telegram si hay noticias importantes nuevas (ALTA o MEDIA)
  - Guarda en docs/portfolio_news.json

Ejecutar:
  python3 portfolio_news_monitor.py

Env vars requeridos para Supabase:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_MONITOR_USER_ID (opcional)
"""

import json
import os
import time
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import yfinance as yf

DOCS = Path('docs')
DOCS.mkdir(exist_ok=True)

# ── Keywords for importance classification ────────────────────────────────────

_KEYWORDS_HIGH = [
    # Earnings / results
    'earnings', 'results', 'beats', 'misses', 'beat', 'miss',
    'guidance', 'outlook', 'forecast', 'raises', 'cuts guidance',
    'eps', 'revenue surprise',
    # Regulatory / macro events
    'cms', 'medicare', 'medicaid', 'fda', 'approval', 'trial', 'recall',
    'sec', 'doj', 'ftc', 'probe', 'investigation', 'lawsuit', 'settlement',
    'tariff', 'sanction',
    # Corporate actions
    'acquisition', 'merger', 'buyout', 'deal', 'takeover', 'acquired',
    'divest', 'spinoff', 'split',
    'dividend cut', 'dividend suspend', 'dividend raise',
    'bankruptcy', 'chapter 11', 'restructuring', 'default',
    # Management
    'ceo resigns', 'ceo resign', 'ceo fired', 'ceo replaced',
    'cfo resign', 'cfo fired',
    'layoff', 'layoffs', 'cuts jobs', 'job cut',
]

_KEYWORDS_MEDIUM = [
    'upgrade', 'downgrade', 'target', 'price target',
    'analyst', 'rating',
    'dividend', 'buyback', 'repurchase',
    'partnership', 'contract', 'wins',
    'guidance', 'raised', 'lowered',
    'quarter', 'annual', 'revenue', 'profit', 'loss',
    'debt', 'refinanc', 'credit',
    'warning', 'concern', 'risk',
]

# News IDs seen in last run (avoid re-alerting same story)
_SEEN_CACHE_PATH = DOCS / '.portfolio_news_seen.json'


def _load_seen_ids() -> set:
    if _SEEN_CACHE_PATH.exists():
        try:
            data = json.loads(_SEEN_CACHE_PATH.read_text())
            # Expire cache entries older than 3 days
            cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
            return {k for k, v in data.items() if v >= cutoff}
        except Exception:
            pass
    return set()


def _save_seen_ids(seen: dict) -> None:
    # Prune to max 1000 entries
    if len(seen) > 1000:
        oldest = sorted(seen.items(), key=lambda x: x[1])
        seen = dict(oldest[-500:])
    try:
        _SEEN_CACHE_PATH.write_text(json.dumps(seen, indent=2))
    except Exception:
        pass


def _load_portfolio_from_supabase() -> list:
    """Load tickers from Supabase personal_portfolio_positions via REST API."""
    supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    service_key  = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    user_id      = os.environ.get('SUPABASE_MONITOR_USER_ID', '')

    if not supabase_url or not service_key:
        return []

    import urllib.request
    url = f"{supabase_url}/rest/v1/personal_portfolio_positions?select=ticker,shares,avg_price"
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
            tickers = [{'ticker': r['ticker'], 'notes': f"{r.get('shares', '')}sh @ {r.get('avg_price', '')}"}
                       for r in rows if r.get('ticker')]
            print(f"  Supabase: {len(tickers)} positions loaded")
            return tickers
    except Exception as e:
        print(f"  Supabase load failed: {e}")
        return []


def _load_portfolio() -> list:
    # Try Supabase first (GitHub Actions sets SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY)
    positions = _load_portfolio_from_supabase()
    if positions:
        return positions

    # Fallback: local portfolio_watch.json
    cfg_path = DOCS / 'portfolio_watch.json'
    if not cfg_path.exists():
        print("  portfolio_watch.json not found — nothing to monitor")
        return []
    data = json.loads(cfg_path.read_text())
    return [entry if isinstance(entry, dict) else {'ticker': entry}
            for entry in data.get('tickers', [])]


def _classify_importance(title: str) -> str:
    t = title.lower()
    for kw in _KEYWORDS_HIGH:
        if kw in t:
            return 'ALTA'
    for kw in _KEYWORDS_MEDIUM:
        if kw in t:
            return 'MEDIA'
    return 'BAJA'


def _time_ago(pub_date_str: str) -> str:
    """Convert ISO pubDate to human-readable 'hace Xh/Xmin'."""
    try:
        dt = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
        diff = datetime.now(timezone.utc) - dt
        hours = int(diff.total_seconds() / 3600)
        if hours < 1:
            mins = int(diff.total_seconds() / 60)
            return f"hace {mins}min"
        if hours < 24:
            return f"hace {hours}h"
        return f"hace {int(hours/24)}d"
    except Exception:
        return ''


def _fetch_ticker_news(ticker: str, lookback_hours: int = 48) -> list:
    """Fetch recent news for a ticker from yfinance."""
    try:
        tk = yf.Ticker(ticker)
        raw_news = tk.news or []
        cutoff_ts = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).timestamp()

        items = []
        for n in raw_news:
            content = n.get('content', {})
            if not content:
                continue

            pub_str = content.get('pubDate') or content.get('displayTime') or ''
            # Parse timestamp
            try:
                pub_dt  = datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
                pub_ts  = pub_dt.timestamp()
            except Exception:
                pub_ts = 0
                pub_dt = None

            if pub_ts < cutoff_ts and pub_ts > 0:
                continue  # Too old

            title  = content.get('title') or ''
            source = (content.get('provider') or {})
            if isinstance(source, dict):
                source = source.get('displayName') or source.get('source') or 'Yahoo Finance'

            url_obj = content.get('canonicalUrl') or content.get('clickThroughUrl') or {}
            url = url_obj.get('url', '') if isinstance(url_obj, dict) else ''

            news_id = n.get('id') or hashlib.md5(title.encode()).hexdigest()[:12]

            items.append({
                'id':         news_id,
                'ticker':     ticker,
                'title':      title,
                'source':     source,
                'pub_date':   pub_str,
                'time_ago':   _time_ago(pub_str) if pub_str else '',
                'url':        url,
                'importance': _classify_importance(title),
            })
        return items

    except Exception as e:
        print(f"  {ticker}: news error — {e}")
        return []


def _fetch_earnings_alert(ticker: str) -> Optional[dict]:
    """Return an earnings alert dict if earnings are within 7 days."""
    try:
        tk   = yf.Ticker(ticker)
        info = tk.info or {}
        ts   = info.get('earningsTimestamp') or info.get('nextFiscalYearEnd')
        if not ts:
            return None
        earn_dt = datetime.fromtimestamp(int(ts))
        days    = (earn_dt - datetime.now()).days
        if 0 <= days <= 7:
            return {
                'id':         f'earn_{ticker}_{earn_dt.strftime("%Y%m%d")}',
                'ticker':     ticker,
                'title':      f'⏰ Earnings en {days} día{"s" if days != 1 else ""} — {earn_dt.strftime("%d %b")}',
                'source':     'Earnings Calendar',
                'pub_date':   datetime.now(timezone.utc).isoformat(),
                'time_ago':   '',
                'url':        '',
                'importance': 'ALTA',
            }
    except Exception:
        pass
    return None


def _send_telegram(alerts: list, portfolio_labels: dict) -> None:
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id   = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not bot_token or not chat_id:
        return

    important = [a for a in alerts if a['importance'] in ('ALTA', 'MEDIA')]
    if not important:
        return

    lines = [
        f'📰 <b>Noticias Cartera</b> — {datetime.now().strftime("%d %b %Y")}',
        '',
    ]

    # Group by ticker
    by_ticker: dict = {}
    for a in important:
        by_ticker.setdefault(a['ticker'], []).append(a)

    for ticker, items in by_ticker.items():
        label = portfolio_labels.get(ticker, ticker)
        lines.append(f'<b>{ticker}</b> <i>({label})</i>')
        for item in items[:3]:  # Max 3 per ticker
            icon = '🔴' if item['importance'] == 'ALTA' else '📌'
            title = item['title'][:120]
            time_str = f" · {item['time_ago']}" if item['time_ago'] else ''
            lines.append(f"  {icon} {title}")
            lines.append(f"  <i>{item['source']}{time_str}</i>")
        lines.append('')

    lines.append('<i>Portfolio Monitor · Stock Analyzer</i>')
    text = '\n'.join(lines)

    try:
        import requests
        resp = requests.post(
            f'https://api.telegram.org/bot{bot_token}/sendMessage',
            json={
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            print(f"  Telegram: enviadas {len(important)} alertas de cartera")
        else:
            print(f"  Telegram error: {resp.status_code} {resp.text[:100]}")
    except Exception as e:
        print(f"  Telegram failed: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run_portfolio_news_monitor() -> dict:
    portfolio = _load_portfolio()
    if not portfolio:
        return {'items': [], 'count': 0}

    seen_ids   = _load_seen_ids()
    seen_ts    = {k: datetime.now(timezone.utc).isoformat() for k in seen_ids}
    new_alerts = []
    all_items  = []

    portfolio_labels = {
        p['ticker']: p.get('notes', p['ticker'])
        for p in portfolio
    }

    for entry in portfolio:
        ticker = entry['ticker'].upper()
        print(f"  {ticker}...", end=' ', flush=True)

        # News
        news = _fetch_ticker_news(ticker, lookback_hours=48)
        for item in news:
            all_items.append(item)
            if item['id'] not in seen_ids and item['importance'] in ('ALTA', 'MEDIA'):
                new_alerts.append(item)
                seen_ts[item['id']] = datetime.now(timezone.utc).isoformat()

        # Earnings alert
        earn = _fetch_earnings_alert(ticker)
        if earn:
            all_items.insert(0, earn)
            if earn['id'] not in seen_ids:
                new_alerts.insert(0, earn)
                seen_ts[earn['id']] = datetime.now(timezone.utc).isoformat()

        count = sum(1 for i in news if i['importance'] in ('ALTA', 'MEDIA'))
        print(f"{len(news)} noticias, {count} importantes")
        time.sleep(0.3)

    # Sort: ALTA first, then MEDIA, then by date
    _order = {'ALTA': 0, 'MEDIA': 1, 'BAJA': 2}
    all_items.sort(key=lambda x: (_order.get(x['importance'], 2), x.get('pub_date', '')), reverse=False)

    # Send Telegram for new important alerts
    if new_alerts:
        print(f"  Sending {len(new_alerts)} new alerts to Telegram...")
        _send_telegram(new_alerts, portfolio_labels)
    else:
        print("  No new important alerts to send")

    # Persist seen IDs
    _save_seen_ids(seen_ts)

    # Save JSON output
    output = {
        'scan_date':     datetime.now().strftime('%Y-%m-%d'),
        'scan_time':     datetime.now().strftime('%H:%M'),
        'tickers':       [p['ticker'] for p in portfolio],
        'count':         len(all_items),
        'alta_count':    sum(1 for i in all_items if i['importance'] == 'ALTA'),
        'media_count':   sum(1 for i in all_items if i['importance'] == 'MEDIA'),
        'new_alerts':    len(new_alerts),
        'items':         all_items,
    }

    out_path = DOCS / 'portfolio_news.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(all_items)} news items → {out_path}")
    print(f"  ALTA: {output['alta_count']} | MEDIA: {output['media_count']} | New Telegram: {len(new_alerts)}")
    return output


if __name__ == '__main__':
    print("Portfolio News Monitor")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("-" * 40)
    run_portfolio_news_monitor()
