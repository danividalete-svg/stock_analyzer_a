# TIKR Pro Scraper — Documentación Técnica Completa

> Este documento explica **exactamente** cómo funciona `tikr_scraper.py` para que un analista
> o un LLM pueda entender el sistema completo, proponer mejoras o extenderlo.

---

## 1. Qué hace este scraper

`tikr_scraper.py` extrae datos financieros de **TIKR Pro** (plataforma de datos financieros
profesionales basada en S&P Capital IQ + Reuters / Refinitiv) para un universo curado de
~105 empresas de alta calidad. Corre **una vez a la semana** (domingos 05:23 UTC) vía
GitHub Actions y guarda todo en `docs/tikr_earnings_data.json`.

El objetivo final es tener datos fundamentales de alta calidad (no yfinance) para:
- Modelo de Owner Earnings / DCF en la app
- Breakdown de FCF con componentes individuales
- Estimados de consenso analistas (forward EPS, EBITDA, Revenue)
- Contexto cualitativo (transcripts, headlines, accionistas, filings SEC)

---

## 2. Universo de tickers

Definido en `curated_tickers.py`. ~105 empresas organizadas en 4 tiers:

| Tier | Criterio | Ejemplos |
|------|----------|---------|
| **TIER 1** ★★★★★ | Moat excepcional, retornos sobre capital sostenidos | VRSK, V, MA, COST, SPGI, RELX |
| **TIER 2** ★★★★☆ | Alta calidad, moat sólido | MSFT, KO, MSCI, ZTS, TMO, INTU |
| **TIER 3** ★★★☆☆ | Buena calidad, algo más cíclicos | AAPL, GOOGL, AMZN, NKE, UNH |
| **TIER 4** ★★☆☆☆ | Cuestionables, monitorización | Excluidos del run semanal por defecto |

El scraper por defecto usa `get_universe()` = TIER_1 + TIER_2 + TIER_3.

**Tickers especiales** (normalizados antes de buscar en TIKR):
```python
TIKR_TICKER_MAP = {
    'AI.PA':  'AI',      # Air Liquide en Paris
    'BRK-B':  'BRK/B',  # Berkshire Hathaway
    'CSU.TO': 'CSU',    # Constellation Software (Toronto)
    'LSEG.L': 'LSEG',   # London Stock Exchange Group (LSE)
    'AUTO.L': 'AUTO',   # Auto Trader Group (LSE)
    'G24.DE': 'G24',    # Scout24 (Xetra)
    'TNE.AX': 'TNE',    # Technology One (ASX)
    '4684.T': '4684',   # OBIC (Tokyo)
    ...
}
```

---

## 3. Arquitectura: 4 fases + autenticación

```
┌─────────────────────────────────────────────────────────────────┐
│  AUTH: AWS Cognito SRP → IdToken JWT (válido ~1h)               │
│  SESSION: requests.Session con headers Chrome 146 / macOS       │
└──────────────────┬──────────────────────────────────────────────┘
                   │
         ┌─────────▼─────────┐
         │  FASE 0: /lv       │  1 call batch → todos los modelos
         │  Modelos usuario   │  de valoración guardados en TIKR
         └─────────┬──────────┘
                   │
         ┌─────────▼─────────┐
         │  FASE 1: IDs       │  Algolia → cid + tid + ric_id
         │  (por ticker)      │  fallback: POST /trkdids
         └─────────┬──────────┘
                   │
         ┌─────────▼─────────┐
         │  FASE 2: /wlp      │  1 call batch → precio actual
         │  (batch 25)        │  + estimados NTM 6 métricas
         └─────────┬──────────┘
                   │
         ┌─────────▼──────────────────────────────────────────────┐
         │  FASE 3: por ticker (6 endpoints)                       │
         │  /transcripts_v2  → earnings calls + conferencias       │
         │  /tf              → financials históricos anuales       │
         │  /est             → consensus estimates forward         │
         │  /headlines       → noticias Reuters                   │
         │  /sigdevs         → eventos corporativos S&P CIQ       │
         │  /shareholders    → accionistas institucionales         │
         │  /listReports     → SEC filings + press releases        │
         └────────────────────────────────────────────────────────┘
```

---

## 4. Autenticación: AWS Cognito SRP

TIKR Pro usa **AWS Cognito** con el protocolo **SRP** (Secure Remote Password).
No es un login web estándar — requiere la librería `pycognito`.

```python
COGNITO_REGION    = 'us-east-1'
COGNITO_POOL_ID   = 'us-east-1_PflCYM8WM'
COGNITO_CLIENT_ID = '7ls0a83u5u94vjb2g6t6mdenik'
```

Variables de entorno requeridas:
- `TIKR_EMAIL` — email de la cuenta Pro
- `TIKR_PASSWORD` — contraseña

El token resultante (`IdToken` JWT) se usa en todos los payloads como campo `auth`.
Válido ~1 hora. El scraper completo tarda ~2-3h para 105 tickers, pero hay un **retry
automático del token** implícito porque se genera al inicio.

**Posible mejora**: refrescar el token a mitad del run si tarda >50 min.

---

## 5. Stealth: cómo evitamos rate limiting / ban

```python
DELAY_MIN        = 4.0   # segundos mínimos entre requests
DELAY_MAX        = 9.0   # segundos máximos
LONG_PAUSE_EVERY = 10    # cada 10 tickers
LONG_PAUSE_MIN   = 25.0  # pausa larga mínima
LONG_PAUSE_MAX   = 55.0  # pausa larga máxima
```

- Delays con **distribución beta** (más natural que uniforme): `betavariate(2, 3)`
- **Headers Chrome 146 macOS** exactos: User-Agent, sec-ch-ua, sec-fetch-*
- **Orden aleatorio** de tickers en cada run: `random.shuffle(tickers)`
- **Cache de IDs** en `docs/tikr_id_cache.json`: no re-resolvemos tickers ya conocidos
- **Cache de financieros** (`/tf`): si los datos tienen < 7 días, reutilizamos (datos anuales no cambian a diario)

---

## 6. Resolución de IDs: Algolia + fallback /trkdids

Para hacer requests a la API de TIKR necesitamos dos IDs por empresa:
- `cid` (company ID) — identifica la empresa
- `tid` (trading item ID) — identifica el instrumento/exchange concreto

**Paso primario: Algolia** (sin autenticación, clave pública)
```
URL: https://tjpay1dyt8-dsn.algolia.net/1/indexes/*/queries
Índice: tikr-terminal-v1
API Key: d88ea2aa3c22293c96736f5ceb5bab4e  (pública, sólo lectura)
```
Algolia devuelve en un solo call: cid, tid, exchangesymbol, companyname, y el
**Reuters RIC** (ej: `MSFT.O`) necesario para headlines/shareholders/sigdevs.

**Fallback: POST /trkdids** — endpoint autenticado de TIKR. Más lento, requiere token.

**IssuerOAPermID** (Reuters Open Access Permanent ID): necesario para `/listReports`.
Se obtiene con un segundo call a `/trkdids` usando cid+tid ya conocidos.

---

## 7. Fase 0: /lv — Modelos de valoración del usuario

```
POST https://api.tikr.com/lv
Body: {"auth": TOKEN, "v": "v1"}
```

Devuelve **todos los modelos de valoración** que el usuario tiene guardados en TIKR Pro,
agrupados por `cid`. Un modelo contiene:

| Campo | Descripción |
|-------|-------------|
| `target_price` | Precio objetivo calculado por el modelo |
| `irr_pct` | Tasa interna de retorno implícita |
| `eps_estimates` | `{"2026": 12.5, "2027": 14.0, ...}` — por año fiscal |
| `revenue_estimates` | Ídem para revenues |
| `ebit_estimates` | Ídem para EBIT |
| `revenue_cagr` | `{"1y": 8.2, "3y": 10.1, "5y": 9.4}` |
| `eps_cagr` | Ídem para EPS |

Los valores se extraen de `hubData.valuationOutput` dentro de `metadata` del modelo.
Las claves de los años tienen formato `"2026##FY"` — se parsean con `fy.split('##')[0]`.

---

## 8. Fase 2: /wlp — Precio actual + estimados NTM (batch)

```
POST https://api.tikr.com/wlp
Body: {"auth": TOKEN, "tickers": [["cid1","tid1"], ["cid2","tid2"], ...], "v": "v1"}
```

Un solo call para hasta 25 tickers. Devuelve:

**Precio** (campo `price[]`):
- `c` = close price
- `h` / `l` = high / low
- `mc` = market cap (en millones)
- `tev` = enterprise value (en millones)
- `sho` = shares outstanding
- `qiso` = currency ISO (USD, EUR, GBP...)

**NTM estimates** (campo `ntm[]` — Next Twelve Months):
```python
NTM_DID = {
    100180: 'ntm_revenue',          # Revenue NTM ($M)
    100187: 'ntm_ebitda',           # EBITDA NTM ($M)
    100215: 'ntm_ebit',             # EBIT NTM ($M)
    114221: 'ntm_fcf',              # Free Cash Flow NTM ($M)
    100173: 'ntm_eps',              # EPS normalizado NTM
    100201: 'ntm_eps_consensus',    # EPS consenso NTM
}
```

**Múltiplos calculados localmente** (función `_compute_ntm_multiples`):
- `ntm_ev_ebitda` = tev / ntm_ebitda
- `ntm_ev_revenue` = tev / ntm_revenue
- `ntm_ev_ebit` = tev / ntm_ebit
- `ntm_pe` = close / ntm_eps
- `ntm_fcf_yield_pct` = ntm_fcf / mc × 100

---

## 9. Fase 3a: /transcripts_v2 — Earnings calls + conferencias

```
POST https://api.tikr.com/transcripts_v2
Body: {"auth": TOKEN, "cid": "12345", "v": "v1"}
```

Tipos de evento relevantes:
- `48` = Earnings Call
- `51` = Conference / Investor Presentation

Extrae los **4 earnings calls más recientes** y **3 conferencias**, ordenados por fecha descendente.
El campo `mostimportantdateutc` es la fecha del evento.

Para el resumen se extraen: headline, date, keydevid, transcriptid, has_audio, has_transcript.

---

## 10. Fase 3b: /tf — Financieros históricos anuales

```
POST https://api.tikr.com/tf
Body: {"auth": TOKEN, "cid": CID_INT, "tid": TID_INT, "p": "1", "repid": 1, "v": "v1"}
```

- `p: "1"` = período anual (vs. "3" para trimestral)
- `repid: 1` = template estándar (hay templates específicos para bancos, seguradoras, etc.)

La respuesta tiene estructura:
```json
{
  "dates": [{"calendaryear": 2024, "periodtypeid": 1}, ...],
  "financials": [
    {"dataitemid": 28, "2024##FY": {"v": 245122.0, "u": 2}, ...},
    ...
  ]
}
```

- `periodtypeid == 1` = anual FY
- `u: 2` = millones USD (kept as-is)
- `u: 0` = ratio/porcentaje (stored as decimal)

### Métricas extraídas (`TF_ITEMS_OF_INTEREST`):

| dataitemid | Nombre amigable | Descripción |
|-----------|-----------------|-------------|
| 28 | `total_revenue` | Revenues — template estándar |
| 29 | `total_revenue` | Revenues — template aseguradoras |
| 10 | `gross_profit` | Gross Profit |
| 4051 | `ebitda` | EBITDA |
| 21 | `ebit` | Operating Income / EBIT |
| **32** | **`interest_expense`** | Net Interest Expense *(añadido 2026-04-13)* |
| **11** | **`interest_expense`** | Interest Expense ID alternativo *(añadido 2026-04-13)* |
| **14** | **`income_tax_expense`** | Income Tax Expense *(añadido 2026-04-13)* |
| 15 | `net_income` | Net Income |
| 142 | `eps_diluted` | Diluted EPS |
| 2006 | `cash_from_operations` | CFO |
| **2023** | **`wc_change`** | Cambio en Capital de Trabajo *(añadido 2026-04-13)* |
| 2021 | `capex` | CapEx (negativo en TIKR) |
| 1096 | `cash` | Cash & Equivalents |
| 4173 | `total_debt` | Total Debt |
| 1006 | `total_equity` | Total Common Equity |
| 4128 | `roe_pct` | Return on Equity % |
| 4094 | `net_margin_pct` | Net Income Margin % |
| 4047 | `ebitda_margin_pct` | EBITDA Margin % |
| 4193 | `net_debt_ebitda` | Net Debt / EBITDA |
| 342 | `shares_diluted` | Weighted Average Diluted Shares |
| 2164 | `buybacks` | Recompra de acciones (negativo = buyback) |

> **Nota importante**: IDs 32/11 (`interest_expense`), 14 (`income_tax_expense`) y 2023
> (`wc_change`) fueron añadidos el 2026-04-13. La primera vez que aparezcan en
> `tikr_earnings_data.json` será en el run del domingo siguiente.
> Hasta entonces, `owner_earnings.py` aproxima estos valores con fórmulas derivadas.

**Lógica de prioridad**: Si ID 28 (`total_revenue`) ya tiene datos, no se sobreescribe con
ID 29. Esto evita conflictos entre templates distintos para la misma métrica.

**Lookback**: últimos 7 años fiscales.

**CAGR de revenue**: calculado automáticamente en 3y, 5y, 7y desde los datos históricos.

---

## 11. Fase 3c: /est — Estimados consensus analistas

```
POST https://api.tikr.com/est
Body: {"auth": TOKEN, "cid": CID_INT, "tid": TID_INT, "p": "1", "v": "v1"}
```

Devuelve `dates[]`, `estimates[]` y `actuals[]`.

**Mapping de IDs para estimados (forward)**:
```python
EST_ITEMS = {
    100180: ('revenue',         0),  # $M
    100187: ('ebitda',          0),  # $M
    100215: ('ebit',            0),  # $M
    100250: ('net_income_norm', 0),  # $M
    100173: ('eps_norm',        3),  # per share
    100278: ('eps_gaap',        3),  # per share
    114221: ('fcf',             0),  # $M
    100177: ('n_analysts',      3),  # número de analistas
}
```

**Mapping de IDs para actuals (histórico)**:
```python
EST_ACTUALS = {
    100186: ('revenue',         0),
    100193: ('ebitda',          0),
    100221: ('ebit',            0),
    100256: ('net_income_norm', 0),
    100179: ('eps_norm',        3),
    100284: ('eps_gaap',        3),
    114220: ('fcf',             0),
}
```

> Nota: los IDs para forward y actuals son **distintos** — TIKR los separa en tablas diferentes.

**Algoritmo**: para cada `(year, dataitemid)` toma la entrada con `effectivedate` más reciente.
Esto garantiza usar siempre el consenso más actualizado.

**Revision flag** (`'up'` / `'down'` / `'stable'`): compara el EPS estimate más reciente vs.
el más antiguo disponible para el año siguiente. Cambio > 1% = `up`/`down`.

**Output**:
```json
{
  "current_year": 2026,
  "forward": {
    "2026": {"revenue": 280000.0, "ebitda": 110000.0, "eps_norm": 13.45, "fcf": 85000.0},
    "2027": {...},
    "2028": {...},
    "2029": {...}
  },
  "recent": {
    "2024": {"revenue": 245122.0, "ebitda": 96937.0, "eps_norm": 11.45, "fcf": 74300.0},
    "2025": {...}
  },
  "revision_flag": "up"
}
```

---

## 12. Fase 3d: /headlines — Noticias Reuters

```
POST https://api.tikr.com/headlines
Body: {"auth": TOKEN, "lang": ["ES", "EN"], "id": "MSFT.O"}
```

`id` está en formato Reuters RIC (ticker + sufijo de exchange, ej: `MSFT.O`, `AI.PA`).

**Construcción del RIC**:
```python
EXCHANGE_RIC = {
    'NasdaqGS': 'O', 'NasdaqGM': 'O', 'NasdaqCM': 'O',
    'NYSE': 'N', 'ARCA': 'N',
    'LSE': 'L', 'Xetra': 'DE', 'TSX': 'TO', 'ASX': 'AX', ...
}
# Resultado: tikrSymbol + "." + suffix → "MSFT.O"
```

Devuelve hasta 10 headlines: headline, datetime, language, source (Reuters), news_id.

---

## 13. Fase 3e: /shareholders — Accionistas institucionales

```
POST https://api.tikr.com/shareholders
Body: {"ticker": "MSFT.O", "auth": TOKEN}
```

Top 10 holders con: name, type (Institutional/Mutual Fund/...), style (Growth/Value/...),
orientation (Active/Passive), turnover_rating, pct_of_shares, shares_held, shares_value_usd,
shares_change_pct, holding_date.

También calcula `top_holders_active` y `top_holders_passive`.

---

## 14. Fase 3f: /sigdevs — Significant Developments (S&P CIQ)

```
POST https://api.tikr.com/sigdevs
Body: {"id": "MSFT.O", "auth": TOKEN}
```

Eventos corporativos relevantes de S&P Capital IQ. Topics numéricos de interés:

| Topic | Descripción |
|-------|-------------|
| 201 | Products / Services |
| 207 | M&A / Acquisitions |
| 210 | Officer Changes |
| 213 | Divestitures |
| 231 | IPO |
| 245 | Earnings Results |
| 253 | Strategic |
| 254 | Regulatory |

Devuelve hasta 15 eventos con: headline, description (500 chars), date, topics[], significance, front_page.

---

## 15. Fase 3g: /listReports — SEC filings + press releases

```
POST https://api.tikr.com/listReports
Body: {"auth": TOKEN, "id": "4295907168"}  # ← OA PermID, NO el RIC
```

**Importante**: usa el **Reuters Open Access PermID** (un número como `4295907168`),
**no** el formato RIC. Se obtiene de Algolia (`OAPermID`) o de `/trkdids` (`IssuerOAPermID`).

Clasifica los documentos en 3 categorías:
- `earnings_releases`: feed `Bridge` + formName contiene `"earnings"` — press releases de resultados
- `sec_filings`: feed `Edgar` + formType en `{10-Q, 10-K, 8-K}`
- `presentations`: PDFs de investor day / quarterly presentations

---

## 16. Output: estructura de tikr_earnings_data.json

```json
{
  "generated_at": "2026-04-13T05:45:00Z",
  "total": 103,
  "errors": ["AWK", "BRK-B"],
  "data": {
    "MSFT": {
      "ticker": "MSFT",
      "tikr_ticker": "MSFT",
      "cid": "12345",
      "tid": "67890",
      "ric_id": "MSFT.O",
      "company_name": "Microsoft Corp.",
      "price": {"c": 380.5, "mc": 2820000, "tev": 2750000, "sho": 7420, "curr": "USD"},
      "ntm": {"ntm_revenue": 280000, "ntm_ebitda": 115000, "ntm_fcf": 85000, "ntm_eps": 13.45},
      "multiples": {"ntm_ev_ebitda": 23.9, "ntm_pe": 28.3, "ntm_fcf_yield_pct": 3.01},
      "valuation_model": {
        "target_price": 450.0,
        "irr_pct": 12.5,
        "eps_estimates": {"2026": 13.45, "2027": 15.20},
        "revenue_estimates": {"2026": 278000, "2027": 305000},
        "revenue_cagr": {"1y": 8.2, "3y": 10.1},
        "eps_cagr": {"1y": 12.0, "3y": 14.5}
      },
      "financials_history": {
        "annual_years": [2024, 2023, 2022, 2021, 2020, 2019, 2018],
        "metrics": {
          "total_revenue":       {2024: 245122.0, 2023: 211915.0, ...},
          "ebitda":              {2024: 126048.0, 2023: 105933.0, ...},
          "ebit":                {2024: 109433.0, 2023: 88523.0,  ...},
          "interest_expense":    {2024: 1243.0,   2023: 1187.0,   ...},
          "income_tax_expense":  {2024: 10666.0,  2023: 9197.0,   ...},
          "net_income":          {2024: 88136.0,  2023: 72361.0,  ...},
          "cash_from_operations":{2024: 118548.0, 2023: 87582.0,  ...},
          "wc_change":           {2024: 4230.0,   2023: 2150.0,   ...},
          "capex":               {2024: -44482.0, 2023: -28107.0, ...},
          "total_debt":          {2024: 97071.0,  2023: 78397.0,  ...},
          "buybacks":            {2024: -17254.0, 2023: -22245.0, ...},
          ...
        },
        "revenue_cagr": {"3y": 11.2, "5y": 13.5, "7y": 12.8}
      },
      "analyst_estimates": {
        "current_year": 2026,
        "forward": {
          "2026": {"revenue": 279350.0, "ebitda": 118200.0, "eps_norm": 13.45, "fcf": 86500.0},
          "2027": {"revenue": 308000.0, "ebitda": 132000.0, "eps_norm": 15.80, "fcf": 97000.0}
        },
        "recent": {
          "2024": {"revenue": 245122.0, "ebitda": 96937.0, "eps_norm": 11.45}
        },
        "revision_flag": "up"
      },
      "transcripts": {...},
      "earnings_summary": {
        "latest_earnings_headline": "Microsoft Q2 FY2025 Earnings Call",
        "latest_earnings_date": "2025-01-29",
        "earnings_history": [...]
      },
      "headlines": [
        {"headline": "Microsoft Azure revenue rises...", "datetime": "2026-04-10T14:30:00", ...}
      ],
      "sigdevs": [
        {"headline": "Microsoft to acquire...", "date": "2026-03-15", "topics": ["M&A"]}
      ],
      "shareholders": {
        "total_shareholder_count": 5420,
        "top_holders": [{"name": "Vanguard Group", "pct_of_shares": 8.3, ...}],
        "top_holders_active": 6,
        "top_holders_passive": 4
      },
      "reports": {
        "earnings_releases": [{"form_name": "Earnings Release", "period_end": "2025-12-31", ...}],
        "sec_filings": [{"form_type": "10-Q", "period_end": "2025-12-31", ...}],
        "presentations": [...]
      },
      "fetched_at": "2026-04-13T06:15:32Z"
    }
  }
}
```

---

## 17. Qué consume este output

El JSON generado lo consume principalmente `owner_earnings.py`:

```python
td = tikr_data.get(ticker, {})

# Financieros históricos
fh = td.get('financials_history', {})
metrics = fh.get('metrics', {})
ebitda_yr     = metrics.get('ebitda', {}).get(year)
interest_yr   = metrics.get('interest_expense', {}).get(year)   # ← nuevo desde Apr 2026
tax_yr        = metrics.get('income_tax_expense', {}).get(year) # ← nuevo
wc_change_yr  = metrics.get('wc_change', {}).get(year)          # ← nuevo
capex_yr      = metrics.get('capex', {}).get(year)
cfo_yr        = metrics.get('cash_from_operations', {}).get(year)

# Estimados forward para DCF
ae = td.get('analyst_estimates', {})
forward = ae.get('forward', {})
fcf_2026 = forward.get('2026', {}).get('fcf')   # FCF consenso en $M

# Datos NTM para múltiplos actuales
ntm = td.get('ntm', {})
ntm_fcf = ntm.get('ntm_fcf')   # FCF NTM en $M (fallback si no hay forward año-a-año)

# Nombre empresa
company_name = td.get('company_name', '')
```

---

## 18. Casos especiales y limitaciones conocidas

| Situación | Comportamiento actual |
|-----------|----------------------|
| Ticker no encontrado en Algolia ni /trkdids | Se añade a `errors[]`, no aparece en output |
| Financieros ya < 7 días en output previo | `/tf` se salta (cache) — ahorra ~2 requests por ticker |
| RIC no disponible (exchange exótico) | Headlines/Shareholders/Sigdevs/Reports vacíos |
| OA PermID no disponible | `/listReports` vacío |
| Template alternativo (repid=2,3 para bancos) | No implementado — repid siempre = 1 |
| Token expira a mitad del run (>1h) | Error en requests tardíos — no hay refresh automático |
| Tickers UK (.L): yfinance devuelve GBX (pence) | Corregido en `owner_earnings.py` con `/100.0` |

---

## 19. Posibles mejoras (con contexto técnico)

1. **Refresh automático del token**: si el run dura >50 min, el JWT expira. Solución: capturar
   `401` en los requests y llamar `get_fresh_token()` + actualizar `session.headers`.

2. **Templates alternativos para bancos/aseguradoras** (`repid=2` o `3`): actualmente
   `repid=1` (template estándar). Para BRK-B, CB, AJG, MMC habría que detectar el tipo de
   empresa y usar el `repid` correcto para obtener métricas específicas del sector.

3. **Estimados trimestrales** (`p: "3"` en `/est`): actualmente sólo anuales. Los trimestrales
   permitirían calcular beat/miss del último quarter.

4. **Más IDs en `TF_ITEMS_OF_INTEREST`**: `D&A` separado del EBITDA (actualmente se deriva como
   EBITDA-EBIT), `SBC` (stock-based compensation), `maintenance_capex` explícito si existe ID.

5. **Leer el transcript completo**: actualmente sólo guardamos metadata (keydevid, transcriptid).
   El texto del transcript se puede obtener con otro endpoint (no implementado).

6. **Manejo de monedas no-USD**: el campo `curr` del precio indica la moneda. Las métricas
   financieras de `/tf` para empresas no-US vienen en la moneda local de TIKR. Actualmente
   se asume que `owner_earnings.py` maneja la conversión.

---

## 20. Cómo ejecutar localmente

```bash
# Prerequisitos
pip install requests pycognito boto3

# Variables de entorno
export TIKR_EMAIL="tu_email@ejemplo.com"
export TIKR_PASSWORD="tu_contraseña"

# Test un ticker
python3 tikr_scraper.py --test MSFT

# Test varios tickers
python3 tikr_scraper.py --tickers MSFT,V,COST

# Run completo universo (TIER 1+2+3, ~105 tickers, ~2-3h)
python3 tikr_scraper.py --run

# Solo TIER 1 (22 tickers, ~30min)
python3 tikr_scraper.py --run --tier 1
```

Output: `docs/tikr_earnings_data.json` (se va guardando ticker a ticker, no al final).

---

## 21. Dependencias

```
requests      — HTTP client
pycognito     — AWS Cognito SRP authentication
boto3         — AWS SDK (usado por pycognito para Cognito)
```

No requiere Playwright ni Selenium — todo es API REST directa.
