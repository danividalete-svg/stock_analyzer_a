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
            positions = []
            for r in rows:
                if not r.get('ticker'):
                    continue
                avg = r.get('avg_price')
                shares = r.get('shares')
                positions.append({
                    'ticker': r['ticker'],
                    'avg_price': float(avg) if avg else None,
                    'shares': float(shares) if shares else None,
                    'notes': f"{shares or '?'}sh @ {avg or '?'}",
                })
            print(f"  Supabase: {len(positions)} positions loaded")
            return positions
    except Exception as e:
        print(f"  Supabase load failed: {e}")
        return []


# P&L thresholds
_STOP_LOSS_PCT     = -8.0
_PROFIT_TARGET_PCT = 12.0
_NEAR_TARGET_PCT   = 8.0


def _check_pl_alerts(portfolio: list) -> tuple[list[dict], dict]:
    """
    Fetches current prices via yfinance and calculates P&L per position.
    Returns (alert_items, summary_dict).
    Alerts include stop-loss, profit, near-target zones.
    """
    alerts   = []
    total_cost = 0.0
    total_val  = 0.0
    positions_pl = []

    for entry in portfolio:
        ticker    = entry['ticker'].upper()
        avg_price = entry.get('avg_price')
        shares    = entry.get('shares')

        if not avg_price or not shares or avg_price <= 0:
            continue

        try:
            info      = yf.Ticker(ticker).info
            cur_price = (info.get('currentPrice') or info.get('regularMarketPrice')
                         or info.get('previousClose') or 0)
        except Exception:
            cur_price = 0

        if not cur_price:
            continue

        pl_pct   = (cur_price - avg_price) / avg_price * 100
        cost     = shares * avg_price
        mkt_val  = shares * cur_price
        total_cost += cost
        total_val  += mkt_val
        positions_pl.append({'ticker': ticker, 'pl_pct': pl_pct, 'mkt_val': mkt_val})

        if pl_pct <= _STOP_LOSS_PCT:
            alerts.append({
                'id':         f'pl_stop_{ticker}',
                'ticker':     ticker,
                'title':      f'🔴 Stop-loss zone: {pl_pct:+.1f}% — revisar tesis',
                'source':     'P&L Monitor',
                'pub_date':   datetime.now(timezone.utc).isoformat(),
                'time_ago':   '',
                'url':        '',
                'importance': 'ALTA',
                'pl_pct':     pl_pct,
                'cur_price':  cur_price,
            })
        elif pl_pct >= _PROFIT_TARGET_PCT:
            alerts.append({
                'id':         f'pl_profit_{ticker}',
                'ticker':     ticker,
                'title':      f'🟢 Profit zone: {pl_pct:+.1f}% — considera recoger',
                'source':     'P&L Monitor',
                'pub_date':   datetime.now(timezone.utc).isoformat(),
                'time_ago':   '',
                'url':        '',
                'importance': 'MEDIA',
                'pl_pct':     pl_pct,
                'cur_price':  cur_price,
            })
        elif pl_pct >= _NEAR_TARGET_PCT:
            alerts.append({
                'id':         f'pl_near_{ticker}',
                'ticker':     ticker,
                'title':      f'🔵 Cerca del objetivo: {pl_pct:+.1f}% — vigilar',
                'source':     'P&L Monitor',
                'pub_date':   datetime.now(timezone.utc).isoformat(),
                'time_ago':   '',
                'url':        '',
                'importance': 'MEDIA',
                'pl_pct':     pl_pct,
                'cur_price':  cur_price,
            })

    total_pl_pct = ((total_val - total_cost) / total_cost * 100) if total_cost > 0 else None
    summary = {
        'total_cost':    total_cost,
        'total_val':     total_val,
        'total_pl_pct':  total_pl_pct,
        'positions':     sorted(positions_pl, key=lambda x: x['pl_pct']),
    }
    return alerts, summary


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


def _groq_classify_batch(items: list[dict]) -> None:
    """Re-classify non-earnings news items using Groq. Mutates 'importance' in-place."""
    import requests as req
    api_key = os.environ.get('GROQ_API_KEY', '')
    if not api_key:
        return  # fall back to keyword classification silently

    # Only re-classify non-earnings items (earnings alerts are already ALTA and authoritative)
    to_classify = [i for i in items if not i['title'].startswith('⏰')]
    if not to_classify:
        return

    numbered = [f'{j+1}. [{i["ticker"]}] {i["title"]}' for j, i in enumerate(to_classify)]
    prompt = (
        'Classify each financial news headline as ALTA, MEDIA, or BAJA impact for a stock investor.\n'
        'ALTA = earnings surprises, guidance changes, M&A, regulatory actions, CEO change, bankruptcy, dividend cut\n'
        'MEDIA = analyst upgrades/downgrades, buybacks, contracts, partnerships, ordinary dividends\n'
        'BAJA = general market commentary, sector overviews, conference appearances\n\n'
        'Headlines:\n' + '\n'.join(numbered) + '\n\n'
        'Reply ONLY with a JSON array of strings, one per headline, e.g. ["ALTA","MEDIA","BAJA",...]'
    )
    try:
        resp = req.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={
                'model': 'llama-3.1-8b-instant',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0,
                'max_tokens': 256,
            },
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json()['choices'][0]['message']['content'].strip()
        # Extract JSON array from response
        start, end = raw.find('['), raw.rfind(']')
        if start == -1 or end == -1:
            return
        labels = json.loads(raw[start:end + 1])
        if not isinstance(labels, list) or len(labels) != len(to_classify):
            return
        valid = {'ALTA', 'MEDIA', 'BAJA'}
        for item, label in zip(to_classify, labels):
            if isinstance(label, str) and label.upper() in valid:
                item['importance'] = label.upper()
        print(f'  Groq re-classified {len(to_classify)} headlines')
    except Exception as e:
        print(f'  Groq classification skipped: {e}')


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


def _send_telegram(alerts: list, portfolio_labels: dict,
                   pl_alerts: list, pl_summary: dict) -> None:
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id   = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not bot_token or not chat_id:
        return

    # P&L alerts are always new (point-in-time); news alerts filter by seen cache
    important_news = [a for a in alerts if a['importance'] in ('ALTA', 'MEDIA')]
    has_content    = important_news or pl_alerts

    if not has_content:
        return

    lines = [
        f'📊 <b>Cartera</b> — {datetime.now().strftime("%d %b %Y %H:%M")}',
        '',
    ]

    # ── P&L summary ───────────────────────────────────────────────────────────
    if pl_summary.get('positions'):
        total_pct = pl_summary.get('total_pl_pct')
        total_str = f"{total_pct:+.1f}%" if total_pct is not None else '?'
        lines.append(f'<b>P&L cartera: {total_str}</b>')
        for p in pl_summary['positions']:
            icon = '🔴' if p['pl_pct'] <= _STOP_LOSS_PCT else (
                   '🟢' if p['pl_pct'] >= _PROFIT_TARGET_PCT else (
                   '🔵' if p['pl_pct'] >= _NEAR_TARGET_PCT else '⚪'))
            lines.append(f"  {icon} <code>{p['ticker']}</code> {p['pl_pct']:+.1f}%")
        lines.append('')

    # ── P&L zone alerts ───────────────────────────────────────────────────────
    if pl_alerts:
        lines.append('⚠️ <b>Alertas de precio:</b>')
        for a in pl_alerts:
            lines.append(f"  {a['title']}")
        lines.append('')

    # ── News alerts ───────────────────────────────────────────────────────────
    if important_news:
        lines.append('📰 <b>Noticias relevantes:</b>')
        by_ticker: dict = {}
        for a in important_news:
            by_ticker.setdefault(a['ticker'], []).append(a)
        for ticker, items in by_ticker.items():
            label = portfolio_labels.get(ticker, ticker)
            lines.append(f'<b>{ticker}</b> <i>({label})</i>')
            for item in items[:3]:
                icon     = '🔴' if item['importance'] == 'ALTA' else '📌'
                title    = item['title'][:120]
                time_str = f" · {item['time_ago']}" if item['time_ago'] else ''
                lines.append(f"  {icon} {title}")
                lines.append(f"  <i>{item['source']}{time_str}</i>")
            lines.append('')

    text = '\n'.join(lines).rstrip()
    if len(text) > 4000:
        text = text[:3980] + '\n<i>... (truncado)</i>'

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
            n = len(pl_alerts) + len(important_news)
            print(f"  Telegram: enviadas {n} alertas de cartera")
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

    # ── P&L check (uses avg_price from Supabase) ─────────────────────────────
    print("  Calculando P&L posiciones...", flush=True)
    pl_alerts, pl_summary = _check_pl_alerts(portfolio)
    if pl_summary.get('positions'):
        for p in pl_summary['positions']:
            print(f"    {p['ticker']}: {p['pl_pct']:+.1f}%")
    if pl_alerts:
        print(f"  ⚠️ {len(pl_alerts)} posiciones en zona de alerta")

    # ── News + Earnings ───────────────────────────────────────────────────────
    for entry in portfolio:
        ticker = entry['ticker'].upper()
        print(f"  {ticker}...", end=' ', flush=True)

        news = _fetch_ticker_news(ticker, lookback_hours=48)
        for item in news:
            all_items.append(item)
            if item['id'] not in seen_ids and item['importance'] in ('ALTA', 'MEDIA'):
                new_alerts.append(item)
                seen_ts[item['id']] = datetime.now(timezone.utc).isoformat()

        earn = _fetch_earnings_alert(ticker)
        if earn:
            all_items.insert(0, earn)
            if earn['id'] not in seen_ids:
                new_alerts.insert(0, earn)
                seen_ts[earn['id']] = datetime.now(timezone.utc).isoformat()

        count = sum(1 for i in news if i['importance'] in ('ALTA', 'MEDIA'))
        print(f"{len(news)} noticias, {count} importantes")
        time.sleep(0.3)

    # Re-classify with Groq (batch, single API call)
    _groq_classify_batch(all_items)

    # Rebuild new_alerts after Groq re-classification (importance may have changed)
    new_alerts = [
        i for i in all_items
        if i['id'] not in seen_ids and i['importance'] in ('ALTA', 'MEDIA')
    ]

    # Sort: ALTA first, then MEDIA, then by date
    _order = {'ALTA': 0, 'MEDIA': 1, 'BAJA': 2}
    all_items.sort(key=lambda x: (_order.get(x['importance'], 2), x.get('pub_date', '')), reverse=False)

    # Enviar solo si hay algo accionable (P&L alerts o noticias nuevas)
    # El resumen P&L completo va en el briefing matutino de financial_agent.py
    if new_alerts or pl_alerts:
        _send_telegram(new_alerts, portfolio_labels, pl_alerts, pl_summary)
    else:
        print("  Cartera OK — sin alertas nuevas")

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
