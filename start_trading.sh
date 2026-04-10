#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  START TRADING — Lanzador del Bounce Trader / Trading Agent
#
#  Modos disponibles:
#    ./start_trading.sh                    # bounce_trader paper, auto
#    ./start_trading.sh --confirm          # bounce_trader + confirmación Telegram
#    ./start_trading.sh --live             # bounce_trader real (confirmación requerida)
#    ./start_trading.sh --status           # ver posiciones abiertas
#
#    ./start_trading.sh --agent            # Trading Agent (multi-señal + Groq) paper
#    ./start_trading.sh --agent --live     # Trading Agent en live
#    ./start_trading.sh --agent --dry-run  # Trading Agent simulado
# ─────────────────────────────────────────────────────────────

set -e
cd "$(dirname "$0")"

# Credenciales Telegram (editar aquí o exportar en ~/.zshrc)
export TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-7662243037:AAExBqSLxv0QuLRxTYZR_JpxgGbKIpVhZFQ}"
export TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-3165866}"

# Activar virtualenv si existe
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║         BOUNCE TRADER — Stock Analyzer       ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Verificar que Python y dependencias están disponibles
python3 -c "import yfinance, ib_insync, pandas, numpy" 2>/dev/null || {
    echo "❌ Faltan dependencias. Ejecuta: pip install yfinance ib_insync pandas numpy"
    exit 1
}

# Pasar todos los argumentos al script Python
if [[ "$1" == "--status" ]]; then
    python3 bounce_trader.py --status
elif [[ "$1" == "--agent" ]]; then
    shift  # eliminar --agent del arglist
    python3 trading_agent.py --loop "$@"
else
    python3 bounce_trader.py --loop "$@"
fi
