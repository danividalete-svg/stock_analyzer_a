#!/usr/bin/env python3
"""
Servidor Flask — Owner Earnings API (standalone).

Detecta automáticamente dónde están los datos:
  1. IMPORTANTE/docs/tikr_earnings_data.json  → modo standalone
  2. <repo_raíz>/docs/tikr_earnings_data.json → modo dentro del repo principal

Ejecutar:
    cd IMPORTANTE/          # desde la carpeta standalone
    python3 api_server.py

  — o —

    python3 IMPORTANTE/api_server.py   # desde la raíz del repo

Puerto: 5002 (coincide con el proxy de Vite en frontend/vite.config.ts)

Endpoints:
    GET /api/health
    GET /api/owner-earnings/<ticker>?target_return=0.15
    GET /api/owner-earnings-batch?target_return=0.15
"""

import os
import sys
from pathlib import Path

# ── Resolución de rutas ───────────────────────────────────────────────────────

SCRIPT_DIR = Path(os.path.abspath(__file__)).parent

# Candidatos para tikr_earnings_data.json (en orden de preferencia)
_candidates = [
    SCRIPT_DIR / 'docs' / 'tikr_earnings_data.json',          # standalone
    SCRIPT_DIR.parent / 'docs' / 'tikr_earnings_data.json',   # dentro del repo
]

_base_dir = None
for _c in _candidates:
    if _c.exists():
        _base_dir = _c.parent.parent   # raíz donde está la carpeta docs/
        break

if _base_dir is None:
    print("ERROR: No se encontró docs/tikr_earnings_data.json")
    print("  Ejecuta tikr_scraper.py primero para generar los datos:")
    print(f"    cd {SCRIPT_DIR}")
    print("    python3 tikr_scraper.py --run")
    sys.exit(1)

# Cambiar cwd a la raíz detectada → owner_earnings.py resuelve TIKR_PATH = Path("docs/...")
os.chdir(_base_dir)
sys.path.insert(0, str(_base_dir))      # para importar owner_earnings.py
sys.path.insert(0, str(SCRIPT_DIR))    # también buscar en IMPORTANTE/

print(f"  Datos TIKR: {_base_dir / 'docs' / 'tikr_earnings_data.json'}")

# ── Flask app ─────────────────────────────────────────────────────────────────

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins="*")


@app.route('/api/health')
def health():
    from pathlib import Path
    data_path = Path("docs/tikr_earnings_data.json")
    return jsonify({
        "status": "ok",
        "server": "owner-earnings-standalone",
        "data_file": str(data_path.resolve()),
        "data_exists": data_path.exists(),
    })


@app.route('/api/owner-earnings/<ticker>')
def owner_earnings_endpoint(ticker: str):
    ticker = ticker.upper().strip()
    try:
        target_return = float(request.args.get('target_return', 0.15))
        ev_fcf_target = request.args.get('ev_fcf_target')
        ev_fcf_target = float(ev_fcf_target) if ev_fcf_target else None

        from owner_earnings import calculate
        result = calculate(ticker, target_return=target_return, ev_fcf_target=ev_fcf_target)
        return jsonify(result)
    except Exception as e:
        return jsonify({"ticker": ticker, "error": str(e)}), 500


@app.route('/api/owner-earnings-batch')
def owner_earnings_batch():
    try:
        target_return = float(request.args.get('target_return', 0.15))

        from owner_earnings import batch_calculate
        results = batch_calculate(target_return=target_return)

        sorted_results = sorted(
            [v for v in results.values() if isinstance(v, dict) and v.get('buy_price')],
            key=lambda x: x.get('upside_pct') or -999,
            reverse=True,
        )

        return jsonify({
            "target_return_pct": round(target_return * 100, 1),
            "total": len(sorted_results),
            "results": sorted_results,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    print(f"  Owner Earnings API → http://localhost:{port}")
    print(f"  Frontend dev server → cd frontend && npm run dev")
    app.run(host='0.0.0.0', port=port, debug=False)
