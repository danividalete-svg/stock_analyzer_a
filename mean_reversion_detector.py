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
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
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

            # Criterios de oversold bounce
            is_oversold = current_rsi < 30
            significant_dip = drawdown_pct < -20
            near_support = distance_to_support < 5  # Dentro del 5% del soporte
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
            if score < 50:
                return None

            return {
                'ticker': ticker,
                'company_name': company_name or ticker,
                'strategy': 'Oversold Bounce',
                'current_price': round(current_price, 2),
                'rsi': round(current_rsi, 1),
                'drawdown_pct': round(drawdown_pct, 1),
                'support_level': round(support, 2),
                'resistance_level': round(resistance, 2),
                'distance_to_support_pct': round(distance_to_support, 1),
                'volume_ratio': round(volume_ratio, 2),
                'reversion_score': round(score, 1),
                'quality': self._get_quality_label(score),
                'entry_zone': f"${round(support * 0.98, 2)} - ${round(support * 1.02, 2)}",
                'target': round(resistance, 2),
                'stop_loss': round(support * 0.95, 2),
                'risk_reward': round((resistance - current_price) / (current_price - support * 0.95), 2) if (current_price - support * 0.95) > 0 else 0,
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

            return {
                'ticker': ticker,
                'company_name': company_name or ticker,
                'strategy': 'Bull Flag Pullback',
                'current_price': round(current_price, 2),
                'rally_pct': round(rally_pct, 1),
                'pullback_pct': round(pullback_pct, 1),
                'sma_50': round(sma_50, 2),
                'sma_200': round(sma_200, 2),
                'trend': 'Bullish' if bullish_trend else 'Bearish',
                'volume_decrease': volume_decrease,
                'reversion_score': round(score, 1),
                'quality': self._get_quality_label(score),
                'entry_zone': f"${round(current_price * 0.98, 2)} - ${round(current_price * 1.02, 2)}",
                'target': round(high_60d, 2),
                'stop_loss': round(sma_50 * 0.97, 2),
                'risk_reward': round((high_60d - current_price) / (current_price - sma_50 * 0.97), 2) if (current_price - sma_50 * 0.97) > 0 else 0,
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

        self.results = opportunities
        return opportunities

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

    # Limitar a primeros 100 para velocidad (puedes cambiar esto)
    if len(tickers) > 100:
        print(f"⚠️  Limitando scan a 100 tickers para velocidad")
        print(f"   (Puedes cambiar esto en el código)")
        tickers = tickers[:100]

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
