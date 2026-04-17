#!/usr/bin/env python3
"""
Sistema Unificado de Insider Trading + DJ Sectorial + Market Breadth + Enhanced Opportunities Analyzer
Versión COMPLETA con Enhanced Trading Opportunities integrado - Con GitHub Pages funcionando
ACTUALIZADO: Incluye Enhanced Trading Opportunity Analyzer con correlaciones automáticas
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import json
import os
import sys
import subprocess
import zipfile
import shutil
from pathlib import Path
import traceback
import re
from typing import Dict, List, Tuple, Optional

# Importar Market Breadth Analyzer
try:
    from market_breadth_analyzer import MarketBreadthAnalyzer, MarketBreadthHTMLGenerator
    MARKET_BREADTH_AVAILABLE = True
    print("✅ Market Breadth Analyzer cargado - MODO COMPLETO (60+ indicadores)")
except ImportError:
    print("⚠️ Market Breadth Analyzer no disponible")
    MARKET_BREADTH_AVAILABLE = False

# Importar el VCP Scanner Enhanced si existe, si no, stub
try:
    from vcp_scanner_usa import VCPScannerEnhanced
except ImportError:
    class VCPScannerEnhanced:
        def __init__(self):
            print("Función no implementada: VCPScannerEnhanced (stub)")
        def scan_market(self):
            return []
        def generate_html(self, results, html_path):
            with open(html_path, "w", encoding="utf-8") as f:
                f.write("<html><body><h1>Función no implementada</h1></body></html>")
            return html_path
        def save_csv(self, results, csv_path):
            pd.DataFrame(results).to_csv(csv_path, index=False)
            return csv_path

# Importar templates HTML
try:
    from templates.html_generator import HTMLGenerator, generate_html_report
    HTML_TEMPLATES_AVAILABLE = True
except ImportError:
    print("⚠️ Templates HTML no disponibles - usando fallback básico")
    HTML_TEMPLATES_AVAILABLE = False

# =============================================
# ENHANCED TRADING OPPORTUNITY ANALYZER INTEGRADO
# =============================================

class EnhancedTradingOpportunityAnalyzer:
    """
    Analizador MEJORADO de oportunidades que incluye interpretaciones automáticas
    NUEVO: Mapeo comprehensivo de tickers a sectores para mejor correlación
    """
    
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.insider_data_history = {}
        self.sector_data_history = {}
        self.consolidated_insider = pd.DataFrame()
        self.consolidated_sector = pd.DataFrame()
        self.analysis_results = {}
        
        # NUEVO: Mapeo comprehensivo de tickers a sectores DJ (igual que en AdvancedTradingScanner)
        self.comprehensive_ticker_mapping = {
            # TECHNOLOGY (DJUSTC)
            'AAPL': 'Technology', 'MSFT': 'Technology', 'GOOGL': 'Technology', 'GOOG': 'Technology',
            'AMZN': 'Technology', 'META': 'Technology', 'NVDA': 'Technology', 'TSLA': 'Technology',
            'NFLX': 'Technology', 'CRM': 'Technology', 'ORCL': 'Technology', 'ADBE': 'Technology',
            'INTC': 'Technology', 'AMD': 'Technology', 'QCOM': 'Technology', 'AVGO': 'Technology',
            'TXN': 'Technology', 'IBM': 'Technology', 'CSCO': 'Technology', 'NOW': 'Technology',
            'SNOW': 'Technology', 'PLTR': 'Technology', 'COIN': 'Technology', 'RBLX': 'Technology',
            'SHOP': 'Technology', 'SQ': 'Technology', 'BLOCK': 'Technology', 'ZM': 'Technology',
            'DOCU': 'Technology', 'TEAM': 'Technology', 'OKTA': 'Technology', 'TWLO': 'Technology',
            
            # BANKS (DJUSBK)
            'JPM': 'Banks', 'BAC': 'Banks', 'WFC': 'Banks', 'C': 'Banks', 'GS': 'Banks',
            'MS': 'Banks', 'USB': 'Banks', 'PNC': 'Banks', 'TFC': 'Banks', 'COF': 'Banks',
            'BK': 'Banks', 'STT': 'Banks', 'SCHW': 'Banks', 'AXP': 'Banks', 'MA': 'Banks',
            'V': 'Banks', 'PYPL': 'Banks', 'DFS': 'Banks', 'SYF': 'Banks', 'ALLY': 'Banks',
            'FITB': 'Banks', 'HBAN': 'Banks', 'RF': 'Banks', 'KEY': 'Banks', 'CFG': 'Banks',
            
            # HEALTHCARE (DJUSHC)
            'JNJ': 'Healthcare', 'UNH': 'Healthcare', 'PFE': 'Healthcare', 'ABBV': 'Healthcare',
            'TMO': 'Healthcare', 'ABT': 'Healthcare', 'DHR': 'Healthcare', 'BMY': 'Healthcare',
            'LLY': 'Healthcare', 'MDT': 'Healthcare', 'GILD': 'Healthcare', 'AMGN': 'Healthcare',
            'CVS': 'Healthcare', 'CI': 'Healthcare', 'HUM': 'Healthcare', 'ANTM': 'Healthcare',
            'ELV': 'Healthcare', 'CNC': 'Healthcare', 'MOH': 'Healthcare', 'HCA': 'Healthcare',
            'ISRG': 'Healthcare', 'SYK': 'Healthcare', 'EW': 'Healthcare', 'ZBH': 'Healthcare',
            'MRNA': 'Healthcare', 'BNTX': 'Healthcare', 'VRTX': 'Healthcare', 'REGN': 'Healthcare',
            
            # OIL & GAS (DJUSEN)
            'XOM': 'Oil & Gas', 'CVX': 'Oil & Gas', 'COP': 'Oil & Gas', 'SLB': 'Oil & Gas',
            'EOG': 'Oil & Gas', 'PSX': 'Oil & Gas', 'VLO': 'Oil & Gas', 'MPC': 'Oil & Gas',
            'KMI': 'Oil & Gas', 'OKE': 'Oil & Gas', 'WMB': 'Oil & Gas', 'EPD': 'Oil & Gas',
            'ET': 'Oil & Gas', 'MPLX': 'Oil & Gas', 'DVN': 'Oil & Gas', 'FANG': 'Oil & Gas',
            'MRO': 'Oil & Gas', 'APA': 'Oil & Gas', 'HAL': 'Oil & Gas', 'BKR': 'Oil & Gas',
            'OXY': 'Oil & Gas', 'PXD': 'Oil & Gas', 'CTRA': 'Oil & Gas', 'EQT': 'Oil & Gas',
            
            # REAL ESTATE (DJUSRE)
            'AMT': 'Real Estate', 'CCI': 'Real Estate', 'EQIX': 'Real Estate', 'PLD': 'Real Estate',
            'SPG': 'Real Estate', 'EXR': 'Real Estate', 'AVB': 'Real Estate', 'EQR': 'Real Estate',
            'WELL': 'Real Estate', 'DLR': 'Real Estate', 'PSA': 'Real Estate', 'O': 'Real Estate',
            'SBAC': 'Real Estate', 'VTR': 'Real Estate', 'ESS': 'Real Estate', 'MAA': 'Real Estate',
            
            # RETAIL (DJUSRT)
            'WMT': 'Retail', 'HD': 'Retail', 'COST': 'Retail', 'LOW': 'Retail', 'TGT': 'Retail',
            'TJX': 'Retail', 'SBUX': 'Retail', 'NKE': 'Retail', 'MCD': 'Retail', 'BKNG': 'Retail',
            'EBAY': 'Retail', 'ETSY': 'Retail', 'W': 'Retail', 'RH': 'Retail', 'BBY': 'Retail',
            
            # UTILITIES (DJUSUT)
            'NEE': 'Utilities', 'DUK': 'Utilities', 'SO': 'Utilities', 'D': 'Utilities',
            'EXC': 'Utilities', 'XEL': 'Utilities', 'SRE': 'Utilities', 'PEG': 'Utilities',
            'AWK': 'Utilities', 'AEP': 'Utilities', 'ED': 'Utilities', 'ES': 'Utilities',
            
            # CHEMICALS (DJUSCH)
            'LIN': 'Chemicals', 'APD': 'Chemicals', 'DD': 'Chemicals', 'DOW': 'Chemicals',
            'ECL': 'Chemicals', 'EMN': 'Chemicals', 'LYB': 'Chemicals', 'CF': 'Chemicals',
            'FMC': 'Chemicals', 'ALB': 'Chemicals', 'CE': 'Chemicals', 'PPG': 'Chemicals',
            
            # INDUSTRIAL GOODS (DJUSIG)
            'BA': 'Industrial Goods', 'CAT': 'Industrial Goods', 'DE': 'Industrial Goods',
            'HON': 'Industrial Goods', 'GE': 'Industrial Goods', 'MMM': 'Industrial Goods',
            'RTX': 'Industrial Goods', 'LMT': 'Industrial Goods', 'NOC': 'Industrial Goods',
            'GD': 'Industrial Goods', 'UPS': 'Industrial Goods', 'FDX': 'Industrial Goods',
            
            # MEDIA (DJUSME)
            'DIS': 'Media', 'CMCSA': 'Media', 'NFLX': 'Media', 'T': 'Media', 'VZ': 'Media',
            'CHTR': 'Media', 'TMUS': 'Media', 'WBD': 'Media', 'PARA': 'Media',
            
            # FOOD & BEVERAGE (DJUSFB)
            'PEP': 'Food & Beverage', 'KO': 'Food & Beverage', 'PG': 'Food & Beverage',
            'UL': 'Food & Beverage', 'MDLZ': 'Food & Beverage', 'GIS': 'Food & Beverage',
            'K': 'Food & Beverage', 'CPB': 'Food & Beverage', 'CAG': 'Food & Beverage',
            'TSN': 'Food & Beverage', 'KR': 'Food & Beverage', 'WBA': 'Food & Beverage',
            
            # Añadir más sectores...
            'AUTOMOBILES & PARTS': 'Auto & Parts',
            'TSLA': 'Auto & Parts', 'F': 'Auto & Parts', 'GM': 'Auto & Parts',
            'RIVN': 'Auto & Parts', 'LCID': 'Auto & Parts', 'NIO': 'Auto & Parts',
        }
        
    def scan_directory_structure(self) -> Dict[str, List[str]]:
        """Escanear automáticamente la estructura de directorios específica del sistema"""
        structure = {
            'insider_dirs': [],
            'sector_dirs': [],
            'insider_files': [],
            'sector_files': []
        }
        
        print(f"🔍 Escaneando estructura desde: {self.base_path}")
        
        # PATRÓN ESPECÍFICO 1: reports/report_YYYY-MM-DD/data.csv (INSIDER TRADING)
        insider_pattern = 'reports/report_*/data.csv'
        insider_files = list(self.base_path.glob(insider_pattern))
        
        for file_path in insider_files:
            structure['insider_files'].append(str(file_path))
            structure['insider_dirs'].append(str(file_path.parent))
        
        # PATRÓN ESPECÍFICO 2: dj_sectorial/dj_sectorial_YYYY-MM-DD/data.csv
        sector_patterns = [
            'dj_sectorial/dj_sectorial_*/data.csv',
            'dj_sectorial_*/data.csv',
            'dj_sectorial/*/data.csv',
            'reports/dj_sectorial_analysis.csv'  # También buscar archivos generados por el sistema principal
        ]
        
        sector_files_found = []
        for pattern in sector_patterns:
            sector_files = list(self.base_path.glob(pattern))
            sector_files_found.extend(sector_files)
            
            for file_path in sector_files:
                if str(file_path) not in structure['sector_files']:
                    structure['sector_files'].append(str(file_path))
                    structure['sector_dirs'].append(str(file_path.parent))
        
        print(f"📄 Encontrados {len(insider_files)} archivos insider")
        print(f"📄 Encontrados {len(sector_files_found)} archivos sectoriales")
        
        return structure
    
    def extract_date_from_path(self, path: str) -> Optional[datetime]:
        """Extraer fecha del nombre del directorio o archivo"""
        # PATRÓN ESPECÍFICO 1: reports/report_2025-06-12/data.csv
        report_pattern = r'report[_/](\d{4}-\d{2}-\d{2})'
        match = re.search(report_pattern, path)
        if match:
            try:
                return datetime.strptime(match.group(1), '%Y-%m-%d')
            except:
                pass
        
        # PATRÓN ESPECÍFICO 2: dj_sectorial/dj_sectorial_2025-06-12/data.csv
        sectorial_pattern = r'dj_sectorial[_/](\d{4}-\d{2}-\d{2})'
        match = re.search(sectorial_pattern, path)
        if match:
            try:
                return datetime.strptime(match.group(1), '%Y-%m-%d')
            except:
                pass
        
        # Fallback: usar fecha del archivo
        try:
            file_path = Path(path)
            if file_path.exists():
                timestamp = file_path.stat().st_mtime
                return datetime.fromtimestamp(timestamp)
        except:
            pass
        
        return datetime.now()
    
    def load_historical_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Cargar datos históricos completos"""
        structure = self.scan_directory_structure()
        
        # Cargar insider data
        if structure['insider_files']:
            self.insider_data_history = self._load_insider_files(structure['insider_files'])
        
        # Cargar sector data
        if structure['sector_files']:
            self.sector_data_history = self._load_sector_files(structure['sector_files'])
        
        return self._consolidate_data()
    
    def _load_insider_files(self, file_paths: List[str]) -> Dict[str, pd.DataFrame]:
        """Cargar archivos insider con manejo mejorado"""
        historical_data = {}
        
        for file_path in file_paths:
            try:
                date = self.extract_date_from_path(file_path)
                date_key = date.strftime('%Y-%m-%d')
                
                raw_data = pd.read_csv(file_path, encoding='utf-8', sep=',', engine='python')
                
                if len(raw_data.columns) >= 10:
                    processed_data = pd.DataFrame({
                        'FileDate': date_key,
                        'ScrapedAt': raw_data.iloc[:, 0],
                        'Ticker': raw_data.iloc[:, 1],
                        'CompanyName': raw_data.iloc[:, 2],
                        'InsiderTitle': raw_data.iloc[:, 3],
                        'Type': raw_data.iloc[:, 4],
                        'Price': pd.to_numeric(raw_data.iloc[:, 5], errors='coerce'),
                        'Qty': pd.to_numeric(raw_data.iloc[:, 6], errors='coerce'),
                        'Owned': pd.to_numeric(raw_data.iloc[:, 7], errors='coerce'),
                        'Value': raw_data.iloc[:, 8],
                        'Source': raw_data.iloc[:, 9]
                    })
                    
                    processed_data['ValueNumeric'] = processed_data['Value'].apply(self._parse_value)
                    processed_data['DaysAgo'] = (datetime.now() - date).days
                    
                    # Limpiar datos
                    processed_data = processed_data.dropna(subset=['Ticker'])
                    processed_data['Ticker'] = processed_data['Ticker'].astype(str).str.strip()
                    processed_data = processed_data[
                        (processed_data['Ticker'] != 'nan') & 
                        (processed_data['Ticker'] != '') & 
                        (processed_data['Ticker'].str.len() > 0)
                    ]
                    
                    if len(processed_data) > 0:
                        historical_data[date_key] = processed_data
                
            except Exception as e:
                print(f"⚠️ Error procesando {file_path}: {e}")
        
        return historical_data
    
    def _load_sector_files(self, file_paths: List[str]) -> Dict[str, pd.DataFrame]:
        """Cargar archivos sectoriales"""
        historical_data = {}
        
        for file_path in file_paths:
            try:
                date = self.extract_date_from_path(file_path)
                date_key = date.strftime('%Y-%m-%d')
                
                sector_data = pd.read_csv(file_path, encoding='utf-8', sep=',', engine='python')
                
                # Agregar metadata temporal
                sector_data['FileDate'] = date_key
                sector_data['DaysAgo'] = (datetime.now() - date).days
                
                # Asegurar tipos correctos
                numeric_columns = ['CurrentPrice', 'Min52w', 'Max52w', 'DistanceFromMin', 'RSI', 'DataPoints']
                for col in numeric_columns:
                    if col in sector_data.columns:
                        sector_data[col] = pd.to_numeric(sector_data[col], errors='coerce')
                
                if len(sector_data) > 0:
                    historical_data[date_key] = sector_data
                
            except Exception as e:
                print(f"⚠️ Error procesando {file_path}: {e}")
        
        return historical_data
    
    def _parse_value(self, value_str) -> float:
        """Convertir strings de valor monetario a números"""
        if pd.isna(value_str) or value_str == '':
            return 0.0
        
        clean_value = str(value_str).replace('$', '').replace(',', '').replace(' ', '').replace('%', '')
        
        multipliers = {'K': 1_000, 'M': 1_000_000, 'B': 1_000_000_000}
        
        for suffix, multiplier in multipliers.items():
            if clean_value.upper().endswith(suffix):
                try:
                    num = float(clean_value[:-1])
                    return num * multiplier
                except:
                    pass
        
        try:
            return float(clean_value)
        except:
            return 0.0
    
    def _consolidate_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Consolidar datos históricos"""
        if self.insider_data_history:
            insider_frames = list(self.insider_data_history.values())
            self.consolidated_insider = pd.concat(insider_frames, ignore_index=True)
        
        if self.sector_data_history:
            sector_frames = list(self.sector_data_history.values())
            self.consolidated_sector = pd.concat(sector_frames, ignore_index=True)
        
        return self.consolidated_insider, self.consolidated_sector
    
    def analyze_enhanced_opportunities(self, recent_days: int = 30) -> Dict:
        """Análisis MEJORADO con interpretaciones automáticas y mapeo robusto"""
        insider_data, sector_data = self.load_historical_data()
        
        if sector_data.empty:
            return {'error': 'No hay datos sectoriales disponibles'}
        
        # Usar datos más recientes por sector
        latest_sectors = sector_data.loc[
            sector_data.groupby('Ticker')['DaysAgo'].idxmin()
        ].copy()
        
        # Calcular scores base
        latest_sectors['BaseScore'] = latest_sectors.apply(self._calculate_sector_score, axis=1)
        
        # MEJORADO: Analizar insider patterns con mapeo robusto
        insider_patterns = self._analyze_insider_patterns_enhanced(insider_data, recent_days)
        sector_mapping = self._create_enhanced_sector_mapping(sector_data)
        
        # Análisis cruzado mejorado
        opportunities = self._perform_enhanced_cross_analysis(
            latest_sectors, insider_patterns, sector_mapping
        )
        
        # NUEVAS INTERPRETACIONES AUTOMÁTICAS
        enhanced_analysis = self._generate_enhanced_interpretations(opportunities)
        
        return {
            'analysis_timestamp': datetime.now().isoformat(),
            'opportunities': opportunities.to_dict('records'),
            'enhanced_analysis': enhanced_analysis,
            'summary': self._generate_enhanced_summary(opportunities),
            'special_patterns': self._detect_advanced_patterns(opportunities),
            'strategic_recommendations': self._generate_strategic_recommendations(opportunities),
            'risk_analysis': self._analyze_risk_distribution(opportunities),
            'upside_calculations': self._calculate_upside_potentials(opportunities),
            'sector_correlations': self._analyze_sector_correlations_enhanced(opportunities),
            'trading_alerts': self._generate_trading_alerts(opportunities),
            'mapping_statistics': self._generate_mapping_statistics(insider_patterns, sector_mapping)
        }
    
    def _calculate_sector_score(self, row) -> int:
        """Calcular score base del sector"""
        score = 0
        
        # Proximidad al mínimo (40%)
        distance_score = max(0, 100 - row['DistanceFromMin'])
        score += distance_score * 0.4
        
        # RSI Score (30%)
        rsi = row['RSI']
        if rsi < 30:
            rsi_score = 100
        elif rsi < 40:
            rsi_score = 80
        elif rsi < 50:
            rsi_score = 60
        elif rsi < 60:
            rsi_score = 40
        else:
            rsi_score = 20
        score += rsi_score * 0.3
        
        # Clasificación (30%)
        classification = row['Classification']
        if classification == 'OPORTUNIDAD':
            class_score = 100
        elif classification == 'CERCA':
            class_score = 70
        elif classification == 'FUERTE':
            class_score = 30
        else:
            class_score = 50
        score += class_score * 0.3
        
        return round(score)
    
    def _analyze_insider_patterns_enhanced(self, insider_data: pd.DataFrame, recent_days: int) -> Dict:
        """Analizar patrones de insider trading MEJORADO"""
        if insider_data.empty:
            return {}
        
        patterns = {}
        recent_cutoff = datetime.now() - timedelta(days=recent_days)
        
        # Filtrar actividad reciente
        recent_data = insider_data[insider_data['DaysAgo'] <= recent_days]
        
        print(f"🏛️ Analizando insider patterns...")
        print(f"   📊 Total trades: {len(insider_data)}")
        print(f"   📈 Trades recientes ({recent_days}d): {len(recent_data)}")
        print(f"   🏢 Empresas únicas: {insider_data['Ticker'].nunique()}")
        
        # Agrupar por ticker
        for ticker in insider_data['Ticker'].unique():
            ticker_data = insider_data[insider_data['Ticker'] == ticker]
            ticker_recent = recent_data[recent_data['Ticker'] == ticker]
            
            total_trades = len(ticker_data)
            recent_trades = len(ticker_recent)
            
            buy_trades = len(ticker_data[
                ticker_data['Type'].str.contains('Purchase|Buy', case=False, na=False)
            ])
            recent_buys = len(ticker_recent[
                ticker_recent['Type'].str.contains('Purchase|Buy', case=False, na=False)
            ])
            
            total_value = ticker_data['ValueNumeric'].sum()
            recent_value = ticker_recent['ValueNumeric'].sum()
            
            exec_trades = len(ticker_data[
                ticker_data['InsiderTitle'].str.contains(
                    'CEO|CFO|President|Chairman|Director', case=False, na=False
                )
            ])
            
            patterns[ticker] = {
                'total_trades': total_trades,
                'recent_trades': recent_trades,
                'buy_ratio': buy_trades / max(total_trades, 1),
                'recent_buy_ratio': recent_buys / max(recent_trades, 1) if recent_trades > 0 else 0,
                'total_value': total_value,
                'recent_value': recent_value,
                'executive_trades': exec_trades,
                'activity_trend': 'INCREASING' if recent_trades > total_trades/4 else 'STABLE',
                'latest_activity_days': ticker_data['DaysAgo'].min(),
                'sector': self.comprehensive_ticker_mapping.get(ticker, 'Unknown')
            }
        
        return patterns
    
    def _create_enhanced_sector_mapping(self, sector_data: pd.DataFrame) -> Dict[str, str]:
        """Crear mapeo mejorado de tickers a sectores"""
        mapping = {}
        
        # PASO 1: Usar el mapeo comprehensivo como base
        mapping.update(self.comprehensive_ticker_mapping)
        
        # PASO 2: Sobrescribir con datos dinámicos si están disponibles
        if not sector_data.empty and 'Ticker' in sector_data.columns and 'Sector' in sector_data.columns:
            latest_sectors = sector_data.loc[
                sector_data.groupby('Ticker')['DaysAgo'].idxmin()
            ]
            
            for _, row in latest_sectors.iterrows():
                if pd.notna(row['Ticker']) and pd.notna(row['Sector']):
                    mapping[str(row['Ticker']).strip()] = str(row['Sector']).strip()
        
        print(f"🎯 Mapeo mejorado creado: {len(mapping)} tickers mapeados")
        return mapping
    
    def _perform_enhanced_cross_analysis(self, latest_sectors, insider_patterns, sector_mapping) -> pd.DataFrame:
        """Análisis cruzado mejorado con estadísticas detalladas"""
        # Agregar información de insider por sector
        sector_insider_activity = {}
        mapped_tickers = 0
        total_insider_tickers = len(insider_patterns)
        
        for ticker, trend in insider_patterns.items():
            sector = sector_mapping.get(ticker, 'Unknown')
            
            if sector != 'Unknown':
                mapped_tickers += 1
                
                if sector not in sector_insider_activity:
                    sector_insider_activity[sector] = {
                        'total_trades': 0,
                        'recent_trades': 0,
                        'total_value': 0,
                        'recent_value': 0,
                        'tickers_with_activity': set(),
                        'executive_activity': 0,
                        'increasing_activity': 0,
                        'insider_tickers': []
                    }
                
                activity = sector_insider_activity[sector]
                activity['total_trades'] += trend['total_trades']
                activity['recent_trades'] += trend['recent_trades']
                activity['total_value'] += trend['total_value']
                activity['recent_value'] += trend['recent_value']
                activity['tickers_with_activity'].add(ticker)
                activity['executive_activity'] += trend['executive_trades']
                activity['insider_tickers'].append(ticker)
                
                if trend['activity_trend'] == 'INCREASING':
                    activity['increasing_activity'] += 1
        
        # Estadísticas de mapeo
        mapping_coverage = (mapped_tickers / total_insider_tickers * 100) if total_insider_tickers > 0 else 0
        
        print(f"\n🔗 ESTADÍSTICAS DE CORRELACIÓN:")
        print(f"   📊 Tickers insider: {total_insider_tickers}")
        print(f"   ✅ Tickers mapeados: {mapped_tickers}")
        print(f"   📈 Sectores con actividad: {len(sector_insider_activity)}")
        print(f"   🎯 Cobertura: {mapping_coverage:.1f}%")
        
        # Crear análisis final con bonificaciones
        results = []
        for _, sector in latest_sectors.iterrows():
            sector_name = sector['Sector']
            base_score = sector['BaseScore']
            
            insider_activity = sector_insider_activity.get(sector_name, {})
            
            final_score = base_score
            signals = []
            urgency = 'BAJA'
            
            # Bonificaciones por actividad insider
            if insider_activity.get('recent_trades', 0) > 0:
                recent_bonus = min(insider_activity['recent_trades'] * 8, 30)
                final_score += recent_bonus
                signals.append(f"{insider_activity['recent_trades']} trades recientes")
                
                if len(insider_activity.get('tickers_with_activity', set())) > 1:
                    final_score += 15
                    signals.append('Múltiples empresas comprando')
                    urgency = 'MEDIA'
                
                if insider_activity.get('executive_activity', 0) > 0:
                    final_score += 12
                    signals.append('Actividad ejecutiva')
                    urgency = 'ALTA'
                
                if insider_activity.get('recent_value', 0) > 1_000_000:
                    final_score += 20
                    signals.append(f"${insider_activity['recent_value']/1_000_000:.1f}M volumen")
                    urgency = 'ALTA'
                
                if insider_activity.get('increasing_activity', 0) > 0:
                    final_score += 10
                    signals.append('Tendencia creciente')
            
            # Determinar urgencia final
            if final_score >= 85 and sector['DistanceFromMin'] < 15:
                urgency = 'CRÍTICA'
            elif final_score >= 75:
                urgency = 'ALTA'
            elif final_score >= 60:
                urgency = 'MEDIA'
            
            results.append({
                **sector.to_dict(),
                'BaseScore': base_score,
                'FinalScore': min(final_score, 100),
                'InsiderActivity': len(insider_activity) > 0,
                'InsiderTrades': insider_activity.get('recent_trades', 0),
                'InsiderValue': insider_activity.get('recent_value', 0),
                'InsiderTickers': insider_activity.get('insider_tickers', []),
                'Signals': signals,
                'Urgency': urgency,
                'RiskLevel': self._calculate_risk_level(sector, insider_activity),
                'MappingCoverage': mapping_coverage
            })
        
        results_df = pd.DataFrame(results)
        return results_df.sort_values('FinalScore', ascending=False)
    
    def _calculate_risk_level(self, sector, insider_activity) -> str:
        """Calcular nivel de riesgo"""
        risk_score = 0
        
        rsi = sector.get('RSI', 50)
        if rsi > 70:
            risk_score += 3
        elif rsi > 60:
            risk_score += 2
        elif rsi < 30:
            risk_score -= 1
        
        distance = sector.get('DistanceFromMin', 50)
        if distance > 40:
            risk_score += 2
        elif distance < 10:
            risk_score -= 1
        
        if insider_activity.get('recent_trades', 0) > 2:
            risk_score -= 2
        if insider_activity.get('executive_activity', 0) > 0:
            risk_score -= 1
        
        if risk_score <= 0:
            return 'BAJO'
        elif risk_score <= 2:
            return 'MEDIO'
        else:
            return 'ALTO'
    
    def _generate_enhanced_interpretations(self, opportunities: pd.DataFrame) -> Dict:
        """Generar interpretaciones automáticas MEJORADAS"""
        if opportunities.empty:
            return {}
        
        interpretations = {
            'market_overview': self._interpret_market_overview(opportunities),
            'top_opportunities_analysis': self._interpret_top_opportunities(opportunities),
            'insider_activity_analysis': self._interpret_insider_activity_enhanced(opportunities),
            'risk_reward_analysis': self._interpret_risk_reward(opportunities),
            'sector_strength_analysis': self._interpret_sector_strengths(opportunities),
            'timing_analysis': self._interpret_timing_signals(opportunities),
            'correlation_analysis': self._interpret_correlation_quality(opportunities)
        }
        
        return interpretations
    
    def _interpret_market_overview(self, opportunities: pd.DataFrame) -> Dict:
        """Interpretar panorama general del mercado"""
        total_sectors = len(opportunities)
        critical_count = len(opportunities[opportunities['Urgency'] == 'CRÍTICA'])
        high_urgency = len(opportunities[opportunities['Urgency'].isin(['CRÍTICA', 'ALTA'])])
        with_insider = len(opportunities[opportunities['InsiderActivity'] == True])
        avg_score = opportunities['FinalScore'].mean()
        mapping_coverage = opportunities['MappingCoverage'].iloc[0] if len(opportunities) > 0 else 0
        
        # Interpretar el estado del mercado
        if critical_count >= 4:
            market_state = "EXCEPCIONAL"
            market_desc = f"Mercado en estado excepcional con {critical_count} oportunidades críticas detectadas"
        elif high_urgency >= 8:
            market_state = "FAVORABLE"
            market_desc = f"Mercado favorable con {high_urgency} oportunidades de alta calidad"
        elif avg_score >= 65:
            market_state = "NORMAL"
            market_desc = "Mercado en estado normal con oportunidades moderadas"
        else:
            market_state = "DESAFIANTE"
            market_desc = "Mercado desafiante con pocas oportunidades claras"
        
        return {
            'market_state': market_state,
            'description': market_desc,
            'total_sectors_analyzed': total_sectors,
            'critical_opportunities': critical_count,
            'high_quality_opportunities': high_urgency,
            'sectors_with_insider_activity': with_insider,
            'average_opportunity_score': round(avg_score, 1),
            'mapping_coverage_percentage': round(mapping_coverage, 1),
            'market_sentiment': 'BULLISH' if critical_count >= 3 else 'NEUTRAL' if high_urgency >= 5 else 'BEARISH'
        }
    
    def _interpret_insider_activity_enhanced(self, opportunities: pd.DataFrame) -> Dict:
        """Interpretar actividad insider MEJORADA"""
        with_insider = opportunities[opportunities['InsiderActivity'] == True]
        
        if len(with_insider) == 0:
            return {
                'status': 'SIN_ACTIVIDAD',
                'description': 'No se detectó actividad insider significativa en los sectores analizados',
                'recommendation': 'Monitorear actividad insider en próximos días',
                'mapping_note': 'Verificar que los tickers insider estén en el mapeo sectorial'
            }
        
        total_insider_volume = with_insider['InsiderValue'].sum()
        avg_insider_trades = with_insider['InsiderTrades'].mean()
        total_insider_tickers = sum([len(tickers) for tickers in with_insider['InsiderTickers']])
        
        # Encontrar el sector con mayor actividad insider
        top_insider = with_insider.loc[with_insider['InsiderValue'].idxmax()]
        
        if len(with_insider) >= 3:
            status = 'ACTIVIDAD_ALTA'
            description = f"Alta actividad insider detectada en {len(with_insider)} sectores con {total_insider_tickers} empresas"
        elif total_insider_volume > 2_000_000:
            status = 'VOLUMEN_ALTO'
            description = f"Volumen insider significativo de ${total_insider_volume/1_000_000:.1f}M"
        else:
            status = 'ACTIVIDAD_MODERADA'
            description = f"Actividad insider moderada en {len(with_insider)} sectores"
        
        return {
            'status': status,
            'description': description,
            'sectors_with_activity': len(with_insider),
            'total_volume_millions': round(total_insider_volume / 1_000_000, 1),
            'total_companies_with_insider': total_insider_tickers,
            'average_trades_per_sector': round(avg_insider_trades, 1),
            'top_insider_sector': {
                'sector': top_insider['Sector'],
                'volume_millions': round(top_insider['InsiderValue'] / 1_000_000, 1),
                'trades': top_insider['InsiderTrades'],
                'companies': len(top_insider['InsiderTickers'])
            },
            'recommendation': 'SEGUIMIENTO_PRIORITARIO' if status == 'ACTIVIDAD_ALTA' else 'MONITOREAR'
        }
    
    def _interpret_correlation_quality(self, opportunities: pd.DataFrame) -> Dict:
        """Nueva función: Interpretar calidad de correlaciones"""
        if opportunities.empty:
            return {}
        
        mapping_coverage = opportunities['MappingCoverage'].iloc[0] if len(opportunities) > 0 else 0
        with_insider = len(opportunities[opportunities['InsiderActivity'] == True])
        total_sectors = len(opportunities)
        
        # Evaluar calidad del mapeo
        if mapping_coverage >= 80:
            mapping_quality = 'EXCELENTE'
            mapping_desc = f"Cobertura excelente ({mapping_coverage:.1f}%) del mapeo ticker-sector"
        elif mapping_coverage >= 60:
            mapping_quality = 'BUENA'
            mapping_desc = f"Buena cobertura ({mapping_coverage:.1f}%) del mapeo ticker-sector"
        elif mapping_coverage >= 40:
            mapping_quality = 'MODERADA'
            mapping_desc = f"Cobertura moderada ({mapping_coverage:.1f}%) - considerar expandir mapeo"
        else:
            mapping_quality = 'DEFICIENTE'
            mapping_desc = f"Cobertura deficiente ({mapping_coverage:.1f}%) - mapeo necesita mejoras"
        
        correlation_rate = (with_insider / total_sectors * 100) if total_sectors > 0 else 0
        
        return {
            'mapping_quality': mapping_quality,
            'mapping_description': mapping_desc,
            'mapping_coverage_percentage': round(mapping_coverage, 1),
            'correlation_rate_percentage': round(correlation_rate, 1),
            'sectors_correlated': with_insider,
            'total_sectors': total_sectors,
            'improvement_suggestion': self._suggest_mapping_improvements(mapping_coverage, correlation_rate)
        }
    
    def _suggest_mapping_improvements(self, mapping_coverage: float, correlation_rate: float) -> str:
        """Sugerir mejoras en el mapeo"""
        if mapping_coverage < 50:
            return "Expandir mapeo de tickers a sectores, especialmente para empresas mid-cap y small-cap"
        elif correlation_rate < 20:
            return "Buscar más fuentes de insider trading o ampliar ventana temporal de análisis"
        elif mapping_coverage < 70:
            return "Añadir más tickers del sector tecnológico y financiero al mapeo"
        else:
            return "Mapeo funcionando bien, considerar añadir sectores emergentes"
    
    def _interpret_top_opportunities(self, opportunities: pd.DataFrame) -> List[Dict]:
        """Interpretar las mejores oportunidades"""
        top_5 = opportunities.head(5)
        interpretations = []
        
        for _, opp in top_5.iterrows():
            # Calcular upside potential
            current_price = opp['CurrentPrice']
            max_52w = opp['Max52w']
            upside_to_max = ((max_52w - current_price) / current_price) * 100
            
            # Interpretar la oportunidad
            interpretation = {
                'sector': opp['Sector'],
                'ticker': opp['Ticker'],
                'final_score': opp['FinalScore'],
                'urgency': opp['Urgency'],
                'distance_from_min': round(opp['DistanceFromMin'], 1),
                'upside_to_max_52w': round(upside_to_max, 1),
                'current_price': current_price,
                'target_price_52w_max': max_52w,
                'insider_activity': opp['InsiderActivity'],
                'insider_companies': len(opp['InsiderTickers']) if opp['InsiderActivity'] else 0,
                'risk_level': opp['RiskLevel']
            }
            
            # Generar descripción interpretativa
            if opp['Urgency'] == 'CRÍTICA' and opp['DistanceFromMin'] < 10:
                interpretation['description'] = f"OPORTUNIDAD EXCEPCIONAL: {opp['Sector']} a solo {opp['DistanceFromMin']:.1f}% del mínimo con potencial upside de {upside_to_max:.1f}%"
                interpretation['recommendation'] = "COMPRA INMEDIATA"
            elif opp['InsiderActivity'] and opp['FinalScore'] >= 90:
                interpretation['description'] = f"SEÑAL INSIDER FUERTE: {opp['Sector']} con {len(opp['InsiderTickers'])} empresas comprando"
                interpretation['recommendation'] = "COMPRA PRIORITARIA"
            elif opp['FinalScore'] >= 80:
                interpretation['description'] = f"OPORTUNIDAD SÓLIDA: {opp['Sector']} con score alto y riesgo {opp['RiskLevel'].lower()}"
                interpretation['recommendation'] = "CONSIDERAR COMPRA"
            else:
                interpretation['description'] = f"OPORTUNIDAD MODERADA: {opp['Sector']} en seguimiento"
                interpretation['recommendation'] = "MONITOREAR"
            
            interpretations.append(interpretation)
        
        return interpretations
    
    def _interpret_risk_reward(self, opportunities: pd.DataFrame) -> Dict:
        """Interpretar análisis riesgo-recompensa"""
        # Categorizar por riesgo
        low_risk = opportunities[opportunities['RiskLevel'] == 'BAJO']
        medium_risk = opportunities[opportunities['RiskLevel'] == 'MEDIO']
        high_risk = opportunities[opportunities['RiskLevel'] == 'ALTO']
        
        # Calcular métricas de upside
        opportunities_copy = opportunities.copy()
        opportunities_copy['UpsideToMax'] = ((opportunities_copy['Max52w'] - opportunities_copy['CurrentPrice']) / opportunities_copy['CurrentPrice']) * 100
        
        avg_upside_low_risk = opportunities_copy[opportunities_copy['RiskLevel'] == 'BAJO']['UpsideToMax'].mean()
        
        # Identificar las mejores relaciones riesgo-recompensa
        best_risk_reward = opportunities_copy[
            (opportunities_copy['RiskLevel'] == 'BAJO') & 
            (opportunities_copy['FinalScore'] >= 75)
        ].head(3)
        
        return {
            'risk_distribution': {
                'low_risk_count': len(low_risk),
                'medium_risk_count': len(medium_risk),
                'high_risk_count': len(high_risk)
            },
            'average_upside_low_risk': round(avg_upside_low_risk, 1) if not pd.isna(avg_upside_low_risk) else 0,
            'best_risk_reward_opportunities': [
                {
                    'sector': row['Sector'],
                    'score': row['FinalScore'],
                    'upside': round(row['UpsideToMax'], 1),
                    'risk': row['RiskLevel'],
                    'insider_activity': row['InsiderActivity']
                }
                for _, row in best_risk_reward.iterrows()
            ],
            'recommendation': 'ENFOCARSE_BAJO_RIESGO' if len(low_risk) >= 5 else 'DIVERSIFICAR_RIESGO'
        }
    
    def _interpret_sector_strengths(self, opportunities: pd.DataFrame) -> List[Dict]:
        """Interpretar fortalezas sectoriales"""
        sector_analysis = []
        
        # Agrupar por sectores similares
        sector_groups = {
            'Healthcare': ['Healthcare', 'Healthcare Equipment', 'Pharmaceuticals'],
            'Technology': ['Technology', 'Software', 'Tech Hardware'],
            'Energy': ['Oil & Gas', 'Oil Producers', 'Energy'],
            'Consumer': ['Food & Beverage', 'Household Goods', 'Beverages', 'Food Producers', 'Retail'],
            'Financial': ['Banks', 'Financials', 'Insurance'],
            'Industrial': ['Industrial Transport', 'General Industrial', 'Support Services', 'Industrial Goods'],
            'Real Estate': ['Real Estate', 'REITs'],
            'Utilities': ['Utilities'],
            'Materials': ['Chemicals', 'Basic Resources', 'Construction']
        }
        
        for group_name, sectors in sector_groups.items():
            group_opportunities = opportunities[opportunities['Sector'].isin(sectors)]
            
            if len(group_opportunities) > 0:
                avg_score = group_opportunities['FinalScore'].mean()
                critical_count = len(group_opportunities[group_opportunities['Urgency'] == 'CRÍTICA'])
                with_insider = len(group_opportunities[group_opportunities['InsiderActivity'] == True])
                total_insider_companies = sum([len(tickers) for tickers in group_opportunities['InsiderTickers']])
                
                # Determinar fortaleza del grupo
                if critical_count >= 2:
                    strength = 'MUY_FUERTE'
                elif avg_score >= 75:
                    strength = 'FUERTE'
                elif avg_score >= 60:
                    strength = 'MODERADO'
                else:
                    strength = 'DÉBIL'
                
                sector_analysis.append({
                    'sector_group': group_name,
                    'strength': strength,
                    'opportunities_count': len(group_opportunities),
                    'average_score': round(avg_score, 1),
                    'critical_opportunities': critical_count,
                    'insider_activity_count': with_insider,
                    'total_insider_companies': total_insider_companies,
                    'top_sector': group_opportunities.iloc[0]['Sector'] if len(group_opportunities) > 0 else None
                })
        
        return sorted(sector_analysis, key=lambda x: x['average_score'], reverse=True)
    
    def _interpret_timing_signals(self, opportunities: pd.DataFrame) -> Dict:
        """Interpretar señales de timing"""
        # Analizar distribución de RSI
        oversold = opportunities[opportunities['RSI'] < 30]
        neutral = opportunities[(opportunities['RSI'] >= 30) & (opportunities['RSI'] <= 70)]
        overbought = opportunities[opportunities['RSI'] > 70]
        
        # Analizar proximidad a mínimos
        very_close_to_min = opportunities[opportunities['DistanceFromMin'] < 10]
        close_to_min = opportunities[(opportunities['DistanceFromMin'] >= 10) & (opportunities['DistanceFromMin'] < 25)]
        
        # Determinar timing general del mercado
        if len(oversold) >= 3 and len(very_close_to_min) >= 3:
            timing_signal = 'EXCELENTE'
            timing_desc = 'Timing excepcional: múltiples sectores en sobreventa cerca de mínimos'
        elif len(oversold) >= 2 or len(very_close_to_min) >= 4:
            timing_signal = 'BUENO'
            timing_desc = 'Buen timing: varios sectores en zona de compra'
        elif len(overbought) >= 3:
            timing_signal = 'PRECAUCIÓN'
            timing_desc = 'Timing de precaución: varios sectores sobrecomprados'
        else:
            timing_signal = 'NEUTRAL'
            timing_desc = 'Timing neutral: mercado en zona equilibrada'
        
        return {
            'overall_timing': timing_signal,
            'description': timing_desc,
            'oversold_count': len(oversold),
            'very_close_to_min_count': len(very_close_to_min),
            'overbought_count': len(overbought),
            'recommendation': 'ACTUAR_AHORA' if timing_signal == 'EXCELENTE' else 'ESPERAR' if timing_signal == 'PRECAUCIÓN' else 'SELECTIVO'
        }
    
    def _generate_enhanced_summary(self, opportunities: pd.DataFrame) -> Dict:
        """Generar resumen mejorado"""
        if opportunities.empty:
            return {}
        
        return {
            'total_opportunities': len(opportunities),
            'critical_count': len(opportunities[opportunities['Urgency'] == 'CRÍTICA']),
            'high_urgency_count': len(opportunities[opportunities['Urgency'].isin(['CRÍTICA', 'ALTA'])]),
            'with_insider_activity': len(opportunities[opportunities['InsiderActivity'] == True]),
            'average_score': round(opportunities['FinalScore'].mean(), 1),
            'top_score': opportunities['FinalScore'].max(),
            'low_risk_opportunities': len(opportunities[opportunities['RiskLevel'] == 'BAJO']),
            'sectors_near_minimum': len(opportunities[opportunities['DistanceFromMin'] < 10]),
            'total_insider_volume_millions': round(opportunities['InsiderValue'].sum() / 1_000_000, 1),
            'mapping_coverage': round(opportunities['MappingCoverage'].iloc[0], 1) if len(opportunities) > 0 else 0,
            'correlation_effectiveness': round((len(opportunities[opportunities['InsiderActivity'] == True]) / len(opportunities)) * 100, 1)
        }
    
    def _detect_advanced_patterns(self, opportunities: pd.DataFrame) -> List[Dict]:
        """Detectar patrones avanzados"""
        patterns = []
        
        for _, opp in opportunities.iterrows():
            # Golden Cross Pattern
            if (opp['InsiderActivity'] and 
                opp['InsiderTrades'] >= 2 and 
                opp['DistanceFromMin'] < 12 and
                opp['Classification'] == 'OPORTUNIDAD'):
                patterns.append({
                    'type': 'GOLDEN_CROSS',
                    'sector': opp['Sector'],
                    'description': f'Patrón Golden Cross: {len(opp["InsiderTickers"])} empresas comprando cerca del mínimo ({opp["DistanceFromMin"]:.1f}%)',
                    'urgency': 'CRÍTICA',
                    'score': opp['FinalScore'],
                    'confidence': 'ALTA'
                })
            
            # Volume Explosion Pattern
            if opp['InsiderValue'] > 2_000_000 and opp['InsiderTrades'] >= 3:
                patterns.append({
                    'type': 'VOLUME_EXPLOSION',
                    'sector': opp['Sector'],
                    'description': f'Explosión de volumen: ${opp["InsiderValue"]/1_000_000:.1f}M con {len(opp["InsiderTickers"])} empresas',
                    'urgency': 'ALTA',
                    'score': opp['FinalScore'],
                    'confidence': 'ALTA'
                })
        
        return sorted(patterns, key=lambda x: x['score'], reverse=True)
    
    def _generate_strategic_recommendations(self, opportunities: pd.DataFrame) -> Dict:
        """Generar recomendaciones estratégicas"""
        if opportunities.empty:
            return {}
        
        top_10 = opportunities.head(10)
        
        # Estrategias por plazo
        short_term = top_10[
            (top_10['Urgency'].isin(['CRÍTICA', 'ALTA'])) &
            (top_10['InsiderActivity'] == True)
        ].head(3)
        
        medium_term = top_10[
            (top_10['RiskLevel'] == 'BAJO') &
            (top_10['DistanceFromMin'] < 15)
        ].head(5)
        
        long_term = top_10[top_10['Classification'] == 'OPORTUNIDAD'].head(5)
        
        return {
            'short_term_strategy': {
                'timeframe': '1-3 meses',
                'focus': 'Aprovechar actividad insider y momentum',
                'recommended_sectors': short_term['Sector'].tolist(),
                'allocation_suggestion': '30-40% del capital disponible',
                'insider_companies_total': sum([len(tickers) for tickers in short_term['InsiderTickers']])
            },
            'medium_term_strategy': {
                'timeframe': '3-12 meses',
                'focus': 'Sectores defensivos cerca de mínimos',
                'recommended_sectors': medium_term['Sector'].tolist(),
                'allocation_suggestion': '40-50% del capital disponible'
            },
            'long_term_strategy': {
                'timeframe': '12+ meses',
                'focus': 'Sectores fundamentalmente sólidos',
                'recommended_sectors': long_term['Sector'].tolist(),
                'allocation_suggestion': '20-30% del capital disponible'
            }
        }
    
    def _analyze_risk_distribution(self, opportunities: pd.DataFrame) -> Dict:
        """Analizar distribución de riesgo"""
        risk_dist = opportunities['RiskLevel'].value_counts().to_dict()
        
        return {
            'distribution': risk_dist,
            'low_risk_percentage': round((risk_dist.get('BAJO', 0) / len(opportunities)) * 100, 1),
            'concentration_risk': 'ALTO' if len(opportunities[:5]['Sector'].unique()) < 4 else 'BAJO',
            'diversification_recommendation': 'Diversificar entre sectores' if len(opportunities[:10]['Sector'].unique()) < 6 else 'Buena diversificación disponible'
        }
    
    def _calculate_upside_potentials(self, opportunities: pd.DataFrame) -> List[Dict]:
        """Calcular potenciales de upside"""
        upside_analysis = []
        
        for _, opp in opportunities.head(10).iterrows():
            current_price = opp['CurrentPrice']
            max_52w = opp['Max52w']
            min_52w = opp['Min52w']
            
            upside_to_max = ((max_52w - current_price) / current_price) * 100
            upside_to_avg = ((((max_52w + min_52w) / 2) - current_price) / current_price) * 100
            
            upside_analysis.append({
                'sector': opp['Sector'],
                'current_price': current_price,
                'upside_to_52w_max_percent': round(upside_to_max, 1),
                'upside_to_52w_avg_percent': round(upside_to_avg, 1),
                'target_price_max': max_52w,
                'target_price_avg': round((max_52w + min_52w) / 2, 2),
                'risk_adjusted_upside': round(upside_to_max * (1 if opp['RiskLevel'] == 'BAJO' else 0.7 if opp['RiskLevel'] == 'MEDIO' else 0.5), 1),
                'insider_support': opp['InsiderActivity'],
                'insider_companies': len(opp['InsiderTickers']) if opp['InsiderActivity'] else 0
            })
        
        return upside_analysis
    
    def _analyze_sector_correlations_enhanced(self, opportunities: pd.DataFrame) -> Dict:
        """Analizar correlaciones sectoriales MEJORADO"""
        # Análisis mejorado de correlaciones
        sectors_by_group = {}
        
        for _, opp in opportunities.iterrows():
            sector = opp['Sector']
            
            # Clasificar por grupos
            if any(word in sector.lower() for word in ['healthcare', 'pharmaceutical', 'health']):
                group = 'Healthcare'
            elif any(word in sector.lower() for word in ['technology', 'software', 'tech']):
                group = 'Technology'
            elif any(word in sector.lower() for word in ['oil', 'gas', 'energy']):
                group = 'Energy'
            elif any(word in sector.lower() for word in ['food', 'beverage', 'household', 'retail']):
                group = 'Consumer'
            elif any(word in sector.lower() for word in ['bank', 'financial', 'insurance']):
                group = 'Financial'
            elif any(word in sector.lower() for word in ['real estate', 'reit']):
                group = 'Real Estate'
            else:
                group = 'Other'
            
            if group not in sectors_by_group:
                sectors_by_group[group] = {
                    'scores': [],
                    'insider_activity': 0,
                    'sectors': []
                }
            
            sectors_by_group[group]['scores'].append(opp['FinalScore'])
            sectors_by_group[group]['sectors'].append(sector)
            if opp['InsiderActivity']:
                sectors_by_group[group]['insider_activity'] += 1
        
        # Calcular scores promedio por grupo
        group_analysis = {}
        for group, data in sectors_by_group.items():
            group_analysis[group] = {
                'average_score': round(np.mean(data['scores']), 1),
                'sector_count': len(data['scores']),
                'insider_activity_count': data['insider_activity'],
                'insider_rate': round((data['insider_activity'] / len(data['scores'])) * 100, 1),
                'sectors': data['sectors']
            }
        
        return {
            'sector_groups': {k: v['sector_count'] for k, v in group_analysis.items()},
            'group_average_scores': {k: v['average_score'] for k, v in group_analysis.items()},
            'group_insider_rates': {k: v['insider_rate'] for k, v in group_analysis.items()},
            'strongest_sector_group': max(group_analysis.items(), key=lambda x: x[1]['average_score'])[0] if group_analysis else None,
            'most_insider_active_group': max(group_analysis.items(), key=lambda x: x[1]['insider_rate'])[0] if group_analysis else None,
            'diversification_available': len(group_analysis) >= 4,
            'detailed_analysis': group_analysis
        }
    
    def _generate_trading_alerts(self, opportunities: pd.DataFrame) -> List[Dict]:
        """Generar alertas de trading"""
        alerts = []
        
        # Alertas críticas
        critical_opps = opportunities[opportunities['Urgency'] == 'CRÍTICA']
        for _, opp in critical_opps.iterrows():
            alerts.append({
                'type': 'CRITICAL_OPPORTUNITY',
                'sector': opp['Sector'],
                'message': f"Oportunidad crítica: {opp['Sector']} a {opp['DistanceFromMin']:.1f}% del mínimo con {len(opp['InsiderTickers'])} empresas comprando",
                'action': 'COMPRAR_INMEDIATAMENTE',
                'score': opp['FinalScore'],
                'urgency': 'CRÍTICA',
                'insider_companies': len(opp['InsiderTickers'])
            })
        
        return sorted(alerts, key=lambda x: x['score'], reverse=True)
    
    def _generate_mapping_statistics(self, insider_patterns: Dict, sector_mapping: Dict) -> Dict:
        """Nueva función: Generar estadísticas del mapeo"""
        total_insider_tickers = len(insider_patterns)
        mapped_tickers = sum(1 for ticker in insider_patterns.keys() if sector_mapping.get(ticker, 'Unknown') != 'Unknown')
        coverage = (mapped_tickers / total_insider_tickers * 100) if total_insider_tickers > 0 else 0
        
        # Analizar sectores más activos
        sector_activity = {}
        for ticker, pattern in insider_patterns.items():
            sector = sector_mapping.get(ticker, 'Unknown')
            if sector != 'Unknown':
                if sector not in sector_activity:
                    sector_activity[sector] = {
                        'tickers': [],
                        'total_trades': 0,
                        'total_value': 0
                    }
                sector_activity[sector]['tickers'].append(ticker)
                sector_activity[sector]['total_trades'] += pattern['total_trades']
                sector_activity[sector]['total_value'] += pattern['total_value']
        
        return {
            'total_insider_tickers': total_insider_tickers,
            'mapped_tickers': mapped_tickers,
            'mapping_coverage_percentage': round(coverage, 1),
            'total_mappings_available': len(sector_mapping),
            'sectors_with_insider_activity': len(sector_activity),
            'most_active_sectors': sorted(
                sector_activity.items(), 
                key=lambda x: x[1]['total_trades'], 
                reverse=True
            )[:5],
            'coverage_quality': 'EXCELENTE' if coverage >= 80 else 'BUENA' if coverage >= 60 else 'MODERADA' if coverage >= 40 else 'DEFICIENTE'
        }
    
    def generate_enhanced_html_report(self, analysis_results: Dict) -> str:
        """Generar reporte HTML mejorado con todas las interpretaciones"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if 'error' in analysis_results:
            return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Error en Análisis</title></head>
<body><h1>Error: {analysis_results['error']}</h1></body></html>"""
        
        enhanced_analysis = analysis_results.get('enhanced_analysis', {})
        opportunities = analysis_results.get('opportunities', [])
        summary = analysis_results.get('summary', {})
        patterns = analysis_results.get('special_patterns', [])
        strategic_recs = analysis_results.get('strategic_recommendations', {})
        mapping_stats = analysis_results.get('mapping_statistics', {})
        
        # Generar HTML moderno mejorado
        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎯 Enhanced Trading Opportunities Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0c1426 0%, #1a202c 100%);
            color: #ffffff;
            line-height: 1.6;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 40px;
            padding: 30px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .header h1 {{
            font-size: 3rem;
            background: linear-gradient(45deg, #4f9cf9, #00d4ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }}
        
        .timestamp {{
            color: #a0aec0;
            font-size: 1.1rem;
        }}
        
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            margin-bottom: 40px;
        }}
        
        .card {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            padding: 25px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}
        
        .card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 20px 40px rgba(79, 156, 249, 0.1);
        }}
        
        .card h3 {{
            color: #4f9cf9;
            margin-bottom: 15px;
            font-size: 1.3rem;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .stat {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 10px 0;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .stat:last-child {{
            border-bottom: none;
        }}
        
        .stat-value {{
            font-weight: bold;
            color: #00d4ff;
        }}
        
        .opportunities-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 15px;
            overflow: hidden;
        }}
        
        .opportunities-table th,
        .opportunities-table td {{
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .opportunities-table th {{
            background: rgba(79, 156, 249, 0.2);
            font-weight: 600;
            color: #4f9cf9;
        }}
        
        .opportunities-table tr:hover {{
            background: rgba(255, 255, 255, 0.05);
        }}
        
        .urgency-crítica {{
            background: linear-gradient(45deg, #ff4757, #ff6b7a);
            color: white;
            padding: 4px 8px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: bold;
        }}
        
        .urgency-alta {{
            background: linear-gradient(45deg, #ffa726, #ffcc02);
            color: white;
            padding: 4px 8px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: bold;
        }}
        
        .urgency-media {{
            background: linear-gradient(45deg, #26c6da, #00acc1);
            color: white;
            padding: 4px 8px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: bold;
        }}
        
        .section {{
            margin: 40px 0;
        }}
        
        .section h2 {{
            color: #4f9cf9;
            margin-bottom: 20px;
            font-size: 2rem;
            border-bottom: 2px solid #4f9cf9;
            padding-bottom: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 Enhanced Trading Opportunities Dashboard</h1>
            <div class="timestamp">📅 Generado: {timestamp}</div>
        </div>"""
        
        # Resumen ejecutivo mejorado
        market_overview = enhanced_analysis.get('market_overview', {})
        correlation_analysis = enhanced_analysis.get('correlation_analysis', {})
        
        if market_overview:
            html_content += f"""
        <div class="section">
            <h2>🎯 Resumen Ejecutivo Mejorado</h2>
            <div class="grid">
                <div class="card">
                    <h3>📊 Estado del Mercado</h3>
                    <div class="stat">
                        <span>Estado General:</span>
                        <span class="stat-value">{market_overview.get('market_state', 'N/A')}</span>
                    </div>
                    <div class="stat">
                        <span>Sentimiento:</span>
                        <span class="stat-value">{market_overview.get('market_sentiment', 'N/A')}</span>
                    </div>
                    <div class="stat">
                        <span>Cobertura Mapeo:</span>
                        <span class="stat-value">{market_overview.get('mapping_coverage_percentage', 0):.1f}%</span>
                    </div>
                    <div style="margin-top: 15px; padding: 10px; background: rgba(79, 156, 249, 0.1); border-radius: 8px;">
                        {market_overview.get('description', 'No disponible')}
                    </div>
                </div>
                
                <div class="card">
                    <h3>📈 Estadísticas Mejoradas</h3>
                    <div class="stat">
                        <span>Total Oportunidades:</span>
                        <span class="stat-value">{summary.get('total_opportunities', 0)}</span>
                    </div>
                    <div class="stat">
                        <span>Críticas:</span>
                        <span class="stat-value">{summary.get('critical_count', 0)}</span>
                    </div>
                    <div class="stat">
                        <span>Con Insider Activity:</span>
                        <span class="stat-value">{summary.get('with_insider_activity', 0)}</span>
                    </div>
                    <div class="stat">
                        <span>Efectividad Correlación:</span>
                        <span class="stat-value">{summary.get('correlation_effectiveness', 0):.1f}%</span>
                    </div>
                    <div class="stat">
                        <span>Score Promedio:</span>
                        <span class="stat-value">{summary.get('average_score', 0)}/100</span>
                    </div>
                </div>
            </div>
        </div>"""
        
        # Top opportunities mejoradas con información de insider
        top_opportunities = enhanced_analysis.get('top_opportunities_analysis', [])
        if top_opportunities:
            html_content += f"""
        <div class="section">
            <h2>🏆 Top Oportunidades Mejoradas</h2>"""
            
            for i, opp in enumerate(top_opportunities[:5]):
                urgency_class = f"urgency-{opp['urgency'].lower()}"
                insider_info = f" | 🏢 {opp['insider_companies']} empresas" if opp.get('insider_companies', 0) > 0 else ""
                
                html_content += f"""
            <div class="card">
                <h3>#{i+1} {opp['sector']} ({opp['ticker']})</h3>
                <div class="grid" style="grid-template-columns: 1fr 1fr;">
                    <div>
                        <div class="stat">
                            <span>Score Final:</span>
                            <span class="stat-value">{opp['final_score']}/100</span>
                        </div>
                        <div class="stat">
                            <span>Precio Actual:</span>
                            <span class="stat-value">${opp['current_price']:.2f}</span>
                        </div>
                        <div class="stat">
                            <span>Dist. del Mínimo:</span>
                            <span class="stat-value">{opp['distance_from_min']}%</span>
                        </div>
                    </div>
                    <div>
                        <div class="stat">
                            <span>Upside Potencial:</span>
                            <span class="stat-value" style="color: #4caf50;">+{opp['upside_to_max_52w']:.1f}%</span>
                        </div>
                        <div class="stat">
                            <span>Urgencia:</span>
                            <span class="{urgency_class}">{opp['urgency']}</span>
                        </div>
                        <div class="stat">
                            <span>Insider Activity:</span>
                            <span class="stat-value">{'✅ Sí' if opp['insider_activity'] else '❌ No'}{insider_info}</span>
                        </div>
                    </div>
                </div>
                <div style="margin-top: 15px; padding: 15px; background: rgba(79, 156, 249, 0.1); border-radius: 8px;">
                    <strong>{opp['recommendation']}</strong><br>
                    {opp['description']}
                </div>
            </div>"""
            
            html_content += "</div>"
        
        # Tabla mejorada de oportunidades
        if opportunities:
            html_content += f"""
        <div class="section">
            <h2>📋 Todas las Oportunidades (Mejoradas)</h2>
            <div style="overflow-x: auto;">
                <table class="opportunities-table">
                    <thead>
                        <tr>
                            <th>Sector</th>
                            <th>Score</th>
                            <th>Precio</th>
                            <th>Dist. Min %</th>
                            <th>RSI</th>
                            <th>Urgencia</th>
                            <th>Insider</th>
                            <th>Empresas</th>
                        </tr>
                    </thead>
                    <tbody>"""
            
            for opp in opportunities[:20]:
                urgency_class = f"urgency-{opp.get('Urgency', '').lower()}"
                insider_icon = "✅" if opp.get('InsiderActivity', False) else "❌"
                insider_companies = len(opp.get('InsiderTickers', [])) if opp.get('InsiderActivity', False) else 0
                
                html_content += f"""
                        <tr>
                            <td><strong>{opp.get('Sector', 'N/A')}</strong></td>
                            <td><strong>{opp.get('FinalScore', 0)}</strong></td>
                            <td>${opp.get('CurrentPrice', 0):.2f}</td>
                            <td>{opp.get('DistanceFromMin', 0):.1f}%</td>
                            <td>{opp.get('RSI', 0):.1f}</td>
                            <td><span class="{urgency_class}">{opp.get('Urgency', 'N/A')}</span></td>
                            <td>{insider_icon}</td>
                            <td>{insider_companies}</td>
                        </tr>"""
            
            html_content += """
                    </tbody>
                </table>
            </div>
        </div>"""
        
        # Footer mejorado
        html_content += f"""
        <div class="section">
            <div class="card" style="text-align: center;">
                <h3>🎯 Enhanced Trading Opportunities System</h3>
                <p>Análisis con mapeo robusto de {len(self.comprehensive_ticker_mapping)} tickers a sectores</p>
                <p>Timestamp: {timestamp}</p>
                <p style="color: #a0aec0; font-size: 0.9rem;">
                    ⚠️ Este análisis es solo para fines informativos. No constituye asesoramiento financiero.
                </p>
            </div>
        </div>
        
    </div>
</body>
</html>"""
        
        return html_content
    
    def save_enhanced_analysis(self, analysis_results: Dict, base_filename: str = "enhanced_trading_analysis") -> Tuple[str, str]:
        """Guardar análisis mejorado en CSV y HTML"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Guardar CSV
        csv_filename = f"reports/{base_filename}_{timestamp}.csv"
        if 'opportunities' in analysis_results:
            df = pd.DataFrame(analysis_results['opportunities'])
            os.makedirs('reports', exist_ok=True)
            df.to_csv(csv_filename, index=False)
        
        # Guardar HTML
        html_filename = f"reports/{base_filename}_{timestamp}.html"
        html_content = self.generate_enhanced_html_report(analysis_results)
        with open(html_filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Guardar JSON completo
        json_filename = f"reports/{base_filename}_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(analysis_results, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"✅ Análisis mejorado guardado:")
        print(f"   📄 CSV: {csv_filename}")
        print(f"   🌐 HTML: {html_filename}")
        print(f"   📋 JSON: {json_filename}")
        
        return html_filename, csv_filename
    
    def run_enhanced_analysis(self, recent_days: int = 14) -> Dict:
        """Ejecutar análisis completo mejorado"""
        print("🚀 INICIANDO ANÁLISIS MEJORADO DE OPORTUNIDADES CON CORRELACIONES")
        print("=" * 70)
        
        try:
            # Realizar análisis
            analysis_results = self.analyze_enhanced_opportunities(recent_days)
            
            if 'error' in analysis_results:
                print(f"❌ Error en análisis: {analysis_results['error']}")
                return analysis_results
            
            # Mostrar resumen en consola
            summary = analysis_results.get('summary', {})
            enhanced_analysis = analysis_results.get('enhanced_analysis', {})
            mapping_stats = analysis_results.get('mapping_statistics', {})
            
            print(f"\n📊 RESUMEN DEL ANÁLISIS MEJORADO:")
            print(f"   🎯 Total oportunidades: {summary.get('total_opportunities', 0)}")
            print(f"   🚨 Oportunidades críticas: {summary.get('critical_count', 0)}")
            print(f"   ⚠️ Alta urgencia: {summary.get('high_urgency_count', 0)}")
            print(f"   👥 Con actividad insider: {summary.get('with_insider_activity', 0)}")
            print(f"   🎯 Mapeo ticker-sector: {summary.get('mapping_coverage', 0):.1f}%")
            print(f"   📈 Efectividad correlación: {summary.get('correlation_effectiveness', 0):.1f}%")
            print(f"   ⭐ Score promedio: {summary.get('average_score', 0)}/100")
            
            # Mostrar estado del mercado
            market_overview = enhanced_analysis.get('market_overview', {})
            if market_overview:
                print(f"\n🎯 ESTADO DEL MERCADO: {market_overview.get('market_state', 'N/A')}")
                print(f"   📈 Sentimiento: {market_overview.get('market_sentiment', 'N/A')}")
                print(f"   📝 {market_overview.get('description', 'No disponible')}")
            
            # Guardar archivos
            html_path, csv_path = self.save_enhanced_analysis(analysis_results)
            analysis_results['html_path'] = html_path
            analysis_results['csv_path'] = csv_path
            
            print(f"\n✅ ANÁLISIS MEJORADO COMPLETADO EXITOSAMENTE")
            return analysis_results
            
        except Exception as e:
            print(f"❌ Error en análisis mejorado: {e}")
            traceback.print_exc()
            return {'error': str(e)}

# =============================================
# FIN DE ENHANCED TRADING OPPORTUNITY ANALYZER
# =============================================

class DJMasterAnalyzer:
    """
    Analizador de sectores Dow Jones - VERSIÓN COMPLETA CON 140 SECTORES
    """
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'es-ES,es;q=0.9,en-GB;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Origin': 'https://www.investing.com',
            'Referer': 'https://www.investing.com/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors', 
            'Sec-Fetch-Site': 'same-site',
            'Sec-Ch-Ua': '"Google Chrome";v="137", "Chromium";v="137", "Not(A)Brand";v="24"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"macOS"',
            'Domain-Id': 'www',
            'Dnt': '1',
        })
        self.api_base = "https://de.api.investing.com/api/financialdata/historical"        # TODOS LOS 140 IDs DE SECTORES DOW JONES VÁLIDOS
        self.ALL_INVESTING_IDS = {
            'DJUSFR': '19965','DJUSAE': '19977', 'DJUSAF': '20029', 'DJUSAG': '20008', 'DJUSAI': '20037',
            'DJUSAL': '20006', 'DJUSAM': '20067', 'DJUSAP': '19962', 'DJUSAR': '20005',
            'DJUSAS': '20004', 'DJUSAT': '20009', 'DJUSAU': '20010', 'DJUSAV': '20066',
            'DJUSBC': '20013', 'DJUSBD': '20015', 'DJUSBE': '20017', 'DJUSBK': '19963',
            'DJUSBS': '19964', 'DJUSBT': '20011', 'DJUSBV': '19978', 'DJUSCA': '20047',
            'DJUSCC': '20021', 'DJUSCH': '20003', 'DJUSCM': '20077', 'DJUSCN': '19966',
            'DJUSCP': '20026', 'DJUSCR': '20022', 'DJUSCS': '20095', 'DJUSCT': '20100',
            'DJUSCX': '20096', 'DJUSDB': '20012', 'DJUSDN': '20028', 'DJUSDR': '19980',
            'DJUSDS': '20058', 'DJUSDT': '20032', 'DJUSDV': '20023', 'DJUSEC': '20035',
            'DJUSEE': '19979', 'DJUSEH': '20084', 'DJUSEN': '19972', 'DJUSES': '20085',
            'DJUSEU': '20036', 'DJUSFA': '20040', 'DJUSFB': '19968', 'DJUSFC': '20041',
            'DJUSFD': '20043', 'DJUSFE': '20056', 'DJUSFH': '20046', 'DJUSFI': '19967',
            'DJUSFO': '19981', 'DJUSFP': '20042', 'DJUSFT': '20044', 'DJUSGF': '40825',
            'DJUSGI': '19984', 'DJUSGT': '19985', 'DJUSGU': '20048', 'DJUSHB': '20052',
            'DJUSHC': '19958', 'DJUSHD': '20034', 'DJUSHG': '19987', 'DJUSHI': '20053',
            'DJUSHL': '20055', 'DJUSHN': '20073', 'DJUSHP': '20050', 'DJUSHR': '20020',
            'DJUSHV': '20051', 'DJUSIB': '20059', 'DJUSID': '20031', 'DJUSIG': '19969',
            'DJUSIL': '20064', 'DJUSIM': '19989', 'DJUSIO': '20057', 'DJUSIP': '20081',
            'DJUSIQ': '19988', 'DJUSIR': '19970', 'DJUSIS': '20001', 'DJUSIT': '19990',
            'DJUSIU': '20088', 'DJUSIV': '20016', 'DJUSIX': '19993', 'DJUSLE': '19991',
            'DJUSLG': '20054', 'DJUSMC': '19986', 'DJUSME': '19971', 'DJUSMF': '20070',
            'DJUSMG': '19992', 'DJUSMR': '20071', 'DJUSMS': '20068', 'DJUSMT': '20065',
            'DJUSMU': '20072', 'DJUSNF': '20074', 'DJUSNG': '19973', 'DJUSNS': '20061',
            'DJUSOG': '19994', 'DJUSOI': '20075', 'DJUSOL': '20060', 'DJUSOS': '20039',
            'DJUSPB': '20082', 'DJUSPC': '20107', 'DJUSPG': '19996', 'DJUSPL': '20079',
            'DJUSPM': '20049', 'DJUSPN': '19997', 'DJUSPR': '20078', 'DJUSRA': '20007',
            'DJUSRB': '20014', 'DJUSRD': '20033', 'DJUSRE': '19974', 'DJUSRH': '19998',
            'DJUSRI': '19999', 'DJUSRL': '20091', 'DJUSRN': '20089', 'DJUSRP': '20086',
            'DJUSRQ': '20087', 'DJUSRR': '20083', 'DJUSRS': '20099', 'DJUSRT': '19975',
            'DJUSRU': '20090', 'DJUSSB': '20062', 'DJUSSC': '20092', 'DJUSSD': '20093',
            'DJUSSF': '20025', 'DJUSSP': '20097', 'DJUSSR': '20098', 'DJUSST': '20063',
            'DJUSSV': '20000', 'DJUSSW': '20094', 'DJUSTB': '20102', 'DJUSTC': '19976',
            'DJUSTK': '20106', 'DJUSTL': '19960', 'DJUSTQ': '20002', 'DJUSTR': '20002',
            'DJUSTS': '20104', 'DJUSTT': '20105', 'DJUSTY': '20103', 'DJUSUT': '19961',
            'DJUSVE': '20027', 'DJUSVN': '20030', 'DJUSWC': '20069', 'DJUSWU': '20108'
        }
        
        # Nombres descriptivos para los sectores
        self.SECTOR_NAMES = {
            # Aerospace & Defense
            'DJUSAE': 'Dow Jones U.S. Aerospace & Defense Index',
            'DJUSAS': 'Dow Jones U.S. Aerospace Index',
            'DJUSDN': 'Dow Jones U.S. Defense Index',
            
            # Airlines
            'DJUSAR': 'Dow Jones U.S. Airlines Index',
            
            # Aluminum & Metals
            'DJUSAL': 'Dow Jones U.S. Aluminum Index',
            'DJUSNF': 'Dow Jones U.S. Nonferrous Metals Index',
            'DJUSST': 'Dow Jones U.S. Iron & Steel Index',
            'DJUSPM': 'Dow Jones U.S. Gold Mining Index',
            'DJUSPT': 'Dow Jones U.S. Platinum & Precious Metals Index',
            
            # Asset Management & Banks
            'DJUSAG': 'Dow Jones U.S. Asset Managers Index',
            'DJUSBK': 'Dow Jones U.S. Banks Index',
            
            # Automobiles & Parts
            'DJUSAP': 'Dow Jones U.S. Automobiles & Parts Index',
            'DJUSAU': 'Dow Jones U.S. Automobiles Index',
            'DJUSAT': 'Dow Jones U.S. Auto Parts Index',
            'DJUSTR': 'Dow Jones U.S. Tires Index',
            
            # Basic Resources & Materials
            'DJUSBS': 'Dow Jones U.S. Basic Resources Index',
            'DJUSIM': 'Dow Jones U.S. Industrial Metals & Mining Index',
            'DJUSMG': 'Dow Jones U.S. Mining Index',
            'DJUSMD': 'Dow Jones U.S. General Mining Index',
            
            # Beverages & Food
            'DJUSBV': 'Dow Jones U.S. Beverages Index',
            'DJUSDB': 'Dow Jones U.S. Brewers Index',
            'DJUSVN': 'Dow Jones U.S. Distillers & Vintners Index',
            'DJUSSD': 'Dow Jones U.S. Soft Drinks Index',
            'DJUSFB': 'Dow Jones U.S. Food & Beverage Index',
            'DJUSFO': 'Dow Jones U.S. Food Producers Index',
            'DJUSFP': 'Dow Jones U.S. Food Products Index',
            'DJUSFD': 'Dow Jones U.S. Food Retailers & Wholesalers Index',
            
            # Biotechnology & Pharmaceuticals
            'DJUSBT': 'Dow Jones U.S. Biotechnology Index',
            'DJUSPN': 'Dow Jones U.S. Pharmaceuticals & Biotechnology Index',
            'DJUSPR': 'Dow Jones U.S. Pharmaceuticals Index',
            
            # Broadcasting & Media
            'DJUSBC': 'Dow Jones U.S. Broadcasting & Entertainment Index',
            'DJUSAV': 'Dow Jones U.S. Media Agencies Index',
            'DJUSME': 'Dow Jones U.S. Media Index',
            'DJUSPB': 'Dow Jones U.S. Publishing Index',
            
            # Building & Construction
            'DJUSBD': 'Dow Jones U.S. Building Materials & Fixtures Index',
            'DJUSCN': 'Dow Jones U.S. Construction & Materials Index',
            'DJUSHV': 'Dow Jones U.S. Heavy Construction Index',
            'DJUSHB': 'Dow Jones U.S. Home Construction Index',
            
            # Business Services
            'DJUSBE': 'Dow Jones U.S. Business Training & Employment Agencies Index',
            'DJUSIV': 'Dow Jones U.S. Business Support Services Index',
            'DJUSFA': 'Dow Jones U.S. Financial Administration Index',
            'DJUSIS': 'Dow Jones U.S. Support Services Index',
            
            # Chemicals
            'DJUSCH': 'Dow Jones U.S. Chemicals Index',
            'DJUSCC': 'Dow Jones U.S. Commodity Chemicals Index',
            'DJUSCX': 'Dow Jones U.S. Specialty Chemicals Index',
            
            # Consumer Electronics & Goods
            'DJUSCE': 'Dow Jones U.S. Consumer Electronics Index',
            'DJUSNG': 'Dow Jones U.S. Personal & Household Goods Index',
            'DJUSHG': 'Dow Jones U.S. Household Goods & Home Construction Index',
            'DJUSHD': 'Dow Jones U.S. Durable Household Products Index',
            'DJUSHN': 'Dow Jones U.S. Nondurable Household Products Index',
            'DJUSFH': 'Dow Jones U.S. Furnishings Index',
            'DJUSCM': 'Dow Jones U.S. Personal Products Index',
            'DJUSCF': 'Dow Jones U.S. Clothing & Accessories Index',
            'DJUSFT': 'Dow Jones U.S. Footwear Index',
            
            # Delivery & Transportation
            'DJUSAF': 'Dow Jones U.S. Delivery Services Index',
            'DJUSIT': 'Dow Jones U.S. Industrial Transportation Index',
            'DJUSMT': 'Dow Jones U.S. Marine Transportation Index',
            'DJUSRR': 'Dow Jones U.S. Railroads Index',
            'DJUSTS': 'Dow Jones U.S. Transportation Services Index',
            'DJUSTK': 'Dow Jones U.S. Trucking Index',
            
            # Electronics & Equipment
            'DJUSAI': 'Dow Jones U.S. Electronic Equipment Index',
            'DJUSEC': 'Dow Jones U.S. Electrical Components & Equipment Index',
            'DJUSEE': 'Dow Jones U.S. Electronic & Electrical Equipment Index',
            'DJUSOE': 'Dow Jones U.S. Electronic Office Equipment Index',
            
            # Energy & Oil
            'DJUSEN': 'Dow Jones U.S. Oil & Gas Index',
            'DJUSOG': 'Dow Jones U.S. Oil & Gas Producers',
            'DJUSOS': 'Dow Jones U.S. Exploration & Production Index',
            'DJUSOL': 'Dow Jones U.S. Integrated Oil & Gas Index',
            'DJUSOI': 'Dow Jones U.S. Oil Equipment & Services Index',
            'DJUSPL': 'Dow Jones U.S. Pipelines Index',
            
            # Financial Services
            'DJUSFI': 'Dow Jones U.S. Financial Services Index',
            'DJUSGF': 'Dow Jones U.S. Financial Services Index',
            'DJUSSF': 'Dow Jones U.S. Consumer Finance Index',
            'DJUSSP': 'Dow Jones U.S. Specialty Finance Index',
            'DJUSSB': 'Dow Jones U.S. Investment Services Index',
            'DJUSMF': 'Dow Jones U.S. Mortgage Finance Index',
            
            # Gambling & Leisure
            'DJUSCA': 'Dow Jones U.S. Gambling Index',
            'DJUSCG': 'Dow Jones U.S. Travel & Leisure Index',
            'DJUSLE': 'Dow Jones U.S. Leisure Goods Index',
            'DJUSRP': 'Dow Jones U.S. Recreational Products Index',
            'DJUSRQ': 'Dow Jones U.S. Recreational Services Index',
            'DJUSTY': 'Dow Jones U.S. Toys Index',
            'DJUSLG': 'Dow Jones U.S. Hotels Index',
            'DJUSRU': 'Dow Jones U.S. Restaurants & Bars Index',
            'DJUSTT': 'Dow Jones U.S. Travel & Tourism Index',
            
            # Healthcare
            'DJUSHC': 'Dow Jones U.S. Health Care Index',
            'DJUSMC': 'Dow Jones U.S. Health Care Equipment & Services Index',
            'DJUSHP': 'Dow Jones U.S. Health Care Providers Index',
            'DJUSAM': 'Dow Jones U.S. Medical Equipment Index',
            'DJUSMS': 'Dow Jones U.S. Medical Supplies Index',
            
            # Industrial & Equipment
            'DJUSIG': 'Dow Jones U.S. Industrial Goods & Services Index',
            'DJUSGI': 'Dow Jones U.S. General Industrials Index',
            'DJUSCP': 'Dow Jones U.S. Containers & Packaging Index',
            'DJUSID': 'Dow Jones U.S. Diversified Industrials Index',
            'DJUSIQ': 'Dow Jones U.S. Industrial Engineering Index',
            'DJUSHR': 'Dow Jones U.S. Commercial Vehicles & Trucks Index',
            'DJUSFE': 'Dow Jones U.S. Industrial Machinery Index',
            'DJUSDS': 'Dow Jones U.S. Industrial Suppliers Index',
            'DJUSPC': 'Dow Jones U.S. Waste & Disposal Services Index',
            
            # Insurance
            'DJUSIR': 'Dow Jones U.S. Insurance Index',
            'DJUSIX': 'Dow Jones U.S. Nonlife Insurance Index',
            'DJUSIF': 'Dow Jones U.S. Full Line Insurance Index',
            'DJUSIB': 'Dow Jones U.S. Insurance Brokers Index',
            'DJUSIP': 'Dow Jones U.S. Property & Casualty Insurance Index',
            'DJUSIU': 'Dow Jones U.S. Reinsurance Index',
            'DJUSIL': 'Dow Jones U.S. Life Insurance Index',
            
            # Real Estate & REITs
            'DJUSRE': 'Dow Jones U.S. Real Estate Index',
            'DJUSRH': 'Dow Jones U.S. Real Estate Investment & Services',
            'DJUSEH': 'Dow Jones U.S. Real Estate Holding & Development Index',
            'DJUSES': 'Dow Jones U.S. Real Estate Services Index',
            'DJUSRI': 'Dow Jones U.S. Real Estate Investment Trusts Index',
            'DJUSIO': 'Dow Jones U.S. Industrial & Office REITs Index',
            'DJUSRL': 'Dow Jones U.S. Retail REITs Index',
            'DJUSRN': 'Dow Jones U.S. Residential REITs Index',
            'DJUSDT': 'Dow Jones U.S. Diversified REITs Index',
            'DJUSSR': 'Dow Jones U.S. Specialty REITs Index',
            'DJUSMR': 'Dow Jones U.S. Mortgage REITs Index',
            'DJUSHL': 'Dow Jones U.S. Hotel & Lodging REITs Index',
            
            # Retail
            'DJUSRT': 'Dow Jones U.S. Retail Index',
            'DJUSDR': 'Dow Jones U.S. Food & Drug Retailers Index',
            'DJUSRD': 'Dow Jones U.S. Drug Retailers Index',
            'DJUSGT': 'Dow Jones U.S. General Retailers Index',
            'DJUSRA': 'Dow Jones U.S. Apparel Retailers Index',
            'DJUSRB': 'Dow Jones U.S. Broadline Retailers Index',
            'DJUSHI': 'Dow Jones U.S. Home Improvement Retailers Index',
            'DJUSCS': 'Dow Jones U.S. Specialized Consumer Services Index',
            'DJUSRS': 'Dow Jones U.S. Specialty Retailers Index',
            
            # Technology & Software
            'DJUSTC': 'Dow Jones U.S. Technology Index',
            'DJUSSV': 'Dow Jones U.S. Software & Computer Services Index',
            'DJUSDV': 'Dow Jones U.S. Computer Services Index',
            'DJUSNS': 'Dow Jones U.S. Internet Index',
            'DJUSSW': 'Dow Jones U.S. Software Index',
            'DJUSTQ': 'Dow Jones U.S. Technology Hardware & Equipment Index',
            'DJUSCR': 'Dow Jones U.S. Computer Hardware Index',
            'DJUSSC': 'Dow Jones U.S. Semiconductors Index',
            'DJUSCT': 'Dow Jones U.S. Telecommunications Equipment Index',
            
            # Telecommunications
            'DJUSTL': 'Dow Jones U.S. Telecommunications Index',
            'DJUSFC': 'Dow Jones U.S. Fixed Line Telecommunications Index',
            'DJUSWC': 'Dow Jones U.S. Mobile Telecommunications Index',
            
            # Tobacco
            'DJUSTB': 'Dow Jones U.S. Tobacco Index',
            
            # Utilities
            'DJUSUT': 'Dow Jones U.S. Utilities Index',
            'DJUSEU': 'Dow Jones U.S. Electricity Index',
            'DJUSVE': 'Dow Jones U.S. Conventional Electricity Index',
            'DJUSUO': 'Dow Jones U.S. Gas, Water & Multiutilities Index',
            'DJUSGU': 'Dow Jones U.S. Gas Distribution Index',
            'DJUSMU': 'Dow Jones U.S. Multiutilities Index',
            'DJUSWU': 'Dow Jones U.S. Water Index',
            
            # Forestry & Paper
            'DJUSFR': 'Dow Jones U.S. Forestry & Paper Index',
            'DJUSFS': 'Dow Jones U.S. Forestry Index',
            'DJUSPP': 'Dow Jones U.S. Paper Index',
            
            # Coal
            'DJUSCL': 'Dow Jones U.S. Coal Index',
        }    
    def get_sector_name(self, ticker):
        """Obtiene el nombre del sector, generando uno automático si no existe"""
        if ticker in self.SECTOR_NAMES:
            return self.SECTOR_NAMES[ticker]
        else:
            # Generar nombre automático basado en el código
            code = ticker.replace('DJUS', '')
            
            # Mapeo de códigos comunes
            code_mapping = {
                'AE': 'Aerospace Equipment', 'AF': 'Agricultural Futures', 'AG': 'Agriculture',
                'AI': 'Artificial Intelligence', 'AM': 'Advanced Materials', 'AV': 'Aviation',
                'BC': 'Broadcasting', 'BD': 'Building', 'BE': 'Biotech Equipment',
                'BT': 'Biotechnology', 'CA': 'Capital Goods', 'CC': 'Consumer Credit',
                'CM': 'Commercial', 'CP': 'Consumer Products', 'CR': 'Consumer Recreation',
                'CS': 'Consumer Services', 'CT': 'Construction Technology', 'CX': 'Consumer Complex',
                'DB': 'Databases', 'DN': 'Defense', 'DS': 'Data Services',
                'DT': 'Digital Technology', 'DV': 'Development', 'EC': 'E-Commerce',
                'EH': 'Environmental Health', 'ES': 'Energy Services', 'EU': 'European Markets',
                'FA': 'Financial Analytics', 'FC': 'Financial Credit', 'FD': 'Food Distribution',
                'FE': 'Financial Engineering', 'FH': 'Financial Holdings', 'FI': 'Financial Instruments',
                'FP': 'Financial Products', 'FT': 'Financial Technology', 'GF': 'Green Finance',
                'GU': 'Gaming & Utilities', 'HB': 'Healthcare Biotech', 'HD': 'Healthcare Devices',
                'HI': 'Healthcare Innovation', 'HL': 'Healthcare Logistics', 'HN': 'Healthcare Networks',
                'HP': 'Healthcare Products', 'HR': 'Healthcare Research', 'HV': 'Healthcare Ventures',
                'IB': 'Investment Banking', 'ID': 'Industrial Design', 'IL': 'Industrial Logistics',
                'IO': 'Industrial Operations', 'IP': 'Intellectual Property', 'IR': 'Industrial Research',
                'IU': 'Industrial Utilities', 'IV': 'Industrial Ventures', 'LG': 'Logistics',
                'MF': 'Manufacturing', 'MR': 'Materials Research', 'MS': 'Materials Science',
                'MT': 'Materials Technology', 'MU': 'Materials Utilities', 'NF': 'New Finance',
                'NS': 'Network Services', 'OI': 'Oil Infrastructure', 'OL': 'Oil Logistics',
                'OS': 'Oil Services', 'PB': 'Publishing & Broadcasting', 'PC': 'Personal Computing',
                'PL': 'Plastics', 'PM': 'Precious Metals', 'PR': 'Public Relations',
                'RB': 'Renewable Bio', 'RD': 'Research & Development', 'RL': 'Real Estate Logistics',
                'RN': 'Renewable', 'RP': 'Real Estate Products', 'RQ': 'Real Estate Quality',
                'RR': 'Real Estate Research', 'RU': 'Real Estate Utilities', 'SB': 'Sustainable Business',
                'SC': 'Supply Chain', 'SD': 'Sustainable Development', 'SF': 'Sustainable Finance',
                'SP': 'Specialty Products', 'SR': 'Sustainable Resources', 'ST': 'Space Technology',
                'SW': 'Software', 'TB': 'Technology Business', 'TK': 'Technology Kits',
                'TR': 'Transportation', 'TS': 'Technology Services', 'TT': 'Technology Tools',
                'TY': 'Technology Systems', 'VE': 'Ventures', 'VN': 'Venture Networks',
                'WC': 'Wireless Communications', 'WU': 'Wireless Utilities'
            }
            
            if code in code_mapping:
                return code_mapping[code]
            else:
                return f"Sector {code}"
    
    def get_historical_data(self, ticker, days_back=365):
        """Obtiene datos históricos para un ticker"""
        try:
            index_id = self.ALL_INVESTING_IDS.get(ticker)
            if not index_id:
                return False, None
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")
            
            url = f"{self.api_base}/{index_id}"
            params = {
                'start-date': start_date_str,
                'end-date': end_date_str,
                'time-frame': 'Daily',
                'add-missing-rows': 'false'
            }
            
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'data' in data and len(data['data']) > 0:
                    historical_data = data['data']
                    
                    # Convertir a DataFrame con limpieza de números
                    df_data = []
                    for item in historical_data:
                        def clean_number(value):
                            if isinstance(value, str):
                                cleaned = value.replace(',', '')
                                try:
                                    return float(cleaned)
                                except (ValueError, TypeError):
                                    return 0.0
                            return float(value) if value else 0.0
                        
                        df_data.append({
                            'Date': item.get('rowDate'),
                            'Close': clean_number(item.get('last_close', 0)),
                            'Open': clean_number(item.get('last_open', 0)),
                            'High': clean_number(item.get('last_max', 0)),
                            'Low': clean_number(item.get('last_min', 0)),
                            'Volume': int(clean_number(item.get('volumeRaw', 0)))
                        })
                    
                    df = pd.DataFrame(df_data)
                    df['Date'] = pd.to_datetime(df['Date'])
                    df = df.sort_values('Date', ascending=False)
                    
                    return True, df
                    
            return False, None
            
        except Exception as e:
            print(f"❌ Error obteniendo {ticker}: {str(e)}")
            return False, None
    
    def calculate_rsi(self, prices, period=14):
        """Calcula RSI"""
        if len(prices) < period + 1:
            return None
            
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def analyze_sector(self, ticker, df):
        """Análisis completo de un sector"""
        if df is None or len(df) < 50:
            return None
        
        current_price = df['Close'].iloc[0]
        min_52w = df['Low'].min()
        max_52w = df['High'].max()
        
        distance_from_min = ((current_price - min_52w) / min_52w) * 100
        rsi = self.calculate_rsi(df['Close'].values)
        
        # Clasificación por estado
        if distance_from_min < 10:
            estado = "🟢"
            classification = "OPORTUNIDAD"
        elif distance_from_min < 25:
            estado = "🟡"
            classification = "CERCA"
        else:
            estado = "🔴"
            classification = "FUERTE"
        
        return {
            'ticker': ticker,
            'sector': self.get_sector_name(ticker),
            'current_price': current_price,
            'min_52w': min_52w,
            'max_52w': max_52w,
            'distance_pct': distance_from_min,
            'rsi': rsi,
            'estado': estado,
            'classification': classification,
            'data_points': len(df)
        }
    
    def batch_analysis(self, tickers, batch_size=5):
        """Análisis por lotes para evitar saturar la API"""
        results = []
        total = len(tickers)
        
        print(f"🚀 INICIANDO ANÁLISIS COMPLETO DE {total} SECTORES DOW JONES")

        
        print("=" * 70)

        
        if total > 50:

        
            print("⚠️  ANÁLISIS EXTENDIDO: Esto puede tomar 15-20 minutos")
        print("=" * 60)
        
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total + batch_size - 1) // batch_size
            
            print(f"\n📦 LOTE {batch_num}/{total_batches}: {', '.join(batch)}")
            
            for ticker in batch:
                print(f"   🔄 Procesando {ticker}...", end=" ")
                
                success, df = self.get_historical_data(ticker)
                if success and df is not None:
                    result = self.analyze_sector(ticker, df)
                    if result:
                        results.append(result)
                        print(f"✅ {result['distance_pct']:.1f}% {result['estado']}")
                    else:
                        print("❌ Sin análisis")
                else:
                    print("❌ Sin datos")
                
                time.sleep(1)  # Pausa entre requests
            
            if i + batch_size < len(tickers):
                print(f"   ⏳ Pausa entre lotes...")
                time.sleep(3)  # Pausa entre lotes
        
        return results
    
    def generate_report(self, results):
        """Genera reporte completo en consola"""
        if not results:
            print("❌ No hay resultados para reportar")
            return
        
        print(f"\n{'='*80}")
        print("🎯 REPORTE SECTORIAL COMPLETO")
        print("=" * 80)
        
        # Tabla principal
        print(f"{'Sector':<20} {'Precio':<10} {'Min52w':<10} {'Dist%':<8} {'RSI':<6} {'Estado'}")
        print("-" * 70)
        
        for r in sorted(results, key=lambda x: x['distance_pct']):
            rsi_str = f"{r['rsi']:.1f}" if r['rsi'] else "N/A"
            print(f"{r['sector']:<20} {r['current_price']:<10.2f} {r['min_52w']:<10.2f} {r['distance_pct']:<8.1f} {rsi_str:<6} {r['estado']}")
        
        # Análisis por categorías
        oportunidades = [r for r in results if r['classification'] == 'OPORTUNIDAD']
        cerca = [r for r in results if r['classification'] == 'CERCA']
        fuertes = [r for r in results if r['classification'] == 'FUERTE']
        
        print(f"\n📊 RESUMEN POR CATEGORÍAS:")
        print(f"   🟢 OPORTUNIDADES (<10%): {len(oportunidades)} sectores")
        print(f"   🟡 CERCA (10-25%): {len(cerca)} sectores")
        print(f"   🔴 FUERTES SUBIDAS, PRECAUCIÓN (>25%): {len(fuertes)} sectores")
        
        if oportunidades:
            print(f"\n🎯 TOP OPORTUNIDADES:")
            for r in sorted(oportunidades, key=lambda x: x['distance_pct'])[:10]:
                rsi_info = f" | RSI: {r['rsi']:.1f}" if r['rsi'] else ""
                print(f"   • {r['sector']}: {r['distance_pct']:.1f}% del mínimo{rsi_info}")

class GitHubPagesUploader:
    """
    NUEVA CLASE: Uploader integrado para GitHub Pages
    """
    def __init__(self):
        self.repo_path = Path("docs")
        self.reports_path = self.repo_path / "reports"
        self.manifest_file = self.repo_path / "manifest.json"
        self.index_file = self.repo_path / "index.html"
        self.base_url = "https://tantancansado.github.io/stock_analyzer_a"
        
        # Inicializar templates si están disponibles
        try:
            from templates.github_pages_templates import GitHubPagesTemplates
            self.templates = GitHubPagesTemplates(self.base_url)
            self.templates_available = True
        except ImportError:
            self.templates = None
            self.templates_available = False
        
        self.setup_directories()
    
    def setup_directories(self):
        """Crea la estructura de directorios necesaria"""
        try:
            self.repo_path.mkdir(exist_ok=True)
            self.reports_path.mkdir(exist_ok=True)
            (self.reports_path / "daily").mkdir(exist_ok=True)
            (self.reports_path / "dj_sectorial").mkdir(exist_ok=True)
            (self.reports_path / "market_breadth").mkdir(exist_ok=True)
            (self.reports_path / "enhanced_opportunities").mkdir(exist_ok=True)  # NUEVO
            
            # Crear archivo .nojekyll
            nojekyll = self.repo_path / ".nojekyll"
            if not nojekyll.exists():
                nojekyll.touch()
        except Exception as e:
            print(f"❌ Error creando directorios: {e}")
    
    def load_manifest(self):
        """Carga el manifest de reportes"""
        if self.manifest_file.exists():
            try:
                with open(self.manifest_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        return {
            "total_reports": 0,
            "total_dj_reports": 0,
            "total_breadth_reports": 0,
            "total_enhanced_reports": 0,  # NUEVO
            "last_update": None,
            "reports": [],
            "dj_reports": [],
            "breadth_reports": [],
            "enhanced_reports": [],  # NUEVO
            "base_url": self.base_url
        }
    
    def save_manifest(self, manifest):
        """Guarda el manifest"""
        try:
            with open(self.manifest_file, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ Error guardando manifest: {e}")
            return False
    
    def upload_report(self, html_file, csv_file, title, description):
        """Sube un reporte a GitHub Pages"""
        try:
            # Determinar tipo de reporte PRIMERO
            if "DJ Sectorial" in title or "sectorial" in title.lower():
                report_type = "dj_sectorial"
            elif "Market Breadth" in title or "breadth" in title.lower():
                report_type = "market_breadth"
            elif "Enhanced" in title or "enhanced" in title.lower() or "opportunities" in title.lower():
                report_type = "enhanced_opportunities"  # NUEVO
            else:
                report_type = "insider"
            
            # Verificar archivos
            if not os.path.exists(html_file) or not os.path.exists(csv_file):
                print(f"❌ Archivos no encontrados: {html_file}, {csv_file}")
                return None
            
            timestamp = datetime.now()
            date_only = timestamp.strftime('%Y-%m-%d')
            
            # Crear ID y carpeta
            if report_type == "dj_sectorial":
                report_id = "dj_sectorial"
                report_dir = self.reports_path / "dj_sectorial"
            elif report_type == "market_breadth":
                report_id = "market_breadth"
                report_dir = self.reports_path / "market_breadth"
            elif report_type == "enhanced_opportunities":
                report_id = f"enhanced_opportunities_{date_only}"
                report_dir = self.reports_path / "enhanced_opportunities" / report_id
            else:
                report_id = f"report_{date_only}"
                report_dir = self.reports_path / "daily" / report_id
            
            report_dir.mkdir(exist_ok=True, parents=True)
            
            # Copiar archivos
            shutil.copy2(html_file, report_dir / "index.html")
            shutil.copy2(csv_file, report_dir / "data.csv")
            
            # Actualizar manifest
            manifest = self.load_manifest()
            
            # Crear entrada del reporte
            if report_type == "dj_sectorial":
                base_path = "reports/dj_sectorial"
            elif report_type == "market_breadth":
                base_path = "reports/market_breadth"
            elif report_type == "enhanced_opportunities":
                base_path = f"reports/enhanced_opportunities/{report_id}"
            else:
                base_path = f"reports/daily/{report_id}"
            
            report_entry = {
                "id": report_id,
                "title": title,
                "description": description,
                "timestamp": timestamp.isoformat(),
                "date": timestamp.strftime('%Y-%m-%d'),
                "time": timestamp.strftime('%H:%M:%S'),
                "html_url": f"{base_path}/index.html",
                "csv_url": f"{base_path}/data.csv",
                "full_url": f"{self.base_url}/{base_path}/index.html",
                "type": report_type
            }
            
            # Actualizar lista de reportes
            if report_type == "dj_sectorial":
                if 'dj_reports' not in manifest:
                    manifest['dj_reports'] = []
                manifest["dj_reports"].insert(0, report_entry)
                manifest["total_dj_reports"] = len(manifest["dj_reports"])
            elif report_type == "market_breadth":
                if 'breadth_reports' not in manifest:
                    manifest['breadth_reports'] = []
                manifest["breadth_reports"].insert(0, report_entry)
                manifest["total_breadth_reports"] = len(manifest["breadth_reports"])
            elif report_type == "enhanced_opportunities":
                if 'enhanced_reports' not in manifest:
                    manifest['enhanced_reports'] = []
                manifest["enhanced_reports"].insert(0, report_entry)
                manifest["total_enhanced_reports"] = len(manifest["enhanced_reports"])
            else:
                manifest["reports"].insert(0, report_entry)
                manifest["total_reports"] = len(manifest["reports"])
            
            manifest["last_update"] = timestamp.isoformat()
            
            # Guardar manifest
            self.save_manifest(manifest)
            
            # Generar páginas
            self.generate_all_pages(manifest)
            
            # Git commit
            self.git_push(report_id)
            
            return {
                "success": True,
                "report_id": report_id,
                "github_url": f"{self.base_url}/{base_path}/index.html",
                "type": report_type
            }
            
        except Exception as e:
            print(f"❌ Error subiendo reporte: {e}")
            traceback.print_exc()
            return None
    
    def generate_all_pages(self, manifest):
        """Genera todas las páginas usando templates"""
        try:
            if self.templates_available:
                # Usar templates Liquid Glass - ARREGLADO
                html_content = self.templates.generate_main_dashboard_with_breadth(manifest)
                with open(self.index_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                # Generar página DJ Sectorial
                dj_content = self.templates.generate_dj_sectorial_page(manifest)
                with open(self.repo_path / "dj_sectorial.html", 'w', encoding='utf-8') as f:
                    f.write(dj_content)
                
                # Generar página Market Breadth
                breadth_content = self.templates.generate_breadth_page(manifest)
                with open(self.repo_path / "market_breadth.html", 'w', encoding='utf-8') as f:
                    f.write(breadth_content)
                
                # Generar página Enhanced Opportunities (NUEVO) - SOLO SI EXISTE LA FUNCIÓN
                if hasattr(self.templates, 'generate_enhanced_opportunities_page'):
                    enhanced_content = self.templates.generate_enhanced_opportunities_page(manifest)
                    with open(self.repo_path / "enhanced_opportunities.html", 'w', encoding='utf-8') as f:
                        f.write(enhanced_content)
                
                print("✅ Páginas generadas con diseño Liquid Glass")
            else:
                # Fallback básico
                self.generate_basic_pages(manifest)
                print("✅ Páginas generadas con diseño básico")
            
        except Exception as e:
            print(f"❌ Error generando páginas: {e}")
    
    def generate_basic_pages(self, manifest):
        """Fallback básico si no hay templates"""
        total_reports = manifest['total_reports']
        total_dj = manifest.get('total_dj_reports', 0)
        total_breadth = manifest.get('total_breadth_reports', 0)
        total_enhanced = manifest.get('total_enhanced_reports', 0)
        
        basic_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Trading Analytics</title>
<style>body{{background:#020617;color:white;font-family:Arial;padding:20px;}}
.card{{background:rgba(255,255,255,0.1);padding:20px;margin:20px 0;border-radius:12px;}}
.stat{{display:inline-block;margin:20px;text-align:center;}}
.stat-num{{font-size:2em;color:#4a90e2;}}</style></head>
<body><div class="card"><h1>📊 Trading Analytics System</h1></div>
<div class="card"><h2>📈 Estadísticas</h2>
<div class="stat"><div class="stat-num">{total_reports}</div><div>Reportes Insider</div></div>
<div class="stat"><div class="stat-num">{total_dj}</div><div>Análisis DJ</div></div>
<div class="stat"><div class="stat-num">{total_breadth}</div><div>Market Breadth</div></div>
<div class="stat"><div class="stat-num">{total_enhanced}</div><div>Enhanced Opportunities</div></div>
</div></body></html>"""
        
        with open(self.index_file, 'w', encoding='utf-8') as f:
            f.write(basic_html)
    
    def git_push(self, report_id):
        """Intenta hacer push automático a GitHub"""
        try:
            if not os.path.exists(".git"):
                return False
            
            subprocess.run(["git", "add", "docs/"], check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", f"📊 {report_id}"], check=True, capture_output=True)
            subprocess.run(["git", "push"], check=True, capture_output=True)
            return True
        except:
            return False

class InsiderTradingSystem:
    """Sistema principal que gestiona todo el flujo"""
    
    def __init__(self):
        self.csv_path = "reports/insiders_daily.csv"
        self.html_path = "reports/insiders_report_completo.html"
        self.bundle_path = "reports/insiders_report_bundle.zip"
        
        # Inicializar DJ Analyzer
        self.dj_analyzer = DJMasterAnalyzer()
        
        # Inicializar Enhanced Opportunities Analyzer (NUEVO)
        self.enhanced_analyzer = EnhancedTradingOpportunityAnalyzer()
        
        # Inicializar GitHub Pages Uploader
        self.github_uploader = GitHubPagesUploader()
        
        # Inicializar generador HTML
        if HTML_TEMPLATES_AVAILABLE:
            self.html_generator = HTMLGenerator()
        else:
            self.html_generator = None
        
        self.setup_directories()
    
    def setup_directories(self):
        """Crea los directorios necesarios"""
        os.makedirs("reports", exist_ok=True)
        os.makedirs("alerts", exist_ok=True)
        os.makedirs("templates", exist_ok=True)
        print("✅ Directorios verificados")
    
    def run_scraper(self):
        """Ejecuta el scraper de OpenInsider"""
        print("\n🕷️ EJECUTANDO SCRAPER")
        print("=" * 50)
        
        try:
            # Buscar el scraper
            scraper_paths = [
                "insiders/openinsider_scraper.py",
                "openinsider_scraper.py",
            ]
            
            scraper_found = None
            for path in scraper_paths:
                if os.path.exists(path):
                    scraper_found = path
                    break
            
            if not scraper_found:
                print("❌ Scraper no encontrado")
                return False
            
            print(f"✅ Ejecutando: {scraper_found}")

            if not scraper_found.endswith(".py"):
                print(f"❌ Formato de scraper no permitido: {scraper_found}")
                return False

            result = subprocess.run(
                [sys.executable, scraper_found],
                capture_output=True,
                text=True,
                timeout=180
            )

            if result.returncode != 0:
                print(f"❌ Error ejecutando scraper: {result.stderr}")
                return False
            
            if os.path.exists(self.csv_path):
                df = pd.read_csv(self.csv_path)
                print(f"✅ CSV generado: {len(df)} registros")
                return True
            else:
                print("❌ CSV no generado")
                return False
                
        except Exception as e:
            print(f"❌ Error en scraper: {e}")
            traceback.print_exc()
            return False
    
    def run_dj_sectorial_analysis(self, mode="principales"):
        """Ejecuta el análisis sectorial de Dow Jones"""
        print("\n📊 EJECUTANDO ANÁLISIS SECTORIAL DJ")
        print("=" * 50)
        
        try:
            if mode == "principales":
                tickers = list(self.dj_analyzer.ALL_INVESTING_IDS.keys())[:16]
                print(f"📊 Modo Principales: {len(tickers)} sectores")
            elif mode == "detallado":
                tickers = list(self.dj_analyzer.ALL_INVESTING_IDS.keys())[:35]
                print(f"🔍 Modo Detallado: {len(tickers)} sectores")
            elif mode == "completo":
                tickers = list(self.dj_analyzer.ALL_INVESTING_IDS.keys())
                print(f"🚀 Modo Completo: {len(tickers)} sectores")
            else:
                tickers = list(self.dj_analyzer.ALL_INVESTING_IDS.keys())[:16]
            
            results = self.dj_analyzer.batch_analysis(tickers, batch_size=5)
            self.dj_analyzer.generate_report(results)
            
            if results:
                self.save_dj_results_to_csv(results)
                self.generate_dj_html(results)
            
            print(f"\n✅ ANÁLISIS DJ COMPLETADO: {len(results)} sectores procesados")
            return results
            
        except Exception as e:
            print(f"❌ Error en análisis DJ: {e}")
            traceback.print_exc()
            return []
    
    def run_enhanced_opportunities_analysis(self, recent_days=14):
        """NUEVO: Ejecuta análisis Enhanced Opportunities"""
        print("\n🎯 EJECUTANDO ANÁLISIS ENHANCED OPPORTUNITIES")
        print("=" * 60)
        
        try:
            enhanced_results = self.enhanced_analyzer.run_enhanced_analysis(recent_days)
            
            if 'error' in enhanced_results:
                print(f"❌ Error en Enhanced Opportunities: {enhanced_results['error']}")
                return None
            
            print(f"✅ ENHANCED OPPORTUNITIES COMPLETADO")
            return enhanced_results
            
        except Exception as e:
            print(f"❌ Error en Enhanced Opportunities: {e}")
            traceback.print_exc()
            return None
    
    def upload_enhanced_to_github_pages(self, enhanced_results):
        """NUEVO: Sube análisis Enhanced Opportunities a GitHub Pages"""
        try:
            if not enhanced_results:
                return None
            
            summary = enhanced_results.get('summary', {})
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            
            # Información para el título
            total_opportunities = summary.get('total_opportunities', 0)
            critical_count = summary.get('critical_count', 0)
            with_insider = summary.get('with_insider_activity', 0)
            avg_score = summary.get('average_score', 0)
            
            title = f"🎯 Enhanced Opportunities - {critical_count} críticas de {total_opportunities} - Score {avg_score} - {timestamp}"
            description = f"Análisis avanzado de oportunidades con correlaciones insider-sector. {critical_count} oportunidades críticas, {with_insider} con actividad insider"
            
            result = self.github_uploader.upload_report(
                enhanced_results['html_path'],
                enhanced_results['csv_path'],
                title,
                description
            )
            
            if result:
                print(f"✅ Enhanced Opportunities subido a GitHub Pages:")
                print(f"   🌐 URL: {result['github_url']}")
                return result
            else:
                print("❌ Error subiendo Enhanced Opportunities")
                return None
                
        except Exception as e:
            print(f"❌ Error subiendo Enhanced Opportunities: {e}")
            return None
    
    def run_market_breadth_analysis(self):
        """Ejecuta análisis de amplitud de mercado COMPLETO"""
        print("\n📊 EJECUTANDO ANÁLISIS DE AMPLITUD DE MERCADO COMPLETO")
        print("=" * 60)
        
        try:
            if not MARKET_BREADTH_AVAILABLE:
                print("❌ Market Breadth Analyzer no disponible")
                return None
            
            analyzer = MarketBreadthAnalyzer()
            
            print("🚀 Ejecutando análisis con TODOS los indicadores NYSE disponibles...")
            analysis_result = analyzer.run_breadth_analysis(include_nyse=True, nyse_mode='all',include_sector_breadth=True )
            
            if analysis_result:
                nyse_count = len(analysis_result.get('nyse_data', {}))
                indices_count = len(analysis_result.get('indices_data', {}))
                total_indicators = nyse_count + indices_count
                
                print(f"✅ Market Breadth COMPLETO:")
                print(f"   📊 Índices analizados: {indices_count}")
                print(f"   🏛️ Indicadores NYSE: {nyse_count}")
                print(f"   🎯 TOTAL indicadores: {total_indicators}")
                print(f"   📈 Modo usado: {analysis_result.get('nyse_mode_used', 'all')}")
                
                # Guardar CSV
                csv_path = analyzer.save_to_csv(analysis_result)
                
                # Generar HTML
                html_generator = MarketBreadthHTMLGenerator(self.github_uploader.base_url)
                html_content = html_generator.generate_breadth_html(analysis_result)
                
                if html_content:
                    html_path = "reports/market_breadth_report.html"
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    print(f"✅ HTML generado: {html_path}")
                    
                    return {
                        'analysis_result': analysis_result,
                        'html_path': html_path,
                        'csv_path': csv_path
                    }
                else:
                    print("❌ Error generando HTML")
                    return None
            else:
                print("❌ Error en análisis")
                return None
                
        except Exception as e:
            print(f"❌ Error en análisis de amplitud: {e}")
            traceback.print_exc()
            return None
    
    def upload_breadth_to_github_pages(self, breadth_results):
        """Sube análisis de amplitud a GitHub Pages"""
        try:
            if not breadth_results:
                return None
            
            analysis_result = breadth_results['analysis_result']
            summary = analysis_result['summary']
            timestamp = analysis_result['analysis_date']
            
            # Información mejorada para el título
            nyse_count = analysis_result.get('nyse_indicators_count', 0)
            indices_count = analysis_result.get('indices_count', 0)
            total_indicators = analysis_result.get('total_indicators', nyse_count + indices_count)
            
            title = f"📊 Market Breadth COMPLETO - {total_indicators} indicadores - {summary['market_bias']} - {timestamp}"
            description = f"Análisis completo de amplitud con {nyse_count} indicadores NYSE + {indices_count} índices. Sesgo: {summary['market_bias']} ({summary['bullish_signals']} alcistas, {summary['bearish_signals']} bajistas)"
            
            result = self.github_uploader.upload_report(
                breadth_results['html_path'],
                breadth_results['csv_path'],
                title,
                description
            )
            
            if result:
                print(f"✅ Market Breadth COMPLETO subido a GitHub Pages:")
                print(f"   🌐 URL: {result['github_url']}")
                return result
            else:
                print("❌ Error subiendo Market Breadth")
                return None
                
        except Exception as e:
            print(f"❌ Error subiendo Market Breadth: {e}")
            return None
    
    def save_dj_results_to_csv(self, results):
        """Guarda los resultados del análisis DJ en CSV"""
        try:
            if not results:
                return False
            
            df_data = []
            for r in results:
                df_data.append({
                    'Ticker': r['ticker'],
                    'Sector': r['sector'], 
                    'CurrentPrice': r['current_price'],
                    'Min52w': r['min_52w'],
                    'Max52w': r['max_52w'],
                    'DistanceFromMin': r['distance_pct'],
                    'RSI': r['rsi'],
                    'Estado': r['estado'],
                    'Classification': r['classification'],
                    'DataPoints': r['data_points'],
                    'AnalysisDate': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            
            df = pd.DataFrame(df_data)
            csv_path = "reports/dj_sectorial_analysis.csv"
            df.to_csv(csv_path, index=False)
            print(f"✅ CSV DJ guardado: {csv_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error guardando CSV DJ: {e}")
            return False
    
    def generate_dj_html(self, results):
        """Genera HTML para análisis DJ usando templates externos"""
        print("\n📄 GENERANDO HTML DJ SECTORIAL")
        print("=" * 50)
        
        try:
            html_path = "reports/dj_sectorial_report.html"
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            
            if self.html_generator:
                html_content = self.html_generator.generate_dj_sectorial_html(results, timestamp)
            else:
                html_content = self._generate_basic_dj_html_fallback(results, timestamp)
            
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"✅ HTML DJ generado: {html_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error generando HTML DJ: {e}")
            traceback.print_exc()
            return False
    
    def _generate_basic_dj_html_fallback(self, results, timestamp):
        """Fallback básico para HTML DJ si no hay templates"""
        total_sectores = len(results) if results else 0
        oportunidades = len([r for r in results if r['classification'] == 'OPORTUNIDAD']) if results else 0
        
        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>DJ Sectorial Report</title>
<style>body{{background:#0a0e1a;color:white;font-family:Arial;margin:20px;}}
h1{{color:#4a90e2;}}table{{width:100%;border-collapse:collapse;}}
th,td{{border:1px solid #4a5568;padding:8px;}}th{{background:#4a90e2;}}</style>
</head><body><h1>📊 DJ Sectorial - {timestamp}</h1>
<p>Total: {total_sectores} | Oportunidades: {oportunidades}</p><table>
<tr><th>Sector</th><th>Precio</th><th>Distancia</th><th>Estado</th></tr>"""
        
        if results:
            for r in sorted(results, key=lambda x: x['distance_pct']):
                html += f"<tr><td>{r['sector']}</td><td>${r['current_price']:.2f}</td><td>{r['distance_pct']:.1f}%</td><td>{r['estado']}</td></tr>"
        
        html += "</table></body></html>"
        return html
    
    def upload_github_pages(self):
        """Sube reporte insider a GitHub Pages"""
        print("\n🌐 SUBIENDO INSIDER A GITHUB PAGES")
        print("=" * 50)
        
        try:
            df = pd.read_csv(self.csv_path) if os.path.exists(self.csv_path) else pd.DataFrame()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            
            if len(df) > 0:
                title = f"📊 Insider Trading - {len(df)} transacciones - {timestamp}"
                description = f"Reporte con {len(df)} transacciones detectadas"
            else:
                title = f"📊 Monitoreo Insider Trading - {timestamp}"
                description = "Monitoreo completado sin transacciones"
            
            result = self.github_uploader.upload_report(
                self.html_path,
                self.csv_path,
                title,
                description
            )
            
            if result:
                print(f"✅ Subido a GitHub Pages: {result['github_url']}")
                return result
            else:
                print("❌ Error subiendo a GitHub Pages")
                return None
                
        except Exception as e:
            print(f"❌ Error con GitHub Pages: {e}")
            traceback.print_exc()
            return None
    
    def upload_dj_to_github_pages(self, dj_results):
        """Sube análisis DJ a GitHub Pages"""
        try:
            print("🌐 Subiendo DJ Sectorial a GitHub Pages...")
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            
            if dj_results:
                oportunidades = len([r for r in dj_results if r['classification'] == 'OPORTUNIDAD'])
                title = f"📊 DJ Sectorial - {oportunidades} oportunidades - {timestamp}"
                description = f"Análisis sectorial Dow Jones con {len(dj_results)} sectores analizados"
            else:
                title = f"📊 DJ Sectorial - Sin datos - {timestamp}"
                description = f"Análisis sectorial completado sin datos disponibles"
            
            html_path = "reports/dj_sectorial_report.html"
            csv_path = "reports/dj_sectorial_analysis.csv"
            
            if os.path.exists(html_path) and os.path.exists(csv_path):
                result = self.github_uploader.upload_report(
                    html_path,
                    csv_path,
                    title,
                    description
                )
                
                if result:
                    print(f"✅ DJ Sectorial subido a GitHub Pages: {result['github_url']}")
                    return result
                else:
                    print("❌ Error subiendo DJ Sectorial")
                    return None
            else:
                print("❌ Archivos DJ no encontrados para subir")
                return None
                
        except Exception as e:
            print(f"❌ Error subiendo DJ a GitHub Pages: {e}")
            return None
    
    def run_daily_ultra_enhanced_analysis(self, dj_mode="principales", include_breadth=True, include_enhanced=True):
        """NUEVO: Análisis diario ULTRA MEJORADO - Insider + DJ + Market Breadth + Enhanced Opportunities"""
        print("\n🌟 ANÁLISIS DIARIO ULTRA MEJORADO - INSIDER + DJ + BREADTH + ENHANCED OPPORTUNITIES")
        print("=" * 90)
        print(f"📅 Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        results = {
            'insider_scraper': False,
            'insider_html': False,
            'dj_analysis': False,
            'dj_html': False,
            'breadth_analysis': False,
            'breadth_html': False,
            'enhanced_analysis': False,  # NUEVO
            'enhanced_html': False,      # NUEVO
            'github_insider': None,
            'github_dj': None,
            'github_breadth': None,
            'github_enhanced': None,     # NUEVO
            'telegram': False
        }
        
        try:
            # FASE 1: INSIDER TRADING
            print("\n🔸 FASE 1: INSIDER TRADING")
            print("=" * 40)
            
            results['insider_scraper'] = self.run_scraper()
            if results['insider_scraper']:
                results['insider_html'] = self.generate_html()
                results['github_insider'] = self.upload_github_pages()
            
            # FASE 2: DJ SECTORIAL
            print("\n🔸 FASE 2: DJ SECTORIAL")
            print("=" * 40)
            
            dj_analysis_results = self.run_dj_sectorial_analysis(dj_mode)
            results['dj_analysis'] = len(dj_analysis_results) > 0
            
            if results['dj_analysis']:
                results['dj_html'] = True
                results['github_dj'] = self.upload_dj_to_github_pages(dj_analysis_results)
            
            # FASE 3: MARKET BREADTH COMPLETO
            breadth_results = None
            if include_breadth and MARKET_BREADTH_AVAILABLE:
                print("\n🔸 FASE 3: MARKET BREADTH COMPLETO (60+ INDICADORES)")
                print("=" * 40)
                
                breadth_results = self.run_market_breadth_analysis()
                results['breadth_analysis'] = breadth_results is not None
                
                if results['breadth_analysis']:
                    results['breadth_html'] = True
                    results['github_breadth'] = self.upload_breadth_to_github_pages(breadth_results)
            else:
                print("\n⚠️ FASE 3: MARKET BREADTH OMITIDA")
            
            # FASE 4: ENHANCED OPPORTUNITIES (NUEVO)
            enhanced_results = None
            if include_enhanced:
                print("\n🔸 FASE 4: ENHANCED OPPORTUNITIES (CORRELACIONES AVANZADAS)")
                print("=" * 40)
                
                enhanced_results = self.run_enhanced_opportunities_analysis()
                results['enhanced_analysis'] = enhanced_results is not None
                
                if results['enhanced_analysis']:
                    results['enhanced_html'] = True
                    results['github_enhanced'] = self.upload_enhanced_to_github_pages(enhanced_results)
            else:
                print("\n⚠️ FASE 4: ENHANCED OPPORTUNITIES OMITIDA")
            
            # FASE 5: NOTIFICACIÓN TELEGRAM
            print("\n🔸 FASE 5: NOTIFICACIÓN TELEGRAM")
            print("=" * 40)
            
            results['telegram'] = self.send_ultra_enhanced_telegram_report(results, dj_analysis_results, breadth_results, enhanced_results)
            
            self.create_bundle()
            
            # Resumen final ULTRA MEJORADO
            print("\n" + "=" * 90)
            print("🎉 RESUMEN ANÁLISIS ULTRA MEJORADO")
            print("=" * 90)
            print(f"🏛️ Insider Trading:")
            print(f"   • Scraper: {'✓' if results['insider_scraper'] else '✗'}")
            print(f"   • HTML: {'✓' if results['insider_html'] else '✗'}")
            print(f"   • GitHub Pages: {'✓' if results['github_insider'] else '✗'}")
            
            print(f"📊 DJ Sectorial:")
            print(f"   • Análisis: {'✓' if results['dj_analysis'] else '✗'}")
            print(f"   • HTML: {'✓' if results['dj_html'] else '✗'}")
            print(f"   • GitHub Pages: {'✓' if results['github_dj'] else '✗'}")
            
            print(f"📈 Market Breadth COMPLETO:")
            print(f"   • Análisis: {'✓' if results['breadth_analysis'] else '✗'}")
            if results['breadth_analysis'] and breadth_results:
                analysis_result = breadth_results['analysis_result']
                nyse_count = analysis_result.get('nyse_indicators_count', 0)
                indices_count = analysis_result.get('indices_count', 0)
                total_indicators = analysis_result.get('total_indicators', nyse_count + indices_count)
                print(f"   • Indicadores: {total_indicators} TOTAL ({nyse_count} NYSE + {indices_count} índices)")
            print(f"   • HTML: {'✓' if results['breadth_html'] else '✗'}")
            print(f"   • GitHub Pages: {'✓' if results['github_breadth'] else '✗'}")
            
            print(f"🎯 Enhanced Opportunities:")  # NUEVO
            print(f"   • Análisis: {'✓' if results['enhanced_analysis'] else '✗'}")
            if results['enhanced_analysis'] and enhanced_results:
                summary = enhanced_results.get('summary', {})
                total_opps = summary.get('total_opportunities', 0)
                critical_count = summary.get('critical_count', 0)
                with_insider = summary.get('with_insider_activity', 0)
                print(f"   • Oportunidades: {total_opps} ({critical_count} críticas, {with_insider} con insider)")
            print(f"   • HTML: {'✓' if results['enhanced_html'] else '✗'}")
            print(f"   • GitHub Pages: {'✓' if results['github_enhanced'] else '✗'}")
            
            print(f"📱 Telegram: {'✓' if results['telegram'] else '✗'}")
            
            # URLs de GitHub Pages
            base_url = "https://tantancansado.github.io/stock_analyzer_a"
            if results['github_insider']:
                insider_url = results['github_insider'].get('github_url', f"{base_url}/reports/daily/") if isinstance(results['github_insider'], dict) else f"{base_url}/reports/daily/"
                github_links += f"\n🏛️ [Ver Insider Trading]({insider_url})"
            if results['github_dj']:
                dj_url = results['github_dj'].get('github_url', f"{base_url}/reports/dj_sectorial/index.html") if isinstance(results['github_dj'], dict) else f"{base_url}/reports/dj_sectorial/index.html"
                github_links += f"\n📊 [Ver DJ Sectorial]({dj_url})"
            if results['github_breadth']:
                breadth_url = results['github_breadth'].get('github_url', f"{base_url}/reports/market_breadth/index.html") if isinstance(results['github_breadth'], dict) else f"{base_url}/reports/market_breadth/index.html"
                github_links += f"\n📈 [Ver Market Breadth COMPLETO]({breadth_url})"
            if results['github_enhanced']:
                enhanced_url = results['github_enhanced'].get('github_url', f"{base_url}/reports/enhanced_opportunities/index.html") if isinstance(results['github_enhanced'], dict) else f"{base_url}/reports/enhanced_opportunities/index.html"
                github_links += f"\n🎯 [Ver Enhanced Opportunities]({enhanced_url})"
            
            return results
            
        except Exception as e:
            print(f"\n❌ Error crítico en análisis ultra mejorado: {e}")
            traceback.print_exc()
            return results
    
    def send_ultra_enhanced_telegram_report(self, results, dj_analysis_results, breadth_results, enhanced_results):
        """NUEVO: Envía reporte ultra mejorado por Telegram con Enhanced Opportunities"""
        try:
            from config import TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN
            from alerts.telegram_utils import send_message, send_file
            
            if not TELEGRAM_CHAT_ID or not TELEGRAM_BOT_TOKEN:
                print("❌ Configuración Telegram incompleta")
                return False
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            
            # Estadísticas Insider
            insider_stats = ""
            if os.path.exists(self.csv_path):
                df = pd.read_csv(self.csv_path)
                if len(df) > 0:
                    insider_stats = f"""🏛️ **Insider Trading:**
• {len(df)} transacciones detectadas
• {df['Insider'].nunique()} empresas únicas
• Estado: {'✅ Subido' if results['github_insider'] else '❌ Error'}"""
                else:
                    insider_stats = f"""🏛️ **Insider Trading:**
• Sin transacciones detectadas
• Estado: {'✅ Monitoreado' if results['insider_scraper'] else '❌ Error'}"""
            
            # Estadísticas DJ Sectorial
            dj_stats = ""
            if dj_analysis_results:
                oportunidades = len([r for r in dj_analysis_results if r['classification'] == 'OPORTUNIDAD'])
                cerca = len([r for r in dj_analysis_results if r['classification'] == 'CERCA'])
                fuertes = len([r for r in dj_analysis_results if r['classification'] == 'FUERTE'])
                
                dj_stats = f"""📊 **DJ Sectorial:**
• {len(dj_analysis_results)} sectores analizados
• 🟢 {oportunidades} oportunidades
• 🟡 {cerca} cerca del mínimo
• 🔴 {fuertes} en zona fuerte
• Estado: {'✅ Subido' if results['github_dj'] else '❌ Error'}"""
            else:
                dj_stats = f"""📊 **DJ Sectorial:**
• Sin datos disponibles
• Estado: {'❌ Error en análisis' if results['dj_analysis'] else '⚠️ Sin ejecutar'}"""
            
            # Estadísticas Market Breadth
            breadth_stats = ""
            if breadth_results and results['breadth_analysis']:
                analysis_result = breadth_results['analysis_result']
                summary = analysis_result['summary']
                nyse_count = analysis_result.get('nyse_indicators_count', 0)
                indices_count = analysis_result.get('indices_count', 0)
                total_indicators = analysis_result.get('total_indicators', nyse_count + indices_count)
                nyse_mode = analysis_result.get('nyse_mode_used', 'all')
                
                breadth_stats = f"""📈 **Market Breadth COMPLETO:**
• 🎯 {total_indicators} indicadores totales (MODO: {nyse_mode.upper()})
• 🏛️ {nyse_count} indicadores NYSE reales
• 📊 {indices_count} índices principales
• Sesgo: {summary['market_bias']}
• Confianza: {summary['confidence']}
• 🟢 {summary['bullish_signals']} señales alcistas
• 🔴 {summary['bearish_signals']} señales bajistas
• Estado: {'✅ Subido' if results['github_breadth'] else '❌ Error'}"""
            else:
                breadth_stats = f"""📈 **Market Breadth:**
• Análisis de amplitud de mercado COMPLETO
• Estado: {'❌ Error' if MARKET_BREADTH_AVAILABLE else '⚠️ No disponible'}"""
            
            # Estadísticas Enhanced Opportunities (NUEVO)
            enhanced_stats = ""
            if enhanced_results and results['enhanced_analysis']:
                summary = enhanced_results.get('summary', {})
                enhanced_analysis = enhanced_results.get('enhanced_analysis', {})
                market_overview = enhanced_analysis.get('market_overview', {})
                
                total_opps = summary.get('total_opportunities', 0)
                critical_count = summary.get('critical_count', 0)
                with_insider = summary.get('with_insider_activity', 0)
                avg_score = summary.get('average_score', 0)
                mapping_coverage = summary.get('mapping_coverage', 0)
                market_state = market_overview.get('market_state', 'N/A')
                
                enhanced_stats = f"""🎯 **Enhanced Opportunities:**
• 🔍 {total_opps} oportunidades analizadas
• 🚨 {critical_count} oportunidades CRÍTICAS
• 👥 {with_insider} con actividad insider
• ⭐ Score promedio: {avg_score}/100
• 🎯 Mapeo ticker-sector: {mapping_coverage:.1f}%
• 📈 Estado mercado: {market_state}
• Estado: {'✅ Subido' if results['github_enhanced'] else '❌ Error'}"""
            else:
                enhanced_stats = f"""🎯 **Enhanced Opportunities:**
• Análisis de correlaciones insider-sector
• Estado: {'❌ Error en análisis' if results['enhanced_analysis'] else '⚠️ Sin ejecutar'}"""

            # Estadísticas Investment Thesis (NUEVO)
            thesis_stats = ""
            theses_file = "docs/theses.json"
            if os.path.exists(theses_file):
                try:
                    import json
                    with open(theses_file, 'r') as f:
                        theses_data = json.load(f)

                    num_theses = len(theses_data)
                    # Calcular ratings promedio
                    ratings = [t.get('rating', {}).get('overall', 0) for t in theses_data.values() if 'rating' in t]
                    avg_rating = sum(ratings) / len(ratings) if ratings else 0
                    top_rated = max(ratings) if ratings else 0

                    # Contar tesis por tier
                    tier_counts = {}
                    for t in theses_data.values():
                        tier = t.get('overview', {}).get('tier', 'N/A')
                        tier_counts[tier] = tier_counts.get(tier, 0) + 1

                    thesis_stats = f"""📄 **Investment Thesis:**
• 📊 {num_theses} tesis generadas
• ⭐ Rating promedio: {avg_rating:.1f}/5
• 🏆 Mejor rating: {top_rated:.1f}/5
• 🎯 Con setup técnico fuerte: {len([r for r in ratings if r >= 3])}
• Estado: ✅ Actualizado"""
                except:
                    thesis_stats = f"""📄 **Investment Thesis:**
• Estado: ⚠️ Error al leer datos"""
            else:
                thesis_stats = f"""📄 **Investment Thesis:**
• Sistema de análisis narrativo completo
• Estado: ⚠️ No generado aún"""

            # URLs de GitHub Pages
            base_url = "https://tantancansado.github.io/stock_analyzer_a"
            github_links = ""
            if results['github_insider']:
                insider_url = results['github_insider'].get('github_url', f"{base_url}/reports/daily/") if isinstance(results['github_insider'], dict) else f"{base_url}/reports/daily/"
                github_links += f"\n🏛️ [Ver Insider Trading]({insider_url})"
            if results['github_dj']:
                dj_url = results['github_dj'].get('github_url', f"{base_url}/reports/dj_sectorial/index.html") if isinstance(results['github_dj'], dict) else f"{base_url}/reports/dj_sectorial/index.html"
                github_links += f"\n📊 [Ver DJ Sectorial]({dj_url})"
            if results['github_breadth']:
                breadth_url = results['github_breadth'].get('github_url', f"{base_url}/reports/market_breadth/index.html") if isinstance(results['github_breadth'], dict) else f"{base_url}/reports/market_breadth/index.html"
                github_links += f"\n📈 [Ver Market Breadth COMPLETO]({breadth_url})"
            if results['github_enhanced']:
                enhanced_url = results['github_enhanced'].get('github_url', f"{base_url}/reports/enhanced_opportunities/index.html") if isinstance(results['github_enhanced'], dict) else f"{base_url}/reports/enhanced_opportunities/index.html"
                github_links += f"\n🎯 [Ver Enhanced Opportunities]({enhanced_url})"

            # Link a Investment Thesis
            if os.path.exists("docs/theses.json"):
                github_links += f"\n📄 [Ver Investment Thesis]({base_url}/super_opportunities_4d.html)"

            if github_links:
                base_url = "https://tantancansado.github.io/stock_analyzer_a"
                github_links += f"\n🏠 [Dashboard Principal]({base_url})"
            
            mensaje = f"""🌟 **REPORTE TRADING ULTRA MEJORADO**

📅 **{timestamp}**

{insider_stats}

{dj_stats}

{breadth_stats}

{enhanced_stats}

{thesis_stats}

🌐 **Enlaces GitHub Pages:**{github_links}

📄 **Archivos CSV adjuntos para análisis detallado**"""
            
            send_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, mensaje)
            
            # Enviar archivos CSV
            files_sent = 0
            
            # CSV Insider
            if os.path.exists(self.csv_path):
                if send_file(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, self.csv_path, "📊 Datos Insider Trading"):
                    files_sent += 1
            
            # CSV DJ Sectorial
            csv_dj_path = "reports/dj_sectorial_analysis.csv"
            if os.path.exists(csv_dj_path):
                if send_file(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, csv_dj_path, "📈 Datos DJ Sectorial"):
                    files_sent += 1
            
            # CSV Market Breadth COMPLETO
            csv_breadth_path = "reports/market_breadth_analysis.csv"
            if os.path.exists(csv_breadth_path) and results['breadth_analysis']:
                caption = "📊 Datos Market Breadth COMPLETO"
                if breadth_results:
                    total_indicators = breadth_results['analysis_result'].get('total_indicators', 0)
                    caption += f" ({total_indicators} indicadores)"
                
                if send_file(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, csv_breadth_path, caption):
                    files_sent += 1
            
            # CSV Enhanced Opportunities (NUEVO)
            if enhanced_results and 'csv_path' in enhanced_results:
                csv_enhanced_path = enhanced_results['csv_path']
                if os.path.exists(csv_enhanced_path):
                    caption = "🎯 Datos Enhanced Opportunities"
                    if enhanced_results:
                        summary = enhanced_results.get('summary', {})
                        critical_count = summary.get('critical_count', 0)
                        caption += f" ({critical_count} críticas)"
                    
                    if send_file(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, csv_enhanced_path, caption):
                        files_sent += 1
            
            print(f"✅ Telegram ultra mejorado enviado - {files_sent} archivos adjuntados")
            return True
            
        except Exception as e:
            print(f"❌ Error enviando reporte ultra mejorado: {e}")
            return False
    
    def generate_html(self):
        """Genera el HTML con los datos del CSV usando templates externos"""
        print("\n📄 GENERANDO HTML INSIDER TRADING")
        print("=" * 50)
        
        try:
            if not os.path.exists(self.csv_path):
                print("❌ CSV no encontrado")
                return False
            
            try:
                from alerts.plot_utils import crear_html_moderno_finviz
                self.html_path = crear_html_moderno_finviz()
                return self.html_path is not None
            except ImportError:
                print("⚠️ plot_utils no disponible, usando templates propios")
                return self.generate_insider_html_with_templates()
                
        except Exception as e:
            print(f"❌ Error generando HTML: {e}")
            return False
    
    def generate_insider_html_with_templates(self):
        """Genera HTML de insider trading usando templates externos"""
        try:
            df = pd.read_csv(self.csv_path)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            
            if self.html_generator:
                html_content = self.html_generator.generate_insider_trading_html(df, timestamp)
            else:
                html_content = self._generate_basic_insider_html_fallback(df, timestamp)
            
            with open(self.html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"✅ HTML Insider generado: {self.html_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error generando HTML Insider con templates: {e}")
            return False
    
    def _generate_basic_insider_html_fallback(self, df, timestamp):
        """Fallback básico para HTML Insider si no hay templates"""
        total_transactions = len(df)
        unique_companies = df['Insider'].nunique() if 'Insider' in df.columns else 0
        
        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Insider Trading Report</title>
<style>body{{background:#0a0e1a;color:white;font-family:Arial;margin:20px;}}
h1{{color:#4a90e2;}}table{{width:100%;border-collapse:collapse;}}
th,td{{border:1px solid #4a5568;padding:8px;}}th{{background:#4a90e2;}}
tr:nth-child(even){{background:#2d3748;}}</style>
</head><body><h1>🏛️ Insider Trading - {timestamp}</h1>
<p>Total: {total_transactions} | Empresas: {unique_companies}</p><table>
<tr><th>Ticker</th><th>Company</th><th>Price</th><th>Qty</th><th>Value</th><th>Type</th></tr>"""
        
        for _, row in df.head(50).iterrows():
            html += f"<tr><td>{row.get('Insider', 'N/A')}</td><td>{row.get('Title', 'N/A')}</td><td>{row.get('Price', 'N/A')}</td><td>{row.get('Qty', 'N/A')}</td><td>{row.get('Value', 'N/A')}</td><td>{row.get('Type', 'N/A')}</td></tr>"
        
        html += "</table></body></html>"
        return html
    
    def create_bundle(self):
        """Crea un ZIP con todos los archivos"""
        print("\n📦 CREANDO BUNDLE")
        print("=" * 50)
        
        try:
            with zipfile.ZipFile(self.bundle_path, 'w') as zipf:
                if os.path.exists(self.html_path):
                    zipf.write(self.html_path, arcname=os.path.basename(self.html_path))
                if os.path.exists(self.csv_path):
                    zipf.write(self.csv_path, arcname=os.path.basename(self.csv_path))
                
                dj_html = "reports/dj_sectorial_report.html"
                dj_csv = "reports/dj_sectorial_analysis.csv"
                if os.path.exists(dj_html):
                    zipf.write(dj_html, arcname="dj_sectorial_report.html")
                if os.path.exists(dj_csv):
                    zipf.write(dj_csv, arcname="dj_sectorial_data.csv")
                
                # Añadir archivos Market Breadth al bundle
                breadth_html = "reports/market_breadth_report.html"
                breadth_csv = "reports/market_breadth_analysis.csv"
                if os.path.exists(breadth_html):
                    zipf.write(breadth_html, arcname="market_breadth_report.html")
                if os.path.exists(breadth_csv):
                    zipf.write(breadth_csv, arcname="market_breadth_data.csv")
                
                # Añadir archivos Enhanced Opportunities al bundle (NUEVO)
                enhanced_files = [f for f in os.listdir("reports") if f.startswith("enhanced_trading_analysis_")]
                for enhanced_file in enhanced_files:
                    file_path = f"reports/{enhanced_file}"
                    if os.path.exists(file_path):
                        zipf.write(file_path, arcname=enhanced_file)
            
            print(f"✅ Bundle creado: {self.bundle_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error creando bundle: {e}")
            return False
    
    def send_telegram(self):
        """Envía reporte por Telegram"""
        print("\n📱 ENVIANDO POR TELEGRAM")
        print("=" * 50)
        
        try:
            try:
                from config import TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN
            except ImportError:
                print("❌ config.py no encontrado")
                return False
            
            if not TELEGRAM_CHAT_ID or not TELEGRAM_BOT_TOKEN:
                print("❌ Configuración Telegram incompleta")
                return False
            
            try:
                from alerts.telegram_utils import send_message, send_file
            except ImportError:
                print("❌ telegram_utils no encontrado")
                return False
            
            df = pd.read_csv(self.csv_path) if os.path.exists(self.csv_path) else pd.DataFrame()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            
            mensaje = f"""📊 REPORTE INSIDER TRADING

📅 Fecha: {timestamp}
📊 Transacciones: {len(df)}
🏢 Empresas: {df['Insider'].nunique() if 'Insider' in df.columns and len(df) > 0 else 0}

📄 Archivos adjuntos"""
            
            send_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, mensaje)
            
            if os.path.exists(self.html_path):
                send_file(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, self.html_path)
            
            if os.path.exists(self.csv_path):
                send_file(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, self.csv_path)
            
            print("✅ Enviado por Telegram")
            return True
            
        except Exception as e:
            print(f"❌ Error enviando por Telegram: {e}")
            traceback.print_exc()
            return False

def run_vcp_scanner_usa_interactive():
    """Flujo interactivo para escanear TODO el mercado USA con el VCP Scanner avanzado."""
    import os
    from datetime import datetime

    print("\n🎯 ESCANEO AVANZADO DE TODO EL MERCADO USA (VCP Scanner)")
    print("=" * 60)
    scanner = VCPScannerEnhanced()
    print("🔍 Ejecutando escaneo de mercado USA...")
    try:
        results = scanner.scan_market()
    except Exception as e:
        print(f"❌ Error ejecutando el escaneo: {e}")
        return
    num_candidates = len(results) if results is not None else 0
    print(f"✅ Escaneo completado. Candidatos detectados: {num_candidates}")
    if num_candidates == 0:
        print("⚠️  No se detectaron candidatos.")
    
    gen_html = input("¿Quieres generar HTML con los resultados? (s/n): ").strip().lower()
    if gen_html != "s":
        print("🛑 Proceso finalizado (no se generó HTML).")
        return
    
    html_path = "reports/vcp_market_scan.html"
    csv_path = "reports/vcp_market_scan.csv"
    try:
        if results is not None:
            scanner.save_csv(results, csv_path)
        scanner.generate_html(results, html_path)
        print(f"✅ HTML generado: {html_path}")
    except Exception as e:
        print(f"❌ Error generando HTML: {e}")
        return
    
    subir = input("¿Quieres subir el HTML a GitHub Pages? (s/n): ").strip().lower()
    if subir != "s":
        print("🛑 Proceso finalizado (HTML no subido a GitHub Pages).")
        return
    
    try:
        system = InsiderTradingSystem()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        title = f"🎯 VCP Market Scanner - {num_candidates} candidatos - {timestamp}"
        description = f"Reporte avanzado de escaneo de TODO el mercado USA. Candidatos detectados: {num_candidates}."
        
        result = system.github_uploader.upload_report(
            html_path,
            csv_path,
            title,
            description
        )
        
        if result:
            print("✅ Subido a GitHub Pages:")
            print(f"   {result['github_url']}")
        else:
            print("❌ Error subiendo a GitHub Pages")
    except Exception as e:
        print(f"❌ Error subiendo a GitHub Pages: {e}")
        return
    print("🎉 Proceso de escaneo avanzado finalizado.")

def test_components():
    """Prueba cada componente individualmente"""
    print("\n🔧 MODO TEST - VERIFICANDO COMPONENTES")
    print("=" * 60)
    
    # 1. Verificar archivos necesarios
    print("\n📁 Verificando archivos:")
    files_to_check = [
        ("Scraper", ["insiders/openinsider_scraper.py", "openinsider_scraper.py"]),
        ("Plot Utils", ["alerts/plot_utils.py"]),
        ("Config", ["config.py"]),
        ("Telegram Utils", ["alerts/telegram_utils.py"]),
        ("Templates HTML", ["templates/html_generator.py"]),
        ("Templates GitHub", ["templates/github_pages_templates.py"]),
        ("Market Breadth", ["market_breadth_analyzer.py"]),
        ("Enhanced Opportunities", ["super_score_integrator.py"])
    ]
    
    for name, paths in files_to_check:
        found = False
        for path in paths:
            if os.path.exists(path):
                print(f"✅ {name}: {path}")
                found = True
                break
        if not found:
            print(f"❌ {name}: NO ENCONTRADO")
    
    # 2. Verificar CSV existente
    print("\n📊 Verificando datos:")
    if os.path.exists("reports/insiders_daily.csv"):
        try:
            df = pd.read_csv("reports/insiders_daily.csv")
            print(f"✅ CSV existente: {len(df)} registros")
        except Exception as e:
            print(f"❌ CSV corrupto: {e}")
    else:
        print("❌ CSV no existe")
    
    # 3. Test Enhanced Opportunities Analyzer (NUEVO)
    print("\n🎯 Testing Enhanced Opportunities Analyzer:")
    try:
        analyzer = EnhancedTradingOpportunityAnalyzer()
        print("✅ Enhanced Opportunities Analyzer inicializado")
        print(f"✅ {len(analyzer.comprehensive_ticker_mapping)} tickers mapeados")
        
        print("🔄 Probando escaneo de estructura...")
        structure = analyzer.scan_directory_structure()
        print(f"✅ Estructura escaneada: {len(structure['insider_files'])} insider, {len(structure['sector_files'])} sector")
        
    except Exception as e:
        print(f"❌ Error en Enhanced Opportunities: {e}")
    
    # 4. Verificar configuración Telegram
    print("\n📱 Verificando Telegram:")
    try:
        from config import TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN
        if TELEGRAM_CHAT_ID and TELEGRAM_BOT_TOKEN:
            print(f"✅ Chat ID: {TELEGRAM_CHAT_ID}")
            print(f"✅ Token: {TELEGRAM_BOT_TOKEN[:10]}...")
        else:
            print("❌ Configuración incompleta")
    except ImportError:
        print("❌ config.py no importable")

def main():
    """Función principal con menú ACTUALIZADO para Enhanced Opportunities"""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--auto":
            system = InsiderTradingSystem()
            system.run_complete_process()
        elif sys.argv[1] == "--ultra-enhanced":
            mode = sys.argv[2] if len(sys.argv) > 2 else "principales"
            system = InsiderTradingSystem()
            system.run_daily_ultra_enhanced_analysis(mode, include_breadth=True, include_enhanced=True)
        elif sys.argv[1] == "--enhanced":
            system = InsiderTradingSystem()
            enhanced_results = system.run_enhanced_opportunities_analysis()
            if enhanced_results:
                system.upload_enhanced_to_github_pages(enhanced_results)
        elif sys.argv[1] == "--test":
            test_components()
        else:
            # Otros comandos existentes...
            pass
    else:
        # Modo interactivo ACTUALIZADO
        while True:
            print("\n" + "=" * 90)
            print("📊 SISTEMA TRADING UNIFICADO - MENÚ PRINCIPAL")
            print("=" * 90)
            print("🌟 ANÁLISIS DIARIO RECOMENDADO:")
            print("  1. 🚀 ANÁLISIS ULTRA MEJORADO (Insider + DJ + Breadth + Enhanced Opportunities)")
            print("  2. 🔥 ANÁLISIS DIARIO COMPLETO (Insider + DJ Sectorial)")
            print("")
            print("🏛️ INSIDER TRADING:")
            print("  3. 🏛️  Proceso completo Insider Trading")
            print("  4. 🕷️  Solo ejecutar scraper")
            print("  5. 📄 Solo generar HTML")
            print("  6. 📱 Solo enviar Telegram")
            print("")
            print("📊 DJ SECTORIAL ANALYSIS:")
            print("  7. 📈 Análisis principales (16 sectores)")
            print("  8. 🔍 Análisis detallado (35 sectores)")
            print("  9. 🚀 Análisis completo (TODOS los sectores)")
            print(" 10. 📊 Solo análisis DJ (sin subir)")
            print("")
            print("📈 MARKET BREADTH ANALYSIS:")
            print(" 11. 📊 Análisis completo de amplitud (60+ indicadores NYSE)")
            print(" 12. 📈 Solo análisis (sin subir)")
            print("")
            print("🎯 ENHANCED OPPORTUNITIES:")  # NUEVO
            print(" 13. 🎯 Análisis Enhanced Opportunities (correlaciones insider-sector)")
            print(" 14. 🔗 Solo análisis Enhanced (sin subir)")
            print("")
            print("🎯 VCP SCANNER:")
            print(" 15. 🎯 Escanear TODO el mercado USA (VCP Scanner avanzado)")
            print("")
            print("🔧 UTILIDADES:")
            print(" 16. 🔍 Verificar componentes")
            print(" 17. 🌐 Probar GitHub Pages")
            print(" 18. 📱 Test Telegram")
            print("  0. ❌ Salir")
            print("=" * 90)
            print("💡 Recomendado para uso diario: Opción 1 (Ultra Mejorado con Enhanced Opportunities)")
            print("🎯 Enhanced Opportunities: Nueva funcionalidad de correlaciones automáticas")
            print("=" * 90)

            opcion = input("Selecciona opción: ").strip()

            system = InsiderTradingSystem()

            if opcion == "1":
                print("\n🌟 ANÁLISIS ULTRA MEJORADO (ENHANCED OPPORTUNITIES)")
                print("Modo DJ Sectorial:")
                print("  1. Principales (16 sectores) - Rápido")
                print("  2. Detallado (35 sectores) - Medio")
                print("  3. Completo (TODOS) - Lento")
                
                dj_mode_choice = input("Selecciona modo DJ (1/2/3): ").strip()
                if dj_mode_choice == "2":
                    dj_mode = "detallado"
                elif dj_mode_choice == "3":
                    dj_mode = "completo"
                else:
                    dj_mode = "principales"
                
                print(f"\n🚀 Ejecutando análisis ultra mejorado con modo DJ: {dj_mode}")
                print("📊 Market Breadth: TODOS los indicadores NYSE (60+)")
                print("🎯 Enhanced Opportunities: Correlaciones insider-sector automáticas")
                system.run_daily_ultra_enhanced_analysis(dj_mode, include_breadth=True, include_enhanced=True)
                
            elif opcion == "13":
                # Enhanced Opportunities completo con subida
                print("\n🎯 EJECUTANDO ENHANCED OPPORTUNITIES COMPLETO")
                enhanced_results = system.run_enhanced_opportunities_analysis()
                if enhanced_results:
                    system.upload_enhanced_to_github_pages(enhanced_results)
                else:
                    print("❌ Enhanced Opportunities no disponible")
            elif opcion == "14":
                # Enhanced Opportunities solo análisis
                print("\n🎯 EJECUTANDO ENHANCED OPPORTUNITIES SOLO ANÁLISIS")
                enhanced_results = system.run_enhanced_opportunities_analysis()
                if enhanced_results:
                    summary = enhanced_results.get('summary', {})
                    print(f"🎯 Análisis completado: {summary.get('total_opportunities', 0)} oportunidades")
                else:
                    print("❌ Enhanced Opportunities no disponible")
            # ... resto de opciones existentes ...
            elif opcion == "0":
                print("👋 ¡Hasta luego!")
                break
            else:
                print("❌ Opción inválida")

            input("\nPresiona Enter para continuar...")

if __name__ == "__main__":
    main()
