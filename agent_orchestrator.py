#!/usr/bin/env python3
"""
AGENT ORCHESTRATOR — Agente autónomo desarrollador de Stock Analyzer
Nivel 2: Monitor + Analista + Ejecutor con aprobación humana vía Telegram

Flujo cada ejecución (cron Railway cada 6h):
  1. Monitor: recoge métricas del sistema (señales, calidad, pipeline)
  2. Analista (Groq): razona sobre el estado, propone mejoras específicas
  3. Telegram: envía propuesta con botones Aplicar/Ignorar
  4. Ejecutor: si aprueba → aplica cambio vía GitHub API + dispara Actions

Variables de entorno requeridas:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  GROQ_API_KEY
  GITHUB_TOKEN, GITHUB_REPO (ej. "tantancansado/stock_analyzer_a")

Uso:
  python3 agent_orchestrator.py            # análisis + propuesta
  python3 agent_orchestrator.py --status   # solo métricas, sin propuesta
  python3 agent_orchestrator.py --force    # fuerza análisis aunque no haya issue

Railway cron: "0 8,14,20,2 * * *" (cada 6h)
"""

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

# ─── Configuración ────────────────────────────────────────────────────────────
BOT_TOKEN   = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID     = os.environ.get('TELEGRAM_CHAT_ID', '')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO  = os.environ.get('GITHUB_REPO', 'tantancansado/stock_analyzer_a')

GITHUB_PAGES_BASE = f'https://raw.githubusercontent.com/{GITHUB_REPO}/main'
GITHUB_API_BASE   = 'https://api.github.com'
CONFIRM_TIMEOUT   = None   # None = sin timeout (agent_monitor.py se encarga)
LOG_PATH          = Path('docs/agent_orchestrator_log.json')

GROQ_MODEL = 'meta-llama/llama-4-scout-17b-16e-instruct'

# Parámetros que el agente puede ajustar (con rangos seguros)
# NOTA: 'current' es solo el valor por defecto — siempre se lee del archivo real
ADJUSTABLE_PARAMS = {
    'RSI_DAILY_MAX': {
        'file': 'mean_reversion_detector.py',
        'description': 'RSI diario máximo para Oversold Bounce',
        'pattern_prefix': 'rsi < ',
        'current': 30,
        'min': 25, 'max': 35,
        'unit': 'puntos RSI',
    },
    'CONFIDENCE_MIN': {
        'file': 'frontend/src/pages/BounceTrader.tsx',
        'description': 'Confianza mínima para mostrar setup en frontend',
        'pattern_prefix': '(s.bounce_confidence ?? 0) < ',
        'current': 40,
        'min': 30, 'max': 55,
        'unit': '%',
    },
    'VIX_VETO': {
        'file': 'mean_reversion_detector.py',
        'description': 'VIX máximo antes de vetar todos los setups',
        'pattern_prefix': 'vix_now > ',
        'current': 35,
        'min': 28, 'max': 45,
        'unit': 'puntos VIX',
    },
    'CUM_RSI2_MAX': {
        'file': 'mean_reversion_detector.py',
        'description': 'CumRSI(2) máximo para señal Connors',
        'pattern_prefix': 'cum_rsi2 < ',
        'current': 35,
        'min': 20, 'max': 50,
        'unit': 'puntos RSI acumulado',
    },
    'SUPPORT_VETO_PCT': {
        'file': 'mean_reversion_detector.py',
        'description': 'Distancia máxima al soporte (negativo = por debajo)',
        'pattern_prefix': 'distance_to_support < ',
        'current': -5,
        'min': -8, 'max': -3,
        'unit': '% bajo soporte',
    },
}


def _read_actual_values() -> dict:
    """
    Lee los valores actuales de los archivos reales vía GitHub API.
    Evita proponer cambios que ya están aplicados.
    """
    import re
    actual = {}
    for param, cfg in ADJUSTABLE_PARAMS.items():
        content, _ = _gh_get_file(cfg['file'])
        if content is None:
            actual[param] = cfg['current']
            continue
        prefix = re.escape(cfg['pattern_prefix'])
        match = re.search(prefix + r'(-?\d+(?:\.\d+)?)', content)
        if match:
            try:
                val = float(match.group(1))
                actual[param] = int(val) if val == int(val) else val
            except ValueError:
                actual[param] = cfg['current']
        else:
            actual[param] = cfg['current']
    return actual


# ─── Monitor ──────────────────────────────────────────────────────────────────

def _fetch_json(path: str) -> Optional[dict]:
    """Descarga JSON desde GitHub Pages (siempre actualizado)."""
    url = f'{GITHUB_PAGES_BASE}/{path}'
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _fetch_csv_lines(path: str) -> list[str]:
    """Descarga CSV desde GitHub Pages y devuelve líneas."""
    url = f'{GITHUB_PAGES_BASE}/{path}'
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return r.text.strip().split('\n')
    except Exception:
        pass
    return []


def gather_metrics() -> dict:
    """Recoge métricas clave del sistema."""
    now = datetime.now(timezone.utc)

    # ── Mean reversion opportunities ──────────────────────────────────────────
    mr = _fetch_json('mean_reversion_opportunities.json')
    bounce_total = 0
    bounce_passing = 0
    bounce_tiers = {'tier1': 0, 'tier2': 0}
    scan_age_hours = None
    vix = None

    if mr:
        scan_date_str = mr.get('scan_date', '')
        if scan_date_str:
            try:
                scan_dt = datetime.fromisoformat(scan_date_str.replace('Z', '+00:00'))
                if scan_dt.tzinfo is None:
                    scan_dt = scan_dt.replace(tzinfo=timezone.utc)
                scan_age_hours = (now - scan_dt).total_seconds() / 3600
            except Exception:
                pass

        ops = mr.get('opportunities', [])
        bounce_ops = [o for o in ops if o.get('strategy') == 'Oversold Bounce']
        bounce_total = len(bounce_ops)

        # Simular filtros frontend
        for o in bounce_ops:
            rsi  = o.get('rsi', 0) or 0
            dist = o.get('distance_to_support_pct')
            price = o.get('current_price', 0) or 0
            conf  = o.get('bounce_confidence', 0) or 0
            dp    = o.get('dark_pool_signal', '')
            rr    = o.get('risk_reward', 0) or 0

            fails = (
                rsi >= 30 or rsi == 0 or
                (dist is not None and dist < -5) or
                price < 1.0 or
                conf < 40 or
                (dp == 'DISTRIBUTION' and conf < 60) or
                (rr != 0 and rr < 1.0)
            )
            if not fails:
                bounce_passing += 1
                tier = o.get('conviction_tier', 1)
                if tier == 2:
                    bounce_tiers['tier2'] += 1
                else:
                    bounce_tiers['tier1'] += 1

        # VIX del primer setup
        for o in ops:
            if o.get('vix'):
                vix = o['vix']
                break

    # ── Value opportunities ────────────────────────────────────────────────────
    value_lines = _fetch_csv_lines('value_opportunities_filtered.csv')
    value_count = max(0, len(value_lines) - 1)  # quitar header

    # ── Portfolio tracker ──────────────────────────────────────────────────────
    tracker = _fetch_json('portfolio_tracker/summary.json')
    win_rate = tracker.get('win_rate_7d') if tracker else None
    avg_return = tracker.get('avg_return_7d') if tracker else None

    # ── Market regime ─────────────────────────────────────────────────────────
    mr_regime = mr.get('market_regime') if mr else None
    if not mr_regime:
        ops_list = (mr or {}).get('opportunities', [])
        mr_regime = ops_list[0].get('market_regime') if ops_list else None

    return {
        'timestamp': now.isoformat(),
        'scan_age_hours': scan_age_hours,
        'market_regime': mr_regime,
        'vix': vix,
        'bounce_total_detected': bounce_total,
        'bounce_passing_filters': bounce_passing,
        'bounce_tier1': bounce_tiers['tier1'],
        'bounce_tier2': bounce_tiers['tier2'],
        'value_filtered_count': value_count,
        'portfolio_win_rate_7d': win_rate,
        'portfolio_avg_return_7d': avg_return,
    }


# ─── Analista (Groq) ──────────────────────────────────────────────────────────

ANALYST_SYSTEM_TEMPLATE = """Eres un analista técnico experto en sistemas de trading algorítmico.
Analizas métricas de un scanner de rebotes técnicos (mean reversion) y propones ajustes
específicos y conservadores a sus parámetros.

REGLAS DE ORO — LEER EN ORDEN, LA PRIMERA QUE APLIQUE GANA:
0. Si vix=null/None O market_regime=null/None → los datos del scan no están disponibles.
   En ese caso SIEMPRE responde con action="none". NUNCA propongas cambios sin datos reales.
1. Solo propones cambios si hay un problema claro y concreto
2. Los cambios son SIEMPRE conservadores: máximo ±3 unidades por ajuste
3. Nunca relajas filtros en mercados bajistas (SPY bajo MA200) o VIX > 30
4. Si detectas 0-2 setups Y VIX < 20 Y mercado alcista confirmado (no None) → filtros posiblemente estrictos
5. Si detecta >15 setups con VIX alto → filtros demasiado laxos
6. Si la tasa de acierto 7d cae por debajo del 40% → endurecer filtros
7. Si scan_age_hours > 36 → datos obsoletos, no propongas cambios (action="none")
8. Si todo está bien o no hay suficientes datos → responde con action: "none"

PARÁMETROS AJUSTABLES (valores reales ahora mismo):
{params_summary}

Responde SOLO en JSON sin ningún texto adicional."""

ANALYST_PROMPT = """Métricas del sistema ahora mismo:
{metrics}

Analiza y responde en este JSON exacto:
{{
  "action": "adjust" | "none",
  "issue": "descripción breve del problema (si action=adjust)",
  "param": "nombre del parámetro a ajustar (de ADJUSTABLE_PARAMS)",
  "current_value": número,
  "proposed_value": número,
  "reasoning": "por qué este ajuste mejora el sistema (2-3 frases)",
  "confidence": 0.0-1.0,
  "risks": "riesgos del ajuste"
}}"""


def groq_analyze(metrics: dict, actual_values: dict) -> Optional[dict]:
    """Usa Groq LLM para analizar métricas y proponer ajuste."""
    if not GROQ_API_KEY:
        print('[agent] GROQ_API_KEY no configurado — skipping analysis')
        return None

    # Build dynamic params summary with REAL current values
    params_lines = []
    for param, cfg in ADJUSTABLE_PARAMS.items():
        cur = actual_values.get(param, cfg['current'])
        params_lines.append(
            f"- {param}: {cfg['description']} (actual={cur}, rango {cfg['min']}-{cfg['max']} {cfg['unit']})"
        )
    analyst_system = ANALYST_SYSTEM_TEMPLATE.format(params_summary='\n'.join(params_lines))

    metrics_str = json.dumps(metrics, indent=2, ensure_ascii=False)
    prompt = ANALYST_PROMPT.format(metrics=metrics_str)

    try:
        r = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {GROQ_API_KEY}', 'Content-Type': 'application/json'},
            json={
                'model': GROQ_MODEL,
                'messages': [
                    {'role': 'system', 'content': analyst_system},
                    {'role': 'user',   'content': prompt},
                ],
                'temperature': 0.2,
                'max_tokens': 512,
                'response_format': {'type': 'json_object'},
            },
            timeout=30,
        )
        r.raise_for_status()
        content = r.json()['choices'][0]['message']['content']
        proposal = json.loads(content)

        # Override current_value with the real file value
        param = proposal.get('param')
        if param and param in actual_values:
            proposal['current_value'] = actual_values[param]

        return proposal
    except Exception as e:
        print(f'[agent] Groq error: {e}')
        return None


# ─── Telegram ─────────────────────────────────────────────────────────────────

def _tg_send(text: str, keyboard: Optional[dict] = None) -> Optional[int]:
    """Envía mensaje Telegram, devuelve message_id."""
    if not BOT_TOKEN or not CHAT_ID:
        return None
    payload = {
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True,
    }
    if keyboard:
        payload['reply_markup'] = keyboard
    try:
        r = requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            json=payload, timeout=10,
        )
        return r.json().get('result', {}).get('message_id')
    except Exception:
        return None


def _tg_edit(msg_id: int, text: str):
    if not BOT_TOKEN or not CHAT_ID or not msg_id:
        return
    try:
        requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/editMessageText',
            json={'chat_id': CHAT_ID, 'message_id': msg_id, 'text': text, 'parse_mode': 'HTML'},
            timeout=5,
        )
    except Exception:
        pass


def telegram_propose(proposal: dict, metrics: dict):
    """
    Envía propuesta a Telegram con botones y sale inmediatamente.
    El agente monitor (siempre activo) es el único que maneja el callback
    y aplica el cambio — esto evita la carrera de doble ejecución.
    """
    param     = proposal.get('param', '?')
    cur_val   = proposal.get('current_value', '?')
    new_val   = proposal.get('proposed_value', '?')
    issue     = proposal.get('issue', '')
    reasoning = proposal.get('reasoning', '')
    risks     = proposal.get('risks', '')
    conf      = int(proposal.get('confidence', 0) * 100)

    text = (
        f"🤖 <b>Propuesta de ajuste</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 VIX: {metrics.get('vix', '?')} | Régimen: {metrics.get('market_regime', '?')}\n"
        f"   Setups: {metrics.get('bounce_total_detected', 0)} detectados → "
        f"{metrics.get('bounce_passing_filters', 0)} pasan filtros\n"
        f"   Win rate 7d: {metrics.get('portfolio_win_rate_7d', 'N/A')}\n"
        f"\n"
        f"⚠️ <b>Problema:</b> {issue}\n"
        f"\n"
        f"🔧 <code>{param}</code>: <b>{cur_val}</b> → <b>{new_val}</b>\n"
        f"💡 {reasoning}\n"
        f"⚡ Riesgos: {risks}\n"
        f"🎯 Confianza: {conf}%"
    )

    keyboard = {'inline_keyboard': [[
        {'text': '✅ Aplicar',   'callback_data': f'approve_{param}_{cur_val}_{new_val}'},
        {'text': '❌ Ignorar',  'callback_data': f'reject_{param}'},
    ]]}

    _tg_send(text, keyboard)
    print(f'[agent] Propuesta enviada a Telegram — el monitor aplicará si se aprueba')


# ─── Ejecutor (GitHub API) ────────────────────────────────────────────────────

def _gh_headers() -> dict:
    return {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
    }


def _gh_get_file(path: str) -> Optional[tuple[str, str]]:
    """Devuelve (content_decoded, sha) del archivo en GitHub."""
    url = f'{GITHUB_API_BASE}/repos/{GITHUB_REPO}/contents/{path}'
    try:
        r = requests.get(url, headers=_gh_headers(), timeout=15)
        if r.status_code == 200:
            data = r.json()
            content = base64.b64decode(data['content']).decode('utf-8')
            return content, data['sha']
    except Exception as e:
        print(f'[executor] Error leyendo {path}: {e}')
    return None, None


def _gh_update_file(path: str, content: str, sha: str, message: str) -> bool:
    """Actualiza un archivo en GitHub vía API."""
    url = f'{GITHUB_API_BASE}/repos/{GITHUB_REPO}/contents/{path}'
    encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    try:
        r = requests.put(
            url,
            headers=_gh_headers(),
            json={
                'message': message,
                'content': encoded,
                'sha': sha,
                'committer': {
                    'name': 'Agent Orchestrator',
                    'email': 'agent@stock-analyzer.ai',
                },
            },
            timeout=20,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        print(f'[executor] Error actualizando {path}: {e}')
        return False


def _gh_trigger_workflow(workflow_file: str, ref: str = 'main') -> bool:
    """Dispara un workflow de GitHub Actions (workflow_dispatch)."""
    url = f'{GITHUB_API_BASE}/repos/{GITHUB_REPO}/actions/workflows/{workflow_file}/dispatches'
    try:
        r = requests.post(
            url, headers=_gh_headers(),
            json={'ref': ref}, timeout=15,
        )
        return r.status_code == 204
    except Exception:
        return False


def apply_param_change(proposal: dict) -> bool:
    """
    Aplica el ajuste de parámetro al archivo fuente vía GitHub API.
    Devuelve True si tuvo éxito.
    """
    param = proposal.get('param')
    if param not in ADJUSTABLE_PARAMS:
        print(f'[executor] Parámetro desconocido: {param}')
        return False

    cfg = ADJUSTABLE_PARAMS[param]
    file_path = cfg['file']
    prefix = cfg['pattern_prefix']
    cur_val  = proposal.get('current_value')
    new_val  = proposal.get('proposed_value')

    # Validar rangos
    if new_val < cfg['min'] or new_val > cfg['max']:
        print(f'[executor] Valor {new_val} fuera de rango [{cfg["min"]}, {cfg["max"]}]')
        return False

    # Leer archivo actual
    content, sha = _gh_get_file(file_path)
    if content is None:
        print(f'[executor] No se pudo leer {file_path}')
        return False

    # Hacer el reemplazo (primera ocurrencia del patrón)
    old_str = f'{prefix}{cur_val}'
    new_str = f'{prefix}{new_val}'

    if old_str not in content:
        print(f'[executor] Patrón no encontrado en {file_path}: "{old_str}"')
        return False

    new_content = content.replace(old_str, new_str, 1)

    # Commit message
    commit_msg = (
        f'agent: adjust {param} {cur_val}→{new_val}\n\n'
        f'Issue: {proposal.get("issue", "")}\n'
        f'Reasoning: {proposal.get("reasoning", "")}\n\n'
        f'Auto-applied by Agent Orchestrator with user approval.'
    )

    success = _gh_update_file(file_path, new_content, sha, commit_msg)
    if success:
        print(f'[executor] ✅ {param}: {cur_val} → {new_val} aplicado en {file_path}')
        # Actualizar parámetro en memoria local
        ADJUSTABLE_PARAMS[param]['current'] = new_val

        # Disparar pipeline si es backend
        if 'mean_reversion' in file_path or 'super_score' in file_path:
            _gh_trigger_workflow('intraday-bounce.yml')
            print('[executor] 🚀 Workflow disparado')
    else:
        print('[executor] ❌ Error aplicando cambio en GitHub')

    return success


# ─── Log ──────────────────────────────────────────────────────────────────────

def _log_entry(entry: dict):
    log = []
    if LOG_PATH.exists():
        try:
            log = json.loads(LOG_PATH.read_text())
        except Exception:
            pass
    log.append(entry)
    log = log[-100:]  # máximo 100 entradas
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps(log, indent=2, ensure_ascii=False))


# ─── Main ─────────────────────────────────────────────────────────────────────

def _data_quality_reasons(metrics: dict) -> list[str]:
    """Devuelve lista de razones por las que no se puede analizar. Vacía = OK."""
    reasons = []
    if metrics.get('vix') is None:
        reasons.append('VIX=None')
    if metrics.get('market_regime') is None:
        reasons.append('régimen=None')
    scan_age = metrics.get('scan_age_hours')
    if scan_age is not None and scan_age >= 36:
        reasons.append(f'scan obsoleto ({scan_age:.0f}h)')
    return reasons


def _validate_proposal(proposal: dict, metrics: dict, force: bool) -> bool:
    """Valida propuesta. Devuelve True si debe enviarse a Telegram."""
    action = proposal.get('action')
    if action == 'none':
        if not force:
            print('   Sistema OK — sin cambios necesarios')
            _log_entry({'ts': metrics['timestamp'], 'action': 'none',
                        'metrics': metrics, 'proposal': proposal})
        return force

    if action != 'adjust':
        print(f'   Acción desconocida: {action}')
        return False

    conf = proposal.get('confidence', 0)
    if conf < 0.6 and not force:
        print(f'   Confianza baja ({conf:.0%}) — descartando propuesta')
        _log_entry({'ts': metrics['timestamp'], 'action': 'low_confidence',
                    'metrics': metrics, 'proposal': proposal})
        return False

    return True


def main():
    parser = argparse.ArgumentParser(description='Agent Orchestrator')
    parser.add_argument('--status',  action='store_true', help='Solo métricas')
    parser.add_argument('--force',   action='store_true', help='Forzar análisis aunque no haya issue')
    parser.add_argument('--dry-run', action='store_true', help='Sin cambios reales')
    args = parser.parse_args()

    print(f'\n{"="*60}')
    print(f'🤖 AGENT ORCHESTRATOR — {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print(f'{"="*60}')

    # 1. Monitor
    print('\n📊 [1/3] Recopilando métricas...')
    metrics  = gather_metrics()
    scan_age = metrics.get('scan_age_hours')
    print(f'   VIX: {metrics.get("vix")} | Régimen: {metrics.get("market_regime")}')
    print(f'   Setups: {metrics.get("bounce_total_detected")} → {metrics.get("bounce_passing_filters")} pasan filtros')
    print(f'   Win rate 7d: {metrics.get("portfolio_win_rate_7d")}')
    if scan_age is not None:
        print(f'   Scan age: {scan_age:.1f}h')

    if args.status:
        print('\n✅ Modo --status: solo métricas. Done.')
        return

    # Guard: datos insuficientes
    reasons = _data_quality_reasons(metrics)
    if reasons and not args.force:
        print(f'\n⚠️  Sin datos suficientes ({", ".join(reasons)}) — abortando análisis')
        _log_entry({'ts': metrics['timestamp'], 'action': 'no_data',
                    'reason': reasons, 'metrics': metrics})
        return

    # 1b. Leer valores actuales desde archivos reales
    print('\n🔍 Leyendo valores actuales de archivos...')
    actual_values = _read_actual_values()
    for param, val in actual_values.items():
        ADJUSTABLE_PARAMS[param]['current'] = val
        print(f'   {param}: {val}')

    # 2. Analista
    print('\n🧠 [2/3] Analizando con Groq...')
    proposal = groq_analyze(metrics, actual_values)

    if proposal is None:
        print('   Sin propuesta (Groq no disponible o sin API key)')
        _log_entry({'ts': metrics['timestamp'], 'action': 'no_groq', 'metrics': metrics})
        return

    print(f'   Acción: {proposal.get("action")}')
    if not _validate_proposal(proposal, metrics, args.force):
        return

    conf = proposal.get('confidence', 0)
    print(f'   Propuesta: {proposal.get("param")} {proposal.get("current_value")} → {proposal.get("proposed_value")} (conf: {conf:.0%})')
    print(f'   Issue: {proposal.get("issue")}')

    # 3. Telegram
    print('\n📱 [3/3] Enviando propuesta a Telegram...')
    if args.dry_run:
        print('   [dry-run] No se enviará nada')
        print(f'   Propuesta: {json.dumps(proposal, indent=2, ensure_ascii=False)}')
        return

    telegram_propose(proposal, metrics)
    _log_entry({
        'ts':      metrics['timestamp'],
        'action':  'proposed',
        'param':   proposal.get('param'),
        'cur_val': proposal.get('current_value'),
        'new_val': proposal.get('proposed_value'),
        'metrics': metrics,
    })

    print('\n✅ Propuesta enviada. El monitor aplicará cuando el usuario apruebe.')
    print(f'{"="*60}\n')


if __name__ == '__main__':
    main()
