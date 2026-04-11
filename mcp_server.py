#!/usr/bin/env python3
"""
STOCK ANALYZER MCP SERVER
Expone las señales del sistema como herramientas para Claude.

Uso local (Claude Code):
  claude mcp add stock-analyzer -- /opt/homebrew/bin/python3.13 /ruta/mcp_server.py

Herramientas disponibles:
  market_overview      — VIX, régimen, frescura del scan, conteo de oportunidades
  top_value_picks      — mejores oportunidades VALUE ahora mismo
  ticker_analysis      — análisis completo de un ticker concreto
  portfolio_status     — win rates, posiciones activas, top/worst performers
  confluence_signals   — tickers donde Bounce + Value + Flow coinciden
  bounce_setups        — setups de mean reversion que pasan todos los filtros
"""

import csv
import io
import json
from datetime import datetime, timezone
from typing import Optional

import requests
from mcp.server.fastmcp import FastMCP

PAGES = 'https://tantancansado.github.io/stock_analyzer_a'
API   = 'https://stockanalyzera-production.up.railway.app'

mcp = FastMCP('Stock Analyzer', instructions=(
    'Usa estas herramientas para responder preguntas sobre el portfolio, '
    'oportunidades de inversión VALUE, señales técnicas y estado del mercado. '
    'El sistema es VALUE/GARP style (Lynch). Estilo conservador, win rate > 50%.'
))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get(url: str, as_json=False, timeout=12):
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code != 200:
            return None
        return r.json() if as_json else r.text
    except Exception:
        return None


def _csv_rows(filename: str) -> list[dict]:
    text = _get(f'{PAGES}/docs/{filename}')
    if not text:
        return []
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def _age_label(iso_str: str) -> str:
    """'2h' / '14h' / '3d' desde una fecha ISO."""
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        secs = (datetime.now(timezone.utc) - dt).total_seconds()
        if secs < 3600:
            return f'{int(secs/60)}min'
        if secs < 86400:
            return f'{secs/3600:.0f}h'
        return f'{secs/86400:.0f}d'
    except Exception:
        return '?'


# ── Tools ──────────────────────────────────────────────────────────────────────

@mcp.tool()
def market_overview() -> str:
    """
    Estado actual del mercado: VIX, régimen (BULL/CORRECTION/BEAR), antigüedad
    del último scan, número de oportunidades VALUE y bounce disponibles.
    Úsalo primero para tener contexto antes de cualquier análisis.
    """
    mr = _get(f'{PAGES}/docs/mean_reversion_opportunities.json', as_json=True)
    value_rows = _csv_rows('value_opportunities_filtered.csv')
    eu_rows    = _csv_rows('european_value_opportunities_filtered.csv')

    lines = ['## Estado del mercado']

    if mr:
        scan_age = _age_label(mr.get('scan_date', ''))
        ops   = mr.get('opportunities', [])
        vix   = next((o.get('vix') for o in ops if o.get('vix')), None)
        regime = mr.get('market_regime') or (ops[0].get('market_regime') if ops else None)

        bounce_ok = [o for o in ops
                     if o.get('strategy') == 'Oversold Bounce'
                     and float(o.get('rsi') or 99) < 30
                     and float(o.get('bounce_confidence') or 0) >= 40
                     and float(o.get('current_price') or 0) >= 1.0]

        lines += [
            f'- Régimen: **{regime or "N/A"}**',
            f'- VIX: **{vix or "N/A"}**',
            f'- Scan: hace {scan_age}',
            f'- Bounces detectados: {len(bounce_ok)} setups activos',
        ]
    else:
        lines.append('- ⚠️ Datos de mercado no disponibles')

    lines += [
        f'- VALUE US: {max(0, len(value_rows))} oportunidades filtradas',
        f'- VALUE EU: {max(0, len(eu_rows))} oportunidades filtradas',
    ]

    return '\n'.join(lines)


@mcp.tool()
def top_value_picks(min_score: int = 55, limit: int = 10, market: str = 'all') -> str:
    """
    Mejores oportunidades VALUE ahora mismo.

    Args:
        min_score: Score mínimo (0-100). Default 55. Usa 70+ para alta convicción.
        limit: Máximo de resultados. Default 10.
        market: 'us', 'eu' o 'all'. Default 'all'.
    """
    rows: list[dict] = []
    if market in ('us', 'all'):
        rows += [dict(r, _market='US') for r in _csv_rows('value_opportunities_filtered.csv')]
    if market in ('eu', 'all'):
        rows += [dict(r, _market='EU') for r in _csv_rows('european_value_opportunities_filtered.csv')]

    if not rows:
        return 'Sin datos VALUE disponibles ahora mismo.'

    def score(r):
        try: return float(r.get('value_score') or 0)
        except: return 0.0

    filtered = [r for r in rows if score(r) >= min_score]
    filtered.sort(key=score, reverse=True)
    filtered = filtered[:limit]

    if not filtered:
        return f'Sin picks con score ≥ {min_score}. Prueba con un mínimo más bajo.'

    lines = [f'## Top {len(filtered)} picks VALUE (score ≥ {min_score})\n']
    for r in filtered:
        ticker  = r.get('ticker', '?')
        company = r.get('company_name') or r.get('name', '')
        sc      = score(r)
        grade   = r.get('grade', '')
        sector  = r.get('sector', '')
        price   = r.get('current_price') or r.get('price', '')
        upside  = r.get('analyst_upside_pct', '')
        fcf     = r.get('fcf_yield_pct', '')
        mkt     = r.get('_market', '')

        parts = [f'**{ticker}** ({mkt}) — score {sc:.0f} [{grade}]']
        if company:
            parts.append(f'  {company}')
        details = []
        if sector:   details.append(f'Sector: {sector}')
        if price:    details.append(f'Precio: ${price}')
        if upside:   details.append(f'Upside: {upside}%')
        if fcf:      details.append(f'FCF yield: {fcf}%')
        if details:
            parts.append('  ' + ' | '.join(details))
        lines.append('\n'.join(parts))

    return '\n\n'.join(lines)


@mcp.tool()
def ticker_analysis(ticker: str) -> str:
    """
    Análisis completo de un ticker: score fundamental, señales técnicas,
    confluencia con bounce y options flow, datos del portfolio tracker.
    Úsalo cuando el usuario pregunta por una acción concreta.

    Args:
        ticker: Símbolo de la acción (ej: 'AAPL', 'NESN.SW', 'LVMH.PA')
    """
    ticker = ticker.strip().upper()
    sections = [f'## Análisis: {ticker}']

    # ── Fundamental scores ─────────────────────────────────────────────────────
    fund_rows = _csv_rows('fundamental_scores.csv')
    fund = next((r for r in fund_rows if r.get('ticker', '').upper() == ticker), None)
    if fund:
        fs = fund.get('fundamental_score', '?')
        vs = fund.get('value_score', '?')
        grade = fund.get('grade', '?')
        sector = fund.get('sector', '')
        roe    = fund.get('roe_pct', '')
        margin = fund.get('profit_margin_pct', '')
        fcf    = fund.get('fcf_yield_pct', '')
        upside = fund.get('analyst_upside_pct', '')
        rr     = fund.get('risk_reward_ratio', '')
        earn_warn = fund.get('earnings_warning', '')

        lines = ['### Fundamentales']
        lines.append(f'- Score VALUE: **{vs}** [{grade}]  |  Score fundamental: {fs}')
        if sector:  lines.append(f'- Sector: {sector}')
        if roe:     lines.append(f'- ROE: {roe}%')
        if margin:  lines.append(f'- Margen neto: {margin}%')
        if fcf:     lines.append(f'- FCF yield: {fcf}%')
        if upside:  lines.append(f'- Upside analistas: {upside}%')
        if rr:      lines.append(f'- Risk/Reward: {rr}x')
        if earn_warn == 'True':
            lines.append('- ⚠️ **Earnings en <7 días** — entrada arriesgada')
        sections.append('\n'.join(lines))
    else:
        sections.append(f'### Fundamentales\n- Sin datos fundamentales para {ticker}')

    # ── Mean reversion / bounce ────────────────────────────────────────────────
    mr = _get(f'{PAGES}/docs/mean_reversion_opportunities.json', as_json=True)
    if mr:
        bounce = next((o for o in mr.get('opportunities', [])
                       if str(o.get('ticker', '')).upper() == ticker), None)
        if bounce:
            lines = ['### Señal Bounce']
            lines.append(f'- RSI: {bounce.get("rsi", "?")}  |  Confianza: {bounce.get("bounce_confidence", "?")}%')
            lines.append(f'- R/R: {bounce.get("risk_reward", "?")}  |  Dark Pool: {bounce.get("dark_pool_signal", "?")}')
            tier = bounce.get('conviction_tier', 1)
            if tier == 2:
                lines.append('- 🎯 **Tier 2 — VALUE-BACKED** (mayor convicción)')
            sections.append('\n'.join(lines))

    # ── Portfolio tracker ──────────────────────────────────────────────────────
    recs = _csv_rows('portfolio_tracker/recommendations.csv')
    ticker_recs = [r for r in recs if r.get('ticker', '').upper() == ticker]
    if ticker_recs:
        active = [r for r in ticker_recs if r.get('status') == 'ACTIVE']
        completed = [r for r in ticker_recs if r.get('status') == 'COMPLETED']
        lines = ['### Historial en Portfolio Tracker']
        lines.append(f'- {len(ticker_recs)} señales totales ({len(active)} activas, {len(completed)} completadas)')
        returns_14d = [float(r['return_14d']) for r in ticker_recs if r.get('return_14d')]
        if returns_14d:
            avg = sum(returns_14d) / len(returns_14d)
            wins = sum(1 for x in returns_14d if x > 0)
            lines.append(f'- Retorno 14d promedio: {avg:+.1f}% | Win rate: {wins}/{len(returns_14d)}')
        sections.append('\n'.join(lines))

    return '\n\n'.join(sections)


@mcp.tool()
def portfolio_status() -> str:
    """
    Estado del portfolio tracker: win rates 7d/14d/30d, posiciones activas,
    mejores y peores performers. Úsalo cuando el usuario pregunta por rendimiento.
    """
    summary = _get(f'{PAGES}/docs/portfolio_tracker/summary.json', as_json=True)
    if not summary:
        return 'Sin datos de portfolio disponibles.'

    lines = ['## Portfolio Tracker']

    overall = summary.get('overall', {})
    for period in ('7d', '14d', '30d'):
        s = overall.get(period, {})
        wr  = s.get('win_rate')
        avg = s.get('avg_return')
        cnt = s.get('count', 0)
        if wr is not None:
            emoji = '🟢' if wr >= 55 else ('🟡' if wr >= 40 else '🔴')
            lines.append(f'- {period}: {emoji} Win {wr:.1f}% | Avg {avg:+.1f}% ({cnt} señales)')

    lines.append(f'\nActivas: {summary.get("active_signals", 0)} | '
                 f'Total históricas: {summary.get("total_signals", 0)}')

    top   = summary.get('top_performers', [])
    worst = summary.get('worst_performers', [])

    if top:
        lines.append('\n**Top performers (14d):**')
        for p in top[:3]:
            ret = p.get('return_14d')
            lines.append(f'  • {p["ticker"]:8} {ret:+.1f}%' if ret else f'  • {p["ticker"]}')

    if worst:
        lines.append('\n**Peores performers (14d):**')
        for p in worst[:3]:
            ret = p.get('return_14d')
            lines.append(f'  • {p["ticker"]:8} {ret:+.1f}%' if ret else f'  • {p["ticker"]}')

    corr = summary.get('score_correlation')
    if corr is not None:
        quality = 'buena ✅' if abs(corr) > 0.3 else 'débil ⚠️'
        lines.append(f'\nCorrelación score→retorno: {corr:.3f} ({quality})')

    return '\n'.join(lines)


@mcp.tool()
def confluence_signals(min_score: int = 4) -> str:
    """
    Tickers donde Bounce + Value + Options Flow coinciden simultáneamente.
    Estos son los picks de mayor convicción del sistema.

    Args:
        min_score: Score mínimo de confluencia (1-10). Default 4.
    """
    mr       = _get(f'{PAGES}/docs/mean_reversion_opportunities.json', as_json=True)
    flow_raw = _get(f'{API}/api/unusual-flow', as_json=True)
    us_rows  = _csv_rows('value_opportunities_filtered.csv')
    eu_rows  = _csv_rows('european_value_opportunities_filtered.csv')

    map_: dict[str, dict] = {}

    def get(ticker):
        if ticker not in map_:
            map_[ticker] = {'ticker': ticker, 'bounce': False, 'value': None, 'flow': False, 'score': 0}
        return map_[ticker]

    # Bounce
    if mr:
        for o in mr.get('opportunities', []):
            if o.get('strategy') != 'Oversold Bounce': continue
            if float(o.get('rsi') or 99) >= 30: continue
            if float(o.get('bounce_confidence') or 0) < 40: continue
            t = str(o.get('ticker', ''))
            item = get(t)
            item['bounce'] = True
            item['score'] += 4 if o.get('conviction_tier') == 2 else 3

    # Value
    for r in us_rows + eu_rows:
        t = r.get('ticker', '').strip()
        if not t: continue
        sc = float(r.get('value_score') or 0)
        if sc < 50: continue
        item = get(t)
        if item['value'] is None or sc > item['value']:
            item['value'] = sc
        item['score'] += 3 if sc >= 70 else 2

    # Flow
    if flow_raw:
        for r in (flow_raw.get('results') or []):
            if r.get('signal') != 'BULLISH': continue
            if float(r.get('total_premium') or 0) < 25000: continue
            t = str(r.get('ticker', ''))
            get(t)['flow'] = True
            get(t)['score'] += 2

    hits = sorted(
        [v for v in map_.values() if v['score'] >= min_score],
        key=lambda x: x['score'], reverse=True
    )[:10]

    if not hits:
        return f'Sin confluencia de señales con score ≥ {min_score} ahora mismo.'

    lines = [f'## Signal Confluence (score ≥ {min_score})\n']
    for h in hits:
        signals = []
        if h['bounce']: signals.append('🎯 Bounce')
        if h['value']:  signals.append(f'💎 Value {h["value"]:.0f}')
        if h['flow']:   signals.append('⚡ Flow')
        lines.append(f'**{h["ticker"]}** — score {h["score"]}  ·  {" | ".join(signals)}')

    return '\n'.join(lines)


@mcp.tool()
def bounce_setups(limit: int = 10) -> str:
    """
    Setups de mean reversion (Oversold Bounce) que pasan todos los filtros
    de calidad: RSI<30, confianza≥40, R/R positivo, precio>$1.
    Ordenados por convicción.

    Args:
        limit: Máximo de resultados. Default 10.
    """
    mr = _get(f'{PAGES}/docs/mean_reversion_opportunities.json', as_json=True)
    if not mr:
        return 'Sin datos de bounce disponibles.'

    ops = mr.get('opportunities', [])
    vix = next((float(o['vix']) for o in ops if o.get('vix')), None)
    regime = mr.get('market_regime') or (ops[0].get('market_regime') if ops else None)

    passing = [o for o in ops
               if o.get('strategy') == 'Oversold Bounce'
               and float(o.get('rsi') or 99) < 30
               and float(o.get('bounce_confidence') or 0) >= 40
               and float(o.get('current_price') or 0) >= 1.0
               and (o.get('dark_pool_signal') != 'DISTRIBUTION'
                    or float(o.get('bounce_confidence') or 0) >= 60)]

    passing.sort(key=lambda o: (
        -(o.get('conviction_tier') or 1),
        -float(o.get('bounce_confidence') or 0)
    ))
    passing = passing[:limit]

    if not passing:
        ctx = f'VIX {vix:.1f}' if vix else ''
        return f'Sin bounces activos ahora mismo. {ctx} | Régimen: {regime or "?"}'

    header = f'## Bounces activos ({len(passing)})'
    if vix:
        header += f' · VIX {vix:.1f} · {regime or ""}'
    lines = [header, '']

    for o in passing:
        ticker = o.get('ticker', '?')
        rsi    = o.get('rsi', '?')
        conf   = o.get('bounce_confidence', '?')
        rr     = o.get('risk_reward', '?')
        dp     = o.get('dark_pool_signal', '')
        price  = o.get('current_price', '?')
        tier   = o.get('conviction_tier', 1)

        tag = '🎯 VALUE-BACKED' if tier == 2 else ''
        dp_tag = f' · DP: {dp}' if dp else ''
        lines.append(
            f'**{ticker}** ${price} · RSI {rsi} · conf {conf}% · R/R {rr}{dp_tag} {tag}'
        )

    return '\n'.join(lines)


if __name__ == '__main__':
    mcp.run()
