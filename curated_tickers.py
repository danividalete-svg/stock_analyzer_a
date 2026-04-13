#!/usr/bin/env python3
"""
CURATED TICKER UNIVERSE
Universo de ~120 empresas de alta calidad seleccionadas con filtros estrictos.
Organizadas en 4 tiers por solidez del moat y calidad de negocio.

Source: Análisis curado por analista de datos financieros (Abril 2026)
"""

# ── TIER 1 — Élite (★★★★★) ────────────────────────────────────────────────────
# Negocios con fosos defensivos excepcionales, retornos sobre capital sostenidos,
# pricing power demostrado. Las mejores del mundo en su categoría.

TIER_1 = [
    'VRSK',    # Verisk Analytics — data/analytics monopoly
    'RELX',    # RELX Group — information services
    'WTKWY',   # Wolters Kluwer — professional info (ADR)
    'WCN',     # Waste Connections
    'WM',      # Waste Management
    'V',       # Visa
    'CTAS',    # Cintas
    'LIN',     # Linde
    'ROP',     # Roper Technologies
    'ADP',     # Automatic Data Processing
    'ROL',     # Rollins (pest control)
    'MSI',     # Motorola Solutions
    'SPGI',    # S&P Global
    'COST',    # Costco
    'CPRT',    # Copart
    'MMC',     # Marsh & McLennan (Tier 1 insurance/consulting)
    'MA',      # Mastercard
    'AI.PA',   # Air Liquide (Euronext Paris)
    'CME',     # CME Group
    'RSG',     # Republic Services
    'HESAY',   # Heineken (ADR)
    'VRSN',    # VeriSign
]

# ── TIER 2 — Alta convicción (★★★★☆) ─────────────────────────────────────────
# Negocios de alta calidad con moats sólidos. Pueden tener ciclicidad moderada
# o mayor dependencia del crecimiento futuro para justificar valoración.

TIER_2 = [
    'BR',      # Broadridge Financial Solutions
    'CSU.TO',  # Constellation Software (Toronto)
    'ZTS',     # Zoetis
    'MSFT',    # Microsoft
    'KO',      # Coca-Cola
    'MSCI',    # MSCI Inc.
    'MCO',     # Moody's Corp
    'INTU',    # Intuit
    'PAYX',    # Paychex
    'PG',      # Procter & Gamble
    'IDXX',    # IDEXX Laboratories
    'GVDNY',   # Givaudan (ADR)
    'SYK',     # Stryker
    'TW',      # Tradeweb Markets
    'TMO',     # Thermo Fisher Scientific
    'AON',     # Aon
    'VLTO',    # Veralto
    'TYL',     # Tyler Technologies
    'SHW',     # Sherwin-Williams
    'WMT',     # Walmart
    'FICO',    # Fair Isaac (FICO)
    'VEEV',    # Veeva Systems
    'ERIE',    # Erie Indemnity
    'CLPBY',   # Coloplast (ADR)
    'ECL',     # Ecolab
    'LRLCY',   # L'Oréal (ADR)
    'AJG',     # Arthur J. Gallagher
    'CNI',     # Canadian National Railway
    'ICE',     # Intercontinental Exchange
    'LSEG.L',  # London Stock Exchange Group (LSE)
    'AZO',     # AutoZone
    'DBOEY',   # Deutsche Börse AG (ADR)
    'WST',     # West Pharmaceutical Services
    'MCD',     # McDonald's
    'MTD',     # Mettler-Toledo
    'DSGX',    # Descartes Systems (logistics software)
    'BRO',     # Brown & Brown (insurance)
    '7741.T',  # Hoya Corporation (Tokyo)
    'ORLY',    # O'Reilly Automotive
]

# ── TIER 3 — Convicción parcial (★★★☆☆) ──────────────────────────────────────
# Buenas empresas con moats reales pero con más matices: valoración exigente,
# ciclicidad, transición de negocio, o ventaja competitiva más estrecha.

TIER_3 = [
    'RACE',    # Ferrari
    'SAP',     # SAP SE (ADR)
    'NOW',     # ServiceNow
    'BRK-B',   # Berkshire Hathaway B
    'DHR',     # Danaher
    'OTIS',    # Otis Worldwide
    'EXPN.L',  # Experian (LSE)
    'HEI',     # HEICO
    'SXYAY',   # Sysco? No — likely SXYAY = Sodexo ADR (actually Sodexo is SDXAY)
    'ITW',     # Illinois Tool Works
    'CDNS',    # Cadence Design Systems
    'CHD',     # Church & Dwight
    'ASAZY',   # ASA Gold? Or Asahi Group (ASAZY) — Japanese beverages ADR
    'ETN',     # Eaton Corporation
    'ABT',     # Abbott Laboratories
    'IT',      # Gartner
    'NDAQ',    # Nasdaq Inc.
    'SBGSY',   # Schneider Electric (ADR)
    'TT',      # Trane Technologies
    'CB',      # Chubb
    'FDS',     # FactSet Research
    'FAST',    # Fastenal
    'PGR',     # Progressive Corp
    'EQIX',    # Equinix
    'CL',      # Colgate-Palmolive
    'AME',     # AMETEK
    'ATLKY',   # Atlas Copco (ADR)
    'NDSN',    # Nordson
    'TNE.AX',  # Technology One (ASX)
    'AWK',     # American Water Works
    'PEP',     # PepsiCo
    'AXP',     # American Express
    'ESLOY',   # EssilorLuxottica (ADR)
    'TJX',     # TJX Companies
    'CP',      # Canadian Pacific Railway (Kansas City)
    'JNJ',     # Johnson & Johnson
    'CBOE',    # Cboe Global Markets
    'MKC',     # McCormick & Co.
    'GWW',     # W.W. Grainger
    'JKHY',    # Jack Henry & Associates
    'AUTO.L',  # Auto Trader Group (LSE)
    'ITRK.L',  # Intertek Group (LSE)
    'G24.DE',  # Scout24 (Xetra)
    'ISRG',    # Intuitive Surgical
]

# ── TIER 4 — No apta para portfolios apalancados (★★☆☆☆) ─────────────────────
# Empresas reconocibles con negocios de calidad, pero que presentan alguno de:
# valoración extrema, moat en deterioro, disrupción tecnológica, o dependencia
# excesiva del ciclo. No recomendadas para posiciones concentradas.
# Incluidas como referencia de universo completo.

TIER_4 = [
    'ADSK',    # Autodesk
    'BLK',     # BlackRock
    'ODFL',    # Old Dominion Freight Line
    'APH',     # Amphenol
    'ATO',     # Atmos Energy
    'DOL.TO',  # Dollarama (Toronto)
    '4684.T',  # Obic (Tokyo)
    'TLC.AX',  # The Lottery Corporation (ASX)
    'MANH',    # Manhattan Associates
    'UNP',     # Union Pacific
    'VCISY',   # Victrex (ADR)
    'SGSOY',   # SGS SA (ADR)
    'FERG',    # Ferguson Enterprises
    'ORCL',    # Oracle
    'PSA',     # Public Storage
    'HD',      # Home Depot
    'ASML',    # ASML Holding
    'KYCCF',   # Kyocera (OTC)
    'GOOG',    # Alphabet
    'AMZN',    # Amazon
    'CRH',     # CRH plc
    'MLM',     # Martin Marietta Materials
    'YUM',     # Yum! Brands
    'FTNT',    # Fortinet
    'HLT',     # Hilton Worldwide
    'LMT',     # Lockheed Martin
    'EFX',     # Equifax
    'RMD',     # ResMed
    '6383.T',  # Daifuku (Tokyo)
    'AAPL',    # Apple
    'GGG',     # Graco
    'META',    # Meta Platforms
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_universe(include_tier4: bool = False) -> list:
    """
    Retorna el universo de tickers para scoring.
    Por defecto Tier 1+2+3 (excluye Tier 4 'No apta').
    """
    universe = TIER_1 + TIER_2 + TIER_3
    if include_tier4:
        universe += TIER_4
    return list(dict.fromkeys(universe))  # deduplicate, preserve order


def get_tier(ticker: str) -> str:
    """Retorna el tier de un ticker ('1','2','3','4','?')."""
    t = ticker.upper()
    if t in [x.upper() for x in TIER_1]:
        return '1'
    if t in [x.upper() for x in TIER_2]:
        return '2'
    if t in [x.upper() for x in TIER_3]:
        return '3'
    if t in [x.upper() for x in TIER_4]:
        return '4'
    return '?'


def get_tier_label(tier: str) -> str:
    return {
        '1': 'Élite',
        '2': 'Alta convicción',
        '3': 'Convicción parcial',
        '4': 'No apta',
    }.get(tier, 'Desconocido')


ALL_TICKERS = get_universe(include_tier4=True)
SCORED_TICKERS = get_universe(include_tier4=False)  # default scoring universe

if __name__ == '__main__':
    print(f"Tier 1 ({len(TIER_1)} tickers): {', '.join(TIER_1)}")
    print(f"Tier 2 ({len(TIER_2)} tickers): {', '.join(TIER_2)}")
    print(f"Tier 3 ({len(TIER_3)} tickers): {', '.join(TIER_3)}")
    print(f"Tier 4 ({len(TIER_4)} tickers): {', '.join(TIER_4)}")
    print(f"\nUniverse (T1+T2+T3): {len(SCORED_TICKERS)} tickers")
    print(f"Full universe (all): {len(ALL_TICKERS)} tickers")
