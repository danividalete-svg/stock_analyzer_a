# TIKR Pro Scraper — Arquitectura y Referencia

Sistema de enriquecimiento de datos financieros que extrae información de TIKR Pro
para alimentar la generación de tesis de inversión (`thesis_generator.py`).

---

## Flujo general

```
curated_tickers.py          tikr_scraper.py              thesis_generator.py
(~105 tickers T1+T2+T3)  →  docs/tikr_earnings_data.json  →  docs/theses.json
```

El scraper corre **semanalmente** (o bajo demanda en local). Los datos generados
son consumidos automáticamente por `thesis_generator.py` en cada ejecución del
pipeline diario.

---

## Fases de ejecución

### Fase 0 — Modelos de valoración `/lv`
**1 llamada** para todos los tickers.

Descarga los modelos DCF que el usuario ha construido en la web de TIKR.
Extrae: `target_price`, `irr_pct`, estimaciones propias de Revenue/EPS/EBIT
por año fiscal, CAGRs históricos.

### Fase 1 — Resolución de IDs
**2 llamadas por ticker** (Algolia + `/trkdids`).

Por cada ticker necesitamos tres IDs antes de poder hacer cualquier otra cosa:

| ID | Fuente | Usado por |
|----|--------|-----------|
| `cid` (CIQ companyid) | Algolia | `/tf`, `/est`, `/transcripts_v2`, `/wlp` |
| `tid` (tradingitemid) | Algolia | `/wlp`, `/est`, `/tf` |
| `oa_perm_id` (Reuters PermID) | `/trkdids` | `/listReports` |
| `ric_id` (Reuters RIC) | construido del exchange | `/headlines`, `/sigdevs`, `/shareholders` |

Ejemplos: MSFT → cid=21835, tid=2630413, perm=4295907168, ric=MSFT.O

Los IDs se cachean en `docs/tikr_id_cache.json` — las siguientes ejecuciones
no repiten las llamadas de resolución.

### Fase 2 — Precios + NTM batch `/wlp`
**1 llamada batch** con todos los tickers.

Devuelve para cada ticker:
- Precio actual (close, high, low)
- Market cap y Enterprise Value (en millones)
- Estimaciones NTM (Next Twelve Months) de consenso:
  `ntm_revenue`, `ntm_ebitda`, `ntm_ebit`, `ntm_fcf`, `ntm_eps`

Los múltiplos se calculan localmente:
`NTM EV/EBITDA`, `NTM EV/Revenue`, `NTM EV/EBIT`, `NTM P/E`, `NTM FCF Yield %`

### Fase 3 — Datos por ticker (loop secuencial)
**~7 llamadas por ticker**, con delays humanos entre cada una.

#### `/tf` — Históricos financieros (7 años)
Payload: `{cid, tid, p:"1" (annual), repid:1}`

Extrae series anuales de:

| Métrica | Descripción |
|---------|-------------|
| `total_revenue` | Ingresos totales ($M) — ID 28 estándar, ID 29 aseguradoras |
| `gross_profit` | Beneficio bruto ($M) |
| `ebitda` | EBITDA ($M) |
| `ebit` | EBIT / Beneficio operativo ($M) |
| `net_income` | Beneficio neto ($M) |
| `eps_diluted` | EPS diluido (por acción) |
| `cash_from_operations` | Cash flow operativo ($M) |
| `capex` | CapEx ($M, negativo) |
| `cash` | Caja y equivalentes ($M) |
| `total_debt` | Deuda total ($M) |
| `total_equity` | Patrimonio neto ($M) |
| `roe_pct` | Return on Equity % |
| `net_margin_pct` | Margen neto % |
| `ebitda_margin_pct` | Margen EBITDA % |
| `net_debt_ebitda` | Deuda neta / EBITDA |
| `shares_diluted` | Acciones diluidas (millones) |
| `buybacks` | Recompra de acciones ($M, negativo = buyback) |

También calcula `revenue_cagr` a 3, 5 y 7 años.

**Cache:** si los datos tienen menos de 7 días, se reusan sin llamar a la API
(los financieros anuales no cambian a diario).

#### `/est` — Estimaciones consenso analistas
Payload: `{cid, tid, p:"1"}`

Devuelve `actuals` (valores reales reportados) y `estimates` (consenso futuro).

**Actuals** (últimos 3 años reportados):

| Campo | dataitemid |
|-------|-----------|
| revenue | 100186 |
| ebitda | 100193 |
| ebit | 100221 |
| net_income_norm | 100256 |
| eps_norm | 100179 |
| eps_gaap | 100284 |
| fcf | 114220 |

**Forward estimates** (hasta 5 años vista):

| Campo | dataitemid |
|-------|-----------|
| revenue | 100180 |
| ebitda | 100187 |
| ebit | 100215 |
| net_income_norm | 100250 |
| eps_norm | 100173 |
| eps_gaap | 100278 |
| fcf | 114221 |

También calcula `revision_flag`: compara el EPS estimado más reciente con
el más antiguo disponible para el año siguiente → `up` / `down` / `stable`.

#### `/transcripts_v2` — Earnings calls
Payload: `{cid}`

Últimas 4 earnings calls y 3 conferencias de inversores.
Extrae: headline, fecha, keydevid, transcriptid.

#### `/headlines` — Noticias Reuters
Payload: `{id: ric_id, lang: ["ES","EN"]}`

Últimas 10 noticias. Campos: headline, datetime, source, language.
Requiere RIC format (ej: `MSFT.O`, `AI.PA`).

#### `/sigdevs` — Eventos corporativos S&P CIQ
Payload: `{id: ric_id}`

Hasta 15 eventos significativos: M&A, cambios directivos, productos,
regulatorio, earnings guidance. Clasificados por topic y significance.

#### `/shareholders` — Accionistas institucionales Reuters
Payload: `{ticker: ric_id}`

Top 10 holders institucionales con: nombre, tipo (active/passive),
% del capital, shares held, variación trimestral.

#### `/listReports` — Filings SEC + earnings releases
Payload: `{id: oa_perm_id}`  ← usa Reuters PermID, NO el RIC

Clasifica automáticamente en:
- `earnings_releases`: comunicados de resultados (Bridge feed)
- `sec_filings`: 10-K, 10-Q, 8-K (Edgar feed)
- `presentations`: investor day, quarterly presentations (PDF)

---

## Estructura del output

`docs/tikr_earnings_data.json`:

```json
{
  "generated_at": "2026-04-13T...",
  "total": 105,
  "errors": [],
  "data": {
    "MSFT": {
      "cid": "21835",
      "tid": "2630413",
      "ric_id": "MSFT.O",
      "price": { "c": 370.87, "mc": 2753943, "tev": 2787759 },
      "multiples": {
        "ntm_ev_ebitda": 13.1,
        "ntm_pe": 21.1,
        "ntm_fcf_yield_pct": 2.43
      },
      "valuation_model": {
        "target_price": 923.37,
        "irr_pct": 18.87,
        "eps_estimates": { "2026": 16.8, "2027": 18.9 },
        "revenue_cagr": { "1y": 14.93, "3y": 12.42, "5y": 14.52 }
      },
      "financials_history": {
        "annual_years": [2025, 2024, 2023, 2022, 2021, 2020, 2019],
        "metrics": {
          "total_revenue": { "2025": 281724, "2024": 245122 },
          "ebitda_margin_pct": { "2025": 55.6, "2024": 52.8 }
        },
        "revenue_cagr": { "3y": 12.42, "5y": 14.52 }
      },
      "analyst_estimates": {
        "current_year": 2026,
        "forward": {
          "2026": { "revenue": 351625, "ebitda": 212612, "eps_norm": 17.57, "fcf": 66886 },
          "2027": { "revenue": 390000, "eps_norm": 20.5 }
        },
        "recent": {
          "2024": { "revenue": 245122, "eps_norm": 11.45 },
          "2025": { "revenue": 281724, "eps_norm": 13.64 }
        },
        "revision_flag": "stable"
      },
      "shareholders": {
        "top_holders": [
          { "name": "Vanguard", "pct_of_shares": 9.6, "orientation": "Passive" }
        ]
      },
      "reports": {
        "earnings_releases": [...],
        "sec_filings": [...]
      }
    }
  }
}
```

---

## Integración con thesis_generator.py

`ThesisGenerator` carga el JSON en `__init__` y expone dos métodos:

- **`_tikr_context(ticker)`** — bloque de texto para el prompt del AI con:
  múltiplos NTM, target/IRR del modelo, 5 años de Revenue/EBITDA/márgenes/ROE,
  Revenue CAGR, estimaciones forward analistas (con flag de revisión),
  top accionistas, último earnings release y filings recientes.

- **`_normalize_value_row()`** — añade al dict de la fila:
  `tikr_ntm_pe`, `tikr_ntm_ev_ebitda`, `tikr_ntm_fcf_yield`,
  `tikr_target_price`, `tikr_irr_pct`

---

## Stealth y frecuencia

| Medida | Implementación |
|--------|---------------|
| Delays humanos | Distribución beta (4-9s), no uniforme |
| Pausa larga | Cada 10 tickers: 25-55s aleatorio |
| Orden aleatorio | `random.shuffle(tickers)` en cada run |
| Headers Chrome 146 | User-Agent, sec-ch-ua, sec-fetch-*, Priority |
| Sesión warm-up | GET a app.tikr.com antes de empezar |
| Sin paralelismo | Una request a la vez |
| Cache `/tf` 7 días | Históricos anuales no cambian a diario |
| Cron irregular | `23 5 * * 0` (domingos 05:23 UTC, no hora redonda) |

**Frecuencia recomendada:** semanal (domingos). Los datos de estimaciones
y precios se actualizan con suficiente frecuencia para análisis VALUE/GARP.

---

## Uso en local

```bash
# Test un ticker
TIKR_EMAIL=... TIKR_PASSWORD=... python3 tikr_scraper.py --test MSFT

# Lista específica
TIKR_EMAIL=... TIKR_PASSWORD=... python3 tikr_scraper.py --tickers "MSFT,NKE,VRSK"

# Universo completo T1+T2+T3 (~105 tickers, ~90 min)
TIKR_EMAIL=... TIKR_PASSWORD=... python3 tikr_scraper.py --run

# Solo un tier
TIKR_EMAIL=... TIKR_PASSWORD=... python3 tikr_scraper.py --run --tier 1
```

---

## Archivos relacionados

| Archivo | Descripción |
|---------|-------------|
| `tikr_scraper.py` | Scraper principal |
| `curated_tickers.py` | Universo T1-T4 (~120 tickers) |
| `thesis_generator.py` | Consumidor del JSON — genera tesis AI |
| `docs/tikr_earnings_data.json` | Output principal |
| `docs/tikr_id_cache.json` | Cache de IDs (cid/tid/perm) — no borrar |
| `.github/workflows/tikr-enrichment.yml` | Workflow semanal (pendiente de crear) |

---

## Auth

AWS Cognito SRP (no password directo):
- Pool: `us-east-1_PflCYM8WM`
- Client: `7ls0a83u5u94vjb2g6t6mdenik`
- Credenciales: variables de entorno `TIKR_EMAIL` / `TIKR_PASSWORD`
- Token válido ~1h (se renueva automáticamente en cada run)
