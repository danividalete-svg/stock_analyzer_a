# TIKR Sabiduria

Esta carpeta aisla el conocimiento con mas valor del repositorio alrededor del scraping de TIKR y del sistema `owner_earnings`.

## Estructura

### `current_system/`
Version principal y mas completa encontrada en la raiz del repo.

Incluye:
- `tikr_scraper.py`
- `TIKR_SCRAPER.md`
- `TIKR_SCRAPER_README.md`
- `owner_earnings.py`
- `OWNER_EARNINGS_README.md`
- `curated_tickers.py`
- `ticker_api.py`
- `frontend/src/pages/OwnerEarnings.tsx`
- `frontend/src/api/client.ts`
- `.github/workflows/tikr-enrichment.yml`
- `docs/tikr_earnings_data.json`
- `docs/owner_earnings_batch.json`

Motivo: aqui esta el scraper TIKR vivo, la documentacion tecnica mas detallada, el modelo `owner_earnings`, la pagina React que lo usa y el workflow semanal que automatiza la extraccion.

### `legacy_importante/`
Copia integra de `IMPORTANTE/`, que funciona como capsula autonoma del sistema.

Incluye:
- scraper TIKR alternativo
- variante legacy de `owner_earnings`
- `api_server.py`
- frontend standalone
- docs y requirements del modulo aislado
- duplicados historicos como `tikr_scraper (1).py` y `TIKR_SCRAPER (1).md`

Motivo: aunque la raiz contiene versiones mas evolucionadas, `IMPORTANTE/` conserva una extraccion previa ya empaquetada para portar el sistema a otro repo con menos dependencias del proyecto principal.

## Lectura recomendada

1. Empieza por `current_system/tikr_scraper.py`
2. Sigue con `current_system/TIKR_SCRAPER_README.md`
3. Revisa `current_system/owner_earnings.py`
4. Revisa `current_system/frontend/src/pages/OwnerEarnings.tsx`
5. Usa `legacy_importante/` como referencia de portabilidad standalone

## Notas utiles

- `current_system/tikr_scraper.py` es distinto de la variante en `legacy_importante/` y parece mas avanzado.
- `current_system/owner_earnings.py` tambien es mas completo que su variante legacy.
- `TIKR_SCRAPER.md` y `OWNER_EARNINGS_README.md` existen tanto en raiz como en `IMPORTANTE/`; se conservan ambas copias para no perder contexto historico.
- `docs/tikr_id_cache.json` no se copio porque no existia en esta revision del repo.
