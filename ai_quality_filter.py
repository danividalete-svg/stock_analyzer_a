#!/usr/bin/env python3
"""
AI-powered quality filter for VALUE + MOMENTUM opportunities
Uses Groq (free) to analyze fundamentals and reject low-quality opportunities
BONUS: Insider buying + Institutional ownership increase confidence
"""
import pandas as pd
import numpy as np
from pathlib import Path
import json
import os
from groq import Groq

# Groq API (free tier) - must be set in environment
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

def analyze_with_ai(ticker_data: dict, strategy: str = "VALUE") -> dict:
    """
    Use Groq AI (llama-3.3-70b) to analyze opportunity quality
    Fallback to rule-based if AI fails
    Args:
        ticker_data: Stock data dict
        strategy: "VALUE" or "MOMENTUM"
    Returns: {verdict: BUY/HOLD/AVOID, confidence: 0-100, reasoning: str}
    """
    try:
        client = Groq(api_key=GROQ_API_KEY)

        # Build strategy-specific prompt
        if strategy == "MOMENTUM":
            prompt = f"""Analyze this MOMENTUM stock (Minervini-style) for safety and quality.

{ticker_data['ticker']} - {ticker_data['sector']} - ${ticker_data['current_price']:.2f}

MOMENTUM METRICS:
Proximity to 52w high: {ticker_data.get('proximity_to_52w_high', 'N/A')}x
RS line at new high: {ticker_data.get('rs_line_at_new_high', 'N/A')} (CRITICAL Minervini rule)
Earnings accelerating: {ticker_data.get('eps_accelerating', 'N/A')}
Revenue accelerating: {ticker_data.get('rev_accelerating', 'N/A')}
Industry strength: {ticker_data.get('industry_group_percentile', 'N/A')}%
Short %: {ticker_data.get('short_percent_float', 'N/A')}%

SMART MONEY VALIDATION:
Options flow: {ticker_data.get('flow_score', 'N/A')}/100
Unusual calls: {ticker_data.get('unusual_calls', 'N/A')}
Whales buying: {ticker_data.get('num_whales', 'N/A')}
Market regime: {ticker_data.get('market_regime', 'N/A')}

FUNDAMENTALS (safety check):
ROE: {ticker_data.get('roe', 'N/A')}%
Margin: {ticker_data.get('profit_margin', 'N/A')}%
Growth: {ticker_data.get('rev_growth', 'N/A')}%

CRITICAL SAFETY CHECKS:
1. RS line at new high? (Minervini won't buy without this)
2. Not over-extended? (proximity < 1.15 = safe, >1.25 = danger)
3. Earnings accelerating? (TRUE = sustainable momentum)
4. Industry strong? (>70% = sector tailwind)
5. Smart money buying? (whales, options flow positive)
6. Market regime? (bear market = higher risk)
7. Fundamentals positive? (ROE>0, Margin>0)

Respond ONLY with JSON:
{{"verdict": "BUY"|"HOLD"|"AVOID", "confidence": 0-100, "reasoning": "brief explanation"}}"""
        elif strategy == "SHORT":
            prompt = f"""You are a short-seller analyst. Validate this bearish opportunity.

{ticker_data['ticker']} - {ticker_data.get('sector','?')} - ${ticker_data.get('current_price', 0):.2f}

SHORT THESIS SCORE: {ticker_data.get('short_score', 'N/A')}/100
Quality: {ticker_data.get('short_quality', 'N/A')}

TECHNICAL BREAKDOWN (bearish signals):
Weinstein Stage: {ticker_data.get('weinstein_stage', 'N/A')} (4 = confirmed downtrend)
Death Cross (MA50<MA200): {ticker_data.get('death_cross', 'N/A')}
Below MA200: {ticker_data.get('below_ma200', 'N/A')}
% from 52w high: {ticker_data.get('pct_from_52w_high', 'N/A')}%
RSI daily: {ticker_data.get('rsi_daily', 'N/A')}

FUNDAMENTAL DETERIORATION:
Revenue growth YoY: {ticker_data.get('rev_growth_yoy', 'N/A')}%
ROE: {ticker_data.get('roe_pct', 'N/A')}%
FCF yield: {ticker_data.get('fcf_yield_pct', 'N/A')}%
Debt/Equity: {ticker_data.get('debt_to_equity', 'N/A')}
Operating margin: {ticker_data.get('operating_margin', 'N/A')}%
Piotroski score: {ticker_data.get('piotroski_score', 'N/A')}/9 (low = weak fundamentals)

ANALYST CONSENSUS:
Analyst target: ${ticker_data.get('analyst_target', 'N/A')} (upside from current: {ticker_data.get('analyst_upside_pct', 'N/A')}%)
Note: For shorts, NEGATIVE analyst upside = analyst target BELOW current price = bearish confirmation

SHORT RISK FACTORS (why this short could FAIL):
Short interest: {ticker_data.get('short_interest_pct', 'N/A')}% (>20% = squeeze risk)
Squeeze risk: {ticker_data.get('squeeze_risk', 'N/A')}
Earnings within 5 days: {ticker_data.get('earnings_warning', 'N/A')}

EXISTING SHORT THESIS (auto-generated):
{ticker_data.get('short_thesis', 'N/A')}

Validate this bearish thesis. Key questions:
1. Is the technical breakdown CONFIRMED and sustained (not a temporary dip)?
2. Are fundamentals GENUINELY deteriorating (not cyclical)?
3. Is squeeze risk LOW enough to safely short?
4. Does the analyst consensus support the bear case?
5. Is there a specific catalyst driving further downside?

IMPORTANT: For SHORT strategy, BUY means "confirmed SHORT opportunity" (good to short), AVOID means the thesis is weak or squeeze risk too high.

Respond ONLY with JSON:
{{"verdict": "BUY"|"HOLD"|"AVOID", "confidence": 0-100, "reasoning": "brief explanation of bearish thesis strength"}}"""

        elif strategy == "MICRO_CAP":
            prompt = f"""You are a micro-cap specialist. Validate this small company for a high-conviction long entry.

{ticker_data['ticker']} - {ticker_data.get('company_name','')} - {ticker_data.get('sector','?')} - ${ticker_data.get('current_price',0):.2f}
Market cap: ${ticker_data.get('market_cap',0):,.0f} | Score: {ticker_data.get('micro_cap_score','N/A')}/100 | Quality: {ticker_data.get('quality','')}

GROWTH QUALITY:
EPS growth YoY: {ticker_data.get('eps_growth_yoy','N/A')}% | Accelerating: {ticker_data.get('eps_accelerating','N/A')}
Revenue growth YoY: {ticker_data.get('rev_growth_yoy','N/A')}% | Accelerating: {ticker_data.get('rev_accelerating','N/A')}

FINANCIAL HEALTH:
Piotroski score: {ticker_data.get('piotroski_score','N/A')}/9 (>=7 = strong)
FCF yield: {ticker_data.get('fcf_yield_pct','N/A')}%
Interest coverage: {ticker_data.get('interest_coverage','N/A')}x
Financial health score: {ticker_data.get('financial_health_score','N/A')}/25

TECHNICAL SETUP:
RS line at new high: {ticker_data.get('rs_line_at_new_high','N/A')} (key for micro-cap breakout)
RS line percentile: {ticker_data.get('rs_line_percentile','N/A')}%
Trend template pass: {ticker_data.get('trend_template_pass','N/A')}

RISK FACTORS:
Short % float: {ticker_data.get('short_percent_float','N/A')}% | Squeeze potential: {ticker_data.get('short_squeeze_potential','N/A')}
Analyst upside: {ticker_data.get('analyst_upside_pct','N/A')}%
Earnings warning: {ticker_data.get('earnings_warning','N/A')}

Micro-cap conviction check:
1. Is growth real and accelerating? (not a one-off quarter)
2. Is the balance sheet solid? (Piotroski >=6, positive FCF, covered debt)
3. Is relative strength confirming? (RS line at new high = institutional accumulation)
4. Is the risk/reward compelling vs. liquidity risk of small caps?
5. Any red flags: dilution risk, no analyst coverage, sector headwinds, extreme short interest?

Only BUY if this is genuinely high-conviction. Micro-caps require extra scrutiny.
Respond ONLY with JSON:
{{"verdict": "BUY"|"HOLD"|"AVOID", "confidence": 0-100, "reasoning": "brief explanation"}}"""

        else:  # VALUE
            prompt = f"""Analyze this VALUE stock opportunity as a fundamental analyst.

{ticker_data['ticker']} - {ticker_data['sector']} - ${ticker_data['current_price']:.2f}

VALUATION:
Target: ${ticker_data.get('target_price_analyst', 'N/A')} ({ticker_data.get('analyst_count', 0)} analysts)
Upside: {ticker_data.get('analyst_upside_pct', 'N/A')}%

FUNDAMENTALS:
ROE: {ticker_data.get('roe', 'N/A')}%
Margin: {ticker_data.get('profit_margin', 'N/A')}%
Debt/Eq: {ticker_data.get('debt_to_equity', 'N/A')}
Growth: {ticker_data.get('rev_growth', 'N/A')}%

QUALITY CHECKS:
1. Upside realistic? (>100% suspicious)
2. Fundamentals strong? (ROE>10%, Margin>10%, Debt<2x)
3. Analyst validation? (3+ analysts)
4. Red flags? (negative ROE, debt>5x, revenue declining)

Respond ONLY with JSON:
{{"verdict": "BUY"|"HOLD"|"AVOID", "confidence": 0-100, "reasoning": "brief explanation"}}"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=150,
            response_format={"type": "json_object"},
        )

        result_text = response.choices[0].message.content.strip()

        # Clean markdown if present
        if '```' in result_text:
            result_text = result_text.split('```')[1]
            if result_text.startswith('json'):
                result_text = result_text[4:]
            result_text = result_text.strip()

        result = json.loads(result_text)
        return result

    except Exception as e:
        # Fallback to rule-based
        return fallback_analysis(ticker_data, strategy)

def fallback_analysis(ticker_data: dict, strategy: str = "VALUE") -> dict:
    """
    Advanced rule-based quality analysis
    Based on fundamental metrics, valuation, insider buying, institutional ownership
    Strategy-specific filters for VALUE vs MOMENTUM
    """
    confidence = 50
    strengths = []
    concerns = []

    # 1. ANALYST COVERAGE (critical for validation)
    analyst_count = ticker_data.get('analyst_count', 0)
    if pd.notna(analyst_count) and analyst_count >= 10:
        confidence += 15
        strengths.append(f"high coverage ({int(analyst_count)})")
    elif pd.notna(analyst_count) and analyst_count >= 5:
        confidence += 10
        strengths.append(f"good coverage ({int(analyst_count)})")
    elif pd.notna(analyst_count) and analyst_count >= 3:
        confidence += 5
        strengths.append(f"moderate coverage ({int(analyst_count)})")
    elif analyst_count == 0 or pd.isna(analyst_count):
        confidence -= 20
        concerns.append("no analyst coverage")

    # 2. UPSIDE VALIDATION
    upside = ticker_data.get('analyst_upside_pct')
    if pd.notna(upside):
        if upside > 100:
            confidence -= 25
            concerns.append(f"unrealistic upside ({upside:.0f}%)")
        elif upside > 20:
            confidence += 15
            strengths.append(f"strong upside ({upside:.0f}%)")
        elif upside > 10:
            confidence += 10
            strengths.append(f"good upside ({upside:.0f}%)")
        elif upside > 5:
            confidence += 5
            strengths.append(f"moderate upside ({upside:.0f}%)")
        else:
            confidence -= 10
            concerns.append(f"low upside ({upside:.0f}%)")
    else:
        confidence -= 15
        concerns.append("no target price")

    # 3. PROFITABILITY
    profit_margin = ticker_data.get('profit_margin')
    if pd.notna(profit_margin):
        if profit_margin > 20:
            confidence += 10
            strengths.append(f"high margin ({profit_margin:.0f}%)")
        elif profit_margin > 10:
            confidence += 5
            strengths.append(f"good margin ({profit_margin:.0f}%)")
        elif profit_margin < 0:
            confidence -= 20
            concerns.append("unprofitable")
        elif profit_margin < 5:
            confidence -= 5
            concerns.append("low margin")

    # 4. ROE (return on equity)
    roe = ticker_data.get('roe')
    if pd.notna(roe):
        if roe > 20:
            confidence += 10
            strengths.append(f"ROE {roe:.0f}%")
        elif roe > 15:
            confidence += 5
        elif roe < 0:
            confidence -= 30
            concerns.append(f"negative ROE ({roe:.0f}%)")
        elif roe < 5:
            confidence -= 10
            concerns.append("low ROE")

    # 5. DEBT LEVEL
    debt = ticker_data.get('debt_to_equity')
    if pd.notna(debt):
        if debt > 10:
            confidence -= 25
            concerns.append(f"extreme debt ({debt:.1f}x)")
        elif debt > 5:
            confidence -= 15
            concerns.append(f"very high debt ({debt:.1f}x)")
        elif debt > 2:
            confidence -= 5
            concerns.append(f"high debt ({debt:.1f}x)")
        elif debt < 0.5:
            confidence += 5
            strengths.append("low debt")

    # 6. REVENUE GROWTH
    rev_growth = ticker_data.get('rev_growth')
    if pd.notna(rev_growth):
        if rev_growth > 30:
            confidence += 10
            strengths.append(f"growth {rev_growth:.0f}%")
        elif rev_growth > 15:
            confidence += 5
        elif rev_growth < -10:
            confidence -= 15
            concerns.append("revenue declining")
        elif rev_growth < 0:
            confidence -= 5

    # 7. INSIDER BUYING (CRITICAL - recent insider purchases = high confidence)
    insiders_score = ticker_data.get('insiders_score', 0)
    if pd.notna(insiders_score):
        if insiders_score >= 80:
            confidence += 20
            strengths.append(f"insider buying STRONG ({insiders_score:.0f}/100)")
        elif insiders_score >= 60:
            confidence += 15
            strengths.append(f"insider buying ({insiders_score:.0f}/100)")
        elif insiders_score >= 40:
            confidence += 10
            strengths.append(f"insider activity ({insiders_score:.0f}/100)")

    # 8. INSTITUTIONAL OWNERSHIP (validation by smart money)
    institutional_score = ticker_data.get('institutional_score', 0)
    if pd.notna(institutional_score):
        if institutional_score >= 80:
            confidence += 10
            strengths.append(f"institutional buying ({institutional_score:.0f}/100)")
        elif institutional_score >= 60:
            confidence += 5
            strengths.append(f"institutional interest ({institutional_score:.0f}/100)")

    # ========================================================================
    # MOMENTUM-SPECIFIC SAFETY FILTERS (Minervini-style risk management)
    # ========================================================================
    if strategy == "MOMENTUM":
        # 9. OVER-EXTENSION CHECK (critical - avoid buying climax tops)
        proximity = ticker_data.get('proximity_to_52w_high')
        if pd.notna(proximity):
            if proximity > 1.25:
                confidence -= 30
                concerns.append(f"OVER-EXTENDED ({proximity:.2f}x 52w high)")
            elif proximity > 1.15:
                confidence -= 15
                concerns.append(f"near over-extension ({proximity:.2f}x)")
            elif proximity > 1.05 and proximity <= 1.15:
                confidence += 10
                strengths.append(f"healthy momentum ({proximity:.2f}x)")
            elif proximity < 0.85:
                confidence -= 10
                concerns.append("too far from highs")

        # 10. EARNINGS ACCELERATION (sustainable momentum requires this)
        eps_accel = ticker_data.get('eps_accelerating')
        rev_accel = ticker_data.get('rev_accelerating')

        if eps_accel == True and rev_accel == True:
            confidence += 15
            strengths.append("earnings+revenue accelerating")
        elif eps_accel == True:
            confidence += 10
            strengths.append("earnings accelerating")
        elif eps_accel == False and rev_accel == False:
            confidence -= 20
            concerns.append("growth decelerating")

        # 11. INDUSTRY GROUP STRENGTH (sector tailwind = safer)
        industry_pct = ticker_data.get('industry_group_percentile')
        if pd.notna(industry_pct):
            if industry_pct >= 80:
                confidence += 15
                strengths.append(f"top industry ({industry_pct:.0f}%)")
            elif industry_pct >= 70:
                confidence += 10
                strengths.append(f"strong industry ({industry_pct:.0f}%)")
            elif industry_pct < 30:
                confidence -= 15
                concerns.append(f"weak industry ({industry_pct:.0f}%)")

        # 12. SHORT SQUEEZE RISK (high short % = artificial momentum)
        short_pct = ticker_data.get('short_percent_float')
        if pd.notna(short_pct):
            if short_pct > 20:
                confidence -= 15
                concerns.append(f"high short % ({short_pct:.1f}%) - squeeze risk")
            elif short_pct > 10:
                confidence -= 5
                concerns.append(f"elevated short ({short_pct:.1f}%)")

        # 13. FUNDAMENTAL FLOOR (momentum needs profitability)
        if pd.notna(roe) and roe < 0:
            confidence -= 25
            concerns.append("MOMENTUM with negative ROE = risky")
        if pd.notna(profit_margin) and profit_margin < 0:
            confidence -= 20
            concerns.append("MOMENTUM unprofitable")

        # 14. RS LINE AT NEW HIGH (Minervini CRITICAL rule)
        rs_at_high = ticker_data.get('rs_line_at_new_high')
        if rs_at_high == True:
            confidence += 20
            strengths.append("RS line new high (Minervini ✓)")
        elif rs_at_high == False:
            confidence -= 20
            concerns.append("RS line NOT at new high (Minervini fail)")

        # 15. OPTIONS FLOW (smart money validation)
        flow_score = ticker_data.get('flow_score')
        unusual_calls = ticker_data.get('unusual_calls')
        if pd.notna(flow_score):
            if flow_score >= 70:
                confidence += 15
                strengths.append(f"strong options flow ({flow_score:.0f})")
            elif flow_score >= 50:
                confidence += 10
                strengths.append(f"positive flow ({flow_score:.0f})")
            elif flow_score < 30:
                confidence -= 10
                concerns.append(f"negative flow ({flow_score:.0f})")

        if pd.notna(unusual_calls) and unusual_calls > 0:
            confidence += 10
            strengths.append("unusual call activity")

        # 16. WHALE COUNT (institutional validation)
        num_whales = ticker_data.get('num_whales')
        if pd.notna(num_whales):
            if num_whales >= 3:
                confidence += 15
                strengths.append(f"{int(num_whales)} whales buying")
            elif num_whales >= 1:
                confidence += 10
                strengths.append(f"{int(num_whales)} whale(s)")
            elif num_whales == 0:
                confidence -= 10
                concerns.append("no whale activity")

        # 17. MARKET REGIME (bearish = more conservative)
        market_regime = ticker_data.get('market_regime', '').lower()
        if 'bear' in market_regime or 'correction' in market_regime:
            confidence -= 15
            concerns.append(f"bear market ({market_regime})")
        elif 'bull' in market_regime or 'uptrend' in market_regime:
            confidence += 5
            strengths.append(f"bull market")

    # VERDICT
    if confidence >= 70:
        verdict = "BUY"
    elif confidence >= 50:
        verdict = "HOLD"
    else:
        verdict = "AVOID"

    # Build reasoning
    if strengths and not concerns:
        reasoning = ", ".join(strengths[:2])
    elif concerns and not strengths:
        reasoning = ", ".join(concerns[:2])
    elif strengths and concerns:
        reasoning = f"{strengths[0]} but {concerns[0]}"
    else:
        reasoning = "neutral fundamentals"

    return {
        'verdict': verdict,
        'confidence': confidence,
        'reasoning': reasoning
    }

def extract_fundamentals(row):
    """Extract fundamental metrics from health_details and earnings_details"""
    roe = None
    debt_to_equity = None
    profit_margin = None

    # Extract from health_details
    health_details = row.get('health_details', '{}')
    if isinstance(health_details, str):
        try:
            hd = eval(health_details)
            roe = hd.get('roe_pct')
            debt_to_equity = hd.get('debt_to_equity')
        except:
            pass

    # Extract from earnings_details
    earnings_details = row.get('earnings_details', '{}')
    if isinstance(earnings_details, str):
        try:
            ed = eval(earnings_details)
            profit_margin = ed.get('profit_margin_pct')
        except:
            pass

    return roe, profit_margin, debt_to_equity

def filter_opportunities(input_path: Path, strategy_name: str, score_field: str):
    """
    Filter opportunities using AI quality analysis
    Args:
        input_path: Path to opportunities CSV
        strategy_name: "VALUE" or "MOMENTUM"
        score_field: "value_score" or "momentum_score"
    """
    print("\n" + "=" * 100)
    print(f"AI-POWERED QUALITY FILTER FOR {strategy_name} OPPORTUNITIES (Groq)")
    print("=" * 100)

    if not input_path.exists():
        print(f"❌ {input_path.name} not found - skipping {strategy_name}")
        return None

    if input_path.stat().st_size == 0:
        print(f"⚠️  {input_path.name} is empty - skipping {strategy_name} (0 setups)")
        return None

    try:
        df = pd.read_csv(input_path)
    except Exception as e:
        print(f"⚠️  {input_path.name} unreadable ({e}) - skipping {strategy_name} (0 setups)")
        return None
    if df.empty:
        print(f"⚠️  {input_path.name} has no rows - skipping {strategy_name} (0 setups)")
        return None
    print(f"\n📊 Input: {len(df)} {strategy_name} opportunities")

    if score_field in df.columns:
        print(f"   Average {score_field}: {df[score_field].mean():.1f}")

    # Analyze each with AI
    results = []
    buy_count = 0
    hold_count = 0
    avoid_count = 0

    print(f"\n🤖 Analyzing with Groq AI (llama-3.3-70b)...")
    print("-" * 100)

    for idx, row in df.iterrows():
        ticker = row['ticker']

        # Extract fundamentals
        roe, profit_margin, debt_to_equity = extract_fundamentals(row)

        # Build data dict for AI (include insider/institutional scores)
        ticker_data = {
            'ticker': ticker,
            'company_name': row['company_name'],
            'sector': row['sector'],
            'current_price': row['current_price'],
            'target_price_analyst': row.get('target_price_analyst'),
            'analyst_count': row.get('analyst_count', 0),
            'analyst_upside_pct': row.get('analyst_upside_pct'),
            'roe': roe,
            'profit_margin': profit_margin,
            'debt_to_equity': debt_to_equity,
            'rev_growth': row.get('rev_growth_yoy'),
            'insiders_score': row.get('insiders_score', 0),
            'institutional_score': row.get('institutional_score', 0),
            # MOMENTUM-specific fields
            'proximity_to_52w_high': row.get('proximity_to_52w_high'),
            'eps_accelerating': row.get('eps_accelerating'),
            'rev_accelerating': row.get('rev_accelerating'),
            'industry_group_percentile': row.get('industry_group_percentile'),
            'short_percent_float': row.get('short_percent_float'),
            # CRITICAL Minervini metrics
            'rs_line_at_new_high': row.get('rs_line_at_new_high'),
            'flow_score': row.get('flow_score'),
            'unusual_calls': row.get('unusual_calls'),
            'num_whales': row.get('num_whales'),
            'market_regime': row.get('market_regime')
        }

        # Analyze with AI (strategy-aware)
        analysis = analyze_with_ai(ticker_data, strategy=strategy_name)

        # Store result
        row_result = row.to_dict()
        row_result['ai_verdict'] = analysis['verdict']
        row_result['ai_confidence'] = analysis['confidence']
        row_result['ai_reasoning'] = analysis['reasoning']
        results.append(row_result)

        # Count
        if analysis['verdict'] == 'BUY':
            buy_count += 1
            emoji = "🟢"
        elif analysis['verdict'] == 'HOLD':
            hold_count += 1
            emoji = "🟡"
        else:
            avoid_count += 1
            emoji = "🔴"

        print(f"{emoji} {ticker:<6} {analysis['verdict']:<6} (conf: {analysis['confidence']:>3}) - {analysis['reasoning'][:60]}")

    # Create filtered DataFrame
    df_results = pd.DataFrame(results)

    # Filter: Keep only BUY with confidence >= 65
    df_filtered = df_results[
        (df_results['ai_verdict'] == 'BUY') &
        (df_results['ai_confidence'] >= 65)
    ].copy()

    # Sort by confidence
    df_filtered = df_filtered.sort_values('ai_confidence', ascending=False)

    print("\n" + "=" * 100)
    print("FILTERING RESULTS")
    print("=" * 100)
    print(f"\n🟢 BUY: {buy_count}")
    print(f"🟡 HOLD: {hold_count}")
    print(f"🔴 AVOID: {avoid_count}")

    print(f"\n✅ FILTERED (BUY with confidence ≥65): {len(df_filtered)}/{len(df)}")
    print(f"   Rejected: {len(df) - len(df_filtered)} low-quality opportunities")

    # Save filtered results
    output_filename = input_path.stem + '_filtered.csv'
    output_path = Path('docs') / output_filename
    df_filtered.to_csv(output_path, index=False)
    print(f"\n💾 Saved to: {output_path}")

    # Show top 10
    print(f"\n🎯 TOP 10 QUALITY {strategy_name} OPPORTUNITIES:")
    print("-" * 100)

    top10 = df_filtered.head(10)
    for i, (_, row) in enumerate(top10.iterrows(), 1):
        ticker = row['ticker']
        price = row['current_price']
        target = row.get('target_price_analyst')
        upside = row.get('analyst_upside_pct')
        confidence = row['ai_confidence']
        insiders = row.get('insiders_score', 0)

        target_str = f"${target:.2f}" if pd.notna(target) else "N/A"
        upside_str = f"+{upside:.1f}%" if pd.notna(upside) else "N/A"
        insider_str = f"I:{insiders:.0f}" if pd.notna(insiders) and insiders > 0 else ""

        print(f"  {i:2}. {ticker:<6} ${price:>8.2f} → {target_str:>8} ({upside_str:>8}) | Conf:{confidence:>3} {insider_str}")

    print("\n" + "=" * 100)

    return len(df_filtered)


def filter_shorts():
    """
    AI double-check for short opportunities from short_opportunities.json.
    Adds ai_verdict, ai_confidence, ai_reasoning to each short.
    Saves docs/short_opportunities_filtered.json — only HIGH-confidence confirmed shorts.
    """
    import json as _json
    short_path = Path('docs/short_opportunities.json')
    if not short_path.exists():
        print("❌ short_opportunities.json not found — run short_scanner.py first")
        return 0

    try:
        with open(short_path) as f:
            raw = _json.load(f)
    except Exception as e:
        print(f"❌ Error loading short_opportunities.json: {e}")
        return 0

    shorts = raw.get('data', [])
    if not shorts:
        print("⚠️  No short opportunities to filter")
        return 0

    # Only process MEDIA + ALTA quality shorts (BAJA not worth AI time)
    candidates = [s for s in shorts if s.get('short_quality') in ('ALTA', 'MEDIA')]
    print(f"\n📊 Short candidates for AI review: {len(candidates)}/{len(shorts)} (ALTA+MEDIA quality)")

    results = []
    confirmed = 0

    print(f"\n🤖 Validating with Groq AI (SHORT strategy)...")
    print("-" * 100)

    for s in candidates:
        ticker = s.get('ticker', '?')
        ticker_data = {
            'ticker': ticker,
            'sector': s.get('sector', ''),
            'current_price': s.get('current_price', 0),
            'short_score': s.get('short_score', 0),
            'short_quality': s.get('short_quality', ''),
            'weinstein_stage': s.get('weinstein_stage'),
            'death_cross': s.get('death_cross'),
            'below_ma200': s.get('below_ma200'),
            'pct_from_52w_high': s.get('pct_from_52w_high'),
            'rsi_daily': s.get('rsi_daily'),
            'rev_growth_yoy': s.get('rev_growth_yoy'),
            'roe_pct': s.get('roe_pct'),
            'fcf_yield_pct': s.get('fcf_yield_pct'),
            'debt_to_equity': s.get('debt_to_equity'),
            'operating_margin': s.get('operating_margin'),
            'piotroski_score': s.get('piotroski_score'),
            'analyst_target': s.get('analyst_target'),
            'analyst_upside_pct': s.get('analyst_upside_pct'),
            'short_interest_pct': s.get('short_interest_pct'),
            'squeeze_risk': s.get('squeeze_risk', 'UNKNOWN'),
            'earnings_warning': s.get('earnings_warning', False),
            'short_thesis': s.get('short_thesis', ''),
        }

        analysis = analyze_with_ai(ticker_data, strategy='SHORT')

        s['ai_verdict'] = analysis['verdict']
        s['ai_confidence'] = analysis['confidence']
        s['ai_reasoning'] = analysis['reasoning']
        results.append(s)

        emoji = '🟢' if analysis['verdict'] == 'BUY' else ('🟡' if analysis['verdict'] == 'HOLD' else '🔴')
        if analysis['verdict'] == 'BUY':
            confirmed += 1
        print(f"{emoji} {ticker:<6} {analysis['verdict']:<6} (conf:{analysis['confidence']:>3}) — {analysis['reasoning'][:70]}")

    # All candidates get AI annotation, but filtered = only BUY >= 65 confidence
    confirmed_shorts = [s for s in results if s.get('ai_verdict') == 'BUY' and s.get('ai_confidence', 0) >= 65]
    confirmed_shorts.sort(key=lambda x: x.get('ai_confidence', 0), reverse=True)

    # Save annotated full list back to short_opportunities.json
    # (add AI fields, keep all shorts)
    all_shorts_annotated = []
    tickers_done = {s['ticker'] for s in results}
    for s in shorts:
        if s['ticker'] in tickers_done:
            annotated = next(r for r in results if r['ticker'] == s['ticker'])
            all_shorts_annotated.append(annotated)
        else:
            # BAJA quality — no AI annotation, passthrough
            s.setdefault('ai_verdict', None)
            s.setdefault('ai_confidence', None)
            s.setdefault('ai_reasoning', None)
            all_shorts_annotated.append(s)

    raw['data'] = all_shorts_annotated
    with open(short_path, 'w') as f:
        _json.dump(raw, f, indent=2, default=str)

    # Save filtered (high-confidence confirmed shorts only)
    filtered_output = {
        'scan_date': raw.get('scan_date', ''),
        'generated_at': raw.get('generated_at', ''),
        'ai_filtered': True,
        'total_candidates': len(candidates),
        'confirmed_shorts': len(confirmed_shorts),
        'data': confirmed_shorts,
    }
    filtered_path = Path('docs/short_opportunities_filtered.json')
    with open(filtered_path, 'w') as f:
        _json.dump(filtered_output, f, indent=2, default=str)

    print(f"\n{'=' * 100}")
    print(f"SHORT AI FILTER RESULTS")
    print(f"  Candidates reviewed: {len(candidates)}")
    print(f"  Confirmed SHORT (BUY ≥65): {len(confirmed_shorts)}")
    print(f"  Saved: {filtered_path}")
    print(f"{'=' * 100}")
    return len(confirmed_shorts)


def filter_micro_cap():
    """
    AI double-check for micro-cap opportunities.
    Only reviews EXCELLENT + GOOD quality tickers (score >= 65).
    Saves docs/micro_cap_opportunities_filtered.csv — only AI-confirmed high-conviction picks.
    """
    import csv as _csv, io as _io

    mc_path = Path('docs/micro_cap_opportunities.csv')
    if not mc_path.exists():
        print("❌ micro_cap_opportunities.csv not found — run micro_cap_scanner.py first")
        return 0

    with open(mc_path, newline='') as f:
        reader = _csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    if not rows:
        print("⚠️  No micro-cap opportunities to filter")
        return 0

    # Only review EXCELLENT + GOOD (score >= 65) — skip noise
    candidates = [r for r in rows if float(r.get('micro_cap_score') or 0) >= 65]
    print(f"\n📊 Micro-cap candidates for AI review: {len(candidates)}/{len(rows)} (score ≥65)")

    confirmed = []
    print(f"\n🤖 Validating with Groq AI (MICRO-CAP strategy)...")
    print("-" * 100)

    for r in candidates:
        ticker = r.get('ticker', '?')
        def _f(key, default=None):
            v = r.get(key)
            if v in (None, '', 'N/A', 'nan', 'None'): return default
            try: return float(v)
            except: return v

        ticker_data = {
            'ticker': ticker,
            'company_name': r.get('company_name', ''),
            'sector': r.get('sector', ''),
            'current_price': _f('current_price', 0),
            'market_cap': _f('market_cap', 0),
            'micro_cap_score': _f('micro_cap_score', 0),
            'quality': r.get('quality', ''),
            'tier': r.get('tier', ''),
            # Numeric fields — fallback_analysis expects float or None
            'piotroski_score': _f('piotroski_score'),
            'fcf_yield_pct': _f('fcf_yield_pct'),
            'eps_growth_yoy': _f('eps_growth_yoy'),
            'rev_growth_yoy': _f('rev_growth_yoy'),
            'analyst_upside_pct': _f('analyst_upside_pct'),
            'analyst_count': _f('analyst_count', 0),
            'rs_line_percentile': _f('rs_line_percentile'),
            'financial_health_score': _f('financial_health_score'),
            'short_percent_float': _f('short_percent_float'),
            'interest_coverage': _f('interest_coverage'),
            # Boolean/string fields
            'eps_accelerating': r.get('eps_accelerating', 'N/A'),
            'rev_accelerating': r.get('rev_accelerating', 'N/A'),
            'rs_line_at_new_high': r.get('rs_line_at_new_high', 'N/A'),
            'trend_template_pass': r.get('trend_template_pass', 'N/A'),
            'short_squeeze_potential': r.get('short_squeeze_potential', 'N/A'),
            'earnings_warning': r.get('earnings_warning', 'N/A'),
            # Standard fallback keys
            'roe': _f('roe_pct'),
            'profit_margin': _f('operating_margin_pct'),
            'debt_to_equity': _f('debt_to_equity'),
            'rev_growth': _f('rev_growth_yoy'),
            'target_price_analyst': _f('target_price_analyst'),
        }
        analysis = analyze_with_ai(ticker_data, strategy='MICRO_CAP')
        r['ai_verdict'] = analysis['verdict']
        r['ai_confidence'] = analysis['confidence']
        r['ai_reasoning'] = analysis['reasoning']

        emoji = '🟢' if analysis['verdict'] == 'BUY' else ('🟡' if analysis['verdict'] == 'HOLD' else '🔴')
        if analysis['verdict'] == 'BUY' and analysis['confidence'] >= 65:
            confirmed.append(r)
        print(f"{emoji} {ticker:<8} {analysis['verdict']:<6} (conf:{analysis['confidence']:>3}) — {analysis['reasoning'][:70]}")

    confirmed.sort(key=lambda x: float(x.get('micro_cap_score') or 0), reverse=True)

    # Save confirmed-only filtered CSV
    all_fields = list(fieldnames) + ['ai_verdict', 'ai_confidence', 'ai_reasoning']
    filtered_path = Path('docs/micro_cap_opportunities_filtered.csv')
    with open(filtered_path, 'w', newline='') as f:
        writer = _csv.DictWriter(f, fieldnames=all_fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(confirmed)

    # Also update main CSV with AI annotations
    annotated_tickers = {r['ticker'] for r in candidates}
    for orig in rows:
        if orig['ticker'] not in annotated_tickers:
            orig['ai_verdict'] = None
            orig['ai_confidence'] = None
            orig['ai_reasoning'] = None
    all_fields_main = list(fieldnames) + ['ai_verdict', 'ai_confidence', 'ai_reasoning']
    with open(mc_path, 'w', newline='') as f:
        writer = _csv.DictWriter(f, fieldnames=all_fields_main, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{'=' * 100}")
    print(f"MICRO-CAP AI FILTER RESULTS")
    print(f"  Candidates reviewed : {len(candidates)}")
    print(f"  Confirmed (BUY ≥65) : {len(confirmed)}")
    print(f"  Saved               : {filtered_path}")
    print(f"{'=' * 100}")
    return len(confirmed)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='AI Quality Filter')
    parser.add_argument('--european', action='store_true',
                        help='Filter European VALUE opportunities only')
    parser.add_argument('--shorts', action='store_true',
                        help='AI double-check for short opportunities')
    parser.add_argument('--micro-cap', action='store_true',
                        help='AI double-check for micro-cap opportunities')
    args = parser.parse_args()

    if args.shorts:
        print("=" * 100)
        print("AI-POWERED QUALITY FILTER - SHORT OPPORTUNITIES")
        print("=" * 100)
        n = filter_shorts()
        print(f"\n✅ Confirmed short opportunities: {n}")
        return

    if getattr(args, 'micro_cap', False):
        print("=" * 100)
        print("AI-POWERED QUALITY FILTER - MICRO-CAP OPPORTUNITIES")
        print("=" * 100)
        n = filter_micro_cap()
        print(f"\n✅ Confirmed micro-cap opportunities: {n}")
        return

    if args.european:
        print("=" * 100)
        print("AI-POWERED QUALITY FILTER - EUROPEAN VALUE")
        print("=" * 100)

        eu_path = Path('docs/european_value_opportunities.csv')
        eu_filtered = filter_opportunities(eu_path, "VALUE", "value_score")

        print(f"\n✅ European VALUE filtered: {eu_filtered if eu_filtered else 0}")
        return

    print("=" * 100)
    print("AI-POWERED QUALITY FILTER - DUAL STRATEGY VALIDATION")
    print("=" * 100)

    total_filtered = 0

    # Filter VALUE opportunities
    value_path = Path('docs/value_opportunities.csv')
    value_filtered = filter_opportunities(value_path, "VALUE", "value_score")
    if value_filtered is not None:
        total_filtered += value_filtered

    # Filter MOMENTUM opportunities
    momentum_path = Path('docs/momentum_opportunities.csv')
    momentum_filtered = filter_opportunities(momentum_path, "MOMENTUM", "momentum_score")
    if momentum_filtered is not None:
        total_filtered += momentum_filtered

    print("\n" + "=" * 100)
    print("FINAL SUMMARY - DUAL STRATEGY FILTER")
    print("=" * 100)
    print(f"\n✅ Total high-quality opportunities validated: {total_filtered}")
    print(f"   VALUE: {value_filtered if value_filtered else 0}")
    print(f"   MOMENTUM: {momentum_filtered if momentum_filtered else 0}")
    print("\n💡 Both strategies now have AI validation + insider/institutional bonus")
    print("=" * 100)

if __name__ == '__main__':
    main()
