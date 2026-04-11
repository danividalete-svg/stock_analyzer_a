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
PROPOSALS_PATH    = Path('docs/agent_proposals.json')

GROQ_MODEL = 'meta-llama/llama-4-scout-17b-16e-instruct'

# ─── Archivos candidatos a análisis de código ─────────────────────────────────
# El agente rota por estos archivos en cada ejecución de --code-review
CODE_FILES_FRONTEND = [
    'frontend/src/pages/ValueUS.tsx',
    'frontend/src/pages/ValueEU.tsx',
    'frontend/src/pages/Dashboard.tsx',
    'frontend/src/pages/MeanReversion.tsx',
    'frontend/src/pages/Portfolio.tsx',
    'frontend/src/pages/Cerebro.tsx',
    'frontend/src/pages/MacroRadar.tsx',
    'frontend/src/pages/BounceTrader.tsx',
    'frontend/src/pages/TickerSearch.tsx',
    'frontend/src/pages/Insiders.tsx',
    'frontend/src/pages/DividendTraps.tsx',
    'frontend/src/pages/Shorts.tsx',
    'frontend/src/components/CerebroBadges.tsx',
    'frontend/src/hooks/useCerebroSignals.ts',
    'frontend/src/api/client.ts',
]

CODE_FILES_BACKEND = [
    'super_score_integrator.py',
    'mean_reversion_detector.py',
    'fundamental_scorer.py',
    'ticker_api.py',
    'intraday_bounce_scanner.py',
    'unusual_flow_scanner.py',
]

CODE_REVIEW_PROMPT = """Eres un senior software engineer revisando una app de análisis de bolsa (React + TypeScript + Python Flask).

Analiza este archivo y encuentra UNA mejora concreta y aplicable:
- Bug real que pueda causar crash o datos incorrectos
- Problema de rendimiento (re-renders innecesarios, cálculos sin memoizar)
- Mejora de UX clara y pequeña
- Código muerto o incorrecto

REGLAS CRÍTICAS:
1. La mejora debe ser PEQUEÑA (máx 20 líneas cambiadas en total)
2. `old_string` debe ser texto que exista LITERALMENTE en el archivo (cópialo exacto)
3. No inventes funcionalidades ni datos
4. Si el archivo está bien, responde con action: "none"
5. Para Python: respetar que dividendYield ya viene en %, no decimal; 50.0 = dato ausente
6. Para React: seguir los patrones del archivo (useMemo, null guards con ??)

Archivo: {filename}
Contenido:
---
{content}
---

Responde SOLO con JSON válido (sin markdown):
{{
  "action": "improve" | "none",
  "title": "Título corto (máx 60 chars)",
  "description": "Qué problema resuelve y por qué (2-3 frases)",
  "impact": "high" | "medium" | "low",
  "type": "frontend" | "backend",
  "changes": [
    {{
      "file": "ruta/exacta/del/archivo",
      "old_string": "código exacto a reemplazar (COPIADO LITERALMENTE del archivo)",
      "new_string": "código nuevo"
    }}
  ]
}}"""

# Parámetros que el agente puede ajustar (con rangos seguros)
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


# ─── Proposals (code review) ─────────────────────────────────────────────────

def _load_proposals() -> list:
    if PROPOSALS_PATH.exists():
        try:
            return json.loads(PROPOSALS_PATH.read_text())
        except Exception:
            pass
    return []


def _save_proposals(proposals: list):
    PROPOSALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROPOSALS_PATH.write_text(json.dumps(proposals, indent=2, ensure_ascii=False))


def _make_prop_id(title: str) -> str:
    import hashlib
    return 'prop_' + hashlib.md5(f'{title}{time.time()}'.encode()).hexdigest()[:8]


# ─── Code Analysis (Groq) ────────────────────────────────────────────────────

def analyze_file_with_ai(filepath: str) -> Optional[dict]:
    """Analiza un archivo con Groq/LLM y devuelve propuesta de mejora."""
    if not GROQ_API_KEY:
        return None

    raw_path = f'{GITHUB_PAGES_BASE}/{filepath}'
    try:
        r = requests.get(raw_path, timeout=15)
        if r.status_code != 200:
            # Try reading locally
            local = Path(filepath)
            if local.exists():
                content = local.read_text(encoding='utf-8')
            else:
                print(f'  ⚠ No se pudo obtener {filepath}')
                return None
        else:
            content = r.text
    except Exception as e:
        print(f'  ⚠ Error leyendo {filepath}: {e}')
        return None

    # Truncar para que quepa en contexto
    if len(content) > 9000:
        content = content[:9000] + '\n... [truncado]'

    prompt = CODE_REVIEW_PROMPT.format(filename=filepath, content=content)

    try:
        resp = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {GROQ_API_KEY}', 'Content-Type': 'application/json'},
            json={
                'model': GROQ_MODEL,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.15,
                'max_tokens': 1200,
                'response_format': {'type': 'json_object'},
            },
            timeout=45,
        )
        resp.raise_for_status()
        data = json.loads(resp.json()['choices'][0]['message']['content'])
        return data
    except Exception as e:
        print(f'  ⚠ Groq error para {filepath}: {e}')
        return None


def validate_proposal(prop: dict, filepath: str) -> bool:
    """Verifica que el old_string exista realmente en el archivo."""
    for ch in prop.get('changes', []):
        target = Path(ch.get('file', filepath))
        if not target.exists():
            return False
        if ch.get('old_string', '') not in target.read_text(encoding='utf-8'):
            return False
    return bool(prop.get('changes'))


def _send_code_proposal(prop: dict) -> Optional[int]:
    """Envía propuesta de código a Telegram con botones. Devuelve message_id."""
    impact_e = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(prop['impact'], '⚪')
    type_e   = '⚛️' if prop['type'] == 'frontend' else '🐍'
    files    = '\n'.join(f"  • <code>{c['file']}</code>" for c in prop['changes'])

    text = (
        f"🤖 <b>Mejora de código propuesta</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{impact_e} Impacto: <b>{prop['impact'].upper()}</b>  {type_e} {prop['type'].upper()}\n\n"
        f"<b>{prop['title']}</b>\n\n"
        f"{prop['description']}\n\n"
        f"📁 Archivos:\n{files}\n\n"
        f"<i>ID: <code>{prop['id']}</code></i>\n"
        f"<i>Responde cuando puedas — sin límite de tiempo</i>"
    )
    keyboard = {'inline_keyboard': [[
        {'text': '✅ Aplicar',   'callback_data': f"agent_approve_{prop['id']}"},
        {'text': '👁 Ver diff',  'callback_data': f"agent_diff_{prop['id']}"},
        {'text': '❌ Rechazar',  'callback_data': f"agent_reject_{prop['id']}"},
    ]]}

    try:
        r = requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            json={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'HTML',
                  'reply_markup': keyboard, 'disable_web_page_preview': True},
            timeout=10,
        )
        return r.json().get('result', {}).get('message_id')
    except Exception:
        return None


def run_code_review(n_files: int = 2):
    """
    Analiza N archivos con IA, genera propuestas, las envía a Telegram y las persiste.
    El agent_monitor.py se encarga de la aprobación (sin timeout).
    """
    import random

    proposals = _load_proposals()
    recently_analyzed = {p.get('source_file') for p in proposals
                         if p.get('status') in ('pending', 'applied', 'deploying')}

    all_files = CODE_FILES_FRONTEND + CODE_FILES_BACKEND
    candidates = [f for f in all_files if f not in recently_analyzed]
    if not candidates:
        candidates = all_files  # reiniciar rotación

    to_analyze = random.sample(candidates, min(n_files, len(candidates)))
    new_count = 0

    for filepath in to_analyze:
        print(f'  🔍 Analizando {filepath}...')
        result = analyze_file_with_ai(filepath)

        if not result or result.get('action') != 'improve':
            print('     → Sin mejoras detectadas')
            continue

        if not validate_proposal(result, filepath):
            print('     → old_string no encontrado — descartando')
            continue

        prop = {
            'id':         _make_prop_id(result['title']),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'source_file': filepath,
            'type':        result.get('type', 'backend'),
            'title':       result.get('title', 'Mejora sin título')[:80],
            'description': result.get('description', ''),
            'impact':      result.get('impact', 'medium'),
            'changes':     result.get('changes', []),
            'status':      'pending',
            'telegram_message_id': None,
        }

        msg_id = _send_code_proposal(prop)
        prop['telegram_message_id'] = msg_id
        proposals.append(prop)
        _save_proposals(proposals)
        new_count += 1
        print(f'     ✅ Propuesta enviada: {prop["title"]} (msg {msg_id})')
        time.sleep(3)

    print(f'\n  📬 {new_count} propuesta(s) nueva(s) enviadas a Telegram')
    return new_count


# ─── Monitor ──────────────────────────────────────────────────────────────────

def _fetch_json(path: str) -> Optional[dict]:
    """Descarga JSON desde GitHub Pages (siempre actualizado)."""
    url = f'{GITHUB_PAGES_BASE}/docs/{path}'
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _fetch_csv_lines(path: str) -> list[str]:
    """Descarga CSV desde GitHub Pages y devuelve líneas."""
    url = f'{GITHUB_PAGES_BASE}/docs/{path}'
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

ANALYST_SYSTEM = """Eres un analista técnico experto en sistemas de trading algorítmico.
Analizas métricas de un scanner de rebotes técnicos (mean reversion) y propones ajustes
específicos y conservadores a sus parámetros.

REGLAS DE ORO:
1. Solo propones cambios si hay un problema claro y concreto
2. Los cambios son SIEMPRE conservadores: máximo ±3 unidades por ajuste
3. Nunca relajas filtros en mercados bajistas (SPY bajo MA200) o VIX > 30
4. Si el sistema detecta 0-2 setups con VIX bajo y mercado alcista → posiblemente filtros demasiado estrictos
5. Si detecta >15 setups con VIX alto → filtros demasiado laxos
6. Si la tasa de acierto 7d cae por debajo del 40% → endurecer filtros
7. Si todo está bien → responde con action: "none"

PARÁMETROS AJUSTABLES:
- RSI_DAILY_MAX: RSI máximo para "oversold" (actual 30, rango 25-35)
- CONFIDENCE_MIN: confianza mínima frontend (actual 40%, rango 30-55%)
- VIX_VETO: VIX que veta todos los setups (actual 35, rango 28-45)
- CUM_RSI2_MAX: CumRSI2 para señal Connors (actual 35, rango 20-50)
- SUPPORT_VETO_PCT: distancia bajo soporte para veto (actual -5%, rango -8 a -3%)

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


def groq_analyze(metrics: dict) -> Optional[dict]:
    """Usa Groq LLM para analizar métricas y proponer ajuste."""
    if not GROQ_API_KEY:
        print('[agent] GROQ_API_KEY no configurado — skipping analysis')
        return None

    metrics_str = json.dumps(metrics, indent=2, ensure_ascii=False)
    prompt = ANALYST_PROMPT.format(metrics=metrics_str)

    try:
        r = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {GROQ_API_KEY}', 'Content-Type': 'application/json'},
            json={
                'model': GROQ_MODEL,
                'messages': [
                    {'role': 'system', 'content': ANALYST_SYSTEM},
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


def telegram_propose(proposal: dict, metrics: dict) -> bool:
    """
    Envía propuesta a Telegram con botones Aplicar/Ignorar.
    Espera CONFIRM_TIMEOUT segundos. Returns True si aprobado.
    """
    param     = proposal.get('param', '?')
    cur_val   = proposal.get('current_value', '?')
    new_val   = proposal.get('proposed_value', '?')
    issue     = proposal.get('issue', '')
    reasoning = proposal.get('reasoning', '')
    risks     = proposal.get('risks', '')
    conf      = int(proposal.get('confidence', 0) * 100)

    info = metrics
    text = (
        f"🤖 <b>Agent Orchestrator — Propuesta de mejora</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Estado actual:</b>\n"
        f"   VIX: {info.get('vix', '?')} | Régimen: {info.get('market_regime', '?')}\n"
        f"   Setups detectados: {info.get('bounce_total_detected', 0)} → pasan filtros: {info.get('bounce_passing_filters', 0)}\n"
        f"   Win rate 7d: {info.get('portfolio_win_rate_7d', 'N/A')}\n"
        f"\n"
        f"⚠️ <b>Problema:</b> {issue}\n"
        f"\n"
        f"🔧 <b>Ajuste propuesto:</b>\n"
        f"   Parámetro: <code>{param}</code>\n"
        f"   Valor actual: <b>{cur_val}</b> → Nuevo: <b>{new_val}</b>\n"
        f"\n"
        f"💡 <b>Razonamiento:</b> {reasoning}\n"
        f"\n"
        f"⚡ <b>Riesgos:</b> {risks}\n"
        f"🎯 Confianza del análisis: {conf}%\n"
        f"\n"
        f"<i>Responde cuando puedas — sin límite de tiempo</i>"
    )

    keyboard = {'inline_keyboard': [[
        {'text': '✅ Aplicar',  'callback_data': f'approve_{param}'},
        {'text': '❌ Ignorar', 'callback_data': f'reject_{param}'},
        {'text': '🔍 Ver métricas', 'callback_data': 'metrics'},
    ]]}

    msg_id = _tg_send(text, keyboard)
    if msg_id is None:
        # Sin Telegram → auto-rechazar en producción para evitar cambios no supervisados
        print('[agent] Sin Telegram — propuesta rechazada automáticamente (sin supervisión)')
        return False

    # Limpiar webhook
    try:
        requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook',
                      json={'drop_pending_updates': False}, timeout=5)
    except Exception:
        pass

    # Offset inicial
    try:
        upd = requests.get(
            f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates',
            params={'limit': 1, 'allowed_updates': ['callback_query']}, timeout=10,
        ).json()
        offset = (upd['result'][-1]['update_id'] + 1) if upd.get('result') else 0
    except Exception:
        offset = 0

    approved = False
    decided  = False
    metrics_requested = False

    while not decided:
        poll_secs = 30
        try:
            upd = requests.get(
                f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates',
                params={'timeout': poll_secs, 'offset': offset,
                        'allowed_updates': ['callback_query']},
                timeout=poll_secs + 5,
            ).json()
            for update in upd.get('result', []):
                offset = update['update_id'] + 1
                cq = update.get('callback_query')
                if not cq:
                    continue
                data = cq.get('data', '')

                if data == f'approve_{param}':
                    approved, decided = True, True
                elif data == f'reject_{param}':
                    approved, decided = False, True
                elif data == 'metrics' and not metrics_requested:
                    metrics_requested = True
                    _tg_send(
                        f"📊 <b>Métricas completas:</b>\n<pre>{json.dumps(metrics, indent=2, ensure_ascii=False)}</pre>",
                    )

                if decided:
                    cb_text = '✅ Aplicando cambio...' if approved else '❌ Propuesta rechazada'
                    try:
                        requests.post(
                            f'https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery',
                            json={'callback_query_id': cq['id'], 'text': cb_text},
                            timeout=5,
                        )
                    except Exception:
                        pass
                    break
        except Exception:
            time.sleep(5)

    final = f"{'✅ APLICADO' if approved else '❌ IGNORADO'} — <b>{param}</b>: {cur_val} → {new_val}"
    _tg_edit(msg_id, final)

    return approved


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

def main():
    parser = argparse.ArgumentParser(description='Agent Orchestrator')
    parser.add_argument('--status',       action='store_true', help='Solo métricas')
    parser.add_argument('--force',        action='store_true', help='Forzar análisis aunque no haya issue')
    parser.add_argument('--dry-run',      action='store_true', help='Sin cambios reales')
    parser.add_argument('--code-review',  action='store_true', help='Analiza archivos de código con IA y propone mejoras')
    parser.add_argument('--n-files',      type=int, default=2, help='Nº de archivos a analizar en --code-review (default: 2)')
    args = parser.parse_args()

    print(f'\n{"="*60}')
    print(f'🤖 AGENT ORCHESTRATOR — {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print(f'{"="*60}')

    # ── Code review mode ──────────────────────────────────────────────────────
    if args.code_review:
        print(f'\n🔍 Modo --code-review: analizando {args.n_files} archivo(s)...')
        if args.dry_run:
            print('   [dry-run] No se enviarán propuestas')
        else:
            run_code_review(n_files=args.n_files)
        return

    # 1. Monitor
    print('\n📊 [1/3] Recopilando métricas...')
    metrics = gather_metrics()
    print(f'   VIX: {metrics.get("vix")} | Régimen: {metrics.get("market_regime")}')
    print(f'   Setups detectados: {metrics.get("bounce_total_detected")} → pasan filtros: {metrics.get("bounce_passing_filters")}')
    print(f'   Win rate 7d: {metrics.get("portfolio_win_rate_7d")}')
    scan_age = metrics.get('scan_age_hours')
    if scan_age is not None:
        print(f'   Scan age: {scan_age:.1f}h')

    if args.status:
        print('\n✅ Modo --status: solo métricas. Done.')
        return

    # 2. Analista
    print('\n🧠 [2/3] Analizando con Groq...')
    proposal = groq_analyze(metrics)

    if proposal is None:
        print('   Sin propuesta (Groq no disponible o sin API key)')
        _log_entry({'ts': metrics['timestamp'], 'action': 'no_groq', 'metrics': metrics})
        return

    print(f'   Acción: {proposal.get("action")}')
    if proposal.get('action') == 'none' and not args.force:
        print('   Sistema OK — sin cambios necesarios')
        _log_entry({'ts': metrics['timestamp'], 'action': 'none', 'metrics': metrics, 'proposal': proposal})
        return

    if proposal.get('action') != 'adjust':
        print(f'   Acción desconocida: {proposal.get("action")}')
        return

    conf = proposal.get('confidence', 0)
    if conf < 0.6 and not args.force:
        print(f'   Confianza baja ({conf:.0%}) — descartando propuesta')
        _log_entry({'ts': metrics['timestamp'], 'action': 'low_confidence', 'metrics': metrics, 'proposal': proposal})
        return

    print(f'   Propuesta: {proposal.get("param")} {proposal.get("current_value")} → {proposal.get("proposed_value")} (conf: {conf:.0%})')
    print(f'   Issue: {proposal.get("issue")}')

    # 3. Telegram
    print('\n📱 [3/3] Enviando propuesta a Telegram...')
    if args.dry_run:
        print('   [dry-run] No se enviará nada')
        print(f'   Propuesta: {json.dumps(proposal, indent=2, ensure_ascii=False)}')
        return

    approved = telegram_propose(proposal, metrics)

    # Log
    _log_entry({
        'ts': metrics['timestamp'],
        'action': 'proposed',
        'approved': approved,
        'metrics': metrics,
        'proposal': proposal,
    })

    if not approved:
        print('\n❌ Propuesta rechazada o sin respuesta. Sin cambios.')
        return

    # 4. Ejecutar
    print('\n🔧 Aplicando cambio...')
    if not GITHUB_TOKEN:
        print('   GITHUB_TOKEN no configurado — no se puede aplicar')
        _tg_send('⚠️ <b>Agent:</b> Falta GITHUB_TOKEN para aplicar el cambio. Configúralo en Railway.')
        return

    success = apply_param_change(proposal)

    if success:
        msg = (
            f"✅ <b>Cambio aplicado:</b>\n"
            f"   {proposal.get('param')}: {proposal.get('current_value')} → {proposal.get('proposed_value')}\n"
            f"   El pipeline se ejecutará en ~5 minutos vía GitHub Actions."
        )
    else:
        msg = (
            f"❌ <b>Error aplicando cambio:</b>\n"
            f"   {proposal.get('param')}: {proposal.get('current_value')} → {proposal.get('proposed_value')}\n"
            f"   Revisar logs en Railway."
        )
    _tg_send(msg)
    print(f'\n{"="*60}')
    print('✅ Agent Orchestrator completado')
    print(f'{"="*60}\n')


if __name__ == '__main__':
    main()
