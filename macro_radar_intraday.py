#!/usr/bin/env python3
"""
MACRO RADAR INTRADAY — Lightweight updater
Runs every 5 min during US market hours (Mon-Fri 13:30-21:00 UTC).

Differences vs macro_radar.py (full):
  - No Groq AI narrative (preserves last full-run narrative)
  - No historical analogs (preserves from last full run)
  - Detects intraday ALERTS: VIX spike, oil surge, regime change, threshold cross
  - Sends Telegram ONLY on meaningful signals
  - Exits 0 if significant change (workflow commits), 2 if no change (skip commit)

Triggers Telegram alert when:
  - Regime changes (e.g. WATCH → STRESS)
  - VIX jumps >10% intraday (vs yesterday close)
  - Oil moves >3% intraday
  - Composite crosses ±1.5 vs last saved value
  - Enters ALERT or CRISIS for the first time today
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Re-use all scoring functions from macro_radar
from macro_radar import (
    _fetch, _percentile, _get_regime,
    _score_vix, _score_yield_curve, _score_ratio,
    _score_oil, _score_dollar, _score_yen, _score_breadth,
    _score_skew, _score_vvix,
    SIGNALS, DOCS,
)

OUT_PATH    = DOCS / "macro_radar.json"
PLAN_PATH   = DOCS / "cerebro_daily_plan.json"
ALERT_PATH  = DOCS / "macro_radar_intraday_alerts.json"
TODAY       = datetime.utcnow().strftime('%Y-%m-%d')


def _load_previous() -> dict:
    if OUT_PATH.exists():
        try:
            with open(OUT_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _is_market_open() -> bool:
    """Rough check: Mon-Fri 9:30am-4pm Eastern."""
    eastern = datetime.now(timezone(timedelta(hours=-4)))
    wd   = eastern.weekday()
    hour = eastern.hour + eastern.minute / 60
    return (wd < 5) and (9.5 <= hour < 16.0)


def run_intraday():
    print(f"=== MACRO RADAR INTRADAY === {datetime.utcnow().strftime('%H:%M')} UTC")

    prev = _load_previous()
    prev_composite = prev.get('composite_score', 0.0)
    prev_regime    = prev.get('regime', {}).get('name', 'WATCH')
    prev_signals   = prev.get('signals', {})
    prev_narrative = prev.get('ai_narrative')
    prev_analogs   = prev.get('historical_analogs', [])
    prev_risks     = prev.get('systemic_risks', [])

    results = {}
    errors  = []

    def _try(key, fn, *args):
        try:
            r = fn(*args)
            if r:
                results[key] = r
                print(f"  {key:20s}: {r.get('score',0):+.1f}  ({r.get('interpretation','')})")
        except Exception as e:
            errors.append(key)
            print(f"  {key:20s}: ERROR {e}")

    # ── Fetch all 15 signals (fast: ~30s total) ───────────────────────────
    df_vix  = _fetch('^VIX', 400)
    if df_vix is not None:
        _try('vix', _score_vix, df_vix)

    df10 = _fetch('^TNX', 400); df2 = _fetch('^IRX', 400)
    if df10 is not None and df2 is not None:
        _try('yield_curve', _score_yield_curve, df10, df2)

    df_hyg = _fetch('HYG', 400); df_lqd = _fetch('LQD', 400)
    if df_hyg is not None and df_lqd is not None:
        _try('credit', _score_ratio, df_hyg, df_lqd, 'credit')

    df_hg = _fetch('HG=F', 400); df_gld = _fetch('GLD', 400)
    if df_hg is not None and df_gld is not None:
        _try('copper_gold', _score_ratio, df_hg, df_gld, 'copper_gold')

    df_spy = _fetch('SPY', 400)
    if df_gld is not None and df_spy is not None:
        _try('gold_spy', _score_ratio, df_gld, df_spy, 'gold_spy')

    df_oil = _fetch('CL=F', 400)
    if df_oil is not None:
        _try('oil', _score_oil, df_oil)

    df_ita = _fetch('ITA', 400)
    if df_ita is not None and df_spy is not None:
        _try('defense', _score_ratio, df_ita, df_spy, 'defense')

    df_dxy = _fetch('DX-Y.NYB', 400)
    if df_dxy is not None:
        _try('dollar', _score_dollar, df_dxy)

    df_jpy = _fetch('USDJPY=X', 400)
    if df_jpy is not None:
        _try('yen', _score_yen, df_jpy)

    if df_spy is not None:
        _try('breadth', _score_breadth, df_spy)

    df_skew = _fetch('^SKEW', 400)
    if df_skew is not None:
        _try('skew', _score_skew, df_skew)

    df_vvix = _fetch('^VVIX', 400)
    if df_vvix is not None:
        _try('vvix', _score_vvix, df_vvix)

    df_kre = _fetch('KRE', 400)
    if df_kre is not None and df_spy is not None:
        _try('regional_banks', _score_ratio, df_kre, df_spy, 'regional_banks')

    df_iwm = _fetch('IWM', 400)
    if df_iwm is not None and df_spy is not None:
        _try('small_cap', _score_ratio, df_iwm, df_spy, 'small_cap')

    df_tip = _fetch('TIP', 400); df_tlt = _fetch('TLT', 400)
    if df_tip is not None and df_tlt is not None:
        _try('real_yields', _score_ratio, df_tip, df_tlt, 'real_yields')

    if not results:
        print("No signals fetched — aborting")
        sys.exit(2)

    # ── Score & regime ────────────────────────────────────────────────────
    max_possible = len(results) * 2
    composite    = sum(v.get('score', 0) for v in results.values())
    regime       = _get_regime(composite)
    regime_name  = regime['name']

    composite_pct = (composite + max_possible) / (2 * max_possible) * 100

    print(f"\nComposite: {composite:.1f}/{max_possible} → {regime_name}")

    # ── Enrich with metadata ──────────────────────────────────────────────
    enriched = {}
    for key, data in results.items():
        sig_def = SIGNALS.get(key, {})
        enriched[key] = {**data, 'label': sig_def.get('label', key),
                         'description': sig_def.get('description', '')}

    # ── Detect significant changes ────────────────────────────────────────
    composite_delta  = abs(composite - prev_composite)
    regime_changed   = regime_name != prev_regime

    # Intraday VIX spike (vs yesterday's close in prev signals)
    vix_now   = results.get('vix', {}).get('current', 0) or 0
    vix_prev  = prev_signals.get('vix', {}).get('current', vix_now) or vix_now
    vix_spike = vix_prev > 0 and (vix_now - vix_prev) / vix_prev > 0.10  # +10%

    # Intraday oil surge
    oil_now   = results.get('oil', {}).get('current', 0) or 0
    oil_prev  = prev_signals.get('oil', {}).get('current', oil_now) or oil_now
    oil_surge = oil_prev > 0 and abs((oil_now - oil_prev) / oil_prev) > 0.03  # ±3%

    danger_regime    = regime_name in ('ALERT', 'CRISIS')
    was_safe         = prev_regime in ('CALM', 'WATCH')
    new_danger       = danger_regime and was_safe

    significant = (
        regime_changed or
        composite_delta >= 1.5 or
        vix_spike or
        oil_surge or
        new_danger
    )

    print(f"  Δcomposite={composite_delta:.1f}  regime_changed={regime_changed}"
          f"  vix_spike={vix_spike}  oil_surge={oil_surge}  significant={significant}")

    # ── Build output — preserve AI narrative + analogs from full run ──────
    output = {
        'timestamp':        datetime.utcnow().isoformat(),
        'date':             TODAY,
        'intraday_update':  True,
        'regime':           regime,
        'composite_score':  round(composite, 2),
        'composite_pct':    round(composite_pct, 1),
        'max_score':        max_possible,
        'signals':          enriched,
        'errors':           errors,
        'ai_narrative':     prev_narrative,   # preserved from full run
        'historical_analogs': prev_analogs,   # preserved from full run
        'systemic_risks':   prev_risks,       # preserved from full run
        'signal_order': [
            'vix', 'yield_curve', 'credit', 'copper_gold', 'gold_spy',
            'oil', 'defense', 'dollar', 'yen', 'breadth',
            'skew', 'vvix', 'regional_banks', 'small_cap', 'real_yields',
        ],
    }

    with open(OUT_PATH, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"Saved macro_radar.json  ({regime_name}  {composite:+.1f})")

    # ── Telegram alert (only on significant change) ───────────────────────
    if significant:
        _send_intraday_alert(
            regime_name, prev_regime, regime_changed,
            composite, max_possible,
            vix_now, vix_prev, vix_spike,
            oil_now, oil_prev, oil_surge,
            enriched,
        )

    # ── Update daily plan macro plays (rule-based, no Groq) ───────────────
    _refresh_daily_plan_macro_plays(enriched, composite, regime_name)

    # ── Save alert log ────────────────────────────────────────────────────
    alert_log = []
    if ALERT_PATH.exists():
        try:
            with open(ALERT_PATH) as f:
                alert_log = json.load(f)
        except Exception:
            pass
    if significant:
        alert_log.append({
            'ts': datetime.utcnow().isoformat(),
            'regime': regime_name, 'prev_regime': prev_regime,
            'composite': composite, 'delta': composite_delta,
            'vix_spike': vix_spike, 'oil_surge': oil_surge,
        })
        alert_log = alert_log[-50:]  # keep last 50
        with open(ALERT_PATH, 'w') as f:
            json.dump(alert_log, f, indent=2)

    # Exit 0 = significant change → workflow will commit
    # Exit 2 = no change → workflow skips commit
    sys.exit(0 if significant else 2)


def _send_intraday_alert(
    regime: str, prev_regime: str, regime_changed: bool,
    composite: float, max_possible: int,
    vix_now: float, vix_prev: float, vix_spike: bool,
    oil_now: float, oil_prev: float, oil_surge: bool,
    signals: dict,
):
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id   = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not bot_token or not chat_id:
        print("  Telegram: no credentials, skipping")
        return

    EMOJI = {'CALM': '🟢', 'WATCH': '🟡', 'STRESS': '🟠', 'ALERT': '🔴', 'CRISIS': '🚨'}
    e = EMOJI.get(regime, '⚪')
    now_str = datetime.utcnow().strftime('%H:%M UTC')

    lines = [f"⚡ <b>Macro Radar Intraday</b>  {now_str}"]

    if regime_changed:
        lines.append(f"{EMOJI.get(prev_regime,'⚪')} {prev_regime} → {e} <b>{regime}</b>  ({composite:+.1f}/{max_possible})")
    else:
        lines.append(f"{e} <b>{regime}</b>  ({composite:+.1f}/{max_possible})")

    if vix_spike:
        vix_chg = (vix_now - vix_prev) / vix_prev * 100
        lines.append(f"🔺 VIX <b>{vix_now:.1f}</b>  ({vix_chg:+.0f}% intraday)")

    if oil_surge:
        oil_chg = (oil_now - oil_prev) / oil_prev * 100
        lines.append(f"🛢 Oil <b>${oil_now:.1f}</b>  ({oil_chg:+.1f}% intraday)")

    # Worst 2 signals
    worst = sorted(signals.items(), key=lambda x: x[1].get('score', 0))[:2]
    for k, v in worst:
        if v.get('score', 0) < -0.5:
            lines.append(f"  • {v.get('label', k)}: {v.get('score', 0):+.1f} — {v.get('interpretation', '')[:50]}")

    text = '\n'.join(lines)
    try:
        import urllib.request
        payload = json.dumps({
            'chat_id': chat_id, 'text': text,
            'parse_mode': 'HTML', 'disable_web_page_preview': True,
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data=payload, headers={'Content-Type': 'application/json'}
        )
        urllib.request.urlopen(req, timeout=10)
        print(f"  Telegram: intraday alert sent ({regime})")
    except Exception as e:
        print(f"  Telegram: failed: {e}")


def _refresh_daily_plan_macro_plays(signals: dict, composite: float, regime_name: str):
    """Re-evaluate rule-based macro plays without calling Groq."""
    if not PLAN_PATH.exists():
        return

    try:
        with open(PLAN_PATH) as f:
            plan = json.load(f)
    except Exception:
        return

    try:
        import yfinance as yf
        tyx = yf.download('^TYX', period='2d', interval='1d', progress=False, auto_adjust=True)
        yield_30yr = float(tyx['Close'].dropna().iloc[-1]) if not tyx.empty else 0.0
    except Exception:
        yield_30yr = 0.0

    vix_val   = signals.get('vix', {}).get('current', 0) or 0
    gold_pct  = signals.get('gold_spy', {}).get('percentile', 50) or 50
    cu_pct    = signals.get('copper_gold', {}).get('percentile', 50) or 50
    oil_pct   = signals.get('oil', {}).get('percentile', 50) or 50
    oil_chg20 = signals.get('oil', {}).get('change_20d', 0) or 0
    vvix_pct  = signals.get('vvix', {}).get('percentile', 50) or 50
    sc_pct    = signals.get('small_cap', {}).get('percentile', 50) or 50
    cr_score  = signals.get('credit', {}).get('score', 0) or 0

    plays = []
    if yield_30yr >= 4.9:
        score = min(95, int(70 + (yield_30yr - 4.5) * 50))
        plays.append({'instrument': 'TLT / VGLT', 'direction': 'LONG',
                      'thesis': f'30yr yield en {yield_30yr:.2f}% — zona históricamente atractiva para bonos largos',
                      'historical': 'TLT +18% promedio cuando 30yr >5% y revierte en 6m',
                      'risk': 'Inflación persistente puede llevar yields a 5.5%',
                      'timeframe': '3-6 meses', 'score': score})

    if gold_pct > 75 and vix_val > 22:
        plays.append({'instrument': 'GLD / GDX', 'direction': 'LONG',
                      'thesis': f'Oro superando al mercado (p{gold_pct:.0f}) con VIX elevado — refugio activo',
                      'historical': 'GLD +15% promedio en entornos VIX>25 sostenido',
                      'risk': 'Subida de tipos reales puede frenar el oro',
                      'timeframe': '1-3 meses', 'score': 80})

    if cu_pct < 20:
        plays.append({'instrument': 'XLP / XLV / XLU', 'direction': 'LONG',
                      'thesis': f'Cobre/Oro en p{cu_pct:.0f} — mercado descontando desaceleración, defensivos favorecidos',
                      'historical': 'XLP supera S&P +12% en los 6m siguientes a Copper/Gold < p20',
                      'risk': 'Rebote económico revertiría rotación',
                      'timeframe': '2-4 meses', 'score': 75})

    if oil_pct > 90 and oil_chg20 > 25:
        plays.append({'instrument': 'XLE', 'direction': 'LONG',
                      'thesis': f'Petróleo en p{oil_pct:.0f} con +{oil_chg20:.0f}% en 20d — componente geopolítico real',
                      'historical': 'XLE +8% adicional en picos geopolíticos de 3+ semanas',
                      'risk': 'Resolución diplomática o recesión colapsaría demanda',
                      'timeframe': '2-8 semanas', 'score': 70})

    if vvix_pct > 85 and vix_val < 35:
        plays.append({'instrument': 'UVXY (small)', 'direction': 'LONG',
                      'thesis': f'VVIX en p{vvix_pct:.0f} con VIX moderado — spike de volatilidad inminente',
                      'historical': 'VIX sube >30% en las 2 semanas siguientes al 80% de las veces con VVIX >p85',
                      'risk': 'Theta decay si spike no materializa en <2 semanas',
                      'timeframe': '1-2 semanas', 'score': 65})

    if sc_pct < 25 and cr_score >= 0:
        plays.append({'instrument': 'IWM (contrarian)', 'direction': 'LONG',
                      'thesis': f'Small caps en p{sc_pct:.0f} con crédito sano — sobreventa táctica',
                      'historical': 'IWM +11% vs SPY en los 3m siguientes cuando cr>0 y sc<p25',
                      'risk': 'Liquidez concentrándose en large caps puede persistir',
                      'timeframe': '1-3 meses', 'score': 60})

    if regime_name in ('ALERT', 'CRISIS'):
        plays.append({'instrument': 'SGOV / BIL', 'direction': 'LONG',
                      'thesis': f'Régimen {regime_name} — T-bills con yield >5% como refugio de capital',
                      'historical': 'Cash outperforms en CRISIS: SPY -15% promedio desde inicio CRISIS',
                      'risk': 'Coste de oportunidad si recuperación rápida',
                      'timeframe': 'Indefinido', 'score': 85})

    plays.sort(key=lambda x: x['score'], reverse=True)

    plan['macro_plays']       = plays
    plan['macro_regime']      = regime_name
    plan['composite_score']   = round(composite, 2)
    plan['intraday_refresh']  = datetime.utcnow().isoformat()

    with open(PLAN_PATH, 'w') as f:
        json.dump(plan, f, indent=2, default=str)
    print(f"Refreshed daily plan macro plays ({len(plays)} plays)")


if __name__ == '__main__':
    run_intraday()
