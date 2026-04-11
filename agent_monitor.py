#!/usr/bin/env python3
"""
AGENT MONITOR — Servicio persistente (Railway)
Monitorea Telegram y aplica propuestas de código aprobadas por el usuario.
Sin timeout: espera la respuesta indefinidamente.

Variables de entorno:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  GITHUB_TOKEN (PAT con permisos repo + workflow)
  GITHUB_REPO  (ej. "tantancansado/stock_analyzer_a")

Ejecutar: python3 agent_monitor.py
"""

import base64
import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

import requests

# ── Config ─────────────────────────────────────────────────────────────────────
BOT_TOKEN    = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID      = os.environ.get('TELEGRAM_CHAT_ID', '')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO  = os.environ.get('GITHUB_REPO', 'tantancansado/stock_analyzer_a')

GITHUB_API         = 'https://api.github.com'
PROPOSALS_PATH     = 'docs/agent_proposals.json'
FRONTEND_WORKFLOW  = 'agent-frontend-deploy.yml'
PROPOSALS_REFRESH  = 120  # segundos entre re-fetch de propuestas

# Params ajustables (para propuestas legadas del orchestrator)
ADJUSTABLE_PARAMS = {
    'RSI_DAILY_MAX':   {'file': 'mean_reversion_detector.py',           'pattern_prefix': 'rsi < ',                              'min': 25, 'max': 35},
    'CONFIDENCE_MIN':  {'file': 'frontend/src/pages/BounceTrader.tsx',  'pattern_prefix': '(s.bounce_confidence ?? 0) < ',       'min': 30, 'max': 55},
    'VIX_VETO':        {'file': 'mean_reversion_detector.py',           'pattern_prefix': 'vix_now > ',                          'min': 28, 'max': 45},
    'CUM_RSI2_MAX':    {'file': 'mean_reversion_detector.py',           'pattern_prefix': 'cum_rsi2 < ',                         'min': 20, 'max': 50},
    'SUPPORT_VETO_PCT':{'file': 'mean_reversion_detector.py',           'pattern_prefix': 'distance_to_support < ',              'min': -8, 'max': -3},
}


# ── GitHub API ─────────────────────────────────────────────────────────────────

def _gh_headers() -> dict:
    return {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
    }


def gh_get_file(path: str) -> tuple[Optional[str], Optional[str]]:
    """Descarga contenido + SHA de un archivo del repo."""
    r = requests.get(f'{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}',
                     headers=_gh_headers(), timeout=15)
    if r.status_code == 200:
        d = r.json()
        return base64.b64decode(d['content']).decode('utf-8'), d['sha']
    return None, None


def gh_update_file(path: str, content: str, sha: str, message: str) -> bool:
    """Actualiza un archivo en el repo vía GitHub API."""
    # Siempre re-fetch el SHA actual para evitar conflictos
    _, current_sha = gh_get_file(path)
    use_sha = current_sha or sha
    r = requests.put(
        f'{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}',
        headers=_gh_headers(),
        json={
            'message': message,
            'content': base64.b64encode(content.encode()).decode(),
            'sha': use_sha,
            'committer': {'name': 'Stock Analyzer Agent 🤖', 'email': 'agent@stock-analyzer.bot'},
        },
        timeout=20,
    )
    return r.status_code in (200, 201)


def gh_trigger_workflow(workflow: str, inputs: dict) -> bool:
    """Dispara un workflow_dispatch en GitHub Actions."""
    r = requests.post(
        f'{GITHUB_API}/repos/{GITHUB_REPO}/actions/workflows/{workflow}/dispatches',
        headers=_gh_headers(),
        json={'ref': 'main', 'inputs': inputs},
        timeout=15,
    )
    return r.status_code == 204


# ── Proposals ──────────────────────────────────────────────────────────────────

class ProposalStore:
    """Cache en memoria de propuestas + sync con GitHub."""

    def __init__(self):
        self._proposals: list[dict] = []
        self._sha: Optional[str] = None
        self._last_fetch = 0.0

    def _fetch(self):
        content, sha = gh_get_file(PROPOSALS_PATH)
        if content:
            try:
                self._proposals = json.loads(content)
                self._sha = sha
            except Exception:
                pass
        self._last_fetch = time.time()

    def get_all(self) -> list[dict]:
        if time.time() - self._last_fetch > PROPOSALS_REFRESH:
            self._fetch()
        return self._proposals

    def get_pending(self) -> list[dict]:
        return [p for p in self.get_all() if p.get('status') == 'pending']

    def find(self, prop_id: str) -> Optional[dict]:
        for p in self.get_all():
            if p.get('id') == prop_id:
                return p
        return None

    def update_status(self, prop_id: str, status: str):
        for p in self._proposals:
            if p.get('id') == prop_id:
                p['status'] = status
                p['updated_at'] = datetime.now(timezone.utc).isoformat()
                break
        self._push(f'agent: {status} proposal {prop_id}')

    def _push(self, message: str):
        content = json.dumps(self._proposals, indent=2, ensure_ascii=False)
        ok = gh_update_file(PROPOSALS_PATH, content, self._sha or '', message)
        if ok:
            # Re-fetch SHA after update
            _, new_sha = gh_get_file(PROPOSALS_PATH)
            if new_sha:
                self._sha = new_sha


# ── Telegram ───────────────────────────────────────────────────────────────────

def tg(method: str, **kwargs) -> dict:
    try:
        r = requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/{method}',
                          json=kwargs, timeout=10)
        return r.json()
    except Exception:
        return {}


def tg_answer(cq_id: str, text: str):
    tg('answerCallbackQuery', callback_query_id=cq_id, text=text)


def tg_send(text: str, **kwargs):
    tg('sendMessage', chat_id=CHAT_ID, text=text, parse_mode='HTML', **kwargs)


def send_diff(prop: dict, cq_id: str):
    tg_answer(cq_id, '👁 Mostrando diff...')
    parts = [f"📋 <b>Diff — {prop['title']}</b>\n"]
    for ch in prop.get('changes', []):
        old_p = ch['old_string'][:400].replace('<', '&lt;').replace('>', '&gt;')
        new_p = ch['new_string'][:400].replace('<', '&lt;').replace('>', '&gt;')
        parts.append(f"\n📄 <code>{ch['file']}</code>\n"
                     f"<pre>--- ANTES\n{old_p}</pre>\n"
                     f"<pre>+++ DESPUÉS\n{new_p}</pre>")
    tg('sendMessage', chat_id=CHAT_ID, text='\n'.join(parts)[:4000], parse_mode='HTML')


# ── Apply changes ──────────────────────────────────────────────────────────────

def apply_code_change(prop: dict) -> bool:
    """Aplica cambios de código vía GitHub API."""
    for ch in prop.get('changes', []):
        content, sha = gh_get_file(ch['file'])
        if content is None:
            print(f'  ❌ No encontrado: {ch["file"]}')
            return False
        if ch['old_string'] not in content:
            print(f'  ❌ old_string no encontrado en {ch["file"]}')
            return False
        new_content = content.replace(ch['old_string'], ch['new_string'], 1)
        if not gh_update_file(ch['file'], new_content, sha, f'🤖 {prop["title"]}'):
            print(f'  ❌ Error actualizando {ch["file"]}')
            return False
        print(f'  ✅ Aplicado en {ch["file"]}')
    return True


def apply_param_change(param: str, cur_val, new_val) -> bool:
    """Aplica ajuste de parámetro (propuestas legadas del orchestrator)."""
    cfg = ADJUSTABLE_PARAMS.get(param)
    if not cfg:
        return False
    content, sha = gh_get_file(cfg['file'])
    if content is None:
        return False
    old_str = f'{cfg["pattern_prefix"]}{cur_val}'
    new_str = f'{cfg["pattern_prefix"]}{new_val}'
    if old_str not in content:
        print(f'  ❌ Patrón no encontrado: "{old_str}"')
        return False
    new_content = content.replace(old_str, new_str, 1)
    return gh_update_file(cfg['file'], new_content, sha,
                          f'agent: adjust {param} {cur_val}→{new_val}')


# ── Main loop ──────────────────────────────────────────────────────────────────

def main():
    print('🤖 Agent Monitor iniciado')
    print(f'   Repo: {GITHUB_REPO}')
    print(f'   Polling Telegram sin timeout...\n')

    store = ProposalStore()

    # Obtener offset inicial (ignorar mensajes viejos)
    offset = 0
    try:
        upd = tg('getUpdates', limit=1)
        if upd.get('result'):
            offset = upd['result'][-1]['update_id'] + 1
    except Exception:
        pass

    # Anuncio de inicio
    tg_send('🤖 <b>Agent Monitor activo</b>\nEsperando propuestas...')

    while True:
        try:
            upd = tg('getUpdates', timeout=30, offset=offset,
                     allowed_updates=['callback_query', 'message'])

            for update in upd.get('result', []):
                offset = update['update_id'] + 1

                # ── Mensajes de texto (comandos) ──────────────────────────────
                msg = update.get('message', {})
                if msg.get('text', '').startswith('/'):
                    handle_command(msg['text'].strip(), store)
                    continue

                # ── Callback queries (botones inline) ─────────────────────────
                cq = update.get('callback_query')
                if not cq:
                    continue

                data   = cq.get('data', '')
                cq_id  = cq['id']

                # Propuestas de código (code review agent)
                if data.startswith('agent_diff_'):
                    prop_id = data[len('agent_diff_'):]
                    prop = store.find(prop_id)
                    if prop:
                        send_diff(prop, cq_id)
                    else:
                        tg_answer(cq_id, '❌ Propuesta no encontrada')

                elif data.startswith('agent_reject_'):
                    prop_id = data[len('agent_reject_'):]
                    prop = store.find(prop_id)
                    if prop and prop.get('status') == 'pending':
                        store.update_status(prop_id, 'rejected')
                        tg_answer(cq_id, '❌ Rechazada')
                        tg_send(f"❌ <b>Rechazado:</b> {prop['title']}")
                    else:
                        tg_answer(cq_id, 'Ya procesada o no encontrada')

                elif data.startswith('agent_approve_'):
                    prop_id = data[len('agent_approve_'):]
                    prop = store.find(prop_id)
                    if not prop or prop.get('status') != 'pending':
                        tg_answer(cq_id, 'Ya procesada o no encontrada')
                        continue

                    tg_answer(cq_id, '⏳ Aplicando...')
                    print(f'\n▶ Aplicando: {prop["title"]}')

                    ok = apply_code_change(prop)
                    if ok:
                        prop_type = prop.get('type', 'backend')
                        if 'frontend' in prop_type:
                            store.update_status(prop_id, 'deploying')
                            build_ok = gh_trigger_workflow(FRONTEND_WORKFLOW, {
                                'description': prop['title'],
                                'chat_id': str(CHAT_ID),
                            })
                            if build_ok:
                                tg_send(f"⚛️ <b>Build iniciado</b>\n{prop['title']}\n\n⏳ ~3 min para deploy completo...")
                                print('  🚀 Build workflow triggered')
                            else:
                                tg_send(f"⚠️ <b>Cambio aplicado</b> pero error triggering build.\n"
                                        f"Haz push manual o dispara el workflow desde GitHub.\n{prop['title']}")
                        else:
                            store.update_status(prop_id, 'applied')
                            tg_send(f"✅ <b>Aplicado</b>\n{prop['title']}")
                    else:
                        store.update_status(prop_id, 'failed')
                        tg_send(f"❌ <b>Error aplicando</b>\n{prop['title']}\n\n"
                                f"El old_string no se encontró en el archivo. "
                                f"El código puede haber cambiado desde la propuesta.")

                # Propuestas de parámetros legadas (orchestrator)
                elif data.startswith(('approve_', 'reject_')):
                    # El orchestrator maneja estas en su propio loop cuando está activo.
                    # Si llegamos aquí, el orchestrator ya terminó → no tenemos contexto del valor.
                    tg_answer(cq_id, '⚠️ Sesión del orchestrator expirada. '
                                     'Ejecuta de nuevo el orchestrator para re-proponer.')

        except KeyboardInterrupt:
            print('\n⏹ Monitor detenido')
            break
        except Exception as e:
            print(f'Error en loop: {e}')
            time.sleep(10)


def handle_command(text: str, store: ProposalStore):
    """Maneja comandos de texto del usuario."""
    cmd = text.split()[0].lower()

    if cmd == '/pending':
        pending = store.get_pending()
        if not pending:
            tg_send('✅ No hay propuestas pendientes.')
            return
        lines = [f"📋 <b>{len(pending)} propuesta(s) pendientes:</b>\n"]
        for p in pending:
            impact_e = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(p.get('impact', ''), '⚪')
            type_e   = '⚛️' if 'frontend' in p.get('type', '') else '🐍'
            lines.append(f"{impact_e}{type_e} <b>{p['title']}</b>\n"
                         f"   ID: <code>{p['id']}</code>")
        tg_send('\n'.join(lines))

    elif cmd == '/status':
        all_p = store.get_all()
        by_status: dict[str, int] = {}
        for p in all_p:
            s = p.get('status', 'unknown')
            by_status[s] = by_status.get(s, 0) + 1
        lines = [f"📊 <b>Estado de propuestas ({len(all_p)} total):</b>"]
        for s, n in sorted(by_status.items()):
            lines.append(f"  • {s}: {n}")
        tg_send('\n'.join(lines))

    elif cmd == '/help':
        tg_send(
            "🤖 <b>Agent Monitor — Comandos</b>\n\n"
            "/pending — Ver propuestas pendientes\n"
            "/status  — Resumen de todas las propuestas\n"
            "/help    — Esta ayuda\n\n"
            "Las propuestas nuevas llegan automáticamente desde el agent_orchestrator."
        )


if __name__ == '__main__':
    main()
