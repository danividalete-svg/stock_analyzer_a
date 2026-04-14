#!/usr/bin/env python3
"""
Servidor Flask mínimo — Owner Earnings endpoints.

Ejecutar SIEMPRE desde la raíz del repositorio:
    python3 IMPORTANTE/api_server.py

Puerto: 5002 (coincide con el proxy de Vite en vite.config.ts)
Endpoints:
    GET /api/owner-earnings/<ticker>?target_return=0.15
    GET /api/owner-earnings-batch?target_return=0.15
    GET /api/health
"""

import sys
import os

# Asegurar que la raíz del repo esté en el path para importar owner_earnings.py
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)  # necesario para que TIKR_PATH = Path("docs/tikr_earnings_data.json") resuelva bien

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins="*")


@app.route('/api/health')
def health():
    return jsonify({"status": "ok", "server": "owner-earnings-minimal"})


@app.route('/api/owner-earnings/<ticker>')
def owner_earnings_endpoint(ticker):
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
    print(f"  Datos TIKR: {os.path.join(ROOT, 'docs', 'tikr_earnings_data.json')}")
    app.run(host='0.0.0.0', port=port, debug=False)
