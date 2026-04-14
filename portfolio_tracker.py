#!/usr/bin/env python3
"""
PORTFOLIO TRACKER — Track recommendations and measure real performance
Records each VALUE/MOMENTUM recommendation with price at signal date.
Checks 7d, 14d, 30d returns to calculate real win rate.
Learns which signals actually work.
"""
import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta
import json
import time
import argparse


TRACKER_DIR = Path('docs/portfolio_tracker')
RECOMMENDATIONS_FILE = TRACKER_DIR / 'recommendations.csv'
PERFORMANCE_FILE = TRACKER_DIR / 'performance.csv'
SUMMARY_FILE = TRACKER_DIR / 'summary.json'
CALIBRATION_FILE = TRACKER_DIR / 'calibration.json'


class PortfolioTracker:
    """Track recommendations and measure real-world results"""

    def __init__(self):
        TRACKER_DIR.mkdir(parents=True, exist_ok=True)
        self.recommendations = self._load_recommendations()

    def _load_recommendations(self) -> pd.DataFrame:
        """Load existing recommendations history"""
        if RECOMMENDATIONS_FILE.exists():
            return pd.read_csv(RECOMMENDATIONS_FILE, parse_dates=['signal_date'])
        return pd.DataFrame(columns=[
            'ticker', 'company_name', 'strategy', 'signal_date', 'signal_price',
            'value_score', 'momentum_score', 'fcf_yield_pct', 'risk_reward_ratio',
            'analyst_upside_pct', 'sector', 'market_regime',
            'return_7d', 'return_14d', 'return_30d',
            'price_7d', 'price_14d', 'price_30d',
            'win_7d', 'win_14d', 'win_30d',
            'max_drawdown_30d', 'status'
        ])

    def record_signals(self):
        """Record today's VALUE + MOMENTUM recommendations"""
        today = pd.Timestamp.now().normalize()

        # Check if already recorded today
        if not self.recommendations.empty:
            existing_today = self.recommendations[
                self.recommendations['signal_date'] == today
            ]
            if len(existing_today) > 0:
                print(f"  Already recorded {len(existing_today)} signals for {today.date()}")
                return

        signals_recorded = 0

        # Record VALUE opportunities — only high-conviction signals (score ≥ 55, grade A/B)
        value_path = Path('docs/value_opportunities.csv')
        if value_path.exists():
            vdf = pd.read_csv(value_path)
            if not vdf.empty:
                # Apply minimum quality gate
                if 'value_score' in vdf.columns:
                    vdf = vdf[vdf['value_score'] >= 55]
                if 'conviction_grade' in vdf.columns:
                    vdf = vdf[vdf['conviction_grade'].isin(['A', 'B'])]
                vdf = vdf.head(6)  # max 6 picks per day
                for _, row in vdf.iterrows():
                    price = row.get('current_price', 0)
                    if not price or pd.isna(price) or float(price) <= 0:
                        continue
                    rec = {
                        'ticker': row['ticker'],
                        'company_name': str(row.get('company_name') or row['ticker']),
                        'strategy': 'VALUE',
                        'signal_date': today,
                        'signal_price': float(price),
                        'value_score': row.get('value_score'),
                        'momentum_score': None,
                        'fcf_yield_pct': row.get('fcf_yield_pct'),
                        'risk_reward_ratio': row.get('risk_reward_ratio'),
                        'analyst_upside_pct': row.get('analyst_upside_pct'),
                        'sector': row.get('sector', 'N/A'),
                        'market_regime': row.get('market_regime', 'N/A'),
                        'return_7d': None, 'return_14d': None, 'return_30d': None,
                        'price_7d': None, 'price_14d': None, 'price_30d': None,
                        'win_7d': None, 'win_14d': None, 'win_30d': None,
                        'max_drawdown_30d': None,
                        'status': 'ACTIVE'
                    }
                    self.recommendations = pd.concat(
                        [self.recommendations, pd.DataFrame([rec])],
                        ignore_index=True
                    )
                    signals_recorded += 1
                print(f"  Recorded {signals_recorded} VALUE signals")

        # Record MOMENTUM opportunities
        mom_recorded = 0
        momentum_path = Path('docs/momentum_opportunities_filtered.csv')
        if momentum_path.exists():
            mdf = pd.read_csv(momentum_path)
            if not mdf.empty:
                for _, row in mdf.iterrows():
                    price = row.get('current_price', 0)
                    if not price or pd.isna(price) or float(price) <= 0:
                        continue
                    rec = {
                        'ticker': row['ticker'],
                        'company_name': str(row.get('company_name') or row['ticker']),
                        'strategy': 'MOMENTUM',
                        'signal_date': today,
                        'signal_price': float(price),
                        'value_score': None,
                        'momentum_score': row.get('momentum_score'),
                        'fcf_yield_pct': row.get('fcf_yield_pct'),
                        'risk_reward_ratio': row.get('risk_reward_ratio'),
                        'analyst_upside_pct': row.get('analyst_upside_pct'),
                        'sector': row.get('sector', 'N/A'),
                        'market_regime': row.get('market_regime', 'N/A'),
                        'return_7d': None, 'return_14d': None, 'return_30d': None,
                        'price_7d': None, 'price_14d': None, 'price_30d': None,
                        'win_7d': None, 'win_14d': None, 'win_30d': None,
                        'max_drawdown_30d': None,
                        'status': 'ACTIVE'
                    }
                    self.recommendations = pd.concat(
                        [self.recommendations, pd.DataFrame([rec])],
                        ignore_index=True
                    )
                    mom_recorded += 1
                print(f"  Recorded {mom_recorded} MOMENTUM signals")

        # Record EUROPEAN VALUE opportunities — only high-conviction signals (score ≥ 55, grade A/B)
        eu_recorded = 0
        for eu_path in [Path('docs/european_value_conviction.csv'), Path('docs/european_value_opportunities_filtered.csv')]:
            if eu_path.exists():
                break
        if eu_path.exists():
            edf = pd.read_csv(eu_path)
            if not edf.empty:
                if 'value_score' in edf.columns:
                    edf = edf[edf['value_score'] >= 55]
                if 'conviction_grade' in edf.columns:
                    edf = edf[edf['conviction_grade'].isin(['A', 'B'])]
                edf = edf.head(6)
                for _, row in edf.iterrows():
                    price = row.get('current_price', 0)
                    if not price or pd.isna(price) or float(price) <= 0:
                        continue
                    rec = {
                        'ticker': row['ticker'],
                        'company_name': str(row.get('company_name') or row['ticker']),
                        'strategy': 'EU_VALUE',
                        'signal_date': today,
                        'signal_price': float(price),
                        'value_score': row.get('value_score'),
                        'momentum_score': None,
                        'fcf_yield_pct': row.get('fcf_yield_pct'),
                        'risk_reward_ratio': row.get('risk_reward_ratio'),
                        'analyst_upside_pct': row.get('analyst_upside_pct'),
                        'sector': row.get('sector', 'N/A'),
                        'market_regime': row.get('market_regime', 'N/A'),
                        'return_7d': None, 'return_14d': None, 'return_30d': None,
                        'price_7d': None, 'price_14d': None, 'price_30d': None,
                        'win_7d': None, 'win_14d': None, 'win_30d': None,
                        'max_drawdown_30d': None,
                        'status': 'ACTIVE'
                    }
                    self.recommendations = pd.concat(
                        [self.recommendations, pd.DataFrame([rec])],
                        ignore_index=True
                    )
                    eu_recorded += 1
                print(f"  Recorded {eu_recorded} EU_VALUE signals")

        total = signals_recorded + mom_recorded + eu_recorded
        print(f"  Total new signals recorded: {total}")
        self._save_recommendations()

    def update_performance(self):
        """Check actual returns for past recommendations"""
        if self.recommendations.empty:
            print("  No recommendations to update")
            return

        today = pd.Timestamp.now().normalize()
        updated = 0

        # Group by ticker to batch yfinance calls
        active = self.recommendations[self.recommendations['status'] == 'ACTIVE'].copy()
        tickers_to_check = active['ticker'].unique()

        print(f"  Checking {len(tickers_to_check)} tickers for performance updates...")

        for ticker in tickers_to_check:
            ticker_recs = self.recommendations[
                (self.recommendations['ticker'] == ticker) &
                (self.recommendations['status'] == 'ACTIVE')
            ]

            # Fetch price history
            try:
                stock = yf.Ticker(ticker)
                earliest_date = ticker_recs['signal_date'].min()
                start_date = pd.Timestamp(earliest_date) - timedelta(days=1)
                hist = stock.history(
                    start=start_date.strftime('%Y-%m-%d'),
                    end=(today + timedelta(days=1)).strftime('%Y-%m-%d')
                )
                if hist.empty:
                    continue

                # yfinance returns tz-aware index; strip tz to allow naive comparisons
                if hist.index.tz is not None:
                    hist.index = hist.index.tz_localize(None)

                for idx, rec in ticker_recs.iterrows():
                    signal_date = pd.Timestamp(rec['signal_date'])
                    signal_price = float(rec['signal_price'])
                    days_since = (today - signal_date).days

                    # Get prices at 7d, 14d, 30d checkpoints
                    for period, col_return, col_price, col_win in [
                        (7, 'return_7d', 'price_7d', 'win_7d'),
                        (14, 'return_14d', 'price_14d', 'win_14d'),
                        (30, 'return_30d', 'price_30d', 'win_30d'),
                    ]:
                        if days_since >= period and pd.isna(rec.get(col_return)):
                            check_date = signal_date + timedelta(days=period)
                            # Find closest trading day
                            mask = hist.index >= check_date
                            if mask.any():
                                check_price = float(hist.loc[mask, 'Close'].iloc[0])
                                # LSE GBp/GBP sanity: if prices differ by ~100x, correct
                                if signal_price > 0 and check_price > 0:
                                    ratio = check_price / signal_price
                                    if ratio < 0.02:   # signal in GBp, fetch in GBP
                                        check_price = check_price * 100
                                    elif ratio > 50:   # signal in GBP, fetch in GBp
                                        check_price = check_price / 100
                                pct_return = ((check_price - signal_price) / signal_price) * 100
                                self.recommendations.at[idx, col_return] = round(pct_return, 2)
                                self.recommendations.at[idx, col_price] = round(check_price, 2)
                                self.recommendations.at[idx, col_win] = pct_return > 0
                                updated += 1

                    # Max drawdown over 30 days
                    if days_since >= 7 and pd.isna(rec.get('max_drawdown_30d')):
                        window_end = min(signal_date + timedelta(days=30), today)
                        window = hist[(hist.index >= signal_date) & (hist.index <= window_end)]
                        if not window.empty:
                            min_price = float(window['Low'].min())
                            drawdown = ((min_price - signal_price) / signal_price) * 100
                            self.recommendations.at[idx, 'max_drawdown_30d'] = round(drawdown, 2)

                    # Mark completed if 30d has passed
                    if days_since >= 30 and not pd.isna(self.recommendations.at[idx, 'return_30d']):
                        self.recommendations.at[idx, 'status'] = 'COMPLETED'

                time.sleep(1.0)  # Rate limiting

            except Exception as e:
                print(f"    Error checking {ticker}: {e}")
                continue

        print(f"  Updated {updated} performance checkpoints")
        self._save_recommendations()

    def generate_summary(self) -> dict:
        """Generate performance summary statistics"""
        if self.recommendations.empty:
            summary = {
                'total_signals': 0,
                'message': 'No recommendations tracked yet',
                'generated_at': datetime.now().isoformat()
            }
            self._save_summary(summary)
            return summary

        df = self.recommendations

        # Overall stats
        total = len(df)
        unique_tickers = df['ticker'].nunique()
        date_range = f"{df['signal_date'].min().date()} to {df['signal_date'].max().date()}"

        # Win rates by period
        def win_stats(col_return, col_win):
            valid = df[df[col_return].notna()]
            if valid.empty:
                return {'count': 0, 'win_rate': None, 'avg_return': None,
                        'median_return': None, 'best': None, 'worst': None}
            wins = valid[valid[col_win] == True]
            return {
                'count': len(valid),
                'win_rate': round(len(wins) / len(valid) * 100, 1),
                'avg_return': round(valid[col_return].mean(), 2),
                'median_return': round(valid[col_return].median(), 2),
                'best': round(valid[col_return].max(), 2),
                'worst': round(valid[col_return].min(), 2),
            }

        # By strategy
        value_df = df[df['strategy'] == 'VALUE']
        mom_df = df[df['strategy'] == 'MOMENTUM']

        # Conviction slice: value_score ≥ 55 (matches frontend default filter)
        conviction_df = df[df['value_score'].notna() & (df['value_score'] >= 55)]

        # Sector analysis
        sector_perf = {}
        for sector in df['sector'].unique():
            sdf = df[(df['sector'] == sector) & df['return_14d'].notna()]
            if len(sdf) >= 2:
                sector_perf[sector] = {
                    'count': len(sdf),
                    'avg_14d': round(sdf['return_14d'].mean(), 2),
                    'win_rate_14d': round((sdf['win_14d'] == True).sum() / len(sdf) * 100, 1)
                }

        # Score correlation — do higher scores = better returns?
        score_corr = None
        if not value_df.empty and value_df['return_14d'].notna().sum() >= 5:
            valid = value_df[value_df['return_14d'].notna() & value_df['value_score'].notna()]
            if len(valid) >= 5:
                score_corr = round(valid['value_score'].corr(valid['return_14d']), 3)

        # Ensure company_name column exists (backfill from ticker for old rows)
        if 'company_name' not in df.columns:
            df['company_name'] = df['ticker']
        else:
            df['company_name'] = df['company_name'].fillna(df['ticker'])

        # Top/Bottom performers — deduplicated by ticker, extreme returns excluded (data errors)
        perf_cols = ['ticker', 'company_name', 'strategy', 'signal_date', 'signal_price', 'return_14d']
        # Filter out likely data errors: LSE pence/GBP mismatch causes -99%, splits cause +900%
        valid_ret = df[df['return_14d'].notna() & (df['return_14d'] > -95) & (df['return_14d'] < 500)]
        if not valid_ret.empty:
            top_by_ticker = valid_ret.loc[valid_ret.groupby('ticker')['return_14d'].idxmax()]
            bot_by_ticker = valid_ret.loc[valid_ret.groupby('ticker')['return_14d'].idxmin()]
            top5 = top_by_ticker.sort_values('return_14d', ascending=False).head(5)[perf_cols].to_dict('records')
            bottom5 = bot_by_ticker.sort_values('return_14d').head(5)[perf_cols].to_dict('records')
        else:
            top5 = []
            bottom5 = []

        # Recent active signals (last 20, most recent first) — shown while waiting for returns
        active_df = df[df['status'] == 'ACTIVE'].sort_values('signal_date', ascending=False)
        signal_cols = ['ticker', 'company_name', 'strategy', 'signal_date', 'signal_price', 'sector', 'value_score']
        recent_signals = active_df.head(20)[
            [c for c in signal_cols if c in active_df.columns]
        ].to_dict('records')
        # Add days_active and first_result_date for UI display
        today_ts = pd.Timestamp.now().normalize()
        for s in recent_signals:
            sig_dt = pd.Timestamp(s['signal_date'])
            s['days_active'] = int((today_ts - sig_dt).days)
            s['first_result_date'] = (sig_dt + pd.Timedelta(days=7)).strftime('%Y-%m-%d')
            s['signal_date'] = sig_dt.strftime('%Y-%m-%d')

        summary = {
            'total_signals': total,
            'unique_tickers': unique_tickers,
            'date_range': date_range,
            'active_signals': int((df['status'] == 'ACTIVE').sum()),
            'completed_signals': int((df['status'] == 'COMPLETED').sum()),

            'overall': {
                '7d': win_stats('return_7d', 'win_7d'),
                '14d': win_stats('return_14d', 'win_14d'),
                '30d': win_stats('return_30d', 'win_30d'),
            },

            # High-conviction only (score ≥ 55) — the real signal quality metric
            'conviction': {
                '7d': (lambda d: {
                    'count': 0, 'win_rate': None, 'avg_return': None
                } if d.empty or d['return_7d'].notna().sum() == 0 else {
                    'count': int(d['return_7d'].notna().sum()),
                    'win_rate': round((d[d['win_7d'] == True]['return_7d'].notna().sum()) / d['return_7d'].notna().sum() * 100, 1),
                    'avg_return': round(d['return_7d'].dropna().mean(), 2),
                })(conviction_df),
            },

            'value_strategy': {
                'count': len(value_df),
                '7d': win_stats('return_7d', 'win_7d') if not value_df.empty else {},
                '14d': win_stats('return_14d', 'win_14d') if not value_df.empty else {},
                '30d': win_stats('return_30d', 'win_30d') if not value_df.empty else {},
            },

            'momentum_strategy': {
                'count': len(mom_df),
                '7d': win_stats('return_7d', 'win_7d') if not mom_df.empty else {},
                '14d': win_stats('return_14d', 'win_14d') if not mom_df.empty else {},
                '30d': win_stats('return_30d', 'win_30d') if not mom_df.empty else {},
            },

            'sector_performance': sector_perf,
            'score_correlation': score_corr,
            'top_performers': top5,
            'worst_performers': bottom5,
            'recent_signals': recent_signals,

            'avg_max_drawdown': round(df['max_drawdown_30d'].mean(), 2) if df['max_drawdown_30d'].notna().sum() > 0 else None,

            'generated_at': datetime.now().isoformat()
        }

        self._save_summary(summary)
        self.generate_calibration()
        return summary

    def generate_calibration(self):
        """Compute score/regime/sector calibration — does a higher score actually predict better returns?"""
        df = self.recommendations
        completed = df[df['return_14d'].notna() & (df['return_14d'] > -95) & (df['return_14d'] < 500)]
        if len(completed) < 10:
            return

        def bucket_stats(subset):
            if subset.empty:
                return None
            wins = (subset['win_14d'] == True).sum()
            return {
                'count': int(len(subset)),
                'win_rate_14d': round(wins / len(subset) * 100, 1),
                'avg_return_14d': round(subset['return_14d'].mean(), 2),
                'median_return_14d': round(subset['return_14d'].median(), 2),
            }

        # Score buckets
        score_buckets = []
        breaks = [(50, 55), (55, 60), (60, 65), (65, 70), (70, 75), (75, 200)]
        for lo, hi in breaks:
            sub = completed[completed['value_score'].notna() &
                            (completed['value_score'] >= lo) & (completed['value_score'] < hi)]
            stats = bucket_stats(sub)
            if stats:
                stats['range'] = f'{lo}-{hi}' if hi < 200 else f'{lo}+'
                score_buckets.append(stats)

        # Market regime
        regime_rows = []
        for regime in completed['market_regime'].dropna().unique():
            sub = completed[completed['market_regime'] == regime]
            stats = bucket_stats(sub)
            if stats:
                stats['regime'] = regime
                regime_rows.append(stats)
        regime_rows.sort(key=lambda x: -x['count'])

        # Sector calibration (min 5 signals)
        sector_rows = []
        for sector in completed['sector'].dropna().unique():
            sub = completed[completed['sector'] == sector]
            if len(sub) < 5:
                continue
            stats = bucket_stats(sub)
            if stats:
                stats['sector'] = sector
                sector_rows.append(stats)
        sector_rows.sort(key=lambda x: -x['win_rate_14d'])

        # FCF yield buckets (only where available)
        fcf_df = completed[completed['fcf_yield_pct'].notna()].copy()
        fcf_buckets = []
        fcf_breaks = [(-99, 0, 'Negative'), (0, 3, '0-3%'), (3, 6, '3-6%'), (6, 12, '6-12%'), (12, 999, '12%+')]
        for lo, hi, label in fcf_breaks:
            sub = fcf_df[(fcf_df['fcf_yield_pct'] >= lo) & (fcf_df['fcf_yield_pct'] < hi)]
            stats = bucket_stats(sub)
            if stats:
                stats['range'] = label
                fcf_buckets.append(stats)

        calibration = {
            'score_buckets': score_buckets,
            'regime_analysis': regime_rows,
            'sector_calibration': sector_rows,
            'fcf_yield_buckets': fcf_buckets,
            'total_completed': int(len(completed)),
            'generated_at': datetime.now().isoformat(),
        }

        def convert(obj):
            if isinstance(obj, (np.integer, np.floating)):
                return float(obj)
            if isinstance(obj, np.bool_):
                return bool(obj)
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [convert(i) for i in obj]
            return obj

        with open(CALIBRATION_FILE, 'w') as f:
            json.dump(convert(calibration), f, indent=2)
        print(f'  Calibration saved: {CALIBRATION_FILE}')

    def print_report(self, summary: dict):
        """Print formatted performance report"""
        print("\n" + "=" * 80)
        print("PORTFOLIO TRACKER — PERFORMANCE REPORT")
        print("=" * 80)

        print(f"\n  Total signals tracked: {summary['total_signals']}")
        print(f"  Unique tickers: {summary.get('unique_tickers', 'N/A')}")
        print(f"  Period: {summary.get('date_range', 'N/A')}")
        print(f"  Active: {summary.get('active_signals', 0)} | Completed: {summary.get('completed_signals', 0)}")

        for label, key in [('OVERALL', 'overall'), ('VALUE', 'value_strategy'), ('MOMENTUM', 'momentum_strategy')]:
            data = summary.get(key, {})
            if not data:
                continue
            print(f"\n  --- {label} ---")
            for period in ['7d', '14d', '30d']:
                stats = data.get(period, {})
                if not stats or stats.get('count', 0) == 0:
                    continue
                wr = stats.get('win_rate')
                avg = stats.get('avg_return')
                n = stats.get('count')
                wr_str = f"{wr}%" if wr is not None else "N/A"
                avg_str = f"{avg:+.2f}%" if avg is not None else "N/A"
                print(f"    {period}: Win Rate {wr_str} | Avg {avg_str} | n={n}")

        # Score correlation
        corr = summary.get('score_correlation')
        if corr is not None:
            direction = "POSITIVE" if corr > 0.1 else ("NEGATIVE" if corr < -0.1 else "WEAK")
            print(f"\n  Score → Return correlation: {corr} ({direction})")
            if corr > 0.1:
                print("    Higher scores DO predict better returns")
            elif corr < -0.1:
                print("    WARNING: Higher scores predict WORSE returns!")

        # Top/Bottom
        top = summary.get('top_performers', [])
        if top:
            print(f"\n  TOP 5 PERFORMERS:")
            for t in top:
                sig_date = str(t.get('signal_date', ''))[:10]
                print(f"    {t['ticker']:6} {t['strategy']:8} {sig_date} ${t.get('signal_price', 0):>8.2f} → {t['return_14d']:+.1f}%")

        bottom = summary.get('worst_performers', [])
        if bottom:
            print(f"\n  WORST 5 PERFORMERS:")
            for t in bottom:
                sig_date = str(t.get('signal_date', ''))[:10]
                print(f"    {t['ticker']:6} {t['strategy']:8} {sig_date} ${t.get('signal_price', 0):>8.2f} → {t['return_14d']:+.1f}%")

        dd = summary.get('avg_max_drawdown')
        if dd is not None:
            print(f"\n  Average Max Drawdown (30d): {dd:.1f}%")

        print("\n" + "=" * 80)

    def _save_recommendations(self):
        """Save recommendations to CSV"""
        self.recommendations.to_csv(RECOMMENDATIONS_FILE, index=False)

    def _save_summary(self, summary: dict):
        """Save summary to JSON"""
        # Convert Timestamps to strings for JSON
        def convert(obj):
            if isinstance(obj, (pd.Timestamp, datetime)):
                return str(obj)
            if isinstance(obj, (np.integer, np.floating)):
                return float(obj)
            if isinstance(obj, np.bool_):
                return bool(obj)
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [convert(i) for i in obj]
            if pd.isna(obj) if isinstance(obj, float) else False:
                return None
            return obj

        with open(SUMMARY_FILE, 'w') as f:
            json.dump(convert(summary), f, indent=2, default=str)
        print(f"  Summary saved: {SUMMARY_FILE}")


def main():
    parser = argparse.ArgumentParser(description='Portfolio Tracker')
    parser.add_argument('--record', action='store_true', help='Record today\'s signals')
    parser.add_argument('--update', action='store_true', help='Update performance for past signals')
    parser.add_argument('--report', action='store_true', help='Generate and print performance report')
    parser.add_argument('--all', action='store_true', help='Record + Update + Report')
    args = parser.parse_args()

    if not any([args.record, args.update, args.report, args.all]):
        args.all = True

    tracker = PortfolioTracker()

    print("\n" + "=" * 80)
    print("PORTFOLIO TRACKER")
    print("=" * 80)

    if args.record or args.all:
        print("\n1. RECORDING TODAY'S SIGNALS")
        print("-" * 40)
        tracker.record_signals()

    if args.update or args.all:
        print("\n2. UPDATING PERFORMANCE")
        print("-" * 40)
        tracker.update_performance()

    if args.report or args.all:
        print("\n3. GENERATING REPORT")
        print("-" * 40)
        summary = tracker.generate_summary()
        tracker.print_report(summary)

    print("\nDone!")


if __name__ == '__main__':
    main()
