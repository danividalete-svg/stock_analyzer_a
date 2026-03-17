# Stock Analyzer — Instrucciones para Claude Code

## Arquitectura general

Sistema dual VALUE + MOMENTUM:
- `super_score_integrator.py` → `docs/value_opportunities.csv` + `docs/momentum_opportunities.csv`
- `fundamental_scorer.py` → `docs/fundamental_scores.csv`
- `ticker_api.py` → API Flask en Railway
- `portfolio_tracker.py` → seguimiento de recomendaciones (7d/14d/30d)
- Frontend: React + Vite + shadcn/ui + Tailwind v4, desplegado en `docs/app/` (GitHub Pages)

Orden del pipeline (GitHub Actions):
```
sector_rotation → mean_reversion → super_score_integrator → ai_quality_filter
→ entry_exit → thesis_generator → super_dashboard_generator → portfolio_tracker → ticker_data_cache
```

## Reglas críticas de código

### Python (backend)
- **NUNCA dar scores cuando el dato es default/missing**: `fundamental_score == 50.0` y `ml_score == 50.0` significan dato ausente — no puntuar
- `negative_roe == True` → `value_score = 0` (HARD REJECT)
- `analyst_upside_pct < 0` → `value_score = 0` (sobrevalorado)
- `dividendYield` en yfinance ya viene en porcentaje (0.38 = 0.38%), NO decimal
- `profit_margin_pct` está en `earnings_details`, NO en `health_details`
- MA filter: si falla por rate-limit ("Too Many Requests"), NO penalizar (-20pts se salta)
- Sin fallbacks silenciosos: si el dato falla → no score, no número inventado

### CSS / Frontend
- **NUNCA usar `overflow: hidden` en `.glass`** — usar `overflow: clip`
  - `overflow: hidden` crea un scroll container que rompe `position: sticky` en los thead
  - `overflow: clip` tiene idéntico efecto visual pero NO crea scroll container
- Las tablas usan `thead th` con `position: sticky; top: var(--topbar-height, 50px)`
- Tema: dark glassmorphism + Cybertruck skin (cyan eléctrico `194 100% 48%`, esquinas afiladas `--radius: 0.25rem`)

### Frontend (React)
- CSVs en producción vienen de GitHub Pages (`VITE_CSV_BASE`), NO de Railway
- Railway API solo tiene snapshot del momento del deploy
- `getCsvUrl()` / `downloadCsv()` en `frontend/src/api/client.ts`
- Watchlist persiste en localStorage con key `sa-watchlist-v1`

## Archivos clave

| Archivo | Descripción |
|---------|-------------|
| `docs/fundamental_scores.csv` | Datos fundamentales por ticker |
| `docs/value_opportunities.csv` | Output VALUE (sin filtrar) |
| `docs/value_opportunities_filtered.csv` | VALUE filtrado por IA |
| `docs/momentum_opportunities.csv` | Output MOMENTUM |
| `docs/portfolio_tracker/recommendations.csv` | Historial de recomendaciones |
| `docs/portfolio_tracker/summary.json` | Resumen de performance |
| `ticker_api.py` | Flask API — todos los endpoints |
| `frontend/src/pages/` | Páginas React |
| `frontend/src/hooks/useTechnicalData.ts` | Cache compartido de señales técnicas (patrón listener) |

## Perfil del usuario

- Inversor VALUE/GARP estilo Lynch, NO trader momentum Minervini
- Objetivo: ganancias consistentes 5-10%, alta tasa de acierto
- Prefiere 0 señales antes que señales falsas
- Evitar sugerir compras sin análisis fundamentales sólidos

## Antes de modificar

1. Leer el archivo antes de editarlo
2. No crear archivos nuevos a menos que sea imprescindible
3. No añadir abstracciones para uso único
4. No añadir comentarios obvios ni docstrings a código no modificado
5. Ante errores de build: diagnosticar causa raíz, no hacer `--no-verify`
