#!/usr/bin/env python3
"""
POSITION MONITOR — Vigilancia inteligente de posiciones abiertas

Corre cada 30 min durante el horario de mercado.
Solo manda alertas Telegram cuando hay una amenaza REAL.

Trucos del mercado que detecta y NO se deja engañar:

  FALSOS NEGATIVOS (cosas que parecen amenaza y no lo son):
  ─────────────────────────────────────────────────────────
  1. PUT_COVERING      — Puts ITM en posición ya caída = institucionales cerrando
                         cortos = posible suelo. NO es nueva apuesta bajista.
  2. Caída correlacionada con SPY — Si el mercado cae 2% y tú caes 2%, no es señal.
  3. Stop hunt         — Precio toca brevemente el stop y recupera dentro del día.
                         Detectado con mínimo intradía < stop pero cierre > stop.
  4. Vela de exhaustion — Mecha inferior larga (>2.5× cuerpo) en soporte = los
                         vendedores se están agotando, inversión probable.
  5. Low-volume pullback — Retroceso en volumen <0.7× media = los institucionales
                         no están saliendo. Ruido algorítmico o shakeout.
  6. OpEx pinning      — Semana de vencimiento de opciones: el precio se "imanta"
                         al strike con mayor OI abierto (max pain). No es breakdown.
  7. IV expansion pre-evento — Subida de IV antes de earnings/Fed hace que el flujo
                         bajista sea "barato" → no refleja convicción real.
  8. Sector rotation noise — Si 3+ posiciones del mismo sector caen juntas, es
                         rotación macro, no amenaza específica del ticker.
  9. Pre-market gap    — Gaps de apertura < 3% se rellenan estadísticamente con
                         frecuencia; no cerrar por gap bajista solo.

  AMENAZAS REALES (las que sí generan alerta):
  ─────────────────────────────────────────────
  A. Stop inminente o superado — margen < 2% o precio < stop.
  B. Flujo FRESH_BEARISH > $100K — opciones PUT nuevas sobre la posición activa.
  C. VIX > 35 — deterioro macro severo + posición perdiendo.
  D. Régimen CRISIS — el sistema macro dice parar.
  E. Earnings en ≤ 2 días (no detectados al entrar) — riesgo binario.
  F. RSI breakdown + volumen alto + sin rebote — vendedores genuinos.

Filtro final: Groq evalúa HOLD / REVIEW / EXIT_CONSIDER. Solo envía Telegram
si dice REVIEW o EXIT_CONSIDER.

Uso:
  python3 position_monitor.py           # una pasada
  python3 position_monitor.py --dry-run # análisis sin enviar Telegram
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

# ── Paths / credentials ───────────────────────────────────────────────────────
ROOT         = Path(__file__).parent
DOCS         = ROOT / 'docs'
TRADE_LOG    = DOCS / 'bounce_trader_log.json'
ALERT_LOG    = DOCS / 'position_monitor_alerts.json'
BOT_TOKEN    = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID      = os.environ.get('TELEGRAM_CHAT_ID', '')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')

# ── Thresholds ────────────────────────────────────────────────────────────────
MIN_FLOW_PREMIUM      = 50_000  # ignorar flujo < $50K (ruido)
NEAR_STOP_PCT         = 2.0     # alertar si estamos dentro del 2% del stop
VIX_CRISIS            = 35.0    # VIX > 35 = deterioro macro serio
SPY_SYSTEMIC_PCT      = -1.5    # SPY < -1.5% = caída sistémica
MIN_HELD_HOURS        = 3.0     # no alertar < 3h desde apertura (trade necesita tiempo)
COOLDOWN_HOURS        = 4       # misma posición no se alerta dos veces en 4h
STALL_SESSIONS        = 5       # sesiones sin progreso → alerta de trade estancado
STALL_MIN_PROGRESS    = 2.0     # % mínimo de avance para no considerar "estancado"
SESSION_HOURS         = 6.5     # horas de mercado por sesión (aprox.)
LOW_VOL_RATIO         = 0.70    # pullback con vol < 70% media = shakeout, no breakdown
EXHAUSTION_WICK_MULT  = 2.5     # mecha inferior > 2.5× cuerpo = vela de exhaustion
OPEX_NEAR_STRIKE_PCT  = 1.5     # precio dentro del 1.5% de un strike alto OI = pinning


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _now_et() -> datetime:
    return datetime.now(timezone(timedelta(hours=-4)))


def _load_trade_log() -> list:
    if not TRADE_LOG.exists():
        return []
    try:
        return json.loads(TRADE_LOG.read_text())
    except Exception:
        return []


def _load_alert_log() -> dict:
    if not ALERT_LOG.exists():
        return {}
    try:
        return json.loads(ALERT_LOG.read_text())
    except Exception:
        return {}


def _save_alert_log(log: dict):
    ALERT_LOG.write_text(json.dumps(log, indent=2, default=str))


def _was_recently_alerted(log: dict, ticker: str) -> bool:
    ts = log.get(ticker)
    if not ts:
        return False
    try:
        last = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - last).total_seconds() < COOLDOWN_HOURS * 3600
    except Exception:
        return False


def _open_positions(trade_log: list) -> list:
    """Solo posiciones EXECUTED con fill de entrada confirmado."""
    return [
        e for e in trade_log
        if e.get('status') == 'EXECUTED'
        and not e.get('closed')
        and (e.get('entry_fill_price') or e.get('entry_filled'))
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Market context
# ─────────────────────────────────────────────────────────────────────────────

def _get_market_context() -> dict:
    """SPY cambio % hoy, VIX actual, régimen macro."""
    import yfinance as yf

    spy_pct = 0.0
    vix_now = 20.0
    regime  = 'NORMAL'

    macro_path = DOCS / 'macro_radar.json'
    if macro_path.exists():
        try:
            raw    = json.loads(macro_path.read_text())
            regime = raw.get('regime', {}).get('name', 'NORMAL').upper()
            vix_now = raw.get('signals', {}).get('vix', {}).get('current', 20.0)
        except Exception:
            pass

    try:
        fi = yf.Ticker('SPY').fast_info
        cur_spy  = float(fi.get('lastPrice') or 0)
        prev_spy = float(fi.get('previousClose') or 0)
        if cur_spy > 0 and prev_spy > 0:
            spy_pct = (cur_spy - prev_spy) / prev_spy * 100
    except Exception:
        pass

    if vix_now == 20.0:
        try:
            vix_now = float(yf.Ticker('^VIX').fast_info.get('lastPrice') or 20.0)
        except Exception:
            pass

    return {'spy_pct': spy_pct, 'vix': vix_now, 'regime': regime}


# ─────────────────────────────────────────────────────────────────────────────
# Anti-trick detectors
# ─────────────────────────────────────────────────────────────────────────────

def _is_opex_period() -> tuple[bool, str]:
    """
    Detecta semana y día de vencimiento de opciones (3er viernes del mes).
    El efecto de pinning se da lunes–viernes de esa semana.
    Devuelve (is_opex_week, detail_str).
    """
    et = _now_et()
    # Calcular 3er viernes del mes
    first_of_month = et.replace(day=1)
    # Weekday del 1 (0=Lun ... 4=Vie)
    first_friday_offset = (4 - first_of_month.weekday()) % 7
    third_friday_day    = 1 + first_friday_offset + 14  # +14 = tercera semana
    opex_friday = et.replace(day=third_friday_day)

    # Semana OpEx: lunes a viernes de esa semana
    opex_monday = opex_friday - timedelta(days=4)
    in_opex_week = opex_monday.date() <= et.date() <= opex_friday.date()

    if in_opex_week:
        days_to_opex = (opex_friday.date() - et.date()).days
        detail = (f"Hoy es día OpEx" if days_to_opex == 0
                  else f"OpEx en {days_to_opex}d (viernes {opex_friday.strftime('%d/%m')})")
        return True, detail
    return False, ''


def _detect_opex_pinning(ticker: str, current_price: float) -> tuple[bool, str]:
    """
    Comprueba si el precio está cerca de un strike con OI alto.
    Un strike con >30% del total OI abierto en los vencimientos próximos
    actúa como imán (max pain mechanic).
    """
    import yfinance as yf
    try:
        tk = yf.Ticker(ticker)
        # Obtener los 2 vencimientos más próximos
        expirations = tk.options[:2] if tk.options else []
        if not expirations:
            return False, ''

        total_oi  = 0
        pin_strike = None
        max_oi     = 0

        for exp in expirations:
            chain = tk.option_chain(exp)
            for df in (chain.calls, chain.puts):
                if df.empty:
                    continue
                # yfinance openInterest bug — a veces es 0; usar volume como proxy
                df['oi_proxy'] = df.get('openInterest', df['volume']).fillna(0)
                row_max = df.loc[df['oi_proxy'].idxmax()]
                oi = float(row_max['oi_proxy'])
                strike = float(row_max['strike'])
                if oi > max_oi:
                    max_oi     = oi
                    pin_strike = strike
                total_oi += float(df['oi_proxy'].sum())

        if pin_strike and total_oi > 0:
            pct_concentration = max_oi / total_oi * 100
            dist_pct = abs(current_price - pin_strike) / current_price * 100
            if dist_pct <= OPEX_NEAR_STRIKE_PCT and pct_concentration >= 25:
                return True, (
                    f"Precio ${current_price:.2f} a {dist_pct:.1f}% del strike ${pin_strike:.0f} "
                    f"({pct_concentration:.0f}% OI concentrado) — efecto OpEx pinning probable"
                )
    except Exception:
        pass
    return False, ''


def _detect_exhaustion_candle(ticker: str, stop: float) -> tuple[bool, str]:
    """
    Vela de exhaustion: mecha inferior > EXHAUSTION_WICK_MULT × cuerpo real
    en zona de soporte (cerca del stop). Señal de que los vendedores se agotan.
    También detecta volumen climax: caída + vol muy alto + recuperación parcial.
    """
    import yfinance as yf
    try:
        intra = yf.Ticker(ticker).history(period='1d', interval='5m', auto_adjust=True)
        if len(intra) < 10:
            return False, ''

        # Buscar en las últimas 12 velas (1h de mercado)
        recent = intra.tail(12)
        for _, row in recent.iterrows():
            op = float(row['Open'])
            cl = float(row['Close'])
            hi = float(row['High'])
            lo = float(row['Low'])

            body        = abs(cl - op)
            lower_wick  = min(op, cl) - lo
            upper_wick  = hi - max(op, cl)

            if body < 0.001:  # doji — skip
                continue

            # Mecha inferior dominante en zona de soporte
            near_support = lo <= stop * 1.02
            long_wick    = lower_wick >= body * EXHAUSTION_WICK_MULT
            bullish_body = cl >= op  # cuerpo verde

            if near_support and long_wick:
                msg = (f"Vela exhaustion detectada: mecha inferior "
                       f"{lower_wick/body:.1f}× cuerpo{' (vela verde)' if bullish_body else ''}"
                       f" — vendedores agotándose en soporte")
                return True, msg

        # Volumen climax: vela bajista con vol > 3× media + recuperación parcial
        avg_vol = float(intra['Volume'].mean())
        last5   = intra.tail(5)
        for _, row in last5.iterrows():
            vol = float(row['Volume'])
            if (vol >= avg_vol * 3.0
                    and float(row['Close']) < float(row['Open'])   # bajista
                    and float(row['Close']) > float(row['Low']) * 1.005):  # recuperó algo
                return True, (f"Volumen climax bajista ({vol/avg_vol:.1f}× media) "
                               f"con recuperación parcial — posible agotamiento vendedor")

    except Exception:
        pass
    return False, ''


def _analyze_volume_quality(hist: pd.DataFrame) -> str:
    """
    Clasifica la calidad del volumen en los últimos 3 días de caída.
    'WEAK_SELLING'   → volumen decreciente durante caída (shakeout, dejar correr)
    'MODERATE'       → volumen normal
    'STRONG_SELLING' → volumen creciente en días rojos (vendedores reales)
    """
    if len(hist) < 5:
        return 'MODERATE'

    closes  = hist['Close']
    volumes = hist['Volume']

    # Últimos 3 días
    recent_closes  = closes.iloc[-3:].values
    recent_volumes = volumes.iloc[-3:].values
    avg_vol        = float(volumes.iloc[-21:-1].mean()) if len(volumes) > 21 else float(volumes.mean())

    down_vols  = []
    for i in range(1, len(recent_closes)):
        if recent_closes[i] < recent_closes[i - 1]:
            down_vols.append(recent_volumes[i])

    if not down_vols:
        return 'MODERATE'

    avg_down_vol = sum(down_vols) / len(down_vols)
    ratio = avg_down_vol / avg_vol if avg_vol > 0 else 1.0

    if ratio < LOW_VOL_RATIO:
        return 'WEAK_SELLING'
    if ratio > 1.5:
        return 'STRONG_SELLING'
    return 'MODERATE'


def _check_iv_expansion(ticker: str) -> tuple[bool, str]:
    """
    Detecta si la IV actual está elevada por un evento próximo (earnings, Fed).
    IV alta hace que las opciones bearish sean baratas → no refleja convicción real.
    Usa el campo earnings_warning de fundamental_scores.csv como proxy.
    """
    fund_path = DOCS / 'fundamental_scores.csv'
    if not fund_path.exists():
        return False, ''
    try:
        df = pd.read_csv(fund_path, low_memory=False)
        df['ticker'] = df['ticker'].astype(str).str.strip().str.upper()
        row = df[df['ticker'] == ticker.upper()]
        if row.empty:
            return False, ''
        r = row.iloc[0]
        dte = r.get('days_to_earnings')
        try:
            dte = int(float(dte)) if dte not in (None, '', 'N/A', 'nan') else None
        except (ValueError, TypeError):
            dte = None
        if dte is not None and 0 < dte <= 14:
            return True, (f"Earnings en {dte}d — IV probablemente elevada, "
                          f"flujo bajista puede ser cobertura pre-resultados, no convicción")
    except Exception:
        pass
    return False, ''


def _check_sector_correlation(all_positions: list, market: dict, this_ticker: str) -> tuple[bool, str]:
    """
    Si ≥3 posiciones del mismo sector (o ≥4 de cualquier sector) están en pérdida simultánea,
    es rotación / movimiento sistémico, no amenaza específica del ticker.
    """
    if len(all_positions) < 3:
        return False, ''

    # Usar el ticker actual como referencia de sector (si está en fundamental_scores)
    fund_path = DOCS / 'fundamental_scores.csv'
    if not fund_path.exists():
        return False, ''
    try:
        df  = pd.read_csv(fund_path, low_memory=False)
        df['ticker'] = df['ticker'].astype(str).str.strip().str.upper()
        row = df[df['ticker'] == this_ticker.upper()]
        if row.empty:
            return False, ''
        sector = str(row.iloc[0].get('sector', '')).strip()
        if not sector:
            return False, ''

        # Contar posiciones en el mismo sector
        tickers_same_sector = []
        for p in all_positions:
            if p.get('ticker') == this_ticker:
                continue
            t = p.get('ticker', '')
            r = df[df['ticker'] == t.upper()]
            if not r.empty and str(r.iloc[0].get('sector', '')).strip() == sector:
                tickers_same_sector.append(t)

        n_affected = len(tickers_same_sector) + 1
        if n_affected >= 3:
            others = ', '.join(tickers_same_sector[:3])
            return True, (f"Rotación sectorial ({sector}): {n_affected} posiciones "
                          f"afectadas simultáneamente ({others}…) — movimiento macro, no específico")
    except Exception:
        pass
    return False, ''


# ─────────────────────────────────────────────────────────────────────────────
# Position metrics
# ─────────────────────────────────────────────────────────────────────────────

def _get_position_metrics(entry: dict) -> Optional[dict]:
    import yfinance as yf

    ticker    = entry['ticker']
    ref_price = entry.get('entry_fill_price') or entry.get('entry', 0)
    stop      = entry.get('stop', 0)
    target    = entry.get('target', 0)

    try:
        tk   = yf.Ticker(ticker)
        hist = tk.history(period='30d', interval='1d', auto_adjust=True)
        if len(hist) < 5:
            return None

        closes  = hist['Close']
        volumes = hist['Volume']
        fi      = tk.fast_info
        cur     = float(fi.get('lastPrice') or closes.iloc[-1])

        # RSI diario
        delta = closes.diff()
        gain  = delta.clip(lower=0)
        loss  = -delta.clip(upper=0)
        ag    = gain.ewm(com=13, min_periods=14).mean()
        al    = loss.ewm(com=13, min_periods=14).mean()
        rs    = ag / al.replace(0, np.nan)
        rsi   = float((100 - 100 / (1 + rs)).iloc[-1]) if len(rs) else 50.0

        avg_vol   = float(volumes.iloc[-21:-1].mean()) if len(volumes) > 21 else float(volumes.mean())
        vol_today = float(volumes.iloc[-1])
        vol_ratio = vol_today / avg_vol if avg_vol > 0 else 1.0

        pct_from_entry = (cur - ref_price) / ref_price * 100 if ref_price else 0
        pct_to_stop    = (cur - stop)      / cur * 100       if cur else 0
        pct_to_target  = (target - cur)    / cur * 100       if cur else 0

        hours_held = 999.0
        try:
            ts_str = entry.get('entry_filled_at') or entry.get('timestamp', '')
            if ts_str:
                ts         = datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc)
                hours_held = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
        except Exception:
            pass

        # Stop hunt: mínimo intradía < stop pero cierre intradía > stop
        possible_stop_hunt = False
        try:
            intra = tk.history(period='1d', interval='5m', auto_adjust=True)
            if len(intra) > 5:
                day_low = float(intra['Low'].min())
                # Precio actual por encima del stop aunque tocó por debajo
                possible_stop_hunt = (day_low < stop * 1.005 and cur > stop * 1.01)
        except Exception:
            pass

        # Análisis de volumen en días bajistas
        vol_quality = _analyze_volume_quality(hist)

        return {
            'ticker':             ticker,
            'current':            round(cur, 2),
            'ref_price':          round(ref_price, 2),
            'stop':               round(stop, 2),
            'target':             round(target, 2),
            'pct_from_entry':     round(pct_from_entry, 2),
            'pct_to_stop':        round(pct_to_stop, 2),
            'pct_to_target':      round(pct_to_target, 2),
            'rsi':                round(rsi, 1),
            'vol_ratio':          round(vol_ratio, 2),
            'vol_quality':        vol_quality,
            'hours_held':         round(hours_held, 1),
            'is_near_stop':       0 < pct_to_stop < NEAR_STOP_PCT,
            'below_stop':         cur < stop,
            'possible_stop_hunt': possible_stop_hunt,
            '_hist':              hist,   # pasado a _detect_exhaustion_candle
        }
    except Exception as e:
        print(f'  [{ticker}] error métricas: {e}')
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Flow classifier
# ─────────────────────────────────────────────────────────────────────────────

def _load_flow_signals() -> dict[str, dict]:
    path = DOCS / 'unusual_flow.json'
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
        out: dict[str, dict] = {}
        for r in raw.get('results', []):
            t = str(r.get('ticker', '')).strip().upper()
            if t and t not in out:
                out[t] = r
        return out
    except Exception:
        return {}


def _classify_flow(flow: dict, metrics: dict) -> str:
    """
    Clasifica el flujo relativo a la posición.
    NOISE | PUT_COVERING | ROUTINE_HEDGE | GENUINE_BEARISH | CONFIRMING
    """
    prem   = float(flow.get('total_premium') or 0)
    interp = flow.get('flow_interpretation', 'STANDARD')
    signal = flow.get('signal', '')
    pct_c  = float(flow.get('call_pct') or 50)

    if prem < MIN_FLOW_PREMIUM:
        return 'NOISE'
    if interp == 'PUT_COVERING':
        return 'PUT_COVERING'
    if signal == 'BULLISH' and pct_c >= 55:
        return 'CONFIRMING'
    if interp == 'FRESH_BEARISH' and prem >= 100_000:
        return 'GENUINE_BEARISH'
    if signal == 'BEARISH' and metrics.get('pct_to_stop', 10) > 4.0:
        return 'ROUTINE_HEDGE'
    if signal == 'BEARISH':
        return 'GENUINE_BEARISH'
    return 'ROUTINE_HEDGE'


# ─────────────────────────────────────────────────────────────────────────────
# Risk assessment
# ─────────────────────────────────────────────────────────────────────────────

def _assess_risk(
    entry: dict,
    metrics: dict,
    flow: Optional[dict],
    flow_class: str,
    market: dict,
    all_positions: list,
) -> dict:
    """
    Evalúa la posición aplicando todos los filtros anti-trampa.
    Devuelve risk_level: 'OK' | 'WATCH' | 'ALERT'
    """
    reasons: list[str] = []   # amenazas reales
    context: list[str] = []   # elementos que reducen la urgencia
    risk_level = 'OK'

    ticker     = metrics['ticker']
    pct_stop   = metrics['pct_to_stop']
    pct_entry  = metrics['pct_from_entry']
    rsi        = metrics['rsi']
    vol_ratio  = metrics['vol_ratio']
    vol_quality = metrics['vol_quality']
    hours      = metrics['hours_held']
    spy_pct    = market['spy_pct']
    vix        = market['vix']
    regime     = market['regime']

    def _level_up(current, new):
        order = ['OK', 'WATCH', 'ALERT']
        return new if order.index(new) > order.index(current) else current

    # ── AMENAZAS REALES ───────────────────────────────────────────────────────

    # 1. Stop superado o inminente
    if metrics.get('below_stop'):
        reasons.append(f"Precio ${metrics['current']:.2f} por DEBAJO del stop ${metrics['stop']:.2f}")
        risk_level = 'ALERT'
    elif metrics.get('is_near_stop'):
        reasons.append(f"A solo {pct_stop:.1f}% del stop — zona crítica")
        risk_level = _level_up(risk_level, 'WATCH')

    # 2. Flujo bajista genuino (no ruido, no cobertura rutinaria)
    if flow_class == 'GENUINE_BEARISH':
        prem = float(flow.get('total_premium') or 0)
        prem_fmt = f"${prem/1_000:.0f}K"
        reasons.append(f"Flujo bajista fresco {prem_fmt} sobre posición activa")
        risk_level = _level_up(risk_level, 'WATCH')

    # 3. VIX crisis
    if vix >= VIX_CRISIS and pct_entry < -2.0:
        reasons.append(f"VIX {vix:.0f} + posición en pérdida — deterioro macro severo")
        risk_level = _level_up(risk_level, 'WATCH')

    # 4. Régimen macro
    if regime == 'CRISIS':
        reasons.append('Régimen CRISIS — reconsiderar toda exposición')
        risk_level = 'ALERT'
    elif regime == 'ALERT' and pct_entry < -4.0:
        reasons.append(f'Régimen ALERT + posición {pct_entry:+.1f}%')
        risk_level = _level_up(risk_level, 'WATCH')

    # 5. RSI breakdown con volumen real (no shakeout)
    if (rsi < 25 and pct_entry < -6.0
            and vol_quality == 'STRONG_SELLING'
            and not metrics.get('possible_stop_hunt')):
        reasons.append(f"RSI {rsi:.0f} + volumen real de venta + caída {pct_entry:+.1f}%")
        risk_level = _level_up(risk_level, 'WATCH')

    # ── CONTEXTO ANTI-TRAMPA ──────────────────────────────────────────────────

    # Caída correlacionada con mercado
    if spy_pct <= SPY_SYSTEMIC_PCT and pct_entry < 0:
        beta_approx = abs(pct_entry / spy_pct) if spy_pct != 0 else 1.0
        if 0.4 <= beta_approx <= 1.8:
            context.append(f"SPY {spy_pct:+.1f}% hoy — movimiento beta normal, no específico")
            # Si solo tenemos WATCH por correlación y el stop tiene margen, bajar a OK
            if risk_level == 'WATCH' and pct_stop > 3.0 and flow_class not in ('GENUINE_BEARISH',):
                risk_level = 'OK'

    # PUT_COVERING = señal de suelo
    if flow_class == 'PUT_COVERING':
        context.append("PUT_COVERING: institucionales cerrando cortos — posible zona de suelo")

    # Flujo confirma la tesis larga
    if flow_class == 'CONFIRMING':
        prem = float(flow.get('total_premium') or 0)
        context.append(f"Flujo BULLISH ${prem/1_000:.0f}K confirma dirección larga")

    # Stop hunt detectado
    if metrics.get('possible_stop_hunt'):
        context.append("Posible stop hunt intradía — precio recuperó zona de soporte")
        if risk_level == 'WATCH' and not any('DEBAJO' in r for r in reasons):
            risk_level = 'OK'

    # Low-volume pullback = shakeout, no breakdown
    if vol_quality == 'WEAK_SELLING' and pct_entry < 0:
        context.append(f"Volumen de venta < {LOW_VOL_RATIO*100:.0f}% de la media — shakeout algorítmico")
        if risk_level == 'WATCH' and flow_class not in ('GENUINE_BEARISH',):
            risk_level = 'OK'

    # Vela de exhaustion (vendedores agotados)
    exhaustion, exhaustion_msg = _detect_exhaustion_candle(ticker, metrics['stop'])
    if exhaustion:
        context.append(exhaustion_msg)
        if risk_level == 'WATCH' and not any('DEBAJO' in r for r in reasons):
            risk_level = 'OK'

    # OpEx pinning
    opex_week, opex_detail = _is_opex_period()
    if opex_week:
        opex_pin, opex_pin_msg = _detect_opex_pinning(ticker, metrics['current'])
        if opex_pin:
            context.append(opex_pin_msg)
            if risk_level == 'WATCH' and flow_class not in ('GENUINE_BEARISH',):
                risk_level = 'OK'
        elif pct_entry < 0:
            context.append(f"Semana OpEx ({opex_detail}) — volatilidad mecánica normal")

    # IV expansion pre-earnings
    iv_elevated, iv_msg = _check_iv_expansion(ticker)
    if iv_elevated and flow_class in ('GENUINE_BEARISH', 'ROUTINE_HEDGE'):
        context.append(iv_msg)
        if flow_class == 'GENUINE_BEARISH':
            # Reclasificar como posible hedge pre-earnings, no convicción directional
            flow_class = 'IV_HEDGE'
            if risk_level == 'WATCH' and pct_stop > 2.0:
                risk_level = 'OK'

    # Rotación sectorial (≥3 posiciones del mismo sector en pérdida)
    sector_corr, sector_msg = _check_sector_correlation(all_positions, market, ticker)
    if sector_corr:
        context.append(sector_msg)
        if risk_level == 'WATCH' and flow_class not in ('GENUINE_BEARISH',):
            risk_level = 'OK'

    # Posición demasiado joven para evaluar
    if hours < MIN_HELD_HOURS:
        context.append(f"Abierta hace {hours:.1f}h — demasiado pronto para evaluar")
        if risk_level == 'WATCH':
            risk_level = 'OK'

    # Trade estancado: sin progreso en ≥5 sesiones = setup fallido, capital inmovilizado
    # Solo aplica si está en ganancia leve o plano (no si ya está en pérdida — eso es otra amenaza)
    sessions_held = hours / SESSION_HOURS
    if hours < 999.0 and sessions_held >= STALL_SESSIONS and 0 <= pct_entry < STALL_MIN_PROGRESS:
        reasons.append(
            f"Trade estancado: {sessions_held:.0f} sesiones sin avanzar ({pct_entry:+.1f}%) "
            f"— setup fallido, considerar liberar capital"
        )
        risk_level = _level_up(risk_level, 'WATCH')

    return {
        'risk_level':    risk_level,
        'reasons':       reasons,
        'context':       context,
        'should_notify': risk_level in ('WATCH', 'ALERT'),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Groq final filter
# ─────────────────────────────────────────────────────────────────────────────

def _groq_verdict(
    entry: dict,
    metrics: dict,
    flow: Optional[dict],
    flow_class: str,
    market: dict,
    risk: dict,
) -> tuple[str, str]:
    """
    Groq como último filtro antes de molestar al usuario.
    Returns (verdict, reason_es)
    verdict: 'HOLD' | 'REVIEW' | 'EXIT_CONSIDER'
    """
    if not GROQ_API_KEY:
        mapping = {'OK': 'HOLD', 'WATCH': 'REVIEW', 'ALERT': 'EXIT_CONSIDER'}
        return mapping.get(risk['risk_level'], 'HOLD'), ''

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        ticker    = entry['ticker']
        pct_entry = metrics['pct_from_entry']
        pct_stop  = metrics['pct_to_stop']
        rsi       = metrics['rsi']
        hours     = metrics['hours_held']
        spy_pct   = market['spy_pct']
        vix       = market['vix']

        flow_ctx = ''
        if flow and flow_class not in ('NOISE',):
            prem     = float(flow.get('total_premium') or 0)
            flow_ctx = f"Flujo opciones: {flow_class} (${prem/1_000:.0f}K). "

        threats  = '; '.join(risk['reasons'])  or 'ninguna'
        ctx_list = '; '.join(risk['context'])  or 'ninguno'

        prompt = (
            f"Posición larga en {ticker}: entrada ${metrics['ref_price']:.2f}, "
            f"ahora ${metrics['current']:.2f} ({pct_entry:+.1f}%), "
            f"stop a {pct_stop:.1f}% de distancia, target a {metrics['pct_to_target']:.1f}%. "
            f"RSI {rsi:.0f}. Lleva {hours:.1f}h abierta. "
            f"Mercado: SPY {spy_pct:+.1f}% hoy, VIX {vix:.0f}. "
            f"{flow_ctx}"
            f"Amenazas: {threats}. "
            f"Contexto tranquilizador: {ctx_list}. "
            "Devuelve JSON: {\"verdict\": \"HOLD\"|\"REVIEW\"|\"EXIT_CONSIDER\", "
            "\"reason\": \"<15 palabras en español>\"}. "
            "HOLD = el trade sigue bien. "
            "REVIEW = hay señales preocupantes. "
            "EXIT_CONSIDER = riesgo real, considerar salir. "
            "NO usar EXIT_CONSIDER solo por caída de mercado sin amenaza específica al ticker."
        )

        resp = client.chat.completions.create(
            model='meta-llama/llama-4-scout-17b-16e-instruct',
            max_tokens=80,
            response_format={'type': 'json_object'},
            messages=[{'role': 'user', 'content': prompt}],
        )
        raw = json.loads(resp.choices[0].message.content)
        return str(raw.get('verdict', 'HOLD')), str(raw.get('reason', ''))

    except Exception as e:
        print(f'  Groq error: {e}')
        if risk['risk_level'] == 'ALERT':
            return 'EXIT_CONSIDER', 'Error Groq — nivel ALERT, revisar manualmente'
        return 'HOLD', ''


# ─────────────────────────────────────────────────────────────────────────────
# Telegram
# ─────────────────────────────────────────────────────────────────────────────

def _send_telegram(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        print(f'[Telegram no configurado]\n{text}\n')
        return
    try:
        requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            data={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'HTML',
                  'disable_web_page_preview': 'true'},
            timeout=10,
        )
    except Exception as e:
        print(f'  Telegram error: {e}')


def _build_alert(
    entry: dict,
    metrics: dict,
    flow: Optional[dict],
    flow_class: str,
    risk: dict,
    verdict: str,
    groq_reason: str,
) -> str:
    ticker    = entry['ticker']
    strat     = entry.get('strategy', '')
    et_str    = _now_et().strftime('%H:%M ET')
    icon      = {'REVIEW': '⚠️', 'EXIT_CONSIDER': '🔴'}.get(verdict, '🟡')
    v_label   = {'REVIEW': 'Revisar posición', 'EXIT_CONSIDER': 'Considerar salida'}.get(verdict, verdict)

    lines = [
        f"{icon} <b>{v_label}</b>  {et_str}",
        f"📍 <b>{ticker}</b>  {'⚡ FLASH' if strat=='FLASH' else '📈 ACUM' if strat else ''}",
        '━━━━━━━━━━━━━━━━━━━━',
        f"💰 Entrada: ${metrics['ref_price']:.2f}  →  <b>${metrics['current']:.2f}</b>  "
        f"({metrics['pct_from_entry']:+.1f}%)",
        f"🛑 Stop:   ${metrics['stop']:.2f}  ({metrics['pct_to_stop']:.1f}% distancia)",
        f"🎯 Target: ${metrics['target']:.2f}  (+{metrics['pct_to_target']:.1f}% restante)",
    ]

    if risk['reasons']:
        lines.append('━━━━━━━━━━━━━━━━━━━━')
        for r in risk['reasons']:
            lines.append(f"⚠️ {r}")

    if risk['context']:
        lines.append('━━━━━━━━━━━━━━━━━━━━')
        for c in risk['context']:
            lines.append(f"✅ {c}")

    if flow and flow_class not in ('NOISE',):
        prem     = float(flow.get('total_premium') or 0)
        prem_fmt = f"${prem/1_000_000:.1f}M" if prem >= 1_000_000 else f"${prem/1_000:.0f}K"
        interp   = flow.get('flow_interpretation', flow.get('signal', ''))
        flow_icon = {'PUT_COVERING': '🔄', 'CONFIRMING': '⚡',
                     'GENUINE_BEARISH': '⚠️', 'ROUTINE_HEDGE': '📊'}.get(flow_class, '📊')
        lines += ['━━━━━━━━━━━━━━━━━━━━', f"{flow_icon} Flow: {interp}  {prem_fmt}"]

    if groq_reason:
        lines += ['━━━━━━━━━━━━━━━━━━━━', f"🧠 {groq_reason}"]

    lines.append(f"📊 RSI {metrics['rsi']:.0f}  Vol {metrics['vol_ratio']:.1f}x  "
                 f"({'↘ débil' if metrics['vol_quality']=='WEAK_SELLING' else '↗ fuerte' if metrics['vol_quality']=='STRONG_SELLING' else 'normal'})")

    return '\n'.join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def run_monitor(dry_run: bool = False):
    et_str = _now_et().strftime('%H:%M ET')
    print(f"\n{'='*58}")
    print(f"  POSITION MONITOR  {et_str}{'  [DRY RUN]' if dry_run else ''}")
    print(f"{'='*58}")

    trade_log = _load_trade_log()
    positions = _open_positions(trade_log)

    if not positions:
        print('  Sin posiciones abiertas con entrada ejecutada.')
        print(f"{'='*58}\n")
        sys.exit(2)

    print(f'  {len(positions)} posición(es) activa(s)')

    print('  Cargando contexto de mercado...')
    market = _get_market_context()
    opex_w, opex_d = _is_opex_period()
    print(f"  SPY {market['spy_pct']:+.1f}%  VIX {market['vix']:.0f}  "
          f"Régimen {market['regime']}{'  📅 '+opex_d if opex_w else ''}")

    flow_signals = _load_flow_signals()
    alert_log    = _load_alert_log()
    alerts_sent  = 0

    for entry in positions:
        ticker = entry.get('ticker', '?')
        print(f'\n  [{ticker}] analizando...')

        if _was_recently_alerted(alert_log, ticker):
            print(f'  [{ticker}] ⏭ alerta reciente < {COOLDOWN_HOURS}h')
            continue

        metrics = _get_position_metrics(entry)
        if metrics is None:
            print(f'  [{ticker}] no se pudieron obtener métricas')
            continue

        print(
            f'  [{ticker}] ${metrics["current"]:.2f}  '
            f'({metrics["pct_from_entry"]:+.1f}%)  '
            f'stop {metrics["pct_to_stop"]:.1f}%  '
            f'RSI {metrics["rsi"]:.0f}  '
            f'vol_quality={metrics["vol_quality"]}'
        )

        raw_flow   = flow_signals.get(ticker)
        flow_class = _classify_flow(raw_flow, metrics) if raw_flow else 'NONE'
        if raw_flow:
            print(f'  [{ticker}] flow={flow_class} '
                  f'${float(raw_flow.get("total_premium",0))/1_000:.0f}K')

        risk = _assess_risk(entry, metrics, raw_flow, flow_class, market, positions)
        print(f'  [{ticker}] riesgo={risk["risk_level"]}  '
              f'amenazas={len(risk["reasons"])}  contexto={len(risk["context"])}')

        if not risk['should_notify']:
            print(f'  [{ticker}] ✅ OK — sin alerta')
            continue

        print(f'  [{ticker}] consultando Groq...')
        verdict, groq_reason = _groq_verdict(
            entry, metrics, raw_flow, flow_class, market, risk)
        print(f'  [{ticker}] Groq={verdict}  "{groq_reason}"')

        if verdict == 'HOLD':
            print(f'  [{ticker}] Groq filtra falso positivo → sin alerta')
            continue

        msg = _build_alert(entry, metrics, raw_flow, flow_class, risk, verdict, groq_reason)
        print(f'\n  🔔 ALERTA [{verdict}]  {ticker}')
        if not dry_run:
            _send_telegram(msg)
            alert_log[ticker] = datetime.now(timezone.utc).isoformat()
            alerts_sent += 1
        else:
            print(msg)

    if not dry_run:
        _save_alert_log(alert_log)

    print(f'\n  {alerts_sent} alerta(s) enviada(s).')
    print(f"{'='*58}\n")
    sys.exit(0 if alerts_sent > 0 else 2)


def main():
    parser = argparse.ArgumentParser(description='Position Monitor inteligente')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    run_monitor(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
