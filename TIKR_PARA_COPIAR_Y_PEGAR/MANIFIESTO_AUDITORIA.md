# Manifiesto de auditoria TIKR

Este archivo deja constancia de la comprobacion manual realizada para asegurarnos de que la extraccion contiene todo lo importante relacionado con el scraping de TIKR y el sistema `owner_earnings`.

## Archivos nucleares encontrados y copiados

### Scraper TIKR y documentacion
- `tikr_scraper.py`
- `TIKR_SCRAPER.md`
- `TIKR_SCRAPER_README.md`
- `curated_tickers.py`
- `.github/workflows/tikr-enrichment.yml`
- `.github/workflows/daily-analysis.yml`
- `requirements.txt`

### Datos y salidas directas del scraper
- `docs/tikr_earnings_data.json`
- `docs/owner_earnings_batch.json`

### Modelo Owner Earnings y su exposicion
- `owner_earnings.py`
- `OWNER_EARNINGS_README.md`
- `ticker_api.py`
- `thesis_generator.py`

### Frontend conectado al sistema
- `frontend/src/pages/OwnerEarnings.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/App.tsx`
- `frontend/src/components/TopBar.tsx`
- `frontend/src/lib/nav.ts`

### Capsula autonoma legacy preservada
- copia integra de `IMPORTANTE/`

## Archivos detectados relacionados pero no tratados como nucleo independiente

### Generados o derivados
- `docs/app/assets/OwnerEarnings-*.js`
- `docs/app/assets/index-*.js`
- `docs/overview.html`

Motivo: son artefactos compilados o de presentacion. No anaden sabiduria fuente por encima del codigo y docs ya copiados.

### Referencias de integracion secundaria
- `cerebro.py`

Motivo: consume datos TIKR, pero no forma parte del scraping ni del modulo portable principal. Se puede recuperar despues si hiciera falta una integracion mas profunda.

### Archivos con nombre parecido pero de otro ambito
- `earnings_calendar.py`
- `frontend/src/pages/EarningsCalendar.tsx`
- `sec_13f_scraper.py`
- `insiders/openinsider_scraper.py`
- `data/earnings/earnings_cache.json`

Motivo: no pertenecen al scraper TIKR ni al sistema `owner_earnings`, aunque compartan terminos como `earnings` o `scraper`.

## Resultado de la auditoria

Conclusion: la carpeta `TIKR_SABIDURIA/` contiene el conocimiento importante del scraping TIKR encontrado en este repo, tanto en su forma actual integrada como en su variante legacy autonoma.

Si en el futuro quieres una extraccion todavia mas agresiva, el siguiente paso seria anadir un tercer bloque `integration_secondary/` con consumidores como `cerebro.py`.
