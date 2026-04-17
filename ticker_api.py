#!/usr/bin/env python3
"""
TICKER ANALYZER API - Flask backend para el dashboard
Estrategia CACHE-FIRST:
  1. Si el ticker está en los CSVs del pipeline diario → respuesta completa en <1s
  2. Si no → análisis live con yfinance (funciona en local, puede fallar en Railway)

Ejecutar:
    python3 ticker_api.py

API:
    GET /api/analyze/<ticker>           → análisis completo en JSON
    GET /api/health                     → estado del servidor
    GET /api/tickers                    → lista de tickers en cache
    GET /api/value-opportunities        → VALUE picks (US)
    GET /api/eu-value-opportunities     → VALUE picks (EU)
    GET /api/global-value               → VALUE picks (Global: BR/KR/JP/HK)
    GET /api/momentum-opportunities     → Momentum picks
    GET /api/sector-rotation            → Sector rotation data
    GET /api/options-flow               → Options flow data
    GET /api/mean-reversion             → Mean reversion opportunities
    GET /api/recurring-insiders         → Recurring insider buys
    GET /api/portfolio-tracker          → Portfolio tracker summary
    GET /api/market-regime              → US + EU market regime
    GET /api/backtest                   → Latest backtest results
    GET /api/theses/<ticker>            → Investment thesis for ticker
    GET /api/search?q=<query>          → Autocomplete: ticker/empresa

Puerto: 5002 (local) | PORT env var (Railway)

PRINCIPIO: null si no hay dato, nunca 50 inventado.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import pandas as pd
import json
import jwt as pyjwt
import time
import re
import os
import logging
from pathlib import Path
from datetime import datetime

from ticker_api_config import load_runtime_config
from ticker_api_data import build_dataset_summary, load_csv_file, load_json_file, load_static_datasets

_logger = logging.getLogger(__name__)

app = Flask(__name__)

_RUNTIME = load_runtime_config()
_IS_PRODUCTION = _RUNTIME.is_production
_DEFAULT_HOURLY_LIMIT = _RUNTIME.default_hourly_limit
_DEFAULT_DAILY_LIMIT = _RUNTIME.default_daily_limit
_RATE_LIMIT_STORAGE_URI = _RUNTIME.rate_limit_storage_uri
_AUTH_BYPASS_ENABLED = _RUNTIME.auth_bypass_enabled
_REQUIRE_SUPABASE_AUTH = _RUNTIME.require_supabase_auth
_PUBLIC_PATHS = set(_RUNTIME.public_paths)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[f"{_DEFAULT_DAILY_LIMIT} per day", f"{_DEFAULT_HOURLY_LIMIT} per hour"],
    storage_uri=_RATE_LIMIT_STORAGE_URI,
)

_CORS_ORIGINS = _RUNTIME.cors_origins
CORS(app, origins=_CORS_ORIGINS, supports_credentials=True)

if _RATE_LIMIT_STORAGE_URI == "memory://" and _IS_PRODUCTION:
    _logger.warning(
        "RATE_LIMIT_STORAGE_URI usa memory:// en produccion; con multiples workers los limites no seran consistentes."
    )
if _AUTH_BYPASS_ENABLED:
    _logger.warning("AUTH_BYPASS activo; la API permitira acceso sin JWT.")


# ─────────────────────────────────────────────────────────────────────────────
# JWT AUTH (Supabase — JWKS, works with ECC P-256 and legacy HS256)
# ─────────────────────────────────────────────────────────────────────────────

SUPABASE_URL = _RUNTIME.supabase_url
_jwks_client = _RUNTIME.jwks_client
_SUPABASE_JWT_SECRET = os.environ.get('SUPABASE_JWT_SECRET', '')

@app.before_request
def _check_auth():
    """Verify Supabase JWT — tries JWKS (ES256) first, falls back to JWT secret (HS256).
    Local bypass requires AUTH_BYPASS=true; production fails closed by default.
    """
    if request.path in _PUBLIC_PATHS or request.method == "OPTIONS":
        return
    if _AUTH_BYPASS_ENABLED:
        return
    if not _jwks_client and not _SUPABASE_JWT_SECRET:
        if _REQUIRE_SUPABASE_AUTH:
            _logger.error("Auth requerida pero SUPABASE_URL/SUPABASE_JWT_SECRET no configurados.")
            return jsonify({'error': 'Auth misconfigured'}), 503
        return
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    if not token:
        return jsonify({'error': 'Unauthorized'}), 401
    verified = False
    if _jwks_client:
        try:
            signing_key = _jwks_client.get_signing_key_from_jwt(token)
            pyjwt.decode(token, signing_key.key,
                         algorithms=['ES256', 'RS256'],
                         audience='authenticated')
            verified = True
        except Exception:
            pass
    if not verified and _SUPABASE_JWT_SECRET:
        try:
            pyjwt.decode(token, _SUPABASE_JWT_SECRET,
                         algorithms=['HS256'],
                         audience='authenticated')
            verified = True
        except Exception:
            pass
    if not verified:
        return jsonify({'error': 'Invalid token'}), 401

# ─────────────────────────────────────────────────────────────────────────────
# CARGA DE CACHE AL ARRANCAR
# ─────────────────────────────────────────────────────────────────────────────

def _load_csv(path, index_col='ticker'):
    return load_csv_file(path, index_col=index_col, logger=_logger)


def _load_json(path):
    return load_json_file(path, logger=_logger)


_DATASETS = load_static_datasets(logger=_logger)
DOCS = _DATASETS.docs
DF_5D = _DATASETS.df_5d
DF_ML = _DATASETS.df_ml
DF_FUND_US = _DATASETS.df_fund_us
DF_FUND_EU = _DATASETS.df_fund_eu
DF_FUND = _DATASETS.df_fund
DF_SCORES = _DATASETS.df_scores
DF_INSIDERS = _DATASETS.df_insiders
DF_REVERSION = _DATASETS.df_reversion
DF_OPTIONS = _DATASETS.df_options
DF_PRICES = _DATASETS.df_prices
DF_POSITIONS = _DATASETS.df_positions
DF_INDUSTRIES = _DATASETS.df_industries
TICKER_CACHE = _DATASETS.ticker_cache

print(build_dataset_summary(_DATASETS))


# ─────────────────────────────────────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────────────────────────────────────

def _sf(val, default=None):
    """safe_float: convierte a float, devuelve default si NaN/None/error."""
    try:
        v = float(val)
        return default if pd.isna(v) else v
    except (TypeError, ValueError):
        return default


def _validate_ticker(ticker):
    return bool(re.match(r'^[A-Z0-9.\-]{1,10}$', ticker.upper())) if ticker else False


def _get_tier(score):
    if score is None:  return None, None
    if score >= 80:    return "🔥", "LEGENDARY"
    if score >= 70:    return "💎", "ELITE"
    if score >= 60:    return "✅", "EXCELLENT"
    if score >= 50:    return "📊", "GOOD"
    if score >= 40:    return "⚡", "AVERAGE"
    return "⚠️", "WEAK"


def _row(df, ticker):
    """Devuelve la fila de un df para el ticker, o None si no existe."""
    if df.empty or ticker not in df.index:
        return None
    return df.loc[ticker]


def _calc_base(vcp, ml, fund):
    """Calcula contribuciones y base score. None donde no hay datos reales."""
    vcp_c  = round(vcp  * 0.40, 1) if vcp  is not None else None
    ml_c   = round(ml   * 0.30, 1) if ml   is not None else None
    fund_c = round(fund * 0.30, 1) if fund is not None else None
    available = [c for c in [vcp_c, ml_c, fund_c] if c is not None]
    base = round(sum(available), 1) if available else None
    return base, vcp_c, ml_c, fund_c


def _notna_str(row, key, fallback=''):
    """Lee un campo string de un pandas Series; devuelve fallback si NaN."""
    val = row.get(key, fallback)
    try:
        if pd.isna(val):
            return fallback
    except (TypeError, ValueError):
        pass
    return str(val) if val is not None else fallback


# ─────────────────────────────────────────────────────────────────────────────
# ANÁLISIS DESDE CACHE (rápido, funciona en Railway)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_health_earnings(rfund):
    """Parse health_details and earnings_details JSON strings from fundamental_scores row."""
    result = {
        "current_ratio": None, "operating_margin_pct": None,
        "debt_to_equity_fund": None, "profit_margin_pct": None,
        "fcf_per_share": None,
    }
    if rfund is None:
        return result
    import ast as _ast
    try:
        hd = rfund.get('health_details')
        if hd is not None and not (isinstance(hd, float) and pd.isna(hd)):
            if isinstance(hd, str):
                try:
                    hd_dict = _ast.literal_eval(hd)
                except (ValueError, SyntaxError):
                    try:
                        hd_dict = json.loads(hd)
                    except Exception:
                        hd_dict = {}
            elif isinstance(hd, dict):
                hd_dict = hd
            else:
                hd_dict = {}
            result["current_ratio"]        = _sf(hd_dict.get('current_ratio'))
            result["operating_margin_pct"] = _sf(hd_dict.get('operating_margin_pct'))
            result["debt_to_equity_fund"]  = _sf(hd_dict.get('debt_to_equity'))
    except Exception:
        pass
    try:
        ed = rfund.get('earnings_details')
        if ed is not None and not (isinstance(ed, float) and pd.isna(ed)):
            if isinstance(ed, str):
                try:
                    ed_dict = _ast.literal_eval(ed)
                except (ValueError, SyntaxError):
                    try:
                        ed_dict = json.loads(ed)
                    except Exception:
                        ed_dict = {}
            elif isinstance(ed, dict):
                ed_dict = ed
            else:
                ed_dict = {}
            result["profit_margin_pct"] = _sf(ed_dict.get('profit_margin_pct'))
    except Exception:
        pass
    result["fcf_per_share"] = _sf(rfund.get('fcf_per_share'))
    return result


def _analyze_from_cache(ticker):
    """Construye la respuesta completa usando los CSVs del pipeline diario.
    Principio: null donde no hay dato, nunca valores inventados."""
    r5d     = _row(DF_5D, ticker)
    rml     = _row(DF_ML, ticker)
    rfund   = _row(DF_FUND, ticker)
    rscores = _row(DF_SCORES, ticker)
    rprice  = _row(DF_PRICES, ticker)
    tc      = TICKER_CACHE.get(ticker, {})

    # ── VCP score ──────────────────────────────────────────────────────────
    vcp_score = _sf(r5d.get('vcp_score') if r5d is not None else None)
    if vcp_score is None and rscores is not None:
        vcp_score = _sf(rscores.get('vcp_score'))

    # ── ML score ──────────────────────────────────────────────────────────
    ml_score = _sf(r5d.get('ml_score') if r5d is not None else None)
    if ml_score is None and rml is not None:
        ml_score = _sf(rml.get('ml_score'))
    if ml_score is None and rscores is not None:
        ml_score = _sf(rscores.get('ml_score'))

    # ── Fundamental score ─────────────────────────────────────────────────
    fund_score = _sf(r5d.get('fundamental_score') if r5d is not None else None)
    if fund_score is None and rfund is not None:
        fund_score = _sf(rfund.get('fundamental_score'))
    if fund_score is None and rscores is not None:
        fund_score = _sf(rscores.get('fundamental_score'))

    # ── Final score (del pipeline — dato genuino) ─────────────────────────
    final_score = None
    if r5d is not None:
        _fs = r5d.get('super_score_5d')
        if _fs is None or (isinstance(_fs, float) and pd.isna(_fs)):
            _fs = r5d.get('super_score_ultimate')
        final_score = _sf(_fs)
    if final_score is None and rscores is not None:
        final_score = _sf(rscores.get('super_score_ultimate'))
    # Si tampoco hay CSV score, calcular desde componentes disponibles
    if final_score is None:
        available = []
        if vcp_score is not None:  available.append(vcp_score * 0.40)
        if ml_score  is not None:  available.append(ml_score  * 0.30)
        if fund_score is not None: available.append(fund_score * 0.30)
        final_score = round(sum(available), 1) if available else None

    tier_emoji, tier_label = _get_tier(final_score)

    # ── Campos 5D ─────────────────────────────────────────────────────────
    if r5d is not None:
        insiders_score  = _sf(r5d.get('insiders_score'), 0.0)
        inst_score      = _sf(r5d.get('institutional_score'), 0.0)
        num_whales      = _sf(r5d.get('num_whales'), 0)
        top_whales      = _notna_str(r5d, 'top_whales')
        sector_name     = _notna_str(r5d, 'sector_name', tc.get('sector', 'Unknown'))
        sector_score    = _sf(r5d.get('sector_score'))
        sector_momentum = _notna_str(r5d, 'sector_momentum', 'stable')
        tier_boost      = _sf(r5d.get('tier_boost'), 0)
        price_target    = _sf(r5d.get('price_target'))
        upside_pct      = _sf(r5d.get('upside_percent'))
        entry_score     = _sf(r5d.get('entry_score'))
        pe_ratio        = _sf(r5d.get('pe_ratio'))
        peg_ratio       = _sf(r5d.get('peg_ratio'))
        fcf_yield       = _sf(r5d.get('fcf_yield'))
        roe             = _sf(r5d.get('roe'))
        rev_growth      = _sf(r5d.get('revenue_growth'))
        next_earnings   = _notna_str(r5d, 'next_earnings') or None
        days_to_earn    = _sf(r5d.get('days_to_earnings'))
        _cp_r5d = _sf(r5d.get('current_price'))
        current_price   = _cp_r5d if _cp_r5d is not None else _sf(tc.get('current_price'))
        company_name    = (_notna_str(r5d, 'company_name')
                          if 'company_name' in r5d.index
                          else tc.get('company_name', ticker))
        if not company_name:
            company_name = tc.get('company_name', ticker)
    else:
        insiders_score = 0.0; inst_score = 0.0; num_whales = 0; top_whales = ''
        tier_boost = 0; price_target = None; upside_pct = None; entry_score = None
        pe_ratio = None; peg_ratio = None; fcf_yield = None; roe = None; rev_growth = None
        next_earnings = None; days_to_earn = None
        current_price = _sf(tc.get('current_price'))
        company_name  = tc.get('company_name', ticker)
        sector_score  = None; sector_momentum = 'stable'
        sector_name   = tc.get('sector', 'Unknown')
        if rscores is not None:
            company_name = _notna_str(rscores, 'company_name', company_name) or company_name
            sector_name  = _notna_str(rscores, 'sector', sector_name) or sector_name

    # ── Filtros técnicos desde super_scores_ultimate ───────────────────────
    ma_passes = None; ma_score = None; ma_checks = None; ma_reason = ''
    ad_signal = None; ad_score = None; ad_reason = ''
    if rscores is not None:
        _ma_pass = rscores.get('ma_filter_pass')
        ma_passes = bool(_ma_pass) if _ma_pass is not None and not (isinstance(_ma_pass, float) and pd.isna(_ma_pass)) else None
        ma_score  = _sf(rscores.get('ma_filter_score'))
        ma_reason = _notna_str(rscores, 'ma_filter_reason')
        _ads = rscores.get('ad_signal')
        ad_signal = str(_ads) if _ads is not None and not (isinstance(_ads, float) and pd.isna(_ads)) else None
        ad_score  = _sf(rscores.get('ad_score'))
        ad_reason = _notna_str(rscores, 'ad_reason')

    # ── RS Line (Minervini) ────────────────────────────────────────────────
    rs_line_score = rs_line_percentile = None
    rs_line_at_high = None   # bool or None
    rs_line_trend = None     # str: 'up'/'flat'/'down' or None

    # Try rfund first (fundamental_scores.csv), then rscores (super_scores_ultimate.csv)
    for _src in [rfund, rscores]:
        if _src is None:
            continue
        if rs_line_score is None:
            rs_line_score = _sf(_src.get('rs_line_score'))
        if rs_line_percentile is None:
            rs_line_percentile = _sf(_src.get('rs_line_percentile'))
        if rs_line_at_high is None:
            _raw = _src.get('rs_line_at_new_high')
            if _raw is not None and not (isinstance(_raw, float) and pd.isna(_raw)):
                rs_line_at_high = bool(_raw)
        if rs_line_trend is None:
            _rt = _src.get('rs_line_trend')
            if _rt is not None and not (isinstance(_rt, float) and pd.isna(_rt)):
                rs_line_trend = str(_rt)

    # ── CANSLIM "A" — EPS/Revenue Acceleration ────────────────────────────
    eps_growth_yoy = rev_growth_yoy = None
    eps_accelerating = rev_accelerating = None
    eps_accel_quarters = rev_accel_quarters = None

    for _src in [rfund, rscores]:
        if _src is None:
            continue
        if eps_growth_yoy is None:
            eps_growth_yoy = _sf(_src.get('eps_growth_yoy'))
        if rev_growth_yoy is None:
            rev_growth_yoy = _sf(_src.get('rev_growth_yoy'))
        if eps_accel_quarters is None:
            eps_accel_quarters = _sf(_src.get('eps_accel_quarters'))
        if rev_accel_quarters is None:
            rev_accel_quarters = _sf(_src.get('rev_accel_quarters'))
        if eps_accelerating is None:
            _raw = _src.get('eps_accelerating')
            if _raw is not None and not (isinstance(_raw, float) and pd.isna(_raw)):
                eps_accelerating = bool(_raw)
        if rev_accelerating is None:
            _raw = _src.get('rev_accelerating')
            if _raw is not None and not (isinstance(_raw, float) and pd.isna(_raw)):
                rev_accelerating = bool(_raw)

    # ── Industry Group Ranking ─────────────────────────────────────────────
    industry_group_rank = industry_group_total = industry_group_percentile = None
    industry_group_label = None
    if rscores is not None:
        industry_group_rank        = _sf(rscores.get('industry_group_rank'))
        industry_group_total       = _sf(rscores.get('industry_group_total'))
        industry_group_percentile  = _sf(rscores.get('industry_group_percentile'))
        _lbl = rscores.get('industry_group_label')
        if _lbl is not None and not (isinstance(_lbl, float) and pd.isna(_lbl)):
            industry_group_label = str(_lbl)

    # ── Short Interest + 52w Proximity ────────────────────────────────────
    short_pct_float = short_ratio = proximity_52w = None
    short_squeeze = None  # bool
    for _src in [rfund, rscores]:
        if _src is None:
            continue
        if short_pct_float is None:
            short_pct_float = _sf(_src.get('short_percent_float'))
        if short_ratio is None:
            short_ratio = _sf(_src.get('short_ratio'))
        if proximity_52w is None:
            proximity_52w = _sf(_src.get('proximity_to_52w_high'))
        if short_squeeze is None:
            _raw = _src.get('short_squeeze_potential')
            if _raw is not None and not (isinstance(_raw, float) and pd.isna(_raw)):
                short_squeeze = bool(_raw)

    # ── Trend Template ─────────────────────────────────────────────────────
    trend_template_score = None
    trend_template_pass  = None  # bool
    for _src in [rfund, rscores]:
        if _src is None:
            continue
        if trend_template_score is None:
            trend_template_score = _sf(_src.get('trend_template_score'))
        if trend_template_pass is None:
            _raw = _src.get('trend_template_pass')
            if _raw is not None and not (isinstance(_raw, float) and pd.isna(_raw)):
                trend_template_pass = bool(_raw)

    # ── Target Prices (analyst + DCF + P/E) ───────────────────────────────
    tp_analyst = tp_analyst_high = tp_analyst_low = None
    tp_analyst_upside = tp_analyst_count = tp_analyst_rec = None
    tp_dcf = tp_dcf_upside = tp_pe = tp_pe_upside = None
    for _src in [rfund, rscores]:
        if _src is None:
            continue
        if tp_analyst is None:      tp_analyst       = _sf(_src.get('target_price_analyst'))
        if tp_analyst_high is None: tp_analyst_high  = _sf(_src.get('target_price_analyst_high'))
        if tp_analyst_low is None:  tp_analyst_low   = _sf(_src.get('target_price_analyst_low'))
        if tp_analyst_upside is None: tp_analyst_upside = _sf(_src.get('analyst_upside_pct'))
        if tp_analyst_rec is None:
            _raw = _src.get('analyst_recommendation')
            if _raw is not None and not (isinstance(_raw, float) and pd.isna(_raw)):
                tp_analyst_rec = str(_raw)
        if tp_analyst_count is None:
            _raw = _src.get('analyst_count')
            if _raw is not None and not (isinstance(_raw, float) and pd.isna(_raw)):
                try:
                    tp_analyst_count = int(_raw)
                except (ValueError, TypeError):
                    pass
        if tp_dcf is None:          tp_dcf           = _sf(_src.get('target_price_dcf'))
        if tp_dcf_upside is None:   tp_dcf_upside    = _sf(_src.get('target_price_dcf_upside_pct'))
        if tp_pe is None:           tp_pe            = _sf(_src.get('target_price_pe'))
        if tp_pe_upside is None:    tp_pe_upside     = _sf(_src.get('target_price_pe_upside_pct'))

    # ── ML detalles ────────────────────────────────────────────────────────
    ml_quality = ml_momentum = ml_trend = ml_volume = None
    if rml is not None:
        ml_quality  = _notna_str(rml, 'quality') or None
        ml_momentum = _sf(rml.get('momentum_score'))
        ml_trend    = _sf(rml.get('trend_score'))
        ml_volume   = _sf(rml.get('volume_score'))

    # ── Insiders ───────────────────────────────────────────────────────────
    insider_data = _row(DF_INSIDERS, ticker)
    insider_info = None
    if insider_data is not None:
        insider_info = {
            "purchase_count":   int(_sf(insider_data.get('purchase_count'), 0)),
            "unique_insiders":  int(_sf(insider_data.get('unique_insiders'), 0)),
            "days_span":        int(_sf(insider_data.get('days_span'), 0)),
            "last_purchase":    _notna_str(insider_data, 'last_purchase'),
            "confidence_score": _sf(insider_data.get('confidence_score')),
        }

    # ── Mean Reversion ─────────────────────────────────────────────────────
    mr_data = _row(DF_REVERSION, ticker)
    mean_reversion = None
    if mr_data is not None:
        mean_reversion = {
            "strategy":      _notna_str(mr_data, 'strategy'),
            "quality":       _notna_str(mr_data, 'quality'),
            "reversion_score": _sf(mr_data.get('reversion_score')),
            "entry_zone":    _notna_str(mr_data, 'entry_zone'),
            "target":        _sf(mr_data.get('target')),
            "stop_loss":     _sf(mr_data.get('stop_loss')),
            "rsi":           _sf(mr_data.get('rsi')),
            "drawdown_pct":  _sf(mr_data.get('drawdown_pct')),
        }

    # ── Options flow ───────────────────────────────────────────────────────
    opt_data = _row(DF_OPTIONS, ticker)
    options_flow = None
    if opt_data is not None:
        options_flow = {
            "sentiment":       _notna_str(opt_data, 'sentiment'),
            "flow_score":      _sf(opt_data.get('flow_score')),
            "quality":         _notna_str(opt_data, 'quality'),
            "put_call_ratio":  _sf(opt_data.get('put_call_ratio')),
            "total_premium":   _sf(opt_data.get('total_premium')),
            "sentiment_emoji": _notna_str(opt_data, 'sentiment_emoji'),
            "unusual_calls":   int(_sf(opt_data.get('unusual_calls'), 0)),
            "unusual_puts":    int(_sf(opt_data.get('unusual_puts'), 0)),
        }

    # ── Entry/exit ─────────────────────────────────────────────────────────
    entry_price = stop_loss = target_price = risk_reward = None
    if rprice is not None:
        entry_price  = _sf(rprice.get('entry_price'))
        stop_loss    = _sf(rprice.get('stop_loss'))
        target_price = _sf(rprice.get('target_price'))
        risk_reward  = _sf(rprice.get('risk_reward'))

    # ── Breakdown scores ───────────────────────────────────────────────────
    base, vcp_c, ml_c, fund_c = _calc_base(vcp_score, ml_score, fund_score)
    penalty = round(base - final_score, 1) if (base is not None and final_score is not None and base > final_score) else 0

    # ── Thesis ─────────────────────────────────────────────────────────────
    thesis = _build_thesis({
        'vcp_score': vcp_score or 0, 'insiders_score': insiders_score,
        'institutional_score': inst_score, 'num_whales': int(num_whales or 0),
        'top_whales': top_whales, 'sector_name': sector_name,
        'sector_momentum': sector_momentum, 'sector_score': sector_score or 0,
        'fundamental_score': fund_score or 0, 'super_score_5d': final_score or 0,
        'super_score_ultimate': final_score or 0, 'tier': tier_label,
        'price_target': price_target, 'upside_percent': upside_pct,
        'fcf_yield': fcf_yield, 'roe': roe, 'revenue_growth': rev_growth,
        'timing_convergence': False, 'vcp_repeater': False,
    })

    return {
        "source": "pipeline_cache",
        "ticker": ticker,
        "company_name": company_name,
        "current_price": current_price,
        "analysis_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "elapsed_seconds": 0.1,

        "final_score": final_score,
        "base_score": base,
        "penalty": penalty,
        "tier_emoji": tier_emoji,
        "tier_label": tier_label,

        "vcp_score": round(vcp_score, 1) if vcp_score is not None else None,
        "ml_score":  round(ml_score,  1) if ml_score  is not None else None,
        "fund_score": round(fund_score, 1) if fund_score is not None else None,
        "vcp_contribution":  vcp_c,
        "ml_contribution":   ml_c,
        "fund_contribution": fund_c,

        "price_target": price_target,
        "upside_percent": upside_pct,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "target_price": target_price,
        "risk_reward": risk_reward,

        "insiders_score": insiders_score,
        "institutional_score": inst_score,
        "num_whales": int(num_whales or 0),
        "top_whales": top_whales,
        "tier_boost": tier_boost,

        "sector_name": sector_name,
        "sector_score": sector_score,
        "sector_momentum": sector_momentum,
        "sector_error": None,

        "ma_passes": ma_passes,
        "ma_score": ma_score,
        "ma_checks": ma_checks,
        "ma_reason": ma_reason,
        "ma_error": None,

        "ad_signal": ad_signal,
        "ad_score": ad_score,
        "ad_reason": ad_reason,
        "ad_error": None,

        "rs_line_score":       round(rs_line_score, 1) if rs_line_score is not None else None,
        "rs_line_percentile":  round(rs_line_percentile, 1) if rs_line_percentile is not None else None,
        "rs_line_at_high":     rs_line_at_high,
        "rs_line_trend":       rs_line_trend,

        "eps_growth_yoy":      round(eps_growth_yoy, 1) if eps_growth_yoy is not None else None,
        "eps_accelerating":    eps_accelerating,
        "eps_accel_quarters":  int(eps_accel_quarters) if eps_accel_quarters is not None else None,
        "rev_growth_yoy":      round(rev_growth_yoy, 1) if rev_growth_yoy is not None else None,
        "rev_accelerating":    rev_accelerating,

        "industry_group_rank":       int(industry_group_rank) if industry_group_rank is not None else None,
        "industry_group_total":      int(industry_group_total) if industry_group_total is not None else None,
        "industry_group_percentile": round(industry_group_percentile, 1) if industry_group_percentile is not None else None,
        "industry_group_label":      industry_group_label,

        "short_percent_float":     round(short_pct_float, 1) if short_pct_float is not None else None,
        "short_ratio":             round(short_ratio, 1) if short_ratio is not None else None,
        "short_squeeze_potential": short_squeeze,
        "proximity_to_52w_high":   round(proximity_52w, 1) if proximity_52w is not None else None,

        "trend_template_score": int(trend_template_score) if trend_template_score is not None else None,
        "trend_template_pass":  trend_template_pass,

        "target_price_analyst":        round(tp_analyst, 2) if tp_analyst is not None else None,
        "target_price_analyst_high":   round(tp_analyst_high, 2) if tp_analyst_high is not None else None,
        "target_price_analyst_low":    round(tp_analyst_low, 2) if tp_analyst_low is not None else None,
        "analyst_upside_pct":          round(tp_analyst_upside, 1) if tp_analyst_upside is not None else None,
        "analyst_recommendation":      tp_analyst_rec,
        "analyst_count":               tp_analyst_count,
        "target_price_dcf":            round(tp_dcf, 2) if tp_dcf is not None else None,
        "target_price_dcf_upside_pct": round(tp_dcf_upside, 1) if tp_dcf_upside is not None else None,
        "target_price_pe":             round(tp_pe, 2) if tp_pe is not None else None,
        "target_price_pe_upside_pct":  round(tp_pe_upside, 1) if tp_pe_upside is not None else None,

        "ml_quality": ml_quality,
        "ml_momentum": ml_momentum,
        "ml_trend": ml_trend,
        "ml_volume": ml_volume,
        "ml_error": None,

        "entry_score": entry_score,
        "forward_pe": pe_ratio,
        "peg_ratio": peg_ratio,
        "fcf_yield": fcf_yield,
        "roe": roe,
        "revenue_growth": rev_growth,
        "dividend_yield": _sf(r5d.get('dividend_yield_pct')) if r5d is not None else None,
        "payout_ratio": _sf(r5d.get('payout_ratio_pct')) if r5d is not None else None,
        "buyback_active": bool(r5d.get('buyback_active')) if r5d is not None and pd.notna(r5d.get('buyback_active')) else None,
        "shares_change": _sf(r5d.get('shares_change_pct')) if r5d is not None else None,
        "interest_coverage": _sf(r5d.get('interest_coverage')) if r5d is not None else _sf(rfund.get('interest_coverage')) if rfund is not None else None,
        "risk_reward": _sf(r5d.get('risk_reward')) if r5d is not None else None,
        "analyst_revision": _sf(r5d.get('analyst_revision_momentum')) if r5d is not None else None,
        "fund_error": None,

        # ── Piotroski F-Score + Magic Formula (from fundamental_scores.csv) ───
        "piotroski_score": _sf(rfund.get('piotroski_score')) if rfund is not None else None,
        "piotroski_label": rfund.get('piotroski_label') if rfund is not None else None,
        "ebit_ev_yield":   _sf(rfund.get('ebit_ev_yield')) if rfund is not None else None,
        "roic_greenblatt": _sf(rfund.get('roic_greenblatt')) if rfund is not None else None,

        # ── Health & earnings details from fundamental_scores.csv ──────────
        **_parse_health_earnings(rfund),

        "next_earnings": next_earnings,
        "days_to_earnings": days_to_earn,
        "earnings_warning": bool(rfund.get('earnings_warning')) if rfund is not None and pd.notna(rfund.get('earnings_warning')) else None,
        "earnings_catalyst": bool(rfund.get('earnings_catalyst')) if rfund is not None and pd.notna(rfund.get('earnings_catalyst')) else None,

        "insider_recurring": insider_info,
        "mean_reversion": mean_reversion,
        "options_flow": options_flow,

        "vcp_ready": False,
        "vcp_contractions": 0,
        "vcp_breakout_potential": None,
        "vcp_stage": None,
        "vcp_reason": None,
        "vcp_error": None,

        "thesis": thesis,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ANÁLISIS LIVE (yfinance — funciona en local, puede fallar en Railway)
# ─────────────────────────────────────────────────────────────────────────────

def _sfl(val, default=None):
    """safe_float_live: sin pandas, para valores de yfinance."""
    try:
        v = float(val)
        return v if v == v else default  # NaN check
    except (TypeError, ValueError):
        return default


def _run_vcp(ticker):
    try:
        from vcp_scanner_usa import CalibratedVCPScanner
        result = CalibratedVCPScanner().process_single_ticker(ticker)
        if result is None:
            return None, {}, "No cumple criterios VCP mínimos"
        return (_sfl(result.vcp_score), {
            "ready_to_buy":      bool(getattr(result, 'ready_to_buy', False)),
            "contractions":      len(getattr(result, 'contractions', []) or []),
            "breakout_potential": _sfl(getattr(result, 'breakout_potential', None)),
            "stage":             getattr(result, 'stage_analysis', None),
            "reason":            getattr(result, 'reason', None),
        }, None)
    except Exception as e:
        return None, {}, str(e)


def _run_ml(ticker):
    try:
        from ml_scoring import MLScorer
        result = MLScorer().score_ticker(ticker)
        if result is None:
            return None, {}, "Datos insuficientes (< 50 días)"
        return (_sfl(result.get('ml_score')), {
            "quality":        result.get('quality'),
            "momentum_score": _sfl(result.get('momentum_score')),
            "trend_score":    _sfl(result.get('trend_score')),
            "volume_score":   _sfl(result.get('volume_score')),
        }, None)
    except Exception as e:
        return None, {}, str(e)


def _run_fundamentals(ticker):
    try:
        from fundamental_analyzer import FundamentalAnalyzer
        fa = FundamentalAnalyzer()
        fund_score  = _sfl(fa.get_fundamental_score(ticker))
        fund_data   = fa.get_fundamental_data(ticker)
        entry_score = _sfl(fa.calculate_entry_score(ticker))
        pt = None
        try:
            pt = fa.calculate_custom_price_target(ticker)
        except Exception:
            pass
        details = {}
        if fund_data:
            val_d  = fund_data.get('valuation', {})
            prof   = fund_data.get('profitability', {})
            growth = fund_data.get('growth', {})
            cf     = fund_data.get('cashflow', {})
            health = fund_data.get('financial_health', {})
            details = {
                "forward_pe":      _sfl(val_d.get('forward_pe')),
                "peg_ratio":       _sfl(val_d.get('peg_ratio')),
                "roe":             _sfl(prof.get('roe')),
                "revenue_growth":  _sfl(growth.get('revenue_growth')),
                "fcf_yield":       _sfl(cf.get('fcf_yield')),
                "debt_to_equity":  _sfl(health.get('debt_to_equity')),
                "profit_margin":   _sfl(prof.get('profit_margin')),
                "current_price":   _sfl(fund_data.get('current_price')),
            }
        pt_det = {}
        if pt:
            pt_det = {
                "custom_target":   _sfl(pt.get('custom_target')),
                "upside_percent":  _sfl(pt.get('upside_percent')),
            }
        return fund_score, details, entry_score, pt_det, None
    except Exception as e:
        return None, {}, None, {}, str(e)


def _run_ma(ticker):
    try:
        from moving_average_filter import MovingAverageFilter
        return MovingAverageFilter().check_stock(ticker), None
    except Exception as e:
        return {'passes': None, 'score': None, 'checks_passed': None, 'reason': str(e)}, str(e)


def _run_ad(ticker):
    try:
        from accumulation_distribution_filter import AccumulationDistributionFilter
        return AccumulationDistributionFilter().analyze_stock(ticker), None
    except Exception as e:
        return {'signal': None, 'score': None, 'reason': str(e)}, str(e)


def _run_sector(ticker):
    try:
        from sector_enhancement import SectorEnhancement
        se = SectorEnhancement()
        sc  = _sfl(se.calculate_sector_score(ticker))
        mom = se.get_sector_momentum(ticker)
        name = 'Unknown'
        try:
            import yfinance as yf
            name = yf.Ticker(ticker).info.get('sector', 'Unknown') or 'Unknown'
        except Exception:
            pass
        return sc, mom, name, None
    except Exception as e:
        return None, None, 'Unknown', str(e)


def _calc_live_score(vcp, ml, fund, ma, ad):
    """Calcula base/penalty/final desde scores live. None si no hay datos."""
    vcp_c  = vcp  * 0.40 if vcp  is not None else None
    ml_c   = ml   * 0.30 if ml   is not None else None
    fund_c = fund * 0.30 if fund is not None else None
    available = [c for c in [vcp_c, ml_c, fund_c] if c is not None]
    if not available:
        return None, None, None
    base = sum(available)
    pen = 0.0
    ma_passes = ma.get('passes')
    if ma_passes is False:
        pen += 20
    elif ma_passes is True and (_sfl(ma.get('score'), 100) or 100) < 80:
        pen += 5
    sig = ad.get('signal')
    if sig == 'STRONG_DISTRIBUTION': pen += 15
    elif sig == 'DISTRIBUTION':      pen += 10
    ad_sc = _sfl(ad.get('score'))
    if ad_sc is not None and ad_sc < 50:
        pen += 5
    return round(base, 1), round(pen, 1), round(max(0, min(100, base - pen)), 1)


def _analyze_live(ticker):
    """Análisis completo con yfinance. Puede ser lento y fallar en Railway."""
    t0 = time.time()

    company_name = ticker; current_price = None
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        company_name  = info.get('longName') or info.get('shortName') or ticker
        current_price = _sfl(info.get('currentPrice') or info.get('regularMarketPrice'))
    except Exception:
        pass

    vcp_score,  vcp_det,  vcp_err  = _run_vcp(ticker);           time.sleep(0.3)
    ml_score,   ml_det,   ml_err   = _run_ml(ticker);            time.sleep(0.3)
    fund_score, fund_det, entry_score, pt_det, fund_err = _run_fundamentals(ticker)
    if current_price is None:
        current_price = fund_det.get('current_price')
    time.sleep(0.3)
    ma_result, ma_err = _run_ma(ticker);                          time.sleep(0.3)
    ad_result, ad_err = _run_ad(ticker);                          time.sleep(0.3)
    sector_score, sector_mom, sector_name, sector_err = _run_sector(ticker)

    base, penalty, final = _calc_live_score(vcp_score, ml_score, fund_score, ma_result, ad_result)
    tier_emoji, tier_label = _get_tier(final)
    vcp_c, ml_c, fund_c = (
        round(vcp_score  * 0.40, 1) if vcp_score  is not None else None,
        round(ml_score   * 0.30, 1) if ml_score   is not None else None,
        round(fund_score * 0.30, 1) if fund_score is not None else None,
    )

    # Insiders / mean reversion / options desde cache aunque sea live
    insider_data = _row(DF_INSIDERS, ticker)
    insider_info = None
    if insider_data is not None:
        insider_info = {
            "purchase_count":   int(_sf(insider_data.get('purchase_count'), 0)),
            "unique_insiders":  int(_sf(insider_data.get('unique_insiders'), 0)),
            "days_span":        int(_sf(insider_data.get('days_span'), 0)),
            "last_purchase":    _notna_str(insider_data, 'last_purchase'),
            "confidence_score": _sf(insider_data.get('confidence_score')),
        }

    mr_data = _row(DF_REVERSION, ticker)
    mean_reversion = None
    if mr_data is not None:
        mean_reversion = {
            "strategy":        _notna_str(mr_data, 'strategy'),
            "quality":         _notna_str(mr_data, 'quality'),
            "reversion_score": _sf(mr_data.get('reversion_score')),
            "entry_zone":      _notna_str(mr_data, 'entry_zone'),
            "target":          _sf(mr_data.get('target')),
            "rsi":             _sf(mr_data.get('rsi')),
        }

    opt_data = _row(DF_OPTIONS, ticker)
    options_flow = None
    if opt_data is not None:
        options_flow = {
            "sentiment":       _notna_str(opt_data, 'sentiment'),
            "flow_score":      _sf(opt_data.get('flow_score')),
            "quality":         _notna_str(opt_data, 'quality'),
            "sentiment_emoji": _notna_str(opt_data, 'sentiment_emoji'),
            "unusual_calls":   int(_sf(opt_data.get('unusual_calls'), 0)),
            "unusual_puts":    int(_sf(opt_data.get('unusual_puts'), 0)),
        }

    thesis = _build_thesis({
        'vcp_score': vcp_score or 0, 'insiders_score': 0,
        'sector_name': sector_name, 'sector_momentum': sector_mom or 'stable',
        'sector_score': sector_score or 0, 'fundamental_score': fund_score or 0,
        'super_score_5d': final or 0, 'tier': tier_label,
        'price_target': pt_det.get('custom_target'),
        'upside_percent': pt_det.get('upside_percent'),
        'fcf_yield': fund_det.get('fcf_yield'),
        'roe': fund_det.get('roe'),
        'revenue_growth': fund_det.get('revenue_growth'),
        'num_whales': 0, 'timing_convergence': False, 'vcp_repeater': False,
    })

    return {
        "source": "live_yfinance",
        "ticker": ticker,
        "company_name": company_name,
        "current_price": current_price,
        "analysis_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "elapsed_seconds": round(time.time() - t0, 1),

        "final_score": final,
        "base_score": base,
        "penalty": penalty,
        "tier_emoji": tier_emoji,
        "tier_label": tier_label,

        "vcp_score":  round(vcp_score,  1) if vcp_score  is not None else None,
        "ml_score":   round(ml_score,   1) if ml_score   is not None else None,
        "fund_score": round(fund_score, 1) if fund_score is not None else None,
        "vcp_contribution":  vcp_c,
        "ml_contribution":   ml_c,
        "fund_contribution": fund_c,

        "price_target": pt_det.get('custom_target'),
        "upside_percent": pt_det.get('upside_percent'),
        "entry_price": None, "stop_loss": None, "target_price": None, "risk_reward": None,

        "insiders_score": 0, "institutional_score": 0,
        "num_whales": 0, "top_whales": "", "tier_boost": 0,

        "sector_name": sector_name,
        "sector_score": sector_score,
        "sector_momentum": sector_mom,
        "sector_error": sector_err,

        "ma_passes": ma_result.get('passes'),
        "ma_score":  _sf(ma_result.get('score')),
        "ma_checks": ma_result.get('checks_passed'),
        "ma_reason": ma_result.get('reason', ''),
        "ma_error":  ma_err,

        "ad_signal": ad_result.get('signal'),
        "ad_score":  _sf(ad_result.get('score')),
        "ad_reason": ad_result.get('reason', ''),
        "ad_error":  ad_err,

        "ml_quality":   ml_det.get('quality'),
        "ml_momentum":  ml_det.get('momentum_score'),
        "ml_trend":     ml_det.get('trend_score'),
        "ml_volume":    ml_det.get('volume_score'),
        "ml_error":     ml_err,

        "entry_score":     entry_score,
        "forward_pe":      fund_det.get('forward_pe'),
        "peg_ratio":       fund_det.get('peg_ratio'),
        "fcf_yield":       fund_det.get('fcf_yield'),
        "roe":             fund_det.get('roe'),
        "revenue_growth":  fund_det.get('revenue_growth'),
        "debt_to_equity":  fund_det.get('debt_to_equity'),
        "fund_error":      fund_err,

        "next_earnings": None, "days_to_earnings": None,

        "insider_recurring": insider_info,
        "mean_reversion":    mean_reversion,
        "options_flow":      options_flow,

        "vcp_ready":             vcp_det.get('ready_to_buy', False),
        "vcp_contractions":      vcp_det.get('contractions', 0),
        "vcp_breakout_potential": vcp_det.get('breakout_potential'),
        "vcp_stage":             vcp_det.get('stage'),
        "vcp_reason":            vcp_det.get('reason'),
        "vcp_error":             vcp_err,

        "thesis": thesis,
    }


# ─────────────────────────────────────────────────────────────────────────────
# THESIS
# ─────────────────────────────────────────────────────────────────────────────

def _build_thesis(opp):
    try:
        from investment_thesis_generator import InvestmentThesisGenerator
        return InvestmentThesisGenerator.generate_thesis(opp)
    except Exception as e:
        return f"(Error generando tesis: {e})"


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    cached = list(DF_5D.index) if not DF_5D.empty else []
    return f"""
    <h2>Ticker Analyzer API</h2>
    <p><code>GET /api/analyze/&lt;ticker&gt;</code> — análisis completo</p>
    <p><code>GET /api/health</code> — estado</p>
    <p><code>GET /api/tickers</code> — tickers en cache ({len(cached)})</p>
    <p>Ejemplo: <a href="/api/analyze/AAPL">/api/analyze/AAPL</a></p>
    """


@app.route('/api/health')
def health():
    cached = list(DF_5D.index) if not DF_5D.empty else []
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "cached_tickers": len(cached),
        "modules": {
            "5d_scores":     not DF_5D.empty,
            "ml_scores":     not DF_ML.empty,
            "fundamental":   not DF_FUND.empty,
            "super_scores":  not DF_SCORES.empty,
            "insiders":      not DF_INSIDERS.empty,
            "mean_reversion": not DF_REVERSION.empty,
            "options_flow":  not DF_OPTIONS.empty,
        }
    })


@app.route('/api/tickers')
def tickers():
    cached = sorted(DF_5D.index.tolist()) if not DF_5D.empty else []
    return jsonify({"tickers": cached, "count": len(cached)})


@app.route('/api/analyze/<ticker>')
@limiter.limit("20 per minute")
def analyze(ticker):
    ticker = ticker.upper().strip()
    if not _validate_ticker(ticker):
        return jsonify({"error": f"Ticker inválido: '{ticker}'"}), 400

    try:
        in_cache = (
            (not DF_5D.empty     and ticker in DF_5D.index)     or
            (not DF_ML.empty     and ticker in DF_ML.index)     or
            (not DF_SCORES.empty and ticker in DF_SCORES.index) or
            (ticker in TICKER_CACHE)
        )

        if in_cache:
            result = _analyze_from_cache(ticker)
        else:
            result = _analyze_live(ticker)
            if not result.get('current_price') and result.get('ml_error'):
                result['warning'] = (
                    'Ticker no está en el cache del pipeline diario. '
                    'El análisis live puede ser incompleto en entornos cloud.'
                )

        return jsonify(result)

    except Exception as e:
        _logger.exception("Error procesando %s: %s", ticker, e)
        return jsonify({
            "error": "Internal server error",
            "ticker": ticker,
        }), 500


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD DATA ENDPOINTS (for React frontend)
# ─────────────────────────────────────────────────────────────────────────────

def _csv_to_json_response(csv_candidates):
    """Smart fallback: try CSV files in order, return first with data."""
    for csv_path, label in csv_candidates:
        p = Path(csv_path)
        if p.exists():
            try:
                df = pd.read_csv(p)
                if len(df) > 0:
                    # Use pandas to_json to safely convert NaN → null (valid JSON)
                    # df.to_dict() with Python's json module would emit NaN literals (invalid JSON)
                    records = json.loads(df.to_json(orient='records'))
                    return jsonify({
                        "data": records,
                        "count": len(df),
                        "source": label,
                    })
            except Exception:
                continue
    return jsonify({"data": [], "count": 0, "source": "none"})


@app.route('/api/value-opportunities')
def value_opportunities():
    return _csv_to_json_response([
        (DOCS / 'value_conviction.csv', 'conviction'),
        (DOCS / 'value_opportunities_filtered.csv', 'ai_filtered'),
        (DOCS / 'value_opportunities.csv', 'unfiltered'),
    ])


@app.route('/api/eu-value-opportunities')
def eu_value_opportunities():
    return _csv_to_json_response([
        (DOCS / 'european_value_conviction.csv', 'conviction'),
        (DOCS / 'european_value_opportunities_filtered.csv', 'ai_filtered'),
        (DOCS / 'european_value_opportunities.csv', 'unfiltered'),
    ])


@app.route('/api/global-value')
def global_value_opportunities():
    return _csv_to_json_response([
        (DOCS / 'global_value_opportunities.csv', 'global_scanner'),
    ])


@app.route('/api/momentum-opportunities')
def momentum_opportunities():
    return _csv_to_json_response([
        (DOCS / 'momentum_opportunities_filtered.csv', 'ai_filtered'),
        (DOCS / 'momentum_opportunities.csv', 'unfiltered'),
    ])


@app.route('/api/sector-rotation')
def sector_rotation():
    data = _load_json(DOCS / 'sector_rotation' / 'latest_scan.json')
    return jsonify(data if data else {"results": [], "alerts": [], "opportunities": []})


@app.route('/api/options-flow')
def options_flow():
    data = _load_json(DOCS / 'options_flow.json')
    if data:
        return jsonify(data)
    # Fallback to CSV
    return _csv_to_json_response([
        (DOCS / 'options_flow.csv', 'csv'),
    ])


@app.route('/api/micro-cap')
def micro_cap():
    return _csv_to_json_response([
        (DOCS / 'micro_cap_opportunities.csv', 'csv'),
    ])


@app.route('/api/shorts')
def shorts():
    data = _load_json(DOCS / 'short_opportunities.json')
    if data:
        # Annotate whether AI filter has run
        filtered = _load_json(DOCS / 'short_opportunities_filtered.json')
        data['ai_filtered_available'] = bool(filtered and filtered.get('data'))
        data['confirmed_count'] = filtered.get('confirmed_shorts', 0) if filtered else 0
        return jsonify(data)
    return _csv_to_json_response([
        (DOCS / 'short_opportunities.csv', 'csv'),
    ])


@app.route('/api/catalysts')
def catalysts():
    """Unified catalyst calendar: earnings, macro, FDA, opex, dividends."""
    from datetime import datetime as dt2
    data = _load_json(DOCS / 'catalysts.json')
    if not data:
        return jsonify({'events': [], 'total_events': 0, 'by_category': {}}), 200
    today = dt2.now().strftime('%Y-%m-%d')
    # Filter only future/today events and recalculate days_away
    filtered = []
    for e in data.get('events', []):
        edate = e.get('date', '')
        if edate >= today:
            e['days_away'] = (dt2.strptime(edate, '%Y-%m-%d') - dt2.now()).days
            filtered.append(e)
    data['events'] = filtered
    data['total_events'] = len(filtered)
    return jsonify(data)


@app.route('/api/portfolio-news')
def portfolio_news():
    return jsonify(_load_json(DOCS / 'portfolio_news.json') or {
        'items': [], 'count': 0, 'alta_count': 0, 'media_count': 0,
        'tickers': [], 'scan_date': None, 'scan_time': None,
    })


@app.route('/api/portfolio-watch', methods=['GET'])
def portfolio_watch_get():
    cfg = _load_json(DOCS / 'portfolio_watch.json')
    return jsonify(cfg or {'tickers': []})


@app.route('/api/portfolio-watch', methods=['POST'])
def portfolio_watch_post():
    """Update the portfolio watch list. Body: {"tickers": [{"ticker":"UNH","notes":"..."}]}"""
    try:
        body = request.get_json(force=True)
        tickers = body.get('tickers', [])
        # Sanitize
        clean = []
        for t in tickers:
            if isinstance(t, dict) and t.get('ticker'):
                clean.append({'ticker': t['ticker'].upper()[:10], 'notes': str(t.get('notes',''))[:80]})
            elif isinstance(t, str):
                clean.append({'ticker': t.upper()[:10], 'notes': ''})
        cfg = {
            'description': 'Tickers de cartera a monitorizar para noticias y alertas Telegram.',
            'tickers': clean,
            'updated': datetime.now().strftime('%Y-%m-%d'),
        }
        with open(DOCS / 'portfolio_watch.json', 'w') as f:
            json.dump(cfg, f, indent=2)
        return jsonify({'ok': True, 'count': len(clean)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400


@app.route('/api/mean-reversion')
def mean_reversion():
    data = _load_json(DOCS / 'mean_reversion_opportunities.json')
    if data:
        return jsonify(data)
    return _csv_to_json_response([
        (DOCS / 'mean_reversion_opportunities.csv', 'csv'),
    ])


@app.route('/api/recurring-insiders')
def recurring_insiders():
    # Returns merged US + EU insider data.
    # Use source DataFrames (not DF_INSIDERS which loses ticker via ignore_index concat)
    import json as _json
    dfs = []
    for src in [_df_ins_us, _df_ins_eu]:
        if not src.empty:
            dfs.append(src.reset_index() if src.index.name == 'ticker' else src)
    if dfs:
        combined = pd.concat(dfs, ignore_index=True)
        records = _json.loads(combined.to_json(orient='records'))
        return jsonify({'data': records, 'count': len(records)})
    return jsonify({'data': [], 'count': 0})


@app.route('/api/position-sizing')
def position_sizing():
    if not DF_POSITIONS.empty:
        import json as _json
        df = DF_POSITIONS.reset_index() if DF_POSITIONS.index.name == 'ticker' else DF_POSITIONS
        records = _json.loads(df.to_json(orient='records'))
        return jsonify({'data': records, 'count': len(df)})
    return jsonify({'data': [], 'count': 0})


@app.route('/api/industry-groups')
def industry_groups():
    if not DF_INDUSTRIES.empty:
        import json as _json
        records = _json.loads(DF_INDUSTRIES.to_json(orient='records'))
        return jsonify({'data': records, 'count': len(records)})
    return jsonify({'data': [], 'count': 0})


@app.route('/api/correlation-matrix')
def correlation_matrix():
    """Compute 60-day return correlation matrix for top VALUE picks."""
    import yfinance as yf2
    import pandas as pd2
    from datetime import datetime as dt2, timedelta as td2

    # Load top value picks (conviction + unfiltered fallback)
    tickers = []
    for fname in ('value_conviction.csv', 'value_opportunities.csv'):
        p = DOCS / fname
        if p.exists():
            try:
                df = pd2.read_csv(p)
                if 'ticker' in df.columns and 'value_score' in df.columns:
                    top = df.nlargest(15, 'value_score')['ticker'].tolist()
                    tickers = [str(t) for t in top if str(t).strip()]
                    break
            except Exception:
                pass

    if len(tickers) < 3:
        return jsonify({'error': 'Not enough tickers for correlation', 'matrix': [], 'tickers': []}), 200

    tickers = tickers[:15]
    start = (dt2.now() - td2(days=90)).strftime('%Y-%m-%d')
    try:
        raw = yf2.download(tickers, start=start, progress=False, auto_adjust=True)
        # Flatten MultiIndex if needed
        if isinstance(raw.columns, pd2.MultiIndex):
            close = raw['Close'] if 'Close' in raw.columns.get_level_values(0) else raw.iloc[:, 0]
        else:
            close = raw[['Close']] if 'Close' in raw.columns else raw

        # Daily returns
        returns = close.pct_change().dropna()
        # Drop columns with too many NaN
        valid = [c for c in returns.columns if returns[c].notna().sum() >= 30]
        returns = returns[valid]

        corr = returns.corr().round(3)
        matrix = []
        for row_t in corr.index:
            matrix.append({col_t: corr.at[row_t, col_t] for col_t in corr.columns})

        return jsonify({
            'tickers': list(corr.index),
            'matrix': matrix,
            'days': len(returns),
            'as_of': dt2.now().strftime('%Y-%m-%d'),
        })
    except Exception as e:
        return jsonify({'error': str(e), 'matrix': [], 'tickers': []}), 200


@app.route('/api/hedge-funds')
def hedge_funds():
    """13F consensus picks from top value/quality funds (Buffett, Ackman, Klarman…)."""
    data = _load_json(DOCS / 'hedge_fund_summary.json')
    if data:
        return jsonify(data)
    return jsonify({'top_consensus': [], 'funds_scraped': [], 'holdings_count': 0})


@app.route('/api/portfolio-tracker/signals')
def portfolio_signals():
    """Individual signal rows for the portfolio tracker."""
    csv_path = DOCS / 'portfolio_tracker' / 'recommendations.csv'
    if csv_path.exists():
        df = _load_csv(csv_path)
        if not df.empty:
            import json as _json
            df2 = df.reset_index() if df.index.name == 'ticker' else df
            records = _json.loads(df2.to_json(orient='records'))
            return jsonify({'data': records, 'count': len(records)})
    return jsonify({'data': [], 'count': 0})


@app.route('/api/download/<dataset>')
def download_csv(dataset: str):
    """Serve a CSV file for download by dataset name."""
    ALLOWED: dict[str, str] = {
        'value-us':         'value_opportunities.csv',
        'value-eu':         'european_value_opportunities.csv',
        'value-global':     'global_value_opportunities.csv',
        'value-us-full':    'value_conviction.csv',
        'value-eu-full':    'european_value_conviction.csv',
        'mean-reversion':   'mean_reversion_opportunities.csv',
        'insiders':         'recurring_insiders.csv',
        'insiders-eu':      'eu_recurring_insiders.csv',
        'options-flow':     'options_flow.csv',
        'momentum':         'momentum_opportunities.csv',
        'fundamental':      'fundamental_scores.csv',
        'fundamental-eu':   'european_fundamental_scores.csv',
    }
    filename = ALLOWED.get(dataset)
    if not filename:
        return jsonify({'error': 'Dataset not found'}), 404
    filepath = DOCS / filename
    if not filepath.exists():
        return jsonify({'error': 'File not available yet'}), 404
    from flask import send_file
    return send_file(str(filepath), mimetype='text/csv',
                     as_attachment=True, download_name=filename)


@app.route('/api/portfolio-tracker')
def portfolio_tracker():
    data = _load_json(DOCS / 'portfolio_tracker' / 'summary.json')
    return jsonify(data if data else {"error": "No portfolio data available"})


@app.route('/api/portfolio-tracker/calibration')
def portfolio_calibration():
    data = _load_json(DOCS / 'portfolio_tracker' / 'calibration.json')
    return jsonify(data if data else {"error": "No calibration data yet"})


@app.route('/api/market-regime')
def market_regime():
    us = _load_json(DOCS / 'market_regime.json')
    eu = _load_json(DOCS / 'european_market_regime.json')
    return jsonify({"us": us, "eu": eu})


@app.route('/api/cerebro/insights')
def cerebro_insights():
    return jsonify(_load_json(DOCS / 'cerebro_insights.json'))

@app.route('/api/cerebro/convergence')
def cerebro_convergence():
    return jsonify(_load_json(DOCS / 'cerebro_convergence.json'))

@app.route('/api/cerebro/alerts')
def cerebro_alerts():
    return jsonify(_load_json(DOCS / 'cerebro_alerts.json'))

@app.route('/api/cerebro/calibration')
def cerebro_calibration():
    return jsonify(_load_json(DOCS / 'cerebro_calibration.json'))

@app.route('/api/cerebro/entry-signals')
def cerebro_entry_signals():
    return jsonify(_load_json(DOCS / 'cerebro_entry_signals.json'))

@app.route('/api/cerebro/exit-signals')
def cerebro_exit_signals():
    return jsonify(_load_json(DOCS / 'cerebro_exit_signals.json'))

@app.route('/api/cerebro/value-traps')
def cerebro_value_traps():
    return jsonify(_load_json(DOCS / 'cerebro_value_traps.json'))

@app.route('/api/cerebro/smart-money')
def cerebro_smart_money():
    return jsonify(_load_json(DOCS / 'cerebro_smart_money.json'))

@app.route('/api/cerebro/insider-clusters')
def cerebro_insider_clusters():
    return jsonify(_load_json(DOCS / 'cerebro_insider_clusters.json'))

@app.route('/api/cerebro/dividend-safety')
def cerebro_dividend_safety():
    return jsonify(_load_json(DOCS / 'cerebro_dividend_safety.json'))

@app.route('/api/cerebro/piotroski')
def cerebro_piotroski():
    return jsonify(_load_json(DOCS / 'cerebro_piotroski.json'))

@app.route('/api/cerebro/stress-test')
def cerebro_stress_test():
    return jsonify(_load_json(DOCS / 'cerebro_stress_test.json'))

@app.route('/api/cerebro/briefing')
def cerebro_briefing():
    return jsonify(_load_json(DOCS / 'cerebro_briefing.json'))

@app.route('/api/cerebro/short-squeeze')
def cerebro_short_squeeze():
    return jsonify(_load_json(DOCS / 'cerebro_short_squeeze.json'))

@app.route('/api/cerebro/quality-decay')
def cerebro_quality_decay():
    return jsonify(_load_json(DOCS / 'cerebro_quality_decay.json'))

@app.route('/api/cerebro/sector-rv')
def cerebro_sector_rv():
    return jsonify(_load_json(DOCS / 'cerebro_sector_rv.json'))

@app.route('/api/cerebro/daily-plan')
def cerebro_daily_plan():
    return jsonify(_load_json(DOCS / 'cerebro_daily_plan.json'))

@app.route('/api/cerebro/earnings-revisions')
def cerebro_earnings_revisions():
    return jsonify(_load_json(DOCS / 'cerebro_earnings_revisions.json'))

@app.route('/api/cerebro/regime-transition')
def cerebro_regime_transition():
    return jsonify(_load_json(DOCS / 'cerebro_regime_transition.json'))

@app.route('/api/cerebro/thesis-drift')
def cerebro_thesis_drift():
    return jsonify(_load_json(DOCS / 'cerebro_thesis_drift.json'))

@app.route('/api/cerebro/correlation-breakdown')
def cerebro_correlation_breakdown():
    return jsonify(_load_json(DOCS / 'cerebro_correlation_breakdown.json'))

@app.route('/api/cerebro/competitor-displacement')
def cerebro_competitor_displacement():
    return jsonify(_load_json(DOCS / 'cerebro_competitor_displacement.json'))

@app.route('/api/cerebro/options-quality')
def cerebro_options_quality():
    return jsonify(_load_json(DOCS / 'cerebro_options_quality.json'))


# ── Chart analysis endpoints ───────────────────────────────────────────────────

@app.route('/api/technical-signals')
def technical_signals_endpoint():
    """Stage 2 MA + ATR + Volume signals from technical_filter.py."""
    return jsonify(_load_json(DOCS / 'technical_signals.json'))


@app.route('/api/technical-signals/<ticker>')
def technical_signals_ticker(ticker):
    data = _load_json(DOCS / 'technical_signals.json')
    sig = data.get('signals', {}).get(ticker.upper())
    if not sig:
        return jsonify({'error': f'{ticker} not found'}), 404
    return jsonify(sig)


@app.route('/api/chart-signals')
def chart_signals_endpoint():
    """Claude Vision chart analysis signals from chart_analyzer.py."""
    return jsonify(_load_json(DOCS / 'chart_signals.json'))


@app.route('/api/chart-signals/<ticker>')
def chart_signals_ticker(ticker):
    data = _load_json(DOCS / 'chart_signals.json')
    sig = data.get('signals', {}).get(ticker.upper())
    if not sig:
        return jsonify({'error': f'{ticker} not found'}), 404
    return jsonify(sig)


@app.route('/api/chart-signals/<ticker>/analyze')
def chart_analyze_on_demand(ticker):
    """On-demand chart analysis for a single ticker (synchronous, slower)."""
    ticker = ticker.upper().strip()
    try:
        from chart_analyzer import generate_chart_bytes, analyze_single
        img = generate_chart_bytes(ticker)
        if not img:
            return jsonify({'error': 'chart generation failed'}), 500
        result = analyze_single(ticker, img)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pattern-signals')
def pattern_signals_endpoint():
    """VCP + TA-Lib candlestick pattern signals from pattern_detector.py."""
    return jsonify(_load_json(DOCS / 'pattern_signals.json'))


@app.route('/api/pattern-signals/<ticker>')
def pattern_signals_ticker(ticker):
    data = _load_json(DOCS / 'pattern_signals.json')
    sig = data.get('signals', {}).get(ticker.upper())
    if not sig:
        return jsonify({'error': f'{ticker} not found'}), 404
    return jsonify(sig)


@app.route('/api/market-breadth')
def market_breadth():
    """Market breadth from fundamental_scores: % in uptrend, % with positive upside, etc."""
    def compute(df):
        total = len(df)
        if total == 0:
            return {'total': 0}
        result = {'total': total}
        if 'trend_template_pass' in df.columns:
            n = int(df['trend_template_pass'].sum())
            result['trend_pass'] = n
            result['trend_pass_pct'] = round(n / total * 100, 1)
        if 'rs_line_at_new_high' in df.columns:
            n = int(df['rs_line_at_new_high'].sum())
            result['rs_at_high'] = n
            result['rs_at_high_pct'] = round(n / total * 100, 1)
        if 'analyst_upside_pct' in df.columns:
            n = int((df['analyst_upside_pct'].dropna() > 0).sum())
            result['positive_upside'] = n
            result['positive_upside_pct'] = round(n / total * 100, 1)
        if 'earnings_warning' in df.columns:
            result['earnings_warnings'] = int(df['earnings_warning'].sum())
        return result

    us, eu = {}, {}
    try:
        us = compute(_load_csv(DOCS / 'fundamental_scores.csv'))
    except Exception:
        pass
    try:
        eu = compute(_load_csv(DOCS / 'european_fundamental_scores.csv'))
    except Exception:
        pass
    return jsonify({'us': us, 'eu': eu})


@app.route('/api/factor-status')
def factor_status():
    """
    Factor Status Dashboard — aggregates factor performance from daily CSVs.
    Returns current state of VALUE, QUALITY, MOMENTUM, INSIDER, SMART MONEY factors.
    Based on Fama-French + AQR framework + Piotroski + Greenblatt.
    """
    import json as _json
    from datetime import datetime as _dt
    import numpy as _np

    result = {
        'generated_at': _dt.utcnow().isoformat() + 'Z',
        'factors': {},
        'combined_score': 0,
        'factor_alignment': '',
        'recommendation': '',
    }

    scores = []

    # ── FACTOR 1: VALUE ──────────────────────────────────────────────────────
    try:
        vdf = _load_csv(DOCS / 'value_opportunities.csv')
        if not vdf.empty:
            n = len(vdf)
            avg_score = float(vdf['value_score'].mean()) if 'value_score' in vdf.columns else 0
            avg_fcf   = float(vdf['fcf_yield_pct'].dropna().mean()) if 'fcf_yield_pct' in vdf.columns else None
            avg_upside= float(vdf['analyst_upside_pct'].dropna().mean()) if 'analyst_upside_pct' in vdf.columns else None
            grade_a   = int((vdf['conviction_grade'] == 'A').sum()) if 'conviction_grade' in vdf.columns else 0
            grade_b   = int((vdf['conviction_grade'] == 'B').sum()) if 'conviction_grade' in vdf.columns else 0

            # Signal: more grade-A picks + good upside = value is finding opportunities
            val_signal = (grade_a * 10 + grade_b * 5) / max(n, 1) * 100
            val_score  = min(100, val_signal + (avg_upside or 0) * 0.5)

            if avg_upside is not None and avg_upside >= 25 and grade_a >= 3:
                status = 'ATTRACTIVE'
            elif avg_upside is not None and avg_upside >= 15:
                status = 'NEUTRAL'
            else:
                status = 'EXPENSIVE'

            result['factors']['value'] = {
                'status': status,
                'score': round(val_score),
                'opportunities': n,
                'grade_a': grade_a,
                'grade_b': grade_b,
                'avg_upside_pct': round(avg_upside, 1) if avg_upside is not None else None,
                'avg_fcf_yield': round(avg_fcf, 1) if avg_fcf is not None else None,
                'interpretation': (
                    'El universo VALUE presenta múltiples picks de alta convicción con upside atractivo.'
                    if status == 'ATTRACTIVE' else
                    'Oportunidades VALUE moderadas. Ser selectivo.' if status == 'NEUTRAL' else
                    'Mercado caro según analistas. Pocos picks con margen de seguridad.'
                ),
                'academic_edge': '+4–6% anual sobre el mercado (Fama-French, décadas de datos)',
            }
            scores.append(val_score)
    except Exception as e:
        result['factors']['value'] = {'status': 'N/A', 'score': 0, 'error': str(e)}

    # ── FACTOR 2: QUALITY (Piotroski F-Score) ──────────────────────────────
    try:
        fdf = _load_csv(DOCS / 'fundamental_scores.csv')
        if not fdf.empty and 'piotroski_score' in fdf.columns:
            ps = fdf['piotroski_score'].dropna()
            if len(ps) > 0:
                avg_f    = float(ps.mean())
                pct_strong = float((ps >= 8).sum() / len(ps) * 100)
                pct_weak   = float((ps <= 2).sum() / len(ps) * 100)
                avg_roic = float(fdf['roic_greenblatt'].dropna().mean()) if 'roic_greenblatt' in fdf.columns else None

                qual_score = min(100, avg_f / 9 * 60 + pct_strong * 0.8 - pct_weak * 1.2)

                if avg_f >= 7 and pct_strong >= 20:
                    status = 'STRONG'
                elif avg_f >= 5:
                    status = 'MIXED'
                else:
                    status = 'WEAK'

                result['factors']['quality'] = {
                    'status': status,
                    'score': round(qual_score),
                    'avg_piotroski': round(avg_f, 1),
                    'pct_strong': round(pct_strong, 1),
                    'pct_weak': round(pct_weak, 1),
                    'avg_roic_pct': round(avg_roic, 1) if avg_roic is not None else None,
                    'interpretation': (
                        f'Universo de alta calidad: {pct_strong:.0f}% de empresas con F-Score ≥8. Señal de compra.'
                        if status == 'STRONG' else
                        f'Calidad mixta en el universo. F-Score medio {avg_f:.1f}/9. Ser selectivo.'
                        if status == 'MIXED' else
                        f'Alto % de value traps ({pct_weak:.0f}% con F≤2). Máxima cautela.'
                    ),
                    'academic_edge': '+13.4% anual F≥8 vs mercado (Equities Lab, 20 años)',
                }
                scores.append(qual_score)
    except Exception as e:
        result['factors']['quality'] = {'status': 'N/A', 'score': 0, 'error': str(e)}

    # ── FACTOR 3: MOMENTUM ──────────────────────────────────────────────────
    try:
        mdf = _load_csv(DOCS / 'momentum_opportunities.csv')
        regime_us = _load_json(DOCS / 'market_regime.json') or {}
        n_mom = len(mdf) if not mdf.empty else 0
        regime_name = regime_us.get('market_regime', regime_us.get('regime', 'UNKNOWN'))
        avg_mom = float(mdf['momentum_score'].mean()) if not mdf.empty and 'momentum_score' in mdf.columns else 0

        if n_mom >= 10 and 'UP' in str(regime_name).upper():
            status = 'BULL'
            mom_score = min(100, 50 + n_mom * 2 + avg_mom * 0.3)
        elif n_mom >= 3:
            status = 'MIXED'
            mom_score = min(80, 30 + n_mom * 3)
        else:
            status = 'BEAR'
            mom_score = max(0, n_mom * 5)

        result['factors']['momentum'] = {
            'status': status,
            'score': round(mom_score),
            'opportunities': n_mom,
            'avg_score': round(avg_mom, 1),
            'market_regime': regime_name,
            'interpretation': (
                f'Momentum fuerte: {n_mom} setups VCP activos. Régimen {regime_name}.'
                if status == 'BULL' else
                f'Momentum mixto: {n_mom} setups. Mercado en transición.'
                if status == 'MIXED' else
                f'Sin setups momentum válidos. Mercado sin tendencia o en corrección.'
            ),
            'academic_edge': '+4–8% anual (presente en 40+ mercados, Jegadeesh & Titman)',
        }
        scores.append(mom_score)
    except Exception as e:
        result['factors']['momentum'] = {'status': 'N/A', 'score': 0, 'error': str(e)}

    # ── FACTOR 4: INSIDER / SMART MONEY ────────────────────────────────────
    try:
        idf = _load_csv(DOCS / 'recurring_insiders.csv')
        n_ins = len(idf) if not idf.empty else 0
        cluster = 0
        if not idf.empty and 'unique_insiders' in idf.columns:
            cluster = int((idf['unique_insiders'] >= 2).sum())
        high_conf = 0
        if not idf.empty and 'confidence_score' in idf.columns:
            high_conf = int((idf['confidence_score'] >= 70).sum())

        if n_ins >= 5 and cluster >= 2:
            status = 'BULLISH'
            ins_score = min(100, 50 + n_ins * 3 + cluster * 5)
        elif n_ins >= 2:
            status = 'NEUTRAL'
            ins_score = min(70, 30 + n_ins * 5)
        else:
            status = 'QUIET'
            ins_score = 20

        result['factors']['insider'] = {
            'status': status,
            'score': round(ins_score),
            'active_signals': n_ins,
            'cluster_buying': cluster,
            'high_confidence': high_conf,
            'interpretation': (
                f'Señal de insiders potente: {cluster} cluster buys (múltiples directivos). Alta información material.'
                if status == 'BULLISH' else
                f'{n_ins} insiders activos. Señal moderada — monitorear si escala.'
                if status == 'NEUTRAL' else
                'Sin actividad insider significativa. Esperar señales antes de actuar.'
            ),
            'academic_edge': '+6–10.2% anual con cluster buying (Lakonishok & Lee, revisión 2022)',
        }
        scores.append(ins_score)
    except Exception as e:
        result['factors']['insider'] = {'status': 'N/A', 'score': 0, 'error': str(e)}

    # ── FACTOR 5: SMART MONEY (Hedge Fund 13F) ──────────────────────────────
    try:
        hf_data = _load_json(DOCS / 'hedge_fund_summary.json') or {}
        consensus = hf_data.get('top_consensus', [])
        n_hf    = len(consensus)
        multi   = sum(1 for r in consensus if r.get('funds_count', 0) >= 2)
        top3    = sum(1 for r in consensus if r.get('funds_count', 0) >= 3)
        funds_n = len(hf_data.get('funds_scraped', []))

        if multi >= 10:
            status = 'STRONG'
            sm_score = min(100, 50 + multi * 2 + top3 * 3)
        elif multi >= 4:
            status = 'MODERATE'
            sm_score = min(70, 30 + multi * 4)
        else:
            status = 'SPARSE'
            sm_score = 20

        result['factors']['smart_money'] = {
            'status': status,
            'score': round(sm_score),
            'total_positions': n_hf,
            'consensus_2plus': multi,
            'consensus_3plus': top3,
            'funds_tracked': funds_n,
            'as_of': hf_data.get('generated_at', ''),
            'interpretation': (
                f'Alto consenso entre mega-gestores: {multi} tickers con 2+ fondos coincidiendo.'
                if status == 'STRONG' else
                f'Consenso moderado: {multi} tickers compartidos entre varios fondos.'
                if status == 'MODERATE' else
                'Posiciones de hedge funds dispersas. Sin fuerte convergencia de ideas.'
            ),
            'academic_edge': 'Fondos 13F con alpha histórico positivo neto de fees (AQR, 2021)',
        }
        scores.append(sm_score)
    except Exception as e:
        result['factors']['smart_money'] = {'status': 'N/A', 'score': 0, 'error': str(e)}

    # ── COMBINED SCORE + RECOMMENDATION ─────────────────────────────────────
    if scores:
        combined = round(sum(scores) / len(scores))
        result['combined_score'] = combined

        green  = sum(1 for f in result['factors'].values() if f.get('status') in ('ATTRACTIVE', 'STRONG', 'BULL', 'BULLISH'))
        yellow = sum(1 for f in result['factors'].values() if f.get('status') in ('NEUTRAL', 'MIXED', 'MODERATE'))
        red    = sum(1 for f in result['factors'].values() if f.get('status') in ('EXPENSIVE', 'WEAK', 'BEAR', 'QUIET', 'SPARSE'))

        if green >= 4:
            result['factor_alignment'] = 'FULL_ALIGNMENT'
            result['recommendation'] = f'Alineación de factores excepcional ({green}/5 verdes). Condiciones ideales para entradas VALUE concentradas. Size up.'
        elif green >= 3:
            result['factor_alignment'] = 'GOOD'
            result['recommendation'] = f'{green}/5 factores favorables. Entorno constructivo — construir posiciones gradualmente.'
        elif green >= 2:
            result['factor_alignment'] = 'MIXED'
            result['recommendation'] = f'Señales mixtas ({green} verde, {yellow} neutro, {red} rojo). Entradas selectivas con position sizing conservador.'
        elif red >= 3:
            result['factor_alignment'] = 'HOSTILE'
            result['recommendation'] = f'{red}/5 factores adversos. Capital preservation mode — reducir exposición y esperar mejor setup.'
        else:
            result['factor_alignment'] = 'CAUTIOUS'
            result['recommendation'] = 'Entorno incierto. Mantener posiciones existentes pero no escalar.'

        # AQR insight: Value-Momentum correlation
        v_score = result['factors'].get('value', {}).get('score', 50)
        m_score = result['factors'].get('momentum', {}).get('score', 50)
        if abs(v_score - m_score) <= 20:
            result['value_momentum_correlation'] = 'LOW'
            result['value_momentum_note'] = 'Value y Momentum alineados — combinación óptima según AQR (máximo Sharpe ratio histórico).'
        elif v_score > m_score + 20:
            result['value_momentum_correlation'] = 'DIVERGENT_VALUE_LEADS'
            result['value_momentum_note'] = 'Value supera a Momentum — típico en mercados de recuperación. Históricamente precede rebote del factor Momentum.'
        else:
            result['value_momentum_correlation'] = 'DIVERGENT_MOMENTUM_LEADS'
            result['value_momentum_note'] = 'Momentum supera a Value — mercado en tendencia. Añadir filtro momentum a picks VALUE.'

    return jsonify(result)


@app.route('/api/daily-briefing')
def daily_briefing():
    data = _load_json(DOCS / 'daily_briefing.json')
    if not data:
        return jsonify({'narrative': None, 'date': None}), 200
    return jsonify(data)


@app.route('/api/insiders-insight')
def insiders_insight():
    data = _load_json(DOCS / 'recurring_insiders_insight.json')
    if not data:
        return jsonify({'narrative': None, 'date': None}), 200
    return jsonify(data)


@app.route('/api/industry-groups-insight')
def industry_groups_insight():
    data = _load_json(DOCS / 'industry_groups_insight.json')
    if not data:
        return jsonify({'narrative': None, 'date': None}), 200
    return jsonify(data)


@app.route('/api/options-flow-insight')
def options_flow_insight():
    data = _load_json(DOCS / 'options_flow_insight.json')
    if not data:
        return jsonify({'narrative': None, 'date': None}), 200
    return jsonify(data)


@app.route('/api/value-eu-insight')
def value_eu_insight():
    data = _load_json(DOCS / 'value_eu_insight.json')
    if not data:
        return jsonify({'narrative': None, 'date': None}), 200
    return jsonify(data)


@app.route('/api/portfolio-insight')
def portfolio_insight():
    data = _load_json(DOCS / 'portfolio_tracker' / 'portfolio_insight.json')
    if not data:
        return jsonify({'narrative': None, 'date': None}), 200
    return jsonify(data)


@app.route('/api/analyze-ai/<ticker>')
def analyze_ticker_ai(ticker):
    """On-demand AI analysis combining all available data for a ticker."""
    import os as _os
    ticker = ticker.upper().strip()

    # Gather data from CSVs
    ticker_data = {}

    # Value opportunities (US + EU)
    for csv_name in ('value_opportunities.csv', 'value_conviction.csv',
                     'european_value_opportunities.csv', 'european_value_conviction.csv'):
        try:
            df = pd.read_csv(DOCS / csv_name)
            if 'ticker' in df.columns:
                row = df[df['ticker'].str.upper() == ticker]
                if not row.empty:
                    r = row.iloc[0]
                    ticker_data.update({
                        'value_score': _sf(r.get('value_score')),
                        'conviction_grade': _notna_str(r, 'conviction_grade'),
                        'sector': _notna_str(r, 'sector'),
                        'analyst_upside_pct': _sf(r.get('analyst_upside_pct')),
                        'fcf_yield_pct': _sf(r.get('fcf_yield_pct')),
                        'risk_reward_ratio': _sf(r.get('risk_reward_ratio')),
                        'dividend_yield_pct': _sf(r.get('dividend_yield_pct')),
                        'piotroski_score': _sf(r.get('piotroski_score')),
                        'peg_ratio': _sf(r.get('peg_ratio')),
                        'days_to_earnings': _sf(r.get('days_to_earnings')),
                        'earnings_warning': bool(r.get('earnings_warning', False)),
                        'market': _notna_str(r, 'market', 'US'),
                    })
                    break
        except Exception:
            pass

    # Fundamental scores
    try:
        rfund = _row(DF_FUND, ticker)
        if rfund is not None:
            ticker_data.update({
                'roe_pct': _sf(rfund.get('roe_pct')),
                'profit_margin_pct': _sf(rfund.get('profit_margin_pct')),
                'revenue_growth_pct': _sf(rfund.get('revenue_growth_pct')),
                'current_ratio': _sf(rfund.get('current_ratio')),
                'interest_coverage': _sf(rfund.get('interest_coverage')),
            })
    except Exception:
        pass

    # Insider activity
    try:
        rins = _row(DF_INSIDERS, ticker)
        if rins is not None:
            ticker_data['insider_purchases'] = _sf(rins.get('purchase_count'))
            ticker_data['insider_insiders'] = _sf(rins.get('unique_insiders'))
    except Exception:
        pass

    # Existing thesis
    thesis_text = ''
    try:
        theses = _load_json(DOCS / 'theses.json')
        if isinstance(theses, dict):
            t = theses.get(ticker, {})
            thesis_text = t.get('thesis_narrative', '') or t.get('overview', '') if isinstance(t, dict) else str(t)
            if len(thesis_text) > 400:
                thesis_text = thesis_text[:400] + '...'
    except Exception:
        pass

    # Macro regime
    macro_regime = 'DESCONOCIDO'
    try:
        mr = _load_json(DOCS / 'macro_radar.json')
        macro_regime = mr.get('regime', {}).get('name', 'DESCONOCIDO')
    except Exception:
        pass

    if not ticker_data and not thesis_text:
        return jsonify({'ticker': ticker, 'narrative': None, 'error': 'No data found for ticker'}), 200

    # Build prompt
    lines = [f"Ticker: {ticker}"]
    if ticker_data.get('sector'):
        lines.append(f"Sector: {ticker_data['sector']}")
    if ticker_data.get('value_score') is not None:
        lines.append(f"Value Score: {ticker_data['value_score']:.0f}/100 | Grade: {ticker_data.get('conviction_grade', '?')}")
    if ticker_data.get('analyst_upside_pct') is not None:
        lines.append(f"Upside analistas: {ticker_data['analyst_upside_pct']:+.1f}%")
    if ticker_data.get('fcf_yield_pct') is not None:
        lines.append(f"FCF Yield: {ticker_data['fcf_yield_pct']:.1f}%")
    if ticker_data.get('risk_reward_ratio') is not None:
        lines.append(f"R:R ratio: {ticker_data['risk_reward_ratio']:.1f}x")
    if ticker_data.get('piotroski_score') is not None:
        lines.append(f"Piotroski F-Score: {ticker_data['piotroski_score']:.0f}/9")
    if ticker_data.get('peg_ratio') is not None:
        lines.append(f"PEG ratio: {ticker_data['peg_ratio']:.2f}")
    if ticker_data.get('roe_pct') is not None:
        lines.append(f"ROE: {ticker_data['roe_pct']:.1f}%")
    if ticker_data.get('profit_margin_pct') is not None:
        lines.append(f"Margen neto: {ticker_data['profit_margin_pct']:.1f}%")
    if ticker_data.get('revenue_growth_pct') is not None:
        lines.append(f"Crecimiento revenue: {ticker_data['revenue_growth_pct']:+.1f}%")
    if ticker_data.get('insider_purchases'):
        lines.append(f"Compras insider: {ticker_data['insider_purchases']:.0f} operaciones por {ticker_data.get('insider_insiders', 1):.0f} directivo(s)")
    if ticker_data.get('days_to_earnings') is not None:
        warn = " ⚠ RIESGO EARNINGS" if ticker_data.get('earnings_warning') else ''
        lines.append(f"Próximos earnings: {ticker_data['days_to_earnings']:.0f} días{warn}")

    metrics_block = '\n'.join(lines)
    thesis_block = f"\nTesis existente (extracto):\n{thesis_text}" if thesis_text else ""

    prompt = f"""Eres un analista value/GARP al estilo Lynch-Graham. Genera una evaluación de convicción concisa en español (4-5 frases, máx 160 palabras) para el siguiente ticker.

Régimen macro: {macro_regime}

Datos fundamentales:
{metrics_block}{thesis_block}

Tu evaluación debe:
1) Resumir qué hace atractivo (o no) a este ticker en el entorno actual
2) Identificar el factor de convicción más importante (FCF, insiders, valoración, crecimiento...)
3) Señalar el principal riesgo o punto a vigilar
4) Dar una conclusión de posicionamiento concreta (entrar, esperar, evitar, reducir)

Tono: analítico, honesto, estilo nota de investigación. Sin emojis. Sin repetir los números exactos del prompt."""

    groq_key = _os.environ.get('GROQ_API_KEY', '')
    if not groq_key:
        return jsonify({'ticker': ticker, 'narrative': None, 'error': 'GROQ_API_KEY not configured'}), 200

    try:
        from groq import Groq as _Groq
        client = _Groq(api_key=groq_key)
        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=250,
            temperature=0.25,
        )
        narrative = resp.choices[0].message.content.strip()
        return jsonify({'ticker': ticker, 'narrative': narrative, 'date': pd.Timestamp.now().strftime('%Y-%m-%d')})
    except Exception as e:
        return jsonify({'ticker': ticker, 'narrative': None, 'error': str(e)}), 200


@app.route('/api/macro-radar')
def macro_radar():
    data = _load_json(DOCS / 'macro_radar.json')
    if not data:
        return jsonify({"error": "No macro radar data available"}), 404
    return jsonify(data)


@app.route('/api/macro-countries')
def macro_countries():
    data = _load_json(DOCS / 'macro_country_analysis.json')
    if not data:
        return jsonify({"error": "No macro country data available"}), 404
    return jsonify(data)


@app.route('/api/macro-radar/history')
def macro_radar_history():
    """Return 60-day time series of composite_score + regime for charting."""
    import glob as glob_mod
    history_dir = DOCS / 'history'
    pattern = str(history_dir / '*' / 'macro_radar.json')
    files = sorted(glob_mod.glob(pattern))  # sorted by date (dirname)
    points = []
    for fpath in files[-60:]:  # last 60 days max
        d = _load_json(fpath)
        if d and 'composite_score' in d:
            points.append({
                'date': d.get('date', ''),
                'composite_score': d.get('composite_score'),
                'composite_pct': d.get('composite_pct'),
                'regime': d.get('regime', {}).get('name', ''),
                'regime_color': d.get('regime', {}).get('color', ''),
            })
    # Also include today's (not yet in history)
    today = _load_json(DOCS / 'macro_radar.json')
    if today and 'composite_score' in today:
        today_date = today.get('date', '')
        if not any(p['date'] == today_date for p in points):
            points.append({
                'date': today_date,
                'composite_score': today.get('composite_score'),
                'composite_pct': today.get('composite_pct'),
                'regime': today.get('regime', {}).get('name', ''),
                'regime_color': today.get('regime', {}).get('color', ''),
            })
    return jsonify({'history': sorted(points, key=lambda x: x['date'])})


@app.route('/api/economic-calendar')
def economic_calendar_api():
    """Return upcoming macro events (Fed, CPI, NFP) from economic_calendar.json."""
    from datetime import datetime as dt2
    data = _load_json(DOCS / 'economic_calendar.json')
    if not data:
        return jsonify({'events': []}), 200
    today = dt2.now().strftime('%Y-%m-%d')
    upcoming = [e for e in data.get('events', []) if e.get('date', '') >= today]
    return jsonify({'events': upcoming, 'total': len(upcoming)})


@app.route('/api/score-history/<ticker>', methods=['GET'])
def score_history(ticker):
    """Return VALUE score history for a ticker across all daily snapshots."""
    ticker = ticker.upper().strip()
    history_dir = DOCS / 'history'
    results = []
    if history_dir.exists():
        for date_dir in sorted(history_dir.iterdir()):
            if not date_dir.is_dir():
                continue
            csv_path = date_dir / 'value_opportunities.csv'
            if not csv_path.exists():
                continue
            try:
                df_h = pd.read_csv(csv_path, usecols=lambda c: c in {'ticker', 'value_score', 'conviction_grade'})
                row = df_h[df_h['ticker'] == ticker]
                if not row.empty:
                    r = row.iloc[0]
                    results.append({
                        'date': date_dir.name,
                        'score': round(float(r['value_score']), 1),
                        'grade': str(r.get('conviction_grade', '') or '') or None,
                    })
            except Exception:
                pass
    return jsonify({'ticker': ticker, 'history': results, 'points': len(results)})


@app.route('/api/dividend-traps')
def dividend_traps():
    """Return dividend trap analysis from dividend_traps.json."""
    data = _load_json(DOCS / 'dividend_traps.json')
    if not data:
        return jsonify({"error": "No dividend trap data. Run dividend_trap_scanner.py"}), 404
    return jsonify(data)


_div_calendar_cache: dict = {'date': '', 'data': None}

@app.route('/api/dividend-calendar')
def dividend_calendar():
    """Upcoming ex-dividend dates for quality stocks — dividend timing tool."""
    from datetime import datetime as dt2, timedelta
    import yfinance as yf
    import concurrent.futures

    today = dt2.now()
    today_str = today.strftime('%Y-%m-%d')

    # Return cache if same day
    if _div_calendar_cache['date'] == today_str and _div_calendar_cache['data']:
        return jsonify(_div_calendar_cache['data'])

    # ONLY AI-filtered VALUE opportunities (quality confirmed by IA)
    candidates: dict = {}  # ticker -> {company, sector, div_yield, fund_score, value_score, ...}

    for csv_name, source_label in [
        ('value_opportunities_filtered.csv', 'value_filtered'),
        ('european_value_opportunities_filtered.csv', 'value_filtered'),
    ]:
        df = _load_csv(DOCS / csv_name)
        if df is not None and not df.empty:
            for t in df.index:
                dy = _sf(df.loc[t].get('dividend_yield_pct'))
                if dy and dy > 0:
                    candidates[t] = {
                        'company': _notna_str(df.loc[t], 'company_name', t),
                        'sector': _notna_str(df.loc[t], 'sector', ''),
                        'dividend_yield': dy,
                        'fundamental_score': _sf(df.loc[t].get('fundamental_score')),
                        'value_score': _sf(df.loc[t].get('value_score')),
                        'conviction_grade': _notna_str(df.loc[t], 'conviction_grade', ''),
                        'ai_verdict': _notna_str(df.loc[t], 'ai_verdict', ''),
                        'ai_confidence': _notna_str(df.loc[t], 'ai_confidence', ''),
                        'source': source_label,
                    }

    if not candidates:
        _div_calendar_cache['date'] = today_str
        _div_calendar_cache['data'] = {'events': [], 'total': 0, 'as_of': today_str}
        return jsonify(_div_calendar_cache['data'])

    # Fetch ex-dividend dates from yfinance (parallel, max 60 tickers)
    tickers_to_check = list(candidates.keys())[:60]
    events = []

    def _get_exdiv(ticker):
        try:
            t_obj = yf.Ticker(ticker)
            cal = t_obj.calendar
            if not cal:
                return None
            exdiv = cal.get('Ex-Dividend Date')
            div_date = cal.get('Dividend Date')
            if not exdiv:
                return None
            # Convert to string
            exdiv_str = str(exdiv)
            if exdiv_str < today_str:
                return None  # past date
            # Check if within 45 days
            from datetime import date
            if hasattr(exdiv, 'year'):
                days_to = (exdiv - today.date()).days
            else:
                days_to = (dt2.strptime(exdiv_str, '%Y-%m-%d').date() - today.date()).days
            if days_to > 45 or days_to < 0:
                return None
            info = t_obj.info
            last_div_value = info.get('lastDividendValue')
            price = info.get('currentPrice') or info.get('previousClose')
            return {
                'ticker': ticker,
                'ex_dividend_date': exdiv_str,
                'payment_date': str(div_date) if div_date else None,
                'days_to_exdiv': days_to,
                'dividend_per_share': round(last_div_value, 4) if last_div_value else None,
                'current_price': round(price, 2) if price else None,
                'capture_yield_pct': round((last_div_value / price) * 100, 2) if last_div_value and price and price > 0 else None,
            }
        except Exception:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_get_exdiv, t): t for t in tickers_to_check}
        for future in concurrent.futures.as_completed(futures):
            ticker = futures[future]
            result = future.result()
            if result:
                c = candidates[ticker]
                result.update({
                    'company': c['company'],
                    'sector': c['sector'],
                    'dividend_yield_annual': c['dividend_yield'],
                    'fundamental_score': c['fundamental_score'],
                    'value_score': c['value_score'],
                    'conviction_grade': c['conviction_grade'],
                    'ai_verdict': c.get('ai_verdict', ''),
                    'ai_confidence': c.get('ai_confidence', ''),
                    'source': c['source'],
                })
                events.append(result)

    events.sort(key=lambda x: x['days_to_exdiv'])

    result_data = {
        'events': events,
        'total': len(events),
        'tickers_scanned': len(tickers_to_check),
        'as_of': today_str,
    }
    _div_calendar_cache['date'] = today_str
    _div_calendar_cache['data'] = result_data
    return jsonify(result_data)


@app.route('/api/earnings-calendar')
def earnings_calendar():
    """Return upcoming earnings from fundamental_scores.csv sorted by date."""
    from datetime import datetime as dt2
    df = _load_csv(DOCS / 'fundamental_scores.csv')
    if df is None:
        return jsonify({'earnings': []}), 200

    df = df.reset_index()
    rows = []
    today_str = dt2.now().strftime('%Y-%m-%d')
    for _, row in df.iterrows():
        edate = str(row.get('earnings_date', '') or '')
        if not edate or edate in ('nan', 'NaT', 'None', ''):
            continue
        # Only future earnings
        if edate < today_str:
            continue
        rows.append({
            'ticker': str(row.get('ticker', '')),
            'company': str(row.get('company_name', '')),
            'sector': str(row.get('sector', '')),
            'earnings_date': edate,
            'days_to_earnings': _sf(row.get('days_to_earnings')),
            'earnings_warning': bool(row.get('earnings_warning', False)),
            'earnings_catalyst': bool(row.get('earnings_catalyst', False)),
            'fundamental_score': _sf(row.get('fundamental_score')),
            'current_price': _sf(row.get('current_price')),
            'analyst_upside_pct': _sf(row.get('analyst_upside_pct')),
        })
    rows.sort(key=lambda x: x['earnings_date'])
    return jsonify({'earnings': rows, 'total': len(rows), 'as_of': today_str})


@app.route('/api/smart-portfolio', methods=['GET'])
def smart_portfolio():
    """Return AI-built smart portfolio from smart_portfolio.json."""
    data = _load_json(DOCS / 'smart_portfolio.json')
    if not data:
        return jsonify({"error": "No portfolio data. Run portfolio_builder.py"}), 404
    return jsonify(data)


@app.route('/api/backtest')
def backtest():
    """Build live backtest stats from portfolio tracker recommendations.csv."""
    import csv as _csv, statistics as _stats

    csv_path = DOCS / 'portfolio_tracker' / 'recommendations.csv'
    if not csv_path.exists():
        return jsonify({"error": "No backtest data available"})

    rows = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        for r in _csv.DictReader(f):
            rows.append(r)

    if not rows:
        return jsonify({"error": "No backtest data available"})

    def _f(v):
        try: return float(v) if v not in ('', None) else None
        except: return None

    def _stats_for(returns):
        if not returns:
            return {"count": 0, "win_rate": None, "avg_return": None,
                    "median_return": None, "best": None, "worst": None}
        wins = [x for x in returns if x > 0]
        return {
            "count": len(returns),
            "win_rate": round(len(wins) / len(returns) * 100, 1),
            "avg_return": round(sum(returns) / len(returns), 2),
            "median_return": round(_stats.median(returns), 2),
            "best": round(max(returns), 2),
            "worst": round(min(returns), 2),
        }

    # Collect per-strategy returns and per-score-bucket returns
    strat_7d: dict[str, list[float]] = {}
    score_buckets_7d: dict[str, list[float]] = {"≥70": [], "60-69": [], "50-59": [], "<50": []}
    trades_7d = []

    for r in rows:
        ret7  = _f(r.get('return_7d'))
        score = _f(r.get('value_score'))
        strat = r.get('strategy', 'VALUE')
        if ret7 is None:
            continue
        strat_7d.setdefault(strat, []).append(ret7)
        if score is not None:
            if score >= 70:   score_buckets_7d["≥70"].append(ret7)
            elif score >= 60: score_buckets_7d["60-69"].append(ret7)
            elif score >= 50: score_buckets_7d["50-59"].append(ret7)
            else:             score_buckets_7d["<50"].append(ret7)
        trades_7d.append({
            "ticker":          r.get('ticker'),
            "company_name":    r.get('company_name'),
            "strategy":        strat,
            "signal_date":     r.get('signal_date'),
            "signal_price":    _f(r.get('signal_price')),
            "value_score":     score,
            "sector":          r.get('sector'),
            "return_7d":       ret7,
            "win_7d":          ret7 > 0,
            "max_drawdown_30d": _f(r.get('max_drawdown_30d')),
        })

    all_7d = [t["return_7d"] for t in trades_7d]
    # Conviction slice: only value_score ≥ 55 (matches frontend default filter)
    conviction_7d = [t["return_7d"] for t in trades_7d if t["value_score"] is not None and t["value_score"] >= 55]
    trades_7d_sorted = sorted(trades_7d, key=lambda x: x["return_7d"], reverse=True)

    # Date range
    dates = sorted(set(r.get('signal_date','') for r in rows if r.get('signal_date')))
    market_regime = rows[0].get('market_regime', '') if rows else ''

    result = {
        "type": "live_tracker",
        "date_range": {"from": dates[0] if dates else None, "to": dates[-1] if dates else None},
        "total_signals": len(rows),
        "market_context": market_regime,
        "periods": {
            "7d": {
                "overall": _stats_for(all_7d),
                "conviction": _stats_for(conviction_7d),
                "by_strategy": {s: _stats_for(rets) for s, rets in strat_7d.items()},
                "by_score": {bucket: _stats_for(rets) for bucket, rets in score_buckets_7d.items()},
            }
        },
        "top_performers_7d": trades_7d_sorted[:10],
        "worst_performers_7d": trades_7d_sorted[-10:][::-1],
        "trades": trades_7d_sorted,
    }
    return jsonify(result)


@app.route('/api/owner-earnings/<ticker>')
def owner_earnings_endpoint(ticker):
    """Owner Earnings valuation model — precio de compra para X% retorno anual."""
    ticker = ticker.upper().strip()
    try:
        target_return = float(request.args.get('target_return', 0.15))
        ev_fcf_target = request.args.get('ev_fcf_target')
        ev_fcf_target = float(ev_fcf_target) if ev_fcf_target else None

        from owner_earnings import calculate
        result = calculate(ticker, target_return=target_return, ev_fcf_target=ev_fcf_target)
        return jsonify(result)
    except Exception as e:
        return jsonify({"ticker": ticker, "error": str(e)}), 500


@app.route('/api/owner-earnings-batch')
def owner_earnings_batch():
    """Owner Earnings para todos los tickers VALUE del universo TIKR."""
    try:
        target_return = float(request.args.get('target_return', 0.15))
        from owner_earnings import batch_calculate
        results = batch_calculate(target_return=target_return)

        sorted_results = sorted(
            [v for v in results.values() if isinstance(v, dict) and v.get('buy_price')],
            key=lambda x: x.get('upside_pct') or -999,
            reverse=True
        )

        return jsonify({
            "target_return_pct": round(target_return * 100, 1),
            "total": len(sorted_results),
            "results": sorted_results
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/theses/<ticker>')
def theses(ticker):
    ticker = ticker.upper().strip()
    data = _load_json(DOCS / 'theses.json')
    if not data:
        data = _load_json(DOCS / 'investment_theses.json')
    if not data:
        return jsonify({"ticker": ticker, "thesis": None})
    # Try ticker__value, then ticker__momentum, then plain ticker
    thesis = data.get(f'{ticker}__value') or data.get(f'{ticker}__momentum') or data.get(ticker)
    return jsonify({"ticker": ticker, "thesis": thesis})


@app.route('/api/search')
def search_tickers():
    """Autocomplete: busca tickers por nombre de empresa o símbolo.
    Falls back to yfinance search if no local results found."""
    q = request.args.get('q', '').strip().lower()
    if not q:
        return jsonify({"results": []})

    results = []
    seen = set()

    def add(ticker, company_name, sector=''):
        if ticker not in seen and len(results) < 20:
            results.append({
                "ticker": ticker,
                "company_name": company_name or ticker,
                "sector": sector or '',
            })
            seen.add(ticker)

    def matches(ticker, company_name):
        if not isinstance(ticker, str):
            return False
        return q in ticker.lower() or q in (company_name or '').lower()

    # 1. Pipeline tickers (DF_5D — más completo)
    if not DF_5D.empty:
        for t in DF_5D.index:
            company = _notna_str(DF_5D.loc[t], 'company_name')
            if matches(t, company):
                add(t, company, _notna_str(DF_5D.loc[t], 'sector', ''))

    # 2. Fundamental scores (incluye EU)
    if not DF_FUND.empty:
        for t in DF_FUND.index:
            if t in seen:
                continue
            company = _notna_str(DF_FUND.loc[t], 'company_name')
            if matches(t, company):
                sector = _notna_str(DF_FUND.loc[t], 'sector_name', '') or _notna_str(DF_FUND.loc[t], 'sector', '')
                add(t, company, sector)

    # 3. Super scores (cobertura amplia)
    if not DF_SCORES.empty:
        for t in DF_SCORES.index:
            if t in seen:
                continue
            company = _notna_str(DF_SCORES.loc[t], 'company_name')
            if matches(t, company):
                add(t, company, _notna_str(DF_SCORES.loc[t], 'sector', ''))

    # 4. Ticker cache (JSON — complementa los CSVs)
    for t, data in TICKER_CACHE.items():
        if t in seen:
            continue
        company = (data.get('company_name') or '').strip()
        if matches(t, company):
            add(t, company, data.get('sector', '') or '')

    # 5. yfinance fallback
    try:
        import yfinance as yf
        q_upper = q.upper()

        # Always try direct ticker lookup if query looks like a ticker (≤6 chars, no spaces)
        if ' ' not in q and len(q) <= 6 and q_upper not in seen:
            try:
                t_obj = yf.Ticker(q_upper)
                info = t_obj.info or {}
                name = info.get('longName') or info.get('shortName', '')
                price = info.get('currentPrice') or info.get('previousClose')
                if name and price and price > 0:
                    # Insert at top (exact ticker match)
                    results.insert(0, {
                        "ticker": q_upper,
                        "company_name": name,
                        "sector": info.get('sector', ''),
                    })
                    seen.add(q_upper)
            except Exception:
                pass

        # yfinance search for company name queries (3+ chars, few local results)
        if len(q) >= 3 and len(results) < 5:
            try:
                search_results = yf.Search(q)
                for item in (search_results.quotes or [])[:5]:
                    sym = (item.get('symbol') or '').upper()
                    name = item.get('longname') or item.get('shortname') or ''
                    if sym and sym not in seen and not sym.endswith('.F'):
                        add(sym, name, item.get('sector', ''))
            except Exception:
                pass
    except Exception:
        pass

    # Ordenar: exacto > nombre empieza por query > ticker empieza > contiene
    # Prioritize clean tickers (no dots = US primary) over foreign listings
    def sort_key(r):
        t = r['ticker'].lower()
        c = r['company_name'].lower()
        has_dot = '.' in r['ticker']  # foreign listing penalty
        if t == q:                     return (0, has_dot)
        if c.startswith(q):            return (1, has_dot)
        if t.startswith(q):            return (2, has_dot)
        if q in c:                     return (3, has_dot)
        return (4, has_dot)

    results.sort(key=sort_key)
    return jsonify({"results": results[:10]})


# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/analyze-personal-portfolio', methods=['POST'])
@limiter.limit("10 per minute")
def analyze_personal_portfolio():
    """Analyze user's personal portfolio positions with yfinance + AI."""
    import os as _os, json as _json, re as _re

    if request.content_length and request.content_length > 512_000:  # 512KB max
        return jsonify({'error': 'Request too large'}), 413
    data = request.get_json(force=True, silent=True) or {}
    positions = data.get('positions', [])
    if not positions:
        return jsonify({'error': 'No positions provided'}), 400

    groq_key = _os.environ.get('GROQ_API_KEY', '')
    if not groq_key:
        return jsonify({'error': 'GROQ_API_KEY not configured'}), 500

    import yfinance as _yf
    from datetime import timedelta as _td

    # ── Position sizing helpers (inline from position_sizer.py) ──────────
    def _calc_atr_volatility(ticker_obj, cur_price):
        """ATR-based volatility as fraction of price."""
        try:
            end = datetime.now()
            df = ticker_obj.history(start=end - _td(days=45), end=end)
            if df.empty or len(df) < 14:
                return 0.20
            h, l, c = df['High'], df['Low'], df['Close']
            tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
            atr = float(tr.rolling(14).mean().iloc[-1])
            return atr / cur_price if cur_price > 0 else 0.20
        except Exception:
            return 0.20

    def _calc_kelly(win_rate=0.75, avg_win=5.0, avg_loss=-3.0, max_pos=0.10):
        if avg_loss >= 0 or avg_win <= 0:
            return 0.0
        ratio = abs(avg_win / avg_loss)
        kelly = (win_rate * ratio - (1 - win_rate)) / ratio
        return max(0, min(kelly * 0.5, max_pos))

    # Load backtest metrics if available
    _bt_win_rate, _bt_avg_win, _bt_avg_loss = 0.75, 5.0, -3.0
    try:
        bt_path = DOCS / 'backtest_metrics.json'
        if bt_path.exists():
            bt = _json.loads(bt_path.read_text())
            _bt_win_rate = bt.get('win_rate', 0.75)
            _bt_avg_win  = bt.get('avg_win', 5.0)
            _bt_avg_loss = bt.get('avg_loss', -3.0)
    except Exception:
        pass

    enriched = []
    for pos in positions:
        ticker  = str(pos.get('ticker', '')).upper().strip()
        shares  = float(pos.get('shares', 0) or 0)
        avg_p   = float(pos.get('avg_price', 0) or 0)
        currency = pos.get('currency', 'USD')
        if not ticker or shares <= 0:
            continue
        try:
            t_obj = _yf.Ticker(ticker)
            info  = t_obj.info
        except Exception:
            t_obj = None
            info  = {}
        cur_price = (info.get('currentPrice') or info.get('regularMarketPrice')
                     or info.get('previousClose') or avg_p or 0)
        mkt_val  = shares * cur_price
        cost     = shares * avg_p
        pl_pct   = ((cur_price - avg_p) / avg_p * 100) if avg_p else 0
        fcf_yield = None
        try:
            fcf = info.get('freeCashflow')
            mc  = info.get('marketCap')
            if fcf and mc and mc > 0:
                fcf_yield = fcf / mc * 100
        except Exception:
            pass

        # ── Position sizing for this holding ─────────────────────────
        volatility = _calc_atr_volatility(t_obj, cur_price) if t_obj else 0.20
        kelly_pct  = _calc_kelly(_bt_win_rate, _bt_avg_win, _bt_avg_loss)

        # Volatility multiplier (high vol → smaller, low vol → larger)
        vol_mult = 0.7 if volatility > 0.15 else (1.2 if volatility < 0.05 else 1.0)
        opt_size_pct = min(kelly_pct * vol_mult, 0.10)  # capped at 10%

        # Stop loss based on 2x ATR
        stop_loss_pct_atr = volatility * 2
        stop_loss_price   = cur_price * (1 - stop_loss_pct_atr)

        # Risk: how much we lose if price hits stop
        risk_per_share = cur_price - stop_loss_price
        risk_amount    = shares * risk_per_share

        enriched.append({
            'ticker': ticker, 'shares': shares, 'avg_price': avg_p,
            'current_price': cur_price, 'currency': currency,
            'market_value': mkt_val, 'cost_basis': cost, 'pl_pct': pl_pct,
            'pl_abs': mkt_val - cost,
            'company_name': info.get('shortName', ticker),
            'sector': info.get('sector', ''),
            'forward_pe': info.get('forwardPE'),
            'trailing_pe': info.get('trailingPE'),
            'analyst_target': info.get('targetMeanPrice'),
            'analyst_upside': (
                (info.get('targetMeanPrice') - cur_price) / cur_price * 100
                if info.get('targetMeanPrice') and cur_price else None
            ),
            'fcf_yield': fcf_yield,
            'dividend_yield': info.get('dividendYield'),
            'revenue_growth': info.get('revenueGrowth'),
            'roe': info.get('returnOnEquity'),
            'debt_to_equity': info.get('debtToEquity'),
            'fifty_two_week_high': info.get('fiftyTwoWeekHigh'),
            'fifty_two_week_low': info.get('fiftyTwoWeekLow'),
            # Position sizing fields
            'volatility_pct': round(volatility * 100, 1),
            'kelly_pct': round(kelly_pct * 100, 1),
            'optimal_size_pct': round(opt_size_pct * 100, 1),
            'stop_loss_atr': round(stop_loss_price, 2),
            'stop_loss_pct_atr': round(stop_loss_pct_atr * 100, 1),
            'risk_amount': round(risk_amount, 0),
            'vol_multiplier': vol_mult,
        })

    if not enriched:
        return jsonify({'error': 'No valid positions fetched'}), 400

    total_value = sum(p['market_value'] for p in enriched) or 1
    for p in enriched:
        p['portfolio_pct'] = p['market_value'] / total_value * 100

    macro_regime = 'DESCONOCIDO'
    try:
        mr = _load_json(DOCS / 'macro_radar.json')
        macro_regime = mr.get('regime', {}).get('name', 'DESCONOCIDO')
    except Exception:
        pass

    lines = []
    for p in enriched:
        l = (f"- {p['ticker']} ({p.get('company_name','')}): "
             f"{p['portfolio_pct']:.1f}% cartera | precio actual {p['currency']}{p['current_price']:.2f} "
             f"| P&L: {p['pl_pct']:+.1f}%")
        if p.get('forward_pe'):   l += f" | PE fwd: {p['forward_pe']:.1f}x"
        if p.get('analyst_target'): l += f" | target analistas: {p['currency']}{p['analyst_target']:.2f} ({p.get('analyst_upside',0):+.1f}%)"
        if p.get('fcf_yield'):    l += f" | FCF yield: {p['fcf_yield']:.1f}%"
        if p.get('sector'):       l += f" | Sector: {p['sector']}"
        lines.append(l)

    tickers_list = ', '.join(p['ticker'] for p in enriched)
    prompt = f"""Eres un analista value/GARP al estilo Lynch-Graham. El usuario tiene esta cartera personal ({len(enriched)} posiciones, valor total ~${total_value:,.0f}):

{chr(10).join(lines)}

Régimen macro actual: {macro_regime}

Analiza la cartera y devuelve ÚNICAMENTE un JSON válido con esta estructura exacta (sin texto extra, sin markdown):
{{
  "portfolio_analysis": {{
    "summary": "evaluación global en 2-3 frases",
    "concentration_warning": "aviso si hay concentración excesiva en sector/posición, o null",
    "overall_recommendation": "qué hacer con la cartera en conjunto en 1-2 frases"
  }},
  "positions": [
    {{
      "ticker": "XXX",
      "action": "MANTENER",
      "conviction": "ALTA",
      "target_price": 123.45,
      "stop_loss": 90.00,
      "recommended_weight_pct": 15.0,
      "analysis": "2-3 frases sobre esta posición: tesis vigente o rota, valoración actual",
      "key_risk": "principal riesgo en 1 frase",
      "options_strategy": "COVERED_CALL",
      "options_rationale": "1-2 frases: por qué esta estrategia ahora, qué zonas de strike/expiry buscar y qué objetivo persigue"
    }}
  ]
}}

Valores posibles para action: MANTENER, AÑADIR, REDUCIR, VENDER
Valores posibles para conviction: ALTA, MEDIA, BAJA
Valores posibles para options_strategy: COVERED_CALL (vender call OTM para ingresos), PROTECTIVE_PUT (comprar put para proteger), COLLAR (vender call + comprar put), BUY_MORE (añadir sin opciones), CASH_SECURED_PUT (vender put para entrar más barato), TRAILING_STOP (stop dinámico sin opciones), HOLD (mantener sin acción adicional), SELL (cerrar posición)
Cubre estos tickers en orden: {tickers_list}
Sé honesto: si la tesis se ha roto, di VENDER. Los pesos recomendados deben sumar ~100%.
Para options_strategy: sé específico — si recomiendas COVERED_CALL indica el rango de delta objetivo (~0.25-0.35 OTM), si es PROTECTIVE_PUT indica cuánto downside proteger."""

    try:
        from groq import Groq as _Groq
        client = _Groq(api_key=groq_key)
        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=4096,
            temperature=0.25,
            response_format={"type": "json_object"},
        )
        ai_text = resp.choices[0].message.content.strip()
        ai_result = _json.loads(ai_text)
    except Exception:
        ai_result = None

    result_positions = []
    for p in enriched:
        row = {
            'ticker': p['ticker'],
            'company_name': p.get('company_name', p['ticker']),
            'sector': p.get('sector', ''),
            'shares': p['shares'],
            'avg_price': round(p['avg_price'], 4),
            'current_price': round(p['current_price'], 4),
            'currency': p['currency'],
            'market_value': round(p['market_value'], 2),
            'pl_pct': round(p['pl_pct'], 2),
            'pl_abs': round(p['pl_abs'], 2),
            'portfolio_pct': round(p['portfolio_pct'], 2),
            'forward_pe': p.get('forward_pe'),
            'analyst_target': p.get('analyst_target'),
            'analyst_upside': p.get('analyst_upside'),
            'fcf_yield': p.get('fcf_yield'),
            'dividend_yield': p.get('dividend_yield'),
            'fifty_two_week_high': p.get('fifty_two_week_high'),
            'fifty_two_week_low': p.get('fifty_two_week_low'),
            'action': 'MANTENER', 'conviction': 'MEDIA',
            'target_price': p.get('analyst_target'),
            'stop_loss': None, 'recommended_weight_pct': round(p['portfolio_pct'], 1),
            'analysis': '', 'key_risk': '',
            'options_strategy': '', 'options_rationale': '',
            # Position sizing
            'volatility_pct': p.get('volatility_pct'),
            'kelly_pct': p.get('kelly_pct'),
            'optimal_size_pct': p.get('optimal_size_pct'),
            'stop_loss_atr': p.get('stop_loss_atr'),
            'stop_loss_pct_atr': p.get('stop_loss_pct_atr'),
            'risk_amount': p.get('risk_amount'),
            'vol_multiplier': p.get('vol_multiplier'),
        }
        if ai_result and 'positions' in ai_result:
            for ap in ai_result['positions']:
                if str(ap.get('ticker', '')).upper() == p['ticker']:
                    row.update({
                        'action': ap.get('action', 'MANTENER'),
                        'conviction': ap.get('conviction', 'MEDIA'),
                        'target_price': ap.get('target_price') or p.get('analyst_target'),
                        'stop_loss': ap.get('stop_loss'),
                        'recommended_weight_pct': ap.get('recommended_weight_pct', row['recommended_weight_pct']),
                        'analysis': ap.get('analysis', ''),
                        'key_risk': ap.get('key_risk', ''),
                        'options_strategy': ap.get('options_strategy', ''),
                        'options_rationale': ap.get('options_rationale', ''),
                    })
                    break
        result_positions.append(row)

    # ── Portfolio-level risk metrics ────────────────────────────────────
    total_risk = sum(r.get('risk_amount', 0) or 0 for r in result_positions)
    total_risk_pct = (total_risk / total_value * 100) if total_value else 0
    oversized = [r['ticker'] for r in result_positions
                 if r.get('portfolio_pct', 0) > (r.get('optimal_size_pct', 100) or 100) * 1.5]

    return jsonify({
        'total_value': round(total_value, 2),
        'risk_metrics': {
            'total_risk_amount': round(total_risk, 0),
            'total_risk_pct': round(total_risk_pct, 1),
            'kelly_base_pct': round(_calc_kelly(_bt_win_rate, _bt_avg_win, _bt_avg_loss) * 100, 1),
            'oversized_positions': oversized,
            'win_rate_used': round(_bt_win_rate * 100 if _bt_win_rate <= 1 else _bt_win_rate, 1),
        },
        'portfolio_analysis': ai_result.get('portfolio_analysis', {}) if ai_result else {},
        'positions': result_positions,
    })


# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/options-chain/<ticker>')
def options_chain(ticker: str):
    """Return real options contracts across all horizons + thesis-aware Groq recommendation.

    Buckets expiries into short (30-75d), medium (3-6mo), long (6-15mo LEAPS).
    Groq receives the full investment thesis and selects the optimal contract
    across ALL horizons — not just the nearest expiry.
    """
    import yfinance as _yf, json as _json, os as _os, re as _re, math as _math
    from datetime import datetime as _dt

    def _safe_float(val, default=0.0):
        try:
            return float(val or default)
        except (TypeError, ValueError):
            return default

    ticker    = ticker.upper().strip()[:10]
    cur_price = _safe_float(request.args.get('price'), 0.0)
    pl_pct    = _safe_float(request.args.get('pl'), 0.0)
    upside    = _safe_float(request.args.get('upside'), 0.0)
    action    = request.args.get('action', 'MANTENER')
    conviction= request.args.get('conviction', 'MEDIA')
    thesis    = (request.args.get('thesis', '') or '')[:800]   # AI analysis text
    key_risk  = (request.args.get('key_risk', '') or '')[:300]

    try:
        t = _yf.Ticker(ticker)
        if not cur_price:
            info = t.info
            cur_price = (info.get('currentPrice') or info.get('regularMarketPrice')
                         or info.get('previousClose') or 0)
        if not cur_price:
            return jsonify({'error': 'No se pudo obtener precio actual'}), 400

        all_expiries = t.options
        if not all_expiries:
            return jsonify({'error': f'{ticker} no tiene opciones negociables (puede ser acción europea o de baja liquidez)'}), 404

        # ── Bucket all available expiries ─────────────────────────────────
        today = _dt.now().date()

        def bucket(days):
            if days < 75:    return 'short'    # 30-75d: covered call income
            if days < 180:   return 'medium'   # 3-6mo: balanced
            if days <= 450:  return 'long'     # 6-15mo: LEAPS, thesis plays
            return None

        buckets = {'short': [], 'medium': [], 'long': []}
        for exp in all_expiries:
            d = _dt.strptime(exp, '%Y-%m-%d').date()
            days_out = (d - today).days
            if days_out < 20:
                continue
            b = bucket(days_out)
            if b and len(buckets[b]) < 2:   # max 2 per bucket
                buckets[b].append((days_out, exp))

        # Fall back: if no buckets filled, take first 3 available
        selected_expiries = []
        for b in ['short', 'medium', 'long']:
            selected_expiries.extend(buckets[b])
        if not selected_expiries:
            for exp in all_expiries[:3]:
                d = _dt.strptime(exp, '%Y-%m-%d').date()
                selected_expiries.append(((d - today).days, exp))

        selected_expiries.sort()

        def _safe_int(v):
            """Convert to int, handling NaN/None/float safely."""
            if v is None or (isinstance(v, float) and (_math.isnan(v) or _math.isinf(v))):
                return 0
            try:
                return int(v)
            except (ValueError, TypeError):
                return 0

        def _safe_float(v, default=0.0):
            if v is None or (isinstance(v, float) and (_math.isnan(v) or _math.isinf(v))):
                return default
            try:
                return float(v)
            except (ValueError, TypeError):
                return default

        def row_to_dict(row, kind, days_out):
            d = {
                'strike':        round(_safe_float(row['strike']), 2),
                'bid':           round(_safe_float(row.get('bid', 0)), 2),
                'ask':           round(_safe_float(row.get('ask', 0)), 2),
                'mid':           round(_safe_float(row.get('mid', 0)), 2),
                'volume':        _safe_int(row.get('volume', 0)),
                'open_interest': _safe_int(row.get('openInterest', 0)),
                'iv':            round(_safe_float(row.get('impliedVolatility', 0)) * 100, 1),
                'pct_otm':       round(_safe_float(row.get('pct_otm', 0)), 1),
            }
            if kind == 'call':
                d['annual_yield_pct'] = round(_safe_float(row.get('annual_yield', 0)), 1)
            else:
                d['cost_pct'] = round(_safe_float(row.get('cost_pct', 0)), 1)
            return d

        result_expiries = []
        for days_out, exp in selected_expiries:
            chain = t.option_chain(exp)

            calls_df = chain.calls.copy()
            calls_df = calls_df[
                (calls_df['strike'] > cur_price * 1.02) &
                (calls_df['strike'] < cur_price * 1.25) &
                (calls_df['bid'] > 0)
            ].copy()
            if not calls_df.empty:
                calls_df['openInterest'] = calls_df['openInterest'].fillna(0)
                calls_df['volume']       = calls_df['volume'].fillna(0)
                calls_df['mid']          = (calls_df['bid'] + calls_df['ask']) / 2
                calls_df['pct_otm']      = (calls_df['strike'] - cur_price) / cur_price * 100
                calls_df['annual_yield'] = calls_df['mid'] / cur_price * (365 / max(days_out, 1)) * 100
                calls_df = calls_df.nlargest(5, 'openInterest')

            puts_df = chain.puts.copy()
            puts_df = puts_df[
                (puts_df['strike'] < cur_price * 0.98) &
                (puts_df['strike'] > cur_price * 0.80) &
                (puts_df['bid'] > 0)
            ].copy()
            if not puts_df.empty:
                puts_df['openInterest'] = puts_df['openInterest'].fillna(0)
                puts_df['volume']       = puts_df['volume'].fillna(0)
                puts_df['mid']      = (puts_df['bid'] + puts_df['ask']) / 2
                puts_df['pct_otm']  = (cur_price - puts_df['strike']) / cur_price * 100
                puts_df['cost_pct'] = puts_df['mid'] / cur_price * 100
                puts_df = puts_df.nlargest(5, 'openInterest')

            result_expiries.append({
                'expiry':          exp,
                'days_out':        days_out,
                'bucket':          bucket(days_out) or 'short',
                'covered_calls':   [row_to_dict(r, 'call', days_out) for _, r in calls_df.iterrows()],
                'protective_puts': [row_to_dict(r, 'put',  days_out) for _, r in puts_df.iterrows()],
            })

        # ── Thesis-aware Groq recommendation across ALL horizons ──────────
        groq_key = _os.environ.get('GROQ_API_KEY', '')
        ai_recommendation = None
        if groq_key and result_expiries:
            # Build a compact contracts summary per expiry for Groq
            contracts_text = []
            for exp_data in result_expiries:
                calls_str = '; '.join(
                    f"CALL ${c['strike']} prima ${c['mid']} yield={c['annual_yield_pct']}%/año OTM={c['pct_otm']}%"
                    for c in exp_data['covered_calls'][:3]
                ) or 'sin liquidez'
                puts_str = '; '.join(
                    f"PUT ${p['strike']} prima ${p['mid']} coste={p['cost_pct']}% OTM={p['pct_otm']}%"
                    for p in exp_data['protective_puts'][:3]
                ) or 'sin liquidez'
                contracts_text.append(
                    f"  [{exp_data['bucket'].upper()} — {exp_data['expiry']} ({exp_data['days_out']}d)]\n"
                    f"    Calls: {calls_str}\n"
                    f"    Puts:  {puts_str}"
                )

            thesis_block = f"\nTesis de inversión: {thesis}" if thesis else ''
            risk_block   = f"\nRiesgo principal: {key_risk}" if key_risk else ''

            prompt = f"""Eres un asesor de opciones que da instrucciones EXACTAS y ULTRA-ESPECÍFICAS. El usuario va a abrir su broker y ejecutar la orden AHORA MISMO. No puede haber ambigüedad.

POSICIÓN ACTUAL:
- Ticker: {ticker}
- Precio actual: ${cur_price:.2f}
- P&L actual: {pl_pct:+.1f}%
- Upside según analistas: {upside:+.1f}%
- Acción recomendada: {action}
- Convicción: {conviction}{thesis_block}{risk_block}

CONTRATOS DISPONIBLES EN EL MERCADO AHORA MISMO:
{chr(10).join(contracts_text)}

INSTRUCCIONES CRÍTICAS:
1. Elige EXACTAMENTE UN contrato principal de la lista de arriba. NO inventes strikes ni expiries que no estén en la lista.
2. Si la convicción es ALTA y el upside >20%, NO vendas covered calls que limiten — mejor LEAPS call o protective put.
3. Si la posición está en pérdida y la tesis es intacta, considera LEAPS call para duplicar exposición a bajo coste.
4. Si hay poco upside, covered call OTM genera ingreso.
5. Piensa en el horizonte de la tesis: catalizador a 6-12 meses → expiry LEAPS.

RESPONDE EN JSON VÁLIDO (sin markdown, sin texto extra). Incluye instrucciones tan claras que un principiante pueda ejecutar la orden:
{{
  "recommended_strategy": "COVERED_CALL | PROTECTIVE_PUT | COLLAR | LEAPS_CALL | CASH_SECURED_PUT | HOLD",
  "thesis_alignment": "por qué esta estrategia encaja con la tesis en 1-2 frases",
  "primary_contract": {{
    "action": "COMPRAR | VENDER",
    "type": "CALL | PUT",
    "strike": 123.00,
    "expiry": "YYYY-MM-DD",
    "premium_approx": 2.50,
    "total_cost_100_shares": 250.00,
    "horizon": "corto | medio | largo",
    "order_instructions": "En tu broker: Sell to Open 1x {ticker} CALL $strike exp DD/MM/YYYY, limit price $X.XX. Necesitas tener 100 acciones."
  }},
  "secondary_contract": null,
  "profit_if_target": "Si {ticker} sube a $X (target analistas), ganas $Y (+Z%) con este contrato",
  "loss_if_drops": "Si {ticker} cae un 15% a $X, pierdes $Y (-Z%)",
  "max_risk": "Lo máximo que puedes perder es $X (la prima pagada / asignación a $strike)",
  "when_to_close": "Cierra la posición cuando: condición exacta (precio, fecha, % ganancia)",
  "step_by_step": "1. Abre tu broker. 2. Busca {ticker} opciones. 3. Selecciona [tipo] strike $X exp DD/MM/YYYY. 4. Pon orden [compra/venta] limit a $X.XX. 5. Confirma."
}}"""

            try:
                from groq import Groq as _Groq
                client = _Groq(api_key=groq_key)
                resp = client.chat.completions.create(
                    model='llama-3.3-70b-versatile',
                    messages=[{'role': 'user', 'content': prompt}],
                    max_tokens=800,
                    temperature=0.2,
                    response_format={"type": "json_object"},
                )
                ai_text = resp.choices[0].message.content.strip()
                ai_recommendation = _json.loads(ai_text)
            except Exception:
                ai_recommendation = None

        return jsonify({
            'ticker':           ticker,
            'current_price':    round(cur_price, 2),
            'expiries':         result_expiries,
            'ai_recommendation': ai_recommendation,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/technical-signals')
def technical_signals():
    """Return technical signals summary + detail from docs/ CSVs."""
    try:
        summary_path = DOCS / 'technical_signals_summary.csv'
        signals_path = DOCS / 'technical_signals.csv'
        if not summary_path.exists() or not signals_path.exists():
            return jsonify({'error': 'Technical signals not generated yet'}), 404
        summary_df = pd.read_csv(str(summary_path))
        signals_df = pd.read_csv(str(signals_path))
        return jsonify({
            'summary': summary_df.to_dict(orient='records'),
            'signals': signals_df.to_dict(orient='records'),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/live-prices')
def live_prices():
    """Real-time key market prices — VIX, SPY, Oil, Gold, 10Y, 30Y, DXY.
    Cached 30s to avoid hammering yfinance on every frontend poll."""
    import yfinance as yf
    import time

    cache = getattr(live_prices, '_cache', None)
    now = time.time()
    if cache and now - cache['ts'] < 30:
        return jsonify(cache['data'])

    TICKERS = {
        'vix':  ('^VIX',     'VIX',       'volatility'),
        'spy':  ('SPY',      'S&P 500',   'equity'),
        'oil':  ('CL=F',     'Petróleo',  'commodity'),
        'gold': ('GLD',      'Oro',       'commodity'),
        'tnx':  ('^TNX',     '10Y Yield', 'rate'),
        'tyx':  ('^TYX',     '30Y Yield', 'rate'),
        'dxy':  ('DX-Y.NYB', 'Dólar DXY', 'currency'),
    }

    result = {}
    try:
        symbols = [v[0] for v in TICKERS.values()]
        raw = yf.download(symbols, period='2d', interval='1d',
                          progress=False, auto_adjust=True, group_by='ticker')

        for key, (sym, label, kind) in TICKERS.items():
            try:
                closes = raw[sym]['Close'].dropna()

                if closes is None or len(closes) < 1:
                    result[key] = {'symbol': sym, 'label': label, 'kind': kind,
                                   'current': None, 'prev_close': None, 'change_pct': None}
                    continue

                current    = float(closes.iloc[-1])
                prev_close = float(closes.iloc[-2]) if len(closes) >= 2 else current
                change_pct = (current / prev_close - 1) * 100 if prev_close else 0.0

                result[key] = {
                    'symbol':     sym,
                    'label':      label,
                    'kind':       kind,
                    'current':    round(current, 2),
                    'prev_close': round(prev_close, 2),
                    'change_pct': round(change_pct, 2),
                }
            except Exception:
                result[key] = {'symbol': sym, 'label': label, 'kind': kind,
                               'current': None, 'prev_close': None, 'change_pct': None}

    except Exception as e:
        return jsonify({'error': str(e), 'prices': {}}), 500

    from datetime import datetime, timezone, timedelta
    eastern  = datetime.now(timezone(timedelta(hours=-4)))
    weekday  = eastern.weekday()
    hour     = eastern.hour + eastern.minute / 60
    market_open = (weekday < 5) and (9.5 <= hour < 16.0)

    payload = {
        'prices':      result,
        'market_open': market_open,
        'fetched_at':  datetime.utcnow().isoformat() + 'Z',
    }
    live_prices._cache = {'ts': now, 'data': payload}
    return jsonify(payload)


@app.route('/api/price-history/<ticker>')
def price_history(ticker: str):
    """Return 6-month weekly closing prices for mini charts / sparklines."""
    import yfinance as yf
    ticker = ticker.upper().strip()
    try:
        hist = yf.Ticker(ticker).history(period='6mo', interval='1wk')
        if hist.empty:
            return jsonify({'ticker': ticker, 'prices': []})
        prices = [
            {'date': str(idx.date()), 'close': round(float(row['Close']), 2)}
            for idx, row in hist.iterrows()
        ]
        return jsonify({'ticker': ticker, 'prices': prices})
    except Exception as e:
        return jsonify({'ticker': ticker, 'prices': [], 'error': str(e)})


@app.route('/api/portfolio-prices', methods=['POST'])
def portfolio_prices():
    """Fast current-price lookup for a list of tickers (portfolio P&L widget)."""
    import yfinance as yf
    data = request.get_json(silent=True) or {}
    tickers = [t.upper().strip() for t in (data.get('tickers') or []) if t]
    if not tickers:
        return jsonify({'prices': {}})
    prices: dict[str, float] = {}
    for t in tickers:
        try:
            info = yf.Ticker(t).fast_info
            price = float(getattr(info, 'last_price', None) or 0)
            if price > 0:
                prices[t] = round(price, 4)
        except Exception:
            pass
    return jsonify({'prices': prices})


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    port = int(os.environ.get('PORT', sys.argv[1] if len(sys.argv) > 1 else 5002))
    print(f"\n🚀 Ticker Analyzer API en http://localhost:{port}")
    print("   /api/analyze/AAPL  |  /api/tickers  |  /api/health\n")
    app.run(host='0.0.0.0', port=port, debug=False)
