#!/usr/bin/env python3
"""
OPTIONS FLOW DETECTOR
Detecta flujo institucional de opciones y actividad inusual

Estrategias detectadas:
1. Unusual Options Activity (UOA) - Volumen anormal
2. Large Block Trades - Bloques institucionales
3. Put/Call Ratio Analysis - Sentiment del mercado
4. Open Interest Spikes - Acumulación institucional
5. Whale Positioning - Movimientos de big money
"""
import yfinance as yf
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import json


class OptionsFlowDetector:
    """Detector de flujo institucional de opciones"""

    def __init__(self):
        self.results = []
        self.min_volume = 100  # Volumen mínimo para considerar
        self.min_premium = 10000  # Premium mínimo ($10k) para bloques

    def get_options_chain(self, ticker: str) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
        """
        Obtiene cadena de opciones para un ticker

        Returns:
            Tuple de (calls DataFrame, puts DataFrame, expiration_date str)
        """
        try:
            stock = yf.Ticker(ticker)

            # Get available expiration dates
            expirations = stock.options

            if not expirations or len(expirations) == 0:
                return None, None, None

            # Get nearest expiration (usually most liquid)
            nearest_exp = expirations[0]

            # Get options chain
            opt_chain = stock.option_chain(nearest_exp)

            calls = opt_chain.calls
            puts = opt_chain.puts

            return calls, puts, nearest_exp

        except Exception as e:
            print(f"   ⚠️  Error obteniendo opciones de {ticker}: {e}")
            return None, None, None

    def detect_unusual_activity(self, ticker: str,
                               company_name: str = None) -> Dict:
        """
        Detecta actividad inusual de opciones

        Criterios:
        - Volumen > 5x promedio de OI (Open Interest)
        - Volumen > 100 contratos
        - Premium total > $10k
        - Ratio volumen/OI anormal
        """
        try:
            calls, puts, expiration_date = self.get_options_chain(ticker)

            if calls is None or puts is None or expiration_date is None:
                return None

            if len(calls) == 0 and len(puts) == 0:
                return None

            stock = yf.Ticker(ticker)
            current_price = stock.info.get('currentPrice', 0)

            if current_price == 0:
                # Fallback to fast_info
                try:
                    current_price = stock.fast_info.get('lastPrice', 0)
                except:
                    return None

            unusual_calls = []
            unusual_puts = []

            # Analyze calls
            if len(calls) > 0:
                for _, row in calls.iterrows():
                    volume = row.get('volume', 0)
                    oi = row.get('openInterest', 0)
                    last_price = row.get('lastPrice', 0)
                    strike = row.get('strike', 0)

                    if volume is None or volume == 0:
                        continue

                    # Calculate metrics
                    vol_oi_ratio = volume / oi if oi > 0 else volume
                    premium = volume * last_price * 100  # Each contract = 100 shares
                    itm = strike < current_price  # In The Money

                    # Unusual activity criteria
                    is_unusual = (
                        volume >= self.min_volume and
                        vol_oi_ratio > 3 and  # Volume is 3x+ open interest
                        premium >= self.min_premium
                    )

                    if is_unusual:
                        unusual_calls.append({
                            'type': 'CALL',
                            'strike': strike,
                            'volume': volume,
                            'oi': oi,
                            'vol_oi_ratio': vol_oi_ratio,
                            'last_price': last_price,
                            'premium': premium,
                            'itm': itm,
                            'implied_volatility': row.get('impliedVolatility', 0)
                        })

            # Analyze puts
            if len(puts) > 0:
                for _, row in puts.iterrows():
                    volume = row.get('volume', 0)
                    oi = row.get('openInterest', 0)
                    last_price = row.get('lastPrice', 0)
                    strike = row.get('strike', 0)

                    if volume is None or volume == 0:
                        continue

                    vol_oi_ratio = volume / oi if oi > 0 else volume
                    premium = volume * last_price * 100
                    itm = strike > current_price

                    is_unusual = (
                        volume >= self.min_volume and
                        vol_oi_ratio > 3 and
                        premium >= self.min_premium
                    )

                    if is_unusual:
                        unusual_puts.append({
                            'type': 'PUT',
                            'strike': strike,
                            'volume': volume,
                            'oi': oi,
                            'vol_oi_ratio': vol_oi_ratio,
                            'last_price': last_price,
                            'premium': premium,
                            'itm': itm,
                            'implied_volatility': row.get('impliedVolatility', 0)
                        })

            # If no unusual activity found
            if len(unusual_calls) == 0 and len(unusual_puts) == 0:
                return None

            # Calculate overall metrics
            total_call_premium = sum(c['premium'] for c in unusual_calls)
            total_put_premium = sum(p['premium'] for p in unusual_puts)
            total_premium = total_call_premium + total_put_premium

            put_call_ratio = total_put_premium / total_call_premium if total_call_premium > 0 else 999

            # Sentiment analysis
            if put_call_ratio > 2:
                sentiment = "BEARISH"
                sentiment_emoji = "🔴"
            elif put_call_ratio < 0.5:
                sentiment = "BULLISH"
                sentiment_emoji = "🟢"
            else:
                sentiment = "NEUTRAL"
                sentiment_emoji = "🟡"

            # Flow score (0-100)
            score = 0

            # Premium size
            if total_premium > 1_000_000:  # $1M+
                score += 40
            elif total_premium > 500_000:  # $500k+
                score += 30
            elif total_premium > 100_000:  # $100k+
                score += 20
            else:
                score += 10

            # Number of unusual contracts
            num_unusual = len(unusual_calls) + len(unusual_puts)
            if num_unusual >= 10:
                score += 30
            elif num_unusual >= 5:
                score += 20
            else:
                score += 10

            # Volume/OI ratios
            avg_vol_oi = np.mean([c['vol_oi_ratio'] for c in unusual_calls] +
                                [p['vol_oi_ratio'] for p in unusual_puts])
            if avg_vol_oi > 10:
                score += 30
            elif avg_vol_oi > 5:
                score += 20
            else:
                score += 10

            # Cap at 100
            score = min(score, 100)

            # Calculate days to expiration
            exp_date = datetime.strptime(expiration_date, '%Y-%m-%d')
            days_to_expiration = (exp_date - datetime.now()).days

            return {
                'ticker': ticker,
                'company_name': company_name or ticker,
                'current_price': round(current_price, 2),
                'expiration_date': expiration_date,
                'days_to_expiration': days_to_expiration,
                'unusual_calls': len(unusual_calls),
                'unusual_puts': len(unusual_puts),
                'total_unusual': num_unusual,
                'call_premium': round(total_call_premium, 2),
                'put_premium': round(total_put_premium, 2),
                'total_premium': round(total_premium, 2),
                'put_call_ratio': round(put_call_ratio, 2),
                'sentiment': sentiment,
                'sentiment_emoji': sentiment_emoji,
                'flow_score': round(score, 1),
                'quality': self._get_quality_label(score),
                'top_calls': sorted(unusual_calls, key=lambda x: x['premium'], reverse=True)[:3],
                'top_puts': sorted(unusual_puts, key=lambda x: x['premium'], reverse=True)[:3],
                'detected_date': datetime.now().strftime('%Y-%m-%d')
            }

        except Exception as e:
            print(f"   ⚠️  Error analizando {ticker}: {e}")
            return None

    def _get_quality_label(self, score: float) -> str:
        """Retorna etiqueta de calidad según score"""
        if score >= 80:
            return "🔥🔥🔥 WHALE ACTIVITY"
        elif score >= 65:
            return "🔥🔥 STRONG FLOW"
        elif score >= 50:
            return "🔥 NOTABLE FLOW"
        else:
            return "MODERATE"

    def scan_tickers(self, tickers: List[str],
                    company_names: Dict[str, str] = None) -> List[Dict]:
        """
        Escanea lista de tickers buscando flujo inusual de opciones

        Args:
            tickers: Lista de símbolos a analizar
            company_names: Dict opcional {ticker: company_name}

        Returns:
            Lista de alertas de flujo detectadas
        """
        print(f"📊 Options Flow Detector")
        print(f"   Escaneando {len(tickers)} tickers...")
        print()

        flows = []

        for i, ticker in enumerate(tickers, 1):
            if i % 25 == 0:
                print(f"   Progreso: {i}/{len(tickers)}")

            company = company_names.get(ticker) if company_names else None

            flow = self.detect_unusual_activity(ticker, company)

            if flow:
                flows.append(flow)
                print(f"   🔥 {ticker}: {flow['sentiment']} - ${flow['total_premium']/1000:.0f}K premium ({flow['flow_score']:.0f}/100)")

            import time
            time.sleep(0.5)

        # Sort by flow score
        flows.sort(key=lambda x: x['flow_score'], reverse=True)

        print()
        print(f"✅ Scan completado: {len(flows)} flujos inusuales detectados")

        self.results = flows
        return flows

    def save_results(self, output_path: str = "docs/options_flow.csv"):
        """Guarda resultados en CSV y JSON"""
        if not self.results:
            print("⚠️  No hay resultados para guardar")
            return

        df = pd.DataFrame(self.results)

        # Ordenar columnas
        cols_order = [
            'ticker', 'company_name', 'sentiment', 'flow_score', 'quality',
            'current_price', 'total_premium', 'put_call_ratio',
            'unusual_calls', 'unusual_puts', 'detected_date'
        ]

        # Añadir columnas restantes
        remaining_cols = [c for c in df.columns if c not in cols_order]
        final_cols = cols_order + remaining_cols
        final_cols = [c for c in final_cols if c in df.columns]

        df = df[final_cols]

        # Guardar CSV
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)

        print(f"💾 Resultados guardados: {output_path}")

        # También guardar JSON para dashboard
        json_path = output_path.with_suffix('.json')

        # Convert to JSON-safe format
        json_safe_results = []
        for r in self.results:
            json_safe = {}
            for k, v in r.items():
                if isinstance(v, (np.integer, np.floating)):
                    json_safe[k] = float(v)
                elif isinstance(v, np.bool_):
                    json_safe[k] = bool(v)
                elif isinstance(v, list):
                    # Handle top_calls and top_puts
                    json_safe[k] = [
                        {kk: float(vv) if isinstance(vv, (np.integer, np.floating))
                         else bool(vv) if isinstance(vv, np.bool_) else vv
                         for kk, vv in item.items()}
                        for item in v
                    ]
                else:
                    json_safe[k] = v
            json_safe_results.append(json_safe)

        results_dict = {
            'scan_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_flows': len(self.results),
            'sentiment_breakdown': {
                'bullish': len([r for r in self.results if r['sentiment'] == 'BULLISH']),
                'bearish': len([r for r in self.results if r['sentiment'] == 'BEARISH']),
                'neutral': len([r for r in self.results if r['sentiment'] == 'NEUTRAL'])
            },
            'total_premium': sum(r['total_premium'] for r in self.results),
            'flows': json_safe_results
        }

        with open(json_path, 'w') as f:
            json.dump(results_dict, f, indent=2)

        print(f"📊 JSON guardado: {json_path}")


def load_5d_opportunities() -> Tuple[List[str], Dict[str, str]]:
    """Carga tickers del universo curado (Tier 1+2+3, ~105 empresas de calidad)."""
    from curated_tickers import get_universe
    tickers = get_universe()

    company_names = {}
    fs_path = Path("docs/fundamental_scores.csv")
    if fs_path.exists():
        try:
            df = pd.read_csv(fs_path)
            if 'company_name' in df.columns:
                company_names = dict(zip(df['ticker'], df['company_name']))
        except Exception:
            pass

    print(f"📊 Cargados {len(tickers)} tickers desde universo curado")
    return tickers, company_names


def main():
    """Main execution"""
    print("=" * 80)
    print("📊 OPTIONS FLOW DETECTOR")
    print("   Detecta flujo institucional y actividad inusual de opciones")
    print("=" * 80)
    print()

    # Cargar tickers
    tickers, company_names = load_5d_opportunities()

    # Limitar a primeros 50 para velocidad (opciones son lentas de escanear)
    if len(tickers) > 50:
        print(f"⚠️  Limitando scan a 50 tickers para velocidad")
        print(f"   (Opciones requieren múltiples API calls por ticker)")
        tickers = tickers[:50]

    # Ejecutar detector
    detector = OptionsFlowDetector()
    flows = detector.scan_tickers(tickers, company_names)

    # Guardar resultados
    detector.save_results()

    # Mostrar top 10
    if flows:
        print()
        print("=" * 80)
        print("🔥 TOP 10 FLUJOS INUSUALES DE OPCIONES")
        print("=" * 80)
        print()

        for i, flow in enumerate(flows[:10], 1):
            print(f"{i}. {flow['ticker']} - {flow['company_name']}")
            print(f"   Sentiment: {flow['sentiment_emoji']} {flow['sentiment']}")
            print(f"   Flow Score: {flow['flow_score']:.0f}/100 ({flow['quality']})")
            print(f"   Premium Total: ${flow['total_premium']/1000:.0f}K")
            print(f"   Put/Call Ratio: {flow['put_call_ratio']:.2f}")
            print(f"   Unusual: {flow['unusual_calls']} calls, {flow['unusual_puts']} puts")

            if flow['top_calls']:
                top_call = flow['top_calls'][0]
                print(f"   🔥 Top Call: ${top_call['strike']:.2f} strike, ${top_call['premium']/1000:.0f}K premium")

            if flow['top_puts']:
                top_put = flow['top_puts'][0]
                print(f"   🔥 Top Put: ${top_put['strike']:.2f} strike, ${top_put['premium']/1000:.0f}K premium")

            print()
    else:
        print("ℹ️  No se detectó flujo inusual en este momento")

    print("=" * 80)
    print("✅ Options Flow Detector completado")
    print("=" * 80)


if __name__ == "__main__":
    main()
