#!/usr/bin/env python3
"""
CEREBRO — Proactive AI Agent
Runs daily at end of pipeline. 6 modules:

1. PATTERN MINING    : portfolio_tracker history → learns what predicts wins
2. CONVERGENCE SCAN  : tickers in 2+ strategies → ranks, narrates, tracks streak
3. ALERT GENERATOR   : MR zone, score drift, earnings warnings, new convergences
4. SELF-CALIBRATION  : identifies over/under-weighted factors
5. AUTO-TUNING       : writes scoring_weights_suggested.json for human review
6. ENTRY SIGNALS     : semáforo de entrada — cuándo comprar y por qué

Outputs (docs/):
  cerebro_insights.json         — what the system learned from history
  cerebro_convergence.json      — today's multi-strategy convergences + AI analysis
  cerebro_alerts.json           — proactive ticker events
  cerebro_calibration.json      — calibration recommendations
  cerebro_entry_signals.json    — entry timing signals with score + missing signals
  scoring_weights_suggested.json — auto-tuning proposals (human review required)
"""

import os, json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date, datetime

try:
    from groq import Groq
    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY")) if os.getenv("GROQ_API_KEY") else None
except Exception:
    groq_client = None

DOCS  = Path("docs")
TODAY = date.today().isoformat()


# ── helpers ───────────────────────────────────────────────────────────────────

def load_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()

def load_json(path: Path) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}

def save_json(path: Path, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)

def sf(v):
    try:
        x = float(v)
        return None if (x != x) else x  # NaN check
    except Exception:
        return None

def ai(prompt: str, max_tokens: int = 300):
    if not groq_client:
        return None
    try:
        r = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens, temperature=0.4,
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        print(f"  [AI] {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 1. PATTERN MINING
# ══════════════════════════════════════════════════════════════════════════════

def mine_patterns() -> dict:
    print("\n[1/5] Pattern mining...")
    df = load_csv(DOCS / "portfolio_tracker" / "recommendations.csv")
    done = df[df["return_7d"].notna()].copy() if not df.empty else pd.DataFrame()
    if len(done) < 10:
        print(f"  Only {len(done)} completed signals — need more data.")
        return {"total_analyzed": len(done), "narrative": None}

    base_wr  = float(done["win_7d"].mean()) * 100 if "win_7d" in done.columns else 50.0
    base_ret = float(done["return_7d"].mean())
    print(f"  {len(done)} signals · baseline WR {base_wr:.1f}%")

    def stats(sub: pd.DataFrame, label: str):
        if len(sub) < 3:
            return None
        wr  = float(sub["win_7d"].mean()) * 100 if "win_7d" in sub.columns else 0.0
        ret = float(sub["return_7d"].mean())
        ret14 = float(sub["return_14d"].mean()) if "return_14d" in sub.columns and sub["return_14d"].notna().any() else None
        return dict(label=label, win_rate_7d=round(wr,1), avg_return_7d=round(ret,2),
                    avg_return_14d=round(ret14,2) if ret14 else None,
                    n=len(sub), vs_baseline_wr=round(wr-base_wr,1), vs_baseline_ret=round(ret-base_ret,2))

    def tier_col(col, ranges):
        out = []
        for lo, hi in ranges:
            s = stats(done[(done[col] >= lo) & (done[col] < hi)], f"{lo}–{hi}")
            if s: out.append(s)
        return out

    score_tiers = tier_col("value_score", [(90,101),(80,90),(70,80),(60,70),(50,60)]) if "value_score" in done.columns else []

    regimes = []
    if "market_regime" in done.columns:
        for r in done["market_regime"].dropna().unique():
            s = stats(done[done["market_regime"] == r], r)
            if s: regimes.append(s)
        regimes.sort(key=lambda x: x["win_rate_7d"], reverse=True)

    sectors = []
    if "sector" in done.columns:
        for sec in done["sector"].dropna().unique():
            s = stats(done[done["sector"] == sec], sec)
            if s: sectors.append(s)
        sectors.sort(key=lambda x: x["win_rate_7d"], reverse=True)

    fcf_tiers = []
    if "fcf_yield_pct" in done.columns:
        for sub, lbl in [
            (done[done["fcf_yield_pct"] >= 5],   "FCF≥5%"),
            (done[(done["fcf_yield_pct"] >= 2) & (done["fcf_yield_pct"] < 5)], "FCF 2-5%"),
            (done[done["fcf_yield_pct"] < 2],    "FCF<2%"),
            (done[done["fcf_yield_pct"] < 0],    "FCF<0%"),
        ]:
            s = stats(sub, lbl)
            if s: fcf_tiers.append(s)

    rr_tiers = []
    if "risk_reward_ratio" in done.columns:
        for sub, lbl in [
            (done[done["risk_reward_ratio"] >= 3], "R:R≥3"),
            (done[(done["risk_reward_ratio"] >= 2) & (done["risk_reward_ratio"] < 3)], "R:R 2-3"),
            (done[done["risk_reward_ratio"] < 2], "R:R<2"),
        ]:
            s = stats(sub, lbl)
            if s: rr_tiers.append(s)

    period_stats = {}
    for p in ["7d","14d","30d"]:
        sub = done[done[f"return_{p}"].notna()] if f"return_{p}" in done.columns else pd.DataFrame()
        if not sub.empty:
            period_stats[p] = dict(
                win_rate=round(float(sub[f"win_{p}"].mean())*100,1) if f"win_{p}" in sub.columns else None,
                avg_return=round(float(sub[f"return_{p}"].mean()),2),
                n=len(sub))

    best_combos = []
    if "value_score" in done.columns and "market_regime" in done.columns:
        s = stats(done[(done["value_score"]>=80) & done["market_regime"].str.upper().str.contains("BULL|ALCISTA",na=False)], "Score≥80 + Mercado alcista")
        if s: best_combos.append(s)
    if "value_score" in done.columns and "fcf_yield_pct" in done.columns:
        s = stats(done[(done["value_score"]>=70) & (done["fcf_yield_pct"]>=5)], "Score≥70 + FCF≥5%")
        if s: best_combos.append(s)

    # AI narrative
    bt = max(score_tiers, key=lambda x: x["win_rate_7d"], default={})
    br = regimes[0] if regimes else {}
    bs = sectors[0] if sectors else {}
    narrative = ai(
        f"Eres el cerebro analítico de un sistema VALUE. {len(done)} señales analizadas, win rate base {base_wr:.1f}%.\n"
        f"Mejor score tier: {bt.get('label','N/A')} → {bt.get('win_rate_7d','N/A')}% WR (ret {bt.get('avg_return_7d','N/A')}%)\n"
        f"Mejor régimen: {br.get('label','N/A')} → {br.get('win_rate_7d','N/A')}% WR\n"
        f"Mejor sector: {bs.get('label','N/A')} → {bs.get('win_rate_7d','N/A')}% WR\n"
        f"FCF≥5%: {next((x['win_rate_7d'] for x in fcf_tiers if x['label']=='FCF≥5%'),'N/A')}% WR\n"
        f"Combos: {[(c['label'],c['win_rate_7d']) for c in best_combos]}\n"
        "3-4 frases en español. Conclusiones accionables: qué favorece victorias, qué evitar.", 250
    ) or f"Sistema analizó {len(done)} señales. Win rate base {base_wr:.1f}%. Mejor tier: {bt.get('label','N/A')} con {bt.get('win_rate_7d','N/A')}% WR."

    print(f"  ✓ Done")
    return dict(generated_at=TODAY, total_analyzed=len(done), baseline_win_rate_7d=round(base_wr,1),
                baseline_avg_return_7d=round(base_ret,2), score_tiers=score_tiers, market_regimes=regimes,
                sectors=sectors[:10], fcf_tiers=fcf_tiers, rr_tiers=rr_tiers, period_stats=period_stats,
                best_combos=best_combos, narrative=narrative)


# ══════════════════════════════════════════════════════════════════════════════
# 2. CONVERGENCE SCAN (with streak tracking)
# ══════════════════════════════════════════════════════════════════════════════

def scan_convergence() -> dict:
    print("\n[2/5] Convergence scan...")

    dfs = {
        "VALUE":    pd.concat([load_csv(DOCS/"value_opportunities.csv"), load_csv(DOCS/"european_value_opportunities.csv")], ignore_index=True),
        "INSIDERS": load_csv(DOCS/"recurring_insiders.csv"),
        "MR":       load_csv(DOCS/"mean_reversion_opportunities.csv"),
        "OPTIONS":  load_csv(DOCS/"options_flow.csv"),
        "MOMENTUM": load_csv(DOCS/"momentum_opportunities.csv"),
    }

    def tset(df): return set(df["ticker"].dropna().str.upper()) if not df.empty and "ticker" in df.columns else set()
    sets = {k: tset(v) for k, v in dfs.items()}

    # Build metadata from VALUE
    meta: dict[str, dict] = {}
    for _, row in dfs["VALUE"].iterrows():
        t = str(row.get("ticker","")).upper()
        if t and t not in meta:
            meta[t] = dict(ticker=t, company_name=str(row.get("company_name","")),
                           sector=str(row.get("sector","")), value_score=sf(row.get("value_score")),
                           conviction_grade=str(row.get("conviction_grade","")),
                           analyst_upside_pct=sf(row.get("analyst_upside_pct")),
                           fcf_yield_pct=sf(row.get("fcf_yield_pct")),
                           current_price=sf(row.get("current_price")),
                           earnings_warning=bool(row.get("earnings_warning", False)),
                           days_to_earnings=sf(row.get("days_to_earnings")))

    # Load previous convergence for streak calculation
    prev = load_json(DOCS / "cerebro_convergence.json")
    prev_streaks: dict[str, int] = {c["ticker"]: c.get("streak_days", 1) for c in prev.get("convergences", [])}
    prev_date = prev.get("generated_at", "")

    all_tickers = set().union(*sets.values())
    convergences = []
    for ticker in all_tickers:
        strategies = [name for name, s in sets.items() if ticker in s]
        if len(strategies) < 2:
            continue
        m = meta.get(ticker, {"ticker": ticker})

        # Streak: how many consecutive days in convergence
        streak = (prev_streaks.get(ticker, 0) + 1) if prev_date != TODAY else prev_streaks.get(ticker, 1)

        score = len(strategies) * 20
        if "VALUE" in strategies and m.get("value_score"):
            score += min(20, (m["value_score"] or 0) / 5)
        if "INSIDERS" in strategies: score += 10
        if streak >= 3: score += 10  # persistence bonus
        score = min(100, int(score))

        convergences.append(dict(
            ticker=ticker, company_name=m.get("company_name",""), sector=m.get("sector",""),
            strategies=strategies, strategy_count=len(strategies), convergence_score=score,
            value_score=m.get("value_score"), conviction_grade=m.get("conviction_grade",""),
            analyst_upside_pct=m.get("analyst_upside_pct"), fcf_yield_pct=m.get("fcf_yield_pct"),
            current_price=m.get("current_price"), streak_days=streak,
            earnings_warning=m.get("earnings_warning", False),
            days_to_earnings=m.get("days_to_earnings"), analysis=None,
        ))

    convergences.sort(key=lambda x: (x["strategy_count"], x["convergence_score"], x["streak_days"]), reverse=True)

    # AI analysis for top 3
    for c in convergences[:3]:
        streak_note = f" (en convergencia {c['streak_days']} días consecutivos)" if c["streak_days"] >= 2 else ""
        c["analysis"] = ai(
            f"Ticker: {c['ticker']} ({c.get('company_name','')} - {c.get('sector','')})\n"
            f"Estrategias: {', '.join(c['strategies'])}{streak_note}\n"
            f"Score VALUE: {c.get('value_score','N/A')} | Grade: {c.get('conviction_grade','N/A')}\n"
            f"Upside: {c.get('analyst_upside_pct','N/A')}% | FCF: {c.get('fcf_yield_pct','N/A')}%\n"
            f"{'⚠️ EARNINGS en ' + str(int(c['days_to_earnings'])) + ' días' if c.get('earnings_warning') else ''}\n"
            "2-3 frases en español. Por qué la convergencia es significativa y qué precauciones tener.", 150
        ) or f"Convergencia de {len(c['strategies'])} estrategias: {', '.join(c['strategies'])}."

    print(f"  ✓ {len(convergences)} convergences ({sum(1 for c in convergences if c['strategy_count']>=3)} triple+)")
    return dict(generated_at=TODAY, total_convergences=len(convergences),
                triple_or_more=sum(1 for c in convergences if c["strategy_count"]>=3),
                convergences=convergences[:25])


# ══════════════════════════════════════════════════════════════════════════════
# 3. ALERT GENERATOR (uses pre-computed convergence, adds score drift)
# ══════════════════════════════════════════════════════════════════════════════

def generate_alerts(convergence: dict) -> dict:
    print("\n[3/5] Alert generation...")
    alerts = []

    value_df  = pd.concat([load_csv(DOCS/"value_opportunities.csv"), load_csv(DOCS/"european_value_opportunities.csv")], ignore_index=True)
    mr_df     = load_csv(DOCS/"mean_reversion_opportunities.csv")
    insiders  = load_csv(DOCS/"recurring_insiders.csv")
    prev_conv = load_json(DOCS/"cerebro_convergence.json")

    # ── MR zone entries ────────────────────────────────────────────────────────
    if not mr_df.empty and "ticker" in mr_df.columns:
        for _, row in mr_df.iterrows():
            t = str(row.get("ticker","")).upper()
            score = sf(row.get("reversion_score"))
            rsi   = sf(row.get("rsi"))
            qual  = str(row.get("quality",""))
            if score and score >= 70:
                alerts.append(dict(ticker=t, type="MR_ZONE",
                    severity="HIGH" if score >= 80 else "MEDIUM",
                    title=f"{t} en zona oversold",
                    message=f"RSI {f'{rsi:.0f}' if rsi else 'N/A'}, score MR {score:.0f}. Calidad: {qual}. Posible rebote técnico.",
                    date=TODAY, data=dict(reversion_score=score, rsi=rsi, quality=qual)))

    # ── Earnings warnings ──────────────────────────────────────────────────────
    if not value_df.empty:
        for _, row in value_df.iterrows():
            t    = str(row.get("ticker","")).upper()
            dte  = sf(row.get("days_to_earnings"))
            warn = bool(row.get("earnings_warning", False))
            vscore = sf(row.get("value_score"))
            if warn and dte is not None and dte <= 7:
                alerts.append(dict(ticker=t, type="EARNINGS_WARNING",
                    severity="HIGH" if dte <= 3 else "MEDIUM",
                    title=f"Earnings de {t} en {int(dte)}d",
                    message=f"Score VALUE {f'{vscore:.0f}' if vscore else 'N/A'}. Earnings en {int(dte)} días — evita entrar.",
                    date=TODAY, data=dict(days_to_earnings=dte, value_score=vscore)))

    # ── Insider buying ─────────────────────────────────────────────────────────
    if not insiders.empty and "ticker" in insiders.columns:
        for _, row in insiders.iterrows():
            t    = str(row.get("ticker","")).upper()
            cnt  = sf(row.get("purchase_count"))
            uniq = sf(row.get("unique_insiders"))
            if cnt and cnt >= 3:
                alerts.append(dict(ticker=t, type="INSIDER_BUYING",
                    severity="HIGH" if (uniq or 0) >= 2 else "MEDIUM",
                    title=f"Insider buying en {t}",
                    message=f"{int(cnt)} compras por {int(uniq or 0)} directivos. Señal de convicción interna.",
                    date=TODAY, data=dict(purchase_count=cnt, unique_insiders=uniq)))

    # ── Score drift (thesis threatened) ───────────────────────────────────────
    # Compare today's value_score vs the score when the ticker first appeared in portfolio_tracker
    tracker = load_csv(DOCS / "portfolio_tracker" / "recommendations.csv")
    if not tracker.empty and not value_df.empty and "ticker" in tracker.columns and "value_score" in tracker.columns:
        # For each ticker currently in VALUE list, find its earliest recorded score
        for _, row in value_df.iterrows():
            t      = str(row.get("ticker","")).upper()
            cur    = sf(row.get("value_score"))
            if cur is None: continue
            hist   = tracker[tracker["ticker"] == t]["value_score"].dropna()
            if hist.empty: continue
            orig   = float(hist.iloc[0])
            drop   = orig - cur
            if drop >= 15:  # score dropped 15+ pts since first signal
                alerts.append(dict(ticker=t, type="SCORE_DRIFT",
                    severity="HIGH" if drop >= 25 else "MEDIUM",
                    title=f"Tesis en riesgo: {t}",
                    message=f"Score bajó {drop:.0f} pts (de {orig:.0f} → {cur:.0f}). "
                            f"Fundamentales pueden haber deteriorado — revisa la tesis.",
                    date=TODAY, data=dict(original_score=round(orig,1), current_score=round(cur,1), drop=round(drop,1))))

    # ── New convergences (not in yesterday's scan) ─────────────────────────────
    prev_tickers = {c["ticker"] for c in prev_conv.get("convergences", [])}
    if prev_conv.get("generated_at", "") != TODAY:
        for c in convergence.get("convergences", []):
            if c["ticker"] not in prev_tickers and c["strategy_count"] >= 2:
                alerts.append(dict(ticker=c["ticker"], type="NEW_CONVERGENCE",
                    severity="HIGH" if c["strategy_count"] >= 3 else "MEDIUM",
                    title=f"Nueva convergencia: {c['ticker']}",
                    message=f"Aparece en {c['strategy_count']} estrategias: {', '.join(c['strategies'])}. "
                            f"Score convergencia: {c['convergence_score']}.",
                    date=TODAY, data=dict(strategies=c["strategies"], convergence_score=c["convergence_score"])))

    # ── Long streak highlight ──────────────────────────────────────────────────
    for c in convergence.get("convergences", []):
        if c.get("streak_days", 0) >= 3:
            alerts.append(dict(ticker=c["ticker"], type="STREAK",
                severity="HIGH" if c["streak_days"] >= 5 else "MEDIUM",
                title=f"{c['ticker']} — {c['streak_days']} días en convergencia",
                message=f"Lleva {c['streak_days']} días consecutivos en {len(c['strategies'])} estrategias. "
                        f"Señal persistente de alta convicción.",
                date=TODAY, data=dict(streak_days=c["streak_days"], strategies=c["strategies"])))

    # Deduplicate by ticker+type, sort HIGH first
    seen, deduped = set(), []
    for a in alerts:
        k = f"{a['ticker']}:{a['type']}"
        if k not in seen:
            seen.add(k)
            deduped.append(a)
    deduped.sort(key=lambda x: ({"HIGH":0,"MEDIUM":1}.get(x["severity"],2), x["ticker"]))

    high = sum(1 for a in deduped if a["severity"] == "HIGH")
    print(f"  ✓ {len(deduped)} alerts ({high} HIGH)")
    return dict(generated_at=TODAY, total=len(deduped), high_count=high, alerts=deduped)


# ══════════════════════════════════════════════════════════════════════════════
# 4. SELF-CALIBRATION
# ══════════════════════════════════════════════════════════════════════════════

def self_calibrate(insights: dict) -> dict:
    print("\n[4/5] Self-calibration...")
    if not insights or "score_tiers" not in insights:
        return dict(generated_at=TODAY, recommendations=[], narrative=None, total_recommendations=0)

    baseline = insights.get("baseline_win_rate_7d", 50)
    recs = []

    for tier in insights.get("score_tiers", []):
        if tier["vs_baseline_wr"] > 10 and tier["n"] >= 10:
            recs.append(dict(type="BOOST", factor=f"Score {tier['label']}",
                insight=f"WR {tier['win_rate_7d']}% ({tier['vs_baseline_wr']:+.1f}pp sobre base). Priorizar este rango.", n=tier["n"]))
        elif tier["vs_baseline_wr"] < -10 and tier["n"] >= 10:
            recs.append(dict(type="REDUCE", factor=f"Score {tier['label']}",
                insight=f"Solo {tier['win_rate_7d']}% WR ({tier['vs_baseline_wr']:+.1f}pp bajo base). Filtrar más agresivo.", n=tier["n"]))

    for reg in insights.get("market_regimes", []):
        if reg["vs_baseline_wr"] < -15 and reg["n"] >= 5:
            recs.append(dict(type="REGIME_FILTER", factor=f"Régimen {reg['label']}",
                insight=f"Solo {reg['win_rate_7d']}% WR en {reg['label']}. Considera pausar señales.", n=reg["n"]))

    for fcf in insights.get("fcf_tiers", []):
        if fcf["label"] == "FCF≥5%" and fcf["vs_baseline_wr"] > 5 and fcf["n"] >= 5:
            recs.append(dict(type="BOOST", factor="FCF Yield ≥5%",
                insight=f"FCF alto mejora WR +{fcf['vs_baseline_wr']:.1f}pp. Aumentar peso FCF.", n=fcf["n"]))
        if fcf["label"] == "FCF<0%" and fcf["vs_baseline_wr"] < -5 and fcf["n"] >= 5:
            recs.append(dict(type="REDUCE", factor="FCF Negativo",
                insight=f"FCF negativo reduce WR {fcf['vs_baseline_wr']:.1f}pp. Penalizar más agresivo.", n=fcf["n"]))

    for rr in insights.get("rr_tiers", []):
        if rr["label"] == "R:R≥3" and rr["vs_baseline_wr"] > 5 and rr["n"] >= 5:
            recs.append(dict(type="BOOST", factor="R:R ≥3",
                insight=f"R:R alto mejora WR +{rr['vs_baseline_wr']:.1f}pp. Aumentar peso R:R.", n=rr["n"]))

    recs_text = "\n".join(f"- [{r['type']}] {r['factor']}: {r['insight']}" for r in recs[:5])
    narrative = ai(
        f"Sistema VALUE — {insights.get('total_analyzed',0)} señales, WR base {baseline:.1f}%.\n"
        f"Recomendaciones de calibración:\n{recs_text or 'Sin recomendaciones significativas.'}\n"
        "2-3 frases en español. Qué ajustes son más urgentes y por qué.", 200
    ) or "El sistema continúa aprendiendo. Se necesitan más señales completadas para recomendaciones precisas."

    print(f"  ✓ {len(recs)} recommendations")
    return dict(generated_at=TODAY, recommendations=recs, narrative=narrative, total_recommendations=len(recs))


# ══════════════════════════════════════════════════════════════════════════════
# 5. AUTO-TUNING — generate scoring_weights_suggested.json
# ══════════════════════════════════════════════════════════════════════════════

def auto_tune(insights: dict, calibration: dict) -> dict:
    print("\n[5/5] Auto-tuning weights...")

    # Current weights (from super_score_integrator logic — approximate)
    current_weights = {
        "fundamentals":          40,   # fundamental_score component
        "profitability_bonus":   15,   # ROE, margins, cashflow
        "insiders":              15,   # insider buying
        "institutional":         15,   # institutional ownership
        "options_flow":          10,   # options activity
        "ml_score":               5,   # ML prediction
        "sector_rotation":       10,   # sector timing
        "mean_reversion":        10,   # oversold bounce
        "fcf_yield_bonus":        8,   # FCF yield extra bonus
        "dividend_quality":       5,   # dividend sustainability
        "buyback_bonus":          3,   # share repurchases
        "analyst_revision":       5,   # estimate revisions
        "risk_reward_bonus":      3,   # R:R ratio
    }

    suggested_weights = dict(current_weights)
    adjustments = []

    # Apply calibration recommendations
    for rec in calibration.get("recommendations", []):
        if rec["type"] == "BOOST" and "FCF" in rec["factor"]:
            delta = min(3, rec["n"] // 10)
            suggested_weights["fcf_yield_bonus"] = current_weights["fcf_yield_bonus"] + delta
            adjustments.append(dict(factor="fcf_yield_bonus", change=f"+{delta}", reason=rec["insight"], n=rec["n"]))

        elif rec["type"] == "BOOST" and "R:R" in rec["factor"]:
            delta = min(2, rec["n"] // 15)
            suggested_weights["risk_reward_bonus"] = current_weights["risk_reward_bonus"] + delta
            adjustments.append(dict(factor="risk_reward_bonus", change=f"+{delta}", reason=rec["insight"], n=rec["n"]))

        elif rec["type"] == "REDUCE" and "FCF Negativo" in rec["factor"]:
            suggested_weights["fcf_yield_bonus"] = max(5, current_weights["fcf_yield_bonus"] - 2)
            adjustments.append(dict(factor="fcf_yield_bonus_penalty", change="-2 (stricter negative FCF penalty)", reason=rec["insight"], n=rec["n"]))

    # Regime-based insight: if CORRECTION has very low WR, boost mean_reversion (it's the strategy that works in corrections)
    for reg in insights.get("market_regimes", []):
        if "CORRECT" in str(reg.get("label","")).upper() and reg.get("vs_baseline_wr",0) < -15:
            suggested_weights["mean_reversion"] = min(15, current_weights["mean_reversion"] + 3)
            adjustments.append(dict(factor="mean_reversion", change="+3 (corrections favor MR bounces)", reason=f"MR outperforms in {reg['label']}", n=reg["n"]))
            break

    # Best score tier insight
    best_tier = max(insights.get("score_tiers",[]), key=lambda x: x["win_rate_7d"], default=None)
    if best_tier and best_tier["vs_baseline_wr"] > 15 and "80" in best_tier.get("label",""):
        adjustments.append(dict(factor="score_threshold_note",
            change="Consider raising minimum threshold to 70+ for published picks",
            reason=f"Score 80+ has {best_tier['win_rate_7d']}% WR vs {insights.get('baseline_win_rate_7d',50):.0f}% base",
            n=best_tier["n"]))

    narrative = ai(
        f"Sistema de scoring VALUE — propuestas de ajuste de pesos basadas en {insights.get('total_analyzed',0)} señales históricas:\n"
        + "\n".join(f"- {a['factor']}: {a['change']} — {a['reason']}" for a in adjustments[:5])
        + "\n\nNota: estos cambios requieren revisión humana antes de aplicar.\n"
        "2 frases en español: resume el impacto esperado de estos ajustes.", 150
    ) or "Ajustes propuestos basados en análisis histórico. Requieren revisión antes de aplicar al pipeline."

    result = dict(
        generated_at=TODAY,
        status="PENDING_REVIEW",
        note="These weights are suggestions only. Apply manually after review.",
        current_weights=current_weights,
        suggested_weights=suggested_weights,
        adjustments=adjustments,
        expected_impact=f"Based on {insights.get('total_analyzed',0)} historical signals",
        narrative=narrative,
    )
    print(f"  ✓ {len(adjustments)} weight adjustments proposed")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 6. ENTRY SIGNALS — semáforo de entrada
# ══════════════════════════════════════════════════════════════════════════════

def scan_entry_signals(convergence: dict) -> dict:
    """
    For each ticker in VALUE (US + EU), compute an entry score 0-100 based on
    how many confirming signals are present. The more signals align, the clearer
    the entry. Also reports which signals are MISSING so the user knows what to
    wait for.

    Entry signal levels:
        STRONG BUY  ≥ 75
        BUY         ≥ 50
        MONITOR     ≥ 30
        WAIT        < 30
    """
    print("[6/6] Entry signal scan...")

    # ── Load all data sources ──────────────────────────────────────────────────
    value_df    = load_csv(DOCS / "value_opportunities.csv")
    value_eu_df = load_csv(DOCS / "european_value_opportunities.csv")
    insiders_df = load_csv(DOCS / "recurring_insiders.csv")
    eu_ins_df   = load_csv(DOCS / "eu_recurring_insiders.csv")
    mr_df       = load_csv(DOCS / "mean_reversion_opportunities.csv")
    options_df  = load_csv(DOCS / "options_flow.csv")
    sector_df   = load_csv(DOCS / "sector_rotation.csv")
    regime_json = load_json(DOCS / "market_regime.json")

    # Previous entry signals (track days_in_value streak)
    prev = load_json(DOCS / "cerebro_entry_signals.json")
    prev_map = {s["ticker"]: s for s in prev.get("signals", [])}

    # ── Build lookup sets ──────────────────────────────────────────────────────
    insider_tickers = set()
    for df in [insiders_df, eu_ins_df]:
        if not df.empty and "ticker" in df.columns:
            insider_tickers |= set(df["ticker"].str.upper().dropna())

    mr_tickers = {}
    if not mr_df.empty and "ticker" in mr_df.columns:
        for _, row in mr_df.iterrows():
            t = str(row.get("ticker", "")).upper()
            mr_tickers[t] = {
                "rsi": sf(row.get("rsi")),
                "reversion_score": sf(row.get("reversion_score")),
                "quality": str(row.get("quality", "")),
            }

    options_bullish = set()
    if not options_df.empty:
        for _, row in options_df.iterrows():
            sent = str(row.get("sentiment", "")).lower()
            if "bull" in sent:
                options_bullish.add(str(row.get("ticker", "")).upper())

    # Favorable sectors from sector rotation
    fav_sectors = set()
    if not sector_df.empty:
        scol = "sector" if "sector" in sector_df.columns else None
        rcol = next((c for c in ["rs_score","score","rank"] if c in sector_df.columns), None)
        if scol and rcol:
            try:
                top = sector_df.nlargest(5, rcol)
                fav_sectors = set(top[scol].str.upper().dropna())
            except Exception:
                pass

    # Market regime
    us_regime = ""
    try:
        us_regime = str(regime_json.get("us", {}).get("regime", "")).upper()
    except Exception:
        pass
    regime_ok = any(r in us_regime for r in ["BULL", "RECOVERY"])

    # Convergence streak map
    conv_streak = {s["ticker"]: s.get("streak_days", 1) for s in convergence.get("convergences", [])}

    # ── Score each VALUE ticker ────────────────────────────────────────────────
    all_value = []
    for df, region in [(value_df, "US"), (value_eu_df, "EU")]:
        if df.empty:
            continue
        for _, row in df.iterrows():
            t = str(row.get("ticker", "")).upper()
            if not t:
                continue

            vscore  = sf(row.get("value_score"))
            upside  = sf(row.get("analyst_upside_pct"))
            fcf     = sf(row.get("fcf_yield_pct"))
            rr      = sf(row.get("risk_reward_ratio"))
            dte     = sf(row.get("days_to_earnings"))
            earn_w  = bool(row.get("earnings_warning", False))
            sector  = str(row.get("sector", "")).upper()
            grade   = str(row.get("conviction_grade", ""))
            price   = sf(row.get("current_price"))
            upside_raw = sf(row.get("analyst_upside_pct"))
            an_rev      = sf(row.get("analyst_revision_momentum"))
            an_count    = sf(row.get("analyst_count"))
            an_rec      = str(row.get("analyst_recommendation", "")).lower()
            company     = str(row.get("company_name", t))

            # Hard filters — skip if fails
            if vscore is None or vscore < 60:
                continue
            if upside is not None and upside < 10:
                continue

            # ── Score signals ──────────────────────────────────────────────────
            fired: list[dict] = []
            missing: list[str] = []

            def sig(name: str, pts: int, condition: bool, missing_label: str = ""):
                if condition:
                    fired.append({"name": name, "pts": pts})
                elif missing_label:
                    missing.append(missing_label)

            # Core value quality
            sig("Value score ≥80",     10, vscore >= 80,              "Value score <80")
            sig("Value score ≥70",      5, 70 <= vscore < 80)         # bonus, no missing
            sig("FCF yield ≥5%",       10, fcf is not None and fcf >= 5,   "FCF yield <5%")
            sig("R:R ≥2",              10, rr is not None and rr >= 2,     "R:R <2")
            sig("Upside ≥20%",          8, upside is not None and upside >= 20, "Upside <20%")

            # Timing / catalysts
            sig("Insider buying",      25, t in insider_tickers,        "Sin insider buying (espera)")
            sig("MR zone / oversold",  20, t in mr_tickers,             "Sin señal MR oversold")
            sig("Options flow alcista",15, t in options_bullish,         "Sin opciones alcistas")
            sig("Analyst revision ↑",   5, an_rev is not None and an_rev > 0, "")

            # Macro / context
            sig("Sector favorable",     8, bool(fav_sectors) and any(s in sector for s in fav_sectors), "Sector no líder")
            sig("Régimen alcista",       7, regime_ok,                   "" if regime_ok else "Régimen no alcista")

            # Persistence — days the ticker has been in VALUE
            streak = conv_streak.get(t, 1)
            prev_days = prev_map.get(t, {}).get("days_in_value", 0)
            days_in_value = prev_days + 1
            sig("En VALUE ≥3 días",    10, days_in_value >= 3,          f"Solo {days_in_value}d en VALUE" if days_in_value < 3 else "")

            # Safety checks — negative signals
            penalty = 0
            if earn_w and dte is not None and dte <= 7:
                penalty += 15
                missing.append(f"⚠ Earnings en {int(dte)}d — riesgo de entrada")
            if upside is not None and upside < 15:
                penalty += 5

            # ── Upside credibility filter ──────────────────────────────────
            # High upside with few/no analysts or 'none' recommendation = unreliable
            if upside is not None and upside > 60:
                if an_count is not None and an_count < 3:
                    penalty += 20
                    missing.append(f"⚠ Upside {upside:.0f}% con solo {int(an_count)} analista(s) — poco creíble")
                elif an_count is not None and an_count < 6:
                    penalty += 12
                    missing.append(f"⚠ Upside {upside:.0f}% con solo {int(an_count)} analistas — verificar")
                elif an_rec in ("none", "", "nan") or not an_rec:
                    penalty += 15
                    missing.append(f"⚠ Upside {upside:.0f}% pero analistas no recomiendan — contradictorio")
                else:
                    penalty += 8
                    missing.append(f"Upside {upside:.0f}% muy alto — confirmar con DCF")
            if upside is not None and upside > 80 and an_count is not None and an_count < 10:
                penalty += 10  # extra penalización para upside extremo con cobertura limitada

            entry_score_raw = sum(s["pts"] for s in fired) - penalty
            entry_score = max(0, min(100, entry_score_raw))

            if entry_score >= 75:
                signal = "STRONG_BUY"
            elif entry_score >= 50:
                signal = "BUY"
            elif entry_score >= 30:
                signal = "MONITOR"
            else:
                signal = "WAIT"

            # MR detail
            mr_detail = mr_tickers.get(t, {})

            all_value.append(dict(
                ticker=t,
                company_name=company,
                region=region,
                sector=sector.title(),
                value_score=vscore,
                conviction_grade=grade,
                current_price=price,
                analyst_upside_pct=upside_raw,
                fcf_yield_pct=fcf,
                risk_reward_ratio=rr,
                days_in_value=days_in_value,
                streak_days=streak,
                entry_score=round(entry_score),
                signal=signal,
                signals_fired=[s["name"] for s in fired],
                signals_pts=fired,
                signals_missing=missing,
                rsi=mr_detail.get("rsi"),
                earnings_warning=earn_w,
                days_to_earnings=int(dte) if dte is not None else None,
            ))

    # Sort: STRONG_BUY first, then by entry_score desc
    order = {"STRONG_BUY": 0, "BUY": 1, "MONITOR": 2, "WAIT": 3}
    all_value.sort(key=lambda x: (order.get(x["signal"], 4), -x["entry_score"]))

    # AI narrative for top 3 strong buys
    top3 = [s for s in all_value if s["signal"] in ("STRONG_BUY", "BUY")][:3]
    narrative = None
    if top3:
        lines = []
        for s in top3:
            lines.append(
                f"{s['ticker']} ({s['company_name']}): entry_score={s['entry_score']}, "
                f"señales={', '.join(s['signals_fired'][:4])}"
            )
        narrative = ai(
            "Analiza estas 3 mejores oportunidades de entrada de hoy (VALUE investing):\n"
            + "\n".join(lines)
            + "\n\nEn 3 frases en español: por qué estas son las mejores entradas de hoy "
            "y qué confirma la señal.", 200
        )

    counts = {k: sum(1 for s in all_value if s["signal"] == k)
              for k in ("STRONG_BUY", "BUY", "MONITOR", "WAIT")}

    result = dict(
        generated_at=TODAY,
        total=len(all_value),
        strong_buy=counts["STRONG_BUY"],
        buy=counts["BUY"],
        monitor=counts["MONITOR"],
        wait=counts["WAIT"],
        narrative=narrative,
        signals=all_value,
    )
    print(f"  ✓ {counts['STRONG_BUY']} STRONG BUY · {counts['BUY']} BUY · {counts['MONITOR']} MONITOR")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 7. EXIT MONITOR — cuándo salir de una posición
# ══════════════════════════════════════════════════════════════════════════════

def scan_exit_signals() -> dict:
    """
    Reviews recent VALUE signals (last 60 days) from portfolio_tracker.
    Flags positions where the thesis may have broken:
      - Score dropped ≥15pts vs entry
      - Earnings warning active
      - Ticker no longer in VALUE list (score=0 or absent)
      - Insider reversal (was buying, now absent)
    """
    print("[7/13] Exit signal scan...")
    pt       = load_csv(DOCS / "portfolio_tracker" / "recommendations.csv")
    value_df = load_csv(DOCS / "value_opportunities.csv")
    eu_df    = load_csv(DOCS / "european_value_opportunities.csv")
    insiders = load_csv(DOCS / "recurring_insiders.csv")

    all_value = pd.concat([value_df, eu_df], ignore_index=True) if not value_df.empty else eu_df
    current   = {}
    if not all_value.empty and "ticker" in all_value.columns:
        for _, row in all_value.iterrows():
            t = str(row.get("ticker","")).upper()
            current[t] = {
                "value_score":     sf(row.get("value_score")),
                "earnings_warning": bool(row.get("earnings_warning", False)),
                "days_to_earnings": sf(row.get("days_to_earnings")),
            }

    insider_active = set()
    if not insiders.empty and "ticker" in insiders.columns:
        insider_active = set(insiders["ticker"].str.upper().dropna())

    exits = []
    if pt.empty or "ticker" not in pt.columns:
        return dict(generated_at=TODAY, total=0, high_count=0, exits=[])

    # Only look at recent signals (last 60 days) without a return yet (still open)
    pt["signal_date"] = pd.to_datetime(pt.get("signal_date", pd.NaT), errors="coerce")
    cutoff = pd.Timestamp.today() - pd.Timedelta(days=60)
    recent = pt[pt["signal_date"] >= cutoff] if "signal_date" in pt.columns else pt

    # Deduplicate by ticker — use highest-scored entry
    seen = {}
    for _, row in recent.iterrows():
        t   = str(row.get("ticker","")).upper()
        vs  = sf(row.get("value_score")) or 0
        if t not in seen or vs > seen[t]["entry_score"]:
            seen[t] = {"entry_score": vs, "signal_date": str(row.get("signal_date",""))}

    for ticker, meta in seen.items():
        reasons  = []
        severity = "LOW"
        curr     = current.get(ticker, {})
        curr_score = curr.get("value_score")
        entry_score = meta["entry_score"]

        # 1. Ticker no longer in VALUE list
        if ticker not in current:
            reasons.append("Ya no aparece en VALUE — tesis posiblemente rota")
            severity = "HIGH"

        # 2. Score dropped significantly
        elif curr_score is not None and entry_score and (entry_score - curr_score) >= 15:
            drop = entry_score - curr_score
            reasons.append(f"Score cayó {drop:.0f}pts ({entry_score:.0f} → {curr_score:.0f})")
            severity = "HIGH" if drop >= 25 else "MEDIUM"

        # 3. Earnings warning
        if curr.get("earnings_warning") and curr.get("days_to_earnings") is not None:
            dte = curr["days_to_earnings"]
            if dte <= 7:
                reasons.append(f"Earnings en {int(dte)}d — alta incertidumbre, considera reducir")
                if severity == "LOW": severity = "MEDIUM"

        # 4. Insider buying stopped (was bought before, no longer active)
        if ticker not in insider_active and entry_score and entry_score > 65:
            reasons.append("Sin insider buying activo — señal de convicción perdida")
            if severity == "LOW": severity = "LOW"

        if reasons:
            exits.append(dict(
                ticker=ticker,
                severity=severity,
                entry_score=entry_score,
                current_score=curr_score,
                signal_date=meta["signal_date"][:10] if meta["signal_date"] else None,
                reasons=reasons,
            ))

    exits.sort(key=lambda x: ({"HIGH":0,"MEDIUM":1,"LOW":2}.get(x["severity"],3), -(x["entry_score"] or 0)))
    high_count = sum(1 for e in exits if e["severity"] == "HIGH")

    narrative = ai(
        f"Monitor de salida VALUE: {len(exits)} posiciones con señales de revisión ({high_count} HIGH).\n"
        + "\n".join(f"- {e['ticker']}: {'; '.join(e['reasons'][:2])}" for e in exits[:5])
        + "\n\n2 frases en español: qué implica esto para gestión de riesgo.", 150
    ) if exits else None

    print(f"  ✓ {len(exits)} señales de salida ({high_count} HIGH)")
    return dict(generated_at=TODAY, total=len(exits), high_count=high_count, narrative=narrative, exits=exits)


# ══════════════════════════════════════════════════════════════════════════════
# 8. VALUE TRAP DETECTOR — identifica trampas de valor
# ══════════════════════════════════════════════════════════════════════════════

def scan_value_traps() -> dict:
    """
    Scans VALUE tickers for trap indicators:
      Piotroski ≤ 3, FCF negative, debt rising vs margins falling,
      near-default fundamental score, no analyst coverage
    Trap score: 0-10 (HIGH ≥6, MEDIUM 3-5)
    """
    print("[8/13] Value trap scan...")
    value_df  = load_csv(DOCS / "value_opportunities.csv")
    eu_df     = load_csv(DOCS / "european_value_opportunities.csv")
    fund_df   = load_csv(DOCS / "fundamental_scores.csv")

    all_value = pd.concat([value_df, eu_df], ignore_index=True) if not value_df.empty else eu_df
    if all_value.empty:
        return dict(generated_at=TODAY, total=0, high_count=0, traps=[])

    fund_map = {}
    if not fund_df.empty and "ticker" in fund_df.columns:
        for _, row in fund_df.iterrows():
            t = str(row.get("ticker","")).upper()
            fund_map[t] = row

    traps = []
    for _, row in all_value.iterrows():
        t      = str(row.get("ticker","")).upper()
        vscore = sf(row.get("value_score")) or 0
        fcf    = sf(row.get("fcf_yield_pct"))
        piotr  = sf(row.get("piotroski_score"))
        an_cnt = sf(row.get("analyst_count"))
        an_rec = str(row.get("analyst_recommendation","")).lower()
        fund_s = sf(row.get("fundamental_score"))
        debt   = sf(row.get("debt_to_equity"))
        op_mar = sf(row.get("operating_margin_pct"))
        company= str(row.get("company_name", t))

        trap_score = 0
        flags = []

        # Piotroski weak (deteriorating quality)
        if piotr is not None:
            if piotr <= 2:
                trap_score += 4; flags.append(f"Piotroski muy débil ({piotr:.0f}/9) — calidad financiera en deterioro")
            elif piotr <= 4:
                trap_score += 2; flags.append(f"Piotroski débil ({piotr:.0f}/9)")

        # Negative FCF (burning cash despite "cheap" valuation)
        if fcf is not None and fcf < 0:
            trap_score += 3; flags.append(f"FCF negativo ({fcf:.1f}%) — quema caja pese a valuación barata")

        # Near-default fundamental score (missing/unreliable data)
        if fund_s is not None and 48 <= fund_s <= 53:
            trap_score += 2; flags.append("Fundamental score cerca de default (50) — datos poco fiables")

        # No analyst coverage with high score (unverified thesis)
        if (an_cnt is None or an_cnt < 2) and vscore > 65:
            trap_score += 2; flags.append("Sin cobertura de analistas — tesis sin verificar externamente")

        # Analysts recommend hold/sell despite high score
        if an_rec in ("hold", "sell") and vscore > 65:
            trap_score += 2; flags.append(f"Analistas recomiendan '{an_rec}' pese a score alto")

        # High debt + low/negative margins (structural weakness)
        if debt is not None and op_mar is not None:
            if debt > 2.0 and op_mar < 5:
                trap_score += 2; flags.append(f"Deuda alta ({debt:.1f}x) + margen operativo bajo ({op_mar:.1f}%)")

        if trap_score < 3 or not flags:
            continue

        level = "HIGH" if trap_score >= 6 else "MEDIUM"
        traps.append(dict(
            ticker=ticker if (ticker := t) else t,
            company_name=company,
            severity=level,
            trap_score=trap_score,
            value_score=vscore,
            flags=flags,
            piotroski=piotr,
            fcf_yield_pct=fcf,
            fundamental_score=fund_s,
        ))

    traps.sort(key=lambda x: (-x["trap_score"], -x["value_score"]))
    high_count = sum(1 for t in traps if t["severity"] == "HIGH")

    narrative = ai(
        f"Trampas de valor detectadas: {len(traps)} tickers con señales de trampa ({high_count} HIGH).\n"
        + "\n".join(f"- {t['ticker']}: {'; '.join(t['flags'][:2])}" for t in traps[:5])
        + "\n\n2 frases en español: por qué estos tickers podrían ser value traps.", 150
    ) if traps else None

    print(f"  ✓ {len(traps)} value traps ({high_count} HIGH)")
    return dict(generated_at=TODAY, total=len(traps), high_count=high_count, narrative=narrative, traps=traps)


# ══════════════════════════════════════════════════════════════════════════════
# 9. SMART MONEY CONVERGENCE — hedge funds + insiders compran lo mismo
# ══════════════════════════════════════════════════════════════════════════════

def scan_smart_money() -> dict:
    """
    Finds tickers where hedge funds (13F) AND insiders are buying simultaneously.
    Smart money convergence = maximum conviction signal.
    """
    print("[9/13] Smart money scan...")
    hf_df    = load_csv(DOCS / "hedge_fund_holdings.csv")
    ins_df   = load_csv(DOCS / "recurring_insiders.csv")
    eu_ins   = load_csv(DOCS / "eu_recurring_insiders.csv")
    value_df = load_csv(DOCS / "value_opportunities.csv")
    eu_df    = load_csv(DOCS / "european_value_opportunities.csv")

    all_value = pd.concat([value_df, eu_df], ignore_index=True) if not value_df.empty else eu_df
    value_map = {}
    if not all_value.empty and "ticker" in all_value.columns:
        for _, row in all_value.iterrows():
            t = str(row.get("ticker","")).upper()
            value_map[t] = {"value_score": sf(row.get("value_score")), "company_name": str(row.get("company_name", t)), "sector": str(row.get("sector",""))}

    # Build hedge fund map: ticker → {funds, count}
    hf_map = {}
    if not hf_df.empty:
        ticker_col = next((c for c in ["ticker","stock","symbol"] if c in hf_df.columns), None)
        fund_col   = next((c for c in ["fund","fund_name","manager"] if c in hf_df.columns), None)
        if ticker_col:
            for _, row in hf_df.iterrows():
                t = str(row.get(ticker_col,"")).upper()
                if not t: continue
                if t not in hf_map:
                    hf_map[t] = {"funds": set(), "count": 0}
                hf_map[t]["count"] += 1
                if fund_col:
                    hf_map[t]["funds"].add(str(row.get(fund_col,"")))

    # Build insider map
    all_ins = pd.concat([ins_df, eu_ins], ignore_index=True) if not ins_df.empty else eu_ins
    ins_map = {}
    if not all_ins.empty and "ticker" in all_ins.columns:
        for _, row in all_ins.iterrows():
            t = str(row.get("ticker","")).upper()
            ins_map[t] = {"purchase_count": sf(row.get("purchase_count")) or 1, "unique_insiders": sf(row.get("unique_insiders")) or 1}

    # Convergence: must be in BOTH
    results = []
    for ticker in set(hf_map.keys()) & set(ins_map.keys()):
        hf   = hf_map[ticker]
        ins  = ins_map[ticker]
        meta = value_map.get(ticker, {})
        n_funds   = len(hf["funds"]) if hf["funds"] else hf["count"]
        n_ins     = int(ins["unique_insiders"] or 1)
        conv_score = min(100, n_funds * 15 + n_ins * 10 + (meta.get("value_score") or 0) * 0.3)
        results.append(dict(
            ticker=ticker,
            company_name=meta.get("company_name", ticker),
            sector=meta.get("sector",""),
            value_score=meta.get("value_score"),
            n_hedge_funds=n_funds,
            hedge_funds=list(hf["funds"])[:5],
            n_insiders=n_ins,
            insider_purchases=int(ins["purchase_count"] or 1),
            convergence_score=round(conv_score),
            in_value=ticker in value_map,
        ))

    results.sort(key=lambda x: -x["convergence_score"])

    narrative = ai(
        f"Smart money convergence: {len(results)} tickers donde hedge funds e insiders compran simultáneamente.\n"
        + "\n".join(f"- {r['ticker']}: {r['n_hedge_funds']} HF + {r['n_insiders']} insiders, score {r['convergence_score']}" for r in results[:5])
        + "\n\n2 frases en español: qué significa esta confluencia de capital inteligente.", 150
    ) if results else None

    print(f"  ✓ {len(results)} smart money convergences")
    return dict(generated_at=TODAY, total=len(results), narrative=narrative, signals=results)


# ══════════════════════════════════════════════════════════════════════════════
# 10. INSIDER SECTOR CLUSTERS — señal a nivel sector
# ══════════════════════════════════════════════════════════════════════════════

def scan_insider_clusters() -> dict:
    """
    Detects when insiders from 3+ DIFFERENT companies in the same sector
    are buying simultaneously — sector-level intelligence signal.
    """
    print("[10/13] Insider sector clustering...")
    ins_df   = load_csv(DOCS / "recurring_insiders.csv")
    eu_ins   = load_csv(DOCS / "eu_recurring_insiders.csv")
    value_df = load_csv(DOCS / "value_opportunities.csv")
    eu_df    = load_csv(DOCS / "european_value_opportunities.csv")

    all_ins   = pd.concat([ins_df, eu_ins], ignore_index=True) if not ins_df.empty else eu_ins
    all_value = pd.concat([value_df, eu_df], ignore_index=True) if not value_df.empty else eu_df

    sector_map = {}
    if not all_value.empty and "ticker" in all_value.columns:
        for _, row in all_value.iterrows():
            t = str(row.get("ticker","")).upper()
            s = str(row.get("sector","Unknown"))
            sector_map[t] = s

    if all_ins.empty or "ticker" not in all_ins.columns:
        return dict(generated_at=TODAY, total=0, clusters=[])

    # Group insiders by sector
    from collections import defaultdict
    sector_tickers = defaultdict(list)
    for _, row in all_ins.iterrows():
        t = str(row.get("ticker","")).upper()
        sec = sector_map.get(t, "Unknown")
        if sec and sec != "Unknown":
            sector_tickers[sec].append({
                "ticker": t,
                "purchase_count": int(sf(row.get("purchase_count")) or 1),
                "unique_insiders": int(sf(row.get("unique_insiders")) or 1),
            })

    clusters = []
    for sector, tickers in sector_tickers.items():
        if len(tickers) < 3:
            continue
        total_purchases = sum(t["purchase_count"] for t in tickers)
        total_insiders  = sum(t["unique_insiders"] for t in tickers)
        cluster_score   = min(100, len(tickers) * 20 + total_purchases * 2)
        clusters.append(dict(
            sector=sector,
            ticker_count=len(tickers),
            tickers=[t["ticker"] for t in tickers],
            total_purchases=total_purchases,
            total_insiders=total_insiders,
            cluster_score=cluster_score,
            signal="STRONG" if len(tickers) >= 5 else "MODERATE",
        ))

    clusters.sort(key=lambda x: -x["cluster_score"])

    narrative = ai(
        f"Clusters sectoriales de insiders: {len(clusters)} sectores con compras coordinadas.\n"
        + "\n".join(f"- {c['sector']}: {c['ticker_count']} empresas, {c['total_purchases']} compras" for c in clusters[:4])
        + "\n\n2 frases en español: qué implica cuando muchos directivos del mismo sector compran.", 150
    ) if clusters else None

    print(f"  ✓ {len(clusters)} sector clusters")
    return dict(generated_at=TODAY, total=len(clusters), narrative=narrative, clusters=clusters)


# ══════════════════════════════════════════════════════════════════════════════
# 11. DIVIDEND SAFETY MONITOR — vigila la seguridad del dividendo
# ══════════════════════════════════════════════════════════════════════════════

def scan_dividend_safety() -> dict:
    """
    For dividend-paying tickers in VALUE lists, assesses dividend sustainability.
    AT RISK: payout_ratio >80% OR FCF negative with dividend
    SAFE: payout_ratio <50% AND FCF covers dividend well
    """
    print("[11/13] Dividend safety scan...")
    value_df = load_csv(DOCS / "value_opportunities.csv")
    eu_df    = load_csv(DOCS / "european_value_opportunities.csv")

    all_value = pd.concat([value_df, eu_df], ignore_index=True) if not value_df.empty else eu_df
    if all_value.empty:
        return dict(generated_at=TODAY, total=0, at_risk=0, dividends=[])

    dividends = []
    for _, row in all_value.iterrows():
        div_yield = sf(row.get("dividend_yield_pct"))
        if div_yield is None or div_yield <= 0:
            continue

        t       = str(row.get("ticker","")).upper()
        company = str(row.get("company_name", t))
        payout  = sf(row.get("payout_ratio_pct"))
        fcf     = sf(row.get("fcf_yield_pct"))
        int_cov = sf(row.get("interest_coverage"))
        vscore  = sf(row.get("value_score")) or 0

        risk_flags = []
        safety_score = 100  # start safe, subtract for risks

        if payout is not None:
            if payout > 90:
                risk_flags.append(f"Payout {payout:.0f}% — insostenible"); safety_score -= 40
            elif payout > 75:
                risk_flags.append(f"Payout {payout:.0f}% — zona de riesgo"); safety_score -= 20
            elif payout < 50:
                safety_score += 10  # bonus for conservative payout

        if fcf is not None:
            if fcf < 0:
                risk_flags.append("FCF negativo — dividendo no cubierto por caja"); safety_score -= 35
            elif fcf < div_yield:
                risk_flags.append(f"FCF ({fcf:.1f}%) < dividendo ({div_yield:.1f}%) — cobertura ajustada"); safety_score -= 15

        if int_cov is not None and int_cov < 2:
            risk_flags.append(f"Interest coverage {int_cov:.1f}x — deuda consume caja"); safety_score -= 15

        safety_score = max(0, min(100, safety_score))
        rating = "AT_RISK" if safety_score < 40 else "WATCH" if safety_score < 65 else "SAFE"

        dividends.append(dict(
            ticker=t,
            company_name=company,
            div_yield=div_yield,
            payout_ratio=payout,
            fcf_yield_pct=fcf,
            interest_coverage=int_cov,
            safety_score=safety_score,
            rating=rating,
            risk_flags=risk_flags,
            value_score=vscore,
        ))

    dividends.sort(key=lambda x: x["safety_score"])
    at_risk = sum(1 for d in dividends if d["rating"] == "AT_RISK")

    narrative = ai(
        f"Monitor de dividendos: {len(dividends)} tickers con dividendo en VALUE. {at_risk} en riesgo.\n"
        + "\n".join(f"- {d['ticker']} ({d['div_yield']:.1f}% yield): {'; '.join(d['risk_flags'][:2]) if d['risk_flags'] else 'SAFE'}" for d in dividends[:5])
        + "\n\n2 frases en español: cómo interpretar la seguridad de dividendos en VALUE investing.", 150
    ) if dividends else None

    print(f"  ✓ {len(dividends)} dividendos analizados ({at_risk} AT RISK)")
    return dict(generated_at=TODAY, total=len(dividends), at_risk=at_risk, narrative=narrative, dividends=dividends)


# ══════════════════════════════════════════════════════════════════════════════
# 12. PIOTROSKI MOMENTUM — mejora de calidad financiera
# ══════════════════════════════════════════════════════════════════════════════

def scan_piotroski_momentum() -> dict:
    """
    Identifies VALUE tickers with improving Piotroski F-scores.
    A company going from 4→7 is more interesting than one stuck at 7.
    Uses history folder to compare vs previous scores.
    """
    print("[12/13] Piotroski momentum scan...")
    value_df = load_csv(DOCS / "value_opportunities.csv")
    eu_df    = load_csv(DOCS / "european_value_opportunities.csv")
    all_value = pd.concat([value_df, eu_df], ignore_index=True) if not value_df.empty else eu_df

    if all_value.empty or "piotroski_score" not in all_value.columns:
        return dict(generated_at=TODAY, total=0, improving=0, candidates=[])

    # Load previous scores from history
    history_dir = DOCS / "history"
    prev_scores = {}
    if history_dir.exists():
        past_dates = sorted([d for d in history_dir.iterdir() if d.is_dir()], reverse=True)
        # Look back up to 14 days for previous scores
        for past_dir in past_dates[1:8]:  # skip today, check last 7 snapshots
            for fname in ["value_opportunities.csv", "european_value_opportunities.csv"]:
                fpath = past_dir / fname
                if fpath.exists():
                    try:
                        old = pd.read_csv(fpath)
                        if "piotroski_score" in old.columns and "ticker" in old.columns:
                            for _, row in old.iterrows():
                                t = str(row.get("ticker","")).upper()
                                ps = sf(row.get("piotroski_score"))
                                if t not in prev_scores and ps is not None:
                                    prev_scores[t] = ps
                    except Exception:
                        pass

    candidates = []
    for _, row in all_value.iterrows():
        t      = str(row.get("ticker","")).upper()
        curr_p = sf(row.get("piotroski_score"))
        if curr_p is None: continue

        vscore  = sf(row.get("value_score")) or 0
        company = str(row.get("company_name", t))
        prev_p  = prev_scores.get(t)

        trend = "STABLE"
        delta = 0
        if prev_p is not None:
            delta = curr_p - prev_p
            if delta >= 2: trend = "IMPROVING"
            elif delta >= 1: trend = "SLIGHT_UP"
            elif delta <= -2: trend = "DETERIORATING"
            elif delta <= -1: trend = "SLIGHT_DOWN"

        signal = "STRONG" if curr_p >= 7 else "WEAK" if curr_p <= 3 else "NEUTRAL"

        if signal == "NEUTRAL" and trend == "STABLE":
            continue  # skip unremarkable

        candidates.append(dict(
            ticker=t,
            company_name=company,
            piotroski_current=curr_p,
            piotroski_prev=prev_p,
            delta=delta,
            trend=trend,
            signal=signal,
            value_score=vscore,
        ))

    candidates.sort(key=lambda x: (
        {"IMPROVING": 0, "SLIGHT_UP": 1, "STRONG": 2, "NEUTRAL": 3, "SLIGHT_DOWN": 4, "DETERIORATING": 5}.get(x["trend"], 3),
        -x["piotroski_current"]
    ))

    improving = sum(1 for c in candidates if c["trend"] in ("IMPROVING", "SLIGHT_UP"))

    narrative = ai(
        f"Piotroski momentum en VALUE: {improving} tickers con mejora de calidad financiera.\n"
        + "\n".join(f"- {c['ticker']}: F-score {c['piotroski_prev'] or '?'} → {c['piotroski_current']} ({c['trend']})" for c in candidates[:5])
        + "\n\n2 frases en español: por qué la mejora de Piotroski señala un posible re-rating.", 150
    ) if candidates else None

    print(f"  ✓ {len(candidates)} tickers Piotroski analizados ({improving} mejorando)")
    return dict(generated_at=TODAY, total=len(candidates), improving=improving, narrative=narrative, candidates=candidates)


# ══════════════════════════════════════════════════════════════════════════════
# 13. PORTFOLIO STRESS TEST — concentración y riesgo oculto
# ══════════════════════════════════════════════════════════════════════════════

def scan_portfolio_stress() -> dict:
    """
    Analyzes recent VALUE signals for hidden concentration risks:
      - Sector concentration (>40% in one sector)
      - Rate sensitivity (utilities/REITs/financials)
      - Earnings risk (% with earnings_warning)
      - Geographic spread (US vs EU)
    """
    print("[13/13] Portfolio stress test...")
    pt       = load_csv(DOCS / "portfolio_tracker" / "recommendations.csv")
    value_df = load_csv(DOCS / "value_opportunities.csv")
    eu_df    = load_csv(DOCS / "european_value_opportunities.csv")

    all_value = pd.concat([value_df, eu_df], ignore_index=True) if not value_df.empty else eu_df
    value_meta = {}
    if not all_value.empty and "ticker" in all_value.columns:
        for _, row in all_value.iterrows():
            t = str(row.get("ticker","")).upper()
            value_meta[t] = {
                "sector": str(row.get("sector","")),
                "earnings_warning": bool(row.get("earnings_warning", False)),
                "region": "EU" if row.get("exchange","").endswith(".L") or row.get("exchange","").endswith(".MC") else "US",
                "value_score": sf(row.get("value_score")) or 0,
            }

    if pt.empty or "ticker" not in pt.columns:
        return dict(generated_at=TODAY, risks=[], narrative=None)

    pt["signal_date"] = pd.to_datetime(pt.get("signal_date", pd.NaT), errors="coerce")
    cutoff = pd.Timestamp.today() - pd.Timedelta(days=60)
    recent = pt[pt["signal_date"] >= cutoff] if "signal_date" in pt.columns else pt.head(50)
    recent_tickers = list(set(recent["ticker"].str.upper().dropna()))

    if not recent_tickers:
        return dict(generated_at=TODAY, risks=[], narrative=None)

    from collections import Counter
    sectors      = Counter()
    regions      = Counter()
    earn_risk    = 0
    rate_sectors = {"Utilities", "Real Estate", "Financial Services", "Financials"}
    rate_exposed = 0

    for t in recent_tickers:
        meta = value_meta.get(t, {})
        sec  = meta.get("sector","Unknown")
        sectors[sec] += 1
        regions[meta.get("region","US")] += 1
        if meta.get("earnings_warning"): earn_risk += 1
        if any(rs.lower() in sec.lower() for rs in rate_sectors): rate_exposed += 1

    total = len(recent_tickers)
    risks = []

    # Sector concentration
    top_sector, top_count = sectors.most_common(1)[0] if sectors else ("", 0)
    if total > 0 and top_count / total > 0.35:
        pct = top_count / total * 100
        risks.append(dict(type="SECTOR_CONCENTRATION", severity="HIGH" if pct > 50 else "MEDIUM",
            message=f"{pct:.0f}% de señales en {top_sector} ({top_count}/{total}) — concentración elevada",
            detail=dict(sector=top_sector, count=top_count, pct=round(pct))))

    # Earnings risk
    if total > 0 and earn_risk / total > 0.25:
        pct = earn_risk / total * 100
        risks.append(dict(type="EARNINGS_RISK", severity="MEDIUM",
            message=f"{earn_risk} de {total} posiciones con earnings próximos — {pct:.0f}% expuesto",
            detail=dict(count=earn_risk, pct=round(pct))))

    # Rate sensitivity
    if total > 0 and rate_exposed / total > 0.30:
        pct = rate_exposed / total * 100
        risks.append(dict(type="RATE_SENSITIVITY", severity="MEDIUM",
            message=f"{pct:.0f}% expuesto a sectores sensibles a tipos de interés",
            detail=dict(count=rate_exposed, pct=round(pct))))

    # Geographic concentration
    us_pct = regions.get("US",0) / total * 100 if total else 0
    if us_pct > 85:
        risks.append(dict(type="GEO_CONCENTRATION", severity="LOW",
            message=f"{us_pct:.0f}% en mercado US — poca diversificación geográfica",
            detail=dict(us=regions.get("US",0), eu=regions.get("EU",0))))

    narrative = ai(
        f"Stress test portfolio ({total} señales recientes): {len(risks)} riesgos detectados.\n"
        + "\n".join(f"- {r['type']}: {r['message']}" for r in risks)
        + "\n\n2 frases en español: cómo mitigar estos riesgos de concentración.", 150
    ) if risks else None

    sector_breakdown = [{"sector": s, "count": c, "pct": round(c/total*100)} for s,c in sectors.most_common(8)] if total else []

    print(f"  ✓ Stress test: {len(risks)} riesgos · {total} posiciones analizadas")
    return dict(generated_at=TODAY, total_positions=total, risks=risks, narrative=narrative,
                sector_breakdown=sector_breakdown, region_breakdown=dict(regions))


# ══════════════════════════════════════════════════════════════════════════════
# 14. PERSONAL BRIEFING — resumen diario inteligente
# ══════════════════════════════════════════════════════════════════════════════

def generate_personal_briefing(entry_sigs: dict, convergence: dict, alerts: dict,
                                 value_traps: dict, exit_sigs: dict, smart_money: dict) -> dict:
    """
    Generates a daily AI briefing combining all Cerebro outputs into
    an actionable morning summary.
    """
    print("[14/14] Generating personal briefing...")
    regime_json = load_json(DOCS / "market_regime.json")
    us_regime   = str(regime_json.get("us", {}).get("regime","NEUTRAL")).upper()

    strong_buy = [s for s in entry_sigs.get("signals",[]) if s["signal"] == "STRONG_BUY"]
    buys       = [s for s in entry_sigs.get("signals",[]) if s["signal"] == "BUY"][:3]
    high_alerts= [a for a in alerts.get("alerts",[]) if a["severity"] == "HIGH"][:3]
    top_conv   = convergence.get("convergences",[])[:3]
    traps_high = [t for t in value_traps.get("traps",[]) if t["severity"] == "HIGH"][:3]
    exits_high = [e for e in exit_sigs.get("exits",[]) if e["severity"] == "HIGH"][:3]
    smart_top  = smart_money.get("signals",[])[:3]

    sections = {
        "regime": us_regime,
        "strong_buy_count": len(strong_buy),
        "buy_count":        len(buys),
        "top_entries":      [(s["ticker"], s["entry_score"]) for s in (strong_buy + buys)[:5]],
        "top_convergences": [(s["ticker"], s["convergence_score"]) for s in top_conv],
        "high_alerts":      [(a["ticker"], a["type"]) for a in high_alerts],
        "traps_warning":    [(t["ticker"], t["trap_score"]) for t in traps_high],
        "exit_warnings":    [(e["ticker"], "; ".join(e["reasons"][:1])) for e in exits_high],
        "smart_money":      [(s["ticker"], s["n_hedge_funds"]) for s in smart_top],
    }

    # Build narrative prompt
    prompt = f"""Briefing diario VALUE investing — {TODAY}
Régimen de mercado: {us_regime}

ENTRADAS: {len(strong_buy)} STRONG BUY + {len(buys)} BUY
{chr(10).join(f"  {t[0]}: score {t[1]}" for t in sections['top_entries'][:3])}

CONVERGENCIAS (multi-estrategia): {', '.join(t[0] for t in sections['top_convergences']) or 'ninguna'}

ALERTAS HIGH: {', '.join(f"{t[0]}({t[1]})" for t in sections['high_alerts']) or 'ninguna'}

TRAMPAS DETECTADAS: {', '.join(t[0] for t in sections['traps_warning']) or 'ninguna'}

SEÑALES DE SALIDA: {', '.join(f"{t[0]}: {t[1]}" for t in sections['exit_warnings']) or 'ninguna'}

SMART MONEY: {', '.join(f"{t[0]}({t[1]} HF)" for t in sections['smart_money']) or 'ningún cruce HF+insiders'}

Redacta un briefing matutino en español (máx 5 frases) como si fuera un analista de confianza:
qué hacer hoy, qué vigilar, qué evitar. Sé directo y conciso."""

    narrative = ai(prompt, 300) or (
        f"Régimen {us_regime}. "
        f"{len(strong_buy)+len(buys)} oportunidades de entrada, "
        f"{len(exits_high)} señales de salida HIGH. "
        f"{'Precaución: ' + str(len(traps_high)) + ' value traps detectadas.' if traps_high else 'Sin trampas de valor relevantes.'}"
    )

    print(f"  ✓ Briefing generado — {len(strong_buy)} STRONG BUY · {len(exits_high)} salidas HIGH")
    return dict(
        generated_at=TODAY,
        regime=us_regime,
        narrative=narrative,
        sections=sections,
    )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print(f"CEREBRO  ·  {TODAY}")
    print("=" * 60)
    if not groq_client:
        print("⚠  No GROQ_API_KEY — rule-based mode (no AI narratives)")

    # Original 6 modules
    insights    = mine_patterns()
    convergence = scan_convergence()
    alerts      = generate_alerts(convergence)
    calibration = self_calibrate(insights)
    tuning      = auto_tune(insights, calibration)
    entry_sigs  = scan_entry_signals(convergence)

    # New agent modules
    exit_sigs   = scan_exit_signals()
    value_traps = scan_value_traps()
    smart_money = scan_smart_money()
    ins_clusters= scan_insider_clusters()
    div_safety  = scan_dividend_safety()
    piotroski   = scan_piotroski_momentum()
    stress      = scan_portfolio_stress()
    briefing    = generate_personal_briefing(entry_sigs, convergence, alerts, value_traps, exit_sigs, smart_money)

    save_json(DOCS / "cerebro_insights.json",           insights)
    save_json(DOCS / "cerebro_convergence.json",         convergence)
    save_json(DOCS / "cerebro_alerts.json",              alerts)
    save_json(DOCS / "cerebro_calibration.json",         calibration)
    save_json(DOCS / "cerebro_entry_signals.json",       entry_sigs)
    save_json(DOCS / "scoring_weights_suggested.json",   tuning)
    save_json(DOCS / "cerebro_exit_signals.json",        exit_sigs)
    save_json(DOCS / "cerebro_value_traps.json",         value_traps)
    save_json(DOCS / "cerebro_smart_money.json",         smart_money)
    save_json(DOCS / "cerebro_insider_clusters.json",    ins_clusters)
    save_json(DOCS / "cerebro_dividend_safety.json",     div_safety)
    save_json(DOCS / "cerebro_piotroski.json",           piotroski)
    save_json(DOCS / "cerebro_stress_test.json",         stress)
    save_json(DOCS / "cerebro_briefing.json",            briefing)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print(f"  Signals analyzed : {insights.get('total_analyzed',0)} · baseline WR {insights.get('baseline_win_rate_7d',0):.1f}%")
    print(f"  Convergences     : {convergence.get('total_convergences',0)} ({convergence.get('triple_or_more',0)} triple+)")
    print(f"  Alerts           : {alerts.get('total',0)} ({alerts.get('high_count',0)} HIGH)")
    print(f"  Entry signals    : {entry_sigs.get('strong_buy',0)} STRONG BUY · {entry_sigs.get('buy',0)} BUY")
    print(f"  Exit signals     : {exit_sigs.get('total',0)} ({exit_sigs.get('high_count',0)} HIGH)")
    print(f"  Value traps      : {value_traps.get('total',0)} ({value_traps.get('high_count',0)} HIGH)")
    print(f"  Smart money      : {smart_money.get('total',0)} HF+insider convergences")
    print(f"  Sector clusters  : {ins_clusters.get('total',0)} clusters")
    print(f"  Dividends at risk: {div_safety.get('at_risk',0)} / {div_safety.get('total',0)}")
    print(f"  Piotroski impr.  : {piotroski.get('improving',0)} / {piotroski.get('total',0)}")
    print(f"  Stress risks     : {len(stress.get('risks',[]))}")
    print(f"  Calibration recs : {calibration.get('total_recommendations',0)}")
    print(f"  Weight proposals : {len(tuning.get('adjustments',[]))}")
    print("=" * 60)

if __name__ == "__main__":
    main()
