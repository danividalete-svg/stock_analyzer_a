#!/usr/bin/env python3
"""
MEAN REVERSION BACKTESTER
Valida las estrategias de Mean Reversion con datos históricos
Simula entradas en oversold bounces y bull flags para calcular rendimiento real
"""
import yfinance as yf
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import json
from mean_reversion_detector import MeanReversionDetector


class MeanReversionBacktester:
    """Backtester para estrategias de Mean Reversion"""

    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.trades = []
        self.detector = MeanReversionDetector()

    def backtest_opportunity(self, ticker: str, opportunity: Dict,
                            holding_period_days: int = 30) -> Dict:
        """
        Backtestea una oportunidad específica

        Args:
            ticker: Símbolo del stock
            opportunity: Dict con datos de la oportunidad
            holding_period_days: Días de retención máxima

        Returns:
            Dict con resultado del trade
        """
        try:
            # Obtener datos históricos (90 días adicionales para el holding period)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=self.detector.lookback_days + holding_period_days + 30)

            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date, end=end_date)

            if len(hist) < 50:
                return None

            # Simular entrada en el precio actual de la oportunidad
            entry_price = opportunity['current_price']
            target_price = opportunity['target']
            stop_loss = opportunity['stop_loss']
            strategy = opportunity['strategy']

            # Encontrar la fecha más cercana al escaneo
            entry_date_idx = len(hist) - 1  # Último día disponible

            # Simular holding period
            exit_date_idx = min(entry_date_idx + holding_period_days, len(hist) - 1)

            # Tracking del trade
            max_profit = 0
            max_loss = 0
            hit_target = False
            hit_stop = False
            exit_reason = "HOLDING_PERIOD"
            exit_price = hist['Close'].iloc[exit_date_idx]

            # Simular movimiento intraperiodo
            for i in range(entry_date_idx, exit_date_idx + 1):
                current_price = hist['Close'].iloc[i]
                current_high = hist['High'].iloc[i]
                current_low = hist['Low'].iloc[i]

                # Calcular profit/loss
                profit_pct = ((current_price - entry_price) / entry_price) * 100
                max_profit = max(max_profit, ((current_high - entry_price) / entry_price) * 100)
                max_loss = min(max_loss, ((current_low - entry_price) / entry_price) * 100)

                # Check target
                if current_high >= target_price:
                    hit_target = True
                    exit_price = target_price
                    exit_reason = "TARGET"
                    break

                # Check stop loss
                if current_low <= stop_loss:
                    hit_stop = True
                    exit_price = stop_loss
                    exit_reason = "STOP_LOSS"
                    break

            # Calcular resultado final
            profit_loss_pct = ((exit_price - entry_price) / entry_price) * 100
            profit_loss_dollar = (exit_price - entry_price) * 100  # Asumiendo 100 shares

            trade_result = {
                'ticker': ticker,
                'company_name': opportunity.get('company_name', ticker),
                'strategy': strategy,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'target_price': target_price,
                'stop_loss': stop_loss,
                'entry_date': hist.index[entry_date_idx].strftime('%Y-%m-%d'),
                'exit_date': hist.index[min(exit_date_idx, len(hist)-1)].strftime('%Y-%m-%d'),
                'holding_days': min(exit_date_idx - entry_date_idx, holding_period_days),
                'profit_loss_pct': round(profit_loss_pct, 2),
                'profit_loss_dollar': round(profit_loss_dollar, 2),
                'max_profit_pct': round(max_profit, 2),
                'max_loss_pct': round(max_loss, 2),
                'hit_target': hit_target,
                'hit_stop': hit_stop,
                'exit_reason': exit_reason,
                'reversion_score': opportunity['reversion_score'],
                'win': profit_loss_pct > 0
            }

            return trade_result

        except Exception as e:
            print(f"   ⚠️  Error backtesting {ticker}: {e}")
            return None

    def backtest_opportunities(self, opportunities: List[Dict],
                              holding_period_days: int = 30) -> List[Dict]:
        """
        Backtestea lista de oportunidades

        Args:
            opportunities: Lista de oportunidades detectadas
            holding_period_days: Días de retención máxima

        Returns:
            Lista de trades ejecutados
        """
        print(f"📊 Backtesting {len(opportunities)} oportunidades...")
        print(f"   Holding period: {holding_period_days} días")
        print()

        trades = []

        for i, opp in enumerate(opportunities, 1):
            if i % 10 == 0:
                print(f"   Progreso: {i}/{len(opportunities)}")

            ticker = opp['ticker']
            result = self.backtest_opportunity(ticker, opp, holding_period_days)

            if result:
                trades.append(result)
                win_icon = "✅" if result['win'] else "❌"
                print(f"   {win_icon} {ticker}: {result['profit_loss_pct']:+.1f}% ({result['exit_reason']})")

        self.trades = trades
        return trades

    def calculate_metrics(self) -> Dict:
        """Calcula métricas de rendimiento del backtest"""
        if not self.trades:
            return {}

        df = pd.DataFrame(self.trades)

        # Overall metrics
        total_trades = len(df)
        winning_trades = len(df[df['win'] == True])
        losing_trades = len(df[df['win'] == False])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # Profit metrics
        avg_win = df[df['win'] == True]['profit_loss_pct'].mean() if winning_trades > 0 else 0
        avg_loss = df[df['win'] == False]['profit_loss_pct'].mean() if losing_trades > 0 else 0
        avg_trade = df['profit_loss_pct'].mean()

        total_profit = df[df['win'] == True]['profit_loss_pct'].sum()
        total_loss = abs(df[df['win'] == False]['profit_loss_pct'].sum())
        profit_factor = (total_profit / total_loss) if total_loss > 0 else float('inf')

        # Best/Worst trades
        best_trade = df.loc[df['profit_loss_pct'].idxmax()].to_dict() if len(df) > 0 else {}
        worst_trade = df.loc[df['profit_loss_pct'].idxmin()].to_dict() if len(df) > 0 else {}

        # Exit reasons
        target_hits = len(df[df['exit_reason'] == 'TARGET'])
        stop_hits = len(df[df['exit_reason'] == 'STOP_LOSS'])
        holding_exits = len(df[df['exit_reason'] == 'HOLDING_PERIOD'])

        # Strategy breakdown
        strategies = {}
        for strategy in df['strategy'].unique():
            strat_df = df[df['strategy'] == strategy]
            strategies[strategy] = {
                'total_trades': len(strat_df),
                'win_rate': (len(strat_df[strat_df['win'] == True]) / len(strat_df) * 100) if len(strat_df) > 0 else 0,
                'avg_profit': strat_df['profit_loss_pct'].mean(),
                'total_profit': strat_df['profit_loss_pct'].sum()
            }

        # Equity curve
        df_sorted = df.sort_values('entry_date')
        df_sorted['cumulative_return'] = (1 + df_sorted['profit_loss_pct'] / 100).cumprod() - 1
        equity_curve = df_sorted[['entry_date', 'cumulative_return']].to_dict('records')

        # Drawdown
        cumulative_returns = (1 + df_sorted['profit_loss_pct'] / 100).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns / running_max - 1) * 100
        max_drawdown = drawdown.min()

        metrics = {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'avg_trade': round(avg_trade, 2),
            'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 999,
            'total_profit_pct': round(total_profit, 2),
            'total_loss_pct': round(total_loss, 2),
            'max_drawdown': round(max_drawdown, 2),
            'target_hits': target_hits,
            'stop_hits': stop_hits,
            'holding_exits': holding_exits,
            'best_trade': best_trade,
            'worst_trade': worst_trade,
            'strategies': strategies,
            'equity_curve': equity_curve,
            'total_return_pct': round((cumulative_returns.iloc[-1] - 1) * 100, 2) if len(cumulative_returns) > 0 else 0
        }

        return metrics

    def save_results(self, output_dir: str = "docs/backtest"):
        """Guarda resultados del backtest"""
        if not self.trades:
            print("⚠️  No hay trades para guardar")
            return

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Save trades CSV
        df_trades = pd.DataFrame(self.trades)
        csv_path = output_path / f"mean_reversion_backtest_trades_{timestamp}.csv"
        df_trades.to_csv(csv_path, index=False)
        print(f"💾 Trades guardados: {csv_path}")

        # Save metrics JSON
        metrics = self.calculate_metrics()
        json_path = output_path / f"mean_reversion_backtest_{timestamp}.json"

        # Convert numpy types to Python native types for JSON serialization
        def convert_to_native(obj):
            if isinstance(obj, dict):
                return {k: convert_to_native(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_native(item) for item in obj]
            elif isinstance(obj, (np.integer, np.floating)):
                return float(obj)
            elif isinstance(obj, np.bool_):
                return bool(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            else:
                return obj

        json_safe_data = {
            'backtest_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'initial_capital': self.initial_capital,
            'metrics': convert_to_native(metrics),
            'trades': convert_to_native(self.trades)
        }

        with open(json_path, 'w') as f:
            json.dump(json_safe_data, f, indent=2)

        print(f"📊 Métricas guardadas: {json_path}")

        # Create latest symlink
        latest_json = output_path / "mean_reversion_backtest_latest.json"
        if latest_json.exists():
            latest_json.unlink()

        # Copy instead of symlink for compatibility
        with open(json_path, 'r') as src:
            with open(latest_json, 'w') as dst:
                dst.write(src.read())

        print(f"🔗 Latest backtest: {latest_json}")

    def print_summary(self):
        """Imprime resumen del backtest"""
        if not self.trades:
            print("ℹ️  No hay trades para mostrar")
            return

        metrics = self.calculate_metrics()

        print()
        print("=" * 80)
        print("📊 MEAN REVERSION BACKTEST - RESUMEN")
        print("=" * 80)
        print()

        print(f"Total Trades: {metrics['total_trades']}")
        print(f"Win Rate: {metrics['win_rate']:.1f}%")
        print(f"  ├─ Wins: {metrics['winning_trades']}")
        print(f"  └─ Losses: {metrics['losing_trades']}")
        print()

        print(f"Performance:")
        print(f"  ├─ Avg Win: +{metrics['avg_win']:.2f}%")
        print(f"  ├─ Avg Loss: {metrics['avg_loss']:.2f}%")
        print(f"  ├─ Avg Trade: {metrics['avg_trade']:+.2f}%")
        print(f"  ├─ Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"  ├─ Total Return: {metrics['total_return_pct']:+.2f}%")
        print(f"  └─ Max Drawdown: {metrics['max_drawdown']:.2f}%")
        print()

        print(f"Exit Reasons:")
        print(f"  ├─ Target Hit: {metrics['target_hits']} ({metrics['target_hits']/metrics['total_trades']*100:.1f}%)")
        print(f"  ├─ Stop Loss: {metrics['stop_hits']} ({metrics['stop_hits']/metrics['total_trades']*100:.1f}%)")
        print(f"  └─ Holding Period: {metrics['holding_exits']} ({metrics['holding_exits']/metrics['total_trades']*100:.1f}%)")
        print()

        print("Strategy Comparison:")
        for strategy, stats in metrics['strategies'].items():
            print(f"  {strategy}:")
            print(f"    ├─ Trades: {stats['total_trades']}")
            print(f"    ├─ Win Rate: {stats['win_rate']:.1f}%")
            print(f"    ├─ Avg Profit: {stats['avg_profit']:+.2f}%")
            print(f"    └─ Total: {stats['total_profit']:+.2f}%")
        print()

        if metrics.get('best_trade'):
            best = metrics['best_trade']
            print(f"🏆 Best Trade: {best['ticker']} ({best['strategy']})")
            print(f"   {best['profit_loss_pct']:+.2f}% - {best['exit_reason']}")

        if metrics.get('worst_trade'):
            worst = metrics['worst_trade']
            print(f"💔 Worst Trade: {worst['ticker']} ({worst['strategy']})")
            print(f"   {worst['profit_loss_pct']:+.2f}% - {worst['exit_reason']}")

        print()
        print("=" * 80)


    def backtest_from_history(self, min_score: float = 80,
                               strategy_filter: str = 'Oversold Bounce',
                               holding_periods: List[int] = None,
                               cooldown_days: int = 14) -> Dict:
        """
        Backtest REAL usando snapshots históricos de docs/history/.
        Entrada al precio del día de detección, salida N días después.
        Aplica cooldown para no contar la misma señal repetida.

        Args:
            min_score: Score mínimo para incluir la señal (default 80)
            strategy_filter: 'Oversold Bounce', 'Bull Flag Pullback', o None (todas)
            holding_periods: Lista de días [7, 14, 30]
            cooldown_days: Días de cooldown por ticker para no repetir entrada

        Returns:
            Dict con trades por holding period y análisis por score tier
        """
        if holding_periods is None:
            holding_periods = [7, 14, 30]

        history_dir = Path("docs/history")
        snapshot_dirs = sorted([d for d in history_dir.iterdir() if d.is_dir()])

        if not snapshot_dirs:
            print("❌ No hay snapshots en docs/history/")
            return {}

        # Recopilar todas las señales históricas
        all_signals = []
        for snap_dir in snapshot_dirs:
            csv = snap_dir / "mean_reversion_opportunities.csv"
            if not csv.exists():
                continue
            try:
                df = pd.read_csv(csv)
                df['snapshot_date'] = snap_dir.name  # YYYY-MM-DD
                all_signals.append(df)
            except Exception as e:
                print(f"   ⚠️  Error leyendo {csv}: {e}")

        if not all_signals:
            print("❌ No se pudieron cargar snapshots históricos")
            return {}

        combined = pd.concat(all_signals, ignore_index=True)
        combined['snapshot_date'] = pd.to_datetime(combined['snapshot_date'])
        combined = combined.sort_values('snapshot_date')

        # Filtro de score y estrategia (cargamos TODOS los scores para el tier analysis)
        if strategy_filter:
            combined = combined[combined['strategy'] == strategy_filter]

        # Cooldown: para cada ticker, solo la primera aparición en cada ventana de cooldown_days
        combined = combined.sort_values(['ticker', 'snapshot_date'])
        filtered_rows = []
        last_seen: Dict[str, pd.Timestamp] = {}
        for _, row in combined.iterrows():
            ticker = row['ticker']
            date = row['snapshot_date']
            if ticker not in last_seen or (date - last_seen[ticker]).days >= cooldown_days:
                filtered_rows.append(row)
                last_seen[ticker] = date
        combined = pd.DataFrame(filtered_rows)

        print(f"📁 {len(snapshot_dirs)} snapshots históricos ({snapshot_dirs[0].name} → {snapshot_dirs[-1].name})")
        print(f"📋 {len(combined)} señales únicas después de cooldown ({cooldown_days}d)")
        print(f"🎯 Estrategia: {strategy_filter or 'TODAS'}")
        print()

        # Descargar régimen de mercado SPY (MA50) para filtro de mercado alcista
        print("📈 Descargando régimen de mercado (SPY MA50)...")
        spy_regime: Dict[str, bool] = {}  # fecha → True si SPY > MA50 (mercado alcista)
        try:
            start_hist = combined['snapshot_date'].min() - timedelta(days=60)
            spy_hist = yf.Ticker('SPY').history(
                start=start_hist.strftime('%Y-%m-%d'),
                end=datetime.now().strftime('%Y-%m-%d')
            )
            if len(spy_hist) >= 50:
                spy_hist['ma50'] = spy_hist['Close'].rolling(50).mean()
                for ts, row_spy in spy_hist.iterrows():
                    date_str = ts.strftime('%Y-%m-%d') if hasattr(ts, 'strftime') else str(ts)[:10]
                    spy_regime[date_str] = bool(row_spy['Close'] > row_spy['ma50'])
                print(f"   ✅ Régimen descargado ({len(spy_regime)} días)")
            else:
                print("   ⚠️  Sin datos SPY — sin filtro de régimen")
        except Exception as e:
            print(f"   ⚠️  Error SPY: {e} — sin filtro de régimen")
        print()

        # Descargar datos de precio para cada ticker (una sola vez)
        print("📥 Descargando datos de precio...")
        tickers_needed = combined['ticker'].unique().tolist()
        price_cache: Dict[str, pd.DataFrame] = {}
        for i, ticker in enumerate(tickers_needed):
            if (i + 1) % 10 == 0:
                print(f"   {i+1}/{len(tickers_needed)}")
            try:
                start = combined[combined['ticker'] == ticker]['snapshot_date'].min() - timedelta(days=1)
                end = datetime.now()
                hist = yf.Ticker(ticker).history(start=start.strftime('%Y-%m-%d'),
                                                  end=end.strftime('%Y-%m-%d'))
                if len(hist) >= 5:
                    price_cache[ticker] = hist
            except Exception:
                pass
        print(f"   ✅ {len(price_cache)} tickers con datos\n")

        # Simular trades
        trades_by_period: Dict[int, List[Dict]] = {p: [] for p in holding_periods}

        for _, signal in combined.iterrows():
            ticker = signal['ticker']
            if ticker not in price_cache:
                continue

            hist = price_cache[ticker]
            entry_date = signal['snapshot_date']
            reversion_score = signal['reversion_score']
            entry_price = signal['current_price']
            csv_target = signal.get('target', None)

            # Encontrar el índice de entrada en el histórico (strip tz para comparación)
            idx_naive = hist.index.tz_convert(None).normalize()
            hist_after = hist[idx_naive >= entry_date.normalize()]
            if len(hist_after) < 2:
                continue  # No hay datos suficientes hacia adelante

            # Entrada al precio de cierre del día de detección
            actual_entry_price = hist_after['Close'].iloc[0]

            # Stop/target RELATIVOS al precio real de entrada para evitar
            # el problema de stop > entry cuando la señal usa entry_zone > current_price
            stop = actual_entry_price * 0.92   # stop fijo 8% bajo entrada
            if csv_target and float(csv_target) > actual_entry_price * 1.05:
                target = float(csv_target)     # usar target del CSV si está >5% sobre entrada
            else:
                target = actual_entry_price * 1.25  # target por defecto +25%

            for period in holding_periods:
                if len(hist_after) < 2:
                    continue

                # Ventana de simulación
                window = hist_after.iloc[:period + 1]
                if len(window) < 2:
                    continue

                # Comprobar si alcanzó target o stop dentro del periodo
                hit_target = False
                hit_stop = False
                exit_price = window['Close'].iloc[-1]
                exit_reason = "HOLDING_PERIOD"
                holding_days = len(window) - 1

                for j in range(1, len(window)):
                    high = window['High'].iloc[j]
                    low = window['Low'].iloc[j]
                    if low <= stop:
                        hit_stop = True
                        exit_price = stop
                        exit_reason = "STOP_LOSS"
                        holding_days = j
                        break
                    if high >= target:
                        hit_target = True
                        exit_price = target
                        exit_reason = "TARGET"
                        holding_days = j
                        break

                pnl_pct = ((exit_price - actual_entry_price) / actual_entry_price) * 100

                # Score tier
                score = float(reversion_score)
                if score >= 90:
                    tier = '90-100'
                elif score >= 80:
                    tier = '80-89'
                elif score >= 70:
                    tier = '70-79'
                else:
                    tier = '60-69'

                date_str = entry_date.strftime('%Y-%m-%d')
                spy_bullish = spy_regime.get(date_str, None)  # None = sin datos

                trades_by_period[period].append({
                    'ticker': ticker,
                    'company_name': signal.get('company_name', ticker),
                    'strategy': signal.get('strategy', ''),
                    'reversion_score': score,
                    'score_tier': tier,
                    'snapshot_date': date_str,
                    'entry_price': round(actual_entry_price, 4),
                    'exit_price': round(exit_price, 4),
                    'target': round(target, 4),
                    'stop_loss': round(stop, 4),
                    'rsi': signal.get('rsi', None),
                    'drawdown_pct': signal.get('drawdown_pct', None),
                    'holding_days': holding_days,
                    'profit_loss_pct': round(pnl_pct, 2),
                    'hit_target': hit_target,
                    'hit_stop': hit_stop,
                    'exit_reason': exit_reason,
                    'win': pnl_pct > 0,
                    'sufficient_data': len(hist_after) >= period,
                    'spy_bullish': spy_bullish,
                })

        return trades_by_period

    def print_history_summary(self, trades_by_period: Dict, min_score: float = 80,
                               strategy_filter: str = None):
        """Imprime resumen del backtest histórico por holding period y score tier"""
        print("=" * 80)
        print(f"📊 MEAN REVERSION HISTORICAL BACKTEST  (score ≥ {min_score})")
        if strategy_filter:
            print(f"   Estrategia: {strategy_filter}")
        print("=" * 80)

        for period, trades in sorted(trades_by_period.items()):
            if not trades:
                print(f"\n⏱️  {period}d: sin trades")
                continue

            df = pd.DataFrame(trades)
            # Solo trades con datos suficientes
            df_full = df[df['sufficient_data'] == True]
            df_use = df_full if len(df_full) >= 3 else df

            total = len(df_use)
            wins = (df_use['win'] == True).sum()
            win_rate = wins / total * 100 if total > 0 else 0
            avg_return = df_use['profit_loss_pct'].mean()
            median_return = df_use['profit_loss_pct'].median()
            target_hits = (df_use['exit_reason'] == 'TARGET').sum()
            stop_hits = (df_use['exit_reason'] == 'STOP_LOSS').sum()

            print(f"\n{'─'*40}")
            print(f"⏱️  HOLDING PERIOD: {period} días  ({total} trades)")
            print(f"{'─'*40}")
            print(f"  Win Rate:     {win_rate:.1f}%  ({wins}W / {total-wins}L)")
            print(f"  Avg Return:   {avg_return:+.2f}%")
            print(f"  Median:       {median_return:+.2f}%")
            print(f"  Target hits:  {target_hits} ({target_hits/total*100:.0f}%)")
            print(f"  Stop hits:    {stop_hits} ({stop_hits/total*100:.0f}%)")

            # Breakdown por score tier
            print(f"\n  📊 Por score tier:")
            for tier in ['90-100', '80-89', '70-79', '60-69']:
                tier_df = df_use[df_use['score_tier'] == tier]
                if len(tier_df) == 0:
                    continue
                t_wins = (tier_df['win'] == True).sum()
                t_wr = t_wins / len(tier_df) * 100
                t_avg = tier_df['profit_loss_pct'].mean()
                print(f"    [{tier}] n={len(tier_df):2d}  WR={t_wr:.0f}%  avg={t_avg:+.1f}%")

            # Breakdown por régimen de mercado SPY MA50
            if 'spy_bullish' in df_use.columns and df_use['spy_bullish'].notna().any():
                print(f"\n  📈 Por régimen de mercado (SPY vs MA50):")
                bull = df_use[df_use['spy_bullish'] == True]
                bear = df_use[df_use['spy_bullish'] == False]
                if len(bull) >= 2:
                    b_wr = (bull['win'] == True).sum() / len(bull) * 100
                    b_avg = bull['profit_loss_pct'].mean()
                    print(f"    ALCISTA (SPY>MA50) n={len(bull):2d}  WR={b_wr:.0f}%  avg={b_avg:+.1f}%")
                if len(bear) >= 2:
                    br_wr = (bear['win'] == True).sum() / len(bear) * 100
                    br_avg = bear['profit_loss_pct'].mean()
                    print(f"    BAJISTA (SPY<MA50) n={len(bear):2d}  WR={br_wr:.0f}%  avg={br_avg:+.1f}%")

            # Top 3 y peores
            print(f"\n  🏆 Mejores:")
            for _, row in df_use.nlargest(3, 'profit_loss_pct').iterrows():
                regime = '📈' if row.get('spy_bullish') else '📉'
                print(f"    {row['ticker']:6s} [{row['score_tier']}] {regime}  {row['profit_loss_pct']:+.1f}%  ({row['exit_reason']})  {row['snapshot_date']}")
            print(f"\n  💔 Peores:")
            for _, row in df_use.nsmallest(3, 'profit_loss_pct').iterrows():
                regime = '📈' if row.get('spy_bullish') else '📉'
                print(f"    {row['ticker']:6s} [{row['score_tier']}] {regime}  {row['profit_loss_pct']:+.1f}%  ({row['exit_reason']})  {row['snapshot_date']}")

        print("\n" + "=" * 80)

    def save_history_results(self, trades_by_period: Dict,
                              output_dir: str = "docs/backtest"):
        """Guarda resultados del backtest histórico"""
        if not any(trades_by_period.values()):
            print("⚠️  No hay trades para guardar")
            return

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # CSV con todos los trades (periodo 30d)
        trades_30 = trades_by_period.get(30, [])
        if trades_30:
            df_all = pd.DataFrame(trades_30)
            csv_path = output_path / f"mr_history_backtest_{timestamp}.csv"
            df_all.to_csv(csv_path, index=False)
            print(f"💾 Trades CSV: {csv_path}")

        # JSON con métricas por periodo y tier
        def to_native(obj):
            if isinstance(obj, dict):
                return {k: to_native(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [to_native(i) for i in obj]
            elif isinstance(obj, (np.integer, np.floating)):
                return float(obj)
            elif isinstance(obj, np.bool_):
                return bool(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj

        summary = {'backtest_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'periods': {}}
        for period, trades in trades_by_period.items():
            if not trades:
                continue
            df = pd.DataFrame(trades)
            df_use = df[df['sufficient_data'] == True] if (df['sufficient_data'] == True).sum() >= 3 else df
            total = len(df_use)
            wins = int((df_use['win'] == True).sum())
            tiers = {}
            for tier in df_use['score_tier'].unique():
                td = df_use[df_use['score_tier'] == tier]
                tiers[tier] = {
                    'n': len(td),
                    'win_rate': round(float((td['win'] == True).sum()) / len(td) * 100, 1),
                    'avg_return': round(float(td['profit_loss_pct'].mean()), 2),
                    'median_return': round(float(td['profit_loss_pct'].median()), 2),
                }
            summary['periods'][str(period)] = {
                'total_trades': total,
                'win_rate': round(wins / total * 100, 1) if total > 0 else 0,
                'avg_return': round(float(df_use['profit_loss_pct'].mean()), 2),
                'median_return': round(float(df_use['profit_loss_pct'].median()), 2),
                'tiers': tiers,
                'trades': to_native(df_use.to_dict('records')),
            }

        json_path = output_path / f"mr_history_backtest_{timestamp}.json"
        with open(json_path, 'w') as f:
            json.dump(summary, f, indent=2)

        # Actualizar latest
        latest = output_path / "mr_history_backtest_latest.json"
        with open(json_path) as src, open(latest, 'w') as dst:
            dst.write(src.read())

        print(f"📊 Métricas JSON: {json_path}")
        print(f"🔗 Latest: {latest}")


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description='Mean Reversion Backtester')
    parser.add_argument('--min-score', type=float, default=80,
                        help='Score mínimo para incluir señal (default: 80)')
    parser.add_argument('--strategy', default='Oversold Bounce',
                        help='Estrategia: "Oversold Bounce", "Bull Flag Pullback", o "ALL" (default: Oversold Bounce)')
    parser.add_argument('--mode', default='history',
                        choices=['history', 'current'],
                        help='history: backtest con snapshots reales | current: simulación con señales de hoy')
    parser.add_argument('--cooldown', type=int, default=14,
                        help='Días de cooldown por ticker para evitar señales repetidas (default: 14)')
    args = parser.parse_args()

    print("=" * 80)
    print("📊 MEAN REVERSION BACKTESTER")
    print(f"   Modo: {args.mode.upper()} | Score ≥ {args.min_score} | Estrategia: {args.strategy}")
    print("=" * 80)
    print()

    strategy_filter = None if args.strategy == 'ALL' else args.strategy
    backtester = MeanReversionBacktester(initial_capital=100000)

    if args.mode == 'history':
        # ─── Backtest histórico real ───────────────────────────────────────────
        trades_by_period = backtester.backtest_from_history(
            min_score=args.min_score,
            strategy_filter=strategy_filter,
            holding_periods=[7, 14, 30],
            cooldown_days=args.cooldown,
        )
        if any(trades_by_period.values()):
            backtester.print_history_summary(trades_by_period, args.min_score, strategy_filter)
            backtester.save_history_results(trades_by_period)
        else:
            print("❌ No se generaron trades con los filtros dados")

    else:
        # ─── Simulación con señales actuales ─────────────────────────────────
        csv_path = Path("docs/mean_reversion_opportunities.csv")
        if not csv_path.exists():
            print("❌ No hay oportunidades. Ejecuta primero: python3 mean_reversion_detector.py")
            return

        df = pd.read_csv(csv_path)
        df_filtered = df[df['reversion_score'] >= args.min_score]
        if strategy_filter:
            df_filtered = df_filtered[df_filtered['strategy'] == strategy_filter]
        print(f"📁 {len(df_filtered)} oportunidades (score ≥ {args.min_score}, estrategia: {strategy_filter or 'TODAS'})")
        print()

        trades = backtester.backtest_opportunities(df_filtered.to_dict('records'), holding_period_days=30)
        if trades:
            backtester.print_summary()
            backtester.save_results()
        else:
            print("❌ No se pudieron ejecutar trades")

    print()
    print("=" * 80)
    print("✅ Backtest completado")
    print("=" * 80)


if __name__ == "__main__":
    main()
