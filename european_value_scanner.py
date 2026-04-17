#!/usr/bin/env python3
"""
EUROPEAN VALUE SCANNER
Escanea acciones europeas (DAX, FTSE, CAC, IBEX, AEX, SMI, FTSE MIB)
usando fundamental_scorer.py y aplica una formula VALUE adaptada para Europa.

Diferencias vs US:
- Insiders FTSE100/AEX25 via yfinance (ver european_insider_scanner.py)
- Sin institutional 13F
- Sin options flow
- Sin sector rotation
- Sin ML scores
- Bonificacion extra a dividendos (Europa es dividend-heavy)

Max score teorico: ~97 pts (FTSE100 con insiders) / ~82 pts (DAX/CAC/sin datos insider)
"""
import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path
from datetime import datetime
import json
import time
import argparse
import ast

from fundamental_scorer import FundamentalScorer
from market_configs import get_all_european_symbols, get_european_market_for_ticker
from curated_tickers_eu import SCORED_EU_TICKERS as CURATED_EU_TICKERS

# Rate limit delay between yfinance API calls
YFINANCE_RATE_DELAY = 0.3


def detect_european_market_regime() -> dict:
    """
    Detecta regimen del mercado europeo usando Euro Stoxx 50 (^STOXX50E)
    Logica simplificada similar a market_regime_detector.py
    """
    print("\n" + "=" * 70)
    print("EUROPEAN MARKET REGIME DETECTOR")
    print("=" * 70)

    try:
        stoxx = yf.Ticker("^STOXX50E")
        hist = stoxx.history(period="6mo")

        if hist.empty or len(hist) < 50:
            print("   No se pudo obtener datos del Euro Stoxx 50")
            return {'regime': 'UNKNOWN', 'recommendation': 'CAUTION'}

        close = hist['Close']

        # Calculate moving averages
        ma50 = close.rolling(50).mean().iloc[-1]
        ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else close.rolling(min(len(close), 100)).mean().iloc[-1]
        current = close.iloc[-1]

        # MA200 slope (last 20 days)
        if len(close) >= 220:
            ma200_20ago = close.rolling(200).mean().iloc[-20]
        else:
            ma200_20ago = ma200 * 0.99  # Assume slight uptrend if not enough data

        ma200_slope = (ma200 - ma200_20ago) / ma200_20ago * 100

        # Determine regime
        above_50 = current > ma50
        above_200 = current > ma200
        ma_aligned = ma50 > ma200
        slope_up = ma200_slope > 0

        score = sum([above_50, above_200, ma_aligned, slope_up])

        if score >= 3:
            regime = 'CONFIRMED_UPTREND'
            recommendation = 'TRADE'
        elif score >= 2:
            regime = 'UPTREND_PRESSURE'
            recommendation = 'CAUTION'
        else:
            regime = 'CORRECTION'
            recommendation = 'AVOID'

        result = {
            'regime': regime,
            'recommendation': recommendation,
            'stoxx50_price': round(current, 2),
            'ma50': round(ma50, 2),
            'ma200': round(ma200, 2),
            'ma200_slope': round(ma200_slope, 2),
        }

        print(f"   Euro Stoxx 50: {current:.0f} | MA50: {ma50:.0f} | MA200: {ma200:.0f}")
        print(f"   Regime: {regime} | Recommendation: {recommendation}")

        # Save report
        report_path = Path('docs/european_market_regime.json')
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, 'w') as f:
            json.dump(result, f, indent=2)

        return result

    except Exception as e:
        print(f"   Error detecting EU regime: {e}")
        return {'regime': 'UNKNOWN', 'recommendation': 'CAUTION'}


def score_european_tickers(max_tickers: int = None, use_curated: bool = False) -> pd.DataFrame:
    """
    Escanea y puntua tickers europeos usando fundamental_scorer

    Args:
        max_tickers: Limitar el numero de tickers (para testing)
        use_curated: Si True, usa el universo curado de curated_tickers_eu.py
                     (~58 empresas de calidad) en lugar del universo amplio (~200 tickers)

    Returns:
        DataFrame con scores fundamentales
    """
    if use_curated:
        symbols = list(CURATED_EU_TICKERS)
        universe_label = f"curado ({len(symbols)} empresas de alta calidad)"
        markets_label = "EU + Nórdicos (.CO/.ST/.HE) + HK/China"
    else:
        symbols = get_all_european_symbols()
        universe_label = f"amplio ({len(symbols)} tickers)"
        markets_label = "DAX40, FTSE100, CAC40, IBEX35, AEX25, SMI20, FTSE MIB"

    if max_tickers:
        symbols = symbols[:max_tickers]

    print(f"\nEUROPEAN FUNDAMENTAL SCORING")
    print("=" * 70)
    print(f"Universo: {universe_label}")
    print(f"Mercados: {markets_label}")

    scorer = FundamentalScorer()
    results = []
    errors = 0

    for i, ticker in enumerate(symbols, 1):
        try:
            print(f"\n[{i}/{len(symbols)}] ", end="")
            result = scorer.score_ticker(ticker)
            result['market'] = get_european_market_for_ticker(ticker)
            results.append(result)
            time.sleep(YFINANCE_RATE_DELAY)
        except Exception as e:
            print(f"   Error scoring {ticker}: {e}")
            errors += 1
            time.sleep(YFINANCE_RATE_DELAY)

    print(f"\n\nScoring completado: {len(results)} OK, {errors} errores")

    if not results:
        print("No se obtuvieron resultados")
        return pd.DataFrame()

    df = pd.DataFrame(results)

    # Save fundamental scores
    output_path = Path('docs/european_fundamental_scores.csv')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Guardado: {output_path}")

    return df


def calculate_european_value_scores(df: pd.DataFrame, market_regime: dict) -> pd.DataFrame:
    """
    Calcula European value_score adaptado (sin insiders/institutional/options/sector rotation)

    Scoring formula (max ~82 pts):
    - Fundamentals: 40pts (ROE, margins, growth, debt)
    - Profitability bonus: 15pts
    - FCF Yield: 8pts
    - Dividend Quality: 8pts (bumped for Europe)
    - Buyback: 3pts
    - Analyst Revision: 5pts
    - Risk/Reward: 3pts
    - Earnings warning: -5pts
    """
    print(f"\n{'='*70}")
    print("EUROPEAN VALUE SCORING")
    print(f"{'='*70}")
    print(f"Input: {len(df)} tickers")

    df = df.copy()
    df['value_score'] = 0.0

    # ─── Fundamentals (40 pts max) ───
    if 'fundamental_score' in df.columns:
        df['_fund'] = pd.to_numeric(df['fundamental_score'], errors='coerce')
        valid_fund = df['_fund'].notna() & ((df['_fund'] - 50.0).abs() > 0.1)
        df.loc[valid_fund, 'value_score'] += (df.loc[valid_fund, '_fund'] / 100) * 40
        df.drop(columns=['_fund'], inplace=True, errors='ignore')
        print(f"   Fundamentals: {valid_fund.sum()} tickers with real data")

    # ─── Profitability bonus (15 pts max) ───
    if 'health_details' in df.columns:
        for idx, row in df.iterrows():
            try:
                health = row.get('health_details', '{}')
                if isinstance(health, str):
                    health = ast.literal_eval(health) if health != '{}' else {}

                earnings = row.get('earnings_details', '{}')
                if isinstance(earnings, str):
                    earnings = ast.literal_eval(earnings) if earnings != '{}' else {}

                roe = health.get('roe_pct', 0)
                profit_margin = earnings.get('profit_margin_pct',
                                health.get('operating_margin_pct', 0))

                prof_bonus = 0.0
                if roe >= 20:
                    prof_bonus += 8.0
                elif roe >= 15:
                    prof_bonus += 5.0

                if profit_margin >= 15:
                    prof_bonus += 7.0
                elif profit_margin >= 10:
                    prof_bonus += 4.0

                df.at[idx, 'value_score'] += prof_bonus
            except:
                pass

    # ─── FCF Yield bonus (8 pts max) ───
    if 'fcf_yield_pct' in df.columns:
        df['_fcf'] = pd.to_numeric(df['fcf_yield_pct'], errors='coerce')
        df['fcf_bonus'] = 0.0
        df.loc[df['_fcf'] >= 8, 'fcf_bonus'] = 8.0
        df.loc[(df['_fcf'] >= 5) & (df['_fcf'] < 8), 'fcf_bonus'] = 6.0
        df.loc[(df['_fcf'] >= 3) & (df['_fcf'] < 5), 'fcf_bonus'] = 3.0
        df.loc[df['_fcf'] < 0, 'fcf_bonus'] = -5.0
        df['value_score'] += df['fcf_bonus']
        df.drop(columns=['_fcf'], inplace=True, errors='ignore')
        print(f"   FCF Yield bonus: {(df['fcf_bonus'] > 0).sum()} tickers")

    # ─── Dividend Quality bonus (8 pts max — bumped for Europe) ───
    if 'dividend_yield_pct' in df.columns:
        df['_div'] = pd.to_numeric(df['dividend_yield_pct'], errors='coerce').fillna(0)
        df['_payout'] = pd.to_numeric(df.get('payout_ratio_pct', pd.Series(0, index=df.index)), errors='coerce').fillna(0)
        df['dividend_bonus'] = 0.0
        # Healthy dividend: yield 1-6% AND payout < 75%
        healthy_div = (df['_div'] > 1.0) & (df['_div'] <= 6.0) & ((df['_payout'] < 75) | (df['_payout'] == 0))
        df.loc[healthy_div & (df['_div'] >= 3.0), 'dividend_bonus'] = 8.0   # Europe premium
        df.loc[healthy_div & (df['_div'] >= 1.5) & (df['_div'] < 3.0), 'dividend_bonus'] = 5.0  # Europe premium
        # Dangerously high yield (>8%) = likely distressed
        df.loc[df['_div'] > 8.0, 'dividend_bonus'] = -3.0
        # Unsustainable payout (>90%)
        df.loc[(df['_payout'] > 90) & (df['_payout'] > 0), 'dividend_bonus'] -= 2.0
        df['value_score'] += df['dividend_bonus']
        df.drop(columns=['_div', '_payout'], inplace=True, errors='ignore')
        print(f"   Dividend bonus: {(df['dividend_bonus'] > 0).sum()} tickers")

    # ─── Buyback bonus (3 pts max) ───
    if 'buyback_active' in df.columns:
        df['buyback_bonus'] = 0.0
        df.loc[df['buyback_active'] == True, 'buyback_bonus'] = 3.0
        df['value_score'] += df['buyback_bonus']
        print(f"   Buyback bonus: {(df['buyback_bonus'] > 0).sum()} tickers")

    # ─── Analyst Revision Momentum (5 pts max) ───
    if 'analyst_revision_momentum' in df.columns:
        df['_rev'] = pd.to_numeric(df['analyst_revision_momentum'], errors='coerce')
        df['revision_bonus'] = 0.0
        df.loc[df['_rev'] > 15, 'revision_bonus'] = 5.0
        df.loc[(df['_rev'] > 5) & (df['_rev'] <= 15), 'revision_bonus'] = 3.0
        df.loc[(df['_rev'] > 0) & (df['_rev'] <= 5), 'revision_bonus'] = 1.0
        df.loc[df['_rev'] < -10, 'revision_bonus'] = -3.0
        df['value_score'] += df['revision_bonus']
        df.drop(columns=['_rev'], inplace=True, errors='ignore')
        print(f"   Revision momentum: {(df['revision_bonus'] > 0).sum()} tickers")

    # ─── Earnings timing warning (-5 pts) ───
    if 'earnings_warning' in df.columns:
        earnings_risk = df['earnings_warning'] == True
        if earnings_risk.sum() > 0:
            df.loc[earnings_risk, 'value_score'] -= 5.0
            print(f"   Earnings warning: {earnings_risk.sum()} tickers penalized")

    # ─── Profitability penalty ───
    if 'profitability_penalty' in df.columns:
        df['value_score'] = (df['value_score'] - df['profitability_penalty']).clip(lower=0)

    # ─── HARD REJECT: Negative ROE ───
    negative_roe_count = 0
    if 'health_details' in df.columns:
        for idx, row in df.iterrows():
            try:
                health = row.get('health_details', '{}')
                if isinstance(health, str):
                    health = ast.literal_eval(health) if health != '{}' else {}
                roe = health.get('roe_pct', 0)
                if roe is not None and roe < 0:
                    df.at[idx, 'value_score'] = 0.0
                    negative_roe_count += 1
            except:
                pass
    if negative_roe_count > 0:
        print(f"   Hard rejected (ROE<0): {negative_roe_count} tickers")

    # ─── VALUATION CHECK: Reject overvalued (analyst_upside < 0) ───
    if 'analyst_upside_pct' in df.columns:
        overvalued = df['analyst_upside_pct'].notna() & (df['analyst_upside_pct'] < 0)
        if overvalued.sum() > 0:
            print(f"   Rejected overvalued (upside<0): {overvalued.sum()} tickers")
            df.loc[overvalued, 'value_score'] = 0.0

    # ─── Risk/Reward ratio (3 pts max) ───
    if 'analyst_upside_pct' in df.columns:
        stop_loss_pct = 8.0
        df['_upside'] = pd.to_numeric(df['analyst_upside_pct'], errors='coerce')
        df['risk_reward_ratio'] = (df['_upside'] / stop_loss_pct).round(2)
        df['rr_bonus'] = 0.0
        df.loc[df['risk_reward_ratio'] >= 3.0, 'rr_bonus'] = 3.0
        df.loc[(df['risk_reward_ratio'] >= 2.0) & (df['risk_reward_ratio'] < 3.0), 'rr_bonus'] = 1.0
        df.loc[(df['risk_reward_ratio'] < 1.0) & df['risk_reward_ratio'].notna(), 'rr_bonus'] = -3.0
        df['value_score'] += df['rr_bonus']
        df.drop(columns=['_upside'], inplace=True, errors='ignore')
        print(f"   Risk/Reward: {(df['risk_reward_ratio'] >= 2.0).sum()} tickers with R:R >= 2")

    # ─── EU Insider bonus (15 pts max) ───────────────────────────────────────
    # Data source: docs/eu_recurring_insiders.csv (generated by european_insider_scanner.py)
    # Coverage: primarily FTSE100 (.L) with partial AEX25 (.AS)
    eu_insiders_path = Path('docs/eu_recurring_insiders.csv')
    if eu_insiders_path.exists():
        try:
            eu_ins = pd.read_csv(eu_insiders_path)
            if not eu_ins.empty and 'ticker' in eu_ins.columns and 'confidence_score' in eu_ins.columns:
                ins_map = eu_ins.set_index('ticker')['confidence_score'].to_dict()
                df['eu_insider_score'] = df['ticker'].map(ins_map).fillna(0.0)
                df['eu_insider_bonus'] = 0.0
                df.loc[df['eu_insider_score'] >= 60, 'eu_insider_bonus'] = 15.0
                df.loc[(df['eu_insider_score'] >= 40) & (df['eu_insider_score'] < 60), 'eu_insider_bonus'] = 8.0
                df.loc[(df['eu_insider_score'] >= 20) & (df['eu_insider_score'] < 40), 'eu_insider_bonus'] = 4.0
                df['value_score'] += df['eu_insider_bonus']
                n_hits = (df['eu_insider_bonus'] > 0).sum()
                print(f"   EU Insider bonus: {n_hits} tickers awarded points (FTSE100/AEX25 coverage)")
                df.drop(columns=['eu_insider_score'], inplace=True, errors='ignore')
        except Exception as e:
            print(f"   EU Insider bonus: skipped ({e})")

    # ─── COVERAGE CHECK: Penalize no analyst coverage ───
    if 'analyst_count' in df.columns:
        no_coverage = df['analyst_count'].isna() | (df['analyst_count'] == 0)
        if no_coverage.sum() > 0:
            df.loc[no_coverage, 'value_score'] = df.loc[no_coverage, 'value_score'] * 0.85
            print(f"   No analyst coverage: {no_coverage.sum()} tickers (-15%)")

    # ─── Market regime penalty ───
    regime = market_regime.get('regime', 'UNKNOWN')
    if regime == 'CORRECTION':
        print(f"   Market CORRECTION: -10% to all scores")
        df['value_score'] = df['value_score'] * 0.90

    df['value_score'] = df['value_score'].clip(lower=0, upper=100).round(1)

    # ─── Add market regime to all rows ───
    df['market_regime'] = regime

    # ─── Filter: minimum value_score >= 25 ───
    qualified = df[df['value_score'] >= 25].copy()
    qualified = qualified.sort_values('value_score', ascending=False)

    print(f"\nRESULTADOS:")
    print(f"   Total scored: {len(df)}")
    print(f"   Qualified (score >= 25): {len(qualified)}")
    if len(qualified) > 0:
        print(f"   Top score: {qualified['value_score'].max():.1f}")
        print(f"   Average score: {qualified['value_score'].mean():.1f}")
        print(f"\n   TOP 10:")
        for _, row in qualified.head(10).iterrows():
            print(f"     {row['ticker']:<10} {row.get('company_name', '')[:25]:<25} Score: {row['value_score']:.1f}  Market: {row.get('market', '')}")

    return qualified


def run_european_scanner(max_tickers: int = None, skip_scoring: bool = False,
                         use_curated: bool = False):
    """
    Pipeline completo del scanner europeo

    Args:
        max_tickers: Limitar tickers (para testing)
        skip_scoring: Usar scores existentes de european_fundamental_scores.csv
        use_curated: Usar universo curado de curated_tickers_eu.py (~58 empresas)
                     en lugar del universo amplio (~200 tickers de índices)
    """
    print("\n" + "=" * 70)
    print("EUROPEAN VALUE SCANNER")
    print("=" * 70)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # 1. Detect European market regime
    market_regime = detect_european_market_regime()
    time.sleep(1)

    # 2. Score fundamentals (or load existing)
    scores_path = Path('docs/european_fundamental_scores.csv')

    # Auto-skip if CSV is fresh (<24h old)
    auto_skip = False
    if scores_path.exists() and not skip_scoring:
        import os
        file_age_hours = (time.time() - os.path.getmtime(scores_path)) / 3600
        if file_age_hours < 24:
            auto_skip = True
            print(f"\nCSV reciente ({file_age_hours:.1f}h) — reutilizando scores existentes")

    if (skip_scoring or auto_skip) and scores_path.exists():
        print(f"Cargando scores existentes de {scores_path}")
        df = pd.read_csv(scores_path)
    else:
        df = score_european_tickers(max_tickers=max_tickers, use_curated=use_curated)

    if df.empty:
        print("No hay datos para procesar")
        return

    # 3. Calculate European value scores
    qualified = calculate_european_value_scores(df, market_regime)

    if qualified.empty:
        print("No hay oportunidades europeas calificadas")
        # Save empty CSV so dashboard doesn't break
        pd.DataFrame().to_csv('docs/european_value_opportunities.csv', index=False)
        return

    # 4. Save opportunities
    output_path = Path('docs/european_value_opportunities.csv')
    qualified.to_csv(output_path, index=False)
    print(f"\nGuardado: {output_path} ({len(qualified)} oportunidades)")

    # 5. Summary by market
    print(f"\nPOR MERCADO:")
    if 'market' in qualified.columns:
        for market, group in qualified.groupby('market'):
            print(f"   {market}: {len(group)} tickers | Avg score: {group['value_score'].mean():.1f}")

    return qualified


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='European Value Scanner')
    parser.add_argument('--max', type=int, help='Max tickers to scan (for testing)')
    parser.add_argument('--skip-scoring', action='store_true',
                        help='Skip fundamental scoring, use existing CSV')
    parser.add_argument('--curated', action='store_true',
                        help='Use curated EU universe (~58 quality companies) instead of broad index (~200 tickers)')
    args = parser.parse_args()

    run_european_scanner(max_tickers=args.max, skip_scoring=args.skip_scoring,
                         use_curated=args.curated)
