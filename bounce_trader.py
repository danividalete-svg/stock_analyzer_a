#!/usr/bin/env python3
"""
BOUNCE TRADER — Scanner + Executor + Monitor integrado
Requiere TWS abierto en puerto 7497 (paper) o 7496 (live).

Uso:
  python3 bounce_trader.py --loop       # bucle cada 15 min, toda la sesión
  python3 bounce_trader.py --dry-run    # simula sin órdenes reales
  python3 bounce_trader.py --status     # muestra trades abiertos y cerrados de hoy
  python3 bounce_trader.py --live       # puerto real 7496 (confirmación requerida)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import requests

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).parent
DOCS     = ROOT / 'docs'
LOG_PATH = DOCS / 'bounce_trader_log.json'

TICKER_SOURCES = [
    DOCS / 'value_conviction.csv',
    DOCS / 'european_value_conviction.csv',
    DOCS / 'value_opportunities_filtered.csv',
    DOCS / 'mean_reversion_opportunities.csv',       # era mean_reversion.csv (no existía)
    DOCS / 'european_value_opportunities_filtered.csv',
]
CEREBRO_SIGNALS_PATH = DOCS / 'cerebro_entry_signals.json'

# ── Telegram ──────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID   = os.environ.get('TELEGRAM_CHAT_ID', '')

# ── IBKR ──────────────────────────────────────────────────────────────────────
IB_HOST        = '127.0.0.1'
IB_PORT_PAPER  = 7497
IB_PORT_LIVE   = 7496
IB_CLIENT_ID   = 10

# ── Criterios de entrada ──────────────────────────────────────────────────────
MIN_DROP_PCT       = -4.0
MAX_RSI            = 32
MAX_SUPPORT_DIST   = 4.0
MIN_VOL_RATIO      = 1.5
MIN_RR             = 2.0
MIN_DROP_FROM_PEAK = 8.0

# ── Gestión de riesgo ─────────────────────────────────────────────────────────
# PAPER ($1M): MAX_POSITION_USD=25000, MAX_OPEN_TRADES=8
# REAL (poco cash+margin): bajar MAX_POSITION_USD a tu cash disponible por trade
RISK_PCT_PER_TRADE = 1.0
MAX_POSITION_USD   = 25000   # paper $1M → ~2.5% por posición; ajustar en real
MAX_OPEN_TRADES      = 8     # live: máximo posiciones simultáneas (NORMAL); en STRESS se reduce a 5
MAX_OPEN_TRADES_PAPER = 20   # paper: límite amplio para testear el sistema
DAILY_LOSS_LIMIT_USD = 1500  # live: stop automático si pérdidas superan este importe (paper: sin límite)
COOLDOWN_HOURS     = 6
STOP_BUFFER_PCT    = 1.5
ENTRY_BUFFER_PCT   = 0.10
SCAN_INTERVAL_MIN  = 15
STALE_TRADE_DAYS   = 7    # días sin cerrar → forzar cierre
MAX_SAME_SECTOR    = 2    # papel: hasta 2 trades por sector (en real dejar en 1)
CONFIRM_TIMEOUT_MIN = None  # None = sin timeout, espera indefinidamente hasta respuesta

# ── Multiplicadores de posición por conviction grade ──────────────────────────
GRADE_RISK_MULT = {
    'EXCELLENT': 1.5,
    'STRONG':    1.0,
    'AVERAGE':   0.7,
    'WEAK':      0.0,   # no operar
}

# ── Mercados europeos — sufijo yfinance → (divisa, exchange IBKR) ──────────────
EU_MARKETS = {
    '.L':  ('GBP', 'LSE'),      # Londres
    '.DE': ('EUR', 'XETRA'),    # Frankfurt
    '.PA': ('EUR', 'SBF'),      # París
    '.SW': ('CHF', 'EBS'),      # Suiza
    '.MC': ('EUR', 'BM'),       # Madrid
    '.AS': ('EUR', 'AEB'),      # Amsterdam
    '.MI': ('EUR', 'BVME'),     # Milán
}


# ─────────────────────────────────────────────────────────────────────────────
# Tiempo y mercado
# ─────────────────────────────────────────────────────────────────────────────

def _now_et() -> datetime:
    return datetime.now(timezone(timedelta(hours=-4)))


def _is_us_open() -> bool:
    et = _now_et()
    t  = et.hour + et.minute / 60
    return et.weekday() < 5 and 9.5 <= t < 16.0


def _is_us_extended() -> bool:
    """Pre-market 4-9:30 ET + after-hours 16-20 ET."""
    et = _now_et()
    t  = et.hour + et.minute / 60
    return et.weekday() < 5 and (4.0 <= t < 9.5 or 16.0 <= t <= 20.0)


def _is_eu_open() -> bool:
    et = _now_et()
    t  = et.hour + et.minute / 60
    return et.weekday() < 5 and 3.0 <= t <= 12.0


def _is_any_market_open(extended: bool = False) -> bool:
    return _is_us_open() or _is_eu_open() or (extended and _is_us_extended())


def _is_end_of_day() -> bool:
    """15:55–16:05 ET — ventana para resumen de cierre US."""
    et = _now_et()
    t  = et.hour + et.minute / 60
    return et.weekday() < 5 and 15.917 <= t <= 16.083


def _is_eu_ticker(ticker: str) -> bool:
    return any(ticker.endswith(sfx) for sfx in EU_MARKETS)


def _ticker_meta(ticker: str) -> tuple:
    """Devuelve (symbol_ibkr, currency, exchange) para un ticker."""
    for sfx, (ccy, exch) in EU_MARKETS.items():
        if ticker.endswith(sfx):
            return ticker[:-len(sfx)], ccy, exch
    return ticker, 'USD', 'SMART'


def _minutes_to_next_open() -> int:
    """Minutos hasta la próxima apertura (EU o US)."""
    et    = _now_et()
    t     = et.hour + et.minute / 60
    wd    = et.weekday()
    if wd >= 5:
        return (7 - wd) * 24 * 60  # lunes
    if t < 3.0:
        return int((3.0 - t) * 60)
    if 12.0 <= t < 9.5 + 24:  # entre cierre EU y apertura US
        return int((9.5 - t) * 60) if t < 9.5 else 0
    return 0


def _minutes_to_open() -> int:
    """Minutos hasta las 9:30 ET. Negativo si ya está abierto."""
    et    = _now_et()
    open_ = et.replace(hour=9, minute=30, second=0, microsecond=0)
    return int((open_ - et).total_seconds() / 60)


# ─────────────────────────────────────────────────────────────────────────────
# Log
# ─────────────────────────────────────────────────────────────────────────────

def _load_log() -> list:
    if LOG_PATH.exists():
        try:
            return json.loads(LOG_PATH.read_text())
        except Exception:
            pass
    return []


def _save_log(log: list):
    LOG_PATH.parent.mkdir(exist_ok=True)
    LOG_PATH.write_text(json.dumps(log, indent=2, default=str))


def _today_str() -> str:
    return _now_et().strftime('%Y-%m-%d')


def _open_trades(log: list) -> list:
    return [e for e in log if e.get('status') == 'EXECUTED' and not e.get('closed')]


def _daily_pnl(log: list) -> float:
    """Pérdidas/ganancias realizadas hoy (USD). Solo trades cerrados hoy."""
    today = _today_str()
    total = 0.0
    for e in log:
        if not e.get('closed'):
            continue
        close_ts = e.get('close_timestamp', '')
        if not close_ts.startswith(today):
            continue
        pnl = e.get('pnl_usd') or e.get('pnl_pct', 0) * e.get('position_usd', 0) / 100
        try:
            total += float(pnl)
        except (TypeError, ValueError):
            pass
    return total


def _recently_traded(log: list, ticker: str) -> tuple:
    """Devuelve (bool, str) — True + razón si en cooldown."""
    for entry in reversed(log):
        if entry.get('ticker') != ticker:
            continue
        if entry.get('status') not in ('EXECUTED', 'DRY_RUN', 'EU_PENDING'):
            continue
        try:
            ts   = datetime.fromisoformat(entry['timestamp'])
            diff = (datetime.now(timezone.utc) - ts.replace(tzinfo=timezone.utc)).total_seconds()
            # Cooldown 24h si la última operación fue un LOSS, 6h si fue WIN/abierta
            was_loss = entry.get('closed') and entry.get('pnl_pct', 0) < 0
            hours    = 24 if was_loss else COOLDOWN_HOURS
            if diff < hours * 3600:
                label = f'cooldown {hours}h (LOSS)' if was_loss else f'cooldown {hours}h'
                return True, label
        except Exception:
            pass
    return False, ''


# ─────────────────────────────────────────────────────────────────────────────
# Análisis técnico
# ─────────────────────────────────────────────────────────────────────────────

def _rsi(closes: pd.Series, period: int = 14) -> float:
    delta    = closes.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    rsi_s    = 100 - (100 / (1 + rs))
    return float(rsi_s.iloc[-1]) if len(rsi_s) else 50.0


def _analyze(ticker: str, fund: Optional[dict] = None) -> Optional[dict]:
    try:
        import yfinance as yf
        tk    = yf.Ticker(ticker)
        hist  = tk.history(period='60d', interval='1d', auto_adjust=True)
        histw = tk.history(period='1y',  interval='1wk', auto_adjust=True)
        if len(hist) < 22:
            return None

        closes  = hist['Close']
        volumes = hist['Volume']

        info    = tk.fast_info
        current = float(info.last_price or closes.iloc[-1])

        prev_close  = float(closes.iloc[-2])
        high_20d    = float(closes.iloc[-21:-1].max())
        low_20d     = float(closes.iloc[-21:-1].min())
        high_10d    = float(closes.iloc[-11:-1].max())
        avg_vol_20d = float(volumes.iloc[-21:-1].mean())
        today_vol   = float(volumes.iloc[-1])
        rsi_d       = _rsi(closes)
        rsi_w       = _rsi(histw['Close']) if len(histw) >= 15 else None
        vol_ratio   = today_vol / avg_vol_20d if avg_vol_20d > 0 else 1.0

        drop_vs_prev = (current - prev_close) / prev_close * 100
        drop_vs_peak = (current - high_20d)   / high_20d   * 100
        dist_support = (current - low_20d)    / low_20d    * 100

        entry  = round(current * (1 + ENTRY_BUFFER_PCT / 100), 2)
        # Si el precio ya está por debajo del mínimo de 20d (soporte roto),
        # el stop va bajo el precio actual en lugar de bajo un soporte ya inútil
        if current >= low_20d:
            stop = round(low_20d * (1 - STOP_BUFFER_PCT / 100), 2)
        else:
            stop = round(current * (1 - (STOP_BUFFER_PCT + 3) / 100), 2)  # stop más amplio (-4.5%)

        # Target: usar precio analistas si está disponible, pero capeado al +25%
        # (el target analista es a 12 meses — para bounce solo usamos como referencia)
        analyst_target = (fund or {}).get('target_analyst')
        tech_target    = round(high_10d * 0.995, 2) if high_10d >= entry * 1.02 else round(entry * 1.04, 2)
        max_bounce_target = round(entry * 1.25, 2)  # cap +25% para bounce realista
        if analyst_target and analyst_target > entry * 1.015:
            target = round(min(analyst_target, max_bounce_target), 2)
            target_source = 'analyst'
        else:
            target = tech_target
            target_source = 'technical'

        upside = (target - entry) / entry * 100
        risk   = (entry  - stop)  / entry * 100
        rr     = upside / risk if risk > 0 else 0.0

        # Detectar estrategia
        strategy = _detect_strategy(drop_vs_prev, drop_vs_peak, rsi_d, rsi_w, vol_ratio, dist_support, rr)

        return {
            'ticker':         ticker,
            'current':        current,
            'entry':          entry,
            'stop':           stop,
            'target':         target,
            'target_source':  target_source,
            'rsi':            rsi_d,
            'rsi_weekly':     rsi_w,
            'drop_vs_prev':   drop_vs_prev,
            'drop_vs_peak':   drop_vs_peak,
            'dist_support':   dist_support,
            'vol_ratio':      vol_ratio,
            'upside_pct':     upside,
            'risk_pct':       risk,
            'rr':             rr,
            'support':        low_20d,
            'strategy':       strategy,  # 'FLASH' | 'ACUMULACION' | None
        }
    except Exception as e:
        print(f'  [{ticker}] error: {e}')
        return None


def _detect_strategy(drop_d, drop_peak, rsi_d, rsi_w, vol, dist_sup, rr) -> Optional[str]:
    """
    FLASH: caída fuerte en un día → rebote rápido 1-3d
    ACUMULACION: oversold en diario Y semanal → recuperación 3-10d
    """
    # FLASH — panic/news driven
    if (drop_d <= MIN_DROP_PCT
            and rsi_d < MAX_RSI
            and dist_sup <= MAX_SUPPORT_DIST
            and vol >= MIN_VOL_RATIO
            and rr >= MIN_RR
            and drop_peak <= -MIN_DROP_FROM_PEAK):
        return 'FLASH'

    # ACUMULACION — RSI diario + semanal ambos oversold, caída acumulada significativa
    if (rsi_d < 30
            and rsi_w is not None and rsi_w < 35
            and drop_peak <= -8.0        # caído ≥8% desde máximo 20d
            and dist_sup <= 5.0          # cerca del soporte
            and rr >= 1.8                # R:R decente
            and drop_d > -15.0):         # no es un desplome de un día (eso lo coge FLASH)
        return 'ACUMULACION'

    return None


def _qualifies(m: dict):
    if m.get('strategy'):
        return True, ''
    # Calcular la razón de rechazo más relevante
    if m['rsi'] >= 35 and (m.get('rsi_weekly') or 100) >= 40:
        return False, f"RSI d={m['rsi']:.0f} w={m.get('rsi_weekly', 0):.0f} (no oversold)"
    if m['drop_vs_peak'] > -8.0:
        return False, f"caída desde máx solo {m['drop_vs_peak']:+.1f}%"
    if m['dist_support'] > 5.0:
        return False, f"lejos soporte {m['dist_support']:.1f}%"
    if m['rr'] < MIN_RR:
        return False, f"R:R {m['rr']:.1f}x"
    return False, f"no cumple criterios (caída={m['drop_vs_prev']:+.1f}% RSI={m['rsi']:.0f})"


# ─────────────────────────────────────────────────────────────────────────────
# IBKR — Ejecución
# ─────────────────────────────────────────────────────────────────────────────

def _execute_order(m: dict, port: int, dry_run: bool, grade: Optional[str] = None) -> dict:
    from ib_insync import IB, Stock

    result = {**m, 'timestamp': _now_et().isoformat(), 'status': 'ERROR', 'date': _today_str()}

    ib = IB()
    try:
        ib.connect(IB_HOST, port, clientId=IB_CLIENT_ID, timeout=15)
        account = ib.wrapper.accounts[0]

        # ── Seguridad: no comprar si ya tienes posición en IBKR ──────────────
        symbol_ibkr, _, _ = _ticker_meta(m['ticker'])
        held_symbols = {p.contract.symbol for p in ib.portfolio()}
        if symbol_ibkr in held_symbols:
            print(f"    ⛔ Ya tienes {m['ticker']} en cartera IBKR — no se duplica")
            result['status'] = 'SKIPPED_ALREADY_HELD'
            return result

        portfolio_usd = 0.0
        for item in ib.accountSummary(account):
            if item.tag == 'NetLiquidation':
                portfolio_usd = float(item.value)
                break

        risk_per_share = m['entry'] - m['stop']
        if risk_per_share <= 0:
            result['status'] = 'ERROR_RISK'
            return result

        # Conviction-based position sizing
        grade_key  = (grade or 'AVERAGE').upper()
        risk_mult  = GRADE_RISK_MULT.get(grade_key, 0.7)
        if risk_mult == 0.0:
            print(f"    ⛔ Grade WEAK — no se opera")
            result['status'] = 'SKIPPED_WEAK_GRADE'
            return result
        # VIX > 25: reducir tamaño al 70%
        vix_mult   = 0.7 if m.get('vix', 20) > 25 else 1.0
        eff_risk   = RISK_PCT_PER_TRADE * risk_mult * vix_mult

        max_risk_usd = portfolio_usd * (eff_risk / 100)
        shares = int(min(max_risk_usd / risk_per_share, MAX_POSITION_USD / m['entry']))
        shares = max(shares, 1)

        result.update({
            'shares':        shares,
            'portfolio_usd': round(portfolio_usd, 0),
            'position_usd':  round(shares * m['entry'], 2),
            'risk_usd':      round(shares * risk_per_share, 2),
            'grade':         grade_key,
            'eff_risk_pct':  round(eff_risk, 2),
        })

        grade_label = f" [{grade_key}×{risk_mult}]" if grade else ""
        print(f"    💼 Portfolio ${portfolio_usd:,.0f}  |  Riesgo ${shares * risk_per_share:,.0f} ({eff_risk:.1f}%{grade_label})")
        print(f"    📦 {shares} acciones × ${m['entry']:.2f} = ${shares * m['entry']:,.0f}")

        if dry_run:
            result['status'] = 'DRY_RUN'
            return result

        symbol, currency, exchange = _ticker_meta(m['ticker'])
        if exchange == 'SMART':
            contract = Stock(symbol, 'SMART', currency)
        else:
            # EU stocks: use SMART routing + primaryExch to avoid Error 200
            contract = Stock(symbol, 'SMART', currency)
            contract.primaryExch = exchange
        ib.qualifyContracts(contract)

        is_eu = _is_eu_ticker(m['ticker'])

        bracket = ib.bracketOrder(
            action='BUY', quantity=shares,
            limitPrice=m['entry'], takeProfitPrice=m['target'], stopLossPrice=m['stop'],
        )
        for o in bracket:
            o.account     = account
            o.tif         = 'GTC'
            o.outsideRth  = m.get('outside_rth', False)
            o.overridePercentageConstraints = True  # bypass validación precio (EU sin market data)

        trades = [ib.placeOrder(contract, o) for o in bracket]
        # EU puede tardar más en recibir ACK — esperar hasta 10s
        wait_iters = 10 if is_eu else 2
        for _ in range(wait_iters):
            ib.sleep(1)
            if trades[0].orderStatus.status != 'PendingSubmit':
                break

        parent_trade = trades[0]
        status   = parent_trade.orderStatus.status
        order_id = parent_trade.order.orderId

        # Imprimir errores IBKR si los hay
        for log_entry in parent_trade.log:
            if log_entry.errorCode:
                print(f"    ⚠️ IBKR error {log_entry.errorCode}: {log_entry.message}")

        if status in ('PreSubmitted', 'Submitted'):
            result.update({'status': 'EXECUTED', 'order_id': order_id, 'ibkr_status': status})
            print(f"    ✅ Bracket colocado — ID {order_id} ({status})")
        elif is_eu and status == 'PendingSubmit':
            # Paper trading sin datos EU — en live funcionará con market data
            result.update({'status': 'EU_PENDING', 'order_id': order_id, 'ibkr_status': status})
            print(f"    ⚠️ EU sin datos de mercado en paper — en live funcionará automáticamente")
            print(f"    📋 Niveles: entrada ${m['entry']:.2f}  stop ${m['stop']:.2f}  target ${m['target']:.2f}")
        else:
            result.update({'status': 'ERROR_ORDER', 'ibkr_status': status})
            print(f"    ❌ Orden rechazada — {status}")

    except Exception as e:
        print(f"    ❌ Error IBKR: {e}")
        result['error'] = str(e)
    finally:
        ib.disconnect()

    return result


# ─────────────────────────────────────────────────────────────────────────────
# IBKR — Monitor de posiciones abiertas
# ─────────────────────────────────────────────────────────────────────────────

def _check_positions(port: int, log: list) -> tuple:
    """
    Comprueba en IBKR el estado de cada bracket abierto:
    1. Detecta fill de ENTRADA (compra ejecutada) → Telegram inmediato
    2. Detecta fill de SALIDA (stop o target tocado) → Telegram con P&L
    3. Auto-cierra trades stale (≥ STALE_TRADE_DAYS días)
    Devuelve (log_actualizado, lista_de_cierres).
    """
    open_entries = _open_trades(log)
    if not open_entries:
        return log, []

    from ib_insync import IB
    closures  = []
    fills_msg = []  # notificaciones de fill de entrada pendientes de enviar

    ib = IB()
    try:
        ib.connect(IB_HOST, port, clientId=IB_CLIENT_ID + 1, timeout=10)

        # Todas las órdenes abiertas de cualquier clientId
        ib.reqAllOpenOrders()
        ib.sleep(1)
        open_order_ids = {t.order.orderId for t in ib.trades()}

        # Fills disponibles indexados por orderId
        all_fills: dict = {}
        for fill in ib.fills():
            oid = fill.execution.orderId
            all_fills.setdefault(oid, []).append(fill)

        for entry in log:
            if entry.get('status') != 'EXECUTED' or entry.get('closed'):
                continue

            order_id = entry.get('order_id')
            if order_id is None:
                continue

            # ── Auto-close stale ──────────────────────────────────────────
            try:
                ts_entry  = datetime.fromisoformat(entry['timestamp'])
                days_open = (datetime.now(timezone.utc) - ts_entry.replace(tzinfo=timezone.utc)).days
                if days_open >= STALE_TRADE_DAYS:
                    import yfinance as yf
                    cur_price = float(yf.Ticker(entry['ticker']).fast_info.last_price)
                    shares_   = entry.get('shares', 0)
                    pnl_per   = cur_price - entry.get('entry', cur_price)
                    entry.update({
                        'closed':      True,
                        'exit_price':  cur_price,
                        'exit_action': 'STALE_TIMEOUT',
                        'pnl_usd':     round(pnl_per * shares_, 2),
                        'pnl_pct':     round(pnl_per / entry.get('entry', cur_price) * 100, 2),
                        'result':      'WIN' if pnl_per > 0 else 'LOSS',
                        'closed_at':   _now_et().isoformat(),
                    })
                    closures.append(entry)
                    print(f"  ⏰ {entry['ticker']} — stale ({days_open}d) cerrado a ${cur_price:.2f}")
                    continue
            except Exception:
                pass

            # ── Detectar fill de ENTRADA ──────────────────────────────────
            # Cuando la LMT de compra se ejecuta, el parent_id desaparece de
            # openOrders pero las hijas (parent+1, parent+2) siguen abiertas.
            child_ids = {order_id + 1, order_id + 2}
            parent_open    = order_id in open_order_ids
            children_open  = bool(child_ids & open_order_ids)

            if not parent_open and children_open and not entry.get('entry_filled'):
                # Buscar precio real de fill en executions
                fill_price = entry.get('entry')  # fallback al precio límite
                if order_id in all_fills:
                    buy_fills = [f for f in all_fills[order_id] if f.execution.side == 'BOT']
                    if buy_fills:
                        fill_price = buy_fills[-1].execution.price

                entry['entry_filled']    = True
                entry['entry_fill_price'] = fill_price
                entry['entry_filled_at']  = _now_et().isoformat()
                fills_msg.append(entry)

                et_str  = _now_et().strftime('%H:%M ET')
                shares_ = entry.get('shares', 0)
                print(f"  🟡 {entry['ticker']} COMPRADO — {shares_} acc a ${fill_price:.2f}  ({et_str})")
                continue  # el trade sigue abierto, no es cierre

            # ── Detectar CIERRE (stop o target) ──────────────────────────
            # Ambas hijas desaparecieron: el trade se cerró
            if not parent_open and not children_open:
                # Buscar fill de venta en executions
                exit_price  = None
                exit_action = 'UNKNOWN'
                ticker_sym  = entry['ticker'].split('.')[0]  # símbolo sin sufijo EU

                for fill in ib.fills():
                    sym_match = (fill.contract.symbol == ticker_sym or
                                 fill.contract.symbol == entry['ticker'])
                    if sym_match and fill.execution.side == 'SLD':
                        exit_price  = fill.execution.price
                        exit_action = 'SELL_FILL'

                if exit_price is None:
                    # No hay fill de venta → la orden de entrada nunca se ejecutó
                    # (cancelada antes de llenar) — no marcar como cierre real
                    if not entry.get('entry_filled'):
                        print(f"  ⚪ {entry['ticker']} — bracket cancelado sin fill de entrada")
                        entry['closed']      = True
                        entry['exit_action'] = 'CANCELLED_UNFILLED'
                        entry['closed_at']   = _now_et().isoformat()
                        # No añadir a closures para no mandar Telegram de P&L
                        continue
                    # Si había fill de entrada, estimar salida por precio actual
                    try:
                        import yfinance as yf
                        exit_price  = float(yf.Ticker(entry['ticker']).fast_info.last_price)
                        exit_action = 'ESTIMATED'
                    except Exception:
                        continue

                shares_   = entry.get('shares', 0)
                ref_price = entry.get('entry_fill_price') or entry.get('entry', exit_price)
                pnl_per   = exit_price - ref_price
                entry.update({
                    'closed':      True,
                    'exit_price':  exit_price,
                    'exit_action': exit_action,
                    'pnl_usd':     round(pnl_per * shares_, 2),
                    'pnl_pct':     round(pnl_per / ref_price * 100, 2) if ref_price else 0,
                    'result':      'WIN' if pnl_per > 0 else 'LOSS',
                    'closed_at':   _now_et().isoformat(),
                })
                closures.append(entry)
                icon = '🟢' if pnl_per > 0 else '🔴'
                print(f"  {icon} {entry['ticker']} cerrado — {pnl_per:+.2f}$ ({entry['pnl_pct']:+.1f}%)")

    except Exception as e:
        print(f"  Monitor IBKR: {e}")
    finally:
        ib.disconnect()

    # Enviar Telegram de fills de entrada (fuera del bloque IBKR)
    for e in fills_msg:
        _tg_fill(e)

    return log, closures


# ─────────────────────────────────────────────────────────────────────────────
# Telegram
# ─────────────────────────────────────────────────────────────────────────────

def _send_telegram(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            data={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'HTML',
                  'disable_web_page_preview': 'true'},
            timeout=10,
        )
    except Exception:
        pass


def _tg_confirm_trade(m: dict, fund: Optional[dict] = None) -> bool:
    """
    Envía setup a Telegram con botones ✅ Ejecutar / ❌ Rechazar.
    Espera indefinidamente hasta que el usuario responda.
    Returns True si aprobado, False si rechazado o timeout.
    Sin Telegram configurado → aprueba automáticamente.
    """
    if not BOT_TOKEN or not CHAT_ID:
        return True

    ticker    = m['ticker']
    strat     = m.get('strategy', '')
    strat_tag = '⚡ FLASH' if strat == 'FLASH' else '📈 ACUMULACIÓN'
    rsi_w_str = f"/{m['rsi_weekly']:.0f}w" if m.get('rsi_weekly') else ''
    grade     = (fund or {}).get('grade', '')
    sector    = (fund or {}).get('sector', '')
    meta      = f"  {grade}{' | ' + sector if sector else ''}\n" if grade or sector else ''
    t_src     = '📡' if m.get('target_source') == 'analyst' else '📐'

    text = (
        f"🔔 <b>Setup detectado — {strat_tag}</b>\n"
        f"📉 <b>{ticker}</b>  {m['drop_vs_prev']:+.1f}% hoy  RSI {m['rsi']:.0f}{rsi_w_str}\n"
        f"{meta}"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Entrada: <b>${m['entry']:.2f}</b>\n"
        f"🎯 Target:  ${m['target']:.2f}  (+{m['upside_pct']:.1f}%) {t_src}\n"
        f"🛑 Stop:    ${m['stop']:.2f}  (R:R {m['rr']:.1f}x)\n"
        f"📊 Vol {m['vol_ratio']:.1f}x  |  Caída {m['drop_vs_peak']:+.1f}% desde máx\n"
        f"⏳ <i>Responde cuando puedas — sin límite de tiempo</i>"
    )
    keyboard = {'inline_keyboard': [[
        {'text': '✅ Ejecutar',  'callback_data': f'approve_{ticker}'},
        {'text': '❌ Rechazar', 'callback_data': f'reject_{ticker}'},
    ]]}

    # Enviar mensaje
    try:
        resp   = requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            json={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'HTML',
                  'reply_markup': keyboard, 'disable_web_page_preview': True},
            timeout=10,
        ).json()
        msg_id = resp['result']['message_id']
    except Exception:
        return True  # si falla enviar → ejecutar igual

    # Asegurar que no hay webhook activo (bloquearía getUpdates)
    try:
        requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook',
                      json={'drop_pending_updates': False}, timeout=5)
    except Exception:
        pass

    # Obtener offset actual para ignorar updates anteriores
    try:
        upd    = requests.get(f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates',
                              params={'limit': 1, 'allowed_updates': ['callback_query']},
                              timeout=10).json()
        offset = (upd['result'][-1]['update_id'] + 1) if upd.get('result') else 0
    except Exception:
        offset = 0

    approved = False
    decided  = False

    while not decided:
        wait = 30  # long-polling en bloques de 30s
        try:
            upd = requests.get(
                f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates',
                params={'timeout': wait, 'offset': offset,
                        'allowed_updates': ['callback_query']},
                timeout=wait + 5,
            ).json()
            for update in upd.get('result', []):
                offset = update['update_id'] + 1
                cq     = update.get('callback_query')
                if not cq:
                    continue
                data = cq.get('data', '')
                if data == f'approve_{ticker}':
                    approved, decided = True, True
                elif data == f'reject_{ticker}':
                    approved, decided = False, True
                if decided:
                    requests.post(
                        f'https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery',
                        json={'callback_query_id': cq['id'],
                              'text': '✅ Ejecutando orden...' if approved else '❌ Trade rechazado'},
                        timeout=5,
                    )
                    break
        except Exception:
            time.sleep(5)

    # Editar mensaje con resultado final
    if decided:
        final = f"{'✅ APROBADO' if approved else '❌ RECHAZADO'} — <b>{ticker}</b> {strat_tag}"
    else:
        final = f"⏰ Sin respuesta — <b>{ticker}</b> no ejecutado"
        approved = False
    try:
        requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/editMessageText',
            json={'chat_id': CHAT_ID, 'message_id': msg_id,
                  'text': final, 'parse_mode': 'HTML'},
            timeout=5,
        )
    except Exception:
        pass

    return approved


def _tg_fill(entry: dict):
    """Telegram cuando la orden de ENTRADA se ejecuta realmente en IBKR."""
    et      = _now_et()
    ticker  = entry.get('ticker', '?')
    shares  = entry.get('shares', 0)
    price   = entry.get('entry_fill_price') or entry.get('entry', 0)
    target  = entry.get('target', 0)
    stop    = entry.get('stop', 0)
    pos_usd = round(shares * price, 0)
    upside  = (target - price) / price * 100 if price else 0
    risk    = (price  - stop)  / price * 100 if price else 0
    rr      = upside / risk if risk > 0 else 0
    strat   = entry.get('strategy', '')
    strat_tag = '⚡ FLASH' if strat == 'FLASH' else '📈 ACUMULACIÓN'
    _send_telegram(
        f"🟡 <b>COMPRA EJECUTADA</b>  {et.strftime('%H:%M ET')}\n"
        f"📈 <b>{ticker}</b>  {strat_tag}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Fill: <b>${price:.2f}</b>  ×{shares} acc  = ${pos_usd:,.0f}\n"
        f"🎯 Target: ${target:.2f}  (+{upside:.1f}%)\n"
        f"🛑 Stop:   ${stop:.2f}  (R:R {rr:.1f}x)\n"
        f"⏳ Esperando target o stop..."
    )


def _tg_entry(m: dict, result: dict, fund: Optional[dict] = None):
    et       = _now_et()
    strat    = m.get('strategy', '')
    strat_tag = '⚡ FLASH' if strat == 'FLASH' else '📈 ACUMULACIÓN'
    mode     = f'🔸 DRY RUN ({strat_tag})' if result['status'] == 'DRY_RUN' else f'📋 ORDEN ENVIADA — {strat_tag}'
    shares   = result.get('shares', '?')
    pos_usd  = result.get('position_usd', 0)
    grade    = result.get('grade') or (fund or {}).get('grade') or ''
    sector   = (fund or {}).get('sector') or ''
    t_src    = '📡' if m.get('target_source') == 'analyst' else '📐'
    rsi_w_str = f"/{m['rsi_weekly']:.0f}w" if m.get('rsi_weekly') else ''

    meta_parts = []
    if grade:
        meta_parts.append(f"Grade: {grade}")
    if sector:
        meta_parts.append(sector)
    meta_line  = f"  {' | '.join(meta_parts)}\n" if meta_parts else ''

    _send_telegram(
        f"⚡ <b>Rebote</b>  {et.strftime('%H:%M ET')}\n"
        f"📉 <b>{m['ticker']}</b>  {m['drop_vs_prev']:+.1f}% hoy  RSI {m['rsi']:.0f}{rsi_w_str}\n"
        f"{meta_line}"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Entrada: <b>${m['entry']:.2f}</b>  ({shares} acc, ${pos_usd:,.0f})\n"
        f"🎯 Target:  ${m['target']:.2f}  (<b>+{m['upside_pct']:.1f}%</b>) {t_src}\n"
        f"🛑 Stop:    ${m['stop']:.2f}  (R:R {m['rr']:.1f}x)\n"
        f"📊 Vol {m['vol_ratio']:.1f}x  Soporte ${m['support']:.2f}\n"
        f"{mode}"
    )


def _tg_closure(entry: dict):
    icon = '🟢 WIN' if entry['result'] == 'WIN' else '🔴 LOSS'
    pnl  = entry['pnl_usd']
    pct  = entry['pnl_pct']
    _send_telegram(
        f"{icon}  <b>{entry['ticker']}</b>  {'+' if pnl >= 0 else ''}{pct:.1f}%  "
        f"(${'+' if pnl >= 0 else ''}{pnl:.0f})\n"
        f"Entrada ${entry.get('entry', 0):.2f} → Salida ${entry.get('exit_price', 0):.2f}"
    )


def _ai_eod_narrative(regime: str, vix: float, pnl_today: float,
                       wins: list, losses: list, still_open: list,
                       closed_today: list, pnl_total: float, hist_wr: float) -> str:
    """Genera 2-3 líneas de narrative con Groq/llama sobre el día."""
    api_key = os.environ.get('GROQ_API_KEY', '')
    if not api_key:
        return ''
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        closed_detail = '  '.join(
            f"{e['ticker']} {e.get('pnl_pct', 0):+.1f}%({'WIN' if e.get('result')=='WIN' else 'LOSS'})"
            for e in closed_today
        )
        open_tickers = ', '.join(e['ticker'] for e in still_open[:8])
        context = (
            f"Régimen macro: {regime}, VIX: {vix:.1f}. "
            f"Hoy: {len(closed_today)} cierres ({closed_detail}), P&L {pnl_today:+.0f} USD. "
            f"Posiciones abiertas ({len(still_open)}): {open_tickers}. "
            f"Histórico acumulado: WR {hist_wr:.0f}%, P&L {pnl_total:+.0f} USD."
        )
        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            max_tokens=100,
            messages=[{
                'role': 'user',
                'content': (
                    'Eres el cerebro de un sistema de trading de rebotes. '
                    'Resume el día en máximo 2 frases, en español, directo y útil. '
                    'Sin saludos ni intro. Si hay pérdidas explica brevemente por qué y qué hacer. '
                    f'Datos: {context}'
                )
            }]
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return ''


def _tg_eod_summary(log: list):
    today      = _today_str()
    et         = _now_et()

    today_t    = [e for e in log if e.get('date') == today
                  and e.get('status') in ('EXECUTED', 'DRY_RUN')]
    closed     = [e for e in log if e.get('closed')
                  and (e.get('closed_at', '') or '').startswith(today)]
    still_open = _open_trades(log)
    wins       = [e for e in closed if e.get('result') == 'WIN']
    losses     = [e for e in closed if e.get('result') == 'LOSS']
    pnl_today  = sum(e.get('pnl_usd', 0) for e in closed)

    all_closed = [e for e in log if e.get('closed') and e.get('pnl_usd') is not None]
    pnl_total  = sum(e.get('pnl_usd', 0) for e in all_closed)
    all_wins   = [e for e in all_closed if e.get('result') == 'WIN']
    hist_wr    = len(all_wins) / len(all_closed) * 100 if all_closed else 0

    regime, vix, _ = _load_project_data()

    if not today_t and not closed and not still_open:
        return

    # ── Narrative IA ──────────────────────────────────────────────────────────
    narrative = _ai_eod_narrative(regime, vix, pnl_today, wins, losses,
                                  still_open, closed, pnl_total, hist_wr)

    # ── Líneas de resumen ─────────────────────────────────────────────────────
    pnl_icon = '🟢' if pnl_today >= 0 else '🔴'
    wr_hoy   = f"{len(wins)/len(closed)*100:.0f}%" if closed else '—'

    lines = [
        f"📊 <b>Cierre {et.strftime('%d/%m')}</b>  |  {regime}  VIX {vix:.1f}",
    ]

    if narrative:
        lines += ['', f"🧠 {narrative}", '']

    # Cierres del día — solo si los hay
    if closed:
        lines.append(f"{pnl_icon} Hoy: {len(closed)} cierres  {pnl_today:+.0f} USD  WR {wr_hoy}")
        for e in closed:
            icon = '✅' if e.get('result') == 'WIN' else '❌'
            lines.append(f"  {icon} {e['ticker']} {e.get('pnl_pct', 0):+.1f}% (${e.get('pnl_usd', 0):+.0f})")

    # Posiciones abiertas — solo tickers, no precios
    if still_open:
        tickers_str = '  '.join(e['ticker'] for e in still_open)
        filled = sum(1 for e in still_open if e.get('entry_filled'))
        lines.append(f"\n⏳ Abiertas {len(still_open)} ({filled} con entrada ejecutada)")
        lines.append(f"  {tickers_str}")

    # Histórico en una línea
    if all_closed:
        lines.append(f"\n📈 Acumulado: {len(all_closed)} trades  WR {hist_wr:.0f}%  {pnl_total:+.0f} USD")

    _send_telegram('\n'.join(lines))


# ─────────────────────────────────────────────────────────────────────────────
# Status en terminal
# ─────────────────────────────────────────────────────────────────────────────

def show_status():
    log     = _load_log()
    today   = _today_str()
    open_t  = _open_trades(log)
    today_t = [e for e in log if e.get('date') == today]
    closed  = [e for e in today_t if e.get('closed')]

    print(f"\n{'='*55}")
    print(f"  BOUNCE TRADER — Status  {_now_et().strftime('%H:%M ET')}")
    print(f"{'='*55}")

    if open_t:
        print(f"\n  📂 POSICIONES ABIERTAS ({len(open_t)})")
        for e in open_t:
            try:
                import yfinance as yf
                cur = float(yf.Ticker(e['ticker']).fast_info.last_price)
                unreal = round((cur - e.get('entry', cur)) * e.get('shares', 0), 0)
                pct    = (cur - e.get('entry', cur)) / e.get('entry', cur) * 100
                icon   = '🟢' if unreal >= 0 else '🔴'
                print(f"  {icon} {e['ticker']:8}  entrada ${e.get('entry',0):.2f}  ahora ${cur:.2f}  "
                      f"{'+' if pct >= 0 else ''}{pct:.1f}%  (${'+' if unreal >= 0 else ''}{unreal:.0f})")
            except Exception:
                print(f"  ⏳ {e['ticker']:8}  entrada ${e.get('entry',0):.2f}  ({e.get('shares',0)} acc)")
    else:
        print("\n  Sin posiciones abiertas")

    if closed:
        wins      = [e for e in closed if e.get('result') == 'WIN']
        total_pnl = sum(e.get('pnl_usd', 0) for e in closed)
        print(f"\n  📊 HOY — {len(closed)} cerrado(s)  |  {len(wins)}W/{len(closed)-len(wins)}L  "
              f"|  P&L ${'+' if total_pnl >= 0 else ''}{total_pnl:.0f}")
        for e in closed:
            icon = '🟢' if e.get('result') == 'WIN' else '🔴'
            print(f"  {icon} {e['ticker']:8}  {'+' if e['pnl_pct'] >= 0 else ''}{e['pnl_pct']:.1f}%  "
                  f"(${'+' if e['pnl_usd'] >= 0 else ''}{e['pnl_usd']:.0f})")

    print(f"\n  Total trades en log: {len(log)}")
    print(f"{'='*55}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Datos del proyecto (macro + fundamentales)
# ─────────────────────────────────────────────────────────────────────────────

def _load_project_data() -> tuple:
    """
    Carga macro_radar.json y fundamental_scores.csv.
    Devuelve (regime_name, vix, fund_df).
    regime_name: 'NORMAL' | 'STRESS' | 'ALERT' | 'CRISIS'
    """
    # ── Macro regime ──────────────────────────────────────────────────────────
    macro_path = DOCS / 'macro_radar.json'
    regime = 'NORMAL'
    vix    = 20.0
    if macro_path.exists():
        try:
            raw    = json.loads(macro_path.read_text())
            regime = raw.get('regime', {}).get('name', 'NORMAL').upper()
            vix    = raw.get('signals', {}).get('vix', {}).get('current', 20.0)
        except Exception:
            pass

    # ── Fundamental scores ────────────────────────────────────────────────────
    fund_path = DOCS / 'fundamental_scores.csv'
    fund_df   = None
    if fund_path.exists():
        try:
            fund_df = pd.read_csv(fund_path, low_memory=False)
            fund_df['ticker'] = fund_df['ticker'].astype(str).str.strip().str.upper()
            fund_df = fund_df.set_index('ticker')
        except Exception:
            pass

    return regime, vix, fund_df


def _get_fund(ticker: str, fund_df) -> dict:
    """
    Extrae datos fundamentales del ticker.
    Devuelve dict con: sector, target_analyst, days_to_earnings,
                       earnings_warning, grade, value_score
    """
    empty = {
        'sector':           None,
        'target_analyst':   None,
        'days_to_earnings': None,
        'earnings_warning': False,
        'grade':            None,
        'value_score':      None,
        'analyst_upside':   None,
    }
    if fund_df is None:
        return empty

    # Intentar con sufijo EU y sin él
    keys = [ticker]
    for sfx in EU_MARKETS:
        if ticker.endswith(sfx):
            keys.append(ticker[:-len(sfx)])

    for key in keys:
        if key not in fund_df.index:
            continue
        row = fund_df.loc[key]

        # Grade desde 'tier' o 'quality'
        tier  = str(row.get('tier', '') or '')
        grade = None
        if 'EXCELLENT' in tier.upper():
            grade = 'EXCELLENT'
        elif 'STRONG' in tier.upper():
            grade = 'STRONG'
        elif 'AVERAGE' in tier.upper() or 'ACCEPTABLE' in tier.upper():
            grade = 'AVERAGE'
        elif 'WEAK' in tier.upper():
            grade = 'WEAK'

        # Días a earnings
        dte = row.get('days_to_earnings')
        try:
            dte = int(float(dte)) if dte not in (None, '', 'N/A', 'nan') else None
        except (ValueError, TypeError):
            dte = None

        # Target analistas
        try:
            ta = float(row.get('target_price_analyst') or 0) or None
        except (ValueError, TypeError):
            ta = None

        # Analyst upside
        try:
            au = float(row.get('analyst_upside_pct') or 0) or None
        except (ValueError, TypeError):
            au = None

        return {
            'sector':           str(row.get('sector') or '').strip() or None,
            'target_analyst':   ta,
            'days_to_earnings': dte,
            'earnings_warning': bool(row.get('earnings_warning', False)),
            'grade':            grade,
            'value_score':      float(row.get('fundamental_score') or 0) or None,
            'analyst_upside':   au,
        }

    return empty


# ─────────────────────────────────────────────────────────────────────────────
# Cargador de tickers
# ─────────────────────────────────────────────────────────────────────────────

def _load_tickers() -> list:
    pairs  = []
    seen   = set()
    sources_loaded = 0

    # ── CSVs ──────────────────────────────────────────────────────────────────
    for csv_path in TICKER_SOURCES:
        if not csv_path.exists():
            continue
        try:
            df = pd.read_csv(csv_path)
            # Filtrar value_opportunities por score ≥ 55
            if 'value_score' in df.columns and csv_path.name not in (
                    'value_conviction.csv', 'european_value_conviction.csv'):
                df = df[df['value_score'].notna() & (df['value_score'] >= 55)]
            # mean_reversion: solo EXCELENTE
            if 'quality' in df.columns and 'reversion_score' in df.columns:
                df = df[df['quality'].str.upper().str.contains('EXCELENTE', na=False)]
            is_mr = 'reversion_score' in df.columns  # mean_reversion source
            added = 0
            for _, row in df.iterrows():
                t = str(row.get('ticker', '')).strip().upper()
                n = str(row.get('company_name', '')).strip()
                if t and t not in seen:
                    seen.add(t)
                    pairs.append((t, n, is_mr))
                    added += 1
            if added:
                sources_loaded += 1
                print(f'    {csv_path.name}: +{added} tickers')
        except Exception as e:
            print(f'  Error leyendo {csv_path.name}: {e}')

    # ── cerebro_entry_signals.json — señales BUY y MONITOR ───────────────────
    if CEREBRO_SIGNALS_PATH.exists():
        try:
            raw     = json.loads(CEREBRO_SIGNALS_PATH.read_text())
            signals = raw.get('signals', [])
            added   = 0
            for s in signals:
                if s.get('signal') not in ('STRONG_BUY', 'BUY', 'MONITOR'):
                    continue
                t = str(s.get('ticker', '')).strip().upper()
                n = str(s.get('company_name', '')).strip()
                if t and t not in seen:
                    seen.add(t)
                    pairs.append((t, n, False))  # cerebro = no es mean_reversion
                    added += 1
            if added:
                sources_loaded += 1
                print(f'    cerebro_entry_signals.json: +{added} tickers (BUY/MONITOR)')
        except Exception as e:
            print(f'  Error leyendo cerebro_entry_signals.json: {e}')

    print(f'  Universo: {len(pairs)} tickers únicos de {sources_loaded} fuentes')
    return pairs


# ─────────────────────────────────────────────────────────────────────────────
# Scan principal
# ─────────────────────────────────────────────────────────────────────────────

_eod_sent = False  # flag para enviar resumen solo una vez


def run_scan(port: int, dry_run: bool, extended: bool = False, confirm: bool = False):
    global _eod_sent

    print(f"\n{'='*55}")
    print(f"  BOUNCE TRADER  {_now_et().strftime('%Y-%m-%d %H:%M ET')}")
    mode_str = 'DRY RUN' if dry_run else ('PAPER' if port == IB_PORT_PAPER else '⚠️  LIVE REAL')
    mode_str += ' + PRE/POST MARKET'
    print(f"  {mode_str}")
    print(f"{'='*55}")

    # ── Datos del proyecto ─────────────────────────────────────────────────────
    regime, vix, fund_df = _load_project_data()
    print(f"  Macro: {regime}  |  VIX: {vix:.1f}")

    if regime == 'CRISIS' and not dry_run:
        print('  🚨 CRISIS regime — trading suspendido.')
        _send_telegram(f"🚨 <b>Bounce Trader</b>: régimen CRISIS detectado — sin operaciones hasta normalización.")
        return

    vix_str = f" ⚠️ VIX alto ({vix:.0f})" if vix > 25 else ''
    if regime == 'ALERT' and not dry_run:
        print(f'  ⚠️  ALERT regime — solo FLASH setups con reducción de tamaño.{vix_str}')

    us_open      = _is_us_open()
    eu_open      = _is_eu_open()
    us_extended  = extended and _is_us_extended()

    if not (us_open or eu_open or us_extended) and not dry_run:
        print('  Mercados cerrados — esperando.')
        return

    markets_open = []
    if us_open:     markets_open.append('🇺🇸 US')
    if eu_open:     markets_open.append('🇪🇺 EU')
    if us_extended: markets_open.append('🌙 US Extended')
    print(f'  Mercados: {" + ".join(markets_open) if markets_open else "ninguno (dry-run)"}')

    log = _load_log()

    # 1. Monitorear posiciones abiertas
    if not dry_run and _open_trades(log):
        print('\n  🔍 Comprobando posiciones abiertas...')
        log, closures = _check_positions(port, log)
        _save_log(log)
        for c in closures:
            _tg_closure(c)

    # 2. Resumen de cierre (una vez al día)
    if _is_end_of_day() and not _eod_sent and not dry_run:
        _tg_eod_summary(log)
        _eod_sent = True

    is_live = (port == IB_PORT_LIVE)

    # Límite diario de pérdidas (solo en live)
    if not dry_run and is_live:
        day_pnl = _daily_pnl(log)
        if day_pnl <= -DAILY_LOSS_LIMIT_USD:
            msg = f'🛑 Daily loss limit alcanzado ({day_pnl:+.0f} USD) — sin nuevas órdenes hoy.'
            print(f'  {msg}')
            _send_telegram(msg)
            return

    # Límite de posiciones: paper → amplio para testear; live → estricto según régimen
    base_limit = MAX_OPEN_TRADES_PAPER if not is_live else MAX_OPEN_TRADES
    max_trades = base_limit if regime not in ('STRESS', 'ALERT') else max(base_limit - 3, 3)

    open_cnt = len(_open_trades(log))
    tickers  = _load_tickers()
    print(f'  Trades abiertos: {open_cnt}/{max_trades}')

    if open_cnt >= max_trades and not dry_run:
        print(f'  ⚠️  Límite alcanzado — solo monitoreando.')
        return

    # Sectores ya cubiertos por trades abiertos
    open_sectors: dict = {}
    for ot in _open_trades(log):
        sec = ot.get('sector')
        if sec:
            open_sectors[sec] = open_sectors.get(sec, 0) + 1

    # 3. Escanear nuevos setups
    found = executed = 0
    skipped = []
    setups = []   # lista de setups qualificados para el resumen final

    for ticker, company, from_mr in tickers:
        # Saltar si el mercado de ese ticker no está abierto ahora
        if not dry_run:
            if _is_eu_ticker(ticker) and not eu_open:
                continue
            if not _is_eu_ticker(ticker) and not (us_open or us_extended):
                continue

        fund = _get_fund(ticker, fund_df)

        # Filtro de precio mínimo global: chicharros < $2 siempre descartados
        # Mean reversion más estricto: < $5
        _price_fund = fund.get('current_price') or fund.get('price')
        try:
            _price_val = float(_price_fund) if _price_fund else 0.0
            if _price_val > 0 and _price_val < 2.0:
                print(f"  [{ticker}] ⏭ precio ${_price_val:.2f} < $2 — descartado")
                continue
            if from_mr and _price_val > 0 and _price_val < 5.0:
                print(f"  [{ticker}] ⏭ precio ${_price_val:.2f} < $5 (MR) — descartado")
                continue
        except (ValueError, TypeError):
            pass

        # ── Filtros de proyecto ───────────────────────────────────────────────
        # Earnings en ≤5 días → skip (riesgo binario)
        dte = fund.get('days_to_earnings')
        if dte is not None and 0 <= dte <= 5:
            print(f"  [{ticker}] ⏭ earnings en {dte}d — saltando")
            continue
        if fund.get('earnings_warning'):
            print(f"  [{ticker}] ⏭ earnings_warning activo — saltando")
            continue

        # En ALERT: solo FLASH setups
        if regime == 'ALERT' and not dry_run:
            # lo evaluamos después de obtener m
            pass

        m = _analyze(ticker, fund)
        if m is None:
            continue

        # Segundo check con precio real de entrada (por si fundamental_scores no tenía precio)
        entry_price = m.get('entry', 0)
        if entry_price > 0 and entry_price < 2.0:
            print(f"  [{ticker}] ⏭ precio entrada ${entry_price:.2f} < $2 — descartado")
            continue
        if from_mr and entry_price > 0 and entry_price < 5.0:
            print(f"  [{ticker}] ⏭ precio entrada ${entry_price:.2f} < $5 (MR) — descartado")
            continue

        # Adjuntar VIX al análisis (para sizing dentro de _execute_order)
        m['vix'] = vix

        ok, reason = _qualifies(m)
        rsi_w_str = f"/{m['rsi_weekly']:.0f}w" if m.get('rsi_weekly') else ''
        status_line = (
            f"  [{ticker}] {m['drop_vs_prev']:+.1f}%d {m['drop_vs_peak']:+.1f}%pk"
            f"  RSI {m['rsi']:.0f}{rsi_w_str}  sup {m['dist_support']:.1f}%"
            f"  vol {m['vol_ratio']:.1f}x  R:R {m['rr']:.1f}"
        )

        if not ok:
            print(f"{status_line}  → {reason}")
            continue

        # En ALERT: solo FLASH
        if regime == 'ALERT' and m.get('strategy') != 'FLASH' and not dry_run:
            print(f"{status_line}  → ⛔ ALERT — solo FLASH")
            continue

        strat    = m.get('strategy', '')
        grade    = fund.get('grade')
        sector   = fund.get('sector')
        grade_lbl = f" [{grade}]" if grade else ""
        sector_lbl = f" {sector}" if sector else ""
        print(f"{status_line}  → ✅ {strat}{grade_lbl}{sector_lbl}")
        found += 1
        setups.append({'ticker': ticker, 'strat': strat, 'grade': grade or '', 'rsi': m['rsi'],
                       'drop': m['drop_vs_peak'], 'rr': m['rr'], 'entry': m.get('entry', 0),
                       'stop': m.get('stop', 0), 'target': m.get('target', 0)})

        in_cooldown, cooldown_label = _recently_traded(log, ticker)
        if in_cooldown:
            msg = f'{ticker}: {cooldown_label}'
            print(f'    ⏭ {msg}')
            skipped.append(msg)
            continue

        if open_cnt >= max_trades and not dry_run:
            msg = f'{ticker}: límite {max_trades} trades'
            print(f'    ⏭ {msg}')
            skipped.append(msg)
            continue

        # Sector concentration check
        if sector and open_sectors.get(sector, 0) >= MAX_SAME_SECTOR and not dry_run:
            msg = f'{ticker}: sector {sector} ya cubierto'
            print(f'    ⏭ {msg}')
            skipped.append(msg)
            continue

        # Filtrar WEAK antes de pedir confirmación
        grade_key = (grade or 'AVERAGE').upper()
        if GRADE_RISK_MULT.get(grade_key, 0.7) == 0.0 and not dry_run:
            msg = f'{ticker}: Grade WEAK — no se opera'
            print(f'    ⛔ {msg}')
            skipped.append(msg)
            continue

        # Marcar si es orden fuera de horario regular
        m['outside_rth'] = us_extended and not _is_eu_ticker(ticker) and not us_open

        # Modo confirmación: esperar OK del usuario antes de ejecutar
        if confirm and not dry_run:
            print('    ⏳ Esperando confirmación Telegram (sin timeout)...')
            if not _tg_confirm_trade(m, fund):
                msg = f'{ticker}: rechazado por usuario'
                print(f'    ❌ {msg}')
                skipped.append(msg)
                continue
            print(f'    ✅ Aprobado — ejecutando...')

        result = _execute_order(m, port, dry_run, grade=grade)
        result.update({'ticker': ticker, 'company': company, 'sector': sector})
        log.append(result)
        _save_log(log)

        if result['status'] in ('EXECUTED', 'DRY_RUN'):
            executed += 1
            if not dry_run:
                open_cnt += 1
                if sector:
                    open_sectors[sector] = open_sectors.get(sector, 0) + 1
            _tg_entry(m, result, fund)

    print(f'\n  ✔ {found} setup(s) | {executed} ejecutado(s) | {len(skipped)} omitido(s)')
    if setups:
        print(f"\n  {'─'*55}")
        print(f"  {'TICKER':<10} {'STRAT':<12} {'GRADE':<9} {'RSI':>4} {'CAÍDA':>7} {'R:R':>5}  ENTRADA / STOP / TARGET")
        print(f"  {'─'*55}")
        executed_tickers = {r.get('ticker') for r in log if r.get('status') in ('EXECUTED', 'DRY_RUN', 'EU_PENDING') and r.get('date') == _today_str()}
        for s in setups:
            executed_mark = '✅' if s['ticker'] in executed_tickers else '⏭'
            print(f"  {executed_mark} {s['ticker']:<9} {s['strat']:<12} {s['grade']:<9} {s['rsi']:>4.0f} {s['drop']:>+6.1f}% {s['rr']:>5.1f}x  ${s['entry']:.2f} / ${s['stop']:.2f} / ${s['target']:.2f}")
    print(f"{'='*55}")


# ─────────────────────────────────────────────────────────────────────────────
# Arranque
# ─────────────────────────────────────────────────────────────────────────────

def _prevent_sleep():
    import subprocess
    if sys.platform != 'darwin':
        return None
    try:
        p = subprocess.Popen(['caffeinate', '-dims'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f'  ☕ caffeinate activo (PID {p.pid}) — Mac no se suspenderá')
        return p
    except Exception as e:
        print(f'  ⚠️  caffeinate: {e}')
        return None


def _check_tws(port: int) -> bool:
    """Verifica que TWS está escuchando antes de arrancar."""
    import socket
    try:
        s = socket.create_connection(('127.0.0.1', port), timeout=3)
        s.close()
        return True
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser(description='Bounce Trader')
    parser.add_argument('--loop',     action='store_true')
    parser.add_argument('--dry-run',  action='store_true')
    parser.add_argument('--status',   action='store_true', help='Ver posiciones abiertas/cerradas hoy')
    parser.add_argument('--live',     action='store_true', help='Puerto live 7496')
    parser.add_argument('--confirm',  action='store_true', help='Pedir confirmación por Telegram antes de cada orden')
    # extended siempre activo (pre-market 4-9:30 ET + after-hours 16-20 ET)
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    port = IB_PORT_LIVE if args.live else IB_PORT_PAPER

    if args.live and not args.dry_run:
        print('⚠️  MODO LIVE — órdenes con dinero REAL')
        if input('Escribe "CONFIRMO": ').strip() != 'CONFIRMO':
            print('Abortado.')
            return

    if not args.dry_run and not _check_tws(port):
        print(f'❌ TWS no detectado en puerto {port}.')
        print('   Abre TWS/IB Gateway y vuelve a intentarlo.')
        sys.exit(1)

    if args.loop:
        caff = _prevent_sleep()
        mode = 'DRY RUN' if args.dry_run else f'PAPER (:{port})'
        print(f'\n🚀 Bounce Trader arrancado — {mode}')
        print(f'   Scan cada {SCAN_INTERVAL_MIN} min | Ctrl+C para detener\n')
        try:
            while True:
                try:
                    run_scan(port, args.dry_run, True, confirm=args.confirm)
                except Exception as e:
                    print(f'Error en ciclo: {e}')
                mins = _minutes_to_open()
                wait = SCAN_INTERVAL_MIN * 60 if mins <= 0 else min(mins * 60, SCAN_INTERVAL_MIN * 60)
                next_scan_local = datetime.now() + timedelta(seconds=wait)
                next_scan_et    = _now_et() + timedelta(seconds=wait)
                print(f'  Próximo scan: {next_scan_local.strftime("%H:%M")} local  ({next_scan_et.strftime("%H:%M ET")})')
                time.sleep(wait)
        except KeyboardInterrupt:
            print('\n\nDetenido por el usuario.')
        finally:
            if caff:
                caff.terminate()
                print('☕ caffeinate liberado.')
    else:
        run_scan(port, args.dry_run, True, confirm=args.confirm)


if __name__ == '__main__':
    main()
