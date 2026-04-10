#!/usr/bin/env python3
"""
INTRADAY BOUNCE SCANNER
Runs every 30 min during US market hours (Mon-Fri 13:30-20:00 UTC).

Detects tickers from the VALUE conviction universe with:
  - Caída ≥3% intraday vs cierre anterior
  - RSI diario < 35 (oversold)
  - Precio dentro del 5% del soporte de 20 días
  - Volumen elevado (>1.3x media) — señal de agotamiento vendedor
  - R:R ≥ 1.5

Envía alerta Telegram SOLO cuando hay un setup válido.
Deduplicación: mismo ticker no se alerta dos veces en 4 horas.

Exit 0 = alerta enviada | Exit 2 = nada que hacer (no commit)
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).parent
DOCS      = ROOT / "docs"
CONV_US   = DOCS / "value_conviction.csv"
CONV_EU   = DOCS / "european_value_conviction.csv"
ALERT_LOG = DOCS / "intraday_bounce_alerts.json"

# ── Credentials ───────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

# ── Parameters ────────────────────────────────────────────────────────────────
MIN_DROP_PCT     = -3.0  # caída mínima vs cierre anterior (%)
MAX_RSI          = 30    # RSI diario máximo para calificar (Connors: <30 = oversold real)
MAX_SUPPORT_DIST = 5.0   # distancia máxima al soporte de 20d (%)
MIN_VOL_RATIO    = 1.3   # ratio de volumen mínimo vs media 20d
MIN_RR           = 1.5   # risk:reward mínimo
COOLDOWN_HOURS   = 4     # horas entre alertas del mismo ticker
STOP_BUFFER_PCT  = 1.5   # stop = soporte - 1.5%


def _is_market_open() -> bool:
    """Lunes-Viernes 9:30-16:00 ET."""
    et = datetime.now(timezone(timedelta(hours=-4)))
    t  = et.hour + et.minute / 60
    return et.weekday() < 5 and 9.5 <= t <= 16.0


def _load_alert_log() -> dict:
    if ALERT_LOG.exists():
        try:
            return json.loads(ALERT_LOG.read_text())
        except Exception:
            pass
    return {}


def _save_alert_log(log: dict):
    ALERT_LOG.write_text(json.dumps(log, indent=2, default=str))


def _was_recently_alerted(log: dict, ticker: str) -> bool:
    if ticker not in log:
        return False
    try:
        last = datetime.fromisoformat(log[ticker])
        return (datetime.utcnow() - last).total_seconds() < COOLDOWN_HOURS * 3600
    except Exception:
        return False


def _rsi(closes: pd.Series, period: int = 14) -> float:
    delta    = closes.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    rsi_s    = 100 - (100 / (1 + rs))
    return float(rsi_s.iloc[-1]) if len(rsi_s) else 50.0


def _analyze_ticker(ticker: str) -> dict | None:
    """Descarga datos y calcula métricas de rebote. Devuelve dict o None."""
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period="60d", interval="1d", auto_adjust=True)
        if len(hist) < 22:
            return None

        closes  = hist["Close"]
        volumes = hist["Volume"]

        prev_close  = float(closes.iloc[-2])
        current     = float(closes.iloc[-1])

        # Filtros básicos de liquidez y tamaño
        avg_vol_raw = float(volumes.iloc[-21:-1].mean())
        if current < 2.0 or (avg_vol_raw * current) < 1_000_000:
            return None  # precio < $2 o vol en dólares < $1M/día
        try:
            import yfinance as yf
            mc = float(yf.Ticker(ticker).fast_info.get('marketCap') or 0)
            if 0 < mc < 300_000_000:
                return None  # micro-cap <$300M
        except Exception:
            pass

        rsi_val     = _rsi(closes)
        # Soporte: mínimo de los 20 días ANTERIORES a la caída reciente (no tautología)
        # closes[-41:-21] = días 40d atrás hasta 20d atrás = suelo establecido antes del decline
        if len(closes) >= 41:
            support_20d = float(closes.iloc[-41:-21].min())
        else:
            support_20d = float(closes.iloc[:-20].min()) if len(closes) > 20 else float(closes.min())
        resist_10d  = float(closes.iloc[-11:-1].max())   # máximo de los 10 días anteriores
        avg_vol_20d = avg_vol_raw
        today_vol   = float(volumes.iloc[-1])
        vol_ratio   = today_vol / avg_vol_20d if avg_vol_20d > 0 else 1.0

        drop_pct      = (current - prev_close) / prev_close * 100
        dist_support  = (current - support_20d) / support_20d * 100

        # Target: resistencia de 10d si está por encima, si no +4% por defecto
        target = resist_10d if resist_10d > current * 1.01 else current * 1.04
        stop   = support_20d * (1 - STOP_BUFFER_PCT / 100)

        upside = (target - current) / current * 100
        risk   = (current - stop)  / current * 100
        rr     = upside / risk if risk > 0 else 0.0

        return {
            "ticker":       ticker,
            "current":      current,
            "prev_close":   prev_close,
            "drop_pct":     drop_pct,
            "rsi":          rsi_val,
            "support":      support_20d,
            "dist_support": dist_support,
            "vol_ratio":    vol_ratio,
            "target":       target,
            "stop":         stop,
            "upside_pct":   upside,
            "rr":           rr,
        }
    except Exception as e:
        print(f"  [{ticker}] error: {e}")
        return None


def _qualifies(m: dict) -> bool:
    return (
        m["drop_pct"]     <= MIN_DROP_PCT
        and m["rsi"]      <  MAX_RSI
        # Precio cerca del soporte previo: dentro del 5% por encima, o máx 3% por debajo
        and -3.0 <= m["dist_support"] <= MAX_SUPPORT_DIST
        and m["vol_ratio"] >= MIN_VOL_RATIO
        and m["rr"]        >= MIN_RR
    )


def _format_alert(m: dict, company: str) -> str:
    et       = datetime.now(timezone(timedelta(hours=-4)))
    time_str = et.strftime("%H:%M ET")
    name_str = f" — {company}" if company and company != m["ticker"] else ""

    return (
        f"⚡ <b>Rebote Detectado</b>  {time_str}\n"
        f"📉 <b>{m['ticker']}</b>{name_str}  "
        f"{m['drop_pct']:+.1f}% hoy  |  RSI {m['rsi']:.0f}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"💰 Entrada:  <b>${m['current']:.2f}</b>\n"
        f"🎯 Target:   ${m['target']:.2f}  (<b>+{m['upside_pct']:.1f}%</b>)\n"
        f"🛑 Stop:     ${m['stop']:.2f}  (R:R {m['rr']:.1f}x)\n"
        f"📊 Vol {m['vol_ratio']:.1f}x media  |  Soporte ${m['support']:.2f}"
    )


def _send_telegram(text: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        print("Sin credenciales Telegram — solo imprimiendo:\n")
        print(text)
        return True
    url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(url, data={
        "chat_id":                  CHAT_ID,
        "text":                     text,
        "parse_mode":               "HTML",
        "disable_web_page_preview": "true",
    }, timeout=15)
    if not resp.ok:
        print(f"Telegram error: {resp.status_code} {resp.text}")
    return resp.ok


def _load_tickers() -> list[tuple[str, str]]:
    """Carga (ticker, company_name) de los CSVs de convicción."""
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for csv_path in [CONV_US, CONV_EU]:
        if not csv_path.exists():
            print(f"  Aviso: {csv_path.name} no encontrado, saltando.")
            continue
        try:
            df = pd.read_csv(csv_path)
            for _, row in df.iterrows():
                t = str(row.get("ticker", "")).strip().upper()
                n = str(row.get("company_name", "")).strip()
                if t and t not in seen:
                    seen.add(t)
                    pairs.append((t, n))
        except Exception as e:
            print(f"  Error leyendo {csv_path.name}: {e}")
    return pairs


def main():
    if not _is_market_open():
        print("Mercado cerrado — nada que hacer.")
        sys.exit(2)

    tickers = _load_tickers()
    if not tickers:
        print("No se encontraron tickers en los CSVs de convicción.")
        sys.exit(2)

    print(f"Escaneando {len(tickers)} tickers...")
    alert_log    = _load_alert_log()
    alerts_sent  = 0

    for ticker, company in tickers:
        if _was_recently_alerted(alert_log, ticker):
            print(f"  [{ticker}] omitido (alerta reciente < {COOLDOWN_HOURS}h)")
            continue

        m = _analyze_ticker(ticker)
        if m is None:
            continue

        print(
            f"  [{ticker}] caída={m['drop_pct']:+.1f}%  RSI={m['rsi']:.0f}"
            f"  soporte_dist={m['dist_support']:.1f}%  vol={m['vol_ratio']:.1f}x"
            f"  R:R={m['rr']:.1f}"
        )

        if not _qualifies(m):
            continue

        print(f"  ✅ {ticker} CALIFICA — enviando alerta")
        msg = _format_alert(m, company)
        if _send_telegram(msg):
            alert_log[ticker] = datetime.utcnow().isoformat()
            alerts_sent += 1

    _save_alert_log(alert_log)

    if alerts_sent > 0:
        print(f"\n{alerts_sent} alerta(s) enviada(s).")
        sys.exit(0)
    else:
        print("\nNingún setup de rebote encontrado.")
        sys.exit(2)


if __name__ == "__main__":
    main()
