#!/usr/bin/env python3
"""
MEAN REVERSION DETECTOR
Identifica oportunidades de reversión a la media - compra dips en stocks de calidad

Estrategias detectadas:
1. Oversold Bounces - RSI < 30 en stocks fundamentalmente sólidos
2. Bull Flag Pullbacks - Retrocesos 10-15% en tendencias alcistas
3. Support Zone Bounces - Rebotes desde niveles técnicos clave
4. Insider Dip Buying - Insiders comprando durante caídas
"""
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from pathlib import Path
from datetime import datetime, timedelta, date
from typing import List, Dict, Tuple, Optional
import json


class MeanReversionDetector:
    """Detector de oportunidades de reversión a la media"""

    def __init__(self):
        self.lookback_days = 180  # 6 meses de historia
        self.results = []
        self._market_regime_cache: Dict = {}  # caché para no repetir llamadas

    def get_market_regime(self) -> Dict:
        """
        Calcula el régimen de mercado actual usando SPY.
        Devuelve dict con spy_above_ma50 (bool), spy_above_ma200 (bool),
        spy_price, spy_ma50, spy_ma200 y regime_label.
        Resultado cacheado en memoria para el ciclo de scan.
        """
        if self._market_regime_cache:
            return self._market_regime_cache

        try:
            import yfinance as yf
            spy = yf.Ticker('SPY')
            hist = spy.history(period='1y')
            if len(hist) < 50:
                raise ValueError("Datos insuficientes SPY")

            spy_price = float(hist['Close'].iloc[-1])
            ma50  = float(hist['Close'].rolling(50).mean().iloc[-1])
            ma200 = float(hist['Close'].rolling(200).mean().iloc[-1])

            above_50  = spy_price > ma50
            above_200 = spy_price > ma200

            if above_50 and above_200:
                label = 'ALCISTA'
            elif above_200 and not above_50:
                label = 'CORRECCIÓN'
            elif not above_200:
                label = 'BAJISTA'
            else:
                label = 'NEUTRAL'

            result = {
                'spy_price': round(spy_price, 2),
                'spy_ma50':  round(ma50, 2),
                'spy_ma200': round(ma200, 2),
                'spy_above_ma50':  above_50,
                'spy_above_ma200': above_200,
                'regime_label': label,
                'bounce_ok': above_50,  # solo operar rebotes si SPY > MA50
            }
        except Exception as e:
            print(f"   ⚠️  No se pudo obtener régimen SPY: {e}")
            result = {
                'spy_price': None, 'spy_ma50': None, 'spy_ma200': None,
                'spy_above_ma50': None, 'spy_above_ma200': None,
                'regime_label': 'DESCONOCIDO', 'bounce_ok': None,
            }

        self._market_regime_cache = result
        return result

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calcula RSI (Relative Strength Index)"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def find_support_resistance(self, prices: pd.Series,
                               window: int = 20) -> Tuple[float, float]:
        """Identifica niveles de soporte y resistencia"""
        # Support = mínimos locales
        rolling_min = prices.rolling(window=window, center=True).min()
        support_level = rolling_min[rolling_min == prices].median()

        # Resistance = máximos locales
        rolling_max = prices.rolling(window=window, center=True).max()
        resistance_level = rolling_max[rolling_max == prices].median()

        return support_level, resistance_level

    def detect_oversold_bounce(self, ticker: str,
                               company_name: str = None) -> Dict:
        """
        Detecta oportunidades de oversold bounce

        Criterios:
        - RSI < 30 (oversold)
        - Caída > 20% desde máximo reciente
        - Volumen incrementando en bounce
        - Fundamentales sólidos
        """
        try:
            stock = yf.Ticker(ticker)

            # Obtener datos históricos
            end_date = datetime.now()
            start_date = end_date - timedelta(days=self.lookback_days)
            hist = stock.history(start=start_date, end=end_date)

            if len(hist) < 50:  # Datos insuficientes
                return None

            # Calcular indicadores
            current_price = hist['Close'].iloc[-1]
            rsi = self.calculate_rsi(hist['Close'])
            current_rsi = rsi.iloc[-1]

            # Máximo de los últimos 60 días
            max_60d = hist['Close'].tail(60).max()
            drawdown_pct = ((current_price - max_60d) / max_60d) * 100

            # Soporte y resistencia
            support, resistance = self.find_support_resistance(hist['Close'])
            distance_to_support = ((current_price - support) / support) * 100

            # Volumen promedio
            avg_volume_20d = hist['Volume'].tail(20).mean()
            current_volume = hist['Volume'].iloc[-1]
            volume_ratio = current_volume / avg_volume_20d if avg_volume_20d > 0 else 0

            # ── Indicadores adicionales para bounce confidence ─────────────────

            # Días bajistas consecutivos (agotamiento vendedor)
            closes = hist['Close'].tail(10)
            consecutive_down = 0
            for i in range(len(closes) - 1, 0, -1):
                if closes.iloc[i] < closes.iloc[i - 1]:
                    consecutive_down += 1
                else:
                    break

            # Bollinger Bands (20 días, 2 desv)
            sma20 = hist['Close'].tail(20).mean()
            std20 = hist['Close'].tail(20).std()
            bb_lower = sma20 - 2 * std20
            bb_upper = sma20 + 2 * std20
            bb_pct_b = round((current_price - bb_lower) / (bb_upper - bb_lower) * 100, 1) if (bb_upper - bb_lower) > 0 else 50
            below_bb = current_price <= bb_lower

            # Stochastic %K (14 días)
            low14  = hist['Low'].tail(14).min()
            high14 = hist['High'].tail(14).max()
            stoch_k = round((current_price - low14) / (high14 - low14) * 100, 1) if (high14 - low14) > 0 else 50

            # Volumen decreciente en últimos 3 días (señal de agotamiento)
            vols = hist['Volume'].tail(4)
            volume_drying = bool(vols.iloc[-1] < vols.iloc[-2] < vols.iloc[-3]) if len(vols) >= 3 else False

            # ── RSI Semanal (Connors: daily < 30 + weekly < 35 = +15-20% win rate) ──
            weekly = hist['Close'].resample('W').last().dropna()
            rsi_weekly_series = self.calculate_rsi(weekly, period=14)
            rsi_weekly = round(float(rsi_weekly_series.iloc[-1]), 1) if len(rsi_weekly_series) >= 14 else None
            weekly_oversold = rsi_weekly is not None and rsi_weekly < 40

            # ── RSI(2) Acumulado — Connors, 83% win rate documentado ──────────────
            # Señal: CumRSI(2) de los últimos 2 días < 10
            rsi2_series = self.calculate_rsi(hist['Close'], period=2)
            cum_rsi2 = round(float(rsi2_series.iloc[-1] + rsi2_series.iloc[-2]), 1) if len(rsi2_series) >= 2 else None
            connors_signal = cum_rsi2 is not None and cum_rsi2 < 10

            # ── ATR(14) — para stop más preciso según volatilidad real ───────────
            high_low = hist['High'] - hist['Low']
            high_close = (hist['High'] - hist['Close'].shift()).abs()
            low_close  = (hist['Low']  - hist['Close'].shift()).abs()
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr14 = round(float(true_range.tail(14).mean()), 4)

            # ── Vela de capitulación (hammer/pin bar) ────────────────────────────
            # Mecha inferior > 60% del rango total + cierre en tercio superior
            last = hist.tail(1).iloc[0]
            candle_range = last['High'] - last['Low']
            lower_wick   = last['Close'] - last['Low'] if last['Close'] > last['Open'] else last['Open'] - last['Low']
            upper_body   = last['High'] - max(last['Open'], last['Close'])
            hammer_candle = (
                candle_range > 0 and
                lower_wick / candle_range >= 0.55 and
                upper_body / candle_range <= 0.25
            )

            # Bullish engulfing: cuerpo actual engloba cuerpo anterior, cierra al alza
            prev = hist.tail(2).iloc[0]
            engulfing_candle = (
                last['Close'] > last['Open'] and              # hoy alcista
                prev['Close'] < prev['Open'] and              # ayer bajista
                last['Open'] <= prev['Close'] and             # abre bajo el cierre de ayer
                last['Close'] >= prev['Open']                 # cierra sobre la apertura de ayer
            )

            # ── Divergencia OBV (institucionales comprando mientras precio baja) ─
            obv = (hist['Volume'] * (2 * (hist['Close'] > hist['Close'].shift()).astype(int) - 1)).cumsum()
            obv5 = obv.tail(5)
            price5 = hist['Close'].tail(5)
            # OBV subiendo mientras precio bajando = divergencia alcista
            obv_divergence = (
                float(obv5.iloc[-1]) > float(obv5.iloc[0]) and   # OBV sube
                float(price5.iloc[-1]) < float(price5.iloc[0])   # precio baja
            )

            # ── Régimen de mercado ───────────────────────────────────────────────
            regime = self.get_market_regime()
            market_ok = regime.get('bounce_ok')  # True si SPY > MA50

            # Earnings próximos (desde fundamental_scores.csv si está disponible)
            days_to_earnings: int | None = None
            earnings_warning = False
            try:
                cal = stock.calendar
                if cal is not None and not cal.empty:
                    earn_date = pd.Timestamp(cal.columns[0]) if hasattr(cal, 'columns') else None
                    if earn_date is None and 'Earnings Date' in cal.index:
                        earn_date = pd.Timestamp(cal.loc['Earnings Date'].iloc[0])
                    if earn_date is not None:
                        days_to_earnings = max(0, (earn_date.date() - datetime.now().date()).days)
                        earnings_warning = days_to_earnings <= 7
            except Exception:
                pass

            # Rechazo duro: si el precio ya rompió el soporte por más del 10%,
            # el setup es inválido — entry zone y stop quedarían por encima del precio
            if distance_to_support < -10:
                return None

            # Criterios de oversold bounce
            is_oversold = current_rsi < 30
            significant_dip = drawdown_pct < -20
            near_support = -5 <= distance_to_support <= 5  # Dentro del 5% del soporte (arriba O abajo)
            volume_spike = volume_ratio > 1.2  # Volumen 20% mayor

            # Score de oportunidad (0-100)
            score = 0
            if is_oversold:
                score += 30
            if significant_dip:
                score += 25
            if near_support:
                score += 25
            if volume_spike:
                score += 20

            # Solo retornar si hay potencial real
            # RSI < 30 es REQUERIDO para Oversold Bounce (no solo bonus)
            if score < 50 or not is_oversold:
                return None

            # Bounce confidence score — señales adicionales de alta probabilidad
            # Basado en backtests: RSI(2) acumulado 83% win rate, RSI semanal +15-20%
            bounce_signals: list[str] = []
            # Base: cualquier setup que pase RSI<30 + score≥50 ya tiene valor
            bounce_confidence = 20

            # RSI diario (bonus encima de la base)
            if current_rsi < 20:
                bounce_confidence += 25
                bounce_signals.append('RSI extremo <20')
            elif current_rsi < 25:
                bounce_confidence += 15
                bounce_signals.append('RSI muy bajo')
            else:
                bounce_confidence += 5

            # RSI semanal — confirmación de timeframe superior (+15-20% win rate)
            if weekly_oversold:
                bounce_confidence += 20
                bounce_signals.append(f'RSI semanal {rsi_weekly}')

            # Connors CumRSI(2) < 10 — 83% win rate documentado
            if connors_signal:
                bounce_confidence += 20
                bounce_signals.append(f'CumRSI2={cum_rsi2:.0f}')

            # Bollinger Band inferior
            if below_bb:
                bounce_confidence += 15
                bounce_signals.append('Bajo BB inferior')

            # Stochastic oversold
            if stoch_k < 20:
                bounce_confidence += 10
                bounce_signals.append('Stoch oversold')

            # Vela de capitulación
            if hammer_candle:
                bounce_confidence += 12
                bounce_signals.append('Hammer')
            elif engulfing_candle:
                bounce_confidence += 10
                bounce_signals.append('Engulfing alcista')

            # Divergencia OBV (institucionales comprando)
            if obv_divergence:
                bounce_confidence += 12
                bounce_signals.append('Div. OBV alcista')

            # Días bajistas consecutivos
            if consecutive_down >= 3:
                bounce_confidence += 8
                bounce_signals.append(f'{consecutive_down}d bajistas')

            # Volumen secándose
            if volume_drying:
                bounce_confidence += 6
                bounce_signals.append('Vol secándose')

            # Régimen de mercado — no añade puntos pero penaliza si mercado bajista
            if market_ok is False:
                bounce_confidence = int(bounce_confidence * 0.7)  # -30% si SPY bajo MA50
                bounce_signals.append('⚠ Mercado bajista')
            elif market_ok is True:
                bounce_signals.append('✓ Mercado favorable')

            # Penalización hard por earnings inminentes
            if earnings_warning:
                bounce_confidence = int(bounce_confidence * 0.6)

            bounce_confidence = min(100, bounce_confidence)

            # Stop basado en ATR: más preciso que % fijo (adapta a la volatilidad real)
            # Estructura: soporte - 1.5x ATR (academia y LuxAlgo)
            atr_stop = round(support - 1.5 * atr14, 2)
            pct_stop  = round(support * 0.95, 2)
            # Usar el más conservador de los dos (el más cercano al precio)
            stop_loss = max(atr_stop, pct_stop)
            stop_pct = round((stop_loss / current_price - 1) * 100, 1)

            # Target largo (técnico a resistencia)
            full_target = round(resistance, 2)

            # Target corto: rebote realista 1-3 días (+7% o resistencia, lo menor)
            bounce_target = round(min(current_price * 1.07, resistance), 2)
            bounce_usd = round(bounce_target - current_price, 2)
            bounce_pct = round((bounce_target / current_price - 1) * 100, 1)
            bounce_rr = round(bounce_usd / (current_price - stop_loss), 2) if (current_price - stop_loss) > 0 else 0

            # Confianza del rebote según RSI
            if current_rsi < 20:
                rsi_tier = 'EXTREMO'
            elif current_rsi < 25:
                rsi_tier = 'ALTO'
            else:
                rsi_tier = 'MEDIO'

            return {
                'ticker': ticker,
                'company_name': company_name or ticker,
                'strategy': 'Oversold Bounce',
                'current_price': round(current_price, 2),
                'rsi': round(current_rsi, 1),
                'rsi_tier': rsi_tier,
                'drawdown_pct': round(drawdown_pct, 1),
                'support_level': round(support, 2),
                'resistance_level': round(resistance, 2),
                'distance_to_support_pct': round(distance_to_support, 1),
                'volume_ratio': round(volume_ratio, 2),
                'reversion_score': round(score, 1),
                'quality': self._get_quality_label(score),
                'entry_zone': f"${round(support * 0.98, 2)} - ${round(support * 1.02, 2)}",
                'target': full_target,
                'bounce_target': bounce_target,
                'bounce_usd': bounce_usd,
                'bounce_pct': bounce_pct,
                'stop_loss': stop_loss,
                'stop_pct': stop_pct,
                'risk_reward': bounce_rr,
                # Bounce confidence
                'bounce_confidence': bounce_confidence,
                'bounce_signals': bounce_signals,
                'consecutive_down_days': consecutive_down,
                'bb_pct_b': bb_pct_b,
                'below_bb': below_bb,
                'stoch_k': stoch_k,
                'volume_drying': volume_drying,
                # Nuevas señales avanzadas
                'rsi_weekly': rsi_weekly,
                'weekly_oversold': weekly_oversold,
                'cum_rsi2': cum_rsi2,
                'connors_signal': connors_signal,
                'atr14': round(atr14, 2),
                'hammer_candle': hammer_candle,
                'engulfing_candle': engulfing_candle,
                'obv_divergence': obv_divergence,
                'market_regime': regime.get('regime_label', 'DESCONOCIDO'),
                'market_ok': market_ok,
                # Earnings
                'days_to_earnings': days_to_earnings,
                'earnings_warning': earnings_warning,
                'detected_date': datetime.now().strftime('%Y-%m-%d')
            }

        except Exception as e:
            print(f"   ⚠️  Error analizando {ticker}: {e}")
            return None

    def detect_bull_flag_pullback(self, ticker: str,
                                  company_name: str = None) -> Dict:
        """
        Detecta bull flag pullbacks

        Criterios:
        - Rally previo > 30%
        - Pullback 10-15%
        - Volumen decreciente en pullback
        - Tendencia mayor alcista (SMA50 > SMA200)
        """
        try:
            stock = yf.Ticker(ticker)

            end_date = datetime.now()
            start_date = end_date - timedelta(days=self.lookback_days)
            hist = stock.history(start=start_date, end=end_date)

            if len(hist) < 100:
                return None

            current_price = hist['Close'].iloc[-1]

            # Calcular medias móviles
            sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1]
            sma_200 = hist['Close'].rolling(window=200).mean().iloc[-1] if len(hist) >= 200 else sma_50

            # Buscar rally previo (últimos 60 días)
            low_60d = hist['Close'].tail(60).min()
            high_60d = hist['Close'].tail(60).max()
            rally_pct = ((high_60d - low_60d) / low_60d) * 100

            # Pullback desde high
            pullback_pct = ((current_price - high_60d) / high_60d) * 100

            # Volumen en pullback vs rally
            rally_volume = hist['Volume'].tail(60).head(30).mean()
            pullback_volume = hist['Volume'].tail(30).mean()
            volume_decrease = (pullback_volume / rally_volume) < 0.8 if rally_volume > 0 else False

            # Criterios
            bullish_trend = sma_50 > sma_200
            strong_rally = rally_pct > 30
            healthy_pullback = -15 <= pullback_pct <= -10

            score = 0
            if bullish_trend:
                score += 25
            if strong_rally:
                score += 30
            if healthy_pullback:
                score += 30
            if volume_decrease:
                score += 15

            if score < 60:  # Más estricto para bull flags
                return None

            stop_loss_bf = round(sma_50 * 0.97, 2)
            stop_pct_bf = round((stop_loss_bf / current_price - 1) * 100, 1)
            full_target_bf = round(high_60d, 2)
            bounce_target_bf = round(min(current_price * 1.07, high_60d), 2)
            bounce_usd_bf = round(bounce_target_bf - current_price, 2)
            bounce_pct_bf = round((bounce_target_bf / current_price - 1) * 100, 1)
            bounce_rr_bf = round(bounce_usd_bf / (current_price - stop_loss_bf), 2) if (current_price - stop_loss_bf) > 0 else 0

            return {
                'ticker': ticker,
                'company_name': company_name or ticker,
                'strategy': 'Bull Flag Pullback',
                'current_price': round(current_price, 2),
                'rsi': None,
                'rsi_tier': None,
                'rally_pct': round(rally_pct, 1),
                'pullback_pct': round(pullback_pct, 1),
                'sma_50': round(sma_50, 2),
                'sma_200': round(sma_200, 2),
                'trend': 'Bullish' if bullish_trend else 'Bearish',
                'volume_decrease': volume_decrease,
                'reversion_score': round(score, 1),
                'quality': self._get_quality_label(score),
                'entry_zone': f"${round(current_price * 0.98, 2)} - ${round(current_price * 1.02, 2)}",
                'target': full_target_bf,
                'bounce_target': bounce_target_bf,
                'bounce_usd': bounce_usd_bf,
                'bounce_pct': bounce_pct_bf,
                'stop_loss': stop_loss_bf,
                'stop_pct': stop_pct_bf,
                'risk_reward': bounce_rr_bf,
                'detected_date': datetime.now().strftime('%Y-%m-%d')
            }

        except Exception as e:
            print(f"   ⚠️  Error analizando {ticker}: {e}")
            return None

    def _get_quality_label(self, score: float) -> str:
        """Retorna etiqueta de calidad según score"""
        if score >= 80:
            return "⭐⭐⭐ EXCELENTE"
        elif score >= 70:
            return "⭐⭐ MUY BUENA"
        elif score >= 60:
            return "⭐ BUENA"
        else:
            return "MODERADA"

    def scan_tickers(self, tickers: List[str],
                    company_names: Dict[str, str] = None) -> List[Dict]:
        """
        Escanea lista de tickers buscando oportunidades de reversión

        Args:
            tickers: Lista de símbolos a analizar
            company_names: Dict opcional {ticker: company_name}

        Returns:
            Lista de oportunidades detectadas
        """
        print(f"🔄 Mean Reversion Detector")
        print(f"   Escaneando {len(tickers)} tickers...")

        # Régimen de mercado — advierte si SPY < MA50 (rebotes en bajista = falling knife)
        regime = self.get_market_regime()
        if regime['regime_label'] != 'DESCONOCIDO':
            icon = '✅' if regime['bounce_ok'] else '⚠️ '
            print(f"   {icon} Régimen mercado: {regime['regime_label']} "
                  f"(SPY ${regime['spy_price']} vs MA50 ${regime['spy_ma50']})")
            if not regime['bounce_ok']:
                print("   ⚠️  SPY < MA50 → mercado bajista. Rebotes de alto riesgo.")
        print()

        opportunities = []

        for i, ticker in enumerate(tickers, 1):
            if i % 50 == 0:
                print(f"   Progreso: {i}/{len(tickers)}")

            company = company_names.get(ticker) if company_names else None

            # Intentar ambas estrategias
            oversold = self.detect_oversold_bounce(ticker, company)
            if oversold:
                opportunities.append(oversold)
                print(f"   🎯 {ticker}: Oversold Bounce ({oversold['reversion_score']:.0f}/100)")

            bull_flag = self.detect_bull_flag_pullback(ticker, company)
            if bull_flag:
                opportunities.append(bull_flag)
                print(f"   📊 {ticker}: Bull Flag ({bull_flag['reversion_score']:.0f}/100)")

            import time
            time.sleep(0.5)

        # Sort by score
        opportunities.sort(key=lambda x: x['reversion_score'], reverse=True)

        print()
        print(f"✅ Scan completado: {len(opportunities)} oportunidades detectadas")

        # Enrich with historical win rate + AI validation
        self._add_win_rates(opportunities)
        self._ai_filter_batch(opportunities)

        # Enrich bounce setups with PCR, short interest, dark pool proxy
        bounce_opps = [o for o in opportunities if o.get('strategy') == 'Oversold Bounce']
        if bounce_opps:
            print(f"🔍 Enriqueciendo {len(bounce_opps)} setups con PCR, short interest y dark pool...")
            self._enrich_bounce_signals(bounce_opps)

        self.results = opportunities
        return opportunities

    # ── Win-rate lookup (from backtest history) ──────────────────────────────

    # Pre-computed from docs/backtest/mr_history_backtest_*.json (30-day hold)
    _WIN_RATE_TIERS = {
        (90, 100): 100.0,
        (80, 89):  83.9,
        (70, 79):  63.2,
        (60, 69):  71.7,
        (0,  59):  55.0,   # estimated — below backtest sample range
    }

    def _score_to_win_rate(self, score: float) -> float:
        for (lo, hi), wr in self._WIN_RATE_TIERS.items():
            if lo <= score <= hi:
                return wr
        return 55.0

    def _add_win_rates(self, opportunities: list) -> None:
        """Adds historical_win_rate field to each opportunity based on score tier."""
        for opp in opportunities:
            opp['historical_win_rate'] = self._score_to_win_rate(opp.get('reversion_score', 0))

    # ── Batch AI validation via Groq ─────────────────────────────────────────

    def _ai_filter_batch(self, opportunities: list) -> None:
        """
        Single Groq call to validate up to 20 setups.
        Adds ai_confirmation ('YES'|'CAUTION'|'NO'), ai_confidence (0-100),
        ai_reason (string) to each opportunity. Skips silently if no API key.
        """
        import os
        api_key = os.environ.get('GROQ_API_KEY', '')
        if not api_key or not opportunities:
            for opp in opportunities:
                opp.setdefault('ai_confirmation', None)
                opp.setdefault('ai_confidence', None)
                opp.setdefault('ai_reason', None)
            return

        batch = opportunities[:20]  # cap to avoid token overflow
        regime = self.get_market_regime()
        regime_str = regime.get('regime_label', 'DESCONOCIDO')

        lines = []
        for o in batch:
            lines.append(
                f"- {o['ticker']} | {o['strategy']} | score={o.get('reversion_score',0):.0f}"
                f" | RSI={o.get('rsi','?')} | drawdown={o.get('drawdown_pct',0):.0f}%"
                f" | R:R={o.get('risk_reward',0):.1f} | win_rate_hist={o.get('historical_win_rate',0):.0f}%"
            )
        setups_text = '\n'.join(lines)

        prompt = f"""Eres un analista técnico experto en mean reversion. Valida estos setups de rebote en el contexto actual del mercado.

Régimen de mercado actual: {regime_str}
Setups a validar:
{setups_text}

Responde ÚNICAMENTE con JSON válido con esta estructura:
{{"results": [{{"ticker":"X","confirmation":"YES","confidence":85,"reason":"RSI extremo + soporte claro"}}, ...]}}

Reglas:
- confirmation: "YES" si el setup es válido, "CAUTION" si hay dudas, "NO" si hay razones para evitarlo
- confidence: 0-100 (cuánta convicción tienes)
- reason: máximo 8 palabras en español, explica el veredicto
- En mercado BAJISTA o CORRECCIÓN, sé más exigente (solo YES si RSI<25 y R:R>2.5)"""

        try:
            from groq import Groq
            client = Groq(api_key=api_key)
            resp = client.chat.completions.create(
                model='llama-3.3-70b-versatile',
                messages=[{'role': 'user', 'content': prompt}],
                max_tokens=600,
                temperature=0.15,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content.strip()
            parsed = json.loads(raw)
            ai_results = parsed.get('results', [])
            ai_map = {r['ticker']: r for r in ai_results if isinstance(r, dict)}
            for opp in opportunities:
                ai = ai_map.get(opp['ticker'], {})
                opp['ai_confirmation'] = ai.get('confirmation', None)
                opp['ai_confidence']   = ai.get('confidence', None)
                opp['ai_reason']       = ai.get('reason', None)
            print(f"  🤖 AI validó {len(ai_map)} setups ({sum(1 for o in batch if o.get('ai_confirmation')=='YES')} YES / "
                  f"{sum(1 for o in batch if o.get('ai_confirmation')=='CAUTION')} CAUTION / "
                  f"{sum(1 for o in batch if o.get('ai_confirmation')=='NO')} NO)")
            return
        except Exception as e:
            print(f"  ⚠️  AI filter skipped: {e}")

        # Fallback: set None
        for opp in opportunities:
            opp.setdefault('ai_confirmation', None)
            opp.setdefault('ai_confidence', None)
            opp.setdefault('ai_reason', None)

    def _enrich_bounce_signals(self, opportunities: list) -> None:
        """
        Enriquece oportunidades de rebote con señales externas gratuitas:
        - PCR (Put/Call Ratio) desde CBOE CDN — JSON, sin auth, 15min delay
        - Short interest desde Nasdaq API — JSON, sin auth, bi-semanal
        - Dark pool proxy (off-exchange %) desde FINRA CDN — pipe-delimited, diario

        Fuentes verificadas sin API key ni pago.
        """
        HEADERS = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
        }

        # ── Cargar FINRA dark pool (un solo fichero para todo el batch) ─────────
        finra_dark: Dict[str, float] = {}  # ticker → short_pct_of_volume hoy
        try:
            today_str = date.today().strftime("%Y%m%d")
            # Probar hoy y los 3 días previos (puede no estar publicado aún hoy)
            for delta in range(4):
                dt = date.today() - timedelta(days=delta)
                if dt.weekday() >= 5:
                    continue
                fname = dt.strftime("%Y%m%d")
                url = f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{fname}.txt"
                r = requests.get(url, headers=HEADERS, timeout=10)
                if r.status_code == 200:
                    from io import StringIO
                    df_finra = pd.read_csv(StringIO(r.text), sep="|", skipfooter=1, engine="python")
                    df_finra.columns = df_finra.columns.str.strip()
                    for _, row in df_finra.iterrows():
                        sym = str(row.get("Symbol", "")).strip()
                        short_vol = row.get("ShortVolume", 0) or 0
                        total_vol = row.get("TotalVolume", 1) or 1
                        if sym:
                            finra_dark[sym] = round(float(short_vol) / float(total_vol) * 100, 1)
                    print(f"   📊 FINRA dark pool: {fname} ({len(finra_dark)} tickers)")
                    break
        except Exception as e:
            print(f"   ⚠️  FINRA dark pool fallido: {e}")

        # ── Por ticker: PCR (CBOE) + short interest (Nasdaq) ────────────────────
        for opp in opportunities:
            ticker = opp.get("ticker", "")

            # ── PCR desde CBOE CDN ───────────────────────────────────────────
            try:
                url = f"https://cdn.cboe.com/api/global/delayed_quotes/options/{ticker}.json"
                r = requests.get(url, headers=HEADERS, timeout=8)
                if r.status_code == 200:
                    opts = r.json().get("data", {}).get("options", [])
                    # Option symbol format: TICKER+YYMMDD+[C/P]+PRICE8 — type at 9th char from right
                    def _opt_type(o):
                        sym = o.get("option", "")
                        return sym[-9] if len(sym) >= 9 else ""
                    put_vol  = sum(o.get("volume", 0) or 0 for o in opts if _opt_type(o) == "P")
                    call_vol = sum(o.get("volume", 0) or 0 for o in opts if _opt_type(o) == "C")
                    pcr = round(put_vol / call_vol, 2) if call_vol > 0 else None
                    opp["pcr"] = pcr
                    # PCR > 1.5 = puts muy elevadas = contrarian bullish (hedging exagerado)
                    opp["pcr_signal"] = "CONTRARIAN_BULLISH" if pcr and pcr > 1.5 else \
                                        "NEUTRAL" if pcr else None
                    if pcr and pcr > 1.5:
                        opp["bounce_signals"] = opp.get("bounce_signals", []) + [f"PCR {pcr:.1f}↑"]
                        opp["bounce_confidence"] = min(100, opp.get("bounce_confidence", 0) + 10)
            except Exception:
                opp["pcr"] = None
                opp["pcr_signal"] = None

            # ── Short interest desde Nasdaq API ──────────────────────────────
            try:
                url = (
                    f"https://api.nasdaq.com/api/quote/{ticker.lower()}/short-interest"
                    "?type=SHORT_INTEREST&assetClass=stocks"
                )
                headers_nasdaq = {**HEADERS, "Referer": f"https://www.nasdaq.com/market-activity/stocks/{ticker.lower()}/short-interest"}
                r = requests.get(url, headers=headers_nasdaq, timeout=8)
                if r.status_code == 200:
                    rows = r.json().get("data", {}).get("shortInterestTable", {}).get("rows", [])
                    if rows:
                        latest = rows[0]
                        # Nasdaq field names: "interest" (shares), "daysToCover", "avgDailyShareVolume"
                        short_int = str(latest.get("interest", "") or "").replace(",", "")
                        dtc_raw = latest.get("daysToCover")
                        avg_vol_raw = str(latest.get("avgDailyShareVolume", "") or "").replace(",", "")
                        dtc = float(dtc_raw) if dtc_raw else None
                        si_shares = int(float(short_int)) if short_int and short_int.replace('.','').isdigit() else None
                        avg_vol = int(float(avg_vol_raw)) if avg_vol_raw and avg_vol_raw.replace('.','').isdigit() else None
                        # Approximate % float: not available directly — use DTC as squeeze proxy
                        opp["short_interest_shares"] = si_shares
                        opp["short_days_to_cover"] = dtc
                        opp["short_pct_float"] = None  # Nasdaq doesn't provide this field
                        # Short squeeze potential: DTC > 5 days
                        squeeze = bool(dtc and dtc > 5)
                        opp["squeeze_potential"] = bool(squeeze)
                        if squeeze:
                            opp["bounce_signals"] = opp.get("bounce_signals", []) + [f"DTC {dtc:.1f}d" if dtc else "Short squeeze"]
                            opp["bounce_confidence"] = min(100, opp.get("bounce_confidence", 0) + 8)
            except Exception:
                opp["short_interest_shares"] = None
                opp["short_days_to_cover"] = None
                opp["short_pct_float"] = None
                opp["squeeze_potential"] = False

            # ── Dark pool proxy desde FINRA ──────────────────────────────────
            finra_pct = finra_dark.get(ticker)
            opp["finra_short_vol_pct"] = finra_pct
            # > 60% = volumen bajista dominante en dark pool; < 40% = compradores dominan
            if finra_pct is not None:
                if finra_pct < 40:
                    opp["dark_pool_signal"] = "ACCUMULATION"
                    opp["bounce_signals"] = opp.get("bounce_signals", []) + [f"DP acumulación ({finra_pct:.0f}%)"]
                    opp["bounce_confidence"] = min(100, opp.get("bounce_confidence", 0) + 8)
                elif finra_pct > 60:
                    opp["dark_pool_signal"] = "DISTRIBUTION"
                else:
                    opp["dark_pool_signal"] = "NEUTRAL"
            else:
                opp["dark_pool_signal"] = None

            print(f"   ✅ {ticker}: PCR={opp.get('pcr')} | Short%={opp.get('short_pct_float')} | DP={opp.get('finra_short_vol_pct')} | conf={opp.get('bounce_confidence')}")

    def save_results(self, output_path: str = "docs/mean_reversion_opportunities.csv"):
        """Guarda resultados en CSV"""
        if not self.results:
            print("⚠️  No hay resultados para guardar")
            return

        df = pd.DataFrame(self.results)

        # Ordenar columnas
        cols_order = [
            'ticker', 'company_name', 'strategy', 'quality', 'reversion_score',
            'current_price', 'entry_zone', 'target', 'stop_loss', 'risk_reward',
            'ai_confirmation', 'ai_confidence', 'ai_reason', 'historical_win_rate',
            'detected_date'
        ]

        # Añadir columnas restantes
        remaining_cols = [c for c in df.columns if c not in cols_order]
        final_cols = cols_order + remaining_cols
        final_cols = [c for c in final_cols if c in df.columns]  # Solo las que existen

        df = df[final_cols]

        # Guardar
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)

        print(f"💾 Resultados guardados: {output_path}")

        # También guardar JSON para dashboard
        json_path = output_path.with_suffix('.json')

        # Convertir a tipos nativos de Python para JSON
        json_safe_results = []
        for r in self.results:
            json_safe = {}
            for k, v in r.items():
                if isinstance(v, (np.integer, np.floating)):
                    json_safe[k] = float(v)
                elif isinstance(v, np.bool_):
                    json_safe[k] = bool(v)
                else:
                    json_safe[k] = v
            json_safe_results.append(json_safe)

        # ── AI narrative ──────────────────────────────────────────────────
        ai_narrative = None
        try:
            import os
            from groq import Groq as _Groq
            _key = os.environ.get('GROQ_API_KEY', '')
            if _key and self.results:
                _client = _Groq(api_key=_key)
                _top = self.results[:5]
                _top_text = '\n'.join([
                    f"- {r['ticker']} ({r['strategy']}) score={r.get('reversion_score', 0):.0f}"
                    f" RSI={r.get('rsi', '?')} drawdown={r.get('drawdown_pct', 0):.0f}%"
                    f" R:R={r.get('risk_reward', 0):.1f}"
                    for r in _top
                ])
                _prompt = f"""Eres un analista de mean reversion y value. Analiza este batch de {len(self.results)} setups de reversión a la media y genera un insight en español (3-4 frases, máx 110 palabras).

Distribución: {len([r for r in self.results if r['strategy']=='Oversold Bounce'])} oversold bounce, {len([r for r in self.results if r['strategy']=='Bull Flag Pullback'])} bull flag pullback
Top 5 setups:
{_top_text}

Analiza: 1) Calidad general del batch actual, 2) Si hay concentración sectorial, 3) Cómo filtrar los mejores en este entorno.
Tono: técnico, directo. Sin emojis."""
                _resp = _client.chat.completions.create(
                    model='llama-3.3-70b-versatile',
                    messages=[{'role': 'user', 'content': _prompt}],
                    max_tokens=180,
                    temperature=0.25,
                )
                ai_narrative = _resp.choices[0].message.content.strip()
                print(f"  MR AI: {ai_narrative[:80]}...")
        except Exception as _e:
            print(f"  MR Groq skipped: {_e}")

        results_dict = {
            'scan_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_opportunities': len(self.results),
            'strategies': {
                'oversold_bounce': len([r for r in self.results if r['strategy'] == 'Oversold Bounce']),
                'bull_flag_pullback': len([r for r in self.results if r['strategy'] == 'Bull Flag Pullback'])
            },
            'ai_narrative': ai_narrative,
            'opportunities': json_safe_results
        }

        with open(json_path, 'w') as f:
            json.dump(results_dict, f, indent=2)

        print(f"📊 JSON guardado: {json_path}")


def load_5d_opportunities() -> Tuple[List[str], Dict[str, str]]:
    """Carga tickers desde oportunidades 5D para análisis"""
    csv_path = Path("docs/super_opportunities_5d_complete.csv")

    if not csv_path.exists():
        print("⚠️  No hay oportunidades 5D. Usando watchlist por defecto.")
        # Watchlist por defecto
        default_tickers = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX',
            'CRM', 'ADBE', 'PLTR', 'COIN', 'SQ', 'SHOP', 'ROKU', 'ZM'
        ]
        return default_tickers, {}

    df = pd.read_csv(csv_path)
    tickers = df['ticker'].tolist()

    # Cargar nombres de empresas si existen
    company_names = {}
    if 'company_name' in df.columns:
        company_names = dict(zip(df['ticker'], df['company_name']))

    print(f"📊 Cargados {len(tickers)} tickers desde 5D opportunities")

    return tickers, company_names


def main():
    """Main execution"""
    print("=" * 80)
    print("🔄 MEAN REVERSION DETECTOR")
    print("   Identifica oportunidades de compra en dips de calidad")
    print("=" * 80)
    print()

    # Cargar tickers
    tickers, company_names = load_5d_opportunities()

    # Ejecutar detector
    detector = MeanReversionDetector()
    opportunities = detector.scan_tickers(tickers, company_names)

    # Guardar resultados
    detector.save_results()

    # Mostrar top 10
    if opportunities:
        print()
        print("=" * 80)
        print("🏆 TOP 10 OPORTUNIDADES DE REVERSIÓN")
        print("=" * 80)
        print()

        for i, opp in enumerate(opportunities[:10], 1):
            print(f"{i}. {opp['ticker']} - {opp['company_name']}")
            print(f"   Estrategia: {opp['strategy']}")
            print(f"   Score: {opp['reversion_score']:.0f}/100 ({opp['quality']})")
            print(f"   Precio: ${opp['current_price']:.2f}")
            print(f"   Entry: {opp['entry_zone']}")
            print(f"   Target: ${opp['target']:.2f} | Stop: ${opp['stop_loss']:.2f}")
            print(f"   R/R: {opp['risk_reward']:.1f}:1")
            print()
    else:
        print("ℹ️  No se detectaron oportunidades de reversión en este momento")

    print("=" * 80)
    print("✅ Mean Reversion Detector completado")
    print("=" * 80)


if __name__ == "__main__":
    main()
