# Owner Earnings Model — Documentación Técnica Completa

> Este documento explica **exactamente** cómo funciona el modelo de valoración Owner Earnings
> del sistema, desde los datos de entrada hasta el precio de compra mostrado en el frontend.
> Diseñado para que un analista o LLM pueda entender el sistema y proponer mejoras.

---

## 1. Qué hace este modelo

`owner_earnings.py` calcula un **precio de compra intrínseco** para cada empresa del universo
curado, respondiendo a la pregunta: _¿A qué precio debo comprar hoy para conseguir un X%
de retorno anual si vendo en el año N al múltiplo histórico?_

El modelo es un DCF simplificado basado en Free Cash Flow con las siguientes características:
- Usa datos de **TIKR Pro** (histórico) + estimados de consenso analistas (forward)
- Calcula precio objetivo **por año** (2026E, 2027E, 2028E, 2029E) con 3 métodos de valoración
- Los múltiplos objetivo son **editables en el frontend** — el usuario puede recalcular sin API
- Para tickers sin estimados anuales, proyecta desde el FCF NTM con CAGR histórico

---

## 2. Archivos involucrados

| Archivo | Rol |
|---------|-----|
| `owner_earnings.py` | Toda la lógica del modelo (Python) |
| `docs/tikr_earnings_data.json` | Fuente de datos (generado por `tikr_scraper.py` cada domingo) |
| `ticker_api.py` | Expone endpoints Flask: `/api/owner-earnings/<ticker>` y `/api/owner-earnings-batch` |
| `frontend/src/pages/OwnerEarnings.tsx` | UI completa: tabla batch + detalle por ticker |
| `frontend/src/api/client.ts` | `fetchOwnerEarnings(ticker)` / `fetchOwnerEarningsBatch()` |

---

## 3. Fórmula FCF

### Método principal: CFO-based (más robusto)
```
Owner Earnings = CFO − CapEx_mantenimiento
CapEx_maint    = min(|CapEx total|, D&A)
D&A            = EBITDA − EBIT
```

La lógica de `CapEx_maint = min(|CapEx|, D&A)` distingue inversión en mantenimiento
de inversión en crecimiento: el exceso de CapEx sobre D&A es expansión voluntaria,
no necesaria para mantener la posición competitiva.

### Método secundario: Template formula (para display y transparencia)
```
Template FCF = EBITDA − CapEx_maint − Interest − Taxes + ΔWC
```

Los componentes tienen prioridad de fuente:
| Componente | Fuente 1 (exacta) | Fuente 2 (derivada) | Fuente 3 (fallback) |
|-----------|-------------------|--------------------|--------------------|
| Interest | TIKR ID 32/11 | `total_debt × 4%` | `(EBIT-NI) × 35%` |
| Income Tax | TIKR ID 14 | `max(0, EBIT - interest - NI)` | — |
| ΔWC | TIKR ID 2023 | `CFO - NI - D&A` | `0.0` |

> **Nota**: Los IDs 32, 11, 14 y 2023 de TIKR fueron añadidos al scraper el 2026-04-13.
> Hasta el próximo run dominical, estos valores se derivan (marcados como `"estimated"` / `"derived"`).

### Prioridad de fuente para valoración
```python
if est_fcf:          # TIKR actuals de /est (más preciso, últimos 3 años)
    oe = est_fcf;    source = "tikr_actuals"
elif cfo:            # CFO - CapEx_maint (robusto, histórico completo)
    oe = cfo - capex_maint; source = "cfo_based"
else:                # Template formula (cuando no hay CFO)
    oe = template_fcf; source = "template"
```

Los tres métodos son matemáticamente equivalentes cuando los componentes se derivan
de los mismos datos. La diferencia solo importa con datos exactos de Interest/Tax/ΔWC
de TIKR.

---

## 4. Flujo de cálculo paso a paso

### Paso 1: Histórico (últimos 7 años)
Para cada año fiscal disponible en TIKR:
1. Extraer: `net_income`, `ebitda`, `ebit`, `capex`, `shares_diluted`, `cfo`, `total_revenue`
2. Calcular `D&A = ebitda - ebit`
3. Calcular `capex_maint = min(|capex|, D&A)`
4. Calcular componentes template (interest, tax, ΔWC) con jerarquía de fuentes
5. Seleccionar `owner_earnings` según prioridad tikr_actuals > cfo_based > template
6. Guardar en `historical_fcf[year]` y `fcf_breakdown[year]` (desglose completo)

### Paso 2: Múltiplo EV/FCF de referencia
Se calcula la **mediana histórica** usando precios anuales reales de yfinance:
```python
for yr in years:
    mc_yr = precio_cierre_yr × shares_yr
    ev_yr = mc_yr + (total_debt_yr - cash_yr)
    multiple = ev_yr / owner_earnings_yr
median_ev_fcf = mediana(multiples)
```

Fallbacks si no hay precios históricos:
1. `100 / ntm_fcf_yield_pct` (invertir el yield NTM)
2. `tev / ntm_fcf` (múltiplo NTM directo)
3. `25.0` (default conservador)

### Paso 3: Múltiplos objetivo (editables)
Los múltiplos por defecto se calculan con un descuento del 10-15% sobre la mediana:
```python
ev_fcf_target   = median_ev_fcf × 0.90   # -10% margen de seguridad
per_target      = ntm_pe × 0.85          # -15% sobre P/E NTM
ev_ebitda_target = ntm_ev_ebitda × 0.85  # -15% sobre EV/EBITDA NTM
```
El usuario puede editarlos en el frontend → recálculo instantáneo sin API.

### Paso 4: Forward FCF (2026E–2029E)
Para cada año en los estimados de analistas de TIKR (`/est`):
```python
fcf_m = est.get("fcf")                          # consenso directo, si existe
if not fcf_m:
    fcf_m = est.get("ebitda") × conv_median      # EBITDA × ratio FCF/EBITDA histórico
```
`conv_median` = mediana histórica de FCF/EBITDA (si hay 3+ años con ambos datos).

Proyección de shares: aplica la mediana histórica de cambio de dilución/buyback.
Proyección de net debt: `net_debt_new = max(0, net_debt_old - fcf × 30%)` (asume 30%
del FCF va a desapalancamiento).

### Paso 4b: Fallback NTM (cuando no hay estimados anuales)
Si `forward_fcf` queda vacío después del paso 4 pero hay `ntm_fcf`:
```python
fcf_growth = CAGR_3y_historico (clamped -5% a +25%)
for i in range(4):
    fcf_proyectado = ntm_fcf × (1 + fcf_growth)^i
    forward_fcf[year]["projected"] = True  # marca como no-consenso
```

### Paso 5: Precio objetivo por año y método
Para cada año forward:
```python
# Método 1: EV/FCF
precio_ev_fcf = fcf_per_share × ev_fcf_target − net_debt_per_share

# Método 2: P/E (solo si hay EPS consenso)
precio_per = eps_norm × per_target

# Método 3: EV/EBITDA (solo si hay EBITDA consenso)
mc_implied = ebitda_fwd × ev_ebitda_target − net_debt
precio_ev_ebitda = mc_implied / shares_projected

# Promedio de métodos disponibles
precio_average = media(métodos_con_datos)
```

### Paso 6: Precio de compra (buy_price)
```python
exit_price = price_targets[último_año]["ev_fcf"]  # prioridad EV/FCF
buy_price  = exit_price / (1 + target_return)^years_to_exit
upside_pct = (buy_price / current_price − 1) × 100
```

### Señal de inversión
```
upside ≥ +15%  → BUY
upside ≥   0%  → WATCH
upside ≥ -20%  → HOLD
upside  < -20% → OVERVALUED
```

---

## 5. Correcciones de moneda (UK stocks)

yfinance devuelve precios en **GBX (peniques)** para tickers LSE (`.L`), mientras TIKR
almacena los financieros en **GBP (libras, millones)**. Factor de corrección: ÷100.

```python
gbx_to_gbp = ticker.endswith('.L')
price = raw_price / 100.0 if gbx_to_gbp else raw_price
```

Tickers afectados: `AUTO.L`, `ITRK.L`, `LSEG.L`, `EXPN.L`.

Sin esta corrección, el precio de compra calculado sería ~100x mayor de lo real
(el bug original mostraba AUTO.L con buy_price de $16,750).

---

## 6. Endpoints de la API (ticker_api.py)

### GET `/api/owner-earnings/<ticker>`
```
Parámetros opcionales:
  target_return  (float, default 0.15) — retorno anual objetivo, ej: 0.12 para 12%
  ev_fcf_target  (float, opcional)     — múltiplo EV/FCF personalizado
```

### GET `/api/owner-earnings-batch`
```
Parámetros opcionales:
  target_return  (float, default 0.15)
```
Devuelve todos los tickers del universo TIKR ordenados por `upside_pct` descendente,
filtrando los que no tienen `buy_price` (NO_DATA: AWK, BRK-B, ERIE y similares sin FCF en TIKR).

---

## 7. Output completo del modelo

```json
{
  "ticker": "VRSK",
  "company_name": "Verisk Analytics",
  "current_price": 285.50,
  "market_cap": 42300.0,
  "tev": 47100.0,

  "historical_fcf": { "2024": 1850.2, "2023": 1650.1, "2022": 1420.5, ... },
  "historical_fcf_per_share": { "2024": 12.35, "2023": 10.80, ... },

  "fcf_breakdown": {
    "2024": {
      "revenue": 3700.0,
      "ebitda": 1980.0, "ebitda_margin": 53.5,
      "dna": 320.0,
      "ebit": 1660.0, "ebit_margin": 44.9,
      "interest": 185.0, "interest_src": "tikr",
      "income_tax": 285.0, "tax_src": "tikr",
      "pre_tax_income": 1475.0,
      "net_income": 1190.0, "net_margin": 32.2,
      "delta_wc": 45.0, "wc_src": "tikr",
      "cfo": 1870.0,
      "capex": -280.0, "capex_maint": 280.0,
      "template_fcf": 1275.0,
      "owner_earnings": 1590.0,
      "source": "cfo_based"
    }
  },

  "capex_pct_sales_median": 7.8,
  "median_ev_fcf": 28.4,
  "ntm_fcf_yield_pct": 3.9,
  "ntm_pe": 32.1,
  "ntm_ev_ebitda": 24.5,
  "ev_fcf_target": 25.6,
  "per_target": 27.3,
  "ev_ebitda_target": 20.8,
  "target_return_pct": 15.0,

  "forward_fcf": {
    "2026": { "fcf": 1980.0, "fcf_per_share": 13.45 },
    "2027": { "fcf": 2180.0, "fcf_per_share": 14.90 },
    "2028": { "fcf": 2390.0, "fcf_per_share": 16.42 },
    "2029": { "fcf": 2580.0, "fcf_per_share": 17.85 }
  },
  "forward_net_debt": { "2026": 4200.0, "2027": 3550.0, "2028": 2830.0, "2029": 2060.0 },
  "forward_shares": { "2026": 147.2, "2027": 146.3, "2028": 145.4, "2029": 144.5 },
  "forward_estimates": {
    "2026": { "eps_norm": 9.80, "ebitda": 2150.0 },
    "2027": { "eps_norm": 11.20, "ebitda": 2380.0 }
  },

  "price_targets": {
    "2026": { "ev_fcf": 315.2, "per": 267.5, "ev_ebitda": 289.4, "average": 290.7 },
    "2027": { "ev_fcf": 352.8, "per": 305.8, "ev_ebitda": 326.1, "average": 328.2 },
    "2028": { "ev_fcf": 391.5, "per": null,  "ev_ebitda": 362.8, "average": 377.2 },
    "2029": { "ev_fcf": 428.7, "per": null,  "ev_ebitda": null,  "average": 428.7 }
  },

  "buy_price": 213.4,
  "exit_price": 428.7,
  "exit_year": 2029,
  "years_to_exit": 4,
  "upside_pct": -25.2,
  "safety_margin_pct": 25.3,
  "signal": "OVERVALUED"
}
```

---

## 8. Tickers con NO_DATA

Tres tickers del universo no generan `buy_price` porque TIKR no tiene datos de FCF
compatibles con el modelo:

| Ticker | Razón |
|--------|-------|
| `AWK` | Utility — contabilidad regulatoria, CFO no refleja FCF libre |
| `BRK-B` | Holding — FCF de Berkshire no es comparable a empresas operativas |
| `ERIE` | Seguradora — modelo de negocio basado en float, no en FCF operativo |

Para estas empresas, el modelo correcto sería P/BV o rendimiento combinado (underwriting + inversión).

---

## 9. Frontend: cómo se pinta (OwnerEarnings.tsx)

### Tabla batch
- Llama a `/api/owner-earnings-batch` al cargar la página
- Muestra: Ticker, Empresa, Precio actual, Buy Price, Upside%, Señal, FCF Yield NTM
- Badge de señal: BUY (verde), WATCH (amarillo), HOLD (gris), OVERVALUED (rojo)
- Click en fila → abre vista de detalle

### Vista de detalle (expandida por ticker)
**Hero card** (izquierda): precio actual, buy price, upside%, señal, años al exit
**Parámetros editables**: 4 inputs (target return %, EV/FCF, P/E, EV/EBITDA target)
  → función `recompute()` recalcula todo localmente sin llamada API

**Tabla FCF Breakdown** (ancho completo): muestra año a año con las 12 columnas del template:
Revenue → EBITDA → D&A → EBIT → Interest (~) → Tax (~) → Pre-tax → NI → ΔWC (~) → CFO → CapEx → Owner Earnings
`~` = valor estimado/derivado (no exacto de TIKR todavía)

**Tabla Price Targets**: por año (2026E–2029E), columnas EV/FCF | P/E | EV/EBITDA | Avg | CAGR
CAGR = `(avg_price / current_price)^(1/años) − 1` = retorno anual si se compra hoy al precio actual

### Función recompute() (recálculo local sin API)
```typescript
function recompute(data, evFcfT, perT, evEbT, returnT): ComputedTargets {
  // Itera forward_fcf para recalcular price_targets con nuevos múltiplos
  // Usa forward_shares, forward_net_debt, forward_estimates del payload original
  // Devuelve: { priceTargets, exitPrice, buyPrice, upsidePct, signal }
}
```
Esto espeja exactamente la lógica de Python en el frontend para respuesta instantánea.

---

## 10. Posibles mejoras

1. **Múltiplo de salida configurable por empresa**: actualmente usa el último año disponible
   como exit year para todos. Podría usar el año con mejor ratio calidad/visibilidad
   (ej: 2027E si hay 10+ analistas, 2026E si solo hay 3).

2. **Ponderación de los 3 métodos**: actualmente es media simple. Podría ponderar por
   disponibilidad de analistas (`n_analysts` viene del campo `100177` en `/est`).

3. **Escenarios bear/base/bull**: el modelo actual es punto único. Con la desviación
   estándar de los estimados (TIKR puede dar el rango alto/bajo) se podría mostrar
   un intervalo de confianza en el buy_price.

4. **Normalización del FCF**: para empresas con FCF volátil (ciclicidad), usar la mediana
   de 5 años en vez del último año como base del forward FCF.

5. **Reinversión explícita**: el modelo actual asume que el FCF disponible es el FCF total.
   En realidad, empresas con alto ROIC reinvierten parte — modelar la tasa de reinversión
   explícitamente daría un DCF más preciso.

6. **Templates por sector**: bancos y aseguradoras (BRK-B, CB, MMC, AON) deberían usar
   ROE × BV growth en vez de EV/FCF. Actualmente se excluyen o dan señales incorrectas.
