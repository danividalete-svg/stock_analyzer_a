#!/usr/bin/env python3
"""
FLOAT FILTER
Filtra stocks por float (shares outstanding)

Basado en CAN SLIM / Minervini:
- Preferir stocks con float bajo-medio (<50M shares)
- Float bajo = más fácil para instituciones mover el precio
- Float muy alto = difícil mover, menos volátil

Categories:
- MICRO_FLOAT: <10M shares (muy volátil, difícil de operar)
- LOW_FLOAT: 10M-25M shares (ideal para momentum)
- MEDIUM_FLOAT: 25M-50M shares (bueno, movimiento moderado)
- HIGH_FLOAT: 50M-200M shares (aceptable, menos volátil)
- MEGA_FLOAT: >200M shares (difícil de mover)
"""
import yfinance as yf
import pandas as pd
from typing import Dict
from pathlib import Path


class FloatFilter:
    """Filtra stocks por float (shares outstanding)"""

    def __init__(self):
        self.cache_dir = Path('cache/float_filter')
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def check_stock(self, ticker: str, verbose: bool = False) -> Dict:
        """
        Verifica el float de un stock

        Args:
            ticker: Symbol del stock
            verbose: Si imprimir detalles

        Returns:
            Dict con:
            - passes: bool (True si float <= 50M)
            - float_category: MICRO | LOW | MEDIUM | HIGH | MEGA
            - shares_outstanding: número de shares
            - score: 0-100 (100 = float ideal)
        """
        if verbose:
            print(f"\n📊 Checking Float: {ticker}")

        try:
            # Get stock info
            stock = yf.Ticker(ticker)
            info = stock.info

            # Get shares outstanding (float)
            shares_outstanding = info.get('sharesOutstanding')
            float_shares = info.get('floatShares')  # Sometimes more accurate

            # Use floatShares if available, otherwise sharesOutstanding
            shares = float_shares if float_shares else shares_outstanding

            if not shares or shares == 0:
                return {
                    'ticker': ticker,
                    'passes': False,
                    'float_category': 'UNKNOWN',
                    'shares_outstanding': None,
                    'shares_outstanding_millions': None,
                    'score': 50,
                    'reason': 'Float data not available'
                }

            shares_millions = shares / 1_000_000

            # Categorize float
            if shares_millions < 10:
                category = 'MICRO_FLOAT'
                score = 85  # Good but very volatile
                passes = True
            elif shares_millions < 25:
                category = 'LOW_FLOAT'
                score = 100  # Ideal
                passes = True
            elif shares_millions < 50:
                category = 'MEDIUM_FLOAT'
                score = 90  # Very good
                passes = True
            elif shares_millions < 200:
                category = 'HIGH_FLOAT'
                score = 60  # Acceptable
                passes = False
            else:
                category = 'MEGA_FLOAT'
                score = 30  # Hard to move
                passes = False

            # Get market cap for context
            market_cap = info.get('marketCap')
            market_cap_billions = market_cap / 1_000_000_000 if market_cap else None

            result = {
                'ticker': ticker,
                'passes': bool(passes),
                'float_category': category,
                'shares_outstanding': float(shares),
                'shares_outstanding_millions': float(round(shares_millions, 1)),
                'market_cap': float(market_cap) if market_cap else None,
                'market_cap_billions': float(round(market_cap_billions, 2)) if market_cap_billions else None,
                'score': int(score),
                'reason': self._get_category_explanation(category, shares_millions)
            }

            if verbose:
                status_emoji = '✅' if passes else '❌'
                cat_emoji = {
                    'MICRO_FLOAT': '🔥',
                    'LOW_FLOAT': '🟢',
                    'MEDIUM_FLOAT': '🟡',
                    'HIGH_FLOAT': '🟠',
                    'MEGA_FLOAT': '🔴'
                }.get(category, '⚪')
                print(f"   {status_emoji} {cat_emoji} {category}")
                print(f"   Float: {shares_millions:.1f}M shares")
                if market_cap_billions:
                    print(f"   Market Cap: ${market_cap_billions:.2f}B")
                print(f"   {result['reason']}")

            return result

        except Exception as e:
            if verbose:
                print(f"   ❌ Error: {str(e)}")
            return {
                'ticker': ticker,
                'passes': False,
                'float_category': 'UNKNOWN',
                'shares_outstanding': None,
                'shares_outstanding_millions': None,
                'score': 50,
                'reason': f'Error: {str(e)}'
            }

    def _get_category_explanation(self, category: str, shares_millions: float) -> str:
        """Genera explicación de la categoría"""
        if category == 'MICRO_FLOAT':
            return f"{shares_millions:.1f}M shares - Very low float, highly volatile"
        elif category == 'LOW_FLOAT':
            return f"{shares_millions:.1f}M shares - Ideal float for momentum"
        elif category == 'MEDIUM_FLOAT':
            return f"{shares_millions:.1f}M shares - Good float, moderate volatility"
        elif category == 'HIGH_FLOAT':
            return f"{shares_millions:.1f}M shares - High float, harder to move"
        else:
            return f"{shares_millions:.1f}M shares - Mega float, very hard to move"

    def filter_dataframe(
        self,
        df: pd.DataFrame,
        ticker_column: str = 'ticker',
        max_float_millions: float = 50.0
    ) -> pd.DataFrame:
        """
        Filtra DataFrame aplicando float filter

        Args:
            df: DataFrame con columna de tickers
            ticker_column: Nombre de la columna con tickers
            max_float_millions: Float máximo en millones (default 50M)

        Returns:
            DataFrame con columnas de float
        """
        print(f"\n{'='*70}")
        print(f"📊 FLOAT FILTER - Max {max_float_millions}M Shares")
        print(f"{'='*70}\n")

        results = []
        total = len(df)

        for idx, ticker in enumerate(df[ticker_column], 1):
            print(f"[{idx}/{total}] Checking {ticker}...", end=' ')
            result = self.check_stock(ticker, verbose=False)
            results.append(result)

            cat_emoji = {
                'MICRO_FLOAT': '🔥',
                'LOW_FLOAT': '🟢',
                'MEDIUM_FLOAT': '🟡',
                'HIGH_FLOAT': '🟠',
                'MEGA_FLOAT': '🔴',
                'UNKNOWN': '⚪'
            }.get(result['float_category'], '⚪')

            shares_str = f"{result['shares_outstanding_millions']:.1f}M" if result['shares_outstanding_millions'] else 'N/A'
            print(f"{cat_emoji} {result['float_category']} ({shares_str})")

        # Create results DataFrame
        results_df = pd.DataFrame(results)

        # Merge with original
        df_filtered = df.copy()
        df_filtered = df_filtered.merge(
            results_df[[
                'ticker', 'passes', 'float_category',
                'shares_outstanding_millions', 'market_cap_billions', 'score', 'reason'
            ]].rename(columns={
                'passes': 'float_filter_pass',
                'score': 'float_score',
                'reason': 'float_reason'
            }),
            left_on=ticker_column,
            right_on='ticker',
            how='left'
        )

        # Summary
        passed = int(df_filtered['float_filter_pass'].sum())
        failed = total - passed
        pass_rate = (passed / total * 100) if total > 0 else 0

        print(f"\n{'='*70}")
        print("📊 FLOAT FILTER SUMMARY")
        print(f"{'='*70}")
        print(f"✅ Low/Medium Float (<{max_float_millions}M): {passed}/{total} ({pass_rate:.1f}%)")
        print(f"❌ High Float (>{max_float_millions}M): {failed}/{total} ({100-pass_rate:.1f}%)")
        print(f"{'='*70}\n")

        return df_filtered


def main():
    """Test float filter"""
    import argparse

    parser = argparse.ArgumentParser(description='Test Float Filter')
    parser.add_argument('--ticker', help='Single ticker to test')
    parser.add_argument('--file', help='CSV file with tickers')
    parser.add_argument('--column', default='ticker', help='Ticker column name')
    args = parser.parse_args()

    filter_tool = FloatFilter()

    if args.ticker:
        # Test single ticker
        result = filter_tool.check_stock(args.ticker, verbose=True)
        print(f"\nResult: {result}")

    elif args.file:
        # Test file
        df = pd.read_csv(args.file)
        filtered = filter_tool.filter_dataframe(df, ticker_column=args.column)

        # Show low float stocks
        low_float = filtered[filtered['float_filter_pass'] == True]
        print(f"\n🔥 Low/Medium Float Stocks ({len(low_float)}):")
        for _, row in low_float.head(15).iterrows():
            shares = row['shares_outstanding_millions']
            print(f"   {row['float_category']:15s} {row['ticker']:6s} | {shares:.1f}M shares")

    else:
        # Test on some stocks
        test_tickers = ['NVDA', 'AAPL', 'TSLA', 'META', 'SMCI', 'PLTR']
        for ticker in test_tickers:
            filter_tool.check_stock(ticker, verbose=True)


if __name__ == '__main__':
    main()
