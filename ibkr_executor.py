#!/usr/bin/env python3
"""
IBKR EXECUTOR — Ejecución automática de órdenes de rebote
Se integra con intraday_bounce_scanner.py.

Uso:
  python3 ibkr_executor.py --ticker AAPL --entry 185.50 --stop 182.00 --target 193.00
  python3 ibkr_executor.py --ticker NVDA --entry 118.40 --stop 115.50 --target 123.50 --dry-run

Parámetros de riesgo (ajustables):
  RISK_PCT_PER_TRADE = 1.0  → arriesga máx 1% del portfolio por operación
  MAX_POSITION_USD   = 5000 → límite absoluto por posición
  MAX_OPEN_TRADES    = 3    → máximo de rebotes abiertos simultáneamente
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from ib_insync import IB, Stock, LimitOrder, StopOrder, BracketOrder

# ── Config ────────────────────────────────────────────────────────────────────
IB_HOST            = '127.0.0.1'
IB_PORT            = 7497        # TWS paper=7497, live=7496
IB_CLIENT_ID       = 10          # distinto al del test (clientId=1)
RISK_PCT_PER_TRADE = 1.0         # % del portfolio a arriesgar por trade
MAX_POSITION_USD   = 5000        # límite absoluto por posición en USD
MAX_OPEN_TRADES    = 3           # máximo trades de rebote simultáneos
TRADE_LOG          = Path(__file__).parent / 'docs' / 'ibkr_bounce_trades.json'


def _load_trade_log() -> list:
    if TRADE_LOG.exists():
        try:
            return json.loads(TRADE_LOG.read_text())
        except Exception:
            pass
    return []


def _save_trade_log(log: list):
    TRADE_LOG.parent.mkdir(exist_ok=True)
    TRADE_LOG.write_text(json.dumps(log, indent=2, default=str))


def _count_open_trades(log: list) -> int:
    return sum(1 for t in log if t.get('status') == 'OPEN')


def _get_portfolio_value(ib: IB, account: str) -> float:
    for item in ib.accountSummary(account):
        if item.tag == 'NetLiquidation':
            return float(item.value)
    return 0.0


def _calc_position_size(portfolio_usd: float, entry: float, stop: float) -> int:
    """
    Calcula número de acciones basado en riesgo fijo.
    Riesgo por acción = entry - stop
    Posición = (portfolio × RISK_PCT%) / riesgo_por_acción
    """
    risk_per_share = entry - stop
    if risk_per_share <= 0:
        return 0
    max_risk_usd = portfolio_usd * (RISK_PCT_PER_TRADE / 100)
    shares = int(max_risk_usd / risk_per_share)
    # Aplicar límite absoluto
    max_by_limit = int(MAX_POSITION_USD / entry)
    shares = min(shares, max_by_limit)
    return max(shares, 1)


def execute_bounce(ticker: str, entry: float, stop: float, target: float,
                   dry_run: bool = False) -> dict:
    """
    Coloca una orden bracket en IBKR:
      - Orden límite de entrada al precio `entry`
      - Stop loss automático en `stop`
      - Take profit automático en `target`
    """
    result = {
        'ticker':    ticker,
        'entry':     entry,
        'stop':      stop,
        'target':    target,
        'timestamp': datetime.now(timezone(timedelta(hours=-4))).isoformat(),
        'status':    'ERROR',
        'shares':    0,
        'order_id':  None,
        'dry_run':   dry_run,
    }

    trade_log = _load_trade_log()

    # Verificar límite de trades abiertos
    open_trades = _count_open_trades(trade_log)
    if open_trades >= MAX_OPEN_TRADES:
        print(f"⚠️  Límite de {MAX_OPEN_TRADES} trades abiertos alcanzado — no se ejecuta {ticker}")
        result['status'] = 'SKIPPED_MAX_TRADES'
        return result

    # Verificar que no hay ya un trade abierto en este ticker
    if any(t['ticker'] == ticker and t['status'] == 'OPEN' for t in trade_log):
        print(f"⚠️  Ya hay un trade abierto en {ticker} — saltando")
        result['status'] = 'SKIPPED_DUPLICATE'
        return result

    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=15)
        account = ib.wrapper.accounts[0]

        portfolio_usd = _get_portfolio_value(ib, account)
        shares = _calc_position_size(portfolio_usd, entry, stop)

        upside_pct = (target - entry) / entry * 100
        risk_pct   = (entry - stop)   / entry * 100
        rr         = upside_pct / risk_pct if risk_pct > 0 else 0
        position_usd = shares * entry

        print(f"\n📊 {ticker}")
        print(f"   Portfolio: ${portfolio_usd:,.0f}  |  Riesgo: {RISK_PCT_PER_TRADE}% = ${portfolio_usd * RISK_PCT_PER_TRADE / 100:,.0f}")
        print(f"   Acciones:  {shares} × ${entry:.2f} = ${position_usd:,.0f}")
        print(f"   Entrada:   ${entry:.2f}  →  Target: ${target:.2f} (+{upside_pct:.1f}%)  Stop: ${stop:.2f} (-{risk_pct:.1f}%)")
        print(f"   R:R: {rr:.1f}x")

        if shares <= 0:
            print("   ❌ Position size calculado = 0, no se ejecuta")
            result['status'] = 'SKIPPED_SIZE_ZERO'
            return result

        if dry_run:
            print("   🔸 DRY RUN — no se coloca orden real")
            result.update({'status': 'DRY_RUN', 'shares': shares})
            return result

        # Orden bracket: entrada límite + stop + target automáticos
        contract = Stock(ticker, 'SMART', 'USD')
        ib.qualifyContracts(contract)

        bracket = ib.bracketOrder(
            action          = 'BUY',
            quantity        = shares,
            limitPrice      = round(entry, 2),
            takeProfitPrice = round(target, 2),
            stopLossPrice   = round(stop, 2),
        )
        for o in bracket:
            o.account = account
            o.tif     = 'GTC'  # Good Till Cancelled — evita cancelación por preset DAY

        trades = [ib.placeOrder(contract, o) for o in bracket]
        ib.sleep(2)

        parent_trade = trades[0]
        status = parent_trade.orderStatus.status
        order_id = parent_trade.order.orderId

        print(f"   ✅ Orden colocada — ID: {order_id}  Status: {status}")

        result.update({
            'status':   'OPEN',
            'shares':   shares,
            'order_id': order_id,
            'account':  account,
        })

        trade_log.append(result)
        _save_trade_log(trade_log)

    except Exception as e:
        print(f"   ❌ Error IBKR: {e}")
        result['error'] = str(e)
    finally:
        ib.disconnect()

    return result


def main():
    parser = argparse.ArgumentParser(description='IBKR Bounce Executor')
    parser.add_argument('--ticker',  required=True)
    parser.add_argument('--entry',   required=True, type=float)
    parser.add_argument('--stop',    required=True, type=float)
    parser.add_argument('--target',  required=True, type=float)
    parser.add_argument('--dry-run', action='store_true', help='Simular sin colocar orden real')
    args = parser.parse_args()

    result = execute_bounce(
        ticker  = args.ticker.upper(),
        entry   = args.entry,
        stop    = args.stop,
        target  = args.target,
        dry_run = args.dry_run,
    )

    print(f"\nResultado: {result['status']}")
    sys.exit(0 if result['status'] in ('OPEN', 'DRY_RUN') else 1)


if __name__ == '__main__':
    main()
