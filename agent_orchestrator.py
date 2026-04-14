#!/usr/bin/env python3
"""
AGENT ORCHESTRATOR — Monitor de salud del sistema Stock Analyzer

Corre cada 6h. Solo alerta cuando detecta algo roto o anómalo:

  1. Pipeline health — módulos que no corrieron hoy o están stale
  2. Output anomalies — conteos fuera de rango histórico (posible bug de scoring)
  3. GitHub Actions failures — workflows que fallaron en las últimas 24h
  4. Score distribution — si los grades/scores cambian bruscamente (bug de scoring)

No propone cambios de código. No hace análisis de mercado (eso es financial_agent.py).
Solo detecta problemas en la infraestructura.

Variables de entorno:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  GITHUB_TOKEN (lectura de Actions API)
  GITHUB_REPO  (ej. "tantancansado/stock_analyzer_a")
  GROQ_API_KEY (opcional — para diagnóstico de anomalías)

Uso:
  python3 agent_orchestrator.py          # análisis completo
  python3 agent_orchestrator.py --status # solo imprime estado, sin Telegram
  python3 agent_orchestrator.py --force  # siempre envía aunque todo esté OK
"""

import argparse
import csv
import io
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import requests

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN    = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID      = os.environ.get('TELEGRAM_CHAT_ID', '')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GH_TOKEN     = os.environ.get('GITHUB_TOKEN', '')
GH_REPO      = os.environ.get('GITHUB_REPO', 'tantancansado/stock_analyzer_a')

PAGES_BASE = f'https://raw.githubusercontent.com/{GH_REPO}/main'
GH_API     = 'https://api.github.com'
LOG_PATH   = Path('docs/agent_orchestrator_log.json')
GROQ_MODEL = 'meta-llama/llama-4-scout-17b-16e-instruct'

# ── Expected output ranges (histórico normal del sistema) ─────────────────────
BASELINES = {
    'value_filtered':    {'min': 5,   'max': 40,  'label': 'VALUE picks filtrados'},
    'value_raw':         {'min': 10,  'max': 80,  'label': 'VALUE picks brutos'},
    'fundamental_rows':  {'min': 80,  'max': 300, 'label': 'filas fundamental_scores'},
    'bounce_detected':   {'min': 0,   'max': 40,  'label': 'bounce setups detectados'},
    'eu_value':          {'min': 0,   'max': 40,  'label': 'VALUE EU picks'},
    'insider_rows':      {'min': 1,   'max': 200, 'label': 'filas recurring_insiders'},
}

# Módulos críticos — si están stale, es un problema real
CRITICAL_MODULES = {'value_us', 'fundamental', 'portfolio', 'cerebro'}

# ── Fetchers ──────────────────────────────────────────────────────────────────

def _fetch_json(path: str) -> Optional[dict]:
    try:
        r = requests.get(f'{PAGES_BASE}/{path}', timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _fetch_csv(path: str) -> list[dict]:
    try:
        r = requests.get(f'{PAGES_BASE}/{path}', timeout=15)
        if r.status_code == 200:
            return list(csv.DictReader(io.StringIO(r.text)))
    except Exception:
        pass
    return []


def _csv_len(path: str) -> int:
    """Returns row count (excluding header)."""
    try:
        r = requests.get(f'{PAGES_BASE}/{path}', timeout=15)
        if r.status_code == 200:
            lines = [l for l in r.text.strip().split('\n') if l.strip()]
            return max(0, len(lines) - 1)
    except Exception:
        pass
    return -1


# ── Health check 1: Pipeline freshness ────────────────────────────────────────

def check_pipeline_health() -> dict:
    """
    Lee pipeline_health.json generado por el pipeline diario.
    Devuelve: {stale_critical, stale_optional, missing, all_ok}
    """
    health = _fetch_json('docs/pipeline_health.json')
    if not health:
        return {'error': 'pipeline_health.json no encontrado', 'stale_critical': ['unknown'], 'stale_optional': [], 'missing': [], 'all_ok': False}

    modules     = health.get('modules', {})
    pipeline_dt = health.get('pipeline_date', '')
    generated   = health.get('generated_at', '')

    stale_critical = []
    stale_optional = []
    missing        = []

    for name, info in modules.items():
        status = info.get('status', 'unknown')
        if status == 'missing':
            missing.append(name)
        elif status == 'stale':
            if name in CRITICAL_MODULES:
                stale_critical.append(f"{name} (último: {info.get('date', '?')})")
            else:
                stale_optional.append(f"{name} (último: {info.get('date', '?')})")

    all_ok = not stale_critical and not missing
    return {
        'pipeline_date':    pipeline_dt,
        'generated_at':     generated,
        'ok_count':         health.get('ok_count', 0),
        'total':            health.get('total', 0),
        'stale_critical':   stale_critical,
        'stale_optional':   stale_optional,
        'missing':          missing,
        'all_ok':           all_ok,
    }


# ── Health check 2: Output count anomalies ────────────────────────────────────

def check_output_counts() -> dict:
    """
    Verifica que los outputs del pipeline tienen conteos dentro del rango esperado.
    Fuera de rango = posible bug de scoring, fallo de datos, o threshold equivocado.
    """
    counts = {
        'value_filtered':   _csv_len('docs/value_opportunities_filtered.csv'),
        'value_raw':        _csv_len('docs/value_opportunities.csv'),
        'fundamental_rows': _csv_len('docs/fundamental_scores.csv'),
        'eu_value':         _csv_len('docs/european_value_opportunities.csv'),
        'insider_rows':     _csv_len('docs/recurring_insiders.csv'),
    }

    # Bounce count from JSON
    mr = _fetch_json('docs/mean_reversion_opportunities.json')
    if mr:
        counts['bounce_detected'] = len([
            o for o in mr.get('opportunities', [])
            if o.get('strategy') == 'Oversold Bounce'
        ])

    anomalies = []
    for key, val in counts.items():
        if val < 0:
            continue  # fetch failed, skip
        baseline = BASELINES.get(key)
        if not baseline:
            continue
        if val < baseline['min']:
            anomalies.append({
                'key': key, 'val': val,
                'label': baseline['label'],
                'issue': f"MUY BAJO ({val} < min {baseline['min']})",
                'severity': 'HIGH' if key in ('value_filtered', 'fundamental_rows') else 'MEDIUM',
            })
        elif val > baseline['max']:
            anomalies.append({
                'key': key, 'val': val,
                'label': baseline['label'],
                'issue': f"MUY ALTO ({val} > max {baseline['max']})",
                'severity': 'MEDIUM',
            })

    return {'counts': counts, 'anomalies': anomalies}


# ── Health check 3: Grade distribution ────────────────────────────────────────

def check_grade_distribution() -> dict:
    """
    Detecta si la distribución de grades cambió bruscamente.
    Un sistema sano tiene una distribución razonablemente estable.
    Si de repente el 90%+ son A o el 90%+ son F, algo falló en el scoring.
    """
    rows = _fetch_csv('docs/value_opportunities_filtered.csv')
    if not rows:
        return {'skipped': True}

    grade_counts: dict[str, int] = {}
    for r in rows:
        g = r.get('conviction_grade') or r.get('grade') or '?'
        grade_counts[g] = grade_counts.get(g, 0) + 1

    total    = sum(grade_counts.values())
    warnings = []

    if total > 0:
        a_pct  = grade_counts.get('A', 0) / total * 100
        f_pct  = (grade_counts.get('F', 0) + grade_counts.get('D', 0)) / total * 100
        ab_pct = (grade_counts.get('A', 0) + grade_counts.get('B', 0)) / total * 100

        if a_pct > 70:
            warnings.append(f'Demasiados grados A ({a_pct:.0f}%) — posible inflación de scores')
        if f_pct > 60:
            warnings.append(f'Demasiados grados F/D ({f_pct:.0f}%) — posible bug de scoring')
        if ab_pct == 0 and total > 5:
            warnings.append('Cero picks A/B con >5 resultados — scoring posiblemente roto')

    return {
        'total':        total,
        'distribution': grade_counts,
        'warnings':     warnings,
    }


# ── Health check 4: GitHub Actions failures ───────────────────────────────────

def check_github_actions() -> dict:
    """
    Lee los últimos runs de cada workflow crítico vía GitHub API.
    Alerta si alguno falló en las últimas 24h.
    """
    if not GH_TOKEN:
        return {'skipped': True, 'reason': 'GITHUB_TOKEN no configurado'}

    critical_workflows = [
        'daily-analysis.yml',
        'intraday-bounce.yml',
        'financial-agent.yml',
    ]

    headers  = {'Authorization': f'token {GH_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
    cutoff   = datetime.now(timezone.utc) - timedelta(hours=24)
    failures = []

    for wf in critical_workflows:
        try:
            url = f'{GH_API}/repos/{GH_REPO}/actions/workflows/{wf}/runs?per_page=3'
            r   = requests.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                continue
            runs = r.json().get('workflow_runs', [])
            for run in runs:
                created = run.get('created_at', '')
                try:
                    run_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                except Exception:
                    continue
                if run_dt < cutoff:
                    break
                conclusion = run.get('conclusion')
                if conclusion in ('failure', 'timed_out', 'cancelled'):
                    failures.append({
                        'workflow': wf,
                        'status':   conclusion,
                        'run_id':   run.get('id'),
                        'created':  created[:16],
                        'url':      run.get('html_url', ''),
                    })
                    break  # solo reportar el más reciente
        except Exception:
            pass

    return {'failures': failures, 'checked': critical_workflows}


# ── Groq diagnostic (opcional) ────────────────────────────────────────────────

def groq_diagnose(issues: list[str]) -> Optional[str]:
    """
    Usa Groq para diagnosticar las anomalías detectadas.
    Solo se llama cuando hay problemas reales — no para generar ruido.
    """
    if not GROQ_API_KEY or not issues:
        return None

    prompt = (
        "Eres un ingeniero de datos analizando anomalías en un pipeline de análisis de bolsa.\n"
        "El sistema genera CSVs diarios con picks VALUE, scores fundamentales y setups de rebote.\n\n"
        "ANOMALÍAS DETECTADAS:\n"
        + '\n'.join(f'- {i}' for i in issues)
        + "\n\nPara cada anomalía, indica en 1-2 frases:"
        "\n1. La causa más probable (fallo de datos, bug de scoring, mercado extremo, etc.)"
        "\n2. Cómo verificarlo rápidamente"
        "\nSé específico y conciso. Sin introducción."
    )

    try:
        r = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {GROQ_API_KEY}', 'Content-Type': 'application/json'},
            json={
                'model': GROQ_MODEL,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.2,
                'max_tokens':  400,
            },
            timeout=20,
        )
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f'[orchestrator] Groq error: {e}')
        return None


# ── Telegram ──────────────────────────────────────────────────────────────────

def _tg(text: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print(text)
        return
    try:
        requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            json={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'HTML',
                  'disable_web_page_preview': True},
            timeout=10,
        )
    except Exception:
        pass


def build_alert(pipeline: dict, counts: dict, grades: dict, actions: dict,
                diagnostic: Optional[str]) -> Optional[str]:
    """
    Construye el mensaje de alerta. Devuelve None si no hay nada que reportar.
    """
    sections = []
    all_issues = []

    # ── Pipeline freshness ────────────────────────────────────────────────────
    if pipeline.get('error'):
        sections.append(f"🔴 <b>Pipeline health:</b> {pipeline['error']}")
        all_issues.append(pipeline['error'])
    elif not pipeline.get('all_ok'):
        lines = ['🔴 <b>Módulos del pipeline con problemas:</b>']
        for m in pipeline.get('stale_critical', []):
            lines.append(f"  • ❌ CRÍTICO: <code>{m}</code>")
            all_issues.append(f'módulo crítico stale: {m}')
        for m in pipeline.get('missing', []):
            lines.append(f"  • 🔴 FALTA: <code>{m}</code>")
            all_issues.append(f'módulo faltante: {m}')
        for m in pipeline.get('stale_optional', [])[:3]:
            lines.append(f"  • 🟡 stale: <code>{m}</code>")
        if pipeline.get('stale_optional') and len(pipeline['stale_optional']) > 3:
            lines.append(f"  • ... (+{len(pipeline['stale_optional']) - 3} más)")
        sections.append('\n'.join(lines))

    # ── Output anomalies ──────────────────────────────────────────────────────
    anomalies = counts.get('anomalies', [])
    if anomalies:
        lines = ['⚠️ <b>Anomalías en outputs:</b>']
        for a in anomalies:
            icon = '🔴' if a['severity'] == 'HIGH' else '🟡'
            lines.append(f"  {icon} <b>{a['label']}:</b> {a['issue']}")
            all_issues.append(f"{a['label']}: {a['issue']}")
        # Show current counts for context
        c = counts.get('counts', {})
        lines.append(
            f"  <i>Conteos: {c.get('value_filtered','?')} VALUE | "
            f"{c.get('fundamental_rows','?')} fund. | "
            f"{c.get('bounce_detected','?')} bounce</i>"
        )
        sections.append('\n'.join(lines))

    # ── Grade distribution ────────────────────────────────────────────────────
    grade_warns = grades.get('warnings', [])
    if grade_warns:
        lines = ['🔬 <b>Distribución de grades anómala:</b>']
        for w in grade_warns:
            lines.append(f"  • {w}")
            all_issues.append(w)
        sections.append('\n'.join(lines))

    # ── GitHub Actions failures ───────────────────────────────────────────────
    failures = actions.get('failures', [])
    if failures:
        lines = ['🚨 <b>Workflows fallidos (24h):</b>']
        for f in failures:
            lines.append(
                f"  • <code>{f['workflow']}</code> → {f['status']} ({f['created']})"
            )
            all_issues.append(f"workflow {f['workflow']}: {f['status']}")
        sections.append('\n'.join(lines))

    if not sections:
        return None  # todo OK — no enviar

    # ── Header ────────────────────────────────────────────────────────────────
    now_str = datetime.now(timezone.utc).strftime('%d/%m %H:%M')
    pd      = pipeline.get('pipeline_date', '?')
    ok      = pipeline.get('ok_count', '?')
    total   = pipeline.get('total', '?')

    header = (
        f"🔧 <b>System Health — {now_str} UTC</b>\n"
        f"Pipeline: {pd} · {ok}/{total} módulos OK\n"
        f"{'━'*26}\n\n"
    )

    body = '\n\n'.join(sections)

    # ── Groq diagnostic ───────────────────────────────────────────────────────
    diag_text = ''
    if diagnostic:
        diag_text = f'\n\n🤖 <b>Diagnóstico:</b>\n<i>{diagnostic}</i>'

    return header + body + diag_text


# ── Log ───────────────────────────────────────────────────────────────────────

def _log(entry: dict) -> None:
    log = []
    if LOG_PATH.exists():
        try:
            log = json.loads(LOG_PATH.read_text())
        except Exception:
            pass
    log.append(entry)
    log = log[-100:]
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps(log, indent=2, ensure_ascii=False))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='System Health Monitor')
    parser.add_argument('--status', action='store_true', help='Solo imprime estado, sin Telegram')
    parser.add_argument('--force',  action='store_true', help='Envía aunque todo esté OK')
    args = parser.parse_args()

    print(f'\n{"="*60}')
    print(f'🔧 SYSTEM MONITOR — {datetime.now().strftime("%Y-%m-%d %H:%M UTC")}')
    print(f'{"="*60}')

    # ── 1. Pipeline health ────────────────────────────────────────────────────
    print('\n📋 [1/4] Pipeline health...')
    pipeline = check_pipeline_health()
    if pipeline.get('error'):
        print(f'  ⚠️  {pipeline["error"]}')
    else:
        print(f'  {pipeline["ok_count"]}/{pipeline["total"]} módulos OK — pipeline: {pipeline["pipeline_date"]}')
        if pipeline['stale_critical']:
            print(f'  ❌ Críticos stale: {pipeline["stale_critical"]}')
        if pipeline['missing']:
            print(f'  🔴 Faltantes: {pipeline["missing"]}')
        if pipeline['stale_optional']:
            print(f'  🟡 Opcionales stale: {pipeline["stale_optional"][:3]}')

    # ── 2. Output counts ──────────────────────────────────────────────────────
    print('\n📊 [2/4] Output counts...')
    counts = check_output_counts()
    c = counts.get('counts', {})
    print(f'  VALUE: {c.get("value_filtered","?")} filtrados / {c.get("value_raw","?")} raw')
    print(f'  Fund: {c.get("fundamental_rows","?")} filas | Bounce: {c.get("bounce_detected","?")} | EU: {c.get("eu_value","?")}')
    if counts['anomalies']:
        print(f'  ⚠️  {len(counts["anomalies"])} anomalías detectadas')
        for a in counts['anomalies']:
            print(f'     • {a["label"]}: {a["issue"]}')

    # ── 3. Grade distribution ─────────────────────────────────────────────────
    print('\n🔬 [3/4] Grade distribution...')
    grades = check_grade_distribution()
    if not grades.get('skipped'):
        print(f'  Total picks: {grades.get("total", "?")} | Dist: {grades.get("distribution", {})}')
        for w in grades.get('warnings', []):
            print(f'  ⚠️  {w}')

    # ── 4. GitHub Actions ─────────────────────────────────────────────────────
    print('\n🚀 [4/4] GitHub Actions (últimas 24h)...')
    actions = check_github_actions()
    if actions.get('skipped'):
        print(f'  Omitido: {actions.get("reason")}')
    elif actions['failures']:
        print(f'  ❌ {len(actions["failures"])} workflow(s) fallidos:')
        for f in actions['failures']:
            print(f'     • {f["workflow"]}: {f["status"]} @ {f["created"]}')
    else:
        print(f'  ✅ Sin fallos en {", ".join(actions["checked"])}')

    if args.status:
        print('\n✅ Modo --status: solo métricas. Done.')
        return

    # ── Collect all issues for Groq ───────────────────────────────────────────
    all_issues = (
        [f'módulo crítico stale: {m}' for m in pipeline.get('stale_critical', [])]
        + [f'módulo faltante: {m}' for m in pipeline.get('missing', [])]
        + [f'{a["label"]}: {a["issue"]}' for a in counts.get('anomalies', [])]
        + grades.get('warnings', [])
        + [f'workflow {f["workflow"]}: {f["status"]}' for f in actions.get('failures', [])]
    )

    has_problems = bool(all_issues)

    # ── Groq diagnostic if there are real problems ────────────────────────────
    diagnostic = None
    if has_problems and GROQ_API_KEY:
        print(f'\n🤖 Consultando Groq para diagnóstico ({len(all_issues)} issues)...')
        diagnostic = groq_diagnose(all_issues)
        if diagnostic:
            print(f'  Diagnóstico generado ({len(diagnostic)} chars)')

    # ── Build and send alert ──────────────────────────────────────────────────
    alert = build_alert(pipeline, counts, grades, actions, diagnostic)

    if alert is None and not args.force:
        now_str = datetime.now(timezone.utc).strftime('%d/%m %H:%M')
        print(f'\n✅ Sistema OK ({now_str}) — sin alertas')
        _log({'ts': datetime.now(timezone.utc).isoformat(), 'action': 'ok',
              'pipeline_date': pipeline.get('pipeline_date'),
              'counts': counts.get('counts', {})})
        return

    if args.force and alert is None:
        # Force mode: send a status summary even if everything is OK
        ok   = pipeline.get('ok_count', '?')
        tot  = pipeline.get('total', '?')
        pd   = pipeline.get('pipeline_date', '?')
        c    = counts.get('counts', {})
        alert = (
            f"✅ <b>System OK — {datetime.now(timezone.utc).strftime('%d/%m %H:%M')} UTC</b>\n"
            f"Pipeline: {pd} · {ok}/{tot} módulos\n"
            f"VALUE: {c.get('value_filtered','?')} picks | Fund: {c.get('fundamental_rows','?')} | "
            f"Bounce: {c.get('bounce_detected','?')}"
        )

    print(f'\n📱 Enviando alerta a Telegram...')
    _tg(alert)

    _log({
        'ts':           datetime.now(timezone.utc).isoformat(),
        'action':       'alert' if has_problems else 'force_ok',
        'issues':       all_issues,
        'pipeline_date': pipeline.get('pipeline_date'),
        'counts':       counts.get('counts', {}),
    })

    print(f'✅ Alerta enviada ({len(all_issues)} issues detectados)')
    print(f'{"="*60}\n')


if __name__ == '__main__':
    main()
