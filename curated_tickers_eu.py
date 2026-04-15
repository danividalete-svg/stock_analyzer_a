#!/usr/bin/env python3
"""
CURATED EUROPEAN TICKER UNIVERSE
~58 empresas europeas de alta calidad organizadas por solidez del moat.

Mismos criterios que curated_tickers.py (universo US).
Para uso con: european_value_scanner.py --curated

Mercados cubiertos:
  .PA  Euronext Paris          (Francia)
  .L   London Stock Exchange   (Reino Unido)
  .DE  XETRA                   (Alemania)
  .AS  Euronext Amsterdam      (Países Bajos)
  .SW  SIX Swiss Exchange      (Suiza)
  .MI  Borsa Italiana          (Italia)
  .MC  BME                     (España)
  .CO  Nasdaq Copenhagen       (Dinamarca)  ← nórdico
  .ST  Nasdaq Stockholm        (Suecia)     ← nórdico
  .HE  Nasdaq Helsinki         (Finlandia)  ← nórdico
  .HK  Hong Kong Stock Exchange             ← sección China separada

Criterio por tier (igual que el universo US):
  Tier 1 — "Aptas para all-in apalancado": ingresos >80% recurrentes,
            moat irreplicable, anti-cíclico, pricing power probado.
  Tier 2 — "Posición significativa con gestión": moat sólido,
            puede tener ciclicidad moderada o exposición geográfica acotada.
  Tier 3 — "Solo posición táctica reducida": moat real con matices,
            valoración exigente, ciclicidad o ventaja más estrecha.
  Tier 4 — "Excluir de cartera apalancada": valoración extrema,
            moat en deterioro, ciclicidad profunda o riesgo regulatorio elevado.

Nota sobre duplicados con curated_tickers.py:
  Varias empresas del universo US aparecen aquí como tickers nativos europeos
  (ej. HESAY → RMS.PA, WTKWY → WKL.AS). Se incluyen porque el EU scanner
  obtiene datos EUR/GBP/CHF con mejor calidad para el mercado nativo.

Source: Análisis curado con los mismos parámetros que curated_tickers.py (Abril 2026)
"""

# ── TIER 1 — Élite (★★★★★) ────────────────────────────────────────────────────
# Fosos defensivos excepcionales. Moat irreplicable, ingresos >80% recurrentes,
# pricing power demostrado, anti-cíclico. Las mejores de Europa en su categoría.
# Nativos de empresas ya confirmadas Tier 1 en curated_tickers.py (US ADRs).

TIER_1_EU = [
    'RMS.PA',    # Hermès International — ultra-lujo, Birkin como activo refugio,
                 # listas de espera 2-4 años, margen operativo >40%, caja neta €12B+
    'WKL.AS',    # Wolters Kluwer — datos regulatorios/compliance/fiscal, 83% recurrente,
                 # datos acumulados 1 siglo, integrado en flujos de trabajo legales/sanitarios
    'AI.PA',     # Air Liquide — gases industriales, contratos 20-25 años con pago mínimo,
                 # red de tuberías irreplicable, duopolio global con Linde
]

# ── TIER 2 — Alta convicción (★★★★☆) ─────────────────────────────────────────
# Negocios de alta calidad con moats sólidos. Pueden tener ciclicidad moderada
# o dependencia del crecimiento futuro. Posición significativa con gestión activa.

TIER_2_EU = [
    # ── Nativos de empresas ya en curated_tickers.py como ADRs ──────────────────
    'OR.PA',       # L'Oréal — beauty global #1, 36 marcas en todos los segmentos de precio,
                   # efecto "lápiz de labios" anti-recesivo documentado (ADR: LRLCY)
    'LSEG.L',      # London Stock Exchange Group — infraestructura datos financieros EU,
                   # Refinitiv data platform, Eurex clearing, 70%+ ingresos recurrentes
    'DB1.DE',      # Deutsche Börse — Eurex clearing monopoly EU (80%+ cuota derivados),
                   # Clearstream custodia, datos Stoxx/DAX, ingresos ligados a volatilidad
                   # (ADR: DBOEY)
    'GIVN.SW',     # Givaudan — fragancias/sabores global #1 (25-27% cuota mundial),
                   # co-desarrollo propietario con P&G/Unilever/Nestlé, retención >95%
                   # (ADR: GVDNY)
    'COLO-B.CO',   # Coloplast — ostomía/continencia/heridas crónicas, switching costs médicos
                   # extremos (paciente adaptado no cambia), condiciones permanentes/crónicas
                   # (ADR: CLPBY)

    # ── Nuevas incorporaciones: compounders europeos sin cobertura en universo US ──
    'MC.PA',       # LVMH — conglomerado lujo 75+ marcas (Louis Vuitton, Dior, Moët, Hennessy),
                   # Arnault capital allocation excepcional, pricing power multi-categoría,
                   # pero más cíclico que Hermès (acceso más amplio = más exposición al ciclo)
    'NOVO-B.CO',   # Novo Nordisk — farmacéutica danesa, liderazgo GLP-1 (Ozempic/Wegovy),
                   # pipeline diabetes/obesidad/NASH, pricing power farmacéutico,
                   # riesgo: competencia Eli Lilly (Mounjaro), patent cliff horizonte 2030+
    'IMCD.AS',     # IMCD Group — distribución química specialty, asset-light (no inventario
                   # en balance), co-formulación con clientes = switching costs, ROIC >30%,
                   # modelo similar a Roper Technologies en distribución especializada
    'DPLM.L',      # Diploma PLC — serial acquirer UK de distribución especializada
                   # (médico-estético, sellos/juntas industriales, electrónica), modelo
                   # Constellation Software/Roper: alta retención, reinversión en adquisiciones
    'PGHN.SW',     # Partners Group — gestión de activos privados (PE, deuda, infra, real estate),
                   # primero en democratizar acceso multi-estrategia privada,
                   # AUM fees recurrentes, pero sensible a ciclo LBO y tipos de interés
    'LONN.SW',     # Lonza — CDMO líder (outsourcing fabricación farmacéutica/biotech),
                   # calificación regulatoria FDA/EMA de 30 meses = switching cost estructural,
                   # GMP compliance masivo, crecimiento secular en biologics/cell&gene therapy
    'STMN.SW',     # Straumann — implantes dentales global #1-2, sistema propietario
                   # (implante + prótesis + digital workflow + formación/certificación cirujanos),
                   # condición crónica (diente perdido no se recupera), ROIC >25%
    'DSV.CO',      # DSV A/S — logística global freight/supply chain, M&A compounder
                   # (Panalpina 2019, Agility 2021, +DB Schenker 2024), redes de consolidación
                   # que mejoran con cada adquisición, pero ciclicidad logística real
    'HLMA.L',      # Halma PLC — serial acquirer UK de seguridad/análisis/medio ambiente,
                   # modelo: adquiere negocios de nicho donde regulación obliga a tener el
                   # producto (detectores gas, visión para discapacitados, sensores agua),
                   # retención >95%, ROIC >15%, similar a Roper pero UK
    'KNEBV.HE',    # KONE — ascensores/escaleras/puertas automáticas global, 60%+ revenue
                   # en service/mantenimiento recurrente, oligopolio con Otis/Schindler/TK,
                   # gestión nórdica disciplinada, margen FCF sólido (similar a OTIS US T3)
    'SAF.PA',      # Safran — propulsión aeroespacial, motor LEAP (JV CFM con GE = mejor
                   # motor comercial del mundo por entregas), installed base crece = MRO crece,
                   # pero dependencia aviación comercial (COVID-19 riesgo conocido)
    'AMS.MC',      # Amadeus IT — GDS (Global Distribution System) aviación near-monopoly EU,
                   # network effect bilateral: agentes necesitan estar en Amadeus porque
                   # aerolíneas están ahí, aerolíneas deben estar porque agentes la usan,
                   # COVID-19 demostró ciclicidad profunda → Tier 2 no Tier 1
    'CPG.L',       # Compass Group — food services global #1, contratos 5-10 años con
                   # corporaciones/universidades/hospitales, economías de escala en compras,
                   # similar a Cintas (CTAS) en modelo de outsourcing de servicio no-core
]

# ── TIER 3 — Convicción parcial (★★★☆☆) ──────────────────────────────────────
# Buenas empresas con moats reales pero con matices: valoración exigente,
# ciclicidad, concentración geográfica, o ventaja competitiva más estrecha.
# Solo posición táctica reducida.

TIER_3_EU = [
    # ── Nativos de empresas ya en curated_tickers.py como ADRs ──────────────────
    'EL.PA',       # EssilorLuxottica — óptica/lujo, integración vertical única
                   # (lentes Essilor + monturas Luxottica + cadenas ópticas LensCrafters/Sunglass Hut),
                   # riesgo: regulación pricing lentes (ADR: ESLOY)
    'SIKA.SW',     # Sika AG — químicos construcción global #1 (aditivos hormigón, impermeabilizantes,
                   # adhesivos), switching cost en especificación técnica, ciclicidad construcción
                   # (ADR: SXYAY)
    'ASSA-B.ST',   # Assa Abloy — cerraduras/control acceso global #1, 200+ adquisiciones
                   # en 3 décadas, digitalización del acceso = tailwind secular, ciclicidad
                   # construcción residencial (ADR: ASAZY)
    'SU.PA',       # Schneider Electric — gestión energética/automatización industrial,
                   # EcoStruxure IoT, data center power growth, pero conglomerado complejo
                   # con ciclicidad industrial real (ADR: SBGSY)
    'ATCO-B.ST',   # Atlas Copco — compresores/vacío/herramientas industriales, aftermarket
                   # suaviza ciclo, cultura de ejecución sueca, pero capex industrial cíclico
                   # (ADR: ATLKY)
    'EXPN.L',      # Experian — buró crédito global #1, datos mandatorios AML/KYC/antifraude,
                   # riesgo: data breach catastrófico tipo Equifax 2017 (ya en US T3)
    'AUTO.L',      # Auto Trader Group — marketplace automoción UK near-monopoly, 75%+ EBIT
                   # margins, limitación: solo UK/Irlanda (ya en US T3)
    'ITRK.L',      # Intertek — testing/inspección/certificación TIC global, demanda regulatoria
                   # mandatoria, pero competencia intensa con SGS/Bureau Veritas (ya en US T3)
    'G24.DE',      # Scout24/ImmoScout24 — marketplace inmobiliario Alemania 90%+ búsquedas,
                   # pricing power, riesgo regulatorio mercado alquiler alemán (ya en US T3)
    'SAP.DE',      # SAP SE — ERP #1 global, switching cost masivo (migrar ERP = proyecto
                   # 3-5 años), transición RISE with SAP cloud en curso (ya en US T3 como SAP)
    'RACE.MI',     # Ferrari — lujo/automoción, exclusividad controlada (lista espera 2+ años),
                   # precios creciendo sistemáticamente, pero moat más estrecho que Hermès
                   # (ya en US T3)

    # ── Nuevas incorporaciones: calidad europea sólida con matices ──────────────
    'GEBN.SW',     # Geberit — fontanería/agua edificios (cisternas, desagües, tuberías de
                   # plástico), instalado en paredes = switching cost de reemplazo brutal,
                   # dominancia DACH >40% cuota, pero ciclicidad construcción nueva
    'SY1.DE',      # Symrise — sabores/fragancias global #2 (detrás de Givaudan), co-desarrollo
                   # propietario con clientes, estable y con barreras, menor escala que líder
    'BEI.DE',      # Beiersdorf — Nivea (skincare confianza global 140 años, 200 países) +
                   # Tesa (cintas industriales B2B con switching costs instaladores),
                   # dual moat consumer + industrial, pero crecimiento moderado
    'ITX.MC',      # Inditex/Zara — fast fashion, supply chain just-in-time único (40%
                   # producción near-shore España/Portugal, diseño→tienda en 2 semanas vs
                   # 6-9 meses competencia), pero riesgo disrupción e-commerce/sostenibilidad
    'LR.PA',       # Legrand — componentes eléctricos para edificios global (enchufes,
                   # cuadros, cableado, SAI), lealtad instaladores/prescriptores en 180+ países,
                   # pero ciclicidad construcción y competencia en precio en gama baja
    'MONC.MI',     # Moncler — lujo outerwear, estrategia "Genius" de colaboraciones con
                   # diseñadores, expansión aspiracional Asia, pero single-category = moat
                   # más estrecho que LVMH/Hermès
    'HEXA-B.ST',   # Hexagon — tecnología medición de precisión (geoespacial satelital,
                   # manufactura CAD/CAM, construcción layout), software+hardware integrado,
                   # similar a Mettler-Toledo pero para industria exterior/gran escala
    'INDT.ST',     # Indutrade — serial acquirer nórdico industrial niche (~300 empresas
                   # adquiridas: control de fluidos, herramientas corte, sellado), modelo
                   # Constellation Software para distribución industrial, pequeño pero ROIC alto
    'LIFCO-B.ST',  # Lifco AB — serial acquirer nórdico diversificado (dental equipamiento,
                   # demolición/herramientas, systems solutions), alta ROIC decentralized,
                   # Melker Schörling como referencia de governance sueca
    'ERF.PA',      # Eurofins Scientific — testing food/pharma/environment global #1,
                   # mandato regulatorio en seguridad alimentaria y farmacéutica,
                   # pero estructura adquisitiva compleja y valoración históricamente exigente
    'DSY.PA',      # Dassault Systèmes — PLM/CAD software (CATIA estándar en aeroespacial
                   # y automoción, SOLIDWORKS para PYME), switching cost masivo en diseño 3D,
                   # pero ciclo largo de adopción y dependencia capex industrial
    'RMV.L',       # Rightmove — portal inmobiliario UK near-monopoly (75%+ búsquedas
                   # compra/alquiler), 75%+ EBIT margins, pricing power sobre agencias,
                   # limitación crítica: solo UK/Irlanda = TAM acotado
    'SGE.L',       # Sage Group — software contabilidad/nóminas PYME SaaS (UK/Francia/ZA
                   # principalmente), switching cost elevado (migrar contabilidad = proyecto
                   # doloroso), pero competencia Microsoft/Xero en cloud emergente
    'DEMANT.CO',   # Demant — audiología global (hearing aids OTC/prescripción + implantes
                   # cocleares + diagnóstico audiológico), condición crónica edad-dependiente,
                   # duopolio con Sonova, pero competencia tecnológica (OTC Hearing Aid Act US)
    'CPR.MI',      # Campari Group — portfolio licores premium (Aperol #1 aperitivo mundial,
                   # Campari, Grand Marnier, Wild Turkey bourbon), brand building M&A, pero
                   # inventario envejecimiento lento en bourbon y whisky pesa en FCF
    'HEIA.AS',     # Heineken — cerveza global #2-3, red distribución 190 países,
                   # marcas Heineken/Amstel/Desperados + marcas locales premium,
                   # pero declive secular volúmenes en mercados maduros (health trends)
]

# ── TIER 4 — No apta para cartera apalancada (★★☆☆☆) ─────────────────────────
# Empresas reconocibles con negocios de cierta calidad, pero con: valoración
# extrema, moat en deterioro, ciclicidad profunda, o riesgo regulatorio elevado.
# Incluidas como referencia de universo completo. No aptas para posición concentrada.

TIER_4_EU = [
    'ASML.AS',   # ASML — monopolio EUV real, pero: valoración extrema histórica + ciclo
                 # semis largo (downcycles -60%) + dependencia cliente TSMC/Samsung concentrada
    'NESN.SW',   # Nestlé — 2000+ marcas, distribución global, pero: restructuring en curso,
                 # crecimiento orgánico <3%, pérdida de cuota a marcas privadas, moat erosionándose
    'ROG.SW',    # Roche — diagnóstico #1 global + farmacéutica oncología, pero: presión
                 # biosimilares en Avastin/Herceptin/MabThera, pipeline dependiente de aprobaciones
    'DGE.L',     # Diageo — spirits premium global #1 (Johnnie Walker, Guinness, Tanqueray),
                 # pero: destocking sistémico 2023-2025, retos volúmenes mercados emergentes
    'ULVR.L',    # Unilever — consumer goods global, pero: reformando portfolio (venta Elida
                 # Beauty, separación helados), pricing power menor, moat diluyéndose
    'AZN.L',     # AstraZeneca — pipeline farmacéutico excelente (oncología/biosimilares/cardiología),
                 # pero: R&D risk inherente, China exposure elevada (~30% revenue), PER exigente
    'DG.PA',     # Vinci SA — concesiones autopistas/aeropuertos + construcción, peajes
                 # ajustados por inflación, pero: riesgo político francés de renegociación/
                 # nationalización periódico (ya en US T4 como VCISY)
    'SGSN.SW',   # SGS SA — TIC global #1 por tamaño, pero: competencia Bureau Veritas/Intertek
                 # sin pricing power fuerte, márgenes modestos, sin moat estructural profundo
                 # (ya en US T4 como SGSOY)
    'NESTE.HE',  # Neste — líder diésel renovable (HVO) y SAF, moat regulatorio EU mandatos
                 # biocombustibles, pero: commodity pricing en márgenes HEVO, capex masivo,
                 # riesgo si mandatos se revierten
    'ABBN.SW',   # ABB — eléctrico/robótica/automatización industrial, spin-offs parciales
                 # (Electrification, Motion, PA, Robotics), pero: conglomerado complejo,
                 # alta ciclicidad capex industrial, no tiene el moat de Schneider en software
]

# ── CHINA — Referencia selectiva (★★★☆☆ con riesgo soberano) ─────────────────
# Solo negocios chinos con moats excepcionales y documentados.
#
# RIESGOS ESPECÍFICOS obligatorios a considerar antes de cualquier posición:
#   - Estructura VIE: el accionista extranjero NO posee acciones directas de la empresa
#     operativa china; posee contractos con una entidad offshore que puede ser invalidada
#   - Riesgo PCCh: intervenciones regulatorias sin previo aviso (Ant Financial 2020,
#     sector tutorías 2021, gaming minors 2021, DiDi 2021)
#   - Riesgo delisting: amenaza recurrente de exclusión de bolsas US para ADRs chinos
#   - Calidad datos: yfinance parcial para algunos campos (analistas, targets)
#   - Geopolítica: escalada tensión US-China puede impactar precios independientemente
#     del negocio subyacente
#
# NO aptas para posición apalancada. Usar solo con sizing mínimo y stops definidos.

TIER_CHINA = [
    '0700.HK',     # Tencent Holdings — ecosistema WeChat (1.3B MAU), gaming global #1,
                   # fintech (WeChat Pay), cloud en crecimiento. Moat de red genuino.
                   # Riesgo: PCCh ya intervino (juegos menores, cuota de Meituan vendida)
    '600519.SS',   # Kweichow Moutai — baijiu Maotai, monopolio cultural/histórico en
                   # espirituoso premium chino, margen bruto >90%, fijación de precios
                   # gubernamental paradójicamente protege el moat, coleccionismo/regalo
                   # corporativo = demanda inelástica. Riesgo: anticorrupción campaigns
]


# ── Helpers ────────────────────────────────────────────────────────────────────

# Sufijos de bolsas nórdicas (no incluidos en market_configs.py original)
NORDIC_SUFFIXES = {'.CO', '.ST', '.HE', '.OL'}

def get_eu_universe(include_tier4: bool = False, include_china: bool = False) -> list:
    """
    Retorna el universo europeo curado.
    Por defecto Tier 1+2+3 (excluye Tier 4 y China).
    """
    universe = TIER_1_EU + TIER_2_EU + TIER_3_EU
    if include_tier4:
        universe += TIER_4_EU
    if include_china:
        universe += TIER_CHINA
    return list(dict.fromkeys(universe))  # deduplicate, preserve order


def get_eu_tier(ticker: str) -> str:
    """Retorna el tier europeo de un ticker ('1','2','3','4','C','?')."""
    t = ticker.upper()
    tiers = [
        (TIER_1_EU, '1'),
        (TIER_2_EU, '2'),
        (TIER_3_EU, '3'),
        (TIER_4_EU, '4'),
        (TIER_CHINA, 'C'),
    ]
    for tier_list, label in tiers:
        if t in [x.upper() for x in tier_list]:
            return label
    return '?'


def get_eu_tier_label(tier: str) -> str:
    return {
        '1': 'Élite',
        '2': 'Alta convicción',
        '3': 'Convicción parcial',
        '4': 'No apta',
        'C': 'China (referencia)',
    }.get(tier, 'Desconocido')


ALL_EU_TICKERS = get_eu_universe(include_tier4=True, include_china=True)
SCORED_EU_TICKERS = get_eu_universe(include_tier4=False, include_china=False)


if __name__ == '__main__':
    print(f"Tier 1 EU ({len(TIER_1_EU)} tickers): {', '.join(TIER_1_EU)}")
    print(f"Tier 2 EU ({len(TIER_2_EU)} tickers): {', '.join(TIER_2_EU)}")
    print(f"Tier 3 EU ({len(TIER_3_EU)} tickers): {', '.join(TIER_3_EU)}")
    print(f"Tier 4 EU ({len(TIER_4_EU)} tickers): {', '.join(TIER_4_EU)}")
    print(f"China    ({len(TIER_CHINA)} tickers): {', '.join(TIER_CHINA)}")
    print(f"\nUniverse scored (T1+T2+T3): {len(SCORED_EU_TICKERS)} tickers")
    print(f"Full universe (all tiers):   {len(ALL_EU_TICKERS)} tickers")

    nordic = [t for t in ALL_EU_TICKERS if any(t.endswith(s) for s in NORDIC_SUFFIXES)]
    print(f"\nNórdicos en universo: {len(nordic)} tickers: {', '.join(nordic)}")
