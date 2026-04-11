"""
Ejemplo de agente con Claude Agent SDK.

Este agente analiza los CSVs del stock analyzer de forma autónoma:
1. Lee value_opportunities.csv y fundamental_scores.csv
2. Filtra las mejores oportunidades según criterios Lynch/GARP
3. Genera un informe de texto con recomendaciones

Para ejecutar:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...
    python agent_example.py

Documentación SDK: https://docs.anthropic.com/en/docs/agents
"""

import anthropic
import json
import csv
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Herramientas (tools) que el agente puede usar
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "read_csv",
        "description": (
            "Lee un CSV del proyecto stock analyzer y devuelve las primeras N filas "
            "como lista de dicts. Datasets disponibles: value_opportunities, "
            "fundamental_scores, momentum_opportunities, portfolio_tracker_summary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset": {
                    "type": "string",
                    "enum": [
                        "value_opportunities",
                        "fundamental_scores",
                        "momentum_opportunities",
                    ],
                },
                "limit": {
                    "type": "integer",
                    "description": "Número máximo de filas a devolver (default 20)",
                    "default": 20,
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Columnas a incluir (vacío = todas)",
                },
            },
            "required": ["dataset"],
        },
    },
    {
        "name": "filter_value_picks",
        "description": (
            "Filtra value_opportunities.csv según criterios VALUE/GARP estrictos: "
            "ROE positivo, FCF yield ≥ 3%, R:R ≥ 2, sin earnings <7d. "
            "Devuelve los tickers que pasan el filtro ordenados por score."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "min_score": {"type": "number", "default": 60},
                "min_fcf_yield": {"type": "number", "default": 3.0},
                "min_rr": {"type": "number", "default": 2.0},
                "exclude_earnings_warning": {"type": "boolean", "default": True},
            },
            "required": [],
        },
    },
    {
        "name": "read_portfolio_summary",
        "description": "Lee el resumen de performance del portfolio tracker (win rate, avg return, etc.)",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

# ---------------------------------------------------------------------------
# Implementación de las herramientas
# ---------------------------------------------------------------------------

DOCS = Path(__file__).parent / "docs"


def _read_csv_file(path: Path, limit: int, columns=None) -> list:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= limit:
                break
            if columns:
                row = {k: v for k, v in row.items() if k in columns}
            rows.append(dict(row))
    return rows


def tool_read_csv(dataset: str, limit: int = 20, columns=None) -> str:
    paths = {
        "value_opportunities": DOCS / "value_opportunities.csv",
        "fundamental_scores": DOCS / "fundamental_scores.csv",
        "momentum_opportunities": DOCS / "momentum_opportunities.csv",
    }
    path = paths.get(dataset)
    if not path or not path.exists():
        return json.dumps({"error": f"Dataset '{dataset}' no encontrado en {DOCS}"})
    rows = _read_csv_file(path, limit, columns)
    return json.dumps({"dataset": dataset, "rows": rows, "count": len(rows)})


def tool_filter_value_picks(
    min_score: float = 60,
    min_fcf_yield: float = 3.0,
    min_rr: float = 2.0,
    exclude_earnings_warning: bool = True,
) -> str:
    path = DOCS / "value_opportunities.csv"
    if not path.exists():
        return json.dumps({"error": "value_opportunities.csv no encontrado"})

    picks = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                score = float(row.get("value_score") or 0)
                fcf = float(row.get("fcf_yield_pct") or 0)
                rr = float(row.get("risk_reward_ratio") or 0)
                earnings_warn = row.get("earnings_warning", "").lower() == "true"
                negative_roe = row.get("negative_roe", "").lower() == "true"
            except ValueError:
                continue

            if negative_roe:
                continue  # Hard reject
            if score < min_score:
                continue
            if fcf < min_fcf_yield:
                continue
            if rr < min_rr:
                continue
            if exclude_earnings_warning and earnings_warn:
                continue

            picks.append({
                "ticker": row.get("ticker"),
                "company": row.get("company_name") or row.get("name"),
                "score": score,
                "fcf_yield_pct": fcf,
                "risk_reward_ratio": rr,
                "analyst_upside_pct": row.get("analyst_upside_pct"),
                "grade": row.get("grade"),
                "sector": row.get("sector"),
            })

    picks.sort(key=lambda x: x["score"], reverse=True)
    return json.dumps({"filtered_picks": picks, "count": len(picks)})


def tool_read_portfolio_summary() -> str:
    path = DOCS / "portfolio_tracker" / "summary.json"
    if not path.exists():
        return json.dumps({"error": "summary.json no encontrado"})
    return path.read_text()


def execute_tool(name: str, inputs: dict) -> str:
    if name == "read_csv":
        return tool_read_csv(**inputs)
    elif name == "filter_value_picks":
        return tool_filter_value_picks(**inputs)
    elif name == "read_portfolio_summary":
        return tool_read_portfolio_summary()
    return json.dumps({"error": f"Herramienta desconocida: {name}"})


# ---------------------------------------------------------------------------
# Agente — bucle agentic
# ---------------------------------------------------------------------------

def run_agent(prompt: str) -> str:
    """
    Ejecuta el agente con el prompt dado.
    El agente usará las tools en bucle hasta completar la tarea.
    """
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": prompt}]

    print(f"\n{'='*60}")
    print(f"AGENTE INICIADO")
    print(f"{'='*60}\n")

    while True:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            tools=TOOLS,
            messages=messages,
            system=(
                "Eres un analista financiero VALUE/GARP especializado en el stock analyzer. "
                "Usa las herramientas disponibles para analizar los datos reales del sistema. "
                "Sé conciso, preciso y usa los criterios Lynch: ROE positivo, FCF yield alto, "
                "R:R ≥ 2, sin empresas con pérdidas."
            ),
        )

        # Añadir respuesta del asistente al historial
        messages.append({"role": "assistant", "content": response.content})

        # Si terminó (no más tool_use), devolver texto final
        if response.stop_reason == "end_turn":
            final = next(
                (b.text for b in response.content if hasattr(b, "text")), ""
            )
            print(f"\nAGENTE COMPLETADO:\n{'-'*40}\n{final}\n")
            return final

        # Procesar tool_use blocks
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            print(f"[TOOL] {block.name}({json.dumps(block.input, ensure_ascii=False)})")
            result = execute_tool(block.name, block.input)
            result_preview = result[:200] + "..." if len(result) > 200 else result
            print(f"[RESULT] {result_preview}\n")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })

        messages.append({"role": "user", "content": tool_results})


# ---------------------------------------------------------------------------
# Main — ejemplos de uso
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Ejemplo 1: Análisis de oportunidades del día
    reporte = run_agent(
        "Analiza las oportunidades VALUE de hoy. "
        "Primero lee el portfolio summary para saber cómo va el sistema, "
        "luego filtra las mejores picks con FCF ≥ 5% y R:R ≥ 2.5, "
        "y dame un resumen ejecutivo de máximo 5 oportunidades con sus tesis clave."
    )

    # Ejemplo 2 (comentado): Agente de monitoreo de pipeline
    # run_agent(
    #     "Compara los scores de hoy en value_opportunities con los fundamentales "
    #     "en fundamental_scores. Identifica cualquier ticker donde el value_score "
    #     "sea ≥70 pero el ROE sea negativo — eso sería un error del sistema."
    # )
