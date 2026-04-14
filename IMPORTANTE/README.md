# Owner Earnings — Sistema Autónomo

Sistema de valoración basado en la fórmula de Owner Earnings de Warren Buffett.
Scraping de TIKR Pro → Cálculo de FCF + precio de compra intrínseco → Visualización React.

---

## Estructura

```
IMPORTANTE/
├── tikr_scraper.py        # Scraper TIKR Pro (genera los datos)
├── owner_earnings.py      # Calculadora Owner Earnings (modelo Buffett)
├── api_server.py          # Flask API — expone los endpoints
├── requirements.txt       # Dependencias Python
├── docs/                  # Datos generados por el scraper
│   └── tikr_earnings_data.json   ← generado al correr tikr_scraper.py
└── frontend/              # App React standalone (sin auth)
    ├── package.json
    ├── vite.config.ts     # proxy /api → localhost:5002
    └── src/
        ├── pages/OwnerEarnings.tsx   # página principal
        ├── components/               # UI components
        ├── lib/                      # utils + nl (narrativa)
        └── api/client.ts             # axios simple
```

---

## Requisitos

- **Python** ≥ 3.10
- **Node.js** ≥ 18
- **Cuenta TIKR Pro** (para el scraper)

---

## Instalación

### Python
```bash
cd IMPORTANTE/
pip install -r requirements.txt
```

### Frontend
```bash
cd IMPORTANTE/frontend/
npm install
```

---

## Uso — 3 pasos

### Paso 1: Generar los datos (solo la primera vez y cada semana)

Necesitas credenciales de TIKR Pro:
```bash
cd IMPORTANTE/
export TIKR_EMAIL="tu@email.com"
export TIKR_PASSWORD="tu_password"
python3 tikr_scraper.py --run
```

Esto genera `docs/tikr_earnings_data.json` (~2-3 MB, ~100 tickers).

Para testear un solo ticker antes del run completo:
```bash
python3 tikr_scraper.py --test MSFT
```

### Paso 2: Arrancar el servidor API

```bash
cd IMPORTANTE/
python3 api_server.py
```

Verifica que funciona:
```bash
curl http://localhost:5002/api/health
curl http://localhost:5002/api/owner-earnings/MSFT
```

### Paso 3: Arrancar el frontend

En otra terminal:
```bash
cd IMPORTANTE/frontend/
npm run dev
```

Abre el navegador en: **http://localhost:5173**

---

## Fórmula Owner Earnings (Buffett)

```
Owner Earnings = CFO − CapEx_mantenimiento
CapEx_mant     = min(|CapEx total|, D&A)
D&A            = EBITDA − EBIT
```

### Precio de compra objetivo
```
exit_price = FCF_por_acción_año_N × EV/FCF_objetivo − deuda_neta_por_acción
buy_price  = exit_price ÷ (1 + retorno_objetivo)^años
```

Los múltiplos objetivo se calculan con un descuento del 10–15% sobre la mediana histórica,
y son **editables en el frontend** → recálculo instantáneo sin llamar a la API.

### Señales
| Upside vs precio actual | Señal |
|------------------------|-------|
| ≥ +15% | **BUY** |
| 0% a +15% | **WATCH** |
| −20% a 0% | **HOLD** |
| < −20% | **OVERVALUED** |

---

## Endpoints API

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/health` | Estado del servidor + ruta del archivo de datos |
| GET | `/api/owner-earnings/<ticker>` | Análisis individual |
| GET | `/api/owner-earnings-batch` | Todos los tickers, ordenados por upside |

Parámetros opcionales:
- `target_return` (float, default `0.15`) — retorno anual objetivo
- `ev_fcf_target` (float, opcional) — múltiplo EV/FCF personalizado

---

## Documentación detallada

- `OWNER_EARNINGS_README.md` — modelo de valoración completo (paso a paso)
- `TIKR_SCRAPER.md` — documentación del scraper TIKR

---

## Notas

- El scraper funciona **únicamente con cuenta TIKR Pro** (autenticación AWS Cognito)
- `yfinance` es opcional: si falla la instalación, el modelo usa fallback NTM para EV/FCF
- El frontend no requiere autenticación — acceso directo sin login
- Para uso en producción, despliega `api_server.py` con gunicorn y el frontend con `npm run build`
