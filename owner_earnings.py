#!/usr/bin/env python3
"""
Owner Earnings Calculator — basado en la plantilla de valoración profesional.

FCF = net_income + D&A - CapEx_mantenimiento
D&A = EBITDA - EBIT
CapEx_mant = min(|CapEx|, D&A)  ← exceso sobre D&A = inversión en crecimiento

Salida principal: precio de compra para conseguir X% de retorno anual.
  exit_price = FCF_per_share_5y × EV_FCF_target − net_debt_per_share_5y
  buy_price  = exit_price / (1 + target_return)^years
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Optional

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False


TIKR_PATH = Path("docs/tikr_earnings_data.json")
_cache: dict = {}
_price_cache: dict = {}  # ticker → {year: annual_close_price}


def _load_tikr() -> dict:
    global _cache
    if _cache:
        return _cache
    if TIKR_PATH.exists():
        _cache = json.loads(TIKR_PATH.read_text()).get("data", {})
    return _cache


def _fv(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _metric(metrics: dict, key: str, year) -> Optional[float]:
    series = metrics.get(key, {})
    return _fv(series.get(str(year), series.get(year)))


def _capex_maintenance(ebitda: float, ebit: float, capex: float) -> float:
    """CapEx mantenimiento = min(|CapEx|, D&A). El exceso es inversión en crecimiento."""
    dna = ebitda - ebit
    return min(abs(capex), dna)


def _owner_earnings(cfo: Optional[float], ni: float, ebitda: float, ebit: float, capex: float) -> float:
    """FCF = CFO − CapEx_maint si CFO disponible, sino net_income + D&A − CapEx_maint."""
    capex_maint = _capex_maintenance(ebitda, ebit, capex)
    if cfo:
        return cfo - capex_maint
    dna = ebitda - ebit
    return ni + dna - capex_maint


def _fcf_conversion_median(historical_fcf: dict, metrics: dict, years: list) -> float:
    """Ratio mediano FCF/EBITDA histórico para proyecciones."""
    ratios = []
    for yr in years:
        fcf = historical_fcf.get(yr)
        ebitda = _metric(metrics, "ebitda", yr)
        if fcf and ebitda and ebitda > 0:
            ratios.append(fcf / ebitda)
    return statistics.median(ratios) if ratios else 0.45


def _historical_annual_prices(ticker: str, years: list) -> dict:
    """Precios de cierre anuales (último día del año fiscal) via yfinance."""
    if not _YF_AVAILABLE or not years:
        return {}
    t = ticker.upper()
    if t in _price_cache:
        return _price_cache[t]
    try:
        oldest = min(years)
        hist = yf.Ticker(t).history(start=f"{oldest - 1}-01-01", end=f"{max(years) + 1}-01-01",
                                     interval="1mo", timeout=10)
        if hist.empty:
            return {}
        hist.index = hist.index.tz_localize(None) if hist.index.tz else hist.index
        result = {}
        for yr in years:
            # Precio de cierre en diciembre del año fiscal
            yr_data = hist[hist.index.year == yr]
            if not yr_data.empty:
                result[yr] = float(yr_data["Close"].iloc[-1])
        _price_cache[t] = result
        return result
    except Exception:
        return {}


def _shares_change_median(metrics: dict, years: list) -> float:
    changes = []
    for i in range(1, min(len(years), 5)):
        s_new = _metric(metrics, "shares_diluted", years[i - 1])
        s_old = _metric(metrics, "shares_diluted", years[i])
        if s_new and s_old and s_old > 0:
            changes.append((s_new - s_old) / s_old)
    return statistics.median(changes) if changes else -0.003


def calculate(
    ticker: str,
    target_return: float = 0.15,
    ev_fcf_target: Optional[float] = None,
    per_target: Optional[float] = None,
    ev_ebitda_target: Optional[float] = None,
) -> dict:
    """
    Calcula el modelo Owner Earnings para un ticker.

    Returns dict con:
      historical_fcf, historical_fcf_per_share, capex_pct_sales_median,
      median_ev_fcf, forward_fcf, price_targets,
      buy_price, exit_price, exit_year, upside_pct, signal
    """
    data = _load_tikr()
    td = data.get(ticker.upper()) or data.get(ticker)
    if not td:
        return {"error": f"Ticker {ticker} not in TIKR data"}

    fh = td.get("financials_history", {})
    metrics = fh.get("metrics", {})
    years = sorted(fh.get("annual_years", []), reverse=True)[:7]
    ae_raw = td.get("analyst_estimates", {})

    price_data = td.get("price", {})
    current_price = _fv(price_data.get("c"))
    market_cap = _fv(price_data.get("mc"))
    tev = _fv(price_data.get("tev"))

    # ── Histórico Owner Earnings ──────────────────────────────────────────────
    historical_fcf: dict = {}
    historical_fcf_ps: dict = {}
    capex_pct_sales: list = []
    fcf_breakdown: dict = {}   # desglose paso a paso para verificación

    # Actuals FCF de /est (más preciso — cubre últimos 3 años)
    est_actuals_fcf = {
        int(yr): _fv(v.get("fcf"))
        for yr, v in ae_raw.get("recent", {}).items()
        if _fv(v.get("fcf"))
    }

    for yr in years:
        ni     = _metric(metrics, "net_income", yr)
        ebitda = _metric(metrics, "ebitda", yr)
        ebit   = _metric(metrics, "ebit", yr)
        capex  = _metric(metrics, "capex", yr)
        shares = _metric(metrics, "shares_diluted", yr)
        cfo    = _metric(metrics, "cash_from_operations", yr)
        rev    = _metric(metrics, "total_revenue", yr)

        if None in (ni, ebitda, ebit, capex, shares) or shares == 0:
            continue

        dna = ebitda - ebit
        capex_maint = _capex_maintenance(ebitda, ebit, capex)
        est_fcf = est_actuals_fcf.get(yr)

        if est_fcf:
            oe = est_fcf
            source = "tikr_actuals"
        elif cfo:
            oe = cfo - capex_maint
            source = "cfo_based"
        else:
            oe = ni + dna - capex_maint
            source = "ni_based"

        historical_fcf[yr] = round(oe, 2)
        historical_fcf_ps[yr] = round(oe / shares, 4)

        fcf_breakdown[yr] = {
            "revenue":       round(rev, 2) if rev else None,
            "ebitda":        round(ebitda, 2),
            "ebitda_margin": round(ebitda / rev * 100, 1) if rev and rev > 0 else None,
            "dna":           round(dna, 2),
            "ebit":          round(ebit, 2),
            "ebit_margin":   round(ebit / rev * 100, 1) if rev and rev > 0 else None,
            "net_income":    round(ni, 2),
            "net_margin":    round(ni / rev * 100, 1) if rev and rev > 0 else None,
            "cfo":           round(cfo, 2) if cfo else None,
            "capex":         round(capex, 2),
            "capex_maint":   round(capex_maint, 2),
            "owner_earnings": round(oe, 2),
            "source":        source,
        }

        if rev and rev > 0:
            capex_pct_sales.append(capex_maint / rev)

    capex_pct_median = statistics.median(capex_pct_sales) if capex_pct_sales else 0.10

    # ── Múltiplos de referencia ───────────────────────────────────────────────
    multiples = td.get("multiples", {})
    ntm = td.get("ntm", {})

    ntm_fcf_yield = _fv(multiples.get("ntm_fcf_yield_pct"))
    ntm_pe = _fv(multiples.get("ntm_pe"))
    ntm_ev_ebitda = _fv(multiples.get("ntm_ev_ebitda"))
    ntm_fcf_m = _fv(ntm.get("ntm_fcf") or ntm.get("fcf"))

    # Mediana EV/FCF histórica: usamos precios anuales reales vía yfinance
    annual_prices = _historical_annual_prices(ticker, years)
    hist_ev_fcf_multiples = []
    for yr in years:
        price_yr = annual_prices.get(yr)
        sh = _metric(metrics, "shares_diluted", yr)
        oe = historical_fcf.get(yr)
        debt = _metric(metrics, "total_debt", yr)
        cash = _metric(metrics, "cash", yr)
        if price_yr and sh and oe and oe > 0 and debt is not None and cash is not None:
            mc_yr = price_yr * sh
            ev_yr = mc_yr + (debt - cash)
            hist_ev_fcf_multiples.append(ev_yr / oe)

    if hist_ev_fcf_multiples:
        median_ev_fcf = statistics.median(hist_ev_fcf_multiples)
    elif ntm_fcf_yield and ntm_fcf_yield > 0:
        median_ev_fcf = 100 / ntm_fcf_yield
    elif ntm_fcf_m and tev and ntm_fcf_m > 0:
        median_ev_fcf = tev / ntm_fcf_m
    else:
        median_ev_fcf = 25.0

    if ev_fcf_target is None:
        ev_fcf_target = round(median_ev_fcf * 0.90, 1)
    if per_target is None:
        per_target = round((ntm_pe or 25) * 0.85, 1)
    if ev_ebitda_target is None:
        ev_ebitda_target = round((ntm_ev_ebitda or 15) * 0.85, 1)

    # ── Forward FCF ───────────────────────────────────────────────────────────
    forward_est = ae_raw.get("forward", {})
    current_year = ae_raw.get("current_year", 2026)

    latest_yr = years[0] if years else None
    shares_proj = _metric(metrics, "shares_diluted", latest_yr) or 250.0
    net_debt_proj = (
        (_metric(metrics, "total_debt", latest_yr) or 0)
        - (_metric(metrics, "cash", latest_yr) or 0)
    )

    median_shares_change = _shares_change_median(metrics, years)
    conv_median = _fcf_conversion_median(historical_fcf, metrics, years)

    forward_fcf: dict = {}
    forward_net_debt: dict = {}
    forward_shares: dict = {}

    for yr_str in sorted(forward_est.keys()):
        est = forward_est[yr_str]
        fcf_m = _fv(est.get("fcf"))

        if not (fcf_m and fcf_m > 0):
            ebitda_fwd = _fv(est.get("ebitda"))
            fcf_m = (ebitda_fwd * conv_median) if ebitda_fwd else None

        if not (fcf_m and fcf_m > 0):
            continue

        shares_proj *= (1 + median_shares_change)
        net_debt_proj = max(0.0, net_debt_proj - fcf_m * 0.30)

        forward_fcf[yr_str] = {
            "fcf": round(fcf_m, 2),
            "fcf_per_share": round(fcf_m / shares_proj, 4),
        }
        forward_net_debt[yr_str] = round(net_debt_proj, 2)
        forward_shares[yr_str] = round(shares_proj, 4)

    # ── Precio objetivo por múltiplo por año ──────────────────────────────────
    price_targets: dict = {}

    for yr_str, fcf_data in forward_fcf.items():
        fcf_ps = fcf_data["fcf_per_share"]
        nd = forward_net_debt.get(yr_str, 0)
        sh = forward_shares.get(yr_str, 1)
        nd_ps = nd / sh if sh else 0
        est = forward_est.get(yr_str, {})
        targets: dict = {}

        targets["ev_fcf"] = round(fcf_ps * ev_fcf_target - nd_ps, 2)

        eps = _fv(est.get("eps_norm"))
        if eps and eps > 0:
            targets["per"] = round(eps * per_target, 2)

        ebitda_fwd = _fv(est.get("ebitda"))
        if ebitda_fwd and sh:
            mc_implied = ebitda_fwd * ev_ebitda_target - nd
            targets["ev_ebitda"] = round(mc_implied / sh, 2)

        valid = [v for v in targets.values() if v and v > 0]
        if valid:
            targets["average"] = round(sum(valid) / len(valid), 2)

        price_targets[yr_str] = targets

    # ── Precio de compra para target_return ───────────────────────────────────
    buy_price = exit_price = exit_year = years_to_exit = None

    if price_targets:
        exit_yr_str = sorted(price_targets.keys())[-1]
        exit_year = int(exit_yr_str)
        years_to_exit = max(1, min(exit_year - (current_year - 1), 10))
        exit_price = price_targets[exit_yr_str].get("ev_fcf") or price_targets[exit_yr_str].get("average")

        if exit_price and exit_price > 0 and current_price:
            buy_price = round(exit_price / ((1 + target_return) ** years_to_exit), 2)

    upside_pct = safety_margin_pct = None
    if buy_price and current_price and current_price > 0:
        upside_pct = round((buy_price / current_price - 1) * 100, 1)
        safety_margin_pct = round((1 - current_price / buy_price) * 100, 1)

    return {
        "ticker": ticker.upper(),
        "current_price": current_price,
        "market_cap": market_cap,
        "tev": tev,
        "historical_fcf": historical_fcf,
        "historical_fcf_per_share": historical_fcf_ps,
        "fcf_breakdown": fcf_breakdown,
        "capex_pct_sales_median": round(capex_pct_median * 100, 2),
        "median_ev_fcf": round(median_ev_fcf, 1),
        "ntm_fcf_yield_pct": ntm_fcf_yield,
        "ntm_pe": ntm_pe,
        "ntm_ev_ebitda": ntm_ev_ebitda,
        "ev_fcf_target": ev_fcf_target,
        "per_target": per_target,
        "ev_ebitda_target": ev_ebitda_target,
        "target_return_pct": round(target_return * 100, 1),
        "forward_fcf": forward_fcf,
        "forward_net_debt": forward_net_debt,
        "price_targets": price_targets,
        "buy_price": buy_price,
        "exit_price": exit_price,
        "exit_year": exit_year,
        "years_to_exit": years_to_exit,
        "upside_pct": upside_pct,
        "safety_margin_pct": safety_margin_pct,
        "signal": _signal(upside_pct),
    }


def _signal(upside_pct: Optional[float]) -> str:
    if upside_pct is None:
        return "NO_DATA"
    if upside_pct >= 15:
        return "BUY"
    if upside_pct >= 0:
        return "WATCH"
    if upside_pct >= -20:
        return "HOLD"
    return "OVERVALUED"


def batch_calculate(target_return: float = 0.15) -> dict:
    return {t: calculate(t, target_return=target_return) for t in _load_tikr()}


if __name__ == "__main__":
    import sys
    tickers = sys.argv[1:] if len(sys.argv) > 1 else ["WCN", "MSFT", "V", "VRSK"]
    if not _load_tikr():
        print("ERROR: docs/tikr_earnings_data.json not found or empty")
        sys.exit(1)

    for t in tickers:
        r = calculate(t)
        if "error" in r:
            print(f"{t}: {r['error']}")
            continue
        bp = r.get("buy_price")
        cp = r.get("current_price")
        up = r.get("upside_pct")
        print(f"\n{'='*60}")
        print(f"  {t}  |  Actual: ${cp}  |  Señal: {r['signal']}")
        print(f"  Precio compra {r['target_return_pct']}%: ${bp}  ({up:+.1f}% vs actual)")
        print(f"  Exit {r['exit_year']}E: ${r['exit_price']}  |  EV/FCF target: {r['ev_fcf_target']}x")
        print(f"  Mediana EV/FCF: {r['median_ev_fcf']}x  |  FCF Yield NTM: {r.get('ntm_fcf_yield_pct')}%")
        print(f"  Owner Earnings ($M): { {k: v for k, v in list(r['historical_fcf'].items())[:4]} }")
        fwd = r.get("forward_fcf", {})
        if fwd:
            fwd_str = " | ".join(f"{yr}: ${v['fcf']:.0f}M (${v['fcf_per_share']:.2f}/sh)"
                                  for yr, v in sorted(fwd.items()))
            print(f"  FCF forward: {fwd_str}")
        for yr, pt in sorted(r.get("price_targets", {}).items()):
            print(f"  {yr}E: EV/FCF=${pt.get('ev_fcf')} | P/E=${pt.get('per')} | avg=${pt.get('average')}")
