#!/usr/bin/env python3
"""
CURATED GLOBAL TICKER UNIVERSE
Universo curado para mercados globales: Japón, Brasil, Corea del Sur, Hong Kong.

Mismos criterios que curated_tickers.py (US) y curated_tickers_eu.py (EU).
Para uso con: global_market_scanner.py --curated

Contexto de selección de mercados:
  Japón       CAPE ~29 (media hist. 40) — mercado con descuento estructural
  Brasil      CAPE ~9  (media hist. 14) — mercado con descuento profundo
  Corea       CAPE ~21 (media hist. 15) — sin descuento significativo, calidad selectiva
  Hong Kong   CAPE ~11 (media hist. 16) — descuento por riesgo China soberano

Criterio de calidad (idéntico al universo US/EU):
  Tier 1 — "Aptas apalancado": moat irreplicable, ingresos >80% recurrentes, anti-cíclico
  Tier 2 — "Alta convicción": moat sólido, puede tener ciclicidad moderada
  Tier 3 — "Convicción parcial": calidad real con matices (ciclicidad, concentración)
  Tier 4 — "Referencia/No apta": cíclico profundo, estatal, commodity, o complejo

RIESGO ESPECÍFICO para todos los tickers de Hong Kong con subyacente chino:
  - Estructura VIE (Tencent/Alibaba/Meituan): accionista extranjero tiene derechos
    contractuales, no propiedad directa de la empresa operativa china
  - Riesgo PCCh: regulaciones sin previo aviso documentadas (gaming, educación, fintech)
  - Geopolítica US-China: puede impactar precio independientemente del negocio

Output esperado del scanner: exporta CURATED_UNIVERSES (mismo formato que UNIVERSES)
"""

# ─────────────────────────────────────────────────────────────────────────────
# JAPÓN
# ─────────────────────────────────────────────────────────────────────────────

TIER_1_JAPAN = [
    '6861.T',    # Keyence — sensores/automatización industrial, >50% EBIT margins,
                 # modelo directo sin distribuidores = margen estructural, ROIC >25%,
                 # switching costs en líneas de producción que usan sus sensores
]

TIER_2_JAPAN = [
    '8035.T',    # Tokyo Electron — equipos fabricación semiconductores (coater/developer,
                 # ALD, RIE), posición crítica en supply chain chips, similar a Lam Research
    '4063.T',    # Shin-Etsu Chemical — wafers silicio near-monopoly global (30%+ cuota),
                 # PVC global #1, productos básicos críticos con switching costs técnicos
    '4661.T',    # Oriental Land — operador Tokyo Disneyland/DisneySea, pricing power único
                 # en entretenimiento familiar Japón, ocupación 95%+, recurring attendance
    '8766.T',    # Tokio Marine Holdings — aseguradora premium Japón, expansión disciplinada
                 # (Philadelphia Consolidated, Delphi Financial), underwriting quality
    '6098.T',    # Recruit Holdings — HR tech (Indeed.com + Glassdoor) + staffing Japón,
                 # flywheel datos empleadores↔candidatos, network effects globales
    '9983.T',    # Fast Retailing/Uniqlo — supply chain just-in-time básico/calidad,
                 # expansión Asia sistemática, DTC eliminando intermediarios
    '6367.T',    # Daikin Industries — HVAC global #1, switching costs en instalaciones
                 # comerciales/industriales, crecimiento secular por calor global
    '4568.T',    # Daiichi Sankyo — pharma oncología, pipeline ADC (antibody-drug conjugates)
                 # con AstraZeneca (Enhertu), riesgo pipeline pero posición tecnológica líder
]

TIER_3_JAPAN = [
    '7203.T',    # Toyota Motor — automotive, gestión calidad excepcional (TPS/lean),
                 # liderazgo híbrido (Prius), pero ciclicidad profunda y capex masivo
    '6758.T',    # Sony Group — entertainment/PlayStation/sensores CMOS, IP de franquicias
                 # (Spider-Man, Music), pero hardware consumer cíclico arrastra el conjunto
    '7974.T',    # Nintendo — gaming, IP franchise única (Mario/Zelda/Pokémon),
                 # hardware propio pero ciclo de consola cada 5-7 años = discontinuidad
    '9432.T',    # NTT (Nippon Telegraph) — infraestructura telecom Japón + NTT Data global,
                 # utilities-like estabilidad, pero crecimiento limitado y regulado
    '7733.T',    # Olympus — endoscopios médicos (>70% cuota global en endoscopía flexible),
                 # consumibles repetitivos, pero en restructuring desde escándalo contable
]

TIER_4_JAPAN = [
    '8306.T',    # MUFG — banco más grande Japón, commodity banking, NIM deprimido por ZIRP
    '9984.T',    # SoftBank — conglomerado inversión/tech, no es un negocio operativo
    '8316.T',    # Sumitomo Mitsui Financial — banco, similar a MUFG
    '6902.T',    # Denso — componentes auto, cíclico directo
    '7267.T',    # Honda Motor — automotive, doble ciclicidad auto+moto
    '6501.T',    # Hitachi — industrial diversificado, mejoró pero aún complejo
    '9433.T',    # KDDI — telecom, utility-like pero sin moat de datos
    '8031.T',    # Mitsui & Co — trading house, diversificado sin pricing power claro
    '2914.T',    # Japan Tobacco — tabaco, flujos estables pero industria en declive secular
    '4502.T',    # Takeda — pharma, pipeline dependiente, post-Shire acquisition digest
]


# ─────────────────────────────────────────────────────────────────────────────
# BRASIL
# ─────────────────────────────────────────────────────────────────────────────

TIER_1_BRAZIL = []
# Ninguna empresa brasileña alcanza los criterios Tier 1 (ingresos >80% recurrentes,
# anti-cíclico, pricing power irreplicable). WEG es la más cercana pero tiene
# ciclicidad industrial real.

TIER_2_BRAZIL = [
    'WEGE3.SA',  # WEG S.A. — motores/drives/automatización industrial, ROIC >20%,
                 # excepcional para empresa industrial, expansión global disciplinada,
                 # gestión familiar Fundação WEG, márgenes crecientes por mix hacia
                 # segmentos de mayor valor (GTD, T&D, solar)
    'TOTS3.SA',  # Totvs — ERP software #1 PYME Brasil (>50% cuota ERPs nacionales),
                 # SaaS recurrente, switching cost masivo (cambiar ERP = proyecto doloroso),
                 # expansión hacia fintech (Totvs Techfin) en clientes cautivos
    'B3SA3.SA',  # B3 — bolsa brasileña, monopolio clearing y liquidación, no tiene
                 # competencia real por regulación, correlación positiva con desarrollo
                 # mercado capitales Brasil, ingresos por volumen + listing fees
]

TIER_3_BRAZIL = [
    'RDOR3.SA',  # Rede D'Or São Luiz — red hospitales premium Brasil, consolidador de
                 # mercado hospitalario fragmentado, marcas premium en oncología/cirugía,
                 # pero capex expansión intensivo y leverage visible
    'RENT3.SA',  # Localiza (fusionada con Unidas) — alquiler coches + gestión flotas,
                 # player dominante post-fusión, escala permite mejores precios compra,
                 # pero negocio impactado por tipos de interés (financia flotas)
    'ITUB4.SA',  # Itaú Unibanco — mejor banco Brasil, ROE consistente >15%,
                 # gestión superior al sector, pero commodity banking con riesgo macro Brasil
    'EMBR3.SA',  # Embraer — jets regionales nicho E-jets (única alternativa a Boeing/Airbus
                 # en regional), cartera de pedidos recuperada post-COVID, pero capex intensivo
    'ABEV3.SA',  # Ambev — bebidas Brasil/LATAM, distribución dominante, economías de escala,
                 # filial AB InBev, pero volúmenes cerveza estancados en Brasil
]

TIER_4_BRAZIL = [
    'PETR4.SA',  # Petrobras — petróleo estatal, riesgo política gobierno elevado
    'VALE3.SA',  # Vale — minería mineral hierro, commodity cíclico extremo
    'BBDC4.SA',  # Bradesco — banco, menor calidad que Itaú
    'BBAS3.SA',  # Banco do Brasil — banco estatal, interferencia política documentada
    'SUZB3.SA',  # Suzano — pulpa celulosa, commodity precio mercado global
    'CSAN3.SA',  # Cosan — conglomerado (combustibles + logística + azúcar + Compass Gas)
    'EGIE3.SA',  # Engie Brasil — utilities eléctrica regulada
    'CMIG4.SA',  # Cemig — utilities eléctrica estatal Minas Gerais, riesgo político
    'CPLE6.SA',  # Copel — utilities eléctrica estatal Paraná
    'ELET3.SA',  # Eletrobras — utilities recién privatizada, restructuring
    'LREN3.SA',  # Lojas Renner — retail moda, ciclicidad consumo Brasil
    'SULA11.SA', # Sul América — seguros, menor escala, competencia intensa
]


# ─────────────────────────────────────────────────────────────────────────────
# COREA DEL SUR
# ─────────────────────────────────────────────────────────────────────────────
# Nota: los chaebols (Samsung, SK, Hyundai, LG) son estructuralmente complejos
# con holding companies, cross-holdings y gobierno corporativo históricamente débil.
# Ajuste de calidad necesario vs. empresas occidentales equivalentes.

TIER_1_KOREA = []
# Ninguna empresa coreana cumple criterios Tier 1 en esta framework.
# Los descuentos de valoración del "Korea Discount" reflejan estos problemas estructurales.

TIER_2_KOREA = [
    '005930.KS',  # Samsung Electronics — semiconductores DRAM/NAND (#1 global) +
                  # smartphones, moat tecnológico real en fabricación de chips de memoria,
                  # pero ciclicidad semis profunda (downcycle -40% beneficio documentado)
    '009150.KS',  # Samsung Electro-Mechanics — MLCCs (condensadores cerámicos, críticos
                  # para electronics/EV) + módulos de cámara para smartphones,
                  # similar a Murata en nicho, tecnología difícil de replicar
]

TIER_3_KOREA = [
    '035420.KS',  # NAVER — búsqueda online Korea near-monopoly (70%+ cuota),
                  # e-commerce (SmartStore), webtoon/contenido, LINE Japan,
                  # pero mercado doméstico Korea limitado en TAM
    '012330.KS',  # Hyundai Mobis — componentes auto (airbags, frenos, módulos electrónicos),
                  # mejor margen dentro del grupo Hyundai, pero cíclico directo
    '105560.KS',  # KB Financial — banco mejor calidad en Korea, capital adecuado,
                  # menor exposición a chaebol que peers, ROE ~10%
]

TIER_4_KOREA = [
    '000660.KS',  # SK Hynix — DRAM commodity, cíclico extremo
    '005380.KS',  # Hyundai Motor — automotive, cíclico
    '000270.KS',  # Kia Motors — automotive, cíclico
    '051910.KS',  # LG Chem — baterías EV + química, cíclico
    '006400.KS',  # Samsung SDI — baterías EV, cíclico
    '028260.KS',  # Samsung C&T — conglomerado holding
    '096770.KS',  # SK Innovation — energía + baterías, cíclico
    '017670.KS',  # SK Telecom — telecom regulada
    '030200.KS',  # KT Corp — telecom regulada
    '086790.KS',  # Hana Financial — banco
    '055550.KS',  # Shinhan Financial — banco
    '066570.KS',  # LG Electronics — consumer electronics bajo margen
    '316140.KS',  # Woori Financial — banco
    '010950.KS',  # S-Oil — refinería, commodity
    '032830.KS',  # Samsung Life — seguro vida, regulado
]


# ─────────────────────────────────────────────────────────────────────────────
# HONG KONG / CHINA H-SHARES
# ─────────────────────────────────────────────────────────────────────────────
# Ver advertencia VIE/PCCh al inicio del archivo. Todos los tickers de empresas
# operativas chinas (Tencent, Alibaba, Meituan...) tienen estructura VIE.
# HKEX y AIA son empresas HK genuinas, sin VIE.

TIER_1_HK = [
    '0700.HK',   # Tencent Holdings — WeChat ecosystem (1.3B MAU), gaming global #1,
                 # fintech WeChat Pay, cloud en crecimiento. Moat de red genuino.
                 # Riesgo VIE + regulatorio PCCh documentado (gaming menores 2021,
                 # venta stake en Meituan/JD dirigida por PCCh)
]

TIER_2_HK = [
    '0388.HK',   # HKEX (Hong Kong Exchanges and Clearing) — bolsa monopolio HK + clearing,
                 # gateway China-capital internacional (Stock Connect), similar a Deutsche Börse,
                 # empresa HK genuina (sin VIE), beneficia de apertura mercados China
    '1299.HK',   # AIA Group — vida/salud insurance pan-Asia (18 mercados), franquicia
                 # distribución agentes única en Asia emergente, empresa HK genuina (sin VIE),
                 # beneficia de creciente clase media asiática y brecha de protección
    '2382.HK',   # Sunny Optical Technology — lentes ópticas para smartphones (top 3 global)
                 # + módulos cámara ADAS para vehículos autónomos, moat tecnológico en óptica
                 # de precisión, empresa HK operativa (estructura menos VIE que tech)
    '9999.HK',   # NetEase — gaming China con IP propio fuerte (Westward Journey, Fantasy
                 # Westward Journey), menor regulación gaming que Tencent por menor tamaño,
                 # expansión internacional gaming (Dead by Daylight, Diablo Immortal)
]

TIER_3_HK = [
    '9988.HK',   # Alibaba (HK listing) — e-commerce China #1 + Aliyun cloud #1 China,
                 # descuento histórico vs. peers, pero riesgo regulatorio SAMR/fintech real
                 # (multa €18B 2021, congelación IPO Ant Financial), estructura VIE
    '2318.HK',   # Ping An Insurance — aseguradora vida + P&C + Lufax fintech + tecnología
                 # sanitaria, calidad underwriting superior sector chino, estructura VIE
    '1211.HK',   # BYD Company — EVs + baterías LFP (proveedor para Tesla entre otros),
                 # integración vertical única en la industria EV, pero competencia intensa
                 # y márgenes bajo presión, estructura parcialmente HK/China
    '2020.HK',   # ANTA Sports — marcas deportivas (Anta, FILA China, participación Arc'teryx),
                 # roll-up de marcas premium aspiracional China, pero depende del consumo chino
]

TIER_4_HK = [
    '0941.HK',   # China Mobile — telecom estatal, bajo retorno, regulada
    '0939.HK',   # China Construction Bank — banco estatal
    '1398.HK',   # ICBC — banco estatal, mayor por activos del mundo pero ROE bajo
    '0883.HK',   # CNOOC — petróleo offshore estatal, commodity cíclico + sanción US risk
    '0857.HK',   # PetroChina — petróleo estatal
    '3988.HK',   # Bank of China — banco estatal
    '1810.HK',   # Xiaomi — smartphones bajo margen, competencia precio brutal
    '9618.HK',   # JD.com (HK) — e-commerce logística, márgenes bajos estructurales
    '3690.HK',   # Meituan — food delivery, rentabilidad mejorada pero aún volátil
    '0002.HK',   # CLP Holdings — utility eléctrica HK regulada
    '6690.HK',   # Haier Smart Home — electrodomésticos, commodity consumer
    '0001.HK',   # CK Hutchison — conglomerado old-style (puertos, telecom, retail)
    '0005.HK',   # HSBC — banco internacional complejo, exposición HK/Asia/UK
]


# ── Estructura compatible con UNIVERSES de global_market_scanner.py ───────────

# Universo curado: solo Tier 1+2+3 por mercado (para scoring)
CURATED_UNIVERSES = {
    "Japan":     TIER_1_JAPAN + TIER_2_JAPAN + TIER_3_JAPAN,
    "Brazil":    TIER_1_BRAZIL + TIER_2_BRAZIL + TIER_3_BRAZIL,
    "Korea":     TIER_1_KOREA + TIER_2_KOREA + TIER_3_KOREA,
    "HongKong":  TIER_1_HK + TIER_2_HK + TIER_3_HK,
}

# Universo completo (incluye Tier 4, para referencia)
FULL_UNIVERSES = {
    "Japan":     TIER_1_JAPAN + TIER_2_JAPAN + TIER_3_JAPAN + TIER_4_JAPAN,
    "Brazil":    TIER_1_BRAZIL + TIER_2_BRAZIL + TIER_3_BRAZIL + TIER_4_BRAZIL,
    "Korea":     TIER_1_KOREA + TIER_2_KOREA + TIER_3_KOREA + TIER_4_KOREA,
    "HongKong":  TIER_1_HK + TIER_2_HK + TIER_3_HK + TIER_4_HK,
}


def get_global_tier(ticker: str) -> str:
    """Retorna el tier global de un ticker ('1','2','3','4','?')."""
    all_tiers = [
        (TIER_1_JAPAN + TIER_1_BRAZIL + TIER_1_KOREA + TIER_1_HK, '1'),
        (TIER_2_JAPAN + TIER_2_BRAZIL + TIER_2_KOREA + TIER_2_HK, '2'),
        (TIER_3_JAPAN + TIER_3_BRAZIL + TIER_3_KOREA + TIER_3_HK, '3'),
        (TIER_4_JAPAN + TIER_4_BRAZIL + TIER_4_KOREA + TIER_4_HK, '4'),
    ]
    t = ticker.upper()
    for tier_list, label in all_tiers:
        if t in [x.upper() for x in tier_list]:
            return label
    return '?'


if __name__ == '__main__':
    for market, tickers in CURATED_UNIVERSES.items():
        print(f"\n{market} — {len(tickers)} tickers curados:")
        for t in tickers:
            print(f"  [{get_global_tier(t)}] {t}")

    total = sum(len(v) for v in CURATED_UNIVERSES.values())
    total_full = sum(len(v) for v in FULL_UNIVERSES.values())
    print(f"\nTotal curado (T1+T2+T3): {total}")
    print(f"Total completo (T1-T4):  {total_full}")
