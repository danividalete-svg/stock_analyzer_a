#!/usr/bin/env python3
"""
MARKET CONFIGURATIONS
Definiciones de mercados internacionales para expansión futura
"""

# USA Markets (actual)
SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
NASDAQ100_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"

# ═══════════════════════════════════════════════════════════════
# EUROPEAN MARKETS
# ═══════════════════════════════════════════════════════════════

DAX40_SYMBOLS = [
    # Germany DAX 40 - Top 40 German companies (XETRA)
    "SAP.DE",       # SAP SE
    "SIE.DE",       # Siemens AG
    "AIR.DE",       # Airbus SE
    "ALV.DE",       # Allianz SE
    "BAS.DE",       # BASF SE
    "BAYN.DE",      # Bayer AG
    "BMW.DE",       # BMW AG
    "VOW3.DE",      # Volkswagen AG
    "DB1.DE",       # Deutsche Boerse AG
    "DBK.DE",       # Deutsche Bank AG
    "DTE.DE",       # Deutsche Telekom AG
    "EOAN.DE",      # E.ON SE
    "FRE.DE",       # Fresenius SE
    "HEI.DE",       # HeidelbergCement AG
    "HEN3.DE",      # Henkel AG
    "IFX.DE",       # Infineon Technologies AG
    "MRK.DE",       # Merck KGaA
    "MUV2.DE",      # Munich Re
    "RWE.DE",       # RWE AG
    "ENR.DE",       # Siemens Energy AG
    "ADS.DE",       # Adidas AG
    "BEI.DE",       # Beiersdorf AG
    "CON.DE",       # Continental AG
    "1COV.DE",      # Covestro AG
    "DTG.DE",       # Daimler Truck Holding AG
    "DHL.DE",       # DHL Group
    "FME.DE",       # Fresenius Medical Care AG
    "HNR1.DE",      # Hannover Re
    "LIN.DE",       # Linde plc
    "MTX.DE",       # MTU Aero Engines AG
    "P911.DE",      # Porsche AG
    "PAH3.DE",      # Porsche Automobil Holding SE
    "PUM.DE",       # Puma SE
    "QIA.DE",       # Qiagen NV
    "RHM.DE",       # Rheinmetall AG
    "SRT3.DE",      # Sartorius AG (preferred)
    "SHL.DE",       # Siemens Healthineers AG
    "SY1.DE",       # Symrise AG
    "VNA.DE",       # Vonovia SE
    "ZAL.DE",       # Zalando SE
]

FTSE100_SYMBOLS = [
    # UK FTSE 100 - Top 40 most liquid UK companies (LSE)
    "SHEL.L",       # Shell plc
    "AZN.L",        # AstraZeneca
    "HSBA.L",       # HSBC Holdings
    "BP.L",         # BP plc
    "ULVR.L",       # Unilever
    "DGE.L",        # Diageo
    "GSK.L",        # GlaxoSmithKline
    "RIO.L",        # Rio Tinto
    "VOD.L",        # Vodafone
    "NG.L",         # National Grid
    "LSEG.L",       # London Stock Exchange Group
    "REL.L",        # RELX plc
    "CPG.L",        # Compass Group
    "AAL.L",        # Anglo American
    "EXPN.L",       # Experian
    "CRH.L",        # CRH plc
    "ABF.L",        # Associated British Foods
    "ANTO.L",       # Antofagasta
    "AHT.L",        # Ashtead Group
    "BATS.L",       # British American Tobacco
    "GLEN.L",       # Glencore
    "PRU.L",        # Prudential plc
    "SSE.L",        # SSE plc
    "SVT.L",        # Severn Trent
    "TSCO.L",       # Tesco
    "BA.L",         # BAE Systems
    "RR.L",         # Rolls-Royce
    "LLOY.L",       # Lloyds Banking Group
    "BARC.L",       # Barclays
    "NWG.L",        # NatWest Group
    "STAN.L",       # Standard Chartered
    "LAND.L",       # British Land
    "SGE.L",        # Sage Group
    "IMB.L",        # Imperial Brands
    "WPP.L",        # WPP plc
    "BT-A.L",       # BT Group
    "MNDI.L",       # Mondi
    "PSON.L",       # Pearson
    "INF.L",        # Informa
    "WTB.L",        # Whitbread
]

CAC40_SYMBOLS = [
    # France CAC 40 - Full 40 French companies (Euronext Paris)
    "MC.PA",        # LVMH
    "OR.PA",        # L'Oréal
    "SAN.PA",       # Sanofi
    "TTE.PA",       # TotalEnergies
    "AIR.PA",       # Airbus
    "BN.PA",        # Danone
    "SAF.PA",       # Safran
    "CS.PA",        # AXA
    "SU.PA",        # Schneider Electric
    "BNP.PA",       # BNP Paribas
    "AI.PA",        # Air Liquide
    "KER.PA",       # Kering
    "RI.PA",        # Pernod Ricard
    "DG.PA",        # Vinci
    "DSY.PA",       # Dassault Systemes
    "EL.PA",        # EssilorLuxottica
    "HO.PA",        # Thales
    "SGO.PA",       # Saint-Gobain
    "VIV.PA",       # Vivendi
    "MT.PA",        # ArcelorMittal SA
    "GLE.PA",       # Societe Generale
    "CA.PA",        # Carrefour
    "CAP.PA",       # Capgemini
    "EN.PA",        # Bouygues
    "VIE.PA",       # Veolia Environnement
    "ACA.PA",       # Credit Agricole
    "ML.PA",        # Michelin
    "RNO.PA",       # Renault
    "PUB.PA",       # Publicis Groupe
    "ORA.PA",       # Orange
    "LR.PA",        # Legrand
    "URW.PA",       # Unibail-Rodamco-Westfield
    "ENGI.PA",      # Engie
    "ERF.PA",       # Eurofins Scientific
    "RMS.PA",       # Hermes International
    "TEP.PA",       # Teleperformance
    "ALO.PA",       # Alstom
    "ATO.PA",       # Atos
    "WLN.PA",       # Worldline
    "STM.PA",       # STMicroelectronics NV
]

IBEX35_SYMBOLS = [
    # Spain IBEX 35 - Top 35 Spanish companies (BME)
    "SAN.MC",       # Banco Santander
    "BBVA.MC",      # BBVA
    "IBE.MC",       # Iberdrola
    "ITX.MC",       # Inditex (Zara)
    "TEF.MC",       # Telefonica
    "REP.MC",       # Repsol
    "FER.MC",       # Ferrovial
    "AMS.MC",       # Amadeus IT
    "CABK.MC",      # CaixaBank
    "ENG.MC",       # Enagas
    "ACS.MC",       # ACS Actividades
    "NTGY.MC",      # Naturgy Energy
    "MAP.MC",       # Mapfre
    "IAG.MC",       # IAG (Iberia/BA parent)
    "GRF.MC",       # Grifols
    "RED.MC",       # Redeia Corporacion SA (ex Red Electrica)
    "MRL.MC",       # Merlin Properties
    "CLNX.MC",      # Cellnex Telecom
    "FDR.MC",       # Fluidra
    "SAB.MC",       # Banco Sabadell
]

AEX25_SYMBOLS = [
    # Netherlands AEX 25 - Top 25 Dutch companies (Euronext Amsterdam)
    "ASML.AS",      # ASML Holding
    "UNA.AS",       # Unilever (Amsterdam listing)
    "INGA.AS",      # ING Group
    "PHIA.AS",      # Philips
    "AD.AS",        # Ahold Delhaize
    "HEIA.AS",      # Heineken
    "WKL.AS",       # Wolters Kluwer
    "RAND.AS",      # Randstad NV
    "AKZA.AS",      # Akzo Nobel
    "ASRNL.AS",     # ASR Nederland NV
    "NN.AS",        # NN Group
    "AGN.AS",       # Aegon
    "KPN.AS",       # KPN
    "DSM.AS",       # DSM-Firmenich AG
    "ASM.AS",       # ASM International NV
    "PRX.AS",       # Prosus
    "IMCD.AS",      # IMCD
    "ABN.AS",       # ABN AMRO
    "BESI.AS",      # BE Semiconductor
    "LIGHT.AS",     # Signify
]

SMI20_SYMBOLS = [
    # Switzerland SMI 20 - Top 20 Swiss companies (SIX)
    "NESN.SW",      # Nestle
    "NOVN.SW",      # Novartis
    "ROG.SW",       # Roche
    "UBSG.SW",      # UBS Group
    "BAER.SW",      # Julius Baer Group AG
    "ZURN.SW",      # Zurich Insurance
    "ABBN.SW",      # ABB
    "SREN.SW",      # Swiss Re
    "GIVN.SW",      # Givaudan
    "LONN.SW",      # Lonza Group
    "SIKA.SW",      # Sika AG
    "GEBN.SW",      # Geberit
    "SCMN.SW",      # Swisscom
    "SLHN.SW",      # Swiss Life
    "PGHN.SW",      # Partners Group
    "SGSN.SW",      # SGS SA
    "HOLN.SW",      # Holcim
    "SCHP.SW",      # Schindler
    "LOGN.SW",      # Logitech
    "ALC.SW",       # Alcon
]

FTSEMIB_SYMBOLS = [
    # Italy FTSE MIB - Top 20 Italian companies (Borsa Italiana)
    "ISP.MI",       # Intesa Sanpaolo
    "UCG.MI",       # UniCredit
    "ENI.MI",       # Eni
    "ENEL.MI",      # Enel
    "STM.MI",       # STMicroelectronics (Milan listing)
    "G.MI",         # Assicurazioni Generali
    "RACE.MI",      # Ferrari
    "TIT.MI",       # Telecom Italia
    "LDO.MI",       # Leonardo
    "BMED.MI",      # Banca Mediolanum
    "FBK.MI",       # FinecoBank
    "PST.MI",       # Poste Italiane
    "CPR.MI",       # Campari
    "TEN.MI",       # Tenaris
    "PRY.MI",       # Prysmian
    "MONC.MI",      # Moncler
    "STLAM.MI",     # Stellantis (Milan listing)
    "BAMI.MI",      # Banco BPM
    "A2A.MI",       # A2A
    "SRG.MI",       # Snam
]

# Asian Markets (futuro)
NIKKEI225_SYMBOLS = [
    # Japan Nikkei 225 - Top Japanese companies
    "7203.T",       # Toyota Motor Corp
    "6758.T",       # Sony Group Corp
    "6861.T",       # Keyence Corp
    "9984.T",       # SoftBank Group Corp
    "8306.T",       # Mitsubishi UFJ Financial
    "6902.T",       # Denso Corp
    "9432.T",       # NTT (Nippon Telegraph)
    "6501.T",       # Hitachi Ltd
    "6954.T",       # Fanuc Corp
    "7974.T",       # Nintendo Co Ltd
]


def get_all_european_symbols():
    """Retorna todos los simbolos europeos combinados (sin duplicados)"""
    all_symbols = (
        DAX40_SYMBOLS +
        FTSE100_SYMBOLS +
        CAC40_SYMBOLS +
        IBEX35_SYMBOLS +
        AEX25_SYMBOLS +
        SMI20_SYMBOLS +
        FTSEMIB_SYMBOLS
    )
    # Remove duplicates (e.g. STM listed in both Paris and Milan)
    seen = set()
    unique = []
    for s in all_symbols:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def get_european_market_for_ticker(ticker: str) -> str:
    """Retorna el mercado europeo al que pertenece un ticker"""
    suffix_map = {
        '.DE': 'DAX40',
        '.L': 'FTSE100',
        '.PA': 'CAC40',
        '.MC': 'IBEX35',
        '.AS': 'AEX25',
        '.SW': 'SMI20',
        '.MI': 'FTSEMIB',
        '.CO': 'OMXCPH',   # Nasdaq Copenhagen (Dinamarca)
        '.ST': 'OMXSTO',   # Nasdaq Stockholm (Suecia)
        '.HE': 'OMXHEL',   # Nasdaq Helsinki (Finlandia)
        '.OL': 'OSEBX',    # Oslo Børs (Noruega)
        '.HK': 'HKEX',     # Hong Kong Stock Exchange
        '.SS': 'SSE',       # Shanghai Stock Exchange
    }
    for suffix, market in suffix_map.items():
        if ticker.endswith(suffix):
            return market
    return 'OTHER'


# Market Metadata
MARKETS = {
    "USA": {
        "sp500": {
            "name": "S&P 500",
            "size": 500,
            "currency": "USD",
            "timezone": "America/New_York",
            "exchange": "NYSE/NASDAQ",
            "source": SP500_URL,
            "active": True,
        },
        "nasdaq100": {
            "name": "NASDAQ 100",
            "size": 100,
            "currency": "USD",
            "timezone": "America/New_York",
            "exchange": "NASDAQ",
            "source": NASDAQ100_URL,
            "active": False,
        },
    },
    "Germany": {
        "dax40": {
            "name": "DAX 40",
            "size": 40,
            "currency": "EUR",
            "timezone": "Europe/Berlin",
            "exchange": "XETRA",
            "symbols": DAX40_SYMBOLS,
            "active": True,
        },
    },
    "UK": {
        "ftse100": {
            "name": "FTSE 100",
            "size": 100,
            "currency": "GBP",
            "timezone": "Europe/London",
            "exchange": "LSE",
            "symbols": FTSE100_SYMBOLS,
            "active": True,
        },
    },
    "France": {
        "cac40": {
            "name": "CAC 40",
            "size": 40,
            "currency": "EUR",
            "timezone": "Europe/Paris",
            "exchange": "Euronext Paris",
            "symbols": CAC40_SYMBOLS,
            "active": True,
        },
    },
    "Spain": {
        "ibex35": {
            "name": "IBEX 35",
            "size": 35,
            "currency": "EUR",
            "timezone": "Europe/Madrid",
            "exchange": "BME",
            "symbols": IBEX35_SYMBOLS,
            "active": True,
        },
    },
    "Netherlands": {
        "aex25": {
            "name": "AEX 25",
            "size": 25,
            "currency": "EUR",
            "timezone": "Europe/Amsterdam",
            "exchange": "Euronext Amsterdam",
            "symbols": AEX25_SYMBOLS,
            "active": True,
        },
    },
    "Switzerland": {
        "smi20": {
            "name": "SMI 20",
            "size": 20,
            "currency": "CHF",
            "timezone": "Europe/Zurich",
            "exchange": "SIX",
            "symbols": SMI20_SYMBOLS,
            "active": True,
        },
    },
    "Italy": {
        "ftsemib": {
            "name": "FTSE MIB",
            "size": 40,
            "currency": "EUR",
            "timezone": "Europe/Rome",
            "exchange": "Borsa Italiana",
            "symbols": FTSEMIB_SYMBOLS,
            "active": True,
        },
    },
    "Japan": {
        "nikkei225": {
            "name": "Nikkei 225",
            "size": 225,
            "currency": "JPY",
            "timezone": "Asia/Tokyo",
            "exchange": "TSE",
            "symbols": NIKKEI225_SYMBOLS[:10],
            "active": False,
        },
    },
}


def get_active_markets():
    """Retorna solo mercados activos"""
    active = {}
    for region, markets in MARKETS.items():
        for market_id, config in markets.items():
            if config.get("active", False):
                active[f"{region}_{market_id}"] = config
    return active


def get_market_symbols(market_id: str):
    """
    Obtiene símbolos de un mercado específico

    Args:
        market_id: ID del mercado (ej: "Germany_dax40", "USA_sp500")
    """
    region, market = market_id.split("_")

    if region not in MARKETS or market not in MARKETS[region]:
        raise ValueError(f"Mercado no encontrado: {market_id}")

    config = MARKETS[region][market]

    # Si tiene lista de símbolos directa
    if "symbols" in config:
        return config["symbols"]

    # Si tiene URL para scraping (como S&P 500)
    if "source" in config and region == "USA" and market == "sp500":
        import pandas as pd
        df = pd.read_html(config["source"])[0]
        return df['Symbol'].tolist()

    raise ValueError(f"No se pueden obtener símbolos para {market_id}")


if __name__ == "__main__":
    # Test
    print("MERCADOS CONFIGURADOS:")
    print("=" * 60)

    for region, markets in MARKETS.items():
        print(f"\n{region}:")
        for market_id, config in markets.items():
            status = "ACTIVO" if config.get("active") else "FUTURO"
            print(f"  {status} {config['name']} ({config['size']} stocks)")
            print(f"           Exchange: {config['exchange']} | Currency: {config['currency']}")

    print("\n\nMERCADOS ACTIVOS:")
    print("=" * 60)
    active = get_active_markets()
    for market_id, config in active.items():
        print(f"  {market_id}: {config['name']}")

    print(f"\nTotal European symbols: {len(get_all_european_symbols())}")
