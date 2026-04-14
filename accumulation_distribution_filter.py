#!/usr/bin/env python3
"""
ACCUMULATION/DISTRIBUTION FILTER
Detecta acumulación institucional vs distribución

Basado en metodología CAN SLIM:
- Institutional sponsorship (grandes fondos comprando)
- Volume patterns (volume en días alcistas > días bajistas)
- Price/Volume relationship (breakouts con volumen)

Signals:
- STRONG_ACCUMULATION: Instituciones comprando agresivamente
- ACCUMULATION: Compra institucional moderada
- NEUTRAL: Sin patrón claro
- DISTRIBUTION: Instituciones vendiendo
- STRONG_DISTRIBUTION: Venta institucional agresiva
"""
import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime
from pathlib import Path


class AccumulationDistributionFilter:
    """Detecta acumulación/distribución institucional"""

    def __init__(self):
        self.cache_dir = Path('cache/ad_filter')
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def analyze_stock(self, ticker: str, period_days: int = 50, verbose: bool = False) -> Dict:
        """
        Analiza acumulación/distribución de un stock

        Args:
            ticker: Symbol del stock
            period_days: Días a analizar (default 50)
            verbose: Si imprimir detalles

        Returns:
            Dict con:
            - signal: STRONG_ACCUMULATION | ACCUMULATION | NEUTRAL | DISTRIBUTION | STRONG_DISTRIBUTION
            - score: 0-100 (100 = fuerte acumulación)
            - volume_ratio: ratio volumen días alcistas / bajistas
            - up_volume_pct: % volumen en días alcistas
            - recent_institutional_buying: bool
        """
        if verbose:
            print(f"\n📊 Analyzing A/D: {ticker}")

        try:
            # Get data
            stock = yf.Ticker(ticker)
            hist = stock.history(period='3mo')

            if hist.empty or len(hist) < period_days:
                return {
                    'ticker': ticker,
                    'signal': 'UNKNOWN',
                    'score': 50,
                    'reason': 'Insufficient data',
                    'details': {}
                }

            # Take last N days
            df = hist.tail(period_days).copy()

            # Calculate price changes
            df['price_change'] = df['Close'].diff()
            df['price_pct_change'] = df['Close'].pct_change() * 100

            # Classify days as up/down
            df['is_up_day'] = df['price_change'] > 0
            df['is_down_day'] = df['price_change'] < 0

            # Calculate volume metrics
            up_days_volume = df[df['is_up_day']]['Volume'].sum()
            down_days_volume = df[df['is_down_day']]['Volume'].sum()
            total_volume = df['Volume'].sum()

            # Avoid division by zero
            if down_days_volume == 0:
                volume_ratio = 10.0  # Very bullish
            else:
                volume_ratio = up_days_volume / down_days_volume

            up_volume_pct = (up_days_volume / total_volume * 100) if total_volume > 0 else 50

            # Count up/down days
            up_days_count = int(df['is_up_day'].sum())
            down_days_count = int(df['is_down_day'].sum())

            # Calculate average volume on up vs down days
            avg_up_volume = df[df['is_up_day']]['Volume'].mean() if up_days_count > 0 else 0
            avg_down_volume = df[df['is_down_day']]['Volume'].mean() if down_days_count > 0 else 0

            # Volume surge detection (recent 5 days)
            recent_volume = df.tail(5)['Volume'].mean()
            baseline_volume = df['Volume'].mean()
            volume_surge = (recent_volume / baseline_volume) if baseline_volume > 0 else 1.0

            # Check for institutional buying (large volume + price up)
            recent_5d = df.tail(5)
            institutional_buying = False
            if len(recent_5d) >= 5:
                # Look for days with both high volume and price increase
                institutional_days = recent_5d[
                    (recent_5d['is_up_day']) &
                    (recent_5d['Volume'] > baseline_volume * 1.5)
                ]
                institutional_buying = len(institutional_days) >= 2

            # Determine signal and score
            signal, score = self._determine_ad_signal(
                volume_ratio,
                up_volume_pct,
                institutional_buying,
                volume_surge
            )

            result = {
                'ticker': ticker,
                'signal': signal,
                'score': int(score),
                'reason': self._get_signal_explanation(signal, volume_ratio, up_volume_pct),
                'details': {
                    'volume_ratio': float(round(volume_ratio, 2)),
                    'up_volume_pct': float(round(up_volume_pct, 1)),
                    'down_volume_pct': float(round(100 - up_volume_pct, 1)),
                    'up_days_count': up_days_count,
                    'down_days_count': down_days_count,
                    'avg_up_volume': float(int(avg_up_volume)),
                    'avg_down_volume': float(int(avg_down_volume)),
                    'volume_surge': float(round(volume_surge, 2)),
                    'institutional_buying': bool(institutional_buying),
                    'period_days': period_days
                }
            }

            if verbose:
                signal_emoji = {
                    'STRONG_ACCUMULATION': '🟢',
                    'ACCUMULATION': '🟡',
                    'NEUTRAL': '⚪',
                    'DISTRIBUTION': '🟠',
                    'STRONG_DISTRIBUTION': '🔴'
                }.get(signal, '❓')
                print(f"   {signal_emoji} {signal} (Score: {score}/100)")
                print(f"   Up Volume: {up_volume_pct:.1f}% | Ratio: {volume_ratio:.2f}x")
                print(f"   Institutional Buying: {'Yes' if institutional_buying else 'No'}")

            return result

        except Exception as e:
            if verbose:
                print(f"   ❌ Error: {str(e)}")
            return {
                'ticker': ticker,
                'signal': 'UNKNOWN',
                'score': 50,
                'reason': f'Error: {str(e)}',
                'details': {}
            }

    def _determine_ad_signal(
        self,
        volume_ratio: float,
        up_volume_pct: float,
        institutional_buying: bool,
        volume_surge: float
    ) -> tuple:
        """
        Determina señal de A/D y score

        Returns:
            (signal, score)
        """
        score = 50  # Start neutral

        # Volume ratio scoring
        if volume_ratio >= 2.0:
            score += 30
            signal = 'STRONG_ACCUMULATION'
        elif volume_ratio >= 1.5:
            score += 20
            signal = 'ACCUMULATION'
        elif volume_ratio >= 1.0:
            score += 10
            signal = 'ACCUMULATION'
        elif volume_ratio >= 0.7:
            score -= 10
            signal = 'NEUTRAL'
        elif volume_ratio >= 0.5:
            score -= 20
            signal = 'DISTRIBUTION'
        else:
            score -= 30
            signal = 'STRONG_DISTRIBUTION'

        # Up volume percentage adjustment
        if up_volume_pct >= 65:
            score += 15
        elif up_volume_pct >= 55:
            score += 5
        elif up_volume_pct <= 35:
            score -= 15
        elif up_volume_pct <= 45:
            score -= 5

        # Institutional buying bonus
        if institutional_buying:
            score += 10
            if signal == 'ACCUMULATION':
                signal = 'STRONG_ACCUMULATION'

        # Volume surge bonus
        if volume_surge >= 1.5:
            score += 5

        # Ensure signal matches score
        if score >= 75:
            signal = 'STRONG_ACCUMULATION'
        elif score >= 60:
            signal = 'ACCUMULATION'
        elif score >= 40:
            signal = 'NEUTRAL'
        elif score >= 25:
            signal = 'DISTRIBUTION'
        else:
            signal = 'STRONG_DISTRIBUTION'

        # Clamp score
        score = max(0, min(100, score))

        return signal, score

    def _get_signal_explanation(self, signal: str, volume_ratio: float, up_volume_pct: float) -> str:
        """Genera explicación del signal"""
        if signal == 'STRONG_ACCUMULATION':
            return f"Strong institutional buying ({volume_ratio:.1f}x ratio, {up_volume_pct:.0f}% up volume)"
        elif signal == 'ACCUMULATION':
            return f"Moderate accumulation ({volume_ratio:.1f}x ratio, {up_volume_pct:.0f}% up volume)"
        elif signal == 'NEUTRAL':
            return f"No clear pattern ({volume_ratio:.1f}x ratio, {up_volume_pct:.0f}% up volume)"
        elif signal == 'DISTRIBUTION':
            return f"Moderate distribution ({volume_ratio:.1f}x ratio, {up_volume_pct:.0f}% up volume)"
        else:
            return f"Strong selling pressure ({volume_ratio:.1f}x ratio, {up_volume_pct:.0f}% up volume)"

    def filter_dataframe(
        self,
        df: pd.DataFrame,
        ticker_column: str = 'ticker',
        min_score: int = 60
    ) -> pd.DataFrame:
        """
        Filtra DataFrame aplicando A/D filter

        Args:
            df: DataFrame con columna de tickers
            ticker_column: Nombre de la columna con tickers
            min_score: Score mínimo para pasar (default 60)

        Returns:
            DataFrame con columnas de A/D
        """
        print(f"\n{'='*70}")
        print("📊 ACCUMULATION/DISTRIBUTION FILTER - Institutional Flow")
        print(f"{'='*70}\n")

        results = []
        total = len(df)

        for idx, ticker in enumerate(df[ticker_column], 1):
            print(f"[{idx}/{total}] Analyzing {ticker}...", end=' ')
            result = self.analyze_stock(ticker, period_days=50, verbose=False)
            results.append(result)

            signal_emoji = {
                'STRONG_ACCUMULATION': '🟢',
                'ACCUMULATION': '🟡',
                'NEUTRAL': '⚪',
                'DISTRIBUTION': '🟠',
                'STRONG_DISTRIBUTION': '🔴'
            }.get(result['signal'], '❓')
            print(f"{signal_emoji} {result['signal']} (Score: {result['score']}/100)")

        # Create results DataFrame
        results_df = pd.DataFrame(results)

        # Merge with original
        df_filtered = df.copy()
        df_filtered = df_filtered.merge(
            results_df[['ticker', 'signal', 'score', 'reason']].rename(columns={
                'signal': 'ad_signal',
                'score': 'ad_score',
                'reason': 'ad_reason'
            }),
            left_on=ticker_column,
            right_on='ticker',
            how='left'
        )

        # Add pass/fail flag
        df_filtered['ad_filter_pass'] = df_filtered['ad_score'] >= min_score

        # Summary
        passed = int(df_filtered['ad_filter_pass'].sum())
        failed = total - passed
        pass_rate = (passed / total * 100) if total > 0 else 0

        print(f"\n{'='*70}")
        print("📊 A/D FILTER SUMMARY")
        print(f"{'='*70}")
        print(f"✅ Accumulation: {passed}/{total} ({pass_rate:.1f}%)")
        print(f"❌ Distribution: {failed}/{total} ({100-pass_rate:.1f}%)")
        print(f"{'='*70}\n")

        return df_filtered


def main():
    """Test A/D filter"""
    import argparse

    parser = argparse.ArgumentParser(description='Test Accumulation/Distribution Filter')
    parser.add_argument('--ticker', help='Single ticker to test')
    parser.add_argument('--file', help='CSV file with tickers')
    parser.add_argument('--column', default='ticker', help='Ticker column name')
    args = parser.parse_args()

    filter_tool = AccumulationDistributionFilter()

    if args.ticker:
        # Test single ticker
        result = filter_tool.analyze_stock(args.ticker, verbose=True)
        print(f"\nResult: {result}")

    elif args.file:
        # Test file
        df = pd.read_csv(args.file)
        filtered = filter_tool.filter_dataframe(df, ticker_column=args.column)

        # Show top 10 accumulation
        top_acc = filtered.nlargest(10, 'ad_score')
        print("\n🔥 Top 10 Accumulation:")
        for _, row in top_acc.iterrows():
            print(f"   {row['ad_signal']:20s} {row['ticker']:6s} | Score: {row['ad_score']}/100")

    else:
        # Test on some stocks
        test_tickers = ['NVDA', 'AAPL', 'TSLA', 'META', 'MSFT']
        for ticker in test_tickers:
            filter_tool.analyze_stock(ticker, verbose=True)


if __name__ == '__main__':
    main()
