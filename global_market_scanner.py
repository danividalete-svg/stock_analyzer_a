#!/usr/bin/env python3
"""
GLOBAL MARKET SCANNER — VALUE opportunities in undervalued markets
Scans stocks in Brazil, South Korea, Japan, Hong Kong using the same
VALUE scoring logic as the US/EU system.

Markets selected because their CAPE ratios are below historical averages
(as of early 2026), providing a double discount: cheap market + cheap stock.

Output: docs/global_value_opportunities.csv
"""
import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path
from datetime import datetime
import time
import json
import os

DOCS = Path("docs")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OUTPUT_FILE = DOCS / "global_value_opportunities.csv"
RATE_DELAY = 0.8  # seconds between yfinance calls

# US-listed equivalents (NYSE/NASDAQ or OTC) for native tickers
ADR_MAP = {
    # Hong Kong
    "9999.HK": "NTES",    # NetEase → NASDAQ
    "9988.HK": "BABA",    # Alibaba → NYSE
    "9618.HK": "JD",      # JD.com → NASDAQ
    "0700.HK": "TCEHY",   # Tencent → OTC
    "1211.HK": "BYDDF",   # BYD → OTC
    "0005.HK": "HSBC",    # HSBC → NYSE
    "2318.HK": "PNGAY",   # Ping An → OTC
    # Japan
    "7203.T":  "TM",      # Toyota → NYSE
    "6758.T":  "SONY",    # Sony → NYSE
    "8306.T":  "MUFG",    # MUFG → NYSE
    "8316.T":  "SMFG",    # SMFG → NYSE
    "9984.T":  "SFTBY",   # SoftBank → OTC
    "7974.T":  "NTDOY",   # Nintendo → OTC
    "4568.T":  "DSNKY",   # Daiichi Sankyo → OTC
    "6098.T":  "RCRUY",   # Recruit → OTC
    "8766.T":  "TKOMY",   # Tokio Marine → OTC
    # Brazil
    "VALE3.SA": "VALE",   # Vale → NYSE
    "ITUB4.SA": "ITUB",   # Itaú → NYSE
    "BBDC4.SA": "BBD",    # Bradesco → NYSE
    "PETR4.SA": "PBR",    # Petrobras → NYSE
    "WEGE3.SA": "WEGZY",  # WEG → OTC
    "ABEV3.SA": "ABEV",   # Ambev → NYSE
    "RDOR3.SA": "RDORY",  # Rede D'Or → OTC
    # Korea (mostly OTC Pink Sheets)
    "005930.KS": "SSNLF", # Samsung → OTC
    "005380.KS": "HYMTF", # Hyundai Motor → OTC
    "000660.KS": "HXSCL", # SK Hynix → OTC
}

# CAPE context per market (Dec 2025 data from Siblis Research)
MARKET_CAPE = {
    "Brazil":    {"cape": 9.0,  "hist_avg": 13.6, "flag": "🇧🇷", "currency": "BRL", "currency_symbol": "R$"},
    "Korea":     {"cape": 21.2, "hist_avg": 15.4, "flag": "🇰🇷", "currency": "KRW", "currency_symbol": "₩"},
    "Japan":     {"cape": 29.4, "hist_avg": 40.0, "flag": "🇯🇵", "currency": "JPY", "currency_symbol": "¥"},
    "HongKong":  {"cape": 10.7, "hist_avg": 16.0, "flag": "🇭🇰", "currency": "HKD", "currency_symbol": "HK$"},
}

# --- Ticker universes ---
# Top companies by market cap + quality names, accessible via DEGIRO
UNIVERSES = {
    "Brazil": [
        "PETR4.SA",  # Petrobras — energy
        "VALE3.SA",  # Vale — mining
        "ITUB4.SA",  # Itaú Unibanco — financials
        "BBDC4.SA",  # Bradesco — financials
        "WEGE3.SA",  # WEG — industrial motors ⭐ high quality
        "ABEV3.SA",  # Ambev — beverages
        "RENT3.SA",  # Localiza — car rental
        "RDOR3.SA",  # Rede D'Or — healthcare
        "EMBR3.SA",  # Embraer — aerospace ⭐
        "TOTS3.SA",  # Totvs — business software
        "B3SA3.SA",  # B3 — stock exchange
        "EGIE3.SA",  # Engie Brasil — utilities
        "SUZB3.SA",  # Suzano — pulp & paper
        "LREN3.SA",  # Lojas Renner — retail
        "CPLE6.SA",  # Copel — utilities
        "CMIG4.SA",  # Cemig — utilities
        "ELET3.SA",  # Eletrobras — utilities
        "CSAN3.SA",  # Cosan — energy/agro
        "BBAS3.SA",  # Banco do Brasil — financials
        "SULA11.SA", # Sul América — insurance
    ],
    "Korea": [
        "005930.KS",  # Samsung Electronics — semiconductors
        "000660.KS",  # SK Hynix — semiconductors
        "005380.KS",  # Hyundai Motor — automotive
        "000270.KS",  # Kia Motors — automotive
        "035420.KS",  # NAVER — tech/search
        "051910.KS",  # LG Chem — chemicals/batteries
        "006400.KS",  # Samsung SDI — batteries EV
        "028260.KS",  # Samsung C&T — construction/trading
        "012330.KS",  # Hyundai Mobis — auto parts ⭐
        "096770.KS",  # SK Innovation — energy/batteries
        "017670.KS",  # SK Telecom — telecom
        "030200.KS",  # KT Corp — telecom
        "055550.KS",  # Shinhan Financial — banking
        "105560.KS",  # KB Financial — banking
        "086790.KS",  # Hana Financial — banking
        "066570.KS",  # LG Electronics — consumer electronics
        "316140.KS",  # Woori Financial — banking
        "009150.KS",  # Samsung Electro-Mechanics — components ⭐
        "010950.KS",  # S-Oil — refining
        "032830.KS",  # Samsung Life Insurance — insurance
    ],
    "Japan": [
        "7203.T",   # Toyota Motor — automotive
        "6758.T",   # Sony Group — electronics/entertainment
        "9984.T",   # SoftBank Group — tech/investment
        "6861.T",   # Keyence — automation/sensors ⭐
        "7974.T",   # Nintendo — gaming
        "8306.T",   # MUFG — banking (largest in Japan)
        "8035.T",   # Tokyo Electron — semiconductor equipment ⭐
        "9432.T",   # NTT — telecom
        "4502.T",   # Takeda Pharmaceutical — pharma
        "9983.T",   # Fast Retailing (Uniqlo) — retail
        "6367.T",   # Daikin — HVAC systems
        "8316.T",   # Sumitomo Mitsui Financial — banking
        "6098.T",   # Recruit Holdings — HR/tech
        "4063.T",   # Shin-Etsu Chemical — specialty chemicals ⭐
        "8766.T",   # Tokio Marine — insurance
        "9433.T",   # KDDI — telecom
        "4568.T",   # Daiichi Sankyo — pharma/oncology
        "6501.T",   # Hitachi — diversified industrial
        "6902.T",   # Denso — auto components ⭐
        "7267.T",   # Honda Motor — automotive
        "2914.T",   # Japan Tobacco — tobacco (high dividend)
        "8031.T",   # Mitsui & Co — trading house
        "4661.T",   # Oriental Land (Tokyo Disney) — theme parks
        "7733.T",   # Olympus — medical devices
        "6503.T",   # Mitsubishi Electric — industrial
    ],
    "HongKong": [
        "0700.HK",  # Tencent — social/gaming/fintech ⭐
        "9988.HK",  # Alibaba (HK) — e-commerce/cloud
        "1211.HK",  # BYD — EVs/batteries ⭐
        "0941.HK",  # China Mobile — telecom
        "0939.HK",  # CCB (China Construction Bank) — banking
        "1398.HK",  # ICBC — banking (world's largest by assets)
        "2318.HK",  # Ping An Insurance — insurance ⭐
        "0883.HK",  # CNOOC — offshore oil & gas
        "0857.HK",  # PetroChina — energy
        "3988.HK",  # Bank of China — banking
        "1810.HK",  # Xiaomi — smartphones/IoT
        "9999.HK",  # NetEase — gaming/education
        "2382.HK",  # Sunny Optical — optical lenses ⭐
        "0388.HK",  # HKEX — stock exchange
        "0005.HK",  # HSBC — international banking
        "1299.HK",  # AIA Group — life insurance ⭐
        "2020.HK",  # ANTA Sports — sportswear
        "6690.HK",  # Haier Smart Home — appliances
        "9618.HK",  # JD.com (HK) — e-commerce/logistics
        "0002.HK",  # CLP Holdings — utilities (HK)
        "3690.HK",  # Meituan — food delivery/local services
        "0001.HK",  # CK Hutchison — diversified conglomerate
    ],
}


def _market_cape_bonus(market: str) -> float:
    """Bonus points for being in an undervalued market (CAPE below historical avg)."""
    info = MARKET_CAPE.get(market, {})
    cape = info.get("cape", 20)
    hist = info.get("hist_avg", 20)
    discount = (hist - cape) / hist if hist > 0 else 0
    if discount >= 0.30:   return 10.0   # ≥30% below historical → max bonus
    if discount >= 0.15:   return 7.0
    if discount >= 0.0:    return 4.0
    return 0.0  # market is expensive (e.g. Korea slightly above hist)


def _score_ticker(ticker: str, market: str):
    """Fetch yfinance data and compute VALUE score for a single ticker."""
    try:
        t = yf.Ticker(ticker)
        info = t.info
    except Exception as e:
        print(f"  ⚠️  {ticker}: yfinance error — {e}")
        return None

    # Basic sanity check
    price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
    if not price or price <= 0:
        return None

    high_52w = info.get("fiftyTwoWeekHigh")
    pct_from_52w_high = round((price - high_52w) / high_52w * 100, 1) if high_52w and high_52w > 0 else None

    name = info.get("longName") or info.get("shortName") or ticker
    sector = info.get("sector") or "Unknown"
    currency = info.get("currency") or MARKET_CAPE.get(market, {}).get("currency", "USD")
    market_cap = info.get("marketCap") or 0

    # Skip micro-caps (< $100M equivalent — rough filter)
    if market_cap and market_cap < 1e10 and currency in ("KRW", "JPY"):
        pass  # These currencies have large nominal values, skip the filter
    elif market_cap and market_cap < 1e8:
        return None

    # ── Fundamental data ────────────────────────────────────────────────
    roe = info.get("returnOnEquity")          # decimal e.g. 0.32
    pe_trailing = info.get("trailingPE")
    pe_forward = info.get("forwardPE")
    profit_margin = info.get("profitMargins")  # decimal
    revenue_growth = info.get("revenueGrowth")  # decimal YoY
    debt_to_equity = info.get("debtToEquity")   # already x100 in yfinance
    dividend_yield = info.get("dividendYield")  # decimal
    payout_ratio = info.get("payoutRatio")
    free_cashflow = info.get("freeCashflow")
    target_price = info.get("targetMeanPrice")
    analyst_count = info.get("numberOfAnalystOpinions") or 0
    shares_outstanding = info.get("sharesOutstanding") or 1

    # Analyst upside
    analyst_upside = None
    if target_price and price and price > 0:
        analyst_upside = (target_price - price) / price * 100

    # Skip if clearly overvalued by analyst consensus
    if analyst_upside is not None and analyst_upside < -5:
        pass  # still score, just low points

    # FCF yield — not meaningful for banks/insurance (capital flows = core business)
    fcf_yield = None
    if sector != "Financial Services":
        if free_cashflow and market_cap and market_cap > 0:
            fcf_yield = (free_cashflow / market_cap) * 100

    # Dividend yield as percentage — with sanity check
    div_yield_pct = None
    if dividend_yield:
        raw = dividend_yield * 100 if dividend_yield < 1 else dividend_yield
        if raw > 15:
            # yfinance bug: sometimes returns per-share amount not yield
            # Try recalculating from trailingAnnualDividendRate / price
            trailing_div = info.get("trailingAnnualDividendRate")
            if trailing_div and price and price > 0:
                recalc = (trailing_div / price) * 100
                div_yield_pct = round(recalc, 2) if 0 < recalc <= 15 else None
            # If still bad, discard — better no data than wrong data
        else:
            div_yield_pct = round(raw, 2)

    # Risk/reward ratio
    rr_ratio = None
    if analyst_upside is not None:
        rr_ratio = round(analyst_upside / 8, 2)  # 8% standard stop loss

    # ── Automatic risk flags ──────────────────────────────────────────────
    risk_flags = []
    if sector == "Financial Services":
        risk_flags.append("FCF no comparable (sector financiero)")
        state_bank_keywords = ["Construction Bank", "ICBC", "Bank of China",
                               "Agricultural Bank", "PetroChina", "CNOOC"]
        if any(k in name for k in state_bank_keywords):
            risk_flags.append("Empresa estatal — riesgo de gobierno corporativo")
        if "Insurance" in name or "Ping An" in name or "AIA" in name:
            risk_flags.append("Aseguradora — posible exposición inmobiliaria")
    if market == "HongKong" and sector == "Financial Services":
        risk_flags.append("Banco/aseguradora HK — exposición sector inmuebles chino")
    if revenue_growth is not None and revenue_growth < -0.05:
        risk_flags.append("Ingresos en declive YoY")
    if analyst_count < 5:
        risk_flags.append("Cobertura analistas baja (<5)")
    if debt_to_equity is not None and debt_to_equity / 100 > 2.0:
        risk_flags.append("Deuda elevada (D/E >2x)")

    # ── VALUE SCORE (0–100) ──────────────────────────────────────────────
    score = 0.0
    reasons = []

    # 1. ROE (15 pts) — core quality metric
    if roe is not None:
        roe_pct = roe * 100
        if roe_pct < 0:
            return None  # Hard reject: negative ROE
        if roe_pct >= 20:
            score += 15; reasons.append(f"ROE {roe_pct:.1f}%")
        elif roe_pct >= 15:
            score += 10; reasons.append(f"ROE {roe_pct:.1f}%")
        elif roe_pct >= 8:
            score += 5

    # 2. Forward P/E (15 pts) — relative to market benchmarks
    pe = pe_forward or pe_trailing
    if pe is not None and pe > 0:
        # Use market-specific P/E benchmarks
        benchmarks = {
            "Brazil": 10.0, "Korea": 11.0, "Japan": 16.0, "HongKong": 11.0
        }
        bench = benchmarks.get(market, 13.0)
        if pe < bench * 0.7:
            score += 15; reasons.append(f"P/E {pe:.1f}x (vs {bench:.0f}x mercado)")
        elif pe < bench:
            score += 10; reasons.append(f"P/E {pe:.1f}x")
        elif pe < bench * 1.3:
            score += 5

    # 3. Analyst upside (25 pts) — conviction from sell-side
    if analyst_upside is not None:
        if analyst_count == 0:
            score *= 0.85  # No coverage penalty
        elif analyst_upside >= 30:
            score += 25; reasons.append(f"Potencial +{analyst_upside:.0f}% analistas")
        elif analyst_upside >= 20:
            score += 18; reasons.append(f"Potencial +{analyst_upside:.0f}%")
        elif analyst_upside >= 10:
            score += 10; reasons.append(f"Potencial +{analyst_upside:.0f}%")
        elif analyst_upside >= 0:
            score += 4
        else:
            score += 0  # negative upside = 0 pts (not a hard reject for global)

    # 4. FCF Yield (10 pts)
    if fcf_yield is not None:
        if fcf_yield >= 8:
            score += 10; reasons.append(f"FCF yield {fcf_yield:.1f}%")
        elif fcf_yield >= 5:
            score += 7; reasons.append(f"FCF yield {fcf_yield:.1f}%")
        elif fcf_yield >= 2:
            score += 3
        elif fcf_yield < 0:
            score -= 5; reasons.append("FCF negativo")

    # 5. Revenue growth (10 pts)
    if revenue_growth is not None:
        rg_pct = revenue_growth * 100
        if rg_pct >= 15:
            score += 10; reasons.append(f"Crecimiento ingresos +{rg_pct:.0f}%")
        elif rg_pct >= 5:
            score += 6
        elif rg_pct >= 0:
            score += 2
        else:
            score -= 3  # declining revenue

    # 6. Profit margin (10 pts)
    if profit_margin is not None:
        pm_pct = profit_margin * 100
        if pm_pct >= 20:
            score += 10; reasons.append(f"Margen {pm_pct:.0f}%")
        elif pm_pct >= 10:
            score += 6
        elif pm_pct >= 0:
            score += 2
        else:
            score -= 5

    # 7. Debt/Equity (5 pts) — note: yfinance gives D/E as e.g. 40.5 = 0.405x
    if debt_to_equity is not None:
        de = debt_to_equity / 100  # convert to standard ratio
        if de <= 0.3:
            score += 5
        elif de <= 0.7:
            score += 3
        elif de <= 1.5:
            score += 1
        else:
            score -= 3  # highly levered

    # 8. Dividend quality (5 pts)
    if div_yield_pct and 1 <= div_yield_pct <= 6:
        if payout_ratio and payout_ratio < 0.75:
            score += 5; reasons.append(f"Dividendo {div_yield_pct:.1f}%")
        else:
            score += 2

    # 9. Market CAPE bonus (10 pts) — double discount
    cape_bonus = _market_cape_bonus(market)
    if cape_bonus > 0:
        score += cape_bonus
        cape_info = MARKET_CAPE[market]
        discount_pct = (cape_info["hist_avg"] - cape_info["cape"]) / cape_info["hist_avg"] * 100
        if discount_pct > 5:
            reasons.append(f"Mercado {market} CAPE {cape_info['cape']:.0f} ({discount_pct:.0f}% descuento histórico)")

    # ── Conviction grade ─────────────────────────────────────────────────
    score = round(max(0, min(100, score)), 2)
    if score >= 65:
        grade = "A"
    elif score >= 50:
        grade = "B"
    elif score >= 35:
        grade = "C"
    else:
        return None  # Too low quality

    # Minimum analyst upside filter (avoid clearly overvalued)
    if analyst_upside is not None and analyst_upside < -15:
        return None

    return {
        "ticker": ticker,
        "company_name": name,
        "current_price": round(price, 2),
        "currency": currency,
        "value_score": score,
        "conviction_grade": grade,
        "conviction_score": score,
        "conviction_reasons": " | ".join(reasons) if reasons else "",
        "conviction_positives": len([r for r in reasons if "FCF" in r or "ROE" in r or "Margen" in r or "CAPE" in r]),
        "conviction_red_flags": len([r for r in reasons if "negativo" in r.lower()]),
        "sector": sector,
        "market": market,
        "market_flag": MARKET_CAPE.get(market, {}).get("flag", "🌐"),
        "market_cape": MARKET_CAPE.get(market, {}).get("cape"),
        "target_price_analyst": round(target_price, 2) if target_price else None,
        "analyst_upside_pct": round(analyst_upside, 1) if analyst_upside is not None else None,
        "analyst_count": analyst_count,
        "fcf_yield_pct": round(fcf_yield, 1) if fcf_yield is not None else None,
        "risk_reward_ratio": rr_ratio,
        "dividend_yield_pct": round(div_yield_pct, 2) if div_yield_pct else None,
        "buyback_active": None,  # Not easily available for all markets
        "roe_pct": round(roe * 100, 1) if roe is not None else None,
        "pe_forward": round(pe_forward, 1) if pe_forward else None,
        "pe_trailing": round(pe_trailing, 1) if pe_trailing else None,
        "profit_margin_pct": round(profit_margin * 100, 1) if profit_margin else None,
        "revenue_growth_pct": round(revenue_growth * 100, 1) if revenue_growth else None,
        "pct_from_52w_high": pct_from_52w_high,
        "risk_flags": " | ".join(risk_flags) if risk_flags else "",
        "nasdaq_adr": ADR_MAP.get(ticker, ""),
        "ai_verdict": "",   # filled by _ai_verify_stock()
        "ai_notes": "",     # filled by _ai_verify_stock()
        "scan_date": datetime.now().strftime("%Y-%m-%d"),
    }


def _ai_verify_stock(result: dict, groq_client) -> dict:
    """
    Use Groq AI to verify data quality and flag investment risks.
    Adds ai_verdict (CLEAN / SUSPECT / RISKY) and ai_notes to the result dict.
    """
    try:
        prompt = f"""You are a financial data analyst. Verify this stock's metrics for data quality and flag investment risks.

Ticker: {result['ticker']} — {result['company_name']}
Sector: {result['sector']} | Market: {result['market']} (CAPE {result.get('market_cape','?')})

Reported metrics:
- ROE: {result.get('roe_pct')}%
- Forward P/E: {result.get('pe_forward')}x | Trailing P/E: {result.get('pe_trailing')}x
- Profit Margin: {result.get('profit_margin_pct')}%
- Revenue Growth YoY: {result.get('revenue_growth_pct')}%
- FCF Yield: {result.get('fcf_yield_pct')}%
- Dividend Yield: {result.get('dividend_yield_pct')}%
- Analyst Upside: {result.get('analyst_upside_pct')}% ({result.get('analyst_count')} analysts)
- Already flagged: {result.get('risk_flags', 'none')}

Check:
1. Are any metrics anomalous or likely wrong for this company type? (e.g. FCF yield >50% for insurer, dividend >15%, P/E <0)
2. Are there known structural risks: regulatory, geopolitical, real estate, cyclical, governance?
3. Is the analyst upside credible given the fundamentals?

Respond ONLY with valid JSON, no extra text:
{{"ai_verdict": "CLEAN|SUSPECT|RISKY", "ai_notes": "one sentence max", "extra_flags": ["optional extra risk flags"]}}"""

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content.strip()
        # Extract JSON even if wrapped in ```
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()
        data = json.loads(raw)

        result["ai_verdict"] = data.get("ai_verdict", "CLEAN")
        result["ai_notes"] = data.get("ai_notes", "")
        # Merge extra flags into existing risk_flags
        extra = data.get("extra_flags", [])
        if extra:
            existing = result.get("risk_flags", "")
            merged = " | ".join(filter(None, [existing] + extra))
            result["risk_flags"] = merged

    except Exception as e:
        print(f"    ⚠️  AI verify failed for {result['ticker']}: {e}")
        result["ai_verdict"] = ""
        result["ai_notes"] = ""

    return result


def run_scanner(markets: list = None):
    """Run the global market scanner for the specified markets."""
    if markets is None:
        markets = list(UNIVERSES.keys())

    DOCS.mkdir(exist_ok=True)
    all_results = []

    total_tickers = sum(len(UNIVERSES[m]) for m in markets)
    processed = 0

    print("\n🌍 GLOBAL MARKET SCANNER")
    print("=" * 70)
    print(f"Markets: {', '.join(markets)}")
    print(f"Total tickers: {total_tickers}")

    for market in markets:
        tickers = UNIVERSES[market]
        cape_info = MARKET_CAPE[market]
        discount = (cape_info["hist_avg"] - cape_info["cape"]) / cape_info["hist_avg"] * 100
        print(f"\n{cape_info['flag']} {market} — CAPE {cape_info['cape']:.1f} "
              f"(hist avg {cape_info['hist_avg']:.1f}, {discount:.0f}% descuento)")
        print(f"  Scanning {len(tickers)} tickers...")

        market_results = []
        for ticker in tickers:
            processed += 1
            result = _score_ticker(ticker, market)
            if result:
                market_results.append(result)
                print(f"  ✅ {ticker:<15} {result['company_name'][:30]:<32} "
                      f"score={result['value_score']:.0f} grade={result['conviction_grade']}")
            else:
                print(f"  ⚪ {ticker:<15} (filtered out)")
            time.sleep(RATE_DELAY)

        market_results.sort(key=lambda x: x["value_score"], reverse=True)
        all_results.extend(market_results)
        print(f"  → {len(market_results)}/{len(tickers)} qualified")

    if not all_results:
        print("\n❌ No opportunities found")
        return

    # ── AI verification pass ──────────────────────────────────────────────
    if GROQ_API_KEY:
        print(f"\n🤖 Running AI verification on {len(all_results)} stocks...")
        try:
            from groq import Groq
            groq_client = Groq(api_key=GROQ_API_KEY)
            for i, result in enumerate(all_results):
                all_results[i] = _ai_verify_stock(result, groq_client)
                verdict = all_results[i].get("ai_verdict", "")
                icon = "✅" if verdict == "CLEAN" else "⚠️" if verdict == "SUSPECT" else "🚫" if verdict == "RISKY" else "⬜"
                print(f"  {icon} {result['ticker']:<15} {verdict or 'no response':<8}  {all_results[i].get('ai_notes','')[:60]}")
                time.sleep(0.5)  # Groq free tier: ~30 req/min
        except Exception as e:
            print(f"  Groq not available: {e}")
    else:
        print("\n⚠️  GROQ_API_KEY not set — skipping AI verification")

    df = pd.DataFrame(all_results)
    df = df.sort_values("value_score", ascending=False)
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"\n{'='*70}")
    print(f"✅ {len(df)} global VALUE opportunities → {OUTPUT_FILE}")
    print(f"\n🏆 TOP 10:")
    for _, row in df.head(10).iterrows():
        flag = MARKET_CAPE.get(row["market"], {}).get("flag", "🌐")
        print(f"  {flag} {row['ticker']:<15} {row['company_name'][:28]:<30} "
              f"score={row['value_score']:.0f} [{row['conviction_grade']}] "
              f"upside={row.get('analyst_upside_pct','N/A')}%")

    # Summary by market
    print("\n📊 Por mercado:")
    for market in markets:
        sub = df[df["market"] == market]
        if len(sub) > 0:
            flag = MARKET_CAPE[market]["flag"]
            print(f"  {flag} {market}: {len(sub)} stocks | avg score: {sub['value_score'].mean():.1f} | "
                  f"top: {sub.iloc[0]['ticker']} ({sub.iloc[0]['value_score']:.0f})")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Global Market VALUE Scanner")
    parser.add_argument("--markets", nargs="+",
                        choices=list(UNIVERSES.keys()),
                        default=None,
                        help="Markets to scan (default: all)")
    args = parser.parse_args()
    run_scanner(markets=args.markets)
