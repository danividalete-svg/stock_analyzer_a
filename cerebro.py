#!/usr/bin/env python3
"""
CEREBRO — Proactive AI Agent
Runs daily at end of pipeline. Does 4 things:

1. PATTERN MINING  : reads portfolio_tracker history → learns what predicts wins
2. CONVERGENCE SCAN: finds tickers in 2+ strategies today → ranks & narrates top picks
3. ALERT GENERATOR : detects events for all tickers (new MR zone, score drop, earnings)
4. SELF-CALIBRATION: identifies which score ranges / sectors / regimes actually work

Outputs (all to docs/):
  cerebro_insights.json    — what the system learned from history
  cerebro_convergence.json — today's top multi-strategy convergence picks
  cerebro_alerts.json      — ticker events (frontend filters by user's watchlist)
"""

import os
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, date

try:
    from groq import Groq
    GROQ_KEY = os.getenv("GROQ_API_KEY")
    groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
except Exception:
    groq_client = None

DOCS = Path("docs")
TODAY = date.today().isoformat()


# ── helpers ──────────────────────────────────────────────────────────────────

def load_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def safe_float(v) -> float | None:
    try:
        f = float(v)
        return None if np.isnan(f) else f
    except Exception:
        return None


def ai_narrative(prompt: str, max_tokens: int = 300) -> str | None:
    if not groq_client:
        return None
    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.4,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"  [AI] error: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 1. PATTERN MINING — what predicts wins?
# ══════════════════════════════════════════════════════════════════════════════

def mine_patterns() -> dict:
    print("\n[CEREBRO] Mining patterns from portfolio tracker history...")
    df = load_csv(DOCS / "portfolio_tracker" / "recommendations.csv")
    if df.empty:
        print("  No data found.")
        return {}

    # Only use VALUE signals with completed 7d return
    completed = df[df["return_7d"].notna()].copy()
    if len(completed) < 10:
        print(f"  Only {len(completed)} completed signals — need more data.")
        return {"total_analyzed": len(completed)}

    print(f"  Analyzing {len(completed)} completed signals...")
    baseline_wr = float(completed["win_7d"].mean()) * 100 if "win_7d" in completed.columns else 50.0
    baseline_ret = float(completed["return_7d"].mean())

    def tier_stats(sub: pd.DataFrame, label: str) -> dict:
        if len(sub) < 3:
            return {}
        wr = float(sub["win_7d"].mean()) * 100 if "win_7d" in sub.columns else 0.0
        ret = float(sub["return_7d"].mean())
        ret14 = float(sub["return_14d"].mean()) if "return_14d" in sub.columns and sub["return_14d"].notna().any() else None
        return {
            "label": label,
            "win_rate_7d": round(wr, 1),
            "avg_return_7d": round(ret, 2),
            "avg_return_14d": round(ret14, 2) if ret14 is not None else None,
            "n": len(sub),
            "vs_baseline_wr": round(wr - baseline_wr, 1),
            "vs_baseline_ret": round(ret - baseline_ret, 2),
        }

    # ── Score tiers ──────────────────────────────────────────────────────────
    score_tiers = []
    if "value_score" in completed.columns:
        for lo, hi in [(90, 101), (80, 90), (70, 80), (60, 70), (50, 60)]:
            sub = completed[(completed["value_score"] >= lo) & (completed["value_score"] < hi)]
            s = tier_stats(sub, f"{lo}–{hi}")
            if s:
                score_tiers.append(s)

    # ── Market regime ────────────────────────────────────────────────────────
    regimes = []
    if "market_regime" in completed.columns:
        for regime in completed["market_regime"].dropna().unique():
            sub = completed[completed["market_regime"] == regime]
            s = tier_stats(sub, regime)
            if s:
                regimes.append(s)
        regimes.sort(key=lambda x: x["win_rate_7d"], reverse=True)

    # ── Sector ───────────────────────────────────────────────────────────────
    sectors = []
    if "sector" in completed.columns:
        for sector in completed["sector"].dropna().unique():
            sub = completed[completed["sector"] == sector]
            s = tier_stats(sub, sector)
            if s:
                sectors.append(s)
        sectors.sort(key=lambda x: x["win_rate_7d"], reverse=True)

    # ── FCF yield effect ─────────────────────────────────────────────────────
    fcf_tiers = []
    if "fcf_yield_pct" in completed.columns:
        high_fcf  = completed[completed["fcf_yield_pct"] >= 5]
        med_fcf   = completed[(completed["fcf_yield_pct"] >= 2) & (completed["fcf_yield_pct"] < 5)]
        low_fcf   = completed[completed["fcf_yield_pct"] < 2]
        neg_fcf   = completed[completed["fcf_yield_pct"] < 0]
        for sub, label in [(high_fcf, "FCF≥5%"), (med_fcf, "FCF 2-5%"), (low_fcf, "FCF<2%"), (neg_fcf, "FCF<0%")]:
            s = tier_stats(sub, label)
            if s:
                fcf_tiers.append(s)

    # ── Risk/Reward effect ───────────────────────────────────────────────────
    rr_tiers = []
    if "risk_reward_ratio" in completed.columns:
        high_rr = completed[completed["risk_reward_ratio"] >= 3]
        med_rr  = completed[(completed["risk_reward_ratio"] >= 2) & (completed["risk_reward_ratio"] < 3)]
        low_rr  = completed[completed["risk_reward_ratio"] < 2]
        for sub, label in [(high_rr, "R:R≥3"), (med_rr, "R:R 2-3"), (low_rr, "R:R<2")]:
            s = tier_stats(sub, label)
            if s:
                rr_tiers.append(s)

    # ── Holding period: 7d vs 14d vs 30d ────────────────────────────────────
    period_stats = {}
    for period in ["7d", "14d", "30d"]:
        col_ret  = f"return_{period}"
        col_win  = f"win_{period}"
        sub = completed[completed[col_ret].notna()] if col_ret in completed.columns else pd.DataFrame()
        if not sub.empty:
            period_stats[period] = {
                "win_rate": round(float(sub[col_win].mean()) * 100, 1) if col_win in sub.columns else None,
                "avg_return": round(float(sub[col_ret].mean()), 2),
                "n": len(sub),
            }

    # ── Best combo: score≥80 + no earnings warning ───────────────────────────
    combos = []
    if "value_score" in completed.columns and "market_regime" in completed.columns:
        high_score_bull = completed[
            (completed["value_score"] >= 80) &
            (completed["market_regime"].str.upper().str.contains("BULL|ALCISTA", na=False))
        ]
        s = tier_stats(high_score_bull, "Score≥80 en mercado alcista")
        if s:
            combos.append(s)

        if "fcf_yield_pct" in completed.columns:
            quality_combo = completed[
                (completed["value_score"] >= 70) &
                (completed["fcf_yield_pct"] >= 5)
            ]
            s = tier_stats(quality_combo, "Score≥70 + FCF≥5%")
            if s:
                combos.append(s)

    # ── Best overall pick ─────────────────────────────────────────────────────
    best_ticker_stats = []
    if "ticker" in completed.columns:
        for ticker in completed["ticker"].unique():
            sub = completed[completed["ticker"] == ticker]
            if len(sub) >= 3:
                s = tier_stats(sub, ticker)
                if s:
                    best_ticker_stats.append(s)
        best_ticker_stats.sort(key=lambda x: x["win_rate_7d"], reverse=True)

    insights = {
        "generated_at": TODAY,
        "total_analyzed": len(completed),
        "baseline_win_rate_7d": round(baseline_wr, 1),
        "baseline_avg_return_7d": round(baseline_ret, 2),
        "score_tiers": score_tiers,
        "market_regimes": regimes,
        "sectors": sectors[:10],
        "fcf_tiers": fcf_tiers,
        "rr_tiers": rr_tiers,
        "period_stats": period_stats,
        "best_combos": combos,
        "top_tickers_by_winrate": best_ticker_stats[:5],
        "narrative": None,
    }

    # ── AI narrative about what the system learned ────────────────────────────
    best_tier  = max(score_tiers, key=lambda x: x["win_rate_7d"], default={})
    best_regime = regimes[0] if regimes else {}
    best_sector = sectors[0] if sectors else {}

    prompt = f"""Eres el cerebro analítico de un sistema de inversión VALUE.
Analiza estos resultados históricos del sistema y genera un párrafo conciso (3-4 frases)
con las conclusiones más importantes para mejorar las señales:

- Señales analizadas: {len(completed)}, win rate base: {baseline_wr:.1f}%
- Mejor rango de score: {best_tier.get('label','N/A')} → win rate {best_tier.get('win_rate_7d','N/A')}%
  (retorno medio {best_tier.get('avg_return_7d','N/A')}%, n={best_tier.get('n',0)})
- Mejor régimen: {best_regime.get('label','N/A')} → win rate {best_regime.get('win_rate_7d','N/A')}%
- Mejor sector: {best_sector.get('label','N/A')} → win rate {best_sector.get('win_rate_7d','N/A')}%
- FCF≥5%: {next((x['win_rate_7d'] for x in fcf_tiers if x['label']=='FCF≥5%'), 'N/A')}% win rate
- Combos: {[c['label']+' → '+str(c['win_rate_7d'])+'%' for c in combos]}

Sé específico y accionable. Menciona qué factores favorecen las victorias y qué evitar.
Responde en español, máximo 4 frases."""

    insights["narrative"] = ai_narrative(prompt) or \
        f"El sistema analizó {len(completed)} señales. Win rate base: {baseline_wr:.1f}%. " \
        f"Mejor rango de score: {best_tier.get('label','N/A')} con {best_tier.get('win_rate_7d','N/A')}% de acierto."

    print(f"  ✓ Pattern mining done: {len(completed)} signals, baseline WR {baseline_wr:.1f}%")
    return insights


# ══════════════════════════════════════════════════════════════════════════════
# 2. CONVERGENCE SCAN — tickers in 2+ strategies today
# ══════════════════════════════════════════════════════════════════════════════

def scan_convergence() -> dict:
    print("\n[CEREBRO] Scanning multi-strategy convergence...")

    # Load all strategy CSVs
    value_us  = load_csv(DOCS / "value_opportunities.csv")
    value_eu  = load_csv(DOCS / "european_value_opportunities.csv")
    insiders  = load_csv(DOCS / "recurring_insiders.csv")
    mr        = load_csv(DOCS / "mean_reversion_opportunities.csv")
    options   = load_csv(DOCS / "options_flow.csv")
    momentum  = load_csv(DOCS / "momentum_opportunities.csv")

    def tickers(df: pd.DataFrame) -> set:
        if df.empty or "ticker" not in df.columns:
            return set()
        return set(df["ticker"].dropna().str.upper())

    sets = {
        "VALUE":    tickers(value_us) | tickers(value_eu),
        "INSIDERS": tickers(insiders),
        "MR":       tickers(mr),
        "OPTIONS":  tickers(options),
        "MOMENTUM": tickers(momentum),
    }

    # Map ticker → metadata from VALUE (primary source)
    meta: dict[str, dict] = {}
    for df in [value_us, value_eu]:
        if df.empty:
            continue
        for _, row in df.iterrows():
            ticker = str(row.get("ticker", "")).upper()
            if ticker and ticker not in meta:
                meta[ticker] = {
                    "ticker": ticker,
                    "company_name": str(row.get("company_name", "")),
                    "sector": str(row.get("sector", "")),
                    "value_score": safe_float(row.get("value_score")),
                    "conviction_grade": str(row.get("conviction_grade", "")),
                    "analyst_upside_pct": safe_float(row.get("analyst_upside_pct")),
                    "fcf_yield_pct": safe_float(row.get("fcf_yield_pct")),
                    "current_price": safe_float(row.get("current_price")),
                }

    # Find convergences
    all_tickers = set().union(*sets.values())
    convergences = []

    for ticker in all_tickers:
        strategies = [name for name, s in sets.items() if ticker in s]
        if len(strategies) < 2:
            continue

        m = meta.get(ticker, {"ticker": ticker})

        # Convergence score: 0-100
        # Each strategy contributes; more strategies = higher score
        score = len(strategies) * 20
        if "VALUE" in strategies and m.get("value_score"):
            score += min(20, m["value_score"] / 5)
        if "INSIDERS" in strategies:
            score += 10
        if "MR" in strategies:
            score += 5  # contrarian signal — adds but risky alone
        score = min(100, int(score))

        convergences.append({
            "ticker": ticker,
            "company_name": m.get("company_name", ""),
            "sector": m.get("sector", ""),
            "strategies": strategies,
            "strategy_count": len(strategies),
            "convergence_score": score,
            "value_score": m.get("value_score"),
            "conviction_grade": m.get("conviction_grade", ""),
            "analyst_upside_pct": m.get("analyst_upside_pct"),
            "fcf_yield_pct": m.get("fcf_yield_pct"),
            "current_price": m.get("current_price"),
            "analysis": None,
        })

    # Sort by convergence score
    convergences.sort(key=lambda x: (x["strategy_count"], x["convergence_score"]), reverse=True)

    # AI analysis for top 3
    for c in convergences[:3]:
        strats = ", ".join(c["strategies"])
        prompt = f"""Ticker: {c['ticker']} ({c.get('company_name','')} - {c.get('sector','')})
Aparece en {len(c['strategies'])} estrategias simultáneamente: {strats}
Score VALUE: {c.get('value_score','N/A')} | Grade: {c.get('conviction_grade','N/A')}
Upside analistas: {c.get('analyst_upside_pct','N/A')}% | FCF Yield: {c.get('fcf_yield_pct','N/A')}%

En 2-3 frases, explica por qué la convergencia de estas estrategias es significativa
y qué precauciones tener. Menciona si es una señal alcista fuerte o si hay matices.
Responde en español, máximo 3 frases."""
        c["analysis"] = ai_narrative(prompt, max_tokens=150) or \
            f"Convergencia de {len(c['strategies'])} estrategias: {strats}. Score: {c.get('convergence_score')}."

    result = {
        "generated_at": TODAY,
        "total_convergences": len(convergences),
        "triple_or_more": sum(1 for c in convergences if c["strategy_count"] >= 3),
        "convergences": convergences[:20],
    }

    print(f"  ✓ Found {len(convergences)} convergences ({result['triple_or_more']} triple+)")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 3. ALERT GENERATOR — detect events for tickers
# ══════════════════════════════════════════════════════════════════════════════

def generate_alerts(prev_convergence: dict | None = None) -> dict:
    print("\n[CEREBRO] Generating proactive alerts...")
    alerts = []

    # Load current data
    value_df  = pd.concat([
        load_csv(DOCS / "value_opportunities.csv"),
        load_csv(DOCS / "european_value_opportunities.csv"),
    ], ignore_index=True)
    mr_df     = load_csv(DOCS / "mean_reversion_opportunities.csv")
    insiders  = load_csv(DOCS / "recurring_insiders.csv")

    # ── Alert: ticker in MR zone (oversold bounce setup) ─────────────────────
    if not mr_df.empty and "ticker" in mr_df.columns:
        for _, row in mr_df.iterrows():
            ticker = str(row.get("ticker", "")).upper()
            score = safe_float(row.get("reversion_score"))
            rsi = safe_float(row.get("rsi"))
            quality = str(row.get("quality", ""))
            if score and score >= 70:
                severity = "HIGH" if score >= 80 else "MEDIUM"
                alerts.append({
                    "ticker": ticker,
                    "type": "MR_ZONE",
                    "severity": severity,
                    "title": f"{ticker} en zona oversold",
                    "message": f"RSI {rsi:.0f if rsi else 'N/A'}, score MR {score:.0f}. "
                               f"Calidad: {quality}. Posible rebote técnico.",
                    "date": TODAY,
                    "data": {
                        "reversion_score": score,
                        "rsi": rsi,
                        "quality": quality,
                    },
                })

    # ── Alert: earnings approaching for VALUE picks ───────────────────────────
    if not value_df.empty:
        for _, row in value_df.iterrows():
            ticker = str(row.get("ticker", "")).upper()
            days_to_earnings = safe_float(row.get("days_to_earnings"))
            earnings_warning = row.get("earnings_warning", False)
            value_score = safe_float(row.get("value_score"))
            if earnings_warning and days_to_earnings is not None and days_to_earnings <= 7:
                alerts.append({
                    "ticker": ticker,
                    "type": "EARNINGS_WARNING",
                    "severity": "HIGH" if days_to_earnings <= 3 else "MEDIUM",
                    "title": f"Earnings de {ticker} en {int(days_to_earnings)}d",
                    "message": f"Score VALUE {value_score:.0f if value_score else 'N/A'}. "
                               f"Earnings en {int(days_to_earnings)} días — evita entrar.",
                    "date": TODAY,
                    "data": {
                        "days_to_earnings": days_to_earnings,
                        "value_score": value_score,
                    },
                })

    # ── Alert: new insider buying ─────────────────────────────────────────────
    if not insiders.empty and "ticker" in insiders.columns:
        for _, row in insiders.iterrows():
            ticker = str(row.get("ticker", "")).upper()
            count = safe_float(row.get("purchase_count"))
            uniq  = safe_float(row.get("unique_insiders"))
            if count and count >= 3:
                alerts.append({
                    "ticker": ticker,
                    "type": "INSIDER_BUYING",
                    "severity": "HIGH" if (uniq or 0) >= 2 else "MEDIUM",
                    "title": f"Insider buying en {ticker}",
                    "message": f"{int(count)} compras por {int(uniq or 0)} directivos. "
                               f"Señal de convicción interna.",
                    "date": TODAY,
                    "data": {
                        "purchase_count": count,
                        "unique_insiders": uniq,
                    },
                })

    # ── Alert: new convergence (ticker just entered 2+ strategies) ────────────
    if prev_convergence:
        prev_tickers = {c["ticker"] for c in prev_convergence.get("convergences", [])}
        current_conv = scan_convergence()  # reuse if available
        for c in current_conv.get("convergences", []):
            if c["ticker"] not in prev_tickers and c["strategy_count"] >= 2:
                alerts.append({
                    "ticker": c["ticker"],
                    "type": "NEW_CONVERGENCE",
                    "severity": "HIGH" if c["strategy_count"] >= 3 else "MEDIUM",
                    "title": f"Nueva convergencia: {c['ticker']}",
                    "message": f"Aparece en {c['strategy_count']} estrategias: "
                               f"{', '.join(c['strategies'])}. Score: {c['convergence_score']}.",
                    "date": TODAY,
                    "data": c,
                })

    # Deduplicate by ticker+type
    seen = set()
    deduped = []
    for a in alerts:
        key = f"{a['ticker']}:{a['type']}"
        if key not in seen:
            seen.add(key)
            deduped.append(a)

    deduped.sort(key=lambda x: ({"HIGH": 0, "MEDIUM": 1}.get(x["severity"], 2), x["ticker"]))

    print(f"  ✓ Generated {len(deduped)} alerts ({sum(1 for a in deduped if a['severity']=='HIGH')} HIGH)")
    return {
        "generated_at": TODAY,
        "total": len(deduped),
        "high_count": sum(1 for a in deduped if a["severity"] == "HIGH"),
        "alerts": deduped,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4. SELF-CALIBRATION — what should we change in scoring?
# ══════════════════════════════════════════════════════════════════════════════

def self_calibrate(insights: dict) -> dict:
    print("\n[CEREBRO] Self-calibration analysis...")
    if not insights or "score_tiers" not in insights:
        return {}

    recommendations = []
    baseline = insights.get("baseline_win_rate_7d", 50)

    # Score tier analysis
    for tier in insights.get("score_tiers", []):
        if tier["vs_baseline_wr"] > 10 and tier["n"] >= 10:
            recommendations.append({
                "type": "BOOST",
                "factor": f"Score {tier['label']}",
                "insight": f"Señales con score {tier['label']} tienen {tier['win_rate_7d']}% WR "
                           f"({tier['vs_baseline_wr']:+.1f}pp sobre base). Priorizar este rango.",
                "n": tier["n"],
            })
        elif tier["vs_baseline_wr"] < -10 and tier["n"] >= 10:
            recommendations.append({
                "type": "REDUCE",
                "factor": f"Score {tier['label']}",
                "insight": f"Señales con score {tier['label']} tienen solo {tier['win_rate_7d']}% WR "
                           f"({tier['vs_baseline_wr']:+.1f}pp bajo base). Filtrar más agresivo.",
                "n": tier["n"],
            })

    # Regime analysis
    for regime in insights.get("market_regimes", []):
        if regime["vs_baseline_wr"] < -15 and regime["n"] >= 5:
            recommendations.append({
                "type": "REGIME_FILTER",
                "factor": f"Régimen {regime['label']}",
                "insight": f"En régimen {regime['label']}, solo {regime['win_rate_7d']}% WR. "
                           f"Considera pausar señales en este régimen.",
                "n": regime["n"],
            })

    # FCF analysis
    for fcf in insights.get("fcf_tiers", []):
        if fcf["label"] == "FCF≥5%" and fcf["vs_baseline_wr"] > 5 and fcf["n"] >= 5:
            recommendations.append({
                "type": "BOOST",
                "factor": "FCF Yield ≥5%",
                "insight": f"FCF yield alto mejora WR en +{fcf['vs_baseline_wr']:.1f}pp. "
                           f"Aumentar peso del FCF en scoring.",
                "n": fcf["n"],
            })

    # AI meta-analysis
    recs_text = "\n".join([f"- [{r['type']}] {r['factor']}: {r['insight']}" for r in recommendations[:5]])
    prompt = f"""Como sistema de IA auto-mejorable de inversión VALUE, analiza estas recomendaciones de calibración
basadas en {insights.get('total_analyzed', 0)} señales históricas:

{recs_text if recs_text else 'Sin recomendaciones significativas aún.'}

Win rate base del sistema: {baseline:.1f}%

En 2-3 frases, resume qué ajustes son más urgentes y por qué.
Responde en español."""

    narrative = ai_narrative(prompt, max_tokens=200) or \
        "El sistema continúa aprendiendo de las señales históricas. " \
        "Se necesitan más datos completados para recomendaciones precisas."

    result = {
        "generated_at": TODAY,
        "recommendations": recommendations,
        "narrative": narrative,
        "total_recommendations": len(recommendations),
    }
    print(f"  ✓ Generated {len(recommendations)} calibration recommendations")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("CEREBRO — Proactive AI Agent")
    print(f"Date: {TODAY}")
    print("=" * 60)

    if not groq_client:
        print("⚠️  Running without AI (no GROQ_API_KEY) — rule-based mode only")

    # Load previous convergence for delta detection
    prev_conv = None
    prev_conv_path = DOCS / "cerebro_convergence.json"
    if prev_conv_path.exists():
        try:
            with open(prev_conv_path) as f:
                prev_conv = json.load(f)
                if prev_conv.get("generated_at") == TODAY:
                    prev_conv = None  # same day — no delta
        except Exception:
            pass

    # Run all 4 modules
    insights    = mine_patterns()
    convergence = scan_convergence()
    alerts      = generate_alerts(prev_convergence=prev_conv)
    calibration = self_calibrate(insights)

    # Write outputs
    outputs = {
        "cerebro_insights.json":     insights,
        "cerebro_convergence.json":  convergence,
        "cerebro_alerts.json":       alerts,
        "cerebro_calibration.json":  calibration,
    }

    for filename, data in outputs.items():
        path = DOCS / filename
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"\n✓ Written: {path}")

    # Summary
    print("\n" + "=" * 60)
    print("CEREBRO SUMMARY")
    print("=" * 60)
    print(f"  Pattern mining : {insights.get('total_analyzed', 0)} signals, "
          f"baseline WR {insights.get('baseline_win_rate_7d', 0):.1f}%")
    print(f"  Convergences   : {convergence.get('total_convergences', 0)} found "
          f"({convergence.get('triple_or_more', 0)} triple+)")
    print(f"  Alerts         : {alerts.get('total', 0)} total "
          f"({alerts.get('high_count', 0)} HIGH)")
    print(f"  Calibration    : {calibration.get('total_recommendations', 0)} recommendations")
    print("=" * 60)


if __name__ == "__main__":
    main()
