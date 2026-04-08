#!/usr/bin/env python3
"""
FUNDAMENTAL SCORING SYSTEM
Sistema completo de análisis fundamental para complementar señales técnicas

Componentes (Weighted Score 0-100):
1. Earnings Quality (30%) - Calidad y crecimiento de ganancias
2. Growth Acceleration (25%) - Aceleración de crecimiento
3. Relative Strength (20%) - Fuerza relativa vs mercado
4. Financial Health (15%) - Salud financiera
5. Catalyst Timing (10%) - Timing de catalizadores

No requiere API keys externas - solo yfinance
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
import time
import random
import argparse
from typing import Dict, List, Optional


def _yf_ticker_with_retry(ticker: str, max_retries: int = 4) -> yf.Ticker:
    """Return a yf.Ticker object, with a small initial delay to reduce 429s."""
    return yf.Ticker(ticker)


def _yf_info_with_retry(stock: yf.Ticker, max_retries: int = 4) -> dict:
    """Fetch .info with exponential backoff on 429 / rate-limit errors."""
    delay = 3.0
    for attempt in range(max_retries):
        try:
            info = stock.info
            # yfinance returns {} or {'trailingPegRatio': None, ...} on soft failures
            if info and len(info) > 5:
                return info
            # Short sleep and retry if response looks empty
            time.sleep(delay)
            delay = min(delay * 2, 30)
        except Exception as e:
            msg = str(e).lower()
            if '429' in msg or 'too many' in msg or 'rate' in msg:
                jitter = random.uniform(0, delay * 0.3)
                print(f"   ⏳ Rate limited — waiting {delay:.0f}s (attempt {attempt+1}/{max_retries})")
                time.sleep(delay + jitter)
                delay = min(delay * 2, 60)
            else:
                raise
    return {}

class FundamentalScorer:
    """Sistema de scoring fundamental completo"""

    def __init__(self, as_of_date: Optional[str] = None):
        """Initialize Fundamental Scorer

        Args:
            as_of_date: Historical date (YYYY-MM-DD) for scoring. Prevents look-ahead bias.
        """
        self.cache_dir = Path('cache/fundamentals')
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 🔴 FIX LOOK-AHEAD BIAS: Store as_of_date
        self.as_of_date = as_of_date
        if as_of_date:
            self.as_of_date_dt = datetime.strptime(as_of_date, '%Y-%m-%d')
            print(f"📅 Fundamental Scorer: Historical mode (as_of_date={as_of_date})")
        else:
            self.as_of_date_dt = datetime.now()

        # Weights para el fundamental score
        self.weights = {
            'earnings_quality': 0.30,    # 30% - Calidad de ganancias
            'growth_acceleration': 0.25, # 25% - Aceleración de crecimiento
            'relative_strength': 0.20,   # 20% - Fuerza relativa
            'financial_health': 0.15,    # 15% - Salud financiera
            'catalyst_timing': 0.10      # 10% - Timing de catalizadores
        }

    def score_ticker(self, ticker: str) -> Dict:
        """
        Análisis fundamental completo con scoring

        Returns:
            Dict con scores y detalles fundamentales
        """
        print(f"📊 Scoring fundamentales: {ticker}")

        try:
            stock = _yf_ticker_with_retry(ticker)
            info = _yf_info_with_retry(stock)
            if not info:
                print(f"   ❌ Error: sin datos de yfinance (rate limit persistente)")
                return self._get_empty_result(ticker)

            # Obtener datos necesarios
            quarterly_earnings = self._get_quarterly_earnings(stock)
            financials = self._get_financials(stock)
            price_history = self._get_price_history(stock)

            # Calcular cada componente del score
            earnings_score = self._calculate_earnings_quality_score(
                quarterly_earnings, info
            )

            growth_score = self._calculate_growth_acceleration_score(
                quarterly_earnings, financials
            )

            rs_score = self._calculate_relative_strength_score(
                price_history, ticker
            )

            health_score = self._calculate_financial_health_score(
                financials, info
            )

            catalyst_score = self._calculate_catalyst_timing_score(
                stock, info
            )

            # Calcular fundamental score total
            fundamental_score = (
                earnings_score['score'] * self.weights['earnings_quality'] +
                growth_score['score'] * self.weights['growth_acceleration'] +
                rs_score['score'] * self.weights['relative_strength'] +
                health_score['score'] * self.weights['financial_health'] +
                catalyst_score['score'] * self.weights['catalyst_timing']
            )

            # Determinar tier
            tier = self._get_tier(fundamental_score)
            quality = self._get_quality(fundamental_score)

            result = {
                'ticker': ticker,
                'company_name': info.get('shortName', ticker),
                'fundamental_score': round(fundamental_score, 1),
                'tier': tier,
                'quality': quality,

                # Componentes individuales
                'earnings_quality_score': earnings_score['score'],
                'growth_acceleration_score': growth_score['score'],
                'relative_strength_score': rs_score['score'],
                'financial_health_score': health_score['score'],
                'catalyst_timing_score': catalyst_score['score'],

                # RS Line flat columns (Minervini)
                'rs_line_score':       rs_score.get('rs_line_score'),
                'rs_line_percentile':  rs_score.get('rs_line_percentile'),
                'rs_line_at_new_high': rs_score.get('rs_line_at_new_high'),
                'rs_line_trend':       rs_score.get('rs_line_trend'),

                # CANSLIM "A" flat columns — EPS/Revenue Acceleration
                'eps_growth_yoy':    earnings_score.get('eps_growth_yoy'),
                'eps_accelerating':  earnings_score.get('eps_accelerating'),
                'eps_accel_quarters': earnings_score.get('eps_accel_quarters', 0),
                'rev_growth_yoy':    growth_score.get('rev_growth_yoy'),
                'rev_accelerating':  growth_score.get('rev_accelerating'),
                'rev_accel_quarters': growth_score.get('rev_accel_quarters', 0),

                # Detalles de cada componente
                'earnings_details': earnings_score['details'],
                'growth_details': growth_score['details'],
                'rs_details': rs_score['details'],
                'health_details': health_score['details'],
                'catalyst_details': catalyst_score['details'],

                # Datos básicos
                'current_price': info.get('currentPrice', info.get('regularMarketPrice', 0)),
                'market_cap': info.get('marketCap', 0),
                'sector': info.get('sector', 'N/A'),
                'industry': info.get('industry', 'N/A'),

                # Short Interest (combustible para short squeeze)
                **self._extract_short_interest(info),

                # 52-Week High Proximity (Minervini: comprar cerca de máximos)
                **self._extract_52w_proximity(info),

                # Minervini Trend Template (8-criteria Stage 2 checklist)
                **self._calculate_trend_template(
                    price_history, info, rs_score.get('rs_line_percentile')
                ),

                # Target Prices (analyst consensus + fundamental-based)
                **self._calculate_target_prices(info),

                # Value Quality Metrics (FCF, dividends, buybacks, revisions, earnings cal)
                **self._calculate_value_quality_metrics(stock, info),

                # Piotroski F-Score (Proven: +13.4% annual alpha)
                **self._calculate_piotroski_fscore(stock, info),

                # Magic Formula (Greenblatt) + PEG (Lynch)
                **self._calculate_magic_formula_metrics(stock, info),

                # Timestamp
                'analyzed_at': datetime.now().isoformat()
            }

            print(f"   ✅ Score: {fundamental_score:.1f}/100 - {quality}")
            return result

        except Exception as e:
            print(f"   ❌ Error: {e}")
            return self._get_empty_result(ticker)

    def _get_quarterly_earnings(self, stock) -> pd.DataFrame:
        """Obtiene earnings trimestrales (Net Income por quarter).

        Usa quarterly_income_stmt (API actual) para construir un DataFrame
        con columna 'Earnings' compatible con el resto del código.
        quarterly_earnings está deprecated en yfinance reciente y devuelve None.
        """
        try:
            qi = stock.quarterly_income_stmt
            if qi is None or qi.empty:
                return pd.DataFrame()

            # Buscar fila de Net Income
            ni_row = None
            for candidate in ['Net Income From Continuing Operation Net Minority Interest',
                               'Net Income Common Stockholders',
                               'Net Income From Continuing And Discontinued Operation',
                               'Net Income']:
                if candidate in qi.index:
                    ni_row = candidate
                    break

            if ni_row is None:
                return pd.DataFrame()

            series = qi.loc[ni_row].sort_index(ascending=False)
            earnings = pd.DataFrame({'Earnings': series.values}, index=series.index)

            # FIX LOOK-AHEAD BIAS: solo datos hasta as_of_date
            if self.as_of_date and isinstance(earnings.index, pd.DatetimeIndex):
                earnings = earnings[earnings.index <= self.as_of_date_dt]

            return earnings
        except:
            pass
        return pd.DataFrame()

    def _get_financials(self, stock) -> Dict:
        """Obtiene datos financieros

        Returns:
            Dict with quarterly financials reported before as_of_date (if specified)
        """
        try:
            quarterly_financials = stock.quarterly_financials
            quarterly_balance_sheet = stock.quarterly_balance_sheet

            # 🔴 FIX LOOK-AHEAD BIAS: Filter financials by date
            if self.as_of_date:
                # Filter quarterly financials
                if quarterly_financials is not None and not quarterly_financials.empty:
                    if isinstance(quarterly_financials.columns, pd.DatetimeIndex):
                        quarterly_financials = quarterly_financials.loc[:, quarterly_financials.columns <= self.as_of_date_dt]

                # Filter balance sheet
                if quarterly_balance_sheet is not None and not quarterly_balance_sheet.empty:
                    if isinstance(quarterly_balance_sheet.columns, pd.DatetimeIndex):
                        quarterly_balance_sheet = quarterly_balance_sheet.loc[:, quarterly_balance_sheet.columns <= self.as_of_date_dt]

            return {
                'quarterly_financials': quarterly_financials,
                'quarterly_balance_sheet': quarterly_balance_sheet,
            }
        except:
            return {
                'quarterly_financials': pd.DataFrame(),
                'quarterly_balance_sheet': pd.DataFrame(),
            }

    def _get_price_history(self, stock) -> pd.DataFrame:
        """Obtiene histórico de precios (1 año)

        Returns:
            DataFrame with price history up to as_of_date (if specified)
        """
        try:
            # 🔴 FIX LOOK-AHEAD BIAS: Use date range instead of period
            if self.as_of_date:
                # Historical mode: fetch data up to as_of_date
                end_date = self.as_of_date_dt
                start_date = end_date - timedelta(days=365)

                hist = stock.history(
                    start=start_date.strftime('%Y-%m-%d'),
                    end=end_date.strftime('%Y-%m-%d')
                )
            else:
                # Current mode: use standard period
                hist = stock.history(period='1y')

            if hist is not None and not hist.empty:
                return hist
        except:
            pass
        return pd.DataFrame()

    def _calculate_earnings_quality_score(
        self,
        quarterly_earnings: pd.DataFrame,
        info: Dict
    ) -> Dict:
        """
        Score de calidad de earnings (0-100)

        Factores:
        - EPS growth YoY
        - Consecutive positive quarters
        - Earnings acceleration
        - Profit margins
        """
        score = 50.0
        details = {}
        eps_growth_yoy = None
        eps_accelerating = None
        eps_accel_quarters = 0

        try:
            if not quarterly_earnings.empty and 'Earnings' in quarterly_earnings.columns:
                earnings = quarterly_earnings['Earnings'].dropna()

                if len(earnings) >= 4:
                    # 1. EPS Growth YoY
                    latest_eps = earnings.iloc[0]
                    prev_eps = earnings.iloc[3]

                    if prev_eps > 0:
                        eps_growth = ((latest_eps - prev_eps) / prev_eps) * 100
                        eps_growth_yoy = round(eps_growth, 1)
                        details['eps_growth_yoy'] = eps_growth_yoy

                        # IBD-style: buscar growth >25%
                        if eps_growth >= 50:
                            score += 30
                        elif eps_growth >= 25:
                            score += 20
                        elif eps_growth >= 10:
                            score += 10
                        elif eps_growth < 0:
                            score -= 20

                    # 2. Consecutive positive earnings
                    positive_quarters = sum(1 for e in earnings.iloc[:4] if e > 0)
                    details['positive_quarters'] = positive_quarters

                    if positive_quarters == 4:
                        score += 15
                    elif positive_quarters >= 3:
                        score += 8

                    # 3. Multi-quarter EPS acceleration (CANSLIM "A")
                    # Calculate QoQ growth rates for last 3 pairs (need ≥4 quarters)
                    qoq_rates = []
                    for i in range(min(3, len(earnings) - 1)):
                        curr = earnings.iloc[i]
                        prev = earnings.iloc[i + 1]
                        if prev != 0:
                            qoq_rates.append((curr - prev) / abs(prev) * 100)
                        else:
                            qoq_rates.append(None)

                    # Count consecutive accelerating pairs (most recent first)
                    accel_count = 0
                    for i in range(len(qoq_rates) - 1):
                        r0, r1 = qoq_rates[i], qoq_rates[i + 1]
                        if r0 is not None and r1 is not None and r0 > r1:
                            accel_count += 1
                        else:
                            break  # stop at first non-acceleration

                    eps_accel_quarters = accel_count
                    eps_accelerating = accel_count >= 1
                    details['earnings_accelerating'] = eps_accelerating
                    details['eps_accel_quarters'] = eps_accel_quarters

                    if accel_count >= 2:
                        score += 20    # 3 consecutive quarters
                    elif accel_count >= 1:
                        score += 10   # 2 consecutive quarters

            # 4. Profit margin
            profit_margin = info.get('profitMargins')
            if profit_margin:
                details['profit_margin_pct'] = round(profit_margin * 100, 1)
                if profit_margin >= 0.20:
                    score += 10
                elif profit_margin >= 0.10:
                    score += 5

            score = max(0, min(100, score))

        except Exception as e:
            print(f"      ⚠️ Earnings quality error: {e}")

        return {
            'score': round(score, 1),
            'details': details,
            'eps_growth_yoy':    eps_growth_yoy,
            'eps_accelerating':  eps_accelerating,
            'eps_accel_quarters': eps_accel_quarters,
        }

    def _calculate_growth_acceleration_score(
        self,
        quarterly_earnings: pd.DataFrame,
        financials: Dict
    ) -> Dict:
        """
        Score de aceleración de crecimiento (0-100)

        Factores:
        - Revenue growth YoY
        - Revenue acceleration
        - Quarter-over-quarter improvement
        """
        score = 50.0
        details = {}
        rev_growth_yoy = None
        rev_accelerating = None
        rev_accel_quarters = 0

        try:
            qf = financials.get('quarterly_financials')

            if qf is not None and not qf.empty:
                # Revenue growth
                if 'Total Revenue' in qf.index:
                    revenue = qf.loc['Total Revenue'].dropna()

                    if len(revenue) >= 4:
                        latest_rev = revenue.iloc[0]
                        prev_rev = revenue.iloc[3]

                        if prev_rev > 0:
                            rev_growth = ((latest_rev - prev_rev) / prev_rev) * 100
                            rev_growth_yoy = round(rev_growth, 1)
                            details['revenue_growth_yoy'] = rev_growth_yoy

                            # IBD-style: buscar growth >25%
                            if rev_growth >= 30:
                                score += 30
                            elif rev_growth >= 20:
                                score += 20
                            elif rev_growth >= 10:
                                score += 10
                            elif rev_growth < 0:
                                score -= 20

                        # Multi-quarter revenue acceleration (CANSLIM "A")
                        qoq_rates = []
                        for i in range(min(3, len(revenue) - 1)):
                            curr = revenue.iloc[i]
                            prev = revenue.iloc[i + 1]
                            if prev != 0:
                                qoq_rates.append((curr - prev) / abs(prev) * 100)
                            else:
                                qoq_rates.append(None)

                        accel_count = 0
                        for i in range(len(qoq_rates) - 1):
                            r0, r1 = qoq_rates[i], qoq_rates[i + 1]
                            if r0 is not None and r1 is not None and r0 > r1:
                                accel_count += 1
                            else:
                                break

                        rev_accel_quarters = accel_count
                        rev_accelerating = accel_count >= 1
                        details['revenue_accelerating'] = rev_accelerating
                        details['rev_accel_quarters'] = rev_accel_quarters

                        if accel_count >= 2:
                            score += 20
                        elif accel_count >= 1:
                            score += 10

            score = max(0, min(100, score))

        except Exception as e:
            print(f"      ⚠️ Growth acceleration error: {e}")

        return {
            'score': round(score, 1),
            'details': details,
            'rev_growth_yoy':    rev_growth_yoy,
            'rev_accelerating':  rev_accelerating,
            'rev_accel_quarters': rev_accel_quarters,
        }

    def _calculate_relative_strength_score(
        self,
        price_history: pd.DataFrame,
        ticker: str
    ) -> Dict:
        """
        Relative Strength vs SPY (0-100)
        Similar a IBD RS Rating + RS Line (Minervini)
        """
        score = 50.0
        details = {}
        rs_line_score = None
        rs_line_percentile = None
        rs_line_at_new_high = None
        rs_line_trend = None

        try:
            if price_history.empty:
                return {
                    'score': 50.0, 'details': {},
                    'rs_line_score': None, 'rs_line_percentile': None,
                    'rs_line_at_new_high': None, 'rs_line_trend': None,
                }

            # Obtener SPY para comparación
            spy = yf.Ticker('SPY')
            spy_history = spy.history(period='1y')

            if not spy_history.empty:
                # Performance en diferentes periodos
                periods = {
                    '3m': 63,   # ~3 meses
                    '6m': 126,  # ~6 meses
                    '1y': 252   # ~1 año
                }

                for period_name, days in periods.items():
                    if len(price_history) > days and len(spy_history) > days:
                        # Stock performance
                        stock_return = (
                            (price_history['Close'].iloc[-1] - price_history['Close'].iloc[-days]) /
                            price_history['Close'].iloc[-days] * 100
                        )

                        # SPY performance
                        spy_return = (
                            (spy_history['Close'].iloc[-1] - spy_history['Close'].iloc[-days]) /
                            spy_history['Close'].iloc[-days] * 100
                        )

                        # Relative strength
                        rs = stock_return - spy_return
                        details[f'rs_{period_name}'] = round(rs, 1)

                        # Scoring
                        if period_name == '3m':
                            weight = 15
                        elif period_name == '6m':
                            weight = 20
                        else:  # 1y
                            weight = 15

                        if rs > 20:
                            score += weight
                        elif rs > 10:
                            score += weight * 0.7
                        elif rs > 0:
                            score += weight * 0.3
                        elif rs < -20:
                            score -= weight

                score = max(0, min(100, score))

                # ── RS Line (Minervini): stock_price / SPY_price ratio ────────
                try:
                    # Align on common dates
                    stock_close = price_history['Close'].rename('stock')
                    spy_close   = spy_history['Close'].rename('spy')
                    aligned     = pd.concat([stock_close, spy_close], axis=1).dropna()

                    if len(aligned) >= 10:
                        rs_line = aligned['stock'] / aligned['spy']

                        rs_current    = float(rs_line.iloc[-1])
                        rs_52w_high   = float(rs_line.max())
                        rs_52w_low    = float(rs_line.min())
                        rs_range      = rs_52w_high - rs_52w_low

                        rs_line_percentile = round(
                            (rs_current - rs_52w_low) / rs_range * 100
                            if rs_range > 0 else 50.0, 1
                        )
                        rs_line_at_new_high = bool(rs_current >= rs_52w_high * 0.98)

                        # 50-day slope (use fewer days if series is short)
                        lookback = min(50, len(rs_line) - 1)
                        if lookback >= 5:
                            base = abs(rs_line.iloc[-lookback])
                            slope_pct = (rs_line.iloc[-1] - rs_line.iloc[-lookback]) / base * 100 if base > 0 else 0.0
                            rs_line_trend = "up" if slope_pct > 2 else ("down" if slope_pct < -2 else "flat")
                        else:
                            rs_line_trend = "flat"

                        # RS Line score 0-100 based on percentile
                        if   rs_line_percentile >= 90: rs_line_score = 95
                        elif rs_line_percentile >= 75: rs_line_score = 80
                        elif rs_line_percentile >= 50: rs_line_score = 60
                        elif rs_line_percentile >= 25: rs_line_score = 35
                        else:                           rs_line_score = 15
                        if rs_line_at_new_high:
                            rs_line_score = min(100, rs_line_score + 10)

                        # Blend 60% existing RS + 40% RS Line score
                        score = round(score * 0.60 + rs_line_score * 0.40, 1)
                        score = max(0, min(100, score))

                        details['rs_line_percentile'] = rs_line_percentile
                        details['rs_line_at_new_high'] = rs_line_at_new_high
                        details['rs_line_trend']       = rs_line_trend
                        details['rs_line_score']       = rs_line_score

                except Exception as e_rs:
                    print(f"      ⚠️ RS Line calculation error: {e_rs}")

        except Exception as e:
            print(f"      ⚠️ Relative strength error: {e}")

        return {
            'score': round(score, 1),
            'details': details,
            'rs_line_score':       rs_line_score,
            'rs_line_percentile':  rs_line_percentile,
            'rs_line_at_new_high': rs_line_at_new_high,
            'rs_line_trend':       rs_line_trend,
        }

    def _calculate_financial_health_score(
        self,
        financials: Dict,
        info: Dict
    ) -> Dict:
        """
        Score de salud financiera (0-100)

        Factores:
        - ROE (Return on Equity)
        - Debt-to-Equity
        - Current Ratio
        - Operating Margins
        """
        score = 50.0
        details = {}

        try:
            # 1. ROE
            roe = info.get('returnOnEquity')
            if roe:
                details['roe_pct'] = round(roe * 100, 1)
                # IBD busca ROE >17%
                if roe >= 0.25:
                    score += 15
                elif roe >= 0.17:
                    score += 10
                elif roe >= 0.10:
                    score += 5
                elif roe < 0:
                    score -= 10

            # 2. Debt-to-Equity
            debt_to_equity = info.get('debtToEquity')
            if debt_to_equity is not None:
                details['debt_to_equity'] = round(debt_to_equity / 100, 2)
                # Menor deuda es mejor
                if debt_to_equity < 30:
                    score += 15
                elif debt_to_equity < 50:
                    score += 10
                elif debt_to_equity < 100:
                    score += 5
                elif debt_to_equity > 200:
                    score -= 15

            # 3. Current Ratio
            current_ratio = info.get('currentRatio')
            if current_ratio:
                details['current_ratio'] = round(current_ratio, 2)
                if 1.5 <= current_ratio <= 3.0:
                    score += 10
                elif current_ratio >= 1.0:
                    score += 5
                elif current_ratio < 1.0:
                    score -= 10

            # 4. Operating Margins
            operating_margins = info.get('operatingMargins')
            if operating_margins:
                details['operating_margin_pct'] = round(operating_margins * 100, 1)
                if operating_margins >= 0.20:
                    score += 10
                elif operating_margins >= 0.10:
                    score += 5

            score = max(0, min(100, score))

        except Exception as e:
            print(f"      ⚠️ Financial health error: {e}")

        return {'score': round(score, 1), 'details': details}

    def _calculate_catalyst_timing_score(
        self,
        stock,
        info: Dict
    ) -> Dict:
        """
        Score de timing de catalizadores (0-100)

        Factores:
        - Días hasta earnings (sweet spot: 30-60 días)
        - Analyst recommendations
        - Target price upside
        """
        score = 50.0
        details = {}

        try:
            # 1. Earnings date
            try:
                calendar = stock.calendar
                if calendar is not None and not calendar.empty:
                    # calendar puede ser Series o DataFrame
                    if isinstance(calendar, pd.Series):
                        earnings_date = calendar.get('Earnings Date')
                    else:
                        earnings_date = calendar.get('Earnings Date', [None])[0] if 'Earnings Date' in calendar else None

                    if earnings_date is not None and pd.notna(earnings_date):
                        days_to_earnings = (pd.Timestamp(earnings_date) - pd.Timestamp.now()).days
                        details['days_to_earnings'] = days_to_earnings

                        # Sweet spot: 30-60 días antes
                        if 30 <= days_to_earnings <= 60:
                            score += 30
                        elif 15 <= days_to_earnings <= 90:
                            score += 15
            except:
                details['days_to_earnings'] = 'N/A'

            # 2. Recommendation
            recommendation = info.get('recommendationKey')
            if recommendation:
                details['recommendation'] = recommendation
                if recommendation in ['strong_buy', 'buy']:
                    score += 10
                elif recommendation == 'hold':
                    score += 0
                elif recommendation in ['sell', 'strong_sell']:
                    score -= 10

            # 3. Target price upside
            target_price = info.get('targetMeanPrice')
            current_price = info.get('currentPrice', info.get('regularMarketPrice'))
            if target_price and current_price and current_price > 0:
                upside = ((target_price - current_price) / current_price) * 100
                details['analyst_upside_pct'] = round(upside, 1)

                if upside >= 30:
                    score += 10
                elif upside >= 15:
                    score += 5
                elif upside < -10:
                    score -= 10

            score = max(0, min(100, score))

        except Exception as e:
            print(f"      ⚠️ Catalyst timing error: {e}")

        return {'score': round(score, 1), 'details': details}

    def _get_tier(self, score: float) -> str:
        """Tier basado en score"""
        if score >= 80:
            return "🏆 ELITE"
        elif score >= 70:
            return "⭐⭐⭐ EXCELLENT"
        elif score >= 60:
            return "⭐⭐ GOOD"
        elif score >= 50:
            return "⭐ AVERAGE"
        else:
            return "⚠️ WEAK"

    def _get_quality(self, score: float) -> str:
        """Quality label para dashboards"""
        if score >= 80:
            return "🟢 Elite"
        elif score >= 70:
            return "🟢 Excellent"
        elif score >= 60:
            return "🟡 Good"
        elif score >= 50:
            return "🟡 Average"
        else:
            return "🔴 Weak"

    def _get_empty_result(self, ticker: str) -> Dict:
        """Resultado vacío en caso de error"""
        return {
            'ticker': ticker,
            'company_name': ticker,
            'fundamental_score': 0.0,
            'tier': '❌ ERROR',
            'quality': '🔴 Error',
            'earnings_quality_score': 0.0,
            'growth_acceleration_score': 0.0,
            'relative_strength_score': 0.0,
            'financial_health_score': 0.0,
            'catalyst_timing_score': 0.0,
            'rs_line_score': None,
            'rs_line_percentile': None,
            'rs_line_at_new_high': None,
            'rs_line_trend': None,
            'eps_growth_yoy': None,
            'eps_accelerating': None,
            'eps_accel_quarters': 0,
            'rev_growth_yoy': None,
            'rev_accelerating': None,
            'rev_accel_quarters': 0,
            'earnings_details': {},
            'growth_details': {},
            'rs_details': {},
            'health_details': {},
            'catalyst_details': {},
            'current_price': 0,
            'market_cap': 0,
            'sector': 'N/A',
            'industry': 'N/A',
            'short_percent_float': None,
            'short_ratio': None,
            'short_squeeze_potential': None,
            'fifty_two_week_high': None,
            'proximity_to_52w_high': None,
            'trend_template_score': None,
            'trend_template_pass': None,
            'target_price_analyst':        None,
            'target_price_analyst_high':   None,
            'target_price_analyst_low':    None,
            'analyst_count':               None,
            'analyst_recommendation':      None,
            'analyst_upside_pct':          None,
            'target_price_dcf':            None,
            'target_price_dcf_upside_pct': None,
            'target_price_pe':             None,
            'target_price_pe_upside_pct':  None,
            # Value Quality Metrics
            'fcf_yield_pct': None,
            'fcf_per_share': None,
            'dividend_yield_pct': None,
            'payout_ratio_pct': None,
            'dividend_rate': None,
            'five_yr_avg_dividend_yield_pct': None,
            'buyback_active': None,
            'shares_change_pct': None,
            'interest_coverage': None,
            'analyst_revision_momentum': None,
            'days_to_earnings': None,
            'earnings_date': None,
            'earnings_warning': False,
            'earnings_catalyst': False,
            # Piotroski F-Score
            'piotroski_score': None,
            'piotroski_label': None,
            # Magic Formula (Greenblatt) + PEG (Lynch)
            'ebit_ev_yield': None,
            'roic_greenblatt': None,
            'peg_ratio': None,
            'analyzed_at': datetime.now().isoformat()
        }

    def _calculate_trend_template(
        self,
        price_history: pd.DataFrame,
        info: Dict,
        rs_percentile: Optional[float]
    ) -> Dict:
        """
        Minervini Trend Template — 8 criterios Stage 2 uptrend.

        1. Price > 150MA and 200MA
        2. 150MA > 200MA
        3. 200MA trending up ≥ 1 month (20 bars)
        4. 50MA > 150MA and 200MA
        5. Price > 50MA
        6. Price ≥ 30% above 52-week low
        7. Price within 25% of 52-week high (proximity >= -25%)
        8. RS Rating ≥ 70

        Returns flat keys: trend_template_score (0-8), trend_template_pass (bool).
        """
        empty = {'trend_template_score': None, 'trend_template_pass': None}

        if price_history.empty or len(price_history) < 200:
            return empty

        try:
            close = price_history['Close']

            ma50  = float(close.rolling(50).mean().iloc[-1])
            ma150 = float(close.rolling(150).mean().iloc[-1])
            ma200 = float(close.rolling(200).mean().iloc[-1])

            # 200MA slope: current vs 20 bars ago
            if len(close) >= 221:
                ma200_20d = float(close.rolling(200).mean().iloc[-21])
                ma200_trending_up = ma200 > ma200_20d
            else:
                ma200_trending_up = False

            price = float(close.iloc[-1])

            low52  = info.get('fiftyTwoWeekLow')
            high52 = info.get('fiftyTwoWeekHigh')

            criteria = [
                price > ma150 and price > ma200,               # 1
                ma150 > ma200,                                  # 2
                ma200_trending_up,                              # 3
                ma50 > ma150 and ma50 > ma200,                 # 4
                price > ma50,                                   # 5
                (low52  is not None and float(low52)  > 0      # 6
                 and price >= float(low52) * 1.30),
                (high52 is not None and float(high52) > 0      # 7
                 and price >= float(high52) * 0.75),
                rs_percentile is not None and rs_percentile >= 70,  # 8
            ]

            score = int(sum(criteria))
            return {
                'trend_template_score': score,
                'trend_template_pass':  score >= 7,
            }
        except Exception:
            return empty

    def _extract_short_interest(self, info: Dict) -> Dict:
        """Extrae datos de short interest de yfinance info."""
        try:
            raw = info.get('shortPercentOfFloat')
            short_pct = round(float(raw) * 100, 1) if raw is not None else None
            raw_ratio = info.get('shortRatio')
            short_ratio = round(float(raw_ratio), 1) if raw_ratio is not None else None
            short_squeeze = short_pct is not None and short_pct >= 8.0
        except (TypeError, ValueError):
            short_pct = short_ratio = None
            short_squeeze = None
        return {
            'short_percent_float':     short_pct,
            'short_ratio':             short_ratio,
            'short_squeeze_potential': short_squeeze,
        }

    def _extract_52w_proximity(self, info: Dict) -> Dict:
        """Calcula proximidad al máximo de 52 semanas (Minervini: comprar cerca de máximos)."""
        try:
            high52 = info.get('fiftyTwoWeekHigh')
            price  = info.get('currentPrice') or info.get('regularMarketPrice')
            proximity = None
            if high52 and price and float(high52) > 0:
                proximity = round((float(price) / float(high52) - 1) * 100, 1)
                # e.g. -5.0 = 5% below 52w high; -40.0 = 40% below
        except (TypeError, ValueError):
            high52 = proximity = None
        return {
            'fifty_two_week_high':  float(high52) if high52 else None,
            'proximity_to_52w_high': proximity,
        }

    def _calculate_piotroski_fscore(self, stock, info: Dict) -> Dict:
        """
        Piotroski F-Score (0-9): Proven academic quality filter.
        Backtested outperformance: +13.4% annually vs market (20-year study).

        9 binary criteria across 3 groups:
          Profitability  (4 pts): ROA>0, CFO>0, ΔROA+, Accruals OK
          Leverage       (3 pts): ΔDebt↓, ΔLiquidity↑, No dilution
          Efficiency     (2 pts): ΔGross Margin+, ΔAsset Turnover+

        Score 8-9 = STRONG (buy signal for value stocks)
        Score 0-2 = WEAK   (value trap — avoid)
        """
        result = {
            'piotroski_score': None,
            'piotroski_label': None,
        }
        try:
            fin = stock.financials        # Annual: rows=metrics, cols=years desc
            bs  = stock.balance_sheet
            cf  = stock.cashflow

            if fin is None or fin.empty or bs is None or bs.empty or cf is None or cf.empty:
                return result
            if fin.shape[1] < 2 or bs.shape[1] < 2:
                return result

            def _val(df, keys, col=0):
                for k in keys:
                    if k in df.index:
                        v = df.loc[k].iloc[col]
                        return float(v) if v is not None and not pd.isna(v) else None
                return None

            # ── Raw values (Y1=current, Y2=prior) ─────────────────────
            ni_y1  = _val(fin, ['Net Income', 'NetIncome'])
            ni_y2  = _val(fin, ['Net Income', 'NetIncome'], 1)
            ta_y1  = _val(bs,  ['Total Assets', 'TotalAssets'])
            ta_y2  = _val(bs,  ['Total Assets', 'TotalAssets'], 1)
            cfo_y1 = _val(cf,  ['Operating Cash Flow', 'Total Cash From Operating Activities',
                                 'Cash From Operations', 'Net Cash Provided By Operating Activities'])
            lt_y1  = _val(bs,  ['Long Term Debt', 'LongTermDebt', 'Long-Term Debt'], 0) or 0.0
            lt_y2  = _val(bs,  ['Long Term Debt', 'LongTermDebt', 'Long-Term Debt'], 1) or 0.0
            ca_y1  = _val(bs,  ['Current Assets', 'Total Current Assets'])
            ca_y2  = _val(bs,  ['Current Assets', 'Total Current Assets'], 1)
            cl_y1  = _val(bs,  ['Current Liabilities', 'Total Current Liabilities'])
            cl_y2  = _val(bs,  ['Current Liabilities', 'Total Current Liabilities'], 1)
            sh_y1  = _val(bs,  ['Ordinary Shares Number', 'Common Stock', 'Share Issued'])
            sh_y2  = _val(bs,  ['Ordinary Shares Number', 'Common Stock', 'Share Issued'], 1)
            rev_y1 = _val(fin, ['Total Revenue', 'Revenue', 'TotalRevenue'])
            rev_y2 = _val(fin, ['Total Revenue', 'Revenue', 'TotalRevenue'], 1)
            gp_y1  = _val(fin, ['Gross Profit', 'GrossProfit'])
            gp_y2  = _val(fin, ['Gross Profit', 'GrossProfit'], 1)

            if not ta_y1 or not ta_y2:
                return result

            roa_y1 = ni_y1 / ta_y1 if ni_y1 is not None else None
            roa_y2 = ni_y2 / ta_y2 if ni_y2 is not None else None

            score = 0

            # ── GROUP 1: Profitability ──────────────────────────────────
            if roa_y1 is not None and roa_y1 > 0:                score += 1  # F1: ROA > 0
            if cfo_y1 is not None and cfo_y1 > 0:                score += 1  # F2: CFO > 0
            if roa_y1 is not None and roa_y2 is not None and roa_y1 > roa_y2: score += 1  # F3: ΔROA+
            # F4: Accruals — cash earnings > accounting earnings
            if cfo_y1 is not None and roa_y1 is not None and (cfo_y1 / ta_y1) > roa_y1:
                score += 1

            # ── GROUP 2: Leverage / Liquidity ──────────────────────────
            # F5: Long-term debt ratio decreasing
            lr_y1 = lt_y1 / ta_y1
            lr_y2 = lt_y2 / ta_y2
            if lr_y1 < lr_y2:                                     score += 1
            # F6: Current ratio improving
            cr_y1 = (ca_y1 / cl_y1) if ca_y1 and cl_y1 and cl_y1 > 0 else None
            cr_y2 = (ca_y2 / cl_y2) if ca_y2 and cl_y2 and cl_y2 > 0 else None
            if cr_y1 is not None and cr_y2 is not None and cr_y1 > cr_y2: score += 1  # F6
            # F7: No new share issuance (tolerance 1%)
            if sh_y1 is None or sh_y2 is None or sh_y1 <= sh_y2 * 1.01: score += 1

            # ── GROUP 3: Operating Efficiency ──────────────────────────
            # F8: Gross margin improving
            gm_y1 = gp_y1 / rev_y1 if gp_y1 and rev_y1 and rev_y1 > 0 else None
            gm_y2 = gp_y2 / rev_y2 if gp_y2 and rev_y2 and rev_y2 > 0 else None
            if gm_y1 is not None and gm_y2 is not None and gm_y1 > gm_y2: score += 1
            # F9: Asset turnover improving
            at_y1 = rev_y1 / ta_y1 if rev_y1 else None
            at_y2 = rev_y2 / ta_y2 if rev_y2 else None
            if at_y1 is not None and at_y2 is not None and at_y1 > at_y2: score += 1

            result['piotroski_score'] = score
            result['piotroski_label'] = 'STRONG' if score >= 8 else ('WEAK' if score <= 2 else 'NEUTRAL')

        except Exception:
            pass
        return result

    def _calculate_magic_formula_metrics(self, stock, info: Dict) -> Dict:
        """
        Greenblatt Magic Formula raw metrics + PEG ratio (Lynch):
          - ebit_ev_yield   = EBIT / Enterprise Value × 100 (earnings yield %)
          - roic_greenblatt = EBIT / (Net PP&E + Working Capital) × 100
          - peg_ratio       = Forward P/E / EPS Growth %

        Universe ranking into magic_formula_rank is done in super_score_integrator.py.
        """
        result = {
            'ebit_ev_yield':   None,
            'roic_greenblatt': None,
            'peg_ratio':       None,
        }
        try:
            fin = stock.financials
            bs  = stock.balance_sheet

            def _val(df, keys, col=0):
                for k in keys:
                    if k in df.index:
                        v = df.loc[k].iloc[col]
                        return float(v) if v is not None and not pd.isna(v) else None
                return None

            # ── EBIT (from annual income statement) ────────────────────
            ebit = None
            if fin is not None and not fin.empty:
                ebit = _val(fin, ['EBIT', 'Operating Income', 'Total Operating Income As Reported',
                                   'Normalized EBITDA'])  # last resort

            ev = info.get('enterpriseValue')

            # ── Earnings Yield (EBIT / EV) ─────────────────────────────
            if ebit and ev and float(ev) > 0:
                result['ebit_ev_yield'] = round((ebit / float(ev)) * 100, 2)

            # ── ROIC = EBIT / (Net PP&E + max(Working Capital, 0)) ─────
            if ebit and bs is not None and not bs.empty:
                net_ppe = _val(bs, ['Net PPE', 'Net Plant Property Equipment And Equipment',
                                    'Property Plant Equipment Net', 'Net Property Plant And Equipment'])
                ca = _val(bs, ['Current Assets', 'Total Current Assets'])
                cl = _val(bs, ['Current Liabilities', 'Total Current Liabilities'])
                if net_ppe is not None and ca is not None and cl is not None:
                    wc = ca - cl
                    invested_capital = (net_ppe or 0) + max(wc, 0)
                    if invested_capital > 0:
                        result['roic_greenblatt'] = round((ebit / invested_capital) * 100, 1)

            # ── PEG Ratio (Lynch: P/E ÷ Growth %) ─────────────────────
            pe = info.get('forwardPE') or info.get('trailingPE')
            growth_pct = None
            eg = info.get('earningsGrowth')
            if eg and not pd.isna(eg):
                growth_pct = float(eg) * 100
            else:
                eps_c = info.get('epsCurrentYear')
                eps_f = info.get('forwardEps')
                if eps_c and eps_f and abs(float(eps_c)) > 0:
                    growth_pct = ((float(eps_f) - float(eps_c)) / abs(float(eps_c))) * 100

            if pe and growth_pct and float(growth_pct) > 0 and float(pe) > 0:
                result['peg_ratio'] = round(float(pe) / float(growth_pct), 2)

        except Exception:
            pass
        return result

    def _calculate_value_quality_metrics(self, stock, info: Dict) -> Dict:
        """
        Métricas de calidad VALUE (Lynch/Buffett style):
        - FCF Yield (Free Cash Flow / Market Cap)
        - Dividend Quality (yield, payout ratio, growth)
        - Buyback Detection (shares outstanding change)
        - Interest Coverage (can the company pay its debt?)
        - Analyst Revision Momentum (are estimates rising?)
        - Earnings Calendar (days to next earnings)
        """
        result = {
            # FCF
            'fcf_yield_pct': None,
            'fcf_per_share': None,
            # Dividends
            'dividend_yield_pct': None,
            'payout_ratio_pct': None,
            'dividend_rate': None,
            'five_yr_avg_dividend_yield_pct': None,
            # Buybacks
            'buyback_active': None,
            'shares_change_pct': None,
            # Debt quality
            'interest_coverage': None,
            # Analyst revisions
            'analyst_revision_momentum': None,  # positive = upgrades
            # Earnings calendar
            'days_to_earnings': None,
            'earnings_date': None,
            'earnings_warning': False,    # <7 days = danger
            'earnings_catalyst': False,   # 7-21 days = catalyst
        }

        try:
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            if not current_price or float(current_price) <= 0:
                return result
            current_price = float(current_price)
            market_cap = info.get('marketCap')

            # ── FCF YIELD ──────────────────────────────────────────────
            fcf = info.get('freeCashflow')
            shares = info.get('sharesOutstanding')
            if fcf and market_cap and market_cap > 0:
                result['fcf_yield_pct'] = round((float(fcf) / float(market_cap)) * 100, 2)
            if fcf and shares and float(shares) > 0:
                result['fcf_per_share'] = round(float(fcf) / float(shares), 2)

            # ── DIVIDEND QUALITY ───────────────────────────────────────
            div_yield = info.get('dividendYield')
            if div_yield and div_yield > 0:
                # yfinance dividendYield is already % (0.38 = 0.38%), not decimal
                result['dividend_yield_pct'] = round(float(div_yield), 2)
            div_rate = info.get('dividendRate')
            if div_rate:
                result['dividend_rate'] = round(float(div_rate), 2)
            payout = info.get('payoutRatio')
            if payout and payout > 0:
                result['payout_ratio_pct'] = round(float(payout) * 100, 1)
            five_yr = info.get('fiveYearAvgDividendYield')
            if five_yr and five_yr > 0:
                result['five_yr_avg_dividend_yield_pct'] = round(float(five_yr), 2)

            # ── BUYBACK DETECTION ──────────────────────────────────────
            # Compare current shares vs implied from historical market cap
            try:
                cashflow = stock.quarterly_cashflow
                if cashflow is not None and not cashflow.empty:
                    # Look for "Repurchase Of Capital Stock" in cashflow
                    buyback_row = None
                    for label in ['Repurchase Of Capital Stock', 'RepurchaseOfCapitalStock',
                                  'Common Stock Repurchased']:
                        if label in cashflow.index:
                            buyback_row = cashflow.loc[label]
                            break
                    if buyback_row is not None:
                        # Sum last 4 quarters of buybacks (negative = buying back)
                        recent_buybacks = buyback_row.head(4).sum()
                        if recent_buybacks < 0 and market_cap and market_cap > 0:
                            buyback_pct = abs(float(recent_buybacks)) / float(market_cap) * 100
                            result['buyback_active'] = True
                            result['shares_change_pct'] = round(-buyback_pct, 2)
                        else:
                            result['buyback_active'] = False
                            if recent_buybacks > 0 and market_cap and market_cap > 0:
                                result['shares_change_pct'] = round(float(recent_buybacks) / float(market_cap) * 100, 2)
                    else:
                        result['buyback_active'] = False
            except Exception:
                pass

            # ── INTEREST COVERAGE ──────────────────────────────────────
            try:
                financials = stock.quarterly_financials
                if financials is not None and not financials.empty:
                    ebit_val = None
                    for label in ['EBIT', 'Operating Income', 'Total Operating Income As Reported']:
                        if label in financials.index:
                            ebit_val = financials.loc[label].head(4).sum()
                            break
                    # Interest from income statement
                    interest_val = None
                    for label in ['Interest Expense', 'InterestExpense']:
                        if label in financials.index:
                            val = financials.loc[label].head(4).sum()
                            interest_val = abs(float(val)) if val else None
                            break
                    # Fallback: estimate from total debt × ~5% rate
                    if not interest_val:
                        total_debt = info.get('totalDebt')
                        if total_debt and total_debt > 0:
                            interest_val = float(total_debt) * 0.05  # estimate 5% rate
                    if ebit_val and interest_val and interest_val > 0:
                        result['interest_coverage'] = round(float(ebit_val) / float(interest_val), 1)
            except Exception:
                pass

            # ── ANALYST REVISION MOMENTUM ──────────────────────────────
            try:
                rec_mean = info.get('recommendationMean')  # 1=Strong Buy, 5=Sell
                num_analysts = info.get('numberOfAnalystOpinions', 0)
                earnings_growth = info.get('earningsGrowth')  # YoY earnings growth estimate
                eps_current = info.get('epsCurrentYear')
                eps_next = info.get('epsNextYear')

                # Method 1: next year vs current year EPS estimates
                if eps_current and eps_next and abs(eps_current) > 0:
                    implied_growth = ((eps_next - eps_current) / abs(eps_current)) * 100
                # Method 2: use earningsGrowth from yfinance
                elif earnings_growth:
                    implied_growth = float(earnings_growth) * 100
                else:
                    implied_growth = None

                if implied_growth is not None:
                    # Weight by analyst conviction: strong buy = full weight
                    if rec_mean and num_analysts and num_analysts >= 3:
                        if rec_mean < 2.0:      # Strong Buy consensus
                            weight = 1.0
                        elif rec_mean < 2.5:    # Buy consensus
                            weight = 0.7
                        elif rec_mean < 3.5:    # Hold
                            weight = 0.4
                        else:                   # Sell
                            weight = 0.2
                        result['analyst_revision_momentum'] = round(implied_growth * weight, 1)
                    else:
                        result['analyst_revision_momentum'] = round(implied_growth * 0.5, 1)
            except Exception:
                pass

            # ── EARNINGS CALENDAR ──────────────────────────────────────
            try:
                earnings_dates = stock.earnings_dates
                if earnings_dates is not None and not earnings_dates.empty:
                    today = pd.Timestamp.now(tz=earnings_dates.index.tz) if earnings_dates.index.tz else pd.Timestamp.now()
                    future = earnings_dates[earnings_dates.index > today]
                    if not future.empty:
                        next_date = future.index[0]
                        days_until = (next_date - today).days
                        result['days_to_earnings'] = int(days_until)
                        result['earnings_date'] = next_date.strftime('%Y-%m-%d')
                        result['earnings_warning'] = days_until <= 7
                        result['earnings_catalyst'] = 7 < days_until <= 21
            except Exception:
                pass

        except Exception as e:
            print(f"      ⚠️ Value quality metrics error: {e}")

        return result

    def _calculate_target_prices(self, info: Dict) -> Dict:
        """
        Calcula precios objetivo usando 3 métodos:
        1. Analyst consensus (targetMeanPrice de yfinance)
        2. DCF simplificado (FCF per share + growth + discount 10%)
        3. P/E justo (EPS forward × fair P/E basado en crecimiento)

        Returns flat dict con todos los campos de target price.
        """
        result = {
            'target_price_analyst':        None,
            'target_price_analyst_high':   None,
            'target_price_analyst_low':    None,
            'analyst_count':               None,
            'analyst_recommendation':      None,
            'analyst_upside_pct':          None,
            'target_price_dcf':            None,
            'target_price_dcf_upside_pct': None,
            'target_price_pe':             None,
            'target_price_pe_upside_pct':  None,
        }

        try:
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            if not current_price or float(current_price) <= 0:
                return result
            current_price = float(current_price)

            def _upside(target):
                if target and target > 0:
                    return round((target - current_price) / current_price * 100, 1)
                return None

            # ── 1. Analyst consensus ──────────────────────────────────────────
            t_mean = info.get('targetMeanPrice')
            t_high = info.get('targetHighPrice')
            t_low  = info.get('targetLowPrice')
            n_analysts = info.get('numberOfAnalystOpinions')
            rec = info.get('recommendationKey')

            if t_mean:
                result['target_price_analyst']      = round(float(t_mean), 2)
                result['analyst_upside_pct']        = _upside(float(t_mean))
            if t_high:
                result['target_price_analyst_high'] = round(float(t_high), 2)
            if t_low:
                result['target_price_analyst_low']  = round(float(t_low),  2)
            if n_analysts:
                result['analyst_count']             = int(n_analysts)
            if rec:
                result['analyst_recommendation']    = str(rec)

            # ── 2. DCF simplificado ───────────────────────────────────────────
            fcf         = info.get('freeCashflow')
            shares      = info.get('sharesOutstanding')
            growth_rate = info.get('earningsGrowth') or info.get('revenueGrowth')

            if fcf and shares and float(shares) > 0:
                fcf_ps = float(fcf) / float(shares)  # FCF per share
                g = float(growth_rate) if growth_rate else 0.08  # default 8%
                g = max(0.03, min(g, 0.30))  # clip 3%-30%
                discount = 0.10
                terminal_g = 0.03

                # PV of 5 years FCF
                pv_fcf = sum(
                    fcf_ps * (1 + g) ** t / (1 + discount) ** t
                    for t in range(1, 6)
                )
                # Terminal value at year 5
                fcf_y5 = fcf_ps * (1 + g) ** 5
                terminal_value = fcf_y5 * (1 + terminal_g) / (discount - terminal_g)
                pv_terminal = terminal_value / (1 + discount) ** 5

                dcf_price = round(pv_fcf + pv_terminal, 2)
                if dcf_price > 0:
                    result['target_price_dcf']            = dcf_price
                    result['target_price_dcf_upside_pct'] = _upside(dcf_price)

            # ── 3. P/E justo ─────────────────────────────────────────────────
            eps_fwd = info.get('epsForwardTwelveMonths')
            eps_ttm = info.get('epsTrailingTwelveMonths')
            g_eps   = info.get('earningsGrowth')

            eps = float(eps_fwd) if eps_fwd and float(eps_fwd) > 0 else (
                  float(eps_ttm) if eps_ttm and float(eps_ttm) > 0 else None)

            if eps and eps > 0:
                g_annual = float(g_eps) if g_eps else 0.10
                g_annual = max(0.03, min(g_annual, 0.35))
                # Fair P/E = PEG 1.0 × growth% (e.g. 15% growth → P/E 15), capped 10-30
                fair_pe = max(10, min(g_annual * 100, 30))
                pe_target = round(eps * fair_pe, 2)
                if pe_target > 0:
                    result['target_price_pe']            = pe_target
                    result['target_price_pe_upside_pct'] = _upside(pe_target)

        except Exception:
            pass  # Return partial results on error

        return result

    def score_batch(
        self,
        tickers: List[str],
        delay: float = 1.5
    ) -> pd.DataFrame:
        """
        Score múltiples tickers en batch

        Args:
            tickers: Lista de tickers
            delay: Delay entre requests

        Returns:
            DataFrame con resultados
        """
        print(f"\n📊 FUNDAMENTAL SCORER - Batch Analysis")
        print(f"Scoring {len(tickers)} tickers...")
        print("=" * 80)

        # Initial pause so GitHub Actions runner IP isn't immediately blocked
        print("⏳ Pausa inicial de 10s para evitar rate limit en batch...")
        time.sleep(10)

        results = []
        consecutive_failures = 0

        for i, ticker in enumerate(tickers, 1):
            print(f"[{i}/{len(tickers)}] {ticker}")

            result = self.score_ticker(ticker)
            results.append(result)

            # Track consecutive failures — if all data is missing, back off harder
            is_empty = result.get('fundamental_score', 50.0) == 50.0
            if is_empty:
                consecutive_failures += 1
            else:
                consecutive_failures = 0

            if consecutive_failures >= 5:
                print(f"   ⏳ 5 fallos consecutivos — pausa larga de 30s para recuperar rate limit")
                time.sleep(30)
                consecutive_failures = 0
            elif i < len(tickers):
                jitter = random.uniform(0, 0.5)
                time.sleep(delay + jitter)

        # Convertir a DataFrame
        df = pd.DataFrame(results)

        # Ordenar por fundamental_score
        df = df.sort_values('fundamental_score', ascending=False)

        print(f"\n✅ Scoring completado: {len(df)} tickers")
        print(f"   Promedio: {df['fundamental_score'].mean():.1f}/100")
        print(f"   Elite (≥80): {len(df[df['fundamental_score'] >= 80])}")
        print(f"   Excellent (≥70): {len(df[df['fundamental_score'] >= 70])}")

        return df

    def save_results(self, df: pd.DataFrame, filename: str = 'fundamental_scores'):
        """Guarda resultados en CSV y JSON"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # CSV para fácil lectura
        csv_path = Path(f'docs/{filename}.csv')
        df.to_csv(csv_path, index=False)
        print(f"\n💾 CSV guardado: {csv_path}")

        # JSON con detalles completos
        json_path = Path(f'docs/{filename}_{timestamp}.json')

        # Convertir a dict y manejar numpy types
        results_dict = df.to_dict('records')
        results_dict = self._convert_to_native(results_dict)

        with open(json_path, 'w') as f:
            json.dump(results_dict, f, indent=2)

        print(f"💾 JSON guardado: {json_path}")

        return csv_path, json_path

    def _convert_to_native(self, obj):
        """Convierte numpy types a Python natives para JSON"""
        if isinstance(obj, dict):
            return {k: self._convert_to_native(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_native(item) for item in obj]
        elif isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif pd.isna(obj):
            return None
        else:
            return obj


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description='📊 Fundamental Scorer')
    parser.add_argument('--ticker', type=str, help='Score un ticker específico')
    parser.add_argument('--vcp', action='store_true', help='Score VCP stocks')
    parser.add_argument('--ml', action='store_true', help='Score ML top stocks')
    parser.add_argument('--5d', dest='five_d', action='store_true',
                       help='Include top-insider tickers from 5D scanner (insiders_score >= 60)')
    parser.add_argument('--top', type=int, default=50, help='Top N tickers (default: 50)')
    parser.add_argument('--value', action='store_true',
                       help='Score VALUE tickers from value_opportunities.csv (target prices, ROE)')
    parser.add_argument('--all', action='store_true', help='Score todas las fuentes (VCP + ML + VALUE)')
    parser.add_argument('--as-of-date', type=str, default=None,
                       help='Historical date for scoring (YYYY-MM-DD). Only use earnings/financials reported before this date. '
                            'Prevents look-ahead bias in backtesting.')

    args = parser.parse_args()

    # 🔴 FIX LOOK-AHEAD BIAS: Pass as_of_date to scorer
    scorer = FundamentalScorer(as_of_date=args.as_of_date)

    if args.as_of_date:
        print(f"📅 Historical mode: Scoring as of {args.as_of_date}")
        print(f"🔴 Only using earnings/financials reported before this date\n")

    if args.ticker:
        # Score un ticker
        result = scorer.score_ticker(args.ticker)

        print(f"\n{'='*80}")
        print(f"📊 FUNDAMENTAL SCORE: {result['ticker']}")
        print(f"{'='*80}")
        print(f"Company: {result['company_name']}")
        print(f"Sector: {result['sector']} | Industry: {result['industry']}")
        print(f"Price: ${result['current_price']:.2f}")
        print(f"\n🎯 FUNDAMENTAL SCORE: {result['fundamental_score']}/100 - {result['tier']}")
        print(f"\n📊 COMPONENTES:")
        print(f"  📈 Earnings Quality: {result['earnings_quality_score']:.1f}/100")
        for key, value in result['earnings_details'].items():
            print(f"      • {key}: {value}")
        print(f"  🚀 Growth Acceleration: {result['growth_acceleration_score']:.1f}/100")
        for key, value in result['growth_details'].items():
            print(f"      • {key}: {value}")
        print(f"  💪 Relative Strength: {result['relative_strength_score']:.1f}/100")
        for key, value in result['rs_details'].items():
            print(f"      • {key}: {value}")
        print(f"  💰 Financial Health: {result['financial_health_score']:.1f}/100")
        for key, value in result['health_details'].items():
            print(f"      • {key}: {value}")
        print(f"  🎯 Catalyst Timing: {result['catalyst_timing_score']:.1f}/100")
        for key, value in result['catalyst_details'].items():
            print(f"      • {key}: {value}")

    elif args.vcp or args.ml or args.all or args.five_d or args.value:
        tickers = []

        # Cargar tickers según fuente
        if args.vcp or args.all:
            vcp_path = Path('docs/reports/vcp/latest.csv')
            if vcp_path.exists():
                vcp_df = pd.read_csv(vcp_path)
                vcp_tickers = vcp_df['ticker'].head(args.top).tolist()
                tickers.extend(vcp_tickers)
                print(f"📊 Cargados {len(vcp_tickers)} tickers de VCP scan")

        if args.ml or args.all:
            ml_path = Path('docs/ml_scores.csv')
            if ml_path.exists():
                ml_df = pd.read_csv(ml_path)
                ml_tickers = ml_df['ticker'].head(args.top).tolist()
                tickers.extend(ml_tickers)
                print(f"🤖 Cargados {len(ml_tickers)} tickers de ML scores")

        if args.five_d or args.all:
            # Include tickers with significant insider activity (not in VCP universe)
            d5_path = Path('docs/super_opportunities_5d_complete_with_earnings.csv')
            if d5_path.exists():
                d5_df = pd.read_csv(d5_path)
                if 'insiders_score' in d5_df.columns and 'ticker' in d5_df.columns:
                    # Only high-insider tickers (recurring/strong insider conviction)
                    high_insider = d5_df[d5_df['insiders_score'] >= 60]['ticker'].tolist()
                    before = len(tickers)
                    tickers.extend(high_insider)
                    added = len(set(high_insider) - set(tickers[:before]))
                    print(f"👔 Cargados {len(high_insider)} tickers 5D (insiders≥60), {added} nuevos")
                else:
                    print("⚠️  5D data no tiene insiders_score — saltando")
            else:
                print("⚠️  No se encontró 5D data — saltando")

        if args.value or args.all:
            # Include VALUE tickers to get target prices, ROE, margins
            val_path = Path('docs/value_opportunities.csv')
            if val_path.exists():
                val_df = pd.read_csv(val_path)
                val_tickers = val_df['ticker'].tolist()
                before = len(set(tickers))
                tickers.extend(val_tickers)
                added = len(set(tickers)) - before
                print(f"💎 Cargados {len(val_tickers)} tickers VALUE, {added} nuevos")

        # Eliminar duplicados
        tickers = list(dict.fromkeys(tickers))

        if not tickers:
            print("❌ No se encontraron tickers. Ejecuta primero VCP scan o ML scoring")
            return

        print(f"\n📊 Scoring {len(tickers)} tickers únicos...")

        # Score batch
        results_df = scorer.score_batch(tickers)

        # Guardar
        scorer.save_results(results_df)

        # Mostrar top 10
        print(f"\n{'='*80}")
        print(f"🏆 TOP 10 FUNDAMENTAL SCORES")
        print(f"{'='*80}")
        print(f"{'Ticker':<8} {'Company':<30} {'F-Score':<8} {'Quality':<15}")
        print(f"{'-'*80}")

        for _, row in results_df.head(10).iterrows():
            ticker = row['ticker']
            company = str(row['company_name'])[:28]
            score = row['fundamental_score']
            quality = row['quality']

            print(f"{ticker:<8} {company:<30} {score:<8.1f} {quality:<15}")

    else:
        print("❌ Especifica --ticker, --vcp, --ml, o --all")
        print("\nEjemplos:")
        print("  python3 fundamental_scorer.py --ticker AAPL")
        print("  python3 fundamental_scorer.py --vcp --top 50")
        print("  python3 fundamental_scorer.py --ml --top 30")
        print("  python3 fundamental_scorer.py --all --top 100")


if __name__ == "__main__":
    main()
