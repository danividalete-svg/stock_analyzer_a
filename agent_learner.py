#!/usr/bin/env python3
"""
AGENT LEARNER — Multi-factor statistical learning from all historical snapshots

Scans ALL history snapshots, retroactively computes actual 14-day returns
via yfinance for every ticker that appeared, then extracts evidence-based
signal quality rules — far richer than tracking only sent recommendations.

Data pipeline:
  - 23+ snapshots × ~135 tickers = 3,000+ labeled data points
  - 12 predictive features: piotroski, FCF yield, ROIC, EBIT/EV, upside, R:R, etc.
  - Regime-conditioned analysis: optimal thresholds per market state
  - Multi-factor rules: "piotroski≥7 AND FCF>5% AND upside>20%" → 58% win

Runs: Mondays 7h UTC (after agent-adaptive)
Railway cron: "0 7 * * 1"
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

PAGES_BASE   = 'https://tantancansado.github.io/stock_analyzer_a'
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
BOT_TOKEN    = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID      = os.environ.get('TELEGRAM_CHAT_ID', '')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO  = os.environ.get('GITHUB_REPO', 'tantancansado/stock_analyzer_a')
GROQ_MODEL   = 'meta-llama/llama-4-scout-17b-16e-instruct'

RETURN_DAYS  = 14          # forward return window
MIN_DAYS_AGO = 14          # snapshot must be ≥14 days old to have return data
MIN_PRICE    = 1.0         # skip penny stocks
MIN_SAMPLES  = 8           # min samples for a statistic to be shown
TOP_RULES    = 5           # top multi-factor rules to extract

# Features to analyze — numeric fields available in value_opportunities.csv
FEATURES = [
    'value_score', 'fundamental_score', 'piotroski_score',
    'fcf_yield_pct', 'ebit_ev_yield', 'roic_greenblatt',
    'analyst_upside_pct', 'risk_reward_ratio', 'interest_coverage',
    'proximity_to_52w_high', 'trend_template_score', 'ml_score',
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get(url: str, as_json=False, timeout=20):
    try:
        r = requests.get(url, timeout=timeout)
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


def _f(v):
    try:
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def gh_update_file(path: str, content: str, message: str) -> bool:
    import base64
    api = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{path}'
    headers = {'Authorization': f'token {GITHUB_TOKEN}',
               'Accept': 'application/vnd.github.v3+json'}
    r = requests.get(api, headers=headers, timeout=10)
    sha = r.json().get('sha', '') if r.status_code == 200 else ''
    payload = {
        'message': message,
        'content': base64.b64encode(content.encode()).decode(),
        'branch': 'main',
    }
    if sha:
        payload['sha'] = sha
    r = requests.put(api, headers=headers, json=payload, timeout=15)
    return r.status_code in (200, 201)


# ── Phase 1: Collect historical data ──────────────────────────────────────────

def collect_historical_data() -> list:
    """
    Fetch all history snapshots ≥14 days old and extract feature rows.
    Returns list of dicts: {ticker, date, current_price, market_regime, features...}
    """
    index = _get(f'{PAGES_BASE}/history/index.json', as_json=True)
    if not index:
        print('  ❌ Cannot fetch history index')
        return []

    today = datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=MIN_DAYS_AGO)

    # Filter snapshots that have enough history for 14d returns
    eligible = [
        s for s in index.get('snapshots', [])
        if 'value_opportunities.csv' in s.get('files', [])
        and datetime.strptime(s['date'], '%Y-%m-%d').date() <= cutoff
    ]
    print(f'  📅 {len(eligible)} eligible snapshots (≥{MIN_DAYS_AGO}d old)')

    records = []

    def fetch_snapshot(snap):
        date_str = snap['date']
        url = f'{PAGES_BASE}/history/{date_str}/value_opportunities.csv'
        text = _get(url, timeout=20)
        if not text:
            return []
        rows = list(csv.DictReader(io.StringIO(text)))
        out = []
        for row in rows:
            price = _f(row.get('current_price'))
            if price is None or price < MIN_PRICE:
                continue
            if row.get('negative_roe', '').lower() == 'true':
                continue  # hard reject — same as live system

            rec = {
                'ticker':       row.get('ticker', '').upper().strip(),
                'date':         date_str,
                'current_price': price,
                'market_regime': row.get('market_regime', 'UNKNOWN'),
                'sector':       row.get('sector', 'Unknown'),
            }
            # Extract numeric features
            for feat in FEATURES:
                rec[feat] = _f(row.get(feat))

            # Boolean flags as 0/1
            rec['trend_pass']     = 1 if row.get('trend_template_pass', '').lower() == 'true' else 0
            rec['buyback']        = 1 if row.get('buyback_active', '').lower() == 'true' else 0
            rec['earnings_warn']  = 1 if row.get('earnings_warning', '').lower() == 'true' else 0

            if rec['ticker']:
                out.append(rec)
        return out

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_snapshot, s): s['date'] for s in eligible}
        for fut in as_completed(futures):
            date = futures[fut]
            try:
                batch = fut.result()
                records.extend(batch)
                print(f'    {date}: {len(batch)} tickers')
            except Exception as e:
                print(f'    {date}: error — {e}')

    print(f'  📊 Total records collected: {len(records)}')
    return records


# ── Phase 2: Fetch actual returns via yfinance ─────────────────────────────────

def fetch_returns(records: list) -> list:
    """
    For each record, fetch the actual price 14d after the snapshot date
    and compute return_14d. Uses batch yfinance download.
    """
    import yfinance as yf

    # Group by ticker — fetch price history once per ticker
    tickers_by_name = defaultdict(list)
    for i, rec in enumerate(records):
        tickers_by_name[rec['ticker']].append(i)

    unique_tickers = list(tickers_by_name.keys())
    print(f'  📈 Fetching prices for {len(unique_tickers)} unique tickers...')

    # Date range: earliest snapshot date − 2 days to today + buffer
    dates = [datetime.strptime(r['date'], '%Y-%m-%d') for r in records]
    start = min(dates) - timedelta(days=2)
    end   = max(dates) + timedelta(days=RETURN_DAYS + 5)

    # Single batch download — one API call for all tickers (fastest, fewest errors)
    price_map = {}  # ticker → {date_str → close_price}
    try:
        df = yf.download(
            unique_tickers,
            start=start.strftime('%Y-%m-%d'),
            end=end.strftime('%Y-%m-%d'),
            auto_adjust=True, progress=False,
            timeout=60,
        )
        if not df.empty:
            close = df['Close']
            for ticker in unique_tickers:
                if ticker in close.columns:
                    s = close[ticker].dropna()
                    if not s.empty:
                        price_map[ticker] = {
                            str(idx.date()): float(v)
                            for idx, v in s.items()
                        }
    except Exception as e:
        print(f'    yfinance batch error: {e}')

    print(f'  ✅ Price data for {len(price_map)} / {len(unique_tickers)} tickers')

    # Compute returns
    labeled = []
    missing = 0
    for rec in records:
        ticker  = rec['ticker']
        snap_dt = datetime.strptime(rec['date'], '%Y-%m-%d')
        fwd_dt  = snap_dt + timedelta(days=RETURN_DAYS)

        prices = price_map.get(ticker, {})
        if not prices:
            missing += 1
            continue

        # Find closest available price on or after snap date
        p_entry = _closest_price(prices, snap_dt)
        p_exit  = _closest_price(prices, fwd_dt)

        if p_entry is None or p_exit is None or p_entry <= 0:
            missing += 1
            continue

        ret = (p_exit - p_entry) / p_entry * 100
        if abs(ret) > 150:  # sanity filter — skip extreme outliers (splits, etc.)
            continue

        rec = dict(rec)
        rec['return_14d'] = round(ret, 2)
        rec['win_14d']    = 1 if ret > 0 else 0
        labeled.append(rec)

    print(f'  🏷️  Labeled: {len(labeled)} records ({missing} missing prices)')
    return labeled


def _closest_price(prices: dict, target: datetime, max_days: int = 5):
    """Find the closest price within max_days of target date."""
    for offset in range(max_days + 1):
        key = str((target + timedelta(days=offset)).date())
        if key in prices:
            return prices[key]
    return None


# ── Phase 3: Statistical analysis ─────────────────────────────────────────────

def _win_rate_stats(records: list) -> dict:
    if not records:
        return None
    n    = len(records)
    wins = sum(r['win_14d'] for r in records)
    rets = [r['return_14d'] for r in records]
    return {
        'n':          n,
        'win_rate':   round(wins / n * 100, 1),
        'avg_return': round(sum(rets) / n, 2),
        'median_ret': round(sorted(rets)[n // 2], 2),
    }


def analyze_features(records: list) -> dict:
    """
    For each numeric feature, compute win rate by quartile.
    Returns feature → [{'range':..., 'win_rate':..., 'n':...}, ...]
    """
    results = {}
    for feat in FEATURES:
        vals = [(r[feat], r) for r in records if r.get(feat) is not None]
        if len(vals) < MIN_SAMPLES * 4:
            continue
        vals.sort(key=lambda x: x[0])
        # Quartile split
        n = len(vals)
        q = n // 4
        quartiles = [vals[:q], vals[q:2*q], vals[2*q:3*q], vals[3*q:]]
        buckets = []
        for i, qrows in enumerate(quartiles):
            if not qrows:
                continue
            stats = _win_rate_stats([r for _, r in qrows])
            lo, hi = qrows[0][0], qrows[-1][0]
            stats['range'] = f'{lo:.1f}–{hi:.1f}'
            stats['q'] = i + 1
            buckets.append(stats)
        if buckets:
            results[feat] = buckets
    return results


def feature_importance(feature_analysis: dict) -> list:
    """
    Rank features by predictive power: variance of win rates across quartiles.
    Higher variance = feature creates more separation between good/bad signals.
    """
    ranked = []
    for feat, buckets in feature_analysis.items():
        if len(buckets) < 3:
            continue
        wrs = [b['win_rate'] for b in buckets if b['n'] >= MIN_SAMPLES]
        if len(wrs) < 2:
            continue
        mean_wr = sum(wrs) / len(wrs)
        variance = sum((w - mean_wr) ** 2 for w in wrs) / len(wrs)
        best_q   = max(wrs)
        worst_q  = min(wrs)
        spread   = best_q - worst_q
        ranked.append({
            'feature':  feat,
            'spread':   round(spread, 1),
            'variance': round(variance, 2),
            'best_wr':  round(best_q, 1),
            'worst_wr': round(worst_q, 1),
        })
    ranked.sort(key=lambda x: -x['spread'])
    return ranked


def analyze_regimes(records: list) -> dict:
    """Per-regime: baseline win rate + optimal score threshold."""
    regimes = defaultdict(list)
    for r in records:
        reg = r.get('market_regime', 'UNKNOWN')
        if reg and reg != 'UNKNOWN':
            regimes[reg].append(r)

    result = {}
    for regime, rows in regimes.items():
        stats = _win_rate_stats(rows)
        if not stats or stats['n'] < MIN_SAMPLES:
            continue

        # Find best value_score threshold within this regime
        score_rows = [(r['value_score'], r) for r in rows if r.get('value_score') is not None]
        best_thresh = None
        best_wr     = 0.0
        for thresh in [50, 55, 58, 60, 62, 65, 68, 70]:
            sub = [r for v, r in score_rows if v >= thresh]
            if len(sub) < MIN_SAMPLES:
                continue
            wr = sum(r['win_14d'] for r in sub) / len(sub) * 100
            if wr > best_wr:
                best_wr     = wr
                best_thresh = thresh

        stats['optimal_score_min'] = best_thresh
        stats['optimal_wr']        = round(best_wr, 1)
        result[regime] = stats

    return result


def analyze_multifactor_rules(records: list) -> list:
    """
    Find the best multi-factor filters: combinations that maximize
    win rate while keeping N ≥ MIN_SAMPLES.
    Returns sorted list of rules.
    """
    rules = []

    # Build candidate thresholds for top features
    thresholds = {
        'piotroski_score':    [(5, None), (6, None), (7, None), (8, None)],
        'fcf_yield_pct':      [(3, None), (5, None), (8, None)],
        'ebit_ev_yield':      [(5, None), (8, None), (12, None)],
        'analyst_upside_pct': [(10, None), (20, None), (30, None)],
        'risk_reward_ratio':  [(2, None), (3, None)],
        'value_score':        [(55, None), (58, None), (60, None), (63, None), (65, None)],
        'roic_greenblatt':    [(10, None), (15, None), (20, None)],
        'interest_coverage':  [(3, None), (5, None)],
    }

    def matches(r, conditions):
        for feat, (lo, hi) in conditions.items():
            v = r.get(feat)
            if v is None:
                return False
            if lo is not None and v < lo:
                return False
            if hi is not None and v > hi:
                return False
        return True

    # 2-factor combinations
    feats = list(thresholds.keys())
    for i, f1 in enumerate(feats):
        for thresh1 in thresholds[f1]:
            for f2 in feats[i+1:]:
                for thresh2 in thresholds[f2]:
                    cond = {f1: thresh1, f2: thresh2}
                    sub = [r for r in records if matches(r, cond)]
                    if len(sub) < MIN_SAMPLES:
                        continue
                    stats = _win_rate_stats(sub)
                    if stats['win_rate'] >= 40:
                        label_parts = []
                        for feat, (lo, _) in cond.items():
                            label_parts.append(f'{feat}≥{lo}')
                        rules.append({
                            'rule':     ' AND '.join(label_parts),
                            'n':        stats['n'],
                            'win_rate': stats['win_rate'],
                            'avg_ret':  stats['avg_return'],
                        })

    # 3-factor combinations using top 4 features only (to limit combinations)
    top_feats = ['piotroski_score', 'fcf_yield_pct', 'analyst_upside_pct', 'value_score']
    for i, f1 in enumerate(top_feats):
        for thresh1 in thresholds.get(f1, []):
            for f2 in top_feats[i+1:]:
                for thresh2 in thresholds.get(f2, []):
                    for f3 in top_feats[i+2:]:
                        for thresh3 in thresholds.get(f3, []):
                            cond = {f1: thresh1, f2: thresh2, f3: thresh3}
                            sub = [r for r in records if matches(r, cond)]
                            if len(sub) < MIN_SAMPLES:
                                continue
                            stats = _win_rate_stats(sub)
                            if stats['win_rate'] >= 45:
                                label_parts = [f'{f}≥{lo}' for f, (lo, _) in cond.items()]
                                rules.append({
                                    'rule':     ' AND '.join(label_parts),
                                    'n':        stats['n'],
                                    'win_rate': stats['win_rate'],
                                    'avg_ret':  stats['avg_return'],
                                })

    # Deduplicate and sort by win_rate, break ties by n
    seen = set()
    unique = []
    for r in sorted(rules, key=lambda x: (-x['win_rate'], -x['n'])):
        if r['rule'] not in seen:
            seen.add(r['rule'])
            unique.append(r)

    return unique[:TOP_RULES * 3]  # keep more, trim later


def analyze_sectors(records: list) -> list:
    """Best and worst sectors by win rate."""
    sectors = defaultdict(list)
    for r in records:
        sec = r.get('sector', '')
        if sec:
            sectors[sec].append(r)

    result = []
    for sec, rows in sectors.items():
        stats = _win_rate_stats(rows)
        if stats and stats['n'] >= MIN_SAMPLES * 2:
            result.append({'sector': sec, **stats})

    return sorted(result, key=lambda x: -x['win_rate'])


# ── Phase 4: Build adaptive config ────────────────────────────────────────────

def build_config(records, feature_analysis, importance, regime_analysis,
                 multifactor_rules, sector_stats) -> dict:
    """Build the enhanced adaptive_config.json."""
    baseline = _win_rate_stats(records)

    # Best regime-conditioned score min
    per_regime_config = {}
    for regime, stats in regime_analysis.items():
        per_regime_config[regime] = {
            'baseline_win_rate':    stats['win_rate'],
            'optimal_score_min':    stats['optimal_score_min'],
            'n':                    stats['n'],
        }

    # Best overall score threshold
    score_rows = [(r['value_score'], r) for r in records if r.get('value_score') is not None]
    best_global_thresh = 55
    best_global_wr = 0
    for thresh in [50, 55, 58, 60, 62, 65, 68, 70]:
        sub = [r for v, r in score_rows if v >= thresh]
        if len(sub) < MIN_SAMPLES:
            continue
        wr = sum(r['win_14d'] for r in sub) / len(sub) * 100
        if wr > best_global_wr:
            best_global_wr = wr
            best_global_thresh = thresh

    return {
        'generated_at':          datetime.now(timezone.utc).isoformat(),
        'source':                 'agent_learner',
        'total_data_points':      len(records),
        'baseline_win_rate':      baseline['win_rate'] if baseline else None,
        'baseline_avg_return':    baseline['avg_return'] if baseline else None,
        'recommended_score_min':  best_global_thresh,
        'top_predictive_features': importance[:8],
        'per_regime_config':      per_regime_config,
        'high_conviction_rules':  multifactor_rules[:TOP_RULES],
        'sector_ranking':         sector_stats[:10],
        'worst_sectors':          sector_stats[-5:] if len(sector_stats) >= 5 else [],
        'feature_analysis':       {
            k: v for k, v in feature_analysis.items()
            if k in [f['feature'] for f in importance[:6]]
        },
    }


# ── Phase 5: Groq narrative ────────────────────────────────────────────────────

def groq_narrative(summary: dict) -> str:
    if not GROQ_API_KEY:
        return ''
    prompt = f"""Eres un analista cuantitativo. Resume estos hallazgos del análisis estadístico del sistema de trading en 3 frases directas en español. Sé muy específico con los números. Sin introducción.

{json.dumps(summary, ensure_ascii=False, indent=2)[:1500]}

Solo 3 frases, sin título ni bullet points."""
    try:
        r = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {GROQ_API_KEY}',
                     'Content-Type': 'application/json'},
            json={'model': GROQ_MODEL,
                  'messages': [{'role': 'user', 'content': prompt}],
                  'max_tokens': 200, 'temperature': 0.2},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f'(Error Groq: {e})'


# ── Main ───────────────────────────────────────────────────────────────────────

def run():
    now = datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')
    print(f'🧠 Agent Learner — {now}')

    # ── Phase 1: Collect ──
    print('Phase 1: Collecting historical data...')
    records = collect_historical_data()
    if len(records) < 50:
        tg_send(f'⚠️ <b>Agent Learner:</b> Solo {len(records)} registros — insuficiente')
        return

    # ── Phase 2: Fetch returns ──
    print('Phase 2: Fetching actual 14d returns...')
    labeled = fetch_returns(records)
    if len(labeled) < 50:
        tg_send(f'⚠️ <b>Agent Learner:</b> Solo {len(labeled)} registros con retornos')
        return

    print(f'  ✅ Working dataset: {len(labeled)} labeled data points')

    # ── Phase 3: Analysis ──
    print('Phase 3: Statistical analysis...')
    feature_analysis = analyze_features(labeled)
    importance       = feature_importance(feature_analysis)
    regime_analysis  = analyze_regimes(labeled)
    rules            = analyze_multifactor_rules(labeled)
    sector_stats     = analyze_sectors(labeled)

    print(f'  Features ranked: {len(importance)}')
    print(f'  Multi-factor rules found: {len(rules)}')
    print(f'  Regimes analyzed: {len(regime_analysis)}')

    # ── Phase 4: Config ──
    config = build_config(
        labeled, feature_analysis, importance,
        regime_analysis, rules, sector_stats,
    )

    if GITHUB_TOKEN:
        ok = gh_update_file(
            'docs/learner_config.json',
            json.dumps(config, indent=2, ensure_ascii=False),
            f'agent-learner: {len(labeled)} data points analyzed',
        )
        print(f'  learner_config.json: {"✅" if ok else "❌"}')

    # ── Phase 5: Report ──
    baseline = config['baseline_win_rate']
    best_rule = rules[0] if rules else None

    # Narrative summary for Groq
    groq_summary = {
        'puntos_analizados': len(labeled),
        'win_rate_baseline': baseline,
        'score_min_recomendado': config['recommended_score_min'],
        'feature_mas_predictiva': importance[0] if importance else None,
        'mejor_regla_multifactor': best_rule,
        'mejores_sectores': [s['sector'] for s in sector_stats[:3]],
        'peores_sectores': [s['sector'] for s in sector_stats[-3:]],
    }
    narrative = groq_narrative(groq_summary)

    # ── Build Telegram message ──
    lines = [
        '🔬 <b>Agent Learner — Análisis Estadístico</b>',
        f'<code>{now}</code>  ·  <b>{len(labeled)}</b> datos reales  ·  {len(importance)} features',
        '─────────────────────',
        '',
        f'📊 <b>Baseline win rate:</b> {baseline:.1f}%  ·  Score mín recomendado: <b>{config["recommended_score_min"]}</b>',
        '',
    ]

    # Feature importance top 5
    lines.append('<b>Features más predictivas</b>')
    for feat_info in importance[:5]:
        bar_len = int(feat_info['spread'] / 3)
        bar = '█' * min(bar_len, 12)
        lines.append(
            f'  <code>{feat_info["feature"][:22]:22s}</code> {bar} '
            f'{feat_info["worst_wr"]:.0f}%→{feat_info["best_wr"]:.0f}%'
        )

    # Per-regime config
    if regime_analysis:
        lines.append('')
        lines.append('<b>Filtros por Régimen</b>')
        for regime, stats in sorted(regime_analysis.items(), key=lambda x: -x[1]['win_rate']):
            icon = '🟢' if stats['win_rate'] >= 35 else ('🟡' if stats['win_rate'] >= 20 else '🔴')
            thresh = stats.get('optimal_score_min', '?')
            lines.append(
                f'  {icon} <b>{regime}</b>: {stats["win_rate"]:.1f}% win '
                f'(score≥{thresh} óptimo)  n={stats["n"]}'
            )

    # Top multi-factor rules
    if rules:
        lines.append('')
        lines.append('<b>Reglas de Alta Convicción</b>')
        for rule in rules[:TOP_RULES]:
            lines.append(
                f'  🎯 {rule["win_rate"]:.1f}% win · n={rule["n"]}'
                f'\n     <code>{rule["rule"]}</code>'
            )

    # Sectors
    if sector_stats:
        top3  = ' · '.join(f'{s["sector"]} <b>{s["win_rate"]:.0f}%</b>' for s in sector_stats[:3])
        bot3  = ' · '.join(f'{s["sector"]} {s["win_rate"]:.0f}%' for s in sector_stats[-3:])
        lines.append('')
        lines.append(f'✅ <b>Sectores:</b> {top3}')
        lines.append(f'❌ <b>Evitar:</b> {bot3}')

    if narrative:
        lines.append('')
        lines.append(f'<i>{narrative}</i>')

    tg_send('\n'.join(lines))
    print(f'✅ Done — best rule: {best_rule["rule"] if best_rule else "none"} ({best_rule["win_rate"]:.1f}% win)' if best_rule else '✅ Done')


if __name__ == '__main__':
    run()
